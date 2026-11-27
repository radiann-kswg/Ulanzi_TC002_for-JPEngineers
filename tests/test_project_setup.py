import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_device", ROOT / "scripts/build-device.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class ProjectSetupTests(unittest.TestCase):
    def test_archive_reads_committed_source_without_demo_build(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = Path(folder) / "official"
            demo = repo / builder.DEMO
            (demo / "src").mkdir(parents=True)
            (demo / "src/Main.cpp").write_text("committed", encoding="ascii")
            (demo / ".project").write_text("<projectDescription><name>Z21_TC002_Demo</name></projectDescription>")
            (demo / ".cproject").write_text('<builder path="/Z21_TC002_Demo/Release"/>')
            (repo / "LICENSE").write_text("license")
            (repo / "THIRD_PARTY_NOTICES.md").write_text("notices")
            for name in (".settings/example", "ui/main.ftu", "Manifest.xml", ".deps.lock"):
                path = demo / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture")
            subprocess.run(["git", "init", "-q", repo], check=True)
            git = ["git", "-C", repo]
            subprocess.run([*git, "add", "."], check=True)
            subprocess.run([*git, "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                            "-c", "commit.gpgsign=false", "commit", "-qm", "fixture"], check=True)
            revision = subprocess.check_output([*git, "rev-parse", "HEAD"], text=True).strip()
            (demo / "src/Main.cpp").write_text("uncommitted")
            target = Path(folder) / "generated"
            with patch.object(builder, "REVISION", revision):
                builder.prepare_project(demo, target)
            self.assertEqual((target / "src/Main.cpp").read_text(), "committed")
            self.assertEqual((target / "src/logic/mainLogic.cc").read_bytes(), (ROOT / "firmware/mainLogic.cc").read_bytes())
            self.assertIn("/TC002Dev/Release", (target / ".cproject").read_text())
            self.assertTrue((target / "resources/tc002/licenses/THIRD_PARTY_NOTICES.md").is_file())
            self.assertEqual((target / "resources/tc002/licenses/project/LICENSE").read_bytes(),
                             (ROOT / "LICENSE").read_bytes())
            self.assertTrue((target / "resources/tc002/tick.wav").is_file())
            mp3 = target / "resources/tc002/minute.mp3"
            canonical = (ROOT / "firmware/assets/audio/minute.mp3").read_bytes()
            self.assertEqual(mp3.read_bytes(), canonical)
            mp3.write_bytes(b"previous private chime")
            (target / "resources/tc002/hour.wav").write_bytes(b"retired bell")
            (target / "resources/tc002/hour23.wav").write_bytes(b"old afternoon melody")
            (target / "resources/tc002/hour13.mp3").write_bytes(b"old afternoon one")
            (target / "stock-second.mp3").write_bytes(b"previous private tick")
            (target / "EasyUI.cfg").write_text('{"startupLibPath":"/tmp/lib/tc002-dev.so"}')
            with patch.object(builder, "REVISION", revision):
                builder.prepare_project(demo, target)
                builder.prepare_project(demo, target)
            backup, = target.parent.glob("generated-legacy-*")
            self.assertEqual((backup / "resources/tc002/minute.mp3").read_bytes(), b"previous private chime")
            self.assertEqual((backup / "stock-second.mp3").read_bytes(), b"previous private tick")
            self.assertTrue((backup / "EasyUI.cfg").is_file())
            self.assertEqual((backup / "resources/tc002/hour.wav").read_bytes(), b"retired bell")
            self.assertFalse((target / "resources/tc002/hour.wav").exists())
            self.assertEqual((backup / "resources/tc002/hour23.wav").read_bytes(), b"old afternoon melody")
            self.assertFalse(list((target / "resources/tc002").glob("hour*.wav")))
            self.assertEqual((backup / "resources/tc002/hour13.mp3").read_bytes(), b"old afternoon one")
            self.assertFalse((target / "resources/tc002/hour13.mp3").exists())
            for name in builder.HOUR_SCORES:
                self.assertEqual((target / "resources/tc002" / (name + ".mp3")).read_bytes(),
                                 (ROOT / "firmware/assets/audio" / (name + ".mp3")).read_bytes())
            self.assertFalse((target / "stock-second.mp3").exists())
            self.assertFalse((target / "EasyUI.cfg").exists())
            self.assertEqual(mp3.read_bytes(), canonical)
            builder.check_destination(target)
            with self.assertRaises(ValueError):
                builder.check_destination(demo)

    def test_runtime_libraries_are_linked_by_name(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)
            package = target / "bin/.dep/public/z21/easyui/2.6.0/lib"
            package.mkdir(parents=True)
            (package / "libeasyui.so").touch()
            lock = {"dependencies": [{"id": "easyui", "revision": "2.6.0"}]}
            (target / ".deps.lock").write_text("// SDK revision\n" + json.dumps(lock))
            _, libraries = builder.sdk_flags(target, target)
            self.assertIn("-L" + str(package), libraries)
            self.assertIn("-l:libeasyui.so", libraries)
            self.assertNotIn(str(package / "libeasyui.so"), libraries)
