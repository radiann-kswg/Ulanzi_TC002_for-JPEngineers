import json
from pathlib import Path
import tempfile
from threading import Event
import time
import unittest
from unittest.mock import patch

try:
    import tkinter as tk
    from tkinter import ttk
except ImportError:
    tk = None


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


@unittest.skipIf(tk is None, "the Windows settings interface requires Tk")
class StudioWindowTests(unittest.TestCase):
    def setUp(self):
        from studio.app import create_window

        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            if "display" in str(error).lower():
                self.skipTest(f"Tk display unavailable: {error}")
            raise
        self.addCleanup(self.root.destroy)
        self.root.withdraw()
        folder = self.enterContext(tempfile.TemporaryDirectory())
        self.path = Path(folder) / "bridge/local.json"
        self.enterContext(patch("studio.setup.load_paths", return_value=("", "")))
        self.app = create_window(self.root, self.path)
        self.root.update()

    def key(self, widget, sequence):
        # A virtual event exercises the registered shortcut from its child widget
        # while keeping the test window hidden and the user's keyboard focus intact.
        script = self.root.bind(sequence)
        self.assertTrue(script, f"Missing shortcut {sequence}")
        self.assertIn(str(self.root), widget.bindtags())
        event = "<<StudioShortcutTest>>"
        self.root.tk.call("bind", str(self.root), event, script)
        try:
            widget.event_generate(event)
            self.root.update()
        finally:
            self.root.tk.call("bind", str(self.root), event, "")

    def test_edit_survives_page_shortcuts_and_only_settings_shortcut_saves(self):
        settings = self.app.settings
        self.assertEqual(self.root.title(), "Ulanzi TC002 JPエンジニア向けOS設定")
        self.assertEqual(self.app.current, "settings")
        settings.device.insert(0, "192.0.2.20")
        self.key(settings.device, "<Control-Tab>")
        self.assertEqual(self.app.current, "setup")
        field = next(w for w in descendants(self.app.pages["setup"]) if isinstance(w, ttk.Entry))
        self.key(field, "<Control-s>")
        self.assertFalse(self.path.exists())
        self.assertTrue(settings.dirty)
        self.assertEqual(settings.saved_device.get(), "")

        self.key(field, "<Control-Shift-Tab>")
        self.assertEqual(self.app.current, "settings")
        self.key(settings.device, "<Control-s>")
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))["device"], "192.0.2.20")
        self.assertEqual(settings.saved_device.get(), "192.0.2.20")
        self.assertFalse(settings.dirty)

        self.key(settings.device, "<Control-Next>")
        self.assertEqual(self.app.current, "setup")
        self.key(field, "<Control-Prior>")
        self.assertEqual(self.app.current, "settings")

    def test_first_show_maps_fields_on_both_pages(self):
        self.root.overrideredirect(True)
        self.root.attributes("-alpha", 0)
        if self.root.tk.call("tk", "windowingsystem") == "win32":
            self.root.attributes("-disabled", True)
        self.root.deiconify()
        self.root.update()
        self.assertTrue(self.app.settings.device.winfo_viewable())
        self.app.show_page("setup")
        self.root.update()
        field = next(w for w in descendants(self.app.pages["setup"]) if isinstance(w, ttk.Entry))
        self.assertTrue(field.winfo_viewable())

    def test_build_keeps_global_status_and_rejects_bridge_action_on_other_page(self):
        release = Event()

        def simulated_build(*args, **kwargs):
            release.wait(5)
            return "テストビルド完了"

        self.app.show_page("setup")
        button = next(w for w in descendants(self.app.pages["setup"])
                      if isinstance(w, ttk.Button) and w.cget("text") == "ARM ビルド")
        with patch("studio.setup.build_project", side_effect=simulated_build) as build, \
                patch("studio.settings_page.bridge_action") as bridge:
            button.invoke()
            try:
                self.assertTrue(self.app.status.busy)
                message = self.app.status.text.get()
                self.assertIn("ビルド", message)
                self.app.show_page("settings")
                self.assertTrue(self.app.settings.save_button.instate(["disabled"]))
                self.app.settings.operate("status")
                self.assertEqual(self.app.status.text.get(), message)
                bridge.assert_not_called()
            finally:
                release.set()
                deadline = time.monotonic() + 4
                while self.app.status.busy and time.monotonic() < deadline:
                    self.root.update()
                    time.sleep(0.01)
        build.assert_called_once()
        self.assertFalse(self.app.status.busy)
        self.assertTrue(self.app.settings.save_button.instate(["!disabled"]))
        self.assertEqual(self.app.status.text.get(), "テストビルド完了")
