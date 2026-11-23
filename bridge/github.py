"""Read GitHub repository and account data through the signed-in gh CLI."""
import asyncio
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal

from .store import clean, key

def gh(*args):
    run=subprocess.run(["gh","api",*args],capture_output=True,timeout=40)
    if run.returncode:
        raise RuntimeError("GitHub API unavailable or missing read permission")
    return json.loads(run.stdout)

def repository(value):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",value) or any(
            part in (".","..") for part in value.split("/")):
        raise ValueError("expected GitHub owner/name")
    return value

def tickets(repos):
    rows=[]
    changes={}
    pulls=issues=0
    decisions={"APPROVED":"承認済","CHANGES_REQUESTED":"変更依頼","REVIEW_REQUIRED":"審査待ち"}
    for repo in repos:
        owner,name=repository(repo).split("/")
        for kind,page in (("pullRequests",0),("issues",3)):
            fields=("isDraft reviewDecision author{login}" if not page else "")
            query="""query($owner:String!,$name:String!,$endCursor:String){
                viewer{login} repository(owner:$owner,name:$name){ KIND(states:OPEN,first:100,
                after:$endCursor,orderBy:{field:UPDATED_AT,direction:DESC}){totalCount
                pageInfo{hasNextPage endCursor} nodes{number title updatedAt FIELDS}}}}""".replace(
                    "KIND",kind).replace("FIELDS",fields)
            results=gh("graphql","--paginate","--slurp","-f","query="+query,"-f","owner="+owner,"-f","name="+name)
            count=results[0]["data"]["repository"][kind]["totalCount"]
            if page: issues+=count
            else: pulls+=count
            for result in results:
                viewer=result["data"]["viewer"]["login"]
                for node in result["data"]["repository"][kind]["nodes"]:
                    label=f'{name}#{node["number"]} '+clean(node["title"])
                    changes[key(repo,page,node["number"])]=[page,label,node["updatedAt"]]
                    rows.append([0,page,("草稿 " if node.get("isDraft") else "")+label])
                    if not page and (node.get("author") or {}).get("login")==viewer:
                        rows.append([0,5,"自分 "+decisions.get(node["reviewDecision"],"未審査")+" "+label])
        requests=gh("--method","GET","--paginate","--slurp","search/issues","-f",
                    "q=repo:"+repo+" is:open is:pr review-requested:@me","-f","per_page=100")
        for result in requests:
            for pr in result["items"]:
                rows.append([0,5,f'依頼 {name}#{pr["number"]} '+clean(pr["title"])])
    for page,num in ((1,pulls),(4,issues)):
        rows.append([0,page,str(num)+"件"])
    for page in (0,3,5):
        if not any(r[1]==page for r in rows): rows.append([0,page,"該当なし"])
    return {"rows":rows,"changes":changes}

def owned_tickets(owner):
    repository(owner+"/check")
    # Fetch totals for every owned repository, including drafts and private work.
    query="""query($owner:String!,$endCursor:String){
      viewer{login} repositoryOwner(login:$owner){repositories(first:15,after:$endCursor,
      ownerAffiliations:[OWNER]){pageInfo{endCursor hasNextPage} nodes{nameWithOwner
      issues(states:OPEN,first:100,orderBy:{field:UPDATED_AT,direction:DESC}){totalCount nodes{number title updatedAt}}
      pullRequests(states:OPEN,first:100,orderBy:{field:UPDATED_AT,direction:DESC}){totalCount
      nodes{number title updatedAt isDraft reviewDecision author{login}}}}}}}"""
    batches=gh("graphql","--paginate","--slurp","-f","query="+query,"-f","owner="+owner)
    rows=[]
    repos=[]
    changes={}
    counts={1:0,4:0}
    for batch in batches:
        viewer=batch["data"]["viewer"]["login"]
        for repo in batch["data"]["repositoryOwner"]["repositories"]["nodes"]:
            full=repo["nameWithOwner"]
            if full.split("/")[0].casefold()!=owner.casefold(): continue
            repos.append(full)
            if max(repo[k]["totalCount"] for k in ("issues","pullRequests"))>100:
                detail=tickets([full])
                changes.update(detail["changes"])
                for _,page,text in detail["rows"]:
                    if page in counts: counts[page]+=int(text[:-1])
                    elif text!="該当なし" and not text.startswith("依頼 "): rows.append([0,page,text])
                continue
            for kind,page,cp in (("issues",3,4),("pullRequests",0,1)):
                counts[cp]+=repo[kind]["totalCount"]
                for node in repo[kind]["nodes"]:
                    label=f'{full.split("/")[1]}#{node["number"]} '+clean(node["title"])
                    changes[key(full,page,node["number"])]=[page,label,node["updatedAt"]]
                    rows.append([0,page,("草稿 " if node.get("isDraft") else "")+label])
                    if page==0 and (node.get("author") or {}).get("login")==viewer:
                        status={"APPROVED":"承認済","CHANGES_REQUESTED":"変更依頼","REVIEW_REQUIRED":"審査待ち"}
                        rows.append([0,5,"自分 "+status.get(node["reviewDecision"],"未審査")+" "+label])
    matches=gh("--method","GET","--paginate","--slurp","search/issues","-f",
               f"q=user:{owner} is:open is:pr review-requested:@me","-f","per_page=100")
    for batch in matches:
        for pr in batch["items"]:
            rows.append([0,5,f'依頼 {pr["repository_url"].rsplit("/",1)[-1]}#{pr["number"]} '+clean(pr["title"])])
    rows.extend([0,p,f"{n}件"] for p,n in counts.items())
    for p in (0,3,5):
        if not any(row[1]==p for row in rows): rows.append([0,p,"該当なし"])
    return {"rows":rows,"repos":repos,"changes":changes}

