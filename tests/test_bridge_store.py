import tempfile
import unittest
from pathlib import Path
from bridge import store, weather

class StoreTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db=store.open_db(Path(self.temp.name)/"test.db")
        self.addCleanup(self.db.close)

    def test_last_good_and_unknown(self):
        store.save(self.db,"x",{"rows":[[0,1,"0 件\nEND"]]},1000,90)
        store.failed(self.db,"x")
        data=store.snapshot(self.db,weather.AKO,1010).decode()
        self.assertIn("old\t0\t1\t1000\t0 件 END\n",data)
        self.assertIn("追加 取得不可",data)

    def test_full_multibyte_snapshot_fits_the_receiver(self):
        rows=[[c,p,"島⚓🚢"*25] for c in range(4) for p in range(8) for _ in range(105)]
        store.save(self.db,"large",{"rows":rows},1000,90)
        wire=store.snapshot(self.db,weather.AKO,1000)
        self.assertLessEqual(len(wire),262144)
        self.assertEqual(wire.decode().count("row\t"),3200)

    def test_a_long_repository_does_not_hide_the_ticket_title(self):
        label="release-engineering-"*5+"#421 表示幅を確認"
        store.save(self.db,"github.list",{"rows":[[0,0,label],[0,0,"あ"*300]]},1000,90)
        wire=store.snapshot(self.db,weather.AKO,1000).decode()
        self.assertIn(label,wire)
        self.assertIn("あ"*255+"…\n",wire)

    def test_scheduled_due_and_dedup(self):
        data={"schedules":[[2,"id",1050,"確認"]]}
        for name in ("one","two"):
            store.save(self.db,name,data,1000,300)
        wire=store.snapshot(self.db,weather.AKO,1010).decode()
        self.assertEqual(wire.count("event\t"),1)
        self.assertIn("row\t2\t1",wire)
        self.assertIn("row\t2\t0",store.snapshot(self.db,weather.AKO,1060).decode())

    def test_date_and_amount_separate(self):
        store.save(self.db,"manual.cost",{"fields":{"1.extra":"2 USD"}},1000,30)
        store.save(self.db,"claude",{"fields":{"1.left":"0%"}},1030,45)
        wire=store.snapshot(self.db,weather.AKO,1040).decode()
        self.assertIn("old\t1\t6\t1000\t追加 2 USD",wire)
        self.assertIn("row\t1\t6\t1030\t残 0%",wire)

    def test_empty_code_roster_does_not_claim_cowork_is_empty(self):
        store.save(self.db,"claude.agents",{"sessionScope":1,"sessions":[]},1000,90)
        wire=store.snapshot(self.db,weather.AKO,1001).decode()
        self.assertIn("確認分 作業 0 待ち 0",wire)
        self.assertIn("Cowork 未取得",wire)
