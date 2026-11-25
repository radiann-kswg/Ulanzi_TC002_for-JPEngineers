from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import tf_card


def path_field(group, row, label, variable, browse):
    ttk.Label(group, text=label, style="Card.TLabel", width=-17).grid(row=row, column=0, sticky="w", padx=(0, 14))
    ttk.Entry(group, textvariable=variable, width=12).grid(row=row, column=1, sticky="ew", pady=2)
    ttk.Button(group, text="参照…", command=browse).grid(row=row, column=2, padx=(8, 0))


def add_card_panel(group, status):
    group.columnconfigure(1, weight=1)
    image, drive = tk.StringVar(group), tk.StringVar(group)

    def choose_image():
        filename = filedialog.askopenfilename(parent=group, title="TC002Dev の Image Build 出力",
                                              filetypes=[("TC002 イメージ", "update.img")])
        if filename:
            image.set(filename)

    def choose_drive():
        folder = filedialog.askdirectory(parent=group, title="FAT32 の TF カードのルート", mustexist=True)
        if folder:
            drive.set(folder)

    path_field(group, 0, "イメージ", image, choose_image)
    path_field(group, 1, "TF カード", drive, choose_drive)

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
        if not messagebox.askokcancel("TF カードを準備", prompt, parent=group):
            return

        def copy():
            checksum = tf_card.prepare_card(source, card)
            return f"{card.root}update.img を照合しました。Windows でカードを安全に取り外せます。\nSHA-256  {checksum}"

        status.run("カードへコピーし、読み戻して照合中…", copy)

    start = ttk.Button(group, text="カードにコピーして照合", command=prepare)
    start.grid(row=2, column=0, columnspan=3, sticky="w", pady=(9, 0))
    status.register(start)
