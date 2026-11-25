"""Load a TC002Dev build into volatile FlyThings Wi-Fi debug storage."""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from device_audio import STOCK_FILES, find_encoder, trial_cues

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "build/TC002Dev"
DEFAULT_ADB = Path(os.environ["FLYTHINGS_HOME"]) / "sdk/platform-tools/adb/adb.exe" if os.environ.get("FLYTHINGS_HOME") else "adb"
CONFIG = "/tmp/EasyUI.cfg"
LIBRARY = "/tmp/lib/tc002-dev.so"

def debug(ip, adb, restore, audio_only=False):
    serial = str(ipaddress.IPv4Address(ip))+":5555"
    def run(*args):
        try:
            return subprocess.check_output([adb,*args],stderr=subprocess.STDOUT,timeout=25)
        except subprocess.CalledProcessError as exc:
            reason = exc.output.decode("utf8","replace").strip()
            raise RuntimeError(reason or f"ADB failed (exit {exc.returncode}).") from exc
    def shell(command):
        return run("-s",serial,"shell",command).decode("utf8","replace").strip()
    def push(local,remote):
        run("-s",serial,"push",str(local),remote)
    run("connect",serial)
    def active_project():
        content=shell("if [ -f "+CONFIG+" ]; then cat "+CONFIG+"; else echo TC002_NO_CONFIG; fi")
        if content=="TC002_NO_CONFIG":
            return None
        try:
            library=json.loads(content)["startupLibPath"]
            if not isinstance(library,str) or not library:
                raise ValueError("missing startup library")
            return library
        except (ValueError, KeyError, TypeError):
            raise RuntimeError("Could not identify the active temporary project.") from None
    existing=active_project()
    ours=existing==LIBRARY
    if existing is not None and not ours:
        raise RuntimeError("A different temporary FlyThings project is active.")
    def factory():
        active=active_project()
        if active is not None and active!=LIBRARY:
            raise RuntimeError("A different temporary FlyThings project is active.")
        if active is None and shell("if [ -f /tmp/tc002-dev.disabled ]; then echo TC002_RETRY; fi")!="TC002_RETRY":
            return
        resident=json.loads(shell("cat /res/etc/EasyUI.cfg"))["startupLibPath"]
        if not isinstance(resident,str) or not resident.startswith("/res/"):
            raise RuntimeError("Could not identify the resident application. Restart the TC002.")
        def running():
            # The resident TC002 shell has no grep. Inspect the GUI process on the host.
            maps=shell('for p in /proc/[0-9]*; do read -r name < "$p/comm" 2>/dev/null || continue; '
                       'case "$name" in zkgui*) cat "$p/maps" 2>/dev/null;; esac; done')
            return any(line.endswith(" "+resident) for line in maps.splitlines())
        if active is None and running():
            return
        if active==LIBRARY and shell("mv /tmp/EasyUI.cfg /tmp/tc002-dev.disabled && echo TC002_SAVED")!="TC002_SAVED":
            raise RuntimeError("Could not disable the temporary project.")
        if shell("setprop ctl.restart zkswe && echo TC002_RESTORED")=="TC002_RESTORED":
            for _ in range(25):
                if running():
                    return
                time.sleep(1)
        raise RuntimeError("Resident app did not start. Retry Restore, or restart the TC002.")
    if restore:
        factory()
        return
    def install_audio():
        with tempfile.TemporaryDirectory(prefix="tc002-trial-") as folder:
            work = Path(folder)
            encoder = find_encoder()
            personal = PROJECT / "resources/audio"
            stock = personal / "Clock.mp3"
            if not stock.is_file():
                stock = None
            if not stock and encoder and shell("if [ -r /res/ui/audio/Clock.mp3 ]; then echo TC002_STOCK; fi") == "TC002_STOCK":
                stock = work / "stock-second.mp3"
                run("-s", serial, "pull", "/res/ui/audio/Clock.mp3", str(stock))
            # Only these filenames in the volatile debug project belong to this uploader.
            if shell("mkdir -p /tmp/ui/audio && echo READY") != "READY":
                raise RuntimeError("Cannot prepare temporary stock audio.")
            publish = []
            for name in STOCK_FILES:
                path = personal / name
                remote = "/tmp/ui/audio/" + name
                if path.is_file():
                    push(path, remote + ".new")
                    publish.append("mv " + remote + ".new " + remote)
                else:
                    publish.append("rm -f " + remote)
            if shell(" && ".join([*publish, "echo READY"])) != "READY":
                raise RuntimeError("Cannot synchronize temporary stock audio.")
            for path in trial_cues(work, encoder, stock):
                remote = "/tmp/ui/tc002/" + path.name
                push(path, remote + ".new")
                if "READY" not in shell("mv " + remote + ".new " + remote + " && echo READY").splitlines():
                    raise RuntimeError("Audio file was not published.")
    if audio_only:
        if not ours: raise RuntimeError("Start the temporary clock before replacing its sounds.")
        install_audio()
        print("Updated temporary MP3 cues.")
        return
    library=PROJECT/"Release/libzkgui.so"
    if not library.is_file(): raise RuntimeError("Build TC002Dev first.")
    config=json.loads(shell("cat /res/etc/EasyUI.cfg"))
    config.update(startupLibPath=LIBRARY,resPath="/tmp/ui/")
    if "READY" not in shell("mkdir -p /tmp/ui/tc002 /tmp/lib && echo READY"):
        raise RuntimeError("Cannot prepare debug directory.")
    # Atomic replacements keep the running process's mappings intact during a rebuild.
    push(library,LIBRARY+".new")
    if "READY" not in shell("mv "+LIBRARY+".new "+LIBRARY+" && echo READY"):
        raise RuntimeError("Cannot publish debug library.")
    push(PROJECT/"ui/main.ftu","/tmp/ui/main.ftu")
    install_audio()
    with tempfile.TemporaryDirectory(prefix="tc002-config-") as folder:
        cfg=Path(folder)/"EasyUI.cfg"
        cfg.write_text(json.dumps(config),encoding="ascii")
        push(cfg,CONFIG+".new")
    def ready_pid():
        return shell("if [ -f /tmp/tc002-dev.ready ]; then cat /tmp/tc002-dev.ready; fi")
    before=ready_pid()
    try:
        if "READY" not in shell("mv /tmp/EasyUI.cfg.new /tmp/EasyUI.cfg && setprop ctl.restart zkswe && echo READY"):
            raise RuntimeError("Could not start the FlyThings debug service.")
        for _ in range(25):
            time.sleep(1)
            pid=ready_pid()
            if pid.isascii() and pid.isdigit() and pid!=before:
                if LIBRARY in shell("cat /proc/"+pid+"/maps"):
                    print("TC002Dev started (volatile debug).")
                    return
        raise RuntimeError("No startup acknowledgement. Restoring factory UI.")
    except BaseException:
        factory()
        raise

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("ip")
    p.add_argument("--adb",type=Path,default=DEFAULT_ADB)
    p.add_argument("--restore",action="store_true")
    p.add_argument("--audio-only",action="store_true")
    args=p.parse_args()
    debug(args.ip,args.adb,args.restore,args.audio_only)
