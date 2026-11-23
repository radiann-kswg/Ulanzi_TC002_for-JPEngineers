"""Stage an Image Build on a selected removable Windows volume."""
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import struct
import tempfile


@dataclass(frozen=True)
class Card:
    root: Path
    serial: int
    label: str


def inspect_card(root):
    root = Path(root)
    if os.name != "nt" or not root.is_absolute() or root != Path(root.anchor) or len(root.drive) != 2:
        raise ValueError("TF カードのドライブ直下を選んでください。")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    if kernel.GetDriveTypeW(str(root)) != 2:  # DRIVE_REMOVABLE
        raise ValueError("リムーバブルドライブとして認識される TF カードを選んでください。")
    serial = wintypes.DWORD()
    label, filesystem = ctypes.create_unicode_buffer(261), ctypes.create_unicode_buffer(32)
    if not kernel.GetVolumeInformationW(str(root), label, len(label), ctypes.byref(serial),
                                        None, None, filesystem, len(filesystem)):
        raise ctypes.WinError(ctypes.get_last_error())
    if filesystem.value.upper() != "FAT32":
        raise ValueError(f"カードの形式は {filesystem.value} です。FAT32 のカードを選んでください。")
    return Card(root, serial.value, label.value)


def image_size(source):
    if source.name.lower() != "update.img" or not source.is_file():
        raise ValueError("FlyThings の Image Build で生成した update.img を選んでください。")
    size = source.stat().st_size
    if not 0 < size < 2**32:
        raise ValueError("空のイメージ、または FAT32 に保存できないサイズです。")
    with source.open("rb") as image:
        header = image.read(572)
    # FlyThings 20260403 fsimg wraps the Z21 res/SquashFS image in this header.
    if (len(header) != 572 or header[:16] != b"ZKSWEV1.0-180127"
            or header[32:36] != b"hsqs" or header[52:57] != bytes.fromhex("02 06 06 55 aa")):
        raise ValueError("対応する Z21 用 Image Build イメージではありません。TC002Dev の出力を選んでください。")
    header_size, payload_size = struct.unpack_from("<II", header, 24)
    if header_size != len(header) or not payload_size or size != header_size + payload_size:
        raise ValueError("イメージの記録サイズとファイル長が一致しません。Image Build をやり直してください。")
    return size


def digest(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def prepare_card(source, card):
    size = image_size(source)
    def check_target():
        if inspect_card(card.root) != card:
            raise ValueError("カードが交換されました。ドライブを選び直してください。")
        if (card.root / "zkautoupgrade").exists():
            raise ValueError("このカードには自動更新用の zkautoupgrade があります。本体で確認できる別のカードを選んでください。")
    check_target()
    dest = card.root / "update.img"
    if dest.exists():
        if source.samefile(dest):
            raise ValueError("照合元には PC 側で生成した update.img を選んでください。")
        if dest.stat().st_size == size:
            existing = digest(dest)
            if digest(source) == existing:
                check_target()
                return existing
        raise FileExistsError("カードに別の update.img があります。退避してから再実行してください。")
    expected = hashlib.sha256()
    stage = None
    try:
        with source.open("rb") as src, tempfile.NamedTemporaryFile(
                prefix=".tc002-", suffix=".tmp", dir=card.root, delete=False) as out:
            stage = Path(out.name)
            while chunk := src.read(1024 * 1024):
                expected.update(chunk)
                out.write(chunk)
            out.flush()
            os.fsync(out.fileno())
        if stage.stat().st_size != size or digest(stage) != expected.hexdigest() or digest(source) != expected.hexdigest():
            raise OSError("カードから読み戻したイメージが一致しません。")
        check_target()
        # Windows rename fails if another writer has already published an image.
        stage.rename(dest)
        stage = None
        return expected.hexdigest()
    finally:
        if stage is not None:
            try:
                if inspect_card(card.root) == card:
                    stage.unlink(missing_ok=True)
            except (OSError, ValueError):
                pass  # The user may already have unplugged the card.
