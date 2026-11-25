"""Read status and account limits from documented desktop interfaces."""
import asyncio
import http.client
import json
import os
import subprocess
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from .store import clean, key
from .usage import budget_used, percentage, reset_epoch

def title(item):
    return clean(item.get("name") or Path(item.get("cwd") or "").name or "セッション",36)

def session(uid,label,status,changed):
    return [key(str(uid)),clean(label,36),status,int(changed)]

class CodexRPC:
    def __init__(self,shared):
        self.shared=shared
        self.n=0

    async def __aenter__(self):
        args=["codex","app-server"]+(["proxy"] if self.shared else ["--stdio"])
        self.proc=await asyncio.create_subprocess_exec(*args,stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,stderr=subprocess.DEVNULL,limit=16*1024*1024)
        try:
            await self.call("initialize",{"clientInfo":{"name":"tc002_clock","version":"1.0"},
                                          "capabilities":{"experimentalApi":True}})
            self.write({"method":"initialized"})
        except BaseException:
            await self.__aexit__(None,None,None)
            raise
        return self

    def write(self,message):
        self.proc.stdin.write(json.dumps(message).encode()+b"\n")

    async def call(self,method,params):
        self.n+=1
        self.write({"id":self.n,"method":method,"params":params})
        await self.proc.stdin.drain()
        async with asyncio.timeout(12):
            while True:
                line=await self.proc.stdout.readline()
                if not line: raise ConnectionError("Codex app server closed")
                msg=json.loads(line)
                if msg.get("id")==self.n and "method" not in msg:
                    if "error" in msg: raise RuntimeError("Codex method unavailable: "+method)
                    return msg["result"]

    async def __aexit__(self,*exc):
        self.proc.stdin.close()
        # Drain the output pipe before the per-poll Windows event loop closes.
        try: await asyncio.wait_for(self.proc.communicate(),2)
        except TimeoutError:
            if self.proc.returncode is None: self.proc.kill()
            await self.proc.communicate()

async def codex_limits():
    async with CodexRPC(False) as rpc:
        data=await rpc.call("account/rateLimits/read",{})
    limits=(data.get("rateLimitsByLimitId") or {}).get("codex") or data["rateLimits"]
    fields, resets={}, {}
    parts=[]
    for kind in ("primary","secondary"):
        window=limits.get(kind)
        if window and percentage(window.get("usedPercent")):
            minutes=window.get("windowDurationMins")
            period={300:"5h",10080:"7d"}.get(minutes,f"{minutes}m" if minutes else kind)
            parts.append(f'{period} {100-window["usedPercent"]:g}%')
            if reset_epoch(window.get("resetsAt")):
                resets[period]=window["resetsAt"]
    if parts:
        fields["2.left"]=" / ".join(parts)
    result={"fields":fields}
    if resets: result["resets"]=resets
    budget=limits.get("individualLimit") or {}
    amount=budget_used(budget.get("used"),budget.get("limit"),"cr")
    if amount is not None:
        fields["2.budget"]=amount
        if reset_epoch(budget.get("resetsAt")):
            result["budgetReset"]=budget["resetsAt"]
    return result

def personal_credit_usage(report, now):
    today=datetime.fromtimestamp(now,timezone.utc).date()
    start=today.replace(day=1)
    end=(start+timedelta(days=32)).replace(day=1)
    rows=report["data"]
    if not isinstance(rows,list) or report.get("has_more") or report.get("next_cursor"):
        raise ValueError("incomplete credit history")
    total=Decimal(0)
    for row in rows:
        day=date.fromisoformat(row["date"][:10])
        if not start<=day<=today: continue
        if "credit_amount" in row:
            amounts=[row["credit_amount"]]
        elif isinstance(row.get("premium_usage_values"),dict) and isinstance(row["premium_usage_values"].get("credit_usage_credits"),dict):
            amounts=row["premium_usage_values"]["credit_usage_credits"].values()
        elif isinstance(row.get("models"),list):
            amounts=[m["on_demand_credits"] for m in row["models"]]
        else:
            raise ValueError("unknown credit history row")
        for value in amounts:
            try: amount=Decimal(str(value))
            except InvalidOperation: raise ValueError("invalid credit amount") from None
            if not amount.is_finite() or amount<0: raise ValueError("invalid credit amount")
            total+=amount
    bounds=[int(datetime(d.year,d.month,1,tzinfo=timezone.utc).timestamp()) for d in (start,end)]
    return {"fields":{"2.creditUsed":f"{total:f} cr"},"periodBounds":bounds}

