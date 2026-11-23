import importlib.util
import struct
import unittest
from pathlib import Path

spec=importlib.util.spec_from_file_location("build_device",Path(__file__).resolve().parents[1]/"scripts/build-device.py")
builder=importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

class StrikeTest(unittest.TestCase):
    def test_factory_attack_increases_at_each_boundary(self):
        spec=importlib.util.spec_from_file_location("device_audio",Path(builder.__file__).with_name("device_audio.py"))
        audio=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(audio)
        samples=[0]*120+[9500,-4200,2200,-1100]*18+[0]*120
        peaks=[]
        for level in range(3):
            pcm=audio.render(samples,level)
            values=[x[0] for x in struct.iter_unpack("<h",pcm)]
            self.assertLess(len(values),audio.RATE)
            self.assertFalse(any(values[:audio.RATE//10]))
            peaks.append(max(map(abs,values)))
        self.assertEqual(peaks,[19000,23500,28400])

    def test_strikes_fit_between_second_ticks(self):
        last=0
        for name in ("minute","hour","midnight"):
            samples=[x[0] for x in struct.iter_unpack("<h",builder.clock_strike(name))]
            self.assertGreater(len(samples),last)
            self.assertLess(len(samples),16000)
            self.assertLess(max(map(abs,samples)),32767)
            self.assertGreater(max(map(abs,samples)),3000)
            self.assertEqual(samples[-1],0)
            last=len(samples)
