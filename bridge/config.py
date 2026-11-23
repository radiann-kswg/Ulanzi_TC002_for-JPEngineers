"""Read and atomically update the local bridge configuration."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import tempfile

from . import github, store, weather


CONFIG = Path(__file__).with_name("local.json")
STUDIO_PATHS = CONFIG.parents[1] / "build/studio-paths.json"


def adb_command(document, selected_ide=None, *, paths=STUDIO_PATHS):
    if document.get("adb"):
        return document["adb"]
    if not selected_ide:
        try:
            selected_ide = read(paths).get("ide")
        except (OSError, ValueError):
            selected_ide = None
    for folder in (selected_ide, os.environ.get("FLYTHINGS_HOME")):
        if isinstance(folder, str) and folder:
            bundled = Path(folder) / "sdk/platform-tools/adb/adb.exe"
            try:
                if bundled.is_file():
                    return str(bundled.resolve())
            except (ValueError, OSError):
                continue
    return "adb"


def read(path):
    try:
        document = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return {}
    if not isinstance(document, dict):
        raise ValueError("設定ファイルの最上位には JSON オブジェクトが必要です。")
    return document


def settings(path):
    document = read(path)
    document.setdefault("place", dict(weather.AKO))
    store.position(document["place"])
    document["repos"] = list(dict.fromkeys(github.repository(r) for r in document.get("repos", [])))
    return document


@contextmanager
def _write_lock(path):
    # Keep the lock inode in place so waiting writers all synchronize on the same file.
    with path.with_suffix(path.suffix + ".lock").open("a+b") as lock:
        if os.name == "nt":
            import msvcrt
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX)
        yield  # Closing the handle also releases its lock after exceptions.


def update(path, edit):
    """Apply edit to the latest document while holding the writer lock."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with _write_lock(path):
        document = edit(read(path))
        encoded = json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        temporary = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                             prefix=path.name + ".", delete=False) as out:
                temporary = Path(out.name)
                out.write(encoded)
            os.replace(temporary, path)
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)
    return document
