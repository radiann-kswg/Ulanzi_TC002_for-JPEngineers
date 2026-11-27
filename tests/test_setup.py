import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from studio import setup


class SetupTest(unittest.TestCase):
    def test_imports_factory_controls_and_preserves_previous_sounds_on_partial_pull(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(setup, "PROJECT", Path(temp)):
            (Path(temp) / ".project").touch()
            names = ("Btn.mp3", "Clock.mp3", "Enter.mp3", "Rotate.mp3", "Rotate.wav",
                     "SlowClock.mp3", "StopWatch.mp3", "Tip.mp3")
            dest = Path(temp) / "resources/audio"
            def transfer(args, **kwargs):
                if "pull" in args:
                    self.assertEqual(args[1:5], ["-s", "192.0.2.1:5555", "pull", "/res/ui/audio"])
                    folder = Path(args[-1])
                    folder.mkdir()
                    for name in (*names, "unknown.mp3"):
                        (folder / name).write_bytes(name.encode())
                return setup.subprocess.CompletedProcess(args, 0)
            with patch.object(setup.subprocess, "run", side_effect=transfer):
                setup.import_stock_sounds("192.0.2.1", "adb")
            self.assertCountEqual([p.name for p in dest.iterdir()], names)
            with tempfile.TemporaryDirectory() as backup:
                source = Path(backup)
                (source / "Clock.mp3").write_bytes(b"new tick")
                (source / "Enter.mp3").touch()
                with self.assertRaises(RuntimeError):
                    setup.copy_stock_sounds(source)
                self.assertEqual((dest / "Clock.mp3").read_bytes(), b"Clock.mp3")
                (source / "Enter.mp3").unlink()
                report = setup.copy_stock_sounds(source)
                self.assertIn("Enter.mp3", report)
            self.assertEqual((dest / "Clock.mp3").read_bytes(), b"new tick")
            self.assertEqual((dest / "Enter.mp3").read_bytes(), b"Enter.mp3")
            def broken_pull(args, **kwargs):
                result = transfer(args, **kwargs)
                return setup.subprocess.CompletedProcess(args, 1) if "pull" in args else result
            with patch.object(setup.subprocess, "run", side_effect=broken_pull), self.assertRaises(RuntimeError):
                setup.import_stock_sounds("192.0.2.1", "adb")
            self.assertEqual((dest / "Clock.mp3").read_bytes(), b"new tick")

    def test_gui_setup_starts_console_workers(self):
        gui = Path("Program Files") / "Python312/pythonw.exe"
        with tempfile.TemporaryDirectory() as temp, patch.object(sys, "executable", str(gui)), \
                patch.object(setup, "store_paths"), patch.object(setup, "run_logged") as run:
            log = Path(temp) / "task.log"
            log.touch()
            run.return_value = log
            setup.setup_tools("", "")
            report = setup.build_project("SDK", "")
            self.assertIn(str(log), report)
            self.assertNotIn("退避先", report)
            setup.debug_device("192.0.2.1", "adb", restore=True)
        self.assertEqual([Path(call.args[0][0]) for call in run.call_args_list],
                         [gui.with_name("python.exe")] * 4)

    def test_build_uses_selected_paths_without_splitting_spaces(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(setup, "store_paths") as store, \
                patch.object(setup, "run_logged") as run:
            backup = Path(temp) / "旧プロジェクト" / "TC002Dev-legacy-example"
            log = Path(temp) / "prepare.log"
            log.write_text(f"Preserved previous local files outside the image project: {backup}\n"
                           "Project prepared.\n", encoding="utf-8")
            run.return_value = log
            report = setup.build_project("E:/IDE root", "F:/source tree", prepare_only=True)
            self.assertIn(f"旧ファイルの退避先　{backup}", report)
            self.assertIn(str(log), report)
            self.assertEqual(run.call_args.args[0][-5:],
                             ["--ide", "E:/IDE root", "--sample", "F:/source tree", "--prepare-only"])
            store.assert_called_once_with("E:/IDE root", "F:/source tree")

    def test_saved_device_and_ide_override(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "local.json"
            with self.assertRaises(ValueError):
                setup.device_target(path, temp)
            path.write_text(json.dumps({"device": "192.0.2.1"}))
            adb = root / "sdk/platform-tools/adb/adb.exe"
            adb.parent.mkdir(parents=True)
            adb.touch()
            address, selected = setup.device_target(path, temp)
            self.assertEqual(address, "192.0.2.1")
            self.assertEqual(Path(selected), adb.resolve())

    def test_restore_only_changes_our_config_and_checks_remote_result(self):
        script = setup.ROOT / "scripts/debug-device.py"
        spec = importlib.util.spec_from_file_location("debug_device", script)
        device = importlib.util.module_from_spec(spec)
        with patch.object(sys, "path", [str(script.parent), *sys.path]):
            spec.loader.exec_module(device)
        own = json.dumps({"startupLibPath": device.LIBRARY}).encode()
        other = json.dumps({"startupLibPath": "/tmp/other.so", "comment": device.LIBRARY}).encode()
        for existing in (other, b"invalid", b'{"startupLibPath":null}'):
            with patch.object(device.subprocess, "check_output", side_effect=[b"", existing]) as adb:
                with self.assertRaises(RuntimeError):
                    device.debug("192.0.2.1", "adb", True)
                self.assertEqual(adb.call_count, 2)
        resident = b'{"startupLibPath":"/res/lib/libzkgui.so"}'
        mapped = b'40000000-40100000 r-xp 00000000 1f:03 14  /res/lib/libzkgui.so'
        for output in (b"TC002_RESTORED", b"error"):
            replies = [b"", own, own, resident, b"TC002_SAVED", output, mapped]
            with patch.object(device.subprocess, "check_output", side_effect=replies):
                if output == b"error":
                    with self.assertRaises(RuntimeError):
                        device.debug("192.0.2.1", "adb", True)
                else:
                    device.debug("192.0.2.1", "adb", True)
        # After the config moved but service restart failed, a second Restore retries the service.
        replies = [b"", b"TC002_NO_CONFIG", b"TC002_NO_CONFIG", b"TC002_RETRY", resident,
                   b"", b"TC002_RESTORED", mapped]
        with patch.object(device.subprocess, "check_output", side_effect=replies) as adb:
            device.debug("192.0.2.1", "adb", True)
            self.assertTrue(any("setprop ctl.restart zkswe" in c.args[0][-1] for c in adb.call_args_list))
