"""Merge TC002 observers into this project's Codex and Claude settings."""
import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]

def install(path,provider):
    data=json.loads(path.read_text("utf-8-sig")) if path.exists() else {}
    groups=data.setdefault("hooks",{})
    events=["UserPromptSubmit","PreToolUse","PermissionRequest","PostToolUse","Stop","SessionEnd"]
    events+=["Notification","StopFailure"] if provider=="claude" else ["Interrupt"]
    exe=Path(sys.executable).as_posix()
    receiver=(ROOT/"scripts/receive-hook.py").as_posix()
    old_command=f'"{exe}" "{receiver}" hook {provider}'
    command=subprocess.list2cmdline([exe,receiver,"hook",provider])
    for event in events:
        handler={"type":"command","command":command,"timeout":3}
        group={"hooks":[handler]}
        if event=="PreToolUse":
            group["matcher"]="AskUserQuestion|request_user_input(_async)?"
        entries=groups.setdefault(event,[])
        for entry in entries:
            for existing in entry.get("hooks",[]):
                if existing.get("command")==old_command: existing["command"]=command
            if (event=="PreToolUse" and entry.get("matcher")=="AskUserQuestion|request_user_input"
                    and entry.get("hooks")==[handler]):
                entry["matcher"]=group["matcher"]
        if group not in entries: entries.append(group)
    # Preserve existing settings, including any unrelated hooks.
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w",encoding="utf-8",dir=path.parent,delete=False) as f:
        json.dump(data,f,ensure_ascii=False,indent=2)
        f.write("\n")
    os.replace(f.name,path)

if __name__=="__main__":
    install(ROOT/".codex/hooks.json","codex")
    install(ROOT/".claude/settings.local.json","claude")
