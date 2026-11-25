"""Persist complete observations independently, then publish one bounded snapshot."""
import hashlib
import json
import sqlite3
import unicodedata
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from .usage import quota_windows, reset_epoch

JST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "build/bridge/state.db"

def clean(value, limit=96):
    text = "".join(c if unicodedata.category(c)[0] != "C" else " " for c in str(value))
    return " ".join(text.split())[:limit]

def when(epoch):
    return datetime.fromtimestamp(epoch, JST).strftime("%m/%d %H:%M")

def key(*parts):
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False).encode()).hexdigest()[:24]

def open_db(path=DEFAULT_DB):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS sources
        (name TEXT PRIMARY KEY, stamp INTEGER NOT NULL, ttl INTEGER NOT NULL,
         failed INTEGER NOT NULL, body TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS input_states
        (category INTEGER, uid TEXT, waiting INTEGER, stamp INTEGER, PRIMARY KEY(category,uid))""")
    db.execute("""CREATE TABLE IF NOT EXISTS popup_events
        (id TEXT PRIMARY KEY, stamp INTEGER, detail TEXT)""")
    return db

def record_popup(db,uid,stamp,detail):
    db.execute("DELETE FROM popup_events WHERE stamp<?",(stamp-60,))
    db.execute("INSERT OR IGNORE INTO popup_events VALUES (?,?,?)",(uid,stamp,detail))

def input_changes(db,name,data,stamp):
    category=data["sessionScope"]
    hook=name.startswith("hook.")
    prior={} if hook else previous(db,name)
    states={uid:(state=="waiting",label) for uid,label,state,_ in data["sessions"]}
    for uid,*_ in prior.get("sessions",[]):
        states.setdefault(uid,(False,""))
    for uid,(waiting,label) in states.items():
        before=db.execute("SELECT waiting,stamp FROM input_states WHERE category=? AND uid=?",
                          (category,uid)).fetchone()
        if before and before[1]>stamp: continue
        if waiting and not (before and before[0]) and (hook or prior or before):
            kind="claude-input-" if category==1 else "codex-input-"
            record_popup(db,kind+uuid.uuid4().hex,stamp,label)
        db.execute("INSERT OR REPLACE INTO input_states VALUES (?,?,?,?)",(category,uid,waiting,stamp))
    db.execute("DELETE FROM input_states WHERE stamp<?",(stamp-7*86400,))

def save(db, name, body, stamp, ttl):
    with db:
        if name in ("github.tickets","github.actions") and body.get("events"):
            # Scanning many repositories can outlast the clock's 60-second delivery window.
            prior={event[1] for event in previous(db,name).get("events",[])}
            body={**body,"events":[[due if uid in prior else stamp,uid,label]
                                  for due,uid,label in body["events"]]}
        if "sessionScope" in body and (name.startswith("hook.") or name in ("claude.agents","codex.sessions")):
            if not db.in_transaction: db.execute("BEGIN IMMEDIATE")
            input_changes(db,name,body,stamp)
        db.execute("INSERT OR REPLACE INTO sources VALUES (?,?,?,0,?)",
                   (name, stamp, ttl, json.dumps(body, ensure_ascii=False, allow_nan=False)))

def failed(db, name):
    with db:
        db.execute("UPDATE sources SET failed=1 WHERE name=?", (name,))

def previous(db, name):
    row = db.execute("SELECT body FROM sources WHERE name=?", (name,)).fetchone()
    return json.loads(row[0]) if row else {}

def position(place):
    lat, lon = float(place["lat"]), float(place["lon"])
    if not (-90 <= lat <= 90 and -180 <= lon <= 180) or not clean(place["name"]):
        raise ValueError("invalid location")
    return lat, lon, clean(place["name"], 40)

def snapshot(db, place, now):
    lat, lon, name = position(place)
    lines = ["TC002/1", f"at\t{now}", f"place\t{lat}\t{lon}\t{name}"]
    pages = defaultdict(list)
    weather_kinds=[]
    notices = {uid:(stamp,uid,detail) for uid,stamp,detail in db.execute(
        "SELECT id,stamp,detail FROM popup_events WHERE stamp BETWEEN ? AND ? ORDER BY stamp,rowid",(now-60,now))}
    schedules = defaultdict(dict)
    groups = {}
    sessions = defaultdict(dict)
    coverage = defaultdict(list)
    scope_sources=defaultdict(set)
    schedule_scope = {}
    inbox=db.execute("SELECT stamp,ttl,failed FROM sources WHERE name='github.alerts'").fetchone()
    live_inbox=inbox and not inbox[2] and now-inbox[0]<=inbox[1]
    for source, stamp, ttl, failure, raw in db.execute(
            "SELECT * FROM sources ORDER BY name"):
        data = json.loads(raw)
        stale = bool(failure or now - stamp > ttl or stamp > now + 90)
        manual = source.startswith("manual")
        if source=="github.list" and not live_inbox:
            for c,p,label in data.get("repoAlerts",[]):
                pages[c,p].append((stamp,stale,label))
        if "scheduleScope" in data:
            schedule_scope[data["scheduleScope"]] = (stamp,stale or manual)
        if "sessionScope" in data:
            c=data["sessionScope"]
            scope_sources[c].add(source)
            coverage[c].append((stamp,stale or manual))
            for uid,label,state,changed in data["sessions"]:
                rank=(changed,not manual)
                if uid not in sessions[c] or rank>sessions[c][uid][0]:
                    sessions[c][uid]=(rank,label,state,stamp,stale or manual)
        for i,(c, p, label) in enumerate(data.get("rows", [])):
            pages[c,p].append((stamp, stale, label))
            if (c,p)==(3,3):
                kinds=data.get("weatherKinds",[])
                weather_kinds.append(kinds[i] if i<len(kinds) else "cloud")
        if source in ("github.tickets","github.actions"):
            for due,uid,label in data.get("events",[]):
                if now-60<=due and uid.startswith(("pr-open-","issue-open-","pr-close-","action-fail-")):
                    notices[uid]=(due,uid,label)
        for c, uid, due, label in data.get("schedules", []):
            observed=schedules[c].get((uid,due))
            if not observed or stamp>=observed[2]:
                schedules[c][uid,due] = (due, label, stamp, stale or manual)
        for group, value in data.get("fields", {}).items():
            # A current automatic observation wins; a newer dated import may replace stale data.
            rank = (not stale and not source.startswith("manual"), stamp)
            if group.endswith(".left"):
                # Keep the deadline and percentage in the same account observation.
                resets=data.get("resets",{})
                current_reset=any(reset_epoch(at) and at>now for at in resets.values())
                rank=(rank[0],rank[0] and current_reset,stamp)
                value=quota_windows(value,resets)
            if group.endswith(".extra") and "period" in data:
                zone=timezone.utc if source=="github.billing" else JST
                if data["period"]!=datetime.fromtimestamp(now,zone).strftime("%Y-%m"):
                    continue
            if group.endswith((".budget",".creditUsed",".budgetPercent")) and "budgetReset" in data and now>=data["budgetReset"]:
                continue
            if "periodBounds" in data and not data["periodBounds"][0]<=now<data["periodBounds"][1]:
                continue
            if group not in groups or rank > groups[group][0]:
                groups[group] = (rank, stamp, stale or manual, value)
    for c, observed in coverage.items():
        members=sorted(sessions[c].values(),reverse=True)
        stamp=min(item[0] for item in observed)
        old=any(item[1] for item in observed)
        missing=[]
        if c==1:
            if "manual.1.cowork.sessions" not in scope_sources[c]: missing.append("Cowork 未取得")
            if not ({"claude.agents","manual.1.code.sessions"} & scope_sources[c]):
                missing.append("Code 未取得")
        elif not ({"codex.sessions","manual.2.desktop.sessions"} & scope_sources[c]):
            missing.append("プロジェクト内")
        counts=[]
        for status,page in (("working",2),("waiting",3),("completed",5)):
            matches=[m for m in members if m[2]==status]
            counts.append(len(matches))
            for rank,label,_,at,stale in matches:
                pages[c,page].append((at,stale,label))
            if not matches: pages[c,page].append((stamp,old,"該当なし"))
        prefix="確認分 " if missing else ""
        pages[c,4].append((stamp,old,prefix+f"作業 {counts[0]} 待ち {counts[1]}"))
        for scope in missing:
            for page in (2,3,4,5): pages[c,page].append((stamp,old,scope))
    for c in range(3):
        left=groups.get(f"{c}.left")
        pages[c,6].append((left[1],left[2],"残 "+left[3]) if left else (0,False,"残 取得不可"))
        amounts=(groups[k] for k in (f"{c}.extra",f"{c}.budget") if k in groups)
        extra=max(amounts,key=lambda obs:obs[0],default=None) or groups.get(f"{c}.creditUsed") or groups.get(f"{c}.budgetPercent")
        pages[c,6].append((extra[1],extra[2],"追加 "+extra[3]) if extra else (0,False,"追加 取得不可"))
    for c, entries in schedules.items():
        listed=set()
        for (uid,due), (_,label,stamp,stale) in sorted(entries.items(),key=lambda item:item[0][1]):
            if due > now and uid not in listed:
                pages[c,1].append((stamp,stale,when(due)+" "+label))
                listed.add(uid)
            if due >= now-60:
                eid = "schedule-"+str(c)+"-"+key(uid)+"-"+str(due)
                notices[eid] = (due,eid,label)
            if due <= now:
                pages[c,0].insert(0,(stamp,stale,when(due)+" "+label+" 予定"))
    for c,(stamp,stale) in schedule_scope.items():
        if not pages[c,1]: pages[c,1].append((stamp,stale,"予定なし"))
        if not pages[c,0]: pages[c,0].append((stamp,stale,"通知なし"))
    labels=[]
    for (c,p), rows in sorted(pages.items()):
        limited = rows[:99] + ([(rows[99][0],rows[99][1],f"ほか {len(rows)-99} 件")] if len(rows)>100 else rows[99:100])
        for i,(stamp, old, label) in enumerate(limited):
            suffix=("\t"+weather_kinds[i]).encode() if (c,p)==(3,3) else b""
            # Allow both a long repository name and its title before the shared byte budget.
            title=clean(label,257)
            if len(title)>256: title=title[:255]+"…"
            labels.append((f"{'old' if old else 'row'}\t{c}\t{p}\t{stamp}\t".encode(),
                           title.encode(),suffix))
    for due, uid, label in sorted(notices.values(),key=lambda event:event[0])[:128]:
        lines.append(f"event\t{due}\t{clean(uid,72)}\t{clean(label,256)}")
    header=("\n".join(lines)+"\n").encode()
    budget=(262144-len(header)-4-sum(len(prefix)+len(suffix)+1 for prefix,_,suffix in labels))//max(1,len(labels))
    wire=bytearray(header)
    for prefix,label,suffix in labels:
        if len(label)>budget:
            label=label[:budget-3].decode("utf-8","ignore").encode()+"…".encode()
        wire.extend(prefix+label+suffix+b"\n")
    return bytes(wire)+b"END\n"
