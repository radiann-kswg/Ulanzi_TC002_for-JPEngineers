"""Convert the three upstream OFL fonts into the clock's sorted 32-byte glyphs."""
import argparse
import struct
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

FONTS = [
    ("x8y12pxDenkiChip", 12, "denki"),
    ("x5y8pxNegaClip", 8, "nega"),
    ("x12y12pxMaruMinya", 12, "maru"),
]

def japanese_characters():
    chars = set(chr(c) for c in range(32, 127))
    for row in range(0xa1, 0xff):
        for column in range(0xa1, 0xff):
            chars.update(bytes((row, column)).decode("euc_jp", errors="ignore"))
    chars.update(chr(c) for c in range(0xff01, 0xffa0))
    return sorted(chars | set("°¥−☀↑↓"))

def pack(font, chars):
    data = bytearray()
    def mask(char):
        glyph = Image.new("1", (16, 12))
        ImageDraw.Draw(glyph).text((0, 0), char, fill=1, font=font)
        return glyph
    missing = mask("\uffff").tobytes()
    for char in chars:
        im = mask(char)
        if im.tobytes() == missing and char != " ":
            continue
        right = (im.getbbox() or (0, 0, 0, 0))[2]
        rows = [sum(im.getpixel((x, y)) << x for x in range(right)) for y in range(12)]
        data.extend(struct.pack("<IBB12H2x", ord(char), round(font.getlength(char)), right, *rows))
    return data

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="directory containing upstream TTF files")
    args = parser.parse_args()
    dest = Path(__file__).resolve().parents[1] / "firmware/assets"
    for name, size, filename in FONTS:
        font = ImageFont.truetype(str(args.source / (name + ".ttf")), size)
        data = pack(font, japanese_characters())
        (dest / (filename + ".bin")).write_bytes(data)
        print(filename, len(data)//32)
