from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

try:
    import tkinter as tk
except ImportError:
    tk = None
else:
    from studio.map_canvas import MapCanvas, _coordinates, _project


@unittest.skipIf(tk is None, "the Windows map requires Tk")
class ProjectionTests(unittest.TestCase):
    def test_reference_pixels_and_antimeridian_round_trip(self):
        # At zoom 2 there are four 256-pixel tiles across the world.
        self.assertEqual(_project(0, 0, 2), (512, 512))
        latitude, longitude = _coordinates(768, 256, 2)
        self.assertAlmostEqual(latitude, 66.51326044)
        self.assertEqual(longitude, 90)
        self.assertEqual(_project(0, -180, 2), _project(0, 180, 2))
        self.assertEqual(_coordinates(1024, 512, 2), (0, -180))
        for lat, lon in ((35.6812, 139.7671), (-16.55, 179.99), (-16.55, -179.99)):
            with self.subTest(lat=lat, lon=lon):
                actual_lat, actual_lon = _coordinates(*_project(lat, lon, 16), 16)
                self.assertAlmostEqual(actual_lat, lat)
                self.assertAlmostEqual(actual_lon, lon)


@unittest.skipIf(tk is None, "the Windows map requires Tk")
class MapGestureTests(unittest.TestCase):
    def setUp(self):
        try:
            root = tk.Tk()
        except tk.TclError as error:
            if "display" in str(error).lower():
                self.skipTest(f"Tk display unavailable: {error}")
            raise
        self.addCleanup(root.destroy)
        root.withdraw()
        self.enterContext(patch("studio.map_canvas._fetch_tile", side_effect=OSError("offline")))
        self.picked = Mock()
        self.map = MapCanvas(root, self.picked)
        self.map.pack()
        root.update()
        # The hidden widget has no screen geometry. Give its pointer events a fixed viewport.
        self.enterContext(patch.object(self.map, "winfo_width", return_value=512))
        self.enterContext(patch.object(self.map, "winfo_height", return_value=256))
        self.map.center_at(0, 179, 3)

    def click(self, x, y):
        pointer = SimpleNamespace(x=x, y=y)
        self.map._start_drag(pointer)
        self.map._release(pointer)
        return self.picked.call_args.args

    def test_zoom_keeps_point_under_pointer_across_date_line(self):
        before = self.click(360, 96)
        self.assertLess(before[1], 0)
        self.map._wheel(SimpleNamespace(x=360, y=96, delta=120))
        self.assertEqual(self.map.zoom, 4)
        after = self.click(360, 96)
        self.assertAlmostEqual(before[0], after[0])
        self.assertAlmostEqual(before[1], after[1])

    def test_drag_moves_previous_location_under_release_without_selecting_it(self):
        before = self.click(256, 128)
        self.picked.reset_mock()
        self.map._start_drag(SimpleNamespace(x=256, y=128))
        destination = SimpleNamespace(x=300, y=150)
        self.map._drag(destination)
        self.map._release(destination)
        self.picked.assert_not_called()
        after = self.click(300, 150)
        self.assertAlmostEqual(before[0], after[0])
        self.assertAlmostEqual(before[1], after[1])
