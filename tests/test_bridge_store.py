import tempfile
import unittest
from pathlib import Path
from bridge import manual, store, weather

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

    def test_notification_includes_title_after_long_repository(self):
        label="PR 終了 "+"long-repository-"*4+"#21 完了した作業名"
        store.save(self.db,"test.event",{"events":[[1000,"pr21",label]]},1000,90)
        self.assertIn("event\t1000\tpr21\t"+label+"\n",store.snapshot(self.db,weather.AKO,1000).decode())

    def test_date_and_amount_separate(self):
        store.save(self.db,"manual.cost",{"fields":{"1.extra":"2 USD"}},1000,30)
        store.save(self.db,"claude",{"fields":{"1.left":"0%"}},1030,45)
        wire=store.snapshot(self.db,weather.AKO,1040).decode()
        self.assertIn("old\t1\t6\t1000\t追加 2 USD",wire)
        self.assertIn("row\t1\t6\t1030\t残 0%",wire)

    def test_window_resets_and_budget_expire_independently(self):
        store.save(self.db,"codex.limits",{"fields":{"2.left":"5h 80% / 7d 12%",
                   "2.budget":"1.5 / 10 cr"},"budgetReset":1200,"resets":{"5h":1800}},1000,600)
        for now,credit in ((1100,"1.5 / 10 cr"),(1200,"取得不可")):
            wire=store.snapshot(self.db,weather.AKO,now).decode()
            self.assertIn("残 5h 80% リセット 1970-01-01T00:30:00Z / 7d 12% リセット ?\n",wire)
            self.assertIn(f"\t2\t6\t{1000 if now<1200 else 0}\t追加 {credit}\n",wire)

    def test_imported_amount_and_reset_reach_the_same_page(self):
        stamp,observations=manual.parse({"provider":"github","observedAt":"2026-11-25T08:00:00Z",
            "remainingPercent":70,"resetsAt":"2026-11-25T18:00:00+09:00",
            "extraSpent":{"amount":0,"budget":20,"currency":"USD","period":"2026-11"}},1800000000)
        for name,body in observations:
            store.save(self.db,name,body,stamp,300)
        wire=store.snapshot(self.db,weather.AKO,stamp).decode()
        self.assertIn(f"old\t0\t6\t{stamp}\t残 70% リセット 2026-11-25T09:00:00Z\n",wire)
        self.assertIn(f"old\t0\t6\t{stamp}\t追加 0 / 20 USD\n",wire)

    def test_empty_code_roster_does_not_claim_cowork_is_empty(self):
        store.save(self.db,"claude.agents",{"sessionScope":1,"sessions":[]},1000,90)
        wire=store.snapshot(self.db,weather.AKO,1001).decode()
        self.assertIn("確認分 作業 0 待ち 0",wire)
        self.assertIn("Cowork 未取得",wire)
