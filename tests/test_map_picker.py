import json
from pathlib import Path
import tempfile
from threading import Event
import time
import unittest
from unittest.mock import Mock, patch

try:
    import tkinter as tk
except ImportError:
    tk = None

from bridge.geocoding import Place


@unittest.skipIf(tk is None, "the Windows location picker requires Tk")
class MapPickerTests(unittest.TestCase):
    def setUp(self):
        from studio.map_picker import MapPicker

        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            if "display" in str(error).lower():
                self.skipTest(f"Tk display unavailable: {error}")
            raise
        self.addCleanup(self.root.destroy)
        self.root.withdraw()
        self.enterContext(patch("studio.map_picker.MapCanvas", side_effect=self.create_map))
        self.search = self.enterContext(patch("bridge.geocoding.search", return_value=[]))
        self.reverse = self.enterContext(patch("bridge.geocoding.reverse", return_value=""))
        self.applied = Mock()
        self.picker = MapPicker(self.root, "", "", "", self.applied)
        self.picker.withdraw()

    def create_map(self, parent, on_pick):
        canvas = tk.Canvas(parent)
        canvas.notice = tk.StringVar(canvas)
        canvas.center_at = Mock()
        canvas.set_marker = Mock()
        canvas.zoom_by = Mock()
        canvas.close = Mock()
        self.click_map = on_pick
        return canvas

    def wait_for(self, condition):
        deadline = time.monotonic() + 3
        while not condition():
            if time.monotonic() >= deadline:
                self.fail("The expected picker update did not arrive")
            self.root.update()
            time.sleep(0.005)

    def delay_reply(self, lookup, value):
        started, release = Event(), Event()
        self.addCleanup(release.set)

        def reply(*_args):
            started.set()
            if not release.wait(3):
                raise RuntimeError("Test reply was not released")
            return value

        lookup.side_effect = reply
        return started, release

    def test_choose_search_result_then_use_clicked_location(self):
        self.search.return_value = [Place("東京都庁", 35.6895, 139.6917),
                                    Place("東京駅", 35.6812, 139.7671)]
        self.picker.query.set("東京")
        self.picker.search()
        self.wait_for(lambda: len(self.picker.results_box.cget("values")) == 2)
        self.picker.results_box.current(1)
        self.picker.choose_result()
        self.assertEqual(self.picker.point, (35.6812, 139.7671))
        self.search.assert_called_once_with("東京")

        self.reverse.return_value = "兵庫県赤穂市"
        self.click_map(34.754, 134.391)
        self.wait_for(lambda: self.picker.name.get() == "兵庫県赤穂市")
        self.assertEqual(self.picker.point, (34.754, 134.391))
        self.applied.assert_not_called()
        self.picker.apply()
        self.applied.assert_called_once_with("兵庫県赤穂市", 34.754, 134.391)

    def test_cancel_discards_selection(self):
        self.click_map(35.0116, 135.7681)
        self.picker.name.set("京都")
        self.picker.close()
        self.root.update()
        self.applied.assert_not_called()

    def test_delayed_search_result_does_not_select_a_place_for_an_edited_query(self):
        started, release = self.delay_reply(self.search, [Place("東京", 35.68, 139.76)])
        self.picker.query.set("東京")
        self.picker.search()
        self.wait_for(started.is_set)
        self.picker.query.set("大阪")
        release.set()
        self.wait_for(lambda: self.picker.poll_id is None)
        self.assertEqual(self.picker.query.get(), "大阪")
        self.assertIsNone(self.picker.point)
        self.assertFalse(self.picker.results_box.cget("values"))

    def test_old_search_and_reverse_lookup_preserve_clicked_pin_and_manual_name(self):
        started, release = self.delay_reply(self.search, [Place("東京", 35.68, 139.76)])
        self.reverse.return_value = "兵庫県赤穂市"
        self.picker.query.set("東京")
        self.picker.search()
        self.wait_for(started.is_set)
        self.click_map(34.754, 134.391)
        self.picker.name.set("お気に入りの場所")
        release.set()
        self.wait_for(lambda: self.reverse.called and self.picker.poll_id is None)
        self.assertEqual(self.picker.point, (34.754, 134.391))
        self.assertEqual(self.picker.name.get(), "お気に入りの場所")
        self.assertFalse(self.picker.results_box.cget("values"))

    def test_settings_page_applies_all_three_fields_only_saving_on_request(self):
        from studio.settings_page import SettingsPage

        self.picker.close()
        folder = self.enterContext(tempfile.TemporaryDirectory())
        path = Path(folder) / "bridge" / "local.json"
        settings = SettingsPage(self.root, path, Mock())
        picker = settings.open_map()
        picker.withdraw()
        self.click_map(34.754125, 134.391125)
        picker.name.set("赤穂")
        picker.apply()
        self.assertTrue(settings.dirty)
        self.assertEqual(settings.variables["name"].get(), "赤穂")
        self.assertEqual(settings.variables["lat"].get(), "34.754125")
        self.assertEqual(settings.variables["lon"].get(), "134.391125")
        self.assertFalse(path.exists())
        self.assertTrue(settings.persist())
        self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["place"],
                         {"name": "赤穂", "lat": 34.754125, "lon": 134.391125})