async def codex_credits(now):
    async with CodexRPC(False) as rpc:
        account=(await rpc.call("account/read",{"refreshToken":False})).get("account") or {}
    if account.get("type")!="chatgpt" or account.get("planType") not in ("free","go","plus","pro","prolite","promax"):
        return {"fields":{}}
    path=Path(os.environ.get("CODEX_HOME",Path.home()/".codex"))/"auth.json"
    tokens=json.loads(path.read_bytes())["tokens"]
    # Send only to the first-party usage endpoint. HTTPSConnection does not follow redirects.
    conn=http.client.HTTPSConnection("chatgpt.com",timeout=15)
    try:
        conn.request("GET","/backend-api/wham/usage/credit-usage-events",headers={
            "Authorization":"Bearer "+tokens["access_token"],"ChatGPT-Account-Id":tokens["account_id"],
            "Accept":"application/json","x-openai-codex-usage-categories":"1","User-Agent":"TC002-clock"})
        response=conn.getresponse()
        if response.status!=200: raise RuntimeError(f"Codex credit history HTTP {response.status}")
        raw=response.read(4*1024*1024+1)
        if len(raw)>4*1024*1024: raise ValueError("credit history too large")
        return personal_credit_usage(json.loads(raw,parse_float=Decimal),now)
    finally:
        conn.close()

async def codex_sessions(now):
    # Only a shared server can attest to the state of threads in the running desktop.
    async with CodexRPC(True) as rpc:
        after=None
        items=[]
        while True:
            batch=await rpc.call("thread/list",{"sourceKinds":["vscode","appServer"],"limit":100,
                "sortKey":"updated_at","cursor":after})
            for thread in batch["data"]:
                status=thread["status"]["type"]
                if status=="active":
                    flags=thread["status"]["activeFlags"]
                    state="waiting" if {"waitingOnApproval","waitingOnUserInput"}.intersection(flags) else "working"
                    items.append(session(thread["id"],title(thread),state,now))
                elif status=="idle" and len(items)<50 and thread["updatedAt"]>=now-86400:
                    # Never equate idle, an interrupted turn or an unloaded thread with completion.
                    detail=await rpc.call("thread/read",{"threadId":thread["id"],"includeTurns":True})
                    turns=detail["thread"]["turns"]
                    if turns and turns[-1]["status"]=="completed":
                        items.append(session(thread["id"],title(thread),"completed",thread["updatedAt"]))
            after=batch.get("nextCursor")
            if not after: break
    return {"sessions":items,"sessionScope":2,"observedAt":now}

def claude_sessions(now,old=None):
    result=subprocess.run(["claude","agents","--json","--all"],capture_output=True,timeout=15,check=True)
    found=json.loads(result.stdout)
    if not isinstance(found,list): raise ValueError("unexpected agent listing")
    items=[]
    prior={s[0]:s for s in (old or {}).get("sessions",[])}
    for item in found:
        uid=item.get("sessionId") or item.get("session_id") or item.get("id")
        mapped={"working":"working","blocked":"waiting","done":"completed",
                "failed":"failed","stopped":"closed"}.get(item.get("state"))
        if item.get("status")=="waiting" and item.get("waitingFor"):
            mapped="waiting"
        elif not mapped:
            mapped={"busy":"working","waiting":"waiting"}.get(item.get("status"))
        if uid and mapped:
            entry=session(uid,title(item),mapped,now)
            before=prior.get(entry[0])
            if before and before[2]==mapped: entry[3]=before[3]
            items.append(entry)
    return {"sessions":items,"sessionScope":1,"observedAt":now}

def hook(data,provider,now):
    category={"claude":1,"codex":2}[provider]
    ev=data.get("hook_event_name")
    state={"UserPromptSubmit":"working","PermissionRequest":"waiting","PostToolUse":"working",
           "Stop":"completed","StopFailure":"failed","Interrupt":"closed","SessionEnd":"closed"}.get(ev)
    tool=data.get("tool_name","").split(".")[-1].split("__")[-1]
    if ev=="PreToolUse" and tool in ("AskUserQuestion","request_user_input","request_user_input_async"):
        state="waiting"
    if ev=="PostToolUse" and tool=="request_user_input_async": return None
    if ev=="Notification":
        state={"permission_prompt":"waiting","elicitation_dialog":"waiting",
               "elicitation_url_dialog":"waiting","elicitation_response":"working"}.get(data.get("notification_type"))
    if not state: return None
    uid=data.get("session_id") or data.get("thread_id")
    if not uid: raise ValueError("missing session ID")
    return category,session(uid,title({"cwd":data.get("cwd")}),state,now)
