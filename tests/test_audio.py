import importlib.util
import re
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
        budgets={"noon":1.8, "midnight":1.8, "notification":.5}
        budgets.update({"hour%02d"%hour:1.8 for hour in builder.HOURS})
        peaks={}
        for name, budget in budgets.items():
            samples=[v for v, in struct.iter_unpack("<h",builder.bell_phrase(builder.BELL_SCORES[name]))]
            peaks[name]=max(map(abs,samples))
            self.assertGreater(peaks[name],3000)
            self.assertLess(peaks[name],32767)
            overhead=.19 if name in builder.HOUR_SCORES else .17
            self.assertLess(len(samples)/16000+overhead,budget)
            self.assertLess(abs(samples[-1]),8)
        self.assertLess(peaks["notification"],min(peaks["hour%02d"%hour] for hour in builder.HOURS))

    def test_hour_melodies_spell_the_hour_in_binary(self):
        self.assertEqual(builder.HOURS, (*range(1,12), *range(18,24)))
        for hour in builder.HOURS:
            notes=builder.BELL_SCORES["hour%02d"%hour]
            # Recover the accents, then check the rhythm independently of tempo.
            ones=[strength>.65 for _,_,_,strength in notes]
            self.assertEqual("".join("01"[one] for one in ones),format(hour%12,"b"))
            self.assertTrue(all(pitch==67 for (_,pitch,_,_),one in zip(notes,ones) if not one))
            self.assertEqual(notes[0][0],0)
            tempo=notes[-1][2]/(.58 if ones[-1] else .30)
            for note,later,one in zip(notes,notes[1:],ones):
                self.assertAlmostEqual(later[0]-note[0],tempo*(.32 if one else .17))
                self.assertAlmostEqual(note[2],tempo*(.38 if one else .16))
            target=1.57 if hour<12 else 1.58
            self.assertAlmostEqual(notes[-1][0]+notes[-1][2],target)
            # The six evening openings lead from the morning G to midnight's D.
            high=[pitch for (_,pitch,_,_),one in zip(notes,ones) if one]
            climb=[pitch for pitch,one in zip((67,71,74,79),ones) if one]
            evening_openings={18:67,19:67,20:71,21:71,22:74,23:74}
            expected=climb if hour<12 else [evening_openings[hour]]+[74]*(len(high)-1)
            self.assertEqual(high,expected)

        for hour, pitches in [(11,[67,67,74,79]), (23,[74,67,74,74])]:
            notes=builder.HOUR_SCORES["hour%02d"%hour]
            self.assertEqual([pitch for _,pitch,_,_ in notes],pitches)
            self.assertEqual([length>notes[1][2] for _,_,length,_ in notes],[True,False,True,True])

    def test_hourly_hold_window_brackets_every_melody(self):
        # firmware/sound.h ignores end reports before earliestEnd and frees the player at latestEnd.
        source=(builder.ROOT/"firmware/sound.h").read_text(encoding="utf-8")
        earliest,latest=(int(v)/1000 for v in re.search(r"earliestEnd=(\d+), latestEnd=(\d+)",source).groups())
        for score in builder.HOUR_SCORES.values():
            length=builder.phrase_length(score)
            self.assertLess(earliest,length)
            self.assertLess(length+.19,latest)

    def test_packaged_hourly_mp3s_fit_in_80_kib(self):
        assets = builder.ROOT / "firmware/assets/audio"
        self.assertCountEqual((p.stem for p in assets.glob("hour*.mp3")), builder.HOUR_SCORES)
        sizes = [(assets / (name + ".mp3")).stat().st_size for name in builder.HOUR_SCORES]
        self.assertTrue(all(sizes))
        self.assertLessEqual(sum(sizes), 80 * 1024)
