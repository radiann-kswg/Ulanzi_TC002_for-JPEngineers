"""Read active Codex desktop automations and calculate upcoming local occurrences."""
import os
import tomllib
from datetime import datetime
from itertools import islice
from pathlib import Path
from zoneinfo import ZoneInfo

from .store import clean

def occurrences(task, now, zone):
    from dateutil.rrule import rrulestr
    if task.get("status")!="ACTIVE": return []
    rule=task["rrule"].removeprefix("RRULE:")
    if not rule or "FREQ=SECONDLY" in rule: raise ValueError("unsupported schedule frequency")
    tz=ZoneInfo(task.get("timezone") or zone)
    created=int(task["created_at"])
    if created>10**11: created//=1000
    start=datetime.fromtimestamp(created,tz).replace(microsecond=0,second=0)
    seq=rrulestr(rule,dtstart=start)
    threshold=datetime.fromtimestamp(now-86400,tz)
    upcoming=[]
    # Separate past and future queries so yesterday's frequent jobs cannot crowd out tomorrow.
    last=seq.before(datetime.fromtimestamp(now,tz),inc=True)
    if last and last>=threshold: upcoming.append(int(last.timestamp()))
    for date in islice(seq.xafter(datetime.fromtimestamp(now,tz)),16):
        upcoming.append(int(date.timestamp()))
    return upcoming

def codex(now, zone="Asia/Tokyo", root=None):
    root=root or Path(os.environ.get("CODEX_HOME",Path.home()/".codex"))/"automations"
    if not root.parent.is_dir(): raise FileNotFoundError("Codex profile")
    schedules=[]
    for file in root.glob("*/automation.toml"):
        with file.open("rb") as stream: task=tomllib.load(stream)
        for due in occurrences(task,now,zone):
            schedules.append([2,str(task["id"]),due,clean(task["name"],40)])
    return {"schedules":schedules,"scheduleScope":2}
