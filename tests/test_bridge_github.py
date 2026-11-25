import unittest
from unittest.mock import patch
from bridge.github import actions_result, repository, ticket_activity, ticket_events

class ActionsTest(unittest.TestCase):
    def test_repository_alerts_without_inbox_permission(self):
        baseline=ticket_activity({"changes":{"1":[0,"A","old"]}},{},100)
        change=ticket_activity({"changes":{"2":[3,"B","new"]}},baseline,105)
        self.assertEqual({r[2] for r in change["repoAlerts"]},{"PR 終了 A","Issue 新規 B"})
        self.assertEqual(len(ticket_activity({"changes":change["changes"]},change,110)["repoAlerts"]),2)

    @patch("bridge.github.gh")
    def test_actual_ticket_dates_drive_popups(self,gh):
        def row(number,created,closed=None,pr=False):
            iso=lambda t: f"1970-01-01T00:00:{t:02}Z" if t is not None else None
            item={"number":number,"title":"件名","created_at":iso(created),"closed_at":iso(closed)}
            if pr: item["pull_request"]={}
            return item
        # The pages include an edited/reopened ticket, an Issue closure, and a
        # PR which was both opened and merged between two polls.
        gh.return_value=[[row(1,12),row(2,7),row(3,5,13)], [row(4,14,15,True)]]
        seed=ticket_events(["a/b"],{},10)
        gh.assert_not_called()
        data=ticket_events(["a/b"],seed,20)
        self.assertEqual([(uid.rsplit("-",1)[0],label) for _,uid,label in data["events"]],
                         [("issue-open","b#1 件名"),("pr-open","b#4 件名"),("pr-close","b#4 件名")])
        self.assertEqual(ticket_events(["a/b"],data,25)["events"],data["events"])
    def test_workflow_branch_and_retry(self):
        def run(i,branch,result,attempt=1):
            return ("u/r",dict(updated_at=f"2026-06-01T12:00:{i:02d}Z",id=i,
                run_attempt=attempt,workflow_id=8,head_branch=branch,name="CI",
                conclusion=result,status="completed"))
        runs=[run(1,"main","success")]
        state=actions_result(runs,{},100)
        runs.extend([run(2,"main","failure"),run(3,"dev","success"),run(4,"main","success"),run(5,"main","success")])
        state=actions_result(runs,state,120)
        self.assertEqual([e[2] for e in state["events"]],["CI main"])
        self.assertTrue(state["events"][0][1].startswith("action-fail-"))
        self.assertIn("復旧 CI main",state["history"])
        self.assertEqual(len(actions_result(runs,state,130)["events"]),1)
    def test_paths(self):
        for invalid in ("a","a/b/c","../repo","repo?x/r"):
            with self.assertRaises(ValueError): repository(invalid)
