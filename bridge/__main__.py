"""Run with python -m bridge. Data collection is read-only and independent of the device."""
import argparse
import asyncio
import concurrent.futures
import ipaddress
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager

from . import claude_desktop, desktop, github, manual, schedules, store, weather
from .config import CONFIG, adb_command, settings, update
from .usage import claude_statusline

def change_place(path,args):
    if (args.lat is None)!=(args.lon is None): raise ValueError("supply both --lat and --lon")
    if args.lat is not None:
        place={"name":args.name,"lat":args.lat,"lon":args.lon}
    else:
        hits=weather.search(args.name)
        if not hits: raise ValueError("no matching place; specify coordinates")
        if len(hits)>1 and args.pick is None:
            for i,hit in enumerate(hits,1): print(i,hit["name"],hit["lat"],hit["lon"])
            print("同名地点があります。--pick 番号で選択してください。")
            return
        index=args.pick or 1
        if not 1<=index<=len(hits): raise ValueError("invalid choice")
        place=hits[index-1]
    store.position(place)
    update(path, lambda current: {**current, "place": place})
    print(place["name"],place["lat"],place["lon"])

def publish(adb,device,wire):
    serial=str(ipaddress.IPv4Address(device))+":5555"
    def run(*args):
        return subprocess.check_output([adb,*args],stderr=subprocess.STDOUT,timeout=20)
    run("connect",serial)
    with tempfile.TemporaryDirectory() as temp:
        path=Path(temp)/"feed"
        path.write_bytes(wire)
        remote="/tmp/tc002-dev."+uuid.uuid4().hex
        run("-s",serial,"push",str(path),remote)
        out=run("-s",serial,"shell","mv "+remote+" /tmp/tc002-dev.feed && echo TC002_OK")
        if b"TC002_OK" not in out: raise RuntimeError("device rejected snapshot")

def jobs(conf,db):
    repos=conf["repos"]
    claude_org=conf.get("claudeOrganization")
    tasks={
        "weather":(900,lambda old,t:weather.observe(conf["place"])),
        "weather.air":(1800,lambda old,t:weather.air(conf["place"])),
        "codex.schedules":(120,lambda old,t:schedules.codex(t,conf.get("timezone","Asia/Tokyo"))),
        "codex.sessions":(30,lambda old,t:asyncio.run(desktop.codex_sessions(t))),
        "codex.limits":(300,lambda old,t:asyncio.run(desktop.codex_limits())),
        "codex.credits":(300,lambda old,t:asyncio.run(desktop.codex_credits(t))),
        "claude.agents":(30,lambda old,t:desktop.claude_sessions(t,old)),
        "claude.desktop.limits":(300,lambda old,t:claude_desktop.limits(t,claude_org)),
        "claude.plan.limits":(300,lambda old,t:claude_desktop.live_limits(claude_org)),
        "github.quota":(300,lambda old,t:github.quota()),
        "github.billing":(1800,lambda old,t:github.billing(t)),
    }
    if conf.get("owner"):
        owner=conf["owner"]
        def owned(collect,old,t):
            # Use a worker-local connection so actions and alerts see new repositories on the next poll.
            from contextlib import closing
            with closing(store.open_db(db)) as state:
                scope=store.previous(state,"github.list").get("repos")
            if scope is None: raise RuntimeError("repository inventory pending")
            return collect(scope,old,t)
        tasks.update({"github.list":(180,lambda old,t:github.ticket_activity(github.owned_tickets(owner),old,t)),
            "github.actions":(240,lambda old,t:owned(github.actions,old,t)),
            "github.alerts":(60,lambda old,t:owned(github.notifications,old,t))})
    elif repos:
        tasks.update({"github.list":(90,lambda old,t:github.ticket_activity(github.tickets(repos),old,t)),
            "github.actions":(45,lambda old,t:github.actions(repos,old,t)),
            "github.alerts":(45,lambda old,t:github.notifications(repos,old,t))})
    return tasks

def serve(db,conf,device,once,out,reload_config=lambda:False):
    dbpath=db.execute("PRAGMA database_list").fetchone()[2]
    tasks=jobs(conf,dbpath)
    # Cache keys reflect the selected repository set and place; old data must never migrate.
    selectors={"repos":[conf.get("owner")]+conf["repos"],"place":conf["place"]}
    old=store.previous(db,"selectors")
    with db:
        if old.get("repos")!=selectors["repos"]:
            db.execute("DELETE FROM sources WHERE name IN ('github.list','github.actions','github.alerts')")
        if old.get("place")!=selectors["place"]:
            db.execute("DELETE FROM sources WHERE name IN ('weather','weather.air')")
    store.save(db,"selectors",selectors,int(time.time()),10**8)
    futures={}
    deadlines={name:0 for name in tasks}
    pushed=0
    states={}
    def push(now):
        wire=store.snapshot(db,conf["place"],now)
        if out: Path(out).write_bytes(wire)
        if device: publish(adb_command(conf),device,wire)
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(tasks)) as pool:
        while True:
            now=int(time.time())
            if not once and reload_config(): return
            for name,(period,collect) in tasks.items():
                if (conf.get("owner") and name in ("github.actions","github.alerts") and
                    "github.list" in futures and not store.previous(db,"github.list")): continue
                if name not in futures and deadlines[name]<=now and (not once or deadlines[name]==0):
                    futures[name]=pool.submit(collect,store.previous(db,name),now)
                    deadlines[name]=now+period
            for name,future in list(futures.items()):
                if not future.done(): continue
                try:
                    data=future.result()
                    store.save(db,name,data,data.get("observedAt",now),max(90,tasks[name][0]*2))
                    status="OK"
                except Exception as exc:
                    store.failed(db,name)
                    status="取得不可 "+type(exc).__name__
                if states.get(name)!=status:
                    print(name,status,flush=True)
                    states[name]=status
                del futures[name]
            if once:
                if not futures and all(deadlines.values()):
                    push(now)
                    return
            elif now-pushed>=15:
                try: push(now)
                except (OSError,RuntimeError,subprocess.SubprocessError) as exc:
                    print("TC002 未接続",type(exc).__name__,file=sys.stderr,flush=True)
                pushed=now
            time.sleep(0.25 if once else 1)

