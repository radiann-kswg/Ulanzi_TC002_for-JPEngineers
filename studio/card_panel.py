from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import tf_card


def add_card_panel(page, status, buttons):
    group = ttk.LabelFrame(page, text="常設用 TF カード", padding=10)
    group.grid(row=2, column=0, sticky="ew", pady=(8, 0))
    group.columnconfigure(1, weight=1)
    ttk.Label(group, text="TC002Dev を IDE で開き、Image Build で PC に update.img を生成します。").grid(
        row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))
    image, drive = tk.StringVar(page), tk.StringVar(page)

    def choose_image():
        filename = filedialog.askopenfilename(parent=page, title="TC002Dev の Image Build 出力",
                                              filetypes=[("TC002 イメージ", "update.img")])
        if filename:
            image.set(filename)

    def choose_drive():
        folder = filedialog.askdirectory(parent=page, title="FAT32 の TF カードのルート", mustexist=True)
        if folder:
            drive.set(folder)

    for row, (label, var, choose) in enumerate((("イメージ", image, choose_image),
                                               ("TF カード", drive, choose_drive)), start=1):
        ttk.Label(group, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(group, textvariable=var).grid(row=row, column=1, sticky="ew", pady=2)
        ttk.Button(group, text="参照…", command=choose).grid(row=row, column=2, padx=(6, 0))

    def prepare():
        if status.busy:
            return
        source = Path(image.get().strip())
        try:
            size = tf_card.image_size(source)
            card = tf_card.inspect_card(Path(drive.get().strip()))
        except (OSError, ValueError) as exc:
            status.message(str(exc))
            return
        prompt = (f"{source}\n{size:,} バイト\n\nコピー先　{card.root}  {card.label}\n\n"
                  "TC002Dev で生成したファイルとカードを確認してください。コピーしますか？")
        if not messagebox.askokcancel("TF カードを準備", prompt, parent=page):
            return

        def copy():
            checksum = tf_card.prepare_card(source, card)
            return f"{card.root}update.img を照合しました。安全に取り外して本体へ挿入してください。\nSHA-256  {checksum}"

        status.run("カードへコピーし、読み戻して照合中…", copy, buttons)

    start = ttk.Button(group, text="カードにコピーして照合", command=prepare)
    start.grid(row=3, column=0, columnspan=3, sticky="w", pady=(6, 0))
    buttons.append(start)
