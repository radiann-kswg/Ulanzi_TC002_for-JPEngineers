"""Parse an explicitly dated local observation. A rejected file never replaces good data."""
import re
from datetime import datetime
from decimal import Decimal
from .desktop import session
from .store import clean

def timestamp(text):
    t=datetime.fromisoformat(str(text))
    if t.utcoffset() is None: raise ValueError("include timezone in timestamps")
    return int(t.timestamp())

def parse(doc,now):
    c={"github":0,"claude":1,"codex":2}[doc["provider"]]
    stamp=timestamp(doc["observedAt"])
    if stamp<=0 or stamp>now+90: raise ValueError("unexpected observation time")
    scope=doc.get("scope","account")
    if scope not in ("account","code","cowork","desktop"): raise ValueError("invalid scope")
    prefix=f"manual.{c}.{scope}."
    obs=[]
    if "remainingPercent" in doc:
        value=float(doc["remainingPercent"])
        if not 0<=value<=100: raise ValueError("invalid remainingPercent")
        entry={"fields":{f"{c}.left":f"{value:g}%"}}
        if "resetsAt" in doc:
            entry["resets"]={"":timestamp(doc["resetsAt"])}
        obs.append((prefix+"left",entry))
    if "extraSpent" in doc:
        billing=doc["extraSpent"]
        amount=Decimal(str(billing["amount"]))
        if not amount.is_finite() or amount<0 or not re.fullmatch("[A-Z]{3}",billing["currency"]):
            raise ValueError("invalid billed amount")
        spent=f"{amount:f}"
        if "budget" in billing:
            budget=Decimal(str(billing["budget"]))
            if not budget.is_finite() or budget<0: raise ValueError("invalid budget")
            spent+=f" / {budget:f}"
        entry={"fields":{f"{c}.extra":f'{spent} {billing["currency"]}'}}
        if "periodEnd" in billing:
            start,end=timestamp(billing["periodStart"]),timestamp(billing["periodEnd"])
            if not start<=stamp<end: raise ValueError("observation outside billing period")
            entry["periodBounds"]=[start,end]
        else:
            period=billing["period"]
            if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])",period): raise ValueError("invalid billing month")
            entry["period"]=period
        obs.append((prefix+"extra",entry))
    if "sessions" in doc:
        if not c: raise ValueError("AI provider required")
        items=[]
        for row in doc["sessions"]:
            if row["state"] not in ("working","waiting","completed","failed","closed"): raise ValueError("invalid session state")
            if not clean(row["id"]) or not clean(row["label"]): raise ValueError("missing session identity")
            items.append(session(row["id"],row["label"],row["state"],stamp))
        obs.append((prefix+"sessions",{"sessionScope":c,"sessions":items}))
    if "schedules" in doc:
        if not c: raise ValueError("AI provider required")
        items=[]
        for row in doc["schedules"]:
            if row.get("enabled",True) is False: continue
            if not clean(row["id"]) or not clean(row["label"]): raise ValueError("missing schedule identity")
            for due in row["occurrences"]:
                items.append([c,str(row["id"]),timestamp(due),clean(row["label"])])
        obs.append((prefix+"schedules",{"scheduleScope":c,"schedules":items}))
    if not obs: raise ValueError("no observation to import")
    return stamp,obs
