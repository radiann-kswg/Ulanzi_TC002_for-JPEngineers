import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
spec = importlib.util.spec_from_file_location("debug_device", SCRIPTS / "debug-device.py")
debug = importlib.util.module_from_spec(spec)
with patch.object(sys, "path", [str(SCRIPTS), *sys.path]):
    spec.loader.exec_module(debug)
    import device_audio as audio


class TrialAudioTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.originals = self.root / "originals"
        self.originals.mkdir()
        for name in audio.CUES:
            (self.originals / (name + ".mp3")).write_bytes(b"original")
        self.enterContext(patch.object(audio, "ORIGINALS", self.originals))

    def test_custom_resident_firmware_needs_no_stock_tick(self):
        pushes = []

        def adb(args, **kwargs):
            if "push" in args:
                pushes.append((Path(args[-2]), args[-1]))
                return b""
            if "connect" in args:
                return b""
            self.assertIn("shell", args)
            if args[-1].startswith("if [ -f"):
                return json.dumps({"startupLibPath": debug.LIBRARY}).encode()
            if args[-1].startswith("if [ -r"):
                return b""
            self.assertTrue(args[-1].startswith(("mv ", "mkdir -p /tmp/ui/audio", "rm -f /tmp/ui/audio/")))
            return b"READY\n"

        # A previous IDE image may still have local audio in its project tree.
        # Trial selection starts from the versioned originals.
        with patch.object(debug, "PROJECT", self.root / "unrelated"), patch.object(
                debug, "find_encoder", return_value="unused"), patch.object(debug.subprocess, "check_output", adb):
            debug.debug("192.0.2.1", "mock-adb", False, audio_only=True)
        self.assertCountEqual([p.stem for p, _ in pushes], audio.CUES)
        for path, target in pushes:
            self.assertEqual(path.parent, self.originals)
            self.assertEqual(target, "/tmp/ui/tc002/" + path.name + ".new")
        self.assertFalse((self.root / "unrelated").exists())

    def test_factory_tick_only_changes_the_minute_cue_inside_scratch_folder(self):
        work = self.root / "scratch"
        work.mkdir()
        pcm = struct.pack("<64h", *([1000, -900] * 32))

        def encode(args, **kwargs):
            self.assertTrue(kwargs["input"])
            self.assertEqual(Path(args[-1]).parent, work)
            Path(args[-1]).write_bytes(b"derived")

        with patch.object(audio.subprocess, "check_output", return_value=pcm), patch.object(audio.subprocess, "run", encode):
            files = audio.trial_cues(work, "encoder", work / "stock-second.mp3")
        self.assertEqual({p.stem for p in files if p.parent == work}, {"minute"})
        self.assertEqual([p.read_bytes() for p in self.originals.iterdir()], [b"original"] * len(audio.CUES))
        self.assertCountEqual([p.stem for p in files], audio.CUES)

    def test_without_encoder_uses_originals(self):
        paths = audio.trial_cues(self.root, None, self.root / "stock-second.mp3")
        self.assertTrue(all(path.parent == self.originals for path in paths))

    def test_first_launch_waits_for_marker_without_polluting_ide_project(self):
        (self.root / "Release").mkdir()
        (self.root / "Release/libzkgui.so").touch()
        (self.root / "ui").mkdir()
        (self.root / "ui/main.ftu").touch()
        personal = self.root / "resources/audio"
        personal.mkdir(parents=True)
        (personal / "Enter.mp3").write_bytes(b"personal enter")
        stock_uploads = []
        marker = iter([b"", b"", b"123"])

        def adb(args, **kwargs):
            cmd = args[-1]
            if cmd == "cat /tmp/tc002-dev.ready":
                raise AssertionError("A missing ready file must also work with modern ADB exit codes")
            if cmd.startswith("if [ -f /tmp/tc002-dev.ready"):
                return next(marker)
            if cmd.startswith("if [ -f /tmp/EasyUI.cfg"):
                return b"TC002_NO_CONFIG"
            if cmd == "cat /res/etc/EasyUI.cfg":
                return b"{}"
            if cmd == "cat /proc/123/maps":
                return debug.LIBRARY.encode()
            if "push" in args:
                local = Path(args[-2])
                self.assertTrue(local.is_file())
                if local.name == "EasyUI.cfg":
                    self.assertNotEqual(local.parent, self.root)
                if args[-1].startswith("/tmp/ui/audio/"):
                    stock_uploads.append((local.read_bytes(), args[-1]))
                return b""
            return b"READY"

        with patch.object(debug, "PROJECT", self.root), patch.object(debug, "find_encoder", return_value=None), \
                patch.object(debug.time, "sleep"), patch.object(debug.subprocess, "check_output", adb):
            debug.debug("192.0.2.1", "mock-adb", False)
        self.assertFalse((self.root / "EasyUI.cfg").exists())
        self.assertEqual(stock_uploads, [(b"personal enter", "/tmp/ui/audio/Enter.mp3.new")])
