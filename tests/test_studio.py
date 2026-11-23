from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from bridge import config
from studio import runner
from studio.settings import Fields, save


class SettingsTests(unittest.TestCase):
    def setUp(self):
        work = tempfile.TemporaryDirectory()
        self.addCleanup(work.cleanup)
        self.path = Path(work.name) / "bridge" / "local.json"
        self.empty = Fields.from_document({})

    def test_first_run_and_bridge_round_trip(self):
        self.assertEqual(config.read(self.path), {})
        self.assertFalse(self.path.parent.exists())
        fields = replace(self.empty, device="192.0.2.40", name="小笠原村", lat="27.09",
                         lon="142.19", repos="example/widget, example/widget test/other")
        normalized = save(self.path, self.empty, fields)
        self.assertEqual(config.settings(self.path)["place"]["name"], "小笠原村")
        self.assertEqual(config.settings(self.path)["repos"], ["example/widget", "test/other"])
        self.assertEqual(normalized, Fields.from_document(config.read(self.path)))

    def test_other_settings_preserved_and_edit_conflicts_detected(self):
        initial = {"timezone": "UTC", "owner": "demo", "place": {"name": "例", "lat": 0, "lon": 0, "id": 12}}
        config.update(self.path, lambda _: initial)
        baseline = Fields.from_document(initial)
        config.update(self.path, lambda doc: {**doc, "futureKey": True})
        save(self.path, baseline, replace(baseline, owner=""))
        result = config.read(self.path)
        self.assertNotIn("owner", result)
        self.assertEqual((result["place"]["id"], result["timezone"], result["futureKey"]), (12, "UTC", True))
        with self.assertRaisesRegex(ValueError, "別の操作"):
            save(self.path, baseline, replace(baseline, owner="older"))
        self.assertEqual(config.read(self.path), result)

    def test_optional_nulls_are_empty_fields(self):
        fields = Fields.from_document({"owner": None, "device": None, "adb": None})
        self.assertEqual((fields.owner, fields.device, fields.adb), ("", "", ""))

    def test_two_studio_writers_cannot_overwrite_each_other(self):
        def edit(name):
            try:
                save(self.path, self.empty, replace(self.empty, name=name))
            except ValueError:
                return False
            return True
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(edit, ("A", "B")))
        self.assertEqual(sorted(results), [False, True])
        self.assertIn(config.read(self.path)["place"]["name"], ["A", "B"])

    def test_invalid_and_corrupt_files_leave_original_intact(self):
        save(self.path, self.empty, self.empty)
        original = self.path.read_bytes()
        for bad in ({"device": "224.0.0.1"}, {"device": "0.0.0.0"}, {"device": "not a host"},
                    {"lat": "nan"}, {"lon": "181"}, {"name": " "}, {"repos": "../foo"},
                    {"owner": "../foo"}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                save(self.path, self.empty, replace(self.empty, **bad))
            self.assertEqual(self.path.read_bytes(), original)
        self.path.write_text("{", encoding="utf-8")
        with self.assertRaises(json.JSONDecodeError):
            save(self.path, self.empty, self.empty)
        self.assertEqual(self.path.read_text(), "{")

    def test_temporary_file_is_removed_on_replace_failure(self):
        with patch.object(config.os, "replace", side_effect=PermissionError), self.assertRaises(PermissionError):
            save(self.path, self.empty, self.empty)
        self.assertEqual([p.name for p in self.path.parent.iterdir()], ["local.json.lock"])

    def test_adb_explicit_sdk_and_path(self):
        sdk = self.path.parent / "example-sdk"
        adb = sdk / "sdk/platform-tools/adb/adb.exe"
        paths = self.path.parent / "studio-paths.json"
        with patch.dict(config.os.environ, FLYTHINGS_HOME=str(sdk)):
            self.assertEqual(config.adb_command({}, paths=paths), "adb")
            adb.parent.mkdir(parents=True)
            adb.touch()
            configured = self.path.parent / "selected-sdk"
            selected_adb = configured / "sdk/platform-tools/adb/adb.exe"
            selected_adb.parent.mkdir(parents=True)
            selected_adb.touch()
            paths.write_text(json.dumps({"ide": str(configured)}), encoding="utf-8")
            self.assertEqual(Path(config.adb_command({}, paths=paths)), selected_adb.resolve())
            self.assertEqual(config.adb_command({"adb": "custom"}, paths=paths), "custom")
            selected_adb.unlink()
            self.assertEqual(Path(config.adb_command({}, paths=paths)), adb.resolve())
            selected_adb.touch()
            adb.unlink()
            self.assertEqual(Path(config.adb_command({}, paths=paths)), selected_adb.resolve())
            for invalid in ("{", "[]", '{"ide":true}'):
                paths.write_text(invalid, encoding="utf-8")
                self.assertEqual(config.adb_command({}, paths=paths), "adb")


class RunnerTests(unittest.TestCase):
    @patch.object(runner.subprocess, "run")
    def test_start_uses_matching_console_interpreter_as_single_argument(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, b"PC bridge started (PID 10).", b"")
        with patch.object(runner.sys, "executable", str(Path("Program Files") / "Python312/pythonw.exe")):
            self.assertIn("実行中", runner.bridge_action("start"))
        args = run.call_args.args[0]
        self.assertEqual(args[-2:], ["-Python", str(Path("Program Files") / "Python312/python.exe")])
        self.assertEqual(Path(args[args.index("-File") + 1]).name, "start-bridge.ps1")

    @patch.object(runner.subprocess, "run")
    def test_stopping_and_failure_messages(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, b"Finishing current requests.", b"")
        self.assertIn("停止処理中", runner.bridge_action("stop"))
        self.assertEqual(run.call_args.args[0][-1], "-Stop")
        run.return_value = subprocess.CompletedProcess([], 1, b"", b"startup failed")
        with self.assertRaisesRegex(RuntimeError, "startup failed"):
            runner.bridge_action("status")
        self.assertEqual(run.call_args.args[0][-1], "-Status")
