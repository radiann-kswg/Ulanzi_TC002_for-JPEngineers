import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from studio import setup


class SetupTest(unittest.TestCase):
    def test_clock_tick_import_keeps_the_previous_copy_on_failure(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(setup, "PROJECT", Path(temp)):
            (Path(temp) / ".project").touch()
            destination = Path(temp) / "resources/audio/Clock.mp3"
            def transfer(args, **kwargs):
                if "pull" in args:
                    self.assertEqual(args[1:5], ["-s", "192.0.2.1:5555", "pull", "/res/ui/audio/Clock.mp3"])
                    Path(args[-1]).write_bytes(b"stock tick")
                return setup.subprocess.CompletedProcess(args, 0)
            with patch.object(setup.subprocess, "run", side_effect=transfer):
                setup.import_clock_tick("192.0.2.1", "adb")
            self.assertEqual(destination.read_bytes(), b"stock tick")
            with patch.object(setup.subprocess, "run", return_value=setup.subprocess.CompletedProcess([], 1)):
                with self.assertRaises(RuntimeError):
                    setup.import_clock_tick("192.0.2.1", "adb")
            self.assertEqual(destination.read_bytes(), b"stock tick")

    def test_gui_setup_starts_console_workers(self):
        gui = Path("Program Files") / "Python312/pythonw.exe"
        with patch.object(sys, "executable", str(gui)), patch.object(setup, "store_paths"), \
                patch.object(setup, "run_logged", return_value=Path("task.log")) as run:
            setup.setup_tools("", "")
            setup.build_project("SDK", "")
            setup.debug_device("192.0.2.1", "adb", restore=True)
        self.assertEqual([Path(call.args[0][0]) for call in run.call_args_list],
                         [gui.with_name("python.exe")] * 4)

    def test_build_uses_selected_paths_without_splitting_spaces(self):
        with patch.object(setup, "store_paths") as store, patch.object(setup, "run_logged") as run:
            run.return_value = Path("prepare.log")
            setup.build_project("E:/IDE root", "F:/source tree", prepare_only=True)
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
        for output in (b"TC002_RESTORED", b"error"):
            replies = [b"", own, own, resident, b"TC002_SAVED", output, b"TC002_RESIDENT"]
            with patch.object(device.subprocess, "check_output", side_effect=replies):
                if output == b"error":
                    with self.assertRaises(RuntimeError):
                        device.debug("192.0.2.1", "adb", True)
                else:
                    device.debug("192.0.2.1", "adb", True)
        # After the config moved but service restart failed, a second Restore retries the service.
        replies = [b"", b"TC002_NO_CONFIG", b"TC002_NO_CONFIG", b"TC002_RETRY", resident,
                   b"", b"TC002_RESTORED", b"TC002_RESIDENT"]
        with patch.object(device.subprocess, "check_output", side_effect=replies) as adb:
            device.debug("192.0.2.1", "adb", True)
            self.assertTrue(any("setprop ctl.restart zkswe" in c.args[0][-1] for c in adb.call_args_list))
