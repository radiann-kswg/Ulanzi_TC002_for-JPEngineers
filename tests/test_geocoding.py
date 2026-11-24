import io
import json
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from bridge import geocoding, weather


def response(data):
    return io.BytesIO(json.dumps(data, ensure_ascii=False).encode("utf-8"))


def point(name, longitude, latitude):
    return {"geometry": {"type": "Point", "coordinates": [longitude, latitude]},
            "properties": {"title": name}}


class GeocodingTests(unittest.TestCase):
    def setUp(self):
        self.urlopen = self.enterContext(patch("bridge.geocoding.urlopen"))
        geocoding._municipalities.cache_clear()
        self.addCleanup(geocoding._municipalities.cache_clear)

    def test_search_escapes_query_and_preserves_coordinates_order_and_cli_shape(self):
        hits = [point("例示公園", 140.5, 35.5), point("例示公園　南口", 140.51, 35.49)]
        query = "例示公園 & A/B #1"
        self.urlopen.side_effect = [response(hits), response(hits)]
        self.assertEqual(geocoding.search(query), [
            geocoding.Place("例示公園", 35.5, 140.5),
            geocoding.Place("例示公園　南口", 35.49, 140.51),
        ])
        request, = self.urlopen.call_args.args
        address = urlsplit(request.full_url)
        self.assertEqual(address.scheme, "https")
        self.assertEqual(address.hostname, "msearch.gsi.go.jp")
        self.assertEqual(parse_qs(address.query), {"q": [query]})
        self.assertTrue(request.get_header("User-agent"))
        self.assertGreater(self.urlopen.call_args.kwargs["timeout"], 0)
        self.assertEqual(weather.search(query), [
            {"name": "例示公園", "lat": 35.5, "lon": 140.5},
            {"name": "例示公園　南口", "lat": 35.49, "lon": 140.51},
        ])

    def test_blank_query_and_invalid_coordinates_do_not_connect(self):
        self.assertEqual(geocoding.search("  "), [])
        for latitude, longitude in [(float("nan"), 0), (91, 0), (0, -181), (True, 0)]:
            with self.subTest(latitude=latitude, longitude=longitude), self.assertRaises(ValueError):
                geocoding.reverse(latitude, longitude)
        self.urlopen.assert_not_called()

    def test_malformed_points_do_not_hide_usable_matches(self):
        self.urlopen.return_value = response([
            None, {"geometry": {"type": "Polygon"}}, {"geometry": None},
            point("範囲外", 181, 0), point("数値以外", 0, False), point("\u0000", 10, 20),
            point("検索結果", 10, 20),
        ])
        self.assertEqual(geocoding.search("結果"), [geocoding.Place("検索結果", 20, 10)])

    def test_reverse_combines_locality_and_municipality_and_reuses_code_table(self):
        address = {"results": {"muniCd": "01234", "lv01Nm": "例示町"}}
        table = 'GSI.MUNI_ARRAY["1234"] = \'1,例示県,1234,例示市　中央区\';'
        self.urlopen.side_effect = [response(address), io.BytesIO(table.encode()), response(address)]
        self.assertEqual(geocoding.reverse(35.5, 140.5), "例示県例示市中央区例示町")
        self.assertEqual(geocoding.reverse(35.51, 140.5), "例示県例示市中央区例示町")
        requests = [call.args[0].full_url for call in self.urlopen.call_args_list]
        self.assertEqual(parse_qs(urlsplit(requests[0]).query), {"lat": ["35.5"], "lon": ["140.5"]})
        self.assertEqual(requests.count(geocoding.MUNICIPALITIES_URL), 1)

    def test_reverse_no_match_and_locality_when_code_table_is_unavailable(self):
        self.urlopen.side_effect = [response({}), response({"results": {"lv01Nm": "例示町"}}),
                                    response({"results": {"muniCd": "12345", "lv01Nm": "例示町"}}),
                                    OSError("offline")]
        self.assertEqual(geocoding.reverse(0, 0), "")
        self.assertEqual(geocoding.reverse(35, 140), "例示町")
        self.assertEqual(geocoding.reverse(35, 140), "例示町")
        self.assertEqual(self.urlopen.call_count, 4)

    def test_unreadable_or_oversized_response_and_connection_error(self):
        self.urlopen.side_effect = [response([]), io.BytesIO(b"{" * (32 * 1024 + 1)),
                                    io.BytesIO(b"\xff"), io.BytesIO(b"<html>"), TimeoutError()]
        for _ in range(5):
            with self.assertRaisesRegex(ValueError, "国土地理院"):
                geocoding.reverse(0, 0)
