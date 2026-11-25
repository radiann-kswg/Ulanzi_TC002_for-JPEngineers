import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from bridge import store, weather
from bridge.__main__ import jobs


class ClaudeDesktopTest(unittest.TestCase):
    account = "11111111-1111-4111-8111-111111111111"
    org = "22222222-2222-4222-8222-222222222222"
    now = int(datetime(2026, 11, 24, tzinfo=timezone.utc).timestamp())

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.root = root / "Claude"
        self.code = self.root / "claude-code-sessions" / self.account / self.org
        self.cowork = self.root / "local-agent-mode-sessions" / self.account / self.org
        for folder in (self.code, self.cowork):
            folder.mkdir(parents=True)
        env = patch.dict(os.environ, APPDATA=str(root))
        env.start()
        self.addCleanup(env.stop)
        self.write(self.root / "config.json", {"lastKnownAccountUuid": self.account})
        self.db = store.open_db(root / "bridge.db")
        self.addCleanup(self.db.close)
        self.tasks = jobs({"repos": [], "place": weather.AKO}, root / "bridge.db")

    @staticmethod
    def write(path, data):
        path.write_text(json.dumps(data), encoding="utf-8")

    def observe(self, name):
        period, collect = self.tasks[name]
        data = collect({}, self.now)
        store.save(self.db, name, data, data.get("observedAt", self.now), max(90, period * 2))
        return data

    def wire(self):
        return store.snapshot(self.db, weather.AKO, self.now).decode()

    def test_limits_use_sample_time_and_selected_organization(self):
        stamp = self.now - 3600
        self.write(self.root / "plan-usage-history.json", {"version": 2, "samples": [
            {"t": stamp*1000, "org": self.org, "u": {"sd": 51, "xu": 100}},
            {"t": self.now*1000, "org": "another", "u": {"fh": 80}}]})
        self.observe("claude.desktop.limits")
        self.assertIn(f"old\t1\t6\t{stamp}\t残 7d 49%", self.wire())
        self.assertIn(f"old\t1\t6\t{stamp}\t追加 予算 100%使用\n", self.wire())
        self.assertIn("7d 49% リセット ?", self.wire())
        self.assertNotIn("5h", self.wire())
        self.write(self.root / "plan-usage-history.json", {"version": 2, "samples": [
            {"t": self.now*1000, "org": self.org, "u": {"xu": 0}}]})
        self.observe("claude.desktop.limits")
        self.assertIn(f"row\t1\t6\t{self.now}\t追加 予算 0%使用\n", self.wire())
        self.write(self.root / "plan-usage-history.json", {"version": 2, "samples": [
            {"t": self.now*1000, "org": self.org, "u": {}}]})
        self.observe("claude.desktop.limits")
        self.assertIn("row\t1\t6\t0\t追加 取得不可\n", self.wire())

    def test_multiple_organizations_require_an_unambiguous_selection(self):
        other = "33333333-3333-4333-8333-333333333333"
        (self.code.parent / other).mkdir()
        self.write(self.root / "plan-usage-history.json", {"version": 2, "samples": [
            {"t": self.now*1000, "org": self.org, "u": {"sd": 25}}]})
        with self.assertRaises(ValueError):
            self.observe("claude.desktop.limits")
        self.tasks = jobs({"repos": [], "place": weather.AKO, "claudeOrganization": self.org}, None)
        self.assertEqual(self.observe("claude.desktop.limits")["fields"]["1.left"], "7d 75%")
