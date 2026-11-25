"""Read the Windows Claude Desktop profile. Only display metadata leaves the PC."""
from datetime import datetime
import json
import os
import subprocess
import tempfile
from pathlib import Path
from uuid import UUID

from .usage import percentage


TREES = {"code": "claude-code-sessions", "cowork": "local-agent-mode-sessions"}


def read(path):
    return json.loads(path.read_bytes())


def profile(org=None):
    root = Path(os.environ["APPDATA"]) / "Claude"
    account = str(UUID(read(root / "config.json")["lastKnownAccountUuid"]))
    organizations = set()
    for tree in TREES.values():
        folder = root / tree / account
        if folder.is_dir():
            for child in folder.iterdir():
                try:
                    uid = str(UUID(child.name))
                except ValueError:
                    continue
                if child.is_dir():
                    organizations.add(uid)
    if org:
        organization = str(UUID(org))
        if organization not in organizations:
            raise ValueError("Claude Desktop organization not in current profile")
    else:
        if len(organizations) != 1:
            raise ValueError("No unique Claude Desktop organization")
        organization = organizations.pop()
    return root, account, organization


def limits(now, org=None):
    root, _, organization = profile(org)
    history = read(root / "plan-usage-history.json")
    if history["version"] != 2:
        raise ValueError("Unknown Claude Desktop usage history")
    samples = (s for s in history["samples"] if s["org"] == organization and 0 < s["t"] <= (now+90)*1000)
    sample = max(samples, key=lambda s: s["t"], default=None)
    if sample is None:
        raise ValueError("No Claude Desktop usage sample for this organization")
    parts = []
    for field, label in (("fh", "5h"), ("sd", "7d")):
        used = sample["u"].get(field)
        if percentage(used):
            parts.append(f"{label} {100-used:g}%")
    fields = {"1.left": " / ".join(parts)} if parts else {}
    extra = sample["u"].get("xu")
    if percentage(extra):
        fields["1.budgetPercent"] = f"予算 {extra:g}%使用"
    return {"observedAt": int(sample["t"] / 1000), "fields": fields}


def plan_limits(raw):
    if not raw.get("rate_limits_available"):
        raise ValueError("Claude plan limits unavailable")
    parts, resets = [], {}
    for key, label in (("five_hour", "5h"), ("seven_day", "7d")):
        window = raw["rate_limits"].get(key) or {}
        used = window.get("utilization")
        if percentage(used):
            parts.append(f"{label} {100-used:g}%")
            try:
                at = datetime.fromisoformat(window.get("resets_at") or "")
                if at.utcoffset() is not None:
                    resets[label] = int(at.timestamp())
            except (TypeError, ValueError, OSError, OverflowError):
                pass
    return {"fields": {"1.left": " / ".join(parts)} if parts else {}, "resets": resets}


def live_limits(org=None):
    _, _, expected = profile(org)
    with tempfile.TemporaryDirectory() as cwd:
        auth = subprocess.run(["claude","auth","status","--json"],cwd=cwd,capture_output=True,check=True,timeout=10)
        if json.loads(auth.stdout).get("orgId") != expected:
            raise ValueError("Claude CLI and Desktop organizations differ")
        requests = [{"type":"control_request","request_id":kind,"request":{"subtype":kind,**options}}
                    for kind,options in (("initialize",{}),("get_usage",{"skip_behaviors":True}))]
        result = subprocess.run(["claude","-p","--input-format","stream-json","--output-format","stream-json",
            "--verbose","--no-session-persistence","--strict-mcp-config","--setting-sources","user","--tools",""],
            cwd=cwd,input=b"".join(json.dumps(r).encode()+b"\n" for r in requests),
            capture_output=True,check=True,timeout=30)
    for line in result.stdout.splitlines():
        message = json.loads(line)
        reply = message.get("response") or {}
        if message.get("type")=="control_response" and reply.get("request_id")=="get_usage" and reply.get("subtype")=="success":
            return plan_limits(reply["response"])
    raise ValueError("Claude usage report unavailable")
