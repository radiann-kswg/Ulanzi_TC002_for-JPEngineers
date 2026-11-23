from pathlib import Path
import tempfile
import struct
import unittest
from unittest.mock import patch

from studio import tf_card


class CardTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.card = tf_card.Card(root / "card", 1, "TC002")
        self.card.root.mkdir()
        self.source = root / "update.img"
        header = bytearray(572)
        header[:16] = b"ZKSWEV1.0-180127"
        header[32:36] = b"hsqs"
        header[52:57] = bytes.fromhex("02 06 06 55 aa")
        struct.pack_into("<II", header, 24, 572, 4)
        self.image = bytes(header) + b"test"
        self.source.write_bytes(self.image)
        self.dest = self.card.root / "update.img"
        inspection = patch.object(tf_card, "inspect_card", return_value=self.card)
        self.inspect = inspection.start()
        self.addCleanup(inspection.stop)

    def test_copy_verify_repeat_and_preserve_existing_image(self):
        expected = tf_card.digest(self.source)
        self.assertEqual(tf_card.prepare_card(self.source, self.card), expected)
        self.assertEqual(self.dest.read_bytes(), self.source.read_bytes())
        self.assertEqual(tf_card.prepare_card(self.source, self.card), expected)
        with self.assertRaises(ValueError):
            tf_card.prepare_card(self.dest, self.card)
        self.source.write_bytes(self.image[:-4] + b"edit")
        with self.assertRaises(FileExistsError):
            tf_card.prepare_card(self.source, self.card)
        self.assertEqual(self.dest.read_bytes(), self.image)

    def test_rejects_wrong_platform_truncation_and_unattended_update(self):
        for invalid in (b"random", self.image[:-1], self.image[:53] + b"\x04\x04" + self.image[55:]):
            self.source.write_bytes(invalid)
            with self.assertRaises(ValueError):
                tf_card.prepare_card(self.source, self.card)
            self.assertFalse(self.dest.exists())
        self.source.write_bytes(self.image)
        (self.card.root / "zkautoupgrade").touch()
        for previous in (False, True):
            if previous:
                self.dest.write_bytes(self.image)
            with self.assertRaisesRegex(ValueError, "zkautoupgrade"):
                tf_card.prepare_card(self.source, self.card)

    def test_card_replacement_or_bad_readback_never_publishes(self):
        self.inspect.side_effect = [self.card, tf_card.Card(self.card.root, 2, "other"), self.card]
        with self.assertRaises(ValueError):
            tf_card.prepare_card(self.source, self.card)
        self.inspect.side_effect = None
        self.assertFalse(self.dest.exists())
        with patch.object(tf_card, "digest", return_value="bad"):
            with self.assertRaises(OSError):
                tf_card.prepare_card(self.source, self.card)
        self.assertEqual(list(self.card.root.iterdir()), [])

class VolumeTest(unittest.TestCase):
    def test_rejects_subfolders_and_system_drive(self):
        with self.assertRaises(ValueError):
            tf_card.inspect_card(Path.cwd())
        if tf_card.os.name == "nt":
            with self.assertRaises(ValueError):
                tf_card.inspect_card(Path("E:"))
            with self.assertRaises(ValueError):
                tf_card.inspect_card(Path(tf_card.os.environ["SystemDrive"] + "/"))
