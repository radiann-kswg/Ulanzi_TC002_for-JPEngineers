"""Receive Dot arrival IDs via Chromium native messaging, or register this host on Windows."""
import argparse
import json
from pathlib import Path
import re
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge import store


def receive(stream, reply, db, now):
    size, = struct.unpack("=I", stream.read(4))
    if size > 128 * 1024:
        raise ValueError("oversized Dot message")
    body = stream.read(size)
    if len(body) != size:
        raise ValueError("truncated Dot message")
    items = json.loads(body)
    if not isinstance(items, list) or len(items) > 128:
        raise ValueError("invalid Dot batch")
    with db:
        for item in items:
            uid, at = item["id"], item["at"]
            if not isinstance(uid, str) or not 1 <= len(uid) <= 512 or type(at) is not int:
                raise ValueError("invalid Dot arrival")
            stamp = at // 1000
            if now - 60 <= stamp <= now + 5:
                store.record_popup(db, "dot-new-" + store.key(uid), stamp, "")
    ack = b'{"ok":true}'
    reply.write(struct.pack("=I", len(ack)) + ack)
    reply.flush()


def install(extension_id, browser):
    import winreg
    if not re.fullmatch("[a-p]{32}", extension_id):
        raise ValueError("拡張機能の32文字の ID を指定してください。")
    folder = ROOT / "build/dot-host" / browser
    folder.mkdir(parents=True, exist_ok=True)
    launcher = folder / "dot-host.cmd"
    # Browsers start the host in the manifest's directory. Use relative paths
    # for the script so a Japanese checkout path need not appear in the batch.
    exe = sys.executable.replace("%", "%%")
    launcher.write_text(f'@echo off\n"{exe}" -E "%~dp0..\\..\\..\\scripts\\dot-host.py"\n',
                        encoding="mbcs")
    manifest = folder / "manifest.json"
    manifest.write_text(json.dumps({
        "name": "jp.tc002.dot", "description": "TC002 Dot inbox",
        "path": str(launcher), "type": "stdio",
        "allowed_origins": [f"chrome-extension://{extension_id}/"],
    }), encoding="utf-8")
    vendor = {"chrome": r"Google\Chrome", "edge": r"Microsoft\Edge"}[browser]
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\{vendor}\NativeMessagingHosts\jp.tc002.dot") as reg:
        winreg.SetValueEx(reg, "", 0, winreg.REG_SZ, str(manifest))
    print("Dot 通知の受信先を登録しました。")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--install"]:
        args = argparse.ArgumentParser()
        args.add_argument("--install", metavar="EXTENSION_ID", required=True)
        args.add_argument("--browser", choices=["edge", "chrome"], required=True)
        opts = args.parse_args()
        install(opts.install, opts.browser)
    else:
        from contextlib import closing
        with closing(store.open_db()) as db:
            receive(sys.stdin.buffer, sys.stdout.buffer, db, int(time.time()))