def ticket_activity(data,old,now):
    before=old.get("changes")
    current=data["changes"]
    history=old.get("repoAlerts",[])[:]
    events=[event for event in old.get("repoEvents",[]) if event[0]>=now-60]
    if before is not None:
        for uid in sorted(before.keys()|current.keys()):
            if before.get(uid)==current.get(uid): continue
            page,label,stamp=(current.get(uid) or before[uid])
            change="新規" if uid not in before else "終了" if uid not in current else "更新"
            text=("PR " if page==0 else "Issue ")+change+" "+label
            history.insert(0,[0,page,text])
            events.append([now,key(uid,stamp,change),text])
    data.update(repoAlerts=history[:30],repoEvents=events[-64:])
    return data

def actions_result(runs,old,now):
    states=old.get("branches",{}).copy()
    # Keep only recently seen run attempts; a second attempt has its own conclusion.
    seen=set(old.get("seen",[]))
    current=set()
    rows=[]
    events=[e for e in old.get("events",[]) if e[0]>=now-60]
    history=old.get("history",[])[:]
    for repo,run in sorted(runs,key=lambda pair:(pair[1]["updated_at"],pair[1]["id"],pair[1]["run_attempt"])):
        result=run["conclusion"] or run["status"]
        branch=run["head_branch"] or "?"
        label=clean(run["name"])+" "+branch
        rows.insert(0,[0,2,result+" "+label])
        if not run["conclusion"]: continue
        uid=key(repo,run["id"],run["run_attempt"],result)
        current.add(uid)
        if uid in seen: continue
        group=key(repo,run["workflow_id"],branch)
        prev=states.get(group,{})
        point=[run["updated_at"],run["id"],run["run_attempt"]]
        if prev.get("point",[])>point: continue
        is_failure=result in ("failure","timed_out","startup_failure")
        recovered=result=="success" and prev.get("failed",False)
        if is_failure or result=="success":
            states[group]={"point":point,"failed":is_failure}
        if old and (is_failure or recovered):
            text=("失敗 " if is_failure else "復旧 ")+label
            events.append([now,uid,text])
            history.insert(0,text)
    return {"rows":[[0,2,item] for item in history[:20]]+(rows or [[0,2,"実行なし"]]),
            "events":events,"history":history[:20],"seen":sorted(current),"branches":states}

def actions(repos,old,now):
    def fetch(repo):
        result=gh("repos/"+repository(repo)+"/actions/runs?per_page=100")
        return [(repo,r) for r in result["workflow_runs"]]
    with ThreadPoolExecutor(max_workers=4) as pool:
        runs=[item for group in pool.map(fetch,repos) for item in group]
    return actions_result(runs,old,now)

def notifications(repos,old,now):
    rows=old.get("rows",[])[:]
    seen=set(old.get("seen",[]))
    current=set()
    events=[e for e in old.get("events",[]) if e[0]>=now-60]
    # Repository endpoint returns the current user's subscribed notifications for this repo.
    scope={repo.casefold() for repo in repos}
    pages=gh("--paginate","--slurp","notifications?per_page=100")
    for batch in reversed(pages):
        for item in reversed(batch):
            repo=item["repository"]["full_name"]
            if repo.casefold() not in scope: continue
            typ=item["subject"]["type"]
            if typ not in ("PullRequest","Issue"): continue
            uid=key(repo,item["id"],item["updated_at"])
            current.add(uid)
            if uid in seen: continue
            text=("PR通知 " if typ=="PullRequest" else "Issue通知 ")+clean(item["subject"]["title"])
            row=[0,0 if typ=="PullRequest" else 3,text]
            if row in rows: rows.remove(row)
            rows.insert(0,row)
            if old: events.append([now,uid,text])
    return {"rows":rows[:30],"events":events,"seen":sorted(current|set(old.get("seen",[])[-200:]))}

def billing(now):
    login=gh("user")["login"]
    t=datetime.fromtimestamp(now,timezone.utc)
    data=gh(f"users/{login}/settings/billing/ai_credit/usage?year={t.year}&month={t.month}")
    amounts=[Decimal(str(row["netAmount"])) for row in data["usageItems"]]
    total=sum(amounts,Decimal(0))
    return {"fields":{"0.extra":f"{total:.2f} USD"},"period":t.strftime("%Y-%m")}

async def _quota():
    from copilot import CopilotClient
    from copilot.generated.rpc import AccountGetQuotaRequest
    client=CopilotClient()
    try:
        await client.start()
        result=await client.rpc.account.get_quota(AccountGetQuotaRequest(),timeout=10)
        premium=result.quota_snapshots["premium_interactions"]
        if premium.entitlement_requests==-1: return {"fields":{"0.left":"無制限"}}
        return {"fields":{"0.left":f"{premium.remaining_percentage:g}%"}}
    finally:
        await client.stop()

def quota():
    return asyncio.run(asyncio.wait_for(_quota(),25))
