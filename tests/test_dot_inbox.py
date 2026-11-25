import importlib.util
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest

from bridge import store, weather

spec = importlib.util.spec_from_file_location("dot_host", Path(__file__).resolve().parents[1]/"scripts/dot-host.py")
host = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host)


class DotInboxTest(unittest.TestCase):
    def test_arrival_retries_and_old_messages(self):
        with tempfile.TemporaryDirectory() as folder:
            db = store.open_db(Path(folder)/"state.db")
            try:
                items = [{"id":"inbox-message", "at":1000001}, {"id":"old", "at":800000}]
                body = json.dumps(items).encode()
                for _ in range(2):
                    reply = io.BytesIO()
                    host.receive(io.BytesIO(struct.pack("=I", len(body))+body), reply, db, 1001)
                    self.assertEqual(reply.getvalue(), struct.pack("=I", 11) + b'{"ok":true}')
                wire = store.snapshot(db, weather.AKO, 1005)
                self.assertEqual(wire.count(b"event\t1000\tdot-new-"), 1)
                self.assertNotIn(b"inbox-message", wire)
                self.assertNotIn(b"dot-new-", store.snapshot(db, weather.AKO, 1061))
            finally:
                db.close()
