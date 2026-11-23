"""Prepare the TC002Dev IDE project and cross-compile it with the FlyThings Z21 SDK."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import wave
import math
import random
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from collections import deque

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "build" / "TC002Dev"
UPSTREAM = "https://github.com/UlanziTechnology/Ulanzi-U-Clock-TC002.git"
REVISION = "677a3aa89784bcb0b3e5ffa6db954efa0ce880de"
DEMO = "Z21_TC002_Demo"

def write_if_changed(path, data):
    if not path.exists() or path.read_bytes() != data:
        path.parent.mkdir(parents=True, exist_ok=True)
        output = tempfile.NamedTemporaryFile(delete=False, dir=path.parent)
        temp = Path(output.name)
        try:
            with output:
                output.write(data)
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)

def sync(src, dst):
    for path in src.rglob("*"):
        if path.is_file():
            write_if_changed(dst / path.relative_to(src), path.read_bytes())

def clock_strike(name):
    # Three damped modes of the case beneath a short, noisy escapement click.
    strikes={"minute":[(0,.70)], "hour":[(0,.48),(.115,.90)],
             "midnight":[(0,.50),(.14,.68),(.32,1.0)]}[name]
    rng=random.Random(42)
    samples=[0.] * int((strikes[-1][0]+.32)*16000)
    for delay,force in strikes:
        for i in range(int(.30*16000)):
            t=i/16000
            body=sum(gain*math.exp(-t/tau)*math.sin(2*math.pi*hz*t)
                     for hz,gain,tau in ((260,.68,.044),(471,.37,.030),(973,.17,.022)))
            click=rng.uniform(-1,1)*math.exp(-t/.007)
            samples[int(delay*16000)+i]+=force*min(1,t/.0014)*(body+.62*click)
    return struct.pack("<%dh"%len(samples),*(int(s*9500) for s in samples))

def negaclip_face(width, rows):
    """Only enclosed transparent pixels belong to the white-cut letter."""
    outside=set()
    pending=deque([(-1,-1)])
    while pending:
        x,y=pending.popleft()
        if (x,y) in outside or not (-1<=x<=width and -1<=y<=12): continue
        if 0<=x<width and 0<=y<12 and rows[y] & (1<<x): continue
        outside.add((x,y))
        pending.extend(((x-1,y),(x+1,y),(x,y-1),(x,y+1)))
    return [sum(1<<x for x in range(width) if (x,y) not in outside and not (row & (1<<x)))
            for y,row in enumerate(rows)]

def generate_resources(target):
    assets = ROOT / "firmware/assets"
    output = ["#pragma once", '#include "display.h"', "namespace tc {"]
    for name in ("denki","nega","maru"):
        glyphs = list(struct.iter_unpack("<IBB12H2x",(assets/(name+".bin")).read_bytes()))
        output.append("static const Glyph "+name+"Data[] = {")
        for code, step, width, *rows in glyphs:
            output.append("{%d,%d,%d,{%s},0}," % (code,step,width,",".join(map(str,rows))))
        output.append("};")
        flags=""
        if name=="nega":
            output.append("static const uint16_t negaFaces[][12] = {")
            for code,step,width,*rows in glyphs:
                output.append("{"+",".join(map(str,negaclip_face(width,rows)))+"},")
            output.append("};")
            flags=",negaFaces"
        output.append("static const Font "+name+" = {"+name+"Data,"+str(len(glyphs))+flags+"};")
    output.append("}")
    write_if_changed(target/"src/tc/fonts.h", ("\n".join(output)+"\n").encode())
    dest = target/"resources"/"tc002"
    dest.mkdir(parents=True,exist_ok=True)
    sync(assets/"licenses", dest/"licenses")
    notices = dest / "licenses/project"
    for name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
        write_if_changed(notices / name, (ROOT / name).read_bytes())
    sync(ROOT / "licenses", notices / "licenses")
    sync(assets / "licenses", notices / "firmware/assets/licenses")
    original = assets / "audio"
    for name in NOTES:
        if not (original / (name + ".mp3")).is_file():
            raise RuntimeError(f"Missing original sound firmware/assets/audio/{name}.mp3")
    preserve_legacy_files(target, original)
    for name in NOTES:
        write_if_changed(dest / (name + ".mp3"), (original / (name + ".mp3")).read_bytes())
    generate_wavs(dest)


def preserve_legacy_files(target, original):
    """Move private files from previous versions out of the IDE project before packaging."""
    candidates = [target / "stock-second.mp3"]
    old_cfg = target / "EasyUI.cfg"
    if old_cfg.is_file():
        try:
            cfg = json.loads(old_cfg.read_bytes())
        except (ValueError, UnicodeError):
            cfg = None
        if isinstance(cfg, dict) and cfg.get("startupLibPath") == "/tmp/lib/tc002-dev.so":
            candidates.append(old_cfg)
    audio = target / "resources/tc002"
    for name in NOTES:
        mp3 = audio / (name + ".mp3")
        if mp3.is_file() and mp3.read_bytes() != (original / mp3.name).read_bytes():
            candidates.append(mp3)
    existing = [path for path in candidates if path.is_file()]
    if existing:
        backup = Path(tempfile.mkdtemp(prefix=target.name + "-legacy-", dir=target.parent))
        for path in existing:
            dest = backup / path.relative_to(target)
            dest.parent.mkdir(parents=True, exist_ok=True)
            path.rename(dest)
        print(f"Preserved previous local files outside the image project: {backup}", flush=True)


NOTES = {"minute":[660], "hour":[660,880], "midnight":[523,659,784],
         "rest":[784,523], "resume":[523,784], "alarm":[880,660,880],
         "tick":[440], "rotate":[620], "button":[740], "enter":[740,990]}


def generate_wavs(dest):
    for name, tones in NOTES.items():
        with wave.open(str(dest/(name+".wav")), "wb") as out:
            out.setparams((1,2,16000,0,"NONE",""))
            if name in ("minute","hour","midnight"):
                out.writeframes(clock_strike(name))
                continue
            for freq in tones:
                length = 360 if name in ("tick", "rotate", "button", "enter") else 1600
                for_sample = [int(5200*min(1,i/100,(length-i)/250)*math.sin(2*math.pi*freq*i/16000)) for i in range(length)]
                out.writeframes(struct.pack("<%dh"%length,*for_sample)+bytes(640))


def regenerate_audio(ffmpeg):
    """Developer-only regeneration; synthesis uses no input audio or device data."""
    dest = ROOT / "firmware/assets/audio"
    with tempfile.TemporaryDirectory() as work:
        folder = Path(work)
        generate_wavs(folder)
        for name in NOTES:
            path = folder / (name + ".mp3")
            subprocess.run([ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error",
                            "-i", folder / (name + ".wav"), "-af", "adelay=115",
                            "-ar", "48000", "-ac", "2", "-codec:a", "libmp3lame", "-b:a", "320k",
                            "-write_xing", "0", "-id3v2_version", "0", "-map_metadata", "-1", path], check=True)
        for name in NOTES:
            write_if_changed(dest / (name + ".mp3"), (folder / (name + ".mp3")).read_bytes())

def source_archive(sample):
    """Read the pinned Git objects, independent of checkout state or prior IDE builds."""
    if sample is None:
        repo = ROOT / "build" / "upstream.git"
        repo.parent.mkdir(parents=True, exist_ok=True)
        if not (repo / "HEAD").is_file():
            subprocess.run(["git", "init", "--bare", str(repo)], check=True)
        git = ["git", "-C", str(repo)]
        if subprocess.run([*git, "cat-file", "-e", REVISION + "^{commit}"],
                          stderr=subprocess.DEVNULL).returncode != 0:
            subprocess.run([*git, "fetch", "--depth=1", "--no-tags", UPSTREAM, REVISION], check=True)
    else:
        repo = sample.parent if sample.name == DEMO else sample
        git = ["git", "-C", str(repo.resolve())]
    paths = ["LICENSE", "THIRD_PARTY_NOTICES.md"] + [
        DEMO + "/" + name for name in ("src", "ui", ".settings", ".project", ".cproject", ".deps.lock", "Manifest.xml")
    ]
    data = subprocess.check_output([*git, "archive", "--format=zip", REVISION, "--", *paths])
    return zipfile.ZipFile(io.BytesIO(data))


def check_destination(target):
    if target.is_dir() and any(target.iterdir()):
        project = target / ".project"
        if not project.is_file() or ET.parse(project).findtext("name") != "TC002Dev":
            raise ValueError("Choose an empty output folder or a generated TC002Dev project.")


@contextmanager
def build_lock(target):
    # A GUI launch and a command-line rebuild must not update the same generated project together.
    import msvcrt
    check_destination(target)
    target.mkdir(parents=True, exist_ok=True)
    with (target.parent / (target.name + ".build.lock")).open("a+b") as lock:
        if lock.tell() == 0:
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise RuntimeError("The project is already being prepared or built.") from None
        try:
            yield
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


def prepare_project(sample, target):
    with source_archive(sample) as archive:
        # Write this first so a partial preparation can be retried.
        for entry in sorted(archive.infolist(), key=lambda x: x.filename != DEMO + "/.project"):
            if entry.is_dir():
                continue
            parts = entry.filename.split("/")
            if parts[0] != DEMO:
                dest = target / "resources/tc002/licenses" / entry.filename
            else:
                dest = target.joinpath(*parts[1:])
            if dest == target / "src/logic/mainLogic.cc":
                continue
            data = archive.read(entry)
            if dest.name in (".project", ".cproject"):
                data = data.replace(DEMO.encode("ascii"), b"TC002Dev")
            write_if_changed(dest, data)
    for path in (ROOT/"firmware").glob("*.h"):
        write_if_changed(target/"src/tc"/path.name,path.read_bytes())
    write_if_changed(target/"src/logic/mainLogic.cc",(ROOT/"firmware/mainLogic.cc").read_bytes())
    generate_resources(target)


def sdk_flags(target, ide):
    # The official .deps.lock contains Chinese comments before the JSON document.
    contents = (target / ".deps.lock").read_bytes()
    packages = deque(json.loads(contents[contents.index(b"{"):])["dependencies"])
    includes = ["-Isrc", "-Isrc/dependencies/include"]
    libraries = ["src/dependencies/lib/libgatt-server.a"]
    seen = set()
    while packages:
        item = packages.popleft()
        name = item["id"]
        if name in seen:
            continue
        seen.add(name)
        packages.extend(item.get("dependencies", []))
        folder = ide / "bin/.dep/public/z21" / name / item["revision"]
        if not folder.is_dir():
            raise RuntimeError(f"Missing SDK package {name} {item['revision']}. "
                               "Import the prepared TC002Dev project in FlyThings and build with Ctrl+Alt+Z.")
        if item.get("includeHeader", True) and (folder / "include").is_dir():
            includes.append("-I" + str(folder / "include"))
        if item.get("linkLibrary", True):
            lib_dir = folder / "lib"
            if lib_dir.is_dir():
                # Some SDK .so files have no SONAME. Give the linker a library name
                # so the TC002 loader never receives a Windows installation path.
                libraries.append("-L" + str(lib_dir))
                libraries.extend("-l:" + path.name for path in sorted(lib_dir.glob("lib*"))
                                 if path.suffix in (".a", ".so"))
    return includes, libraries


def compile_project(target, ide):
    if not ide:
        raise ValueError("Choose the FlyThings installation with --ide or the FLYTHINGS_HOME environment variable.")
    ide = ide.resolve()
    toolchain = ide / "sdk/toolchains/z21/bin"
    compiler = toolchain / "arm-pc-linux-gnueabihf-gcc.exe"
    if not compiler.is_file():
        raise RuntimeError("The Z21 compiler is missing. Import TC002Dev into FlyThings and build with Ctrl+Alt+Z.")
    includes, libraries = sdk_flags(target, ide)
    env = os.environ.copy()
    env["PATH"] = str(toolchain) + os.pathsep + env.get("PATH", "")
    common = ["-O3", "-Wall", "-Wformat", "-Werror=format-security", "-fstack-protector", "-fno-caller-saves",
              "-fPIC", "-D__PLATFORM_Z21__=1", "-DUSE_ANDROID_LOG=1", "-D_FORTIFY_SOURCE=1", "-D_RELEASE=1",
              "-mfloat-abi=hard", "-mfpu=vfp", *includes]
    sources = sorted(path.relative_to(target) for path in (target / "src").rglob("*")
                     if path.suffix in (".c", ".cpp"))
    release = target / "Release"
    release.mkdir(exist_ok=True)
    # Keep the previous working library intact if compilation is cancelled or fails.
    with tempfile.TemporaryDirectory(prefix=".compile-", dir=release) as work:
        temp = Path(work).relative_to(target)
        def compile_one(source):
            obj = temp / source.with_suffix(".o")
            (target / obj).parent.mkdir(parents=True, exist_ok=True)
            language = ["-std=c++11", "-fexceptions"] if source.suffix == ".cpp" else []
            subprocess.run([compiler, *common, *language, "-c", source, "-o", obj], cwd=target, env=env, check=True)
            return obj
        with ThreadPoolExecutor(max_workers=4) as pool:
            objects = list(pool.map(compile_one, sources))
        output = temp / "libzkgui.so"
        subprocess.run([compiler, "-s", "-shared", "-Wl,-z,now,-z,relro,-z,defs,-Bsymbolic", "-o", output,
                        *objects, "-Wl,--start-group", *libraries, "-lpthread", "-lm", "-ldl", "-lstdc++",
                        "-Wl,--end-group"], cwd=target, env=env, check=True)
        os.replace(target / output, release / "libzkgui.so")
    print(release / "libzkgui.so")

if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sample", type=Path, help="Existing official Git checkout or its Z21_TC002_Demo folder")
    ap.add_argument("--ide", type=Path, default=os.environ.get("FLYTHINGS_HOME"), help="FlyThings installation root")
    ap.add_argument("--output", type=Path, default=TARGET, help="Generated FlyThings project directory")
    ap.add_argument("--prepare-only", action="store_true", help="Prepare a project for IDE import without compiling")
    ap.add_argument("--regenerate-audio", type=Path, metavar="FFMPEG", help="Regenerate the ten original checked-in MP3s using FFmpeg 7.1")
    args=ap.parse_args()
    try:
        if args.regenerate_audio:
            regenerate_audio(args.regenerate_audio)
            sys.exit(0)
        target = args.output.resolve()
        with build_lock(target):
            prepare_project(args.sample, target)
            print(f"Prepared FlyThings project: {target}", flush=True)
            if not args.prepare_only:
                compile_project(target, args.ide)
    except (ValueError, OSError, RuntimeError, subprocess.CalledProcessError, ET.ParseError) as error:
        sys.exit(str(error))
