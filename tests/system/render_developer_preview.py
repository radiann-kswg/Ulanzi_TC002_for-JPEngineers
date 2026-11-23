"""Enlarge the actual LED frames exported by run-native.ps1 -DeveloperPreview."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parents[2]
directory = root / "build/native-tests"
data = (directory / "developer-preview.rgb").read_bytes()
tile_bytes = 52 * 16 * 3
assert len(data) == tile_bytes * 48
font = ImageFont.truetype("C:/Windows/Fonts/YuGothM.ttc", 17)
headline = ImageFont.truetype("C:/Windows/Fonts/YuGothB.ttc", 23)
rows = [
    ["PR一覧","PR残件","Actions","Issue一覧","Issue残件","コードレビュー","残り使用量","電池"],
    ["予定通知","次の予定","作業中","入力待ち","セッション件数","直近の完了","追加利用額","IPアドレス"],
    ["予定通知","次の予定","作業中","入力待ち","セッション件数","直近の完了","利用枠","電池"],
]
for dataset, name in enumerate(("developer-preview", "developer-stress")):
    sheet = Image.new("RGB", (844, 1030), "#11191D")
    draw = ImageDraw.Draw(sheet)
    for c, (service, color) in enumerate(zip(("GitHub","Claude","Codex"),("#c6a9fa","#f0a581","#77dcca"))):
        x = 15 + c * 277
        draw.text((x, 8), service, font=headline, fill=color)
        for p in range(8):
            y = 54 + p * 121
            draw.text((x,y), rows[c][p], font=font, fill="#e1ebe7")
            start = (dataset*24+p*3+c)*tile_bytes
            image = Image.frombytes("RGB",(52,16),data[start:start+tile_bytes])
            sheet.paste(image.resize((260,80),Image.Resampling.NEAREST),(x,y+29))
    sheet.save(directory / (name+".png"),optimize=True)
