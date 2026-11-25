import importlib.util
import struct
import unittest
from pathlib import Path

spec=importlib.util.spec_from_file_location("build_device",Path(__file__).resolve().parents[1]/"scripts/build-device.py")
builder=importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

class StrikeTest(unittest.TestCase):
    def test_factory_minute_keeps_its_priming_and_level(self):
        spec=importlib.util.spec_from_file_location("device_audio",Path(builder.__file__).with_name("device_audio.py"))
        audio=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(audio)
        samples=[0]*120+[9500,-4200,2200,-1100]*18+[0]*120
        pcm=audio.render_minute(samples)
        values=[x[0] for x in struct.iter_unpack("<h",pcm)]
        self.assertLess(len(values),audio.RATE)
        self.assertFalse(any(values[:audio.RATE//10]))
        self.assertEqual(max(map(abs,values)),19000)
        self.assertCountEqual(audio.CUES,builder.CUES)

    def test_each_score_fits_its_playback_window_and_decays(self):
        # Include the hardware lead-in and MP3 frame padding in the timing budget.
        budgets={"hour":.85, "noon":1.8, "midnight":1.8, "notification":.5}
        peaks={}
        for name, budget in budgets.items():
            samples=[v for v, in struct.iter_unpack("<h",builder.bell_phrase(builder.BELL_SCORES[name]))]
            peaks[name]=max(map(abs,samples))
            self.assertGreater(peaks[name],3000)
            self.assertLess(peaks[name],32767)
            self.assertLess(len(samples)/16000+.17,budget)
            self.assertLess(abs(samples[-1]),8)
        self.assertLess(peaks["notification"],peaks["hour"])
