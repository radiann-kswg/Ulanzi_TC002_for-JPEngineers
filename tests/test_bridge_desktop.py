import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from bridge import desktop, manual, schedules, store, weather
from bridge.__main__ import main

class DesktopTest(unittest.TestCase):
    def test_claude_agent_states(self):
        raw=[{"sessionId":str(i),"name":"task","state":x} for i,x in enumerate(
            ["working","blocked","done","failed","stopped"])]
        with patch("bridge.desktop.subprocess.run") as run:
            run.return_value.stdout=json.dumps(raw).encode()
            self.assertEqual([i[2] for i in desktop.claude_sessions(100)["sessions"]],
                             ["working","waiting","completed","failed","closed"])

    def test_hook_does_not_copy_prompt(self):
        _,entry=desktop.hook({"session_id":"1","cwd":"project","hook_event_name":"PermissionRequest",
                              "prompt":"private content"},"claude",100)
        self.assertEqual(entry[2],"waiting")
        self.assertNotIn("private content",entry)

    def test_one_import_replaces_one_scope(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"input.json"
            dbpath=Path(td)/"bridge.db"
            observed="2025-02-01T10:00:00+09:00"
            doc={"provider":"claude","scope":"cowork","observedAt":observed,
                 "sessions":[{"id":"same","label":"作業A","state":"waiting"}]}
            path.write_text(json.dumps(doc))
            for _ in range(2): main(["--db",str(dbpath),"import",str(path)])
            db=store.open_db(dbpath)
            try:
                epoch=manual.timestamp(observed)
                wire=store.snapshot(db,weather.AKO,epoch).decode()
                self.assertIn("作業 0 待ち 1",wire)
                self.assertEqual(wire.count("作業A"),1)
            finally: db.close()
    def test_invalid_import(self):
        with self.assertRaises(ValueError):
            manual.parse({"provider":"claude","observedAt":"2026-01-01","extraSpent":{"amount":0}},10)
    def test_extra_usage_expires_at_the_contract_boundary(self):
        checked="2026-11-23T21:00:00+09:00"
        end="2026-12-05T00:00:00+09:00"
        t=manual.timestamp(checked)
        stamp,obs=manual.parse({"provider":"codex","observedAt":checked,"extraSpent":{
            "amount":0,"currency":"USD","periodStart":"2026-11-05T00:00:00+09:00","periodEnd":end}},t)
        with tempfile.TemporaryDirectory() as td:
            db=store.open_db(Path(td)/"test.db")
            try:
                store.save(db,obs[0][0],obs[0][1],stamp,3600)
                self.assertIn("追加 0 USD",store.snapshot(db,weather.AKO,t).decode())
                self.assertNotIn("追加 0 USD",store.snapshot(db,weather.AKO,manual.timestamp(end)).decode())
            finally: db.close()
    def test_weekly_occurrences(self):
        t=int(datetime(2026,11,23,10,0,tzinfo=store.JST).timestamp())
        task={"status":"ACTIVE","created_at":t*1000,"rrule":"FREQ=WEEKLY;BYDAY=MO;BYHOUR=11;BYMINUTE=0"}
        self.assertEqual(schedules.occurrences(task,t,"Asia/Tokyo")[0],t+3600)
        self.assertEqual(schedules.occurrences(dict(task,status="PAUSED"),t,"Asia/Tokyo"),[])
