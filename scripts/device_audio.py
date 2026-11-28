"""Select the standard cues and optionally voice the minute click from the owner's clock."""
import math
from pathlib import Path
import shutil
import struct
import subprocess

RATE=24000
ROOT = Path(__file__).resolve().parents[1]
ORIGINALS = ROOT / "firmware/assets/audio"
CUES = ("tick", "rotate", "button", "enter", "minute",
        *("hour%02d" % hour for hour in (*range(1, 12), *range(18, 24))), "noon", "midnight",
        "notification", "rest", "resume", "alarm")
STOCK_FILES = ("Btn.mp3", "Clock.mp3", "Enter.mp3", "Rotate.mp3", "Rotate.wav",
               "SlowClock.mp3", "StopWatch.mp3", "Tip.mp3")
OPTIONAL_STOCK_FILES = ("Alarm.mp3",)  # Present on stock 2.0.4.

def render_minute(tick):
    peak=max(map(abs,tick))
    if peak<100: raise ValueError("factory tick is silent")
    audible=[i for i,x in enumerate(tick) if abs(x)>peak*.012]
    tick=tick[max(0,audible[0]-24):min(len(tick),audible[-1]+180)]
    # The same escapement engages, followed by a lower pawl seating against the case.
    ratio=.94
    delay=round(RATE*.082)
    length=round(len(tick)/ratio)+delay+round(RATE*.12)
    body=[0.]*length
    for i in range(length):
        lead=tick[i]/peak if i<len(tick) else 0.
        pos=(i-delay)*ratio
        impact=0.
        if 0<=pos<len(tick)-1:
            j=int(pos)
            impact=(tick[j]+(pos-j)*(tick[j+1]-tick[j]))/peak
        t=(i-delay)/RATE
        resonance=0 if t<0 else math.exp(-t/.024)*min(1,t/.002)*(
            .37*math.sin(2*math.pi*410*t)+.19*math.sin(2*math.pi*728*t))
        body[i]=lead+.80*(impact+resonance)
    gain=19000/max(map(abs,body))
    # The stock click has a quiet lead-in while the hardware audio output opens.
    return bytes(round(.115*RATE)*2)+struct.pack("<%dh"%length,*(round(gain*x) for x in body))

def find_encoder():
    return shutil.which("ffmpeg") or next((ROOT / "build/audio-tools").rglob("ffmpeg*.exe"), None)


def trial_cues(work, encoder=None, stock_tick=None):
    cues = {name: ORIGINALS / (name + ".mp3") for name in CUES}
    if not all(path.is_file() for path in cues.values()):
        raise FileNotFoundError("Missing original MP3s in firmware/assets/audio.")
    if not stock_tick or not encoder:
        return list(cues.values())
    base = [str(encoder), "-hide_banner", "-loglevel", "error", "-y"]
    pcm = subprocess.check_output([*base, "-i", str(stock_tick), "-t", "2", "-ac", "1",
                                   "-ar", str(RATE), "-f", "s16le", "-"], timeout=25)
    samples = struct.unpack("<%dh" % (len(pcm) // 2), pcm)
    # Match the stock 48 kHz stereo MP3 framing accepted by the device player.
    output = work / "minute.mp3"
    subprocess.run([*base, "-f", "s16le", "-ar", str(RATE), "-ac", "1", "-i", "-",
                    "-ar", "48000", "-ac", "2", "-codec:a", "libmp3lame", "-b:a", "320k",
                    "-write_xing", "0", "-id3v2_version", "0", "-map_metadata", "-1", str(output)],
                   input=render_minute(samples), check=True, timeout=25)
    cues["minute"] = output
    return list(cues.values())
