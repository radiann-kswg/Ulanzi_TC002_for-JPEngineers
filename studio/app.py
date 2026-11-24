"""Native workspace for configuring a TC002 and preparing its device software."""
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from bridge import config
from . import APP_NAME, theme
from .jobs import TaskStatus
from .settings_page import SettingsPage
from .setup_tab import create_setup_page
from .viewport import Viewport, bind_scrolling


ASSETS = Path(__file__).with_name("assets")
PAGES = {"settings": "接続と表示", "setup": "OS セットアップ"}


class StudioWindow:
    def __init__(self, root, config_path):
        self.root = root
        self.config_path = Path(config_path)
        self.current = None
        self.setup = None
        theme.apply(root)
        root.title(APP_NAME)
        density = root.winfo_fpixels("1i") / 96
        available = root.winfo_screenwidth() - 16, root.winfo_screenheight() - 85
        dimensions = tuple(min(round(n * density), limit) for n, limit in zip((1100, 760), available))
        root.geometry("%dx%d" % dimensions)
        root.minsize(*(min(round(n * density), limit) for n, limit in zip((860, 530), available)))
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)

        self.icon = tk.PhotoImage(master=root, file=ASSETS / "icon.png")
        self.brand_icon = self.icon.subsample(2)
        root.iconphoto(True, self.icon)
        header = ttk.Frame(root, style="Header.TFrame", padding=(20, 9))
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Label(header, image=self.brand_icon, style="Brand.TLabel").pack(side="left", padx=(0, 10))
        ttk.Label(header, text="Ulanzi TC002", style="Brand.TLabel").pack(side="left")
        tk.Frame(header, bg=theme.EDGE, width=1, height=18).pack(side="left", padx=14)
        ttk.Label(header, text="JPエンジニア向けOS設定", style="BrandDetail.TLabel").pack(side="left")

        rail = ttk.Frame(root, style="Rail.TFrame", padding=(14, 18))
        rail.grid(row=1, column=1, rowspan=2, sticky="nsew")
        self.nav = {}
        ttk.Label(rail, text="設定メニュー", style="Rail.TLabel").pack(anchor="w", padx=4, pady=(0, 8))
        self.glyphs = {}
        for key, title in PAGES.items():
            glyph = self.nav_icon(key)
            self.glyphs[key] = glyph
            button = ttk.Button(rail, text=title, image=glyph, compound="left", style="Nav.TButton",
                                command=lambda page=key: self.show_page(page))
            button.pack(fill="x", pady=(0, 4))
            self.nav[key] = button
        tk.Frame(rail, bg=theme.EDGE, height=1).pack(fill="x", pady=16)
        ttk.Label(rail, text="対象の時計", style="Rail.TLabel").pack(anchor="w", padx=4, pady=(0, 8))
        self.target = tk.StringVar(root)
        self.device_card(rail)

        workspace = ttk.Frame(root, padding=(18, 10, 16, 12))
        workspace.grid(row=1, column=0, sticky="nsew")
        workspace.columnconfigure(0, weight=1)
        workspace.rowconfigure(1, weight=1)
        self.heading = ttk.Label(workspace, style="Page.TLabel")
        self.heading.grid(row=0, column=0, sticky="w", pady=(0, 9))
        self.status = TaskStatus(root)
        self.status.grid(row=2, column=0, sticky="ew")
        self.pages = {key: Viewport(workspace) for key in PAGES}
        self.settings = SettingsPage(self.pages["settings"].content, self.config_path, self.status)
        self.settings.pack(fill="x")
        self.settings.saved_device.trace_add("write", self.update_target)
        self.update_target()
        self.show_page("settings")
        bind_scrolling(root)
        root.bind("<Control-s>", self.shortcut_save)
        for sequence in ("<Control-Tab>", "<Control-Shift-Tab>", "<Control-Next>", "<Control-Prior>"):
            root.bind(sequence, self.shortcut_switch)
        root.protocol("WM_DELETE_WINDOW", self.close)

    def nav_icon(self, key):
        # The extra transparent columns keep the icon clear of its button label.
        image = tk.PhotoImage(master=self.root, width=26, height=18)
        if key == "settings":
            marks = ((1, 4, 17, 6), (4, 2, 7, 8), (1, 12, 17, 14), (11, 10, 14, 16))
        else:
            marks = ((8, 1, 10, 10), (5, 6, 7, 8), (7, 8, 11, 10), (11, 6, 13, 8),
                     (1, 11, 3, 16), (15, 11, 17, 16), (2, 14, 16, 16))
        for rect in marks:
            image.put(theme.MUTED, to=rect)
        return image

    def device_card(self, rail):
        card = ttk.Frame(rail, style="Card.TFrame", padding=12)
        card.pack(fill="x")
        ttk.Label(card, text="TC002", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(card, text="保存済みの接続先", style="CardMuted.TLabel").pack(anchor="w", pady=(6, 0))
        ttk.Label(card, textvariable=self.target, style="Card.TLabel", width=17,
                  font=(theme.FONT, 12, "bold")).pack(anchor="w", pady=(2, 0))
        tk.Frame(card, bg=theme.EDGE, height=1).pack(fill="x", pady=(12, 0))
        self.clock_image = tk.PhotoImage(master=self.root, file=ASSETS / "tc002.png").subsample(2)
        ttk.Label(card, image=self.clock_image, style="Card.TLabel").pack(pady=(10, 3))
        ttk.Label(card, text="時計画面の表示例（52 × 16）", style="CardMuted.TLabel").pack(anchor="center")

    def update_target(self, *_):
        self.target.set(self.settings.saved_device.get() or
                        ("読み込みエラー" if self.settings.baseline is None else "未設定"))

    def show_page(self, key):
        if self.current == key:
            return
        if self.current is not None:
            previous = self.pages[self.current]
            self.nav[self.current].configure(style="Nav.TButton")
            focus = self.root.focus_get()
            if focus and str(focus).startswith(str(previous) + "."):
                self.nav[key].focus_set()
            previous.grid_remove()
        if key == "setup" and self.setup is None:
            self.setup = create_setup_page(self.pages[key].content, self.config_path, self.status)
            self.setup.pack(fill="x")
        self.current = key
        self.heading.configure(text=PAGES[key])
        self.nav[key].configure(style="Selected.Nav.TButton")
        self.pages[key].grid(row=1, column=0, sticky="nsew")

    def shortcut_save(self, _event):
        if self.current == "settings" and not self.status.busy:
            self.settings.persist()
        return "break"

    def shortcut_switch(self, _event):
        self.show_page("setup" if self.current == "settings" else "settings")
        return "break"

    def close(self):
        if self.status.busy:
            messagebox.showinfo("処理中", "処理が完了してから閉じてください。", parent=self.root)
        elif not self.settings.dirty or messagebox.askyesno(APP_NAME, "変更を保存せずに閉じますか？", parent=self.root):
            self.root.destroy()


def create_window(root, config_path=config.CONFIG):
    return StudioWindow(root, config_path)


def main():
    root = tk.Tk()
    create_window(root)
    root.mainloop()
