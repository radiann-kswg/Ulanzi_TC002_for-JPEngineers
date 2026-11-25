"""Commands run by the Windows setup screen. Device operations always take a saved target."""
import ipaddress
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from bridge.config import adb_command, read, update
from scripts.device_audio import STOCK_FILES
from .runner import console_python

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "build/TC002Dev"
PATHS = ROOT / "build/studio-paths.json"


def load_paths(path=PATHS):
    values = read(path)
    ide, sample = values.get("ide", os.environ.get("FLYTHINGS_HOME", "")), values.get("sample", "")
    if not isinstance(ide, str) or not isinstance(sample, str):
        raise ValueError("フォルダーは文字列で指定してください。")
    return ide, sample


def store_paths(ide, sample, path=PATHS):
    update(path, lambda current: {**current, "ide": ide, "sample": sample})


def run_logged(args, action):
    logs = ROOT / "build/studio-logs"
    logs.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=action+"-", suffix=".log", dir=logs, delete=False) as log:
        result = subprocess.run(args, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                env={**os.environ, "PYTHONIOENCODING": "utf-8", "GIT_TERMINAL_PROMPT": "0"},
                                creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        with open(log.name, "rb") as stream:
            stream.seek(max(0, stream.seek(0, os.SEEK_END) - 4096))
            tail = stream.read().decode("utf-8", "replace").splitlines()
        reason = next((line.strip() for line in reversed(tail) if line.strip()), "")
        raise RuntimeError(f"{reason[:260]}\nログ {log.name}")
    return Path(log.name)


def setup_tools(ide, sample):
    store_paths(ide, sample)
    python = console_python()
    for target, requirements in (("bridge-deps", ["-r", str(ROOT / "bridge/requirements.txt")]),
                                 ("audio-tools", ["imageio-ffmpeg==0.6.0"])):
        run_logged([python, "-m", "pip", "install", "--disable-pip-version-check", "--upgrade",
                    "--target", str(ROOT / "build" / target), *requirements], "dependencies")
    return "PC ブリッジと一時実行の音声ツールを準備しました。"


def build_project(ide, sample, prepare_only=False):
    args = [console_python(), str(ROOT / "scripts/build-device.py")]
    if ide:
        args.extend(["--ide", ide])
    elif not prepare_only:
        raise ValueError("FlyThings IDE のフォルダーを選んでください。")
    if sample:
        args.extend(["--sample", sample])
    if prepare_only:
        args.append("--prepare-only")
    store_paths(ide, sample)
    log = run_logged(args, "prepare" if prepare_only else "build")
    return f"{'プロジェクトを生成しました' if prepare_only else 'ARM ビルドが完了しました'}。ログ {log.name}"


def open_ide(ide):
    exe = Path(ide) / "bin/ide.exe"
    if not ide or not exe.is_file():
        raise ValueError("bin/ide.exe を含む FlyThings IDE のフォルダーを選んでください。")
    if not (PROJECT / ".project").is_file():
        raise ValueError("先に「プロジェクトを生成」を実行してください。")
    subprocess.Popen([str(exe.resolve()), "-data", str(ROOT / "flythings-workspace")], cwd=ROOT)
    return "FlyThings で build/TC002Dev を既存プロジェクトとしてインポートしてください。"


def device_target(config_path, ide):
    conf = read(config_path)
    try:
        address = str(ipaddress.IPv4Address(conf.get("device", "")))
    except ValueError:
        raise ValueError("「接続と表示」で時計の IPv4 アドレスを保存してください。") from None
    adb = adb_command(conf, ide)
    if not shutil.which(adb):
        raise ValueError("ADB が見つかりません。「接続と表示」で adb.exe を指定してください。")
    return address, adb


def debug_device(address, adb, restore):
    if not restore and not (PROJECT / "Release/libzkgui.so").is_file():
        raise ValueError("先に「ARM ビルド」を実行してください。")
    args = [console_python(), str(ROOT / "scripts/debug-device.py"), address, "--adb", adb]
    if restore:
        args.append("--restore")
    run_logged(args, "restore" if restore else "debug")
    return f"{address} の一時設定を解除しました。" if restore else f"{address} で独自時計が起動しました。"


def copy_stock_sounds(source):
    """Merge known factory files from this clock's backup into its personal build."""
    if not (PROJECT / ".project").is_file():
        raise ValueError("先に「プロジェクトを生成」を実行してください。")
    source = Path(source)
    available = [name for name in STOCK_FILES if (source / name).is_file()]
    if not available:
        raise RuntimeError("標準音源が見つかりません。同じ時計のバックアップの ui/audio を選んでください。")
    folder = PROJECT / "resources/audio"
    with tempfile.TemporaryDirectory(dir=PROJECT.parent) as work:
        for name in available:
            copy = Path(work) / name
            shutil.copyfile(source / name, copy)
            if not copy.stat().st_size:
                raise RuntimeError(f"標準音源 {name} が空です。音源の読み出し元を確認してください。")
        folder.mkdir(parents=True, exist_ok=True)
        for name in available:
            os.replace(Path(work) / name, folder / name)
    missing = [name for name in STOCK_FILES if name not in available]
    report = f"標準音源を{len(available)}点取り込みました。"
    if missing:
        report += "取り込み元にない音源　" + "、".join(missing) + "。"
    return report + "FlyThings で Image Build を実行してください。"


def import_stock_sounds(address, adb):
    serial = str(ipaddress.IPv4Address(address)) + ":5555"
    with tempfile.TemporaryDirectory() as work:
        incoming = Path(work) / "audio"
        for args in (["connect", serial], ["-s", serial, "pull", "/res/ui/audio", str(incoming)]):
            result = subprocess.run([adb, *args], capture_output=True, timeout=30,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if result.returncode:
                raise RuntimeError("標準音源を取得できませんでした。時計の接続を確認するか、バックアップから取り込んでください。")
        return copy_stock_sounds(incoming)
