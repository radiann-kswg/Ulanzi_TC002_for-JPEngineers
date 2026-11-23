"""Bridge process controls for the desktop application."""
import locale
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def bridge_action(action):
    executable = Path(sys.executable)
    if executable.name.lower() == "pythonw.exe":
        executable = executable.with_name("python.exe")
    command = ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
               "Bypass", "-File", str(ROOT / "scripts/start-bridge.ps1")]
    if action == "start":
        command.extend(["-Python", str(executable)])
    elif action in ("stop", "status"):
        command.append("-" + action.capitalize())
    else:
        raise ValueError("Unknown bridge action")
    result = subprocess.run(command, cwd=ROOT, timeout=65, capture_output=True,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        detail = result.stderr.decode(locale.getpreferredencoding(False), errors="replace").strip()
        raise RuntimeError("ブリッジの操作に失敗しました。\n" + (detail[:500] or "build/bridge/runner.err を確認してください。"))
    output = result.stdout.decode("ascii", errors="replace")
    if "Finishing current requests" in output:
        return "停止処理中です。しばらくしてから状態を確認してください。"
    if "stopped" in output:
        return "ブリッジは停止しています。"
    if "already running" in output or "bridge started" in output:
        return "ブリッジは実行中です。"
    raise RuntimeError("ブリッジの状態を確認できませんでした。build/bridge/runner.err を確認してください。")
