"""Native Windows controls for the TC002 bridge and setup workflow."""
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from bridge import config
from . import APP_NAME
from .jobs import TaskStatus, active_task
from .runner import bridge_action
from .settings import Fields, save
from .setup_tab import add_setup_tab
from .setup import device_target


class SettingsTab(ttk.Frame):
    def __init__(self, notebook, config_path):
        super().__init__(notebook, padding=(18, 14))
        self.path = Path(config_path)
        self.baseline = None
        self.variables = {key: tk.StringVar(self) for key in Fields.__dataclass_fields__}
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

        clock = ttk.LabelFrame(self, text="時計と天気", padding=12)
        clock.grid(row=0, column=0, padx=(0, 7), sticky="nsew")
        clock.columnconfigure(0, weight=1)
        self.device = self.entry(clock, 0, "時計の IPv4 アドレス", "device")
        self.entry(clock, 2, "地点の表示名（天気は下の座標で取得）", "name")
        coords = ttk.Frame(clock)
        coords.grid(row=4, column=0, sticky="ew")
        for column, (label, key) in enumerate((("緯度", "lat"), ("経度", "lon"))):
            coords.columnconfigure(column, weight=1)
            part = ttk.Frame(coords)
            part.grid(row=0, column=column, padx=(0, 5) if column == 0 else (5, 0), sticky="ew")
            part.columnconfigure(0, weight=1)
            self.entry(part, 0, label, key, width=12)

        source = ttk.LabelFrame(self, text="PC との連携", padding=12)
        source.grid(row=0, column=1, padx=(7, 0), sticky="nsew")
        source.columnconfigure(0, weight=1)
        self.entry(source, 0, "GitHub 所有者（指定すると所有リポジトリ全体）", "owner")
        self.entry(source, 2, "個別のリポジトリ（owner/name をコンマ区切り）", "repos")
        ttk.Label(source, text="ADB（空欄で SDK または PATH から検出）").grid(row=4, sticky="w")
        adb = ttk.Frame(source)
        adb.grid(row=5, sticky="ew", pady=(3, 0))
        adb.columnconfigure(0, weight=1)
        ttk.Entry(adb, textvariable=self.variables["adb"]).grid(row=0, column=0, sticky="ew")
        ttk.Button(adb, text="参照…", command=self.browse, width=7).grid(row=0, column=1, padx=(5, 0))

        actions = ttk.Frame(self)
        actions.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(12, 16))
        self.save_button = ttk.Button(actions, text="設定を保存", command=self.persist)
        self.save_button.pack(side="left")
        ttk.Button(actions, text="再読み込み", command=self.reload).pack(side="left", padx=6)
        self.notice = tk.StringVar(self)
        ttk.Label(actions, textvariable=self.notice).pack(side="left", padx=4)
        ttk.Separator(self).grid(row=2, column=0, columnspan=2, sticky="ew")

        controls = ttk.Frame(self)
        controls.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        controls.columnconfigure(0, weight=1)
        ttk.Label(controls, text="PC ブリッジ", style="Heading.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(controls, text="PC が取得した天気・開発サービスの表示データを時計に送ります。",
                  wraplength=580, justify="left").grid(row=1, column=0, sticky="w", pady=(4, 8))
        buttons = ttk.Frame(controls)
        buttons.grid(row=2, column=0, sticky="w")
        self.bridge_buttons = []
        for label, action in (("保存して起動", "start"), ("停止", "stop"), ("状態を確認", "status")):
            button = ttk.Button(buttons, text=label, command=lambda op=action: self.operate(op))
            button.pack(side="left", padx=(0, 6))
            self.bridge_buttons.append(button)
        self.status = TaskStatus(self)
        self.status.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        for var in self.variables.values():
            var.trace_add("write", self.changed)
        self.load()

    def entry(self, parent, row, text, key, width=24):
        ttk.Label(parent, text=text).grid(row=row, column=0, sticky="w")
        entry = ttk.Entry(parent, textvariable=self.variables[key], width=width)
        entry.grid(row=row+1, column=0, sticky="ew", pady=(3, 10))
        return entry

    def values(self):
        return Fields(**{key: variable.get() for key, variable in self.variables.items()})

    @property
    def dirty(self):
        return self.baseline is not None and self.values() != self.baseline

    def changed(self, *_):
        self.notice.set("未保存の変更があります" if self.dirty else "")

    def populate(self, fields):
        self.baseline = fields
        for key, variable in self.variables.items():
            variable.set(getattr(fields, key))

    def load(self):
        try:
            self.populate(Fields.from_document(config.read(self.path)))
        except (OSError, ValueError) as error:
            self.baseline = None
            self.status.message(f"設定を読み込めません。ファイルを確認し、再読み込みしてください。\n{error}")
            return
        self.status.message("設定を読み込みました。" if self.path.exists() else "初回設定です。時計に表示された IP アドレスを入力してください。")

    def reload(self):
        if not self.dirty or messagebox.askyesno("再読み込み", "未保存の変更を破棄して設定を読み込みますか？", parent=self):
            self.load()

    def persist(self):
        if self.baseline is None:
            self.status.message("設定を再読み込みしてから保存してください。")
            return False
        try:
            self.populate(save(self.path, self.baseline, self.values()))
        except (OSError, ValueError) as error:
            self.status.message(f"設定を保存できません。{error}")
            return False
        self.status.message("設定を保存しました。")
        return True

    def browse(self):
        path = filedialog.askopenfilename(parent=self, title="Android Debug Bridge を選択",
                                          filetypes=[("Android Debug Bridge", "adb.exe")])
        if path:
            self.variables["adb"].set(path)

    def operate(self, action):
        if self.status.busy:
            self.status.message("処理が完了するまでお待ちください。")
            return
        if action == "start":
            if not self.variables["device"].get().strip():
                self.status.message("時計の IPv4 アドレスを入力してから起動してください。")
                self.device.focus_set()
                return
            if not self.persist():
                return
            try:
                device_target(self.path, "")
            except (OSError, ValueError) as error:
                self.status.message(str(error))
                return
        titles = {"start": "ブリッジを起動しています…", "stop": "停止を待っています…", "status": "状態を確認しています…"}
        self.status.run(titles[action], lambda: bridge_action(action), self.bridge_buttons)


def create_window(root, config_path=config.CONFIG):
    root.title(APP_NAME)
    body = ttk.Frame(root, padding=(16, 10))
    body.pack(fill="both", expand=True)
    ttk.Style(root).configure("Heading.TLabel", font=("Yu Gothic UI", 12, "bold"))
    ttk.Label(body, text=APP_NAME, font=("Yu Gothic UI", 19, "bold")).pack(anchor="w", pady=(0, 8))
    notebook = ttk.Notebook(body)
    notebook.pack(fill="both", expand=True)
    settings = SettingsTab(notebook, config_path)
    notebook.add(settings, text="接続と表示")
    add_setup_tab(notebook, Path(config_path))
    notebook.enable_traversal()

    def close():
        if active_task(root):
            messagebox.showinfo("処理中", "処理が完了してから閉じてください。", parent=root)
        elif not settings.dirty or messagebox.askyesno(APP_NAME, "変更を保存せずに閉じますか？", parent=root):
            root.destroy()

    def shortcut(event):
        if notebook.select() == str(settings):
            settings.persist()
            return "break"

    root.bind("<Control-s>", shortcut)
    root.protocol("WM_DELETE_WINDOW", close)
    return notebook


def main():
    root = tk.Tk()
    create_window(root)
    root.mainloop()