@contextmanager
def watcher_lock(path):
    import msvcrt
    with Path(path).open("a+b") as lock:
        if lock.tell()==0:
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        try: msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        except OSError: raise RuntimeError("A TC002 bridge is already running for this database.") from None
        try: yield
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)

def main(args=None):
    p=argparse.ArgumentParser()
    p.add_argument("--config",type=Path,default=CONFIG)
    p.add_argument("--db",type=Path,default=store.DEFAULT_DB)
    sub=p.add_subparsers(dest="cmd",required=True)
    run=sub.add_parser("run")
    run.add_argument("--device")
    run.add_argument("--once",action="store_true")
    run.add_argument("--out",type=Path)
    sub.add_parser("places").add_argument("query")
    place=sub.add_parser("set-place")
    place.add_argument("name")
    place.add_argument("--lat",type=float)
    place.add_argument("--lon",type=float)
    place.add_argument("--pick",type=int)
    sub.add_parser("import").add_argument("file",type=Path)
    hook=sub.add_parser("hook")
    hook.add_argument("provider",choices=("claude","codex"))
    sub.add_parser("statusline")
    sub.add_parser("status")
    if hasattr(sys.stdout,"reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr,"reconfigure"): sys.stderr.reconfigure(encoding="utf-8")
    a=p.parse_args(args)
    if a.cmd=="places":
        print(json.dumps(weather.search(a.query),ensure_ascii=False,indent=2))
        return
    conf=settings(a.config)
    if a.cmd=="set-place":
        change_place(a.config,a)
        return
    db=store.open_db(a.db)
    try:
        now=int(time.time())
        if a.cmd=="status":
            for name,stamp,ttl,failed in db.execute("SELECT name,stamp,ttl,failed FROM sources ORDER BY name"):
                if name!="selectors":
                    label="前回値" if failed or now-stamp>ttl else "取得済"
                    print(name,label,store.when(stamp))
        elif a.cmd=="run":
            device=a.device or conf.get("device")
            if not (device or a.out): p.error("specify --device or --out")
            with watcher_lock(a.db.with_suffix(".lock")):
                def modified(): return a.config.stat().st_mtime_ns if a.config.exists() else 0
                stop=a.db.parent/f"stop-{os.getpid()}"
                try:
                    while not stop.exists():
                        initial=modified()
                        conf=settings(a.config)
                        serve(db,conf,a.device or conf.get("device"),a.once,a.out,
                              lambda:stop.exists() or modified()!=initial)
                        if a.once: break
                finally:
                    stop.unlink(missing_ok=True)
        elif a.cmd=="import":
            stamp,observations=manual.parse(json.loads(a.file.read_text("utf-8-sig")),now)
            with db:
                for name,data in observations:
                    db.execute("""INSERT INTO sources VALUES (?,?,?,0,?)
                        ON CONFLICT(name) DO UPDATE SET stamp=excluded.stamp,body=excluded.body
                        WHERE excluded.stamp>=sources.stamp""",
                        (name,stamp,86400,json.dumps(data,ensure_ascii=False)))
        elif a.cmd=="hook":
            event=desktop.hook(json.load(sys.stdin.buffer),a.provider,now)
            if event:
                category,item=event
                name=f"hook.{category}.{item[0]}"
                db.execute("BEGIN IMMEDIATE")
                old=store.previous(db,name).get("sessions",[])
                if item[2]=="closed" and old and old[0][2]=="completed": return
                if item[2]=="completed" and old and old[0][2] in ("waiting","failed","closed"): return
                db.execute("DELETE FROM sources WHERE name LIKE 'hook.%' AND stamp<?",(now-7*86400,))
                store.save(db,name,{"sessionScope":category,"sessions":[item]},now,3600)
        elif a.cmd=="statusline":
            raw=json.load(sys.stdin.buffer).get("rate_limits",{})
            if raw:
                data=claude_statusline(raw)
                store.save(db,"claude.limits",data,now,600)
                if "1.left" in data["fields"]: print(data["fields"]["1.left"])
    finally:
        db.close()

if __name__=="__main__": main()
