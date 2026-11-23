import unittest
from bridge.github import actions_result, repository, ticket_activity

class ActionsTest(unittest.TestCase):
    def test_repository_alerts_without_inbox_permission(self):
        baseline=ticket_activity({"changes":{"1":[0,"A","old"]}},{},100)
        self.assertEqual(baseline["repoEvents"],[])
        change=ticket_activity({"changes":{"2":[3,"B","new"]}},baseline,105)
        self.assertEqual([e[2] for e in change["repoEvents"]],["PR 終了 A","Issue 新規 B"])
        self.assertEqual(len(ticket_activity({"changes":change["changes"]},change,110)["repoAlerts"]),2)
    def test_workflow_branch_and_retry(self):
        def run(i,branch,result,attempt=1):
            return ("u/r",dict(updated_at=f"2026-06-01T12:00:{i:02d}Z",id=i,
                run_attempt=attempt,workflow_id=8,head_branch=branch,name="CI",
                conclusion=result,status="completed"))
        runs=[run(1,"main","success")]
        state=actions_result(runs,{},100)
        runs.extend([run(2,"main","failure"),run(3,"dev","success"),run(4,"main","success"),run(5,"main","success")])
        state=actions_result(runs,state,120)
        self.assertEqual([e[2] for e in state["events"]],["失敗 CI main","復旧 CI main"])
        self.assertEqual(len(actions_result(runs,state,130)["events"]),2)
    def test_paths(self):
        for invalid in ("a","a/b/c","../repo","repo?x/r"):
            with self.assertRaises(ValueError): repository(invalid)
