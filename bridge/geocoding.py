"""On-demand Japanese place lookups through GSI Maps."""
from dataclasses import dataclass
from functools import cache
from http.client import HTTPException
import json
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen


SEARCH_URL = "https://msearch.gsi.go.jp/address-search/AddressSearch"
REVERSE_URL = "https://mreversegeocoder.gsi.go.jp/reverse-geocoder/LonLatToAddress"
MUNICIPALITIES_URL = "https://maps.gsi.go.jp/js/muni.js"
USER_AGENT = "Ulanzi-TC002-for-JPEngineers/1.0"


@dataclass(frozen=True)
class Place:
    name: str
    latitude: float
    longitude: float


def _read(url, limit):
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=8) as response:
            body = response.read(limit + 1)
    except (OSError, HTTPException) as error:
        raise ValueError("国土地理院に接続できませんでした。通信状態を確認してください。") from error
    if len(body) > limit:
        raise ValueError("国土地理院からの応答が大きすぎます。")
    try:
        return body.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("国土地理院からの応答を読み取れませんでした。") from error


def _json(url, params, limit):
    text = _read(url + "?" + urlencode(params), limit)
    try:
        return json.loads(text)
    except (ValueError, RecursionError) as error:
        raise ValueError("国土地理院からの応答を読み取れませんでした。") from error


def _label(value):
    if not isinstance(value, str):
        return ""
    name = value.strip()
    return name if name.replace("　", " ").isprintable() else ""


def _coordinate(value, limit):
    return type(value) in (int, float) and -limit <= value <= limit


def search(query: str) -> list[Place]:
    query = query.strip()
    if not query:
        return []
    hits = _json(SEARCH_URL, {"q": query}, 4 * 1024 * 1024)
    if not isinstance(hits, list):
        raise ValueError("国土地理院の検索結果を読み取れませんでした。")
    places = []
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        geometry, properties = hit.get("geometry"), hit.get("properties")
        if not isinstance(geometry, dict) or geometry.get("type") != "Point" or not isinstance(properties, dict):
            continue
        coordinates = geometry.get("coordinates")
        if not isinstance(coordinates, list) or len(coordinates) < 2:
            continue
        longitude, latitude = coordinates[:2]
        name = _label(properties.get("title"))
        if name and _coordinate(latitude, 90) and _coordinate(longitude, 180):
            places.append(Place(name, latitude, longitude))
    return places


@cache
def _municipalities():
    # Read the published GSI.MUNI_ARRAY assignments as data. Some keys omit a leading zero.
    source = _read(MUNICIPALITIES_URL, 512 * 1024)
    rows = re.findall(
        r"""GSI\.MUNI_ARRAY\["([0-9]{4,5})"\]\s*=\s*'[0-9]+,([^,'\r\n]+),[0-9]+,([^,'\r\n]+)';""",
        source,
    )
    if not rows:
        raise ValueError("国土地理院の市区町村名を読み取れませんでした。")
    return {code.lstrip("0"): prefecture + city.replace("　", "") for code, prefecture, city in rows}


def reverse(latitude: float, longitude: float) -> str:
    if not _coordinate(latitude, 90) or not _coordinate(longitude, 180):
        raise ValueError("緯度または経度が範囲外です。")
    document = _json(REVERSE_URL, {"lat": latitude, "lon": longitude}, 32 * 1024)
    if not isinstance(document, dict):
        raise ValueError("国土地理院の住所情報を読み取れませんでした。")
    result = document.get("results", {})
    if not isinstance(result, dict):
        raise ValueError("国土地理院の住所情報を読み取れませんでした。")
    locality = _label(result.get("lv01Nm"))
    code = str(result.get("muniCd", ""))
    if not re.fullmatch("[0-9]{4,5}", code):
        return locality
    try:
        municipality = _municipalities().get(code.lstrip("0"), "")
    except ValueError:
        return locality
    return municipality + locality
