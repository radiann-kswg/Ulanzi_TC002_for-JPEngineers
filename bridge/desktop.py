"""Read status and account limits from documented desktop interfaces."""
import asyncio
import json
import os
import subprocess
from pathlib import Path
from .store import clean, key

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
    limits=data["rateLimits"]
    parts=[]
    for kind in ("primary","secondary"):
        window=limits.get(kind)
        if window and window.get("usedPercent") is not None:
            minutes=window.get("windowDurationMins")
            period={300:"5h",10080:"7d"}.get(minutes,f"{minutes}m" if minutes else kind)
            parts.append(f'{period} {100-window["usedPercent"]:g}%')
    if not parts: raise ValueError("no subscription window")
    return {"fields":{"2.left":" / ".join(parts)}}

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
    return {"sessions":items,"sessionScope":2}

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
    return {"sessions":items,"sessionScope":1}

def hook(data,provider,now):
    category={"claude":1,"codex":2}[provider]
    ev=data.get("hook_event_name")
    state={"UserPromptSubmit":"working","PermissionRequest":"waiting","PostToolUse":"working",
           "Stop":"completed","StopFailure":"failed","Interrupt":"closed","SessionEnd":"closed"}.get(ev)
    if ev=="PreToolUse" and data.get("tool_name","").split(".")[-1] in (
            "AskUserQuestion","request_user_input"): state="waiting"
    if ev=="Notification":
        state={"permission_prompt":"waiting","elicitation_dialog":"waiting",
               "elicitation_url_dialog":"waiting","elicitation_response":"working"}.get(data.get("notification_type"))
    if not state: return None
    uid=data.get("session_id") or data.get("thread_id")
    if not uid: raise ValueError("missing session ID")
    return category,session(uid,title({"cwd":data.get("cwd")}),state,now)
