import importlib.util
import struct
import unittest
from pathlib import Path

root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("build_device",root/"scripts/build-device.py")
builder=importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

class NegaClipTest(unittest.TestCase):
    def test_negative_letters_and_transparent_space(self):
        records=struct.iter_unpack("<IBB12H2x",(root/"firmware/assets/nega.bin").read_bytes())
        for code,advance,width,*rows in records:
            if chr(code) not in "0123456789:+-SDT ": continue
            face=builder.negaclip_face(width,rows)
            self.assertEqual(any(face),chr(code)!=" ",repr(chr(code)))
            self.assertFalse(any(a & b for a,b in zip(face,rows)))
            self.assertEqual(face[-1],0)
