"""Bridge process controls for the desktop application."""
import locale
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def console_python():
    """Use the console interpreter for background commands started by pythonw."""
    executable = Path(sys.executable)
    if executable.name.lower() == "pythonw.exe":
        executable = executable.with_name("python.exe")
    return str(executable)


def bridge_action(action):
    command = ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
               "Bypass", "-File", str(ROOT / "scripts/start-bridge.ps1")]
    if action == "start":
        command.extend(["-Python", console_python()])
    elif action in ("stop", "status"):
        command.append("-" + action.capitalize())
    else:
        raise ValueError("Unknown bridge action")
    # A detached worker can inherit PowerShell's output handles. Reading a file
    # after PowerShell exits doesn't wait for the worker to close those handles.
    with tempfile.TemporaryFile() as log:
        result = subprocess.run(command, cwd=ROOT, timeout=65, stdout=log, stderr=subprocess.STDOUT,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        log.seek(0)
        output = log.read().decode(locale.getpreferredencoding(False), errors="replace")
    if result.returncode:
        detail = output.strip()
        raise RuntimeError("ブリッジの操作に失敗しました。\n" + (detail[:500] or "build/bridge/runner.err を確認してください。"))
    if "Finishing current requests" in output:
        return "停止処理中です。しばらくしてから状態を確認してください。"
    if "stopped" in output:
        return "ブリッジは停止しています。"
    if "already running" in output or "bridge started" in output:
        return "ブリッジは実行中です。"
    raise RuntimeError("ブリッジの状態を確認できませんでした。build/bridge/runner.err を確認してください。")
