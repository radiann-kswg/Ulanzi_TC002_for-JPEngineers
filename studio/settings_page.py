"""Connection, data source and bridge controls for the Windows settings screen."""
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from bridge import config
from .runner import bridge_action
from .settings import Fields, save
from .setup import device_target


class SettingsPage(ttk.Frame):
    def __init__(self, parent, config_path, status):
        super().__init__(parent)
        self.path = Path(config_path)
        self.status = status
        self.baseline = None
        self.variables = {key: tk.StringVar(self) for key in Fields.__dataclass_fields__}
        self.notice = tk.StringVar(self)
        self.saved_device = tk.StringVar(self)
        self.columnconfigure((0, 1), weight=1, uniform="panels")

        pair = ttk.Frame(self)
        pair.grid(row=0, column=0, columnspan=2, sticky="ew")
        pair.columnconfigure((0, 1), weight=1, uniform="pair")
        clock = self.card("時計との接続", pair)
        clock.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        clock.columnconfigure(0, weight=1)
        self.device = self.field(clock, 1, 0, "時計の IPv4 アドレス", "device", span=2)
        self.field(clock, 3, 0, "ADB（空欄で自動検出）", "adb", span=2).grid_configure(columnspan=1)
        ttk.Button(clock, text="参照…", command=self.browse).grid(
            row=4, column=1, sticky="ew", padx=(6, 0))

        weather = self.card("天気の取得地点", pair)
        weather.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        weather.columnconfigure((0, 1), weight=1, uniform="coordinates")
        self.field(weather, 1, 0, "地点の表示名", "name", span=2)
        self.field(weather, 3, 0, "緯度", "lat", padx=(0, 5))
        self.field(weather, 3, 1, "経度", "lon", padx=(5, 0))

        def fit_cards(event):
            stacked = event.width < 2 * max(clock.winfo_reqwidth(), weather.winfo_reqwidth()) + 12
            clock.grid(columnspan=2 if stacked else 1, padx=0 if stacked else (0, 6))
            weather.grid(row=int(stacked), column=0 if stacked else 1, columnspan=2 if stacked else 1,
                         padx=0 if stacked else (6, 0), pady=(10 if stacked else 0, 0))

        pair.bind("<Configure>", fit_cards)

        github = self.card("GitHub の監視対象")
        github.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        github.columnconfigure((0, 1), weight=1, uniform="github")
        self.field(github, 1, 0, "所有者", "owner", padx=(0, 8))
        self.field(github, 1, 1, "個別のリポジトリ", "repos", padx=(8, 0))
        self.hint(github, 3, "所有者を指定すると、その所有者の全リポジトリを監視します。個別に指定するときは所有者を空欄にし、owner/name をコンマで区切ります。")

        actions = ttk.Frame(self)
        actions.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 16))
        actions.columnconfigure(0, weight=1)
        ttk.Label(actions, textvariable=self.notice).grid(row=0, column=0, sticky="w")
        reload_button = ttk.Button(actions, text="再読み込み", command=self.reload)
        reload_button.grid(row=0, column=1, padx=(0, 8))
        self.save_button = ttk.Button(actions, text="設定を保存", command=self.persist, style="Accent.TButton")
        self.save_button.grid(row=0, column=2)

        controls = self.card("PC ブリッジ")
        controls.grid(row=3, column=0, columnspan=2, sticky="ew")
        controls.columnconfigure(0, weight=1)
        self.hint(controls, 1, "PC が取得した天気や開発情報を時計に送ります。")
        buttons = ttk.Frame(controls, style="Card.TFrame")
        buttons.grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.bridge_buttons = []
        for label, action in (("保存して起動", "start"), ("停止", "stop"), ("状態を確認", "status")):
            button = ttk.Button(buttons, text=label, command=lambda op=action: self.operate(op))
            button.pack(side="left", padx=(0, 8))
            self.bridge_buttons.append(button)
        self.status.register(self.save_button, reload_button, *self.bridge_buttons)

        for variable in self.variables.values():
            variable.trace_add("write", self.changed)
        self.load()

    def card(self, title, parent=None):
        frame = ttk.Frame(parent or self, style="Card.TFrame", padding=(16, 12))
        ttk.Label(frame, text=title, style="CardTitle.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        return frame

    def field(self, parent, row, column, title, key, span=1, padx=0):
        ttk.Label(parent, text=title, style="Card.TLabel").grid(
            row=row, column=column, columnspan=span, sticky="w", padx=padx, pady=(8, 3))
        entry = ttk.Entry(parent, textvariable=self.variables[key], width=12)
        entry.grid(row=row + 1, column=column, columnspan=span, sticky="ew", padx=padx)
        return entry

    def hint(self, parent, row, text):
        label = ttk.Label(parent, text=text, style="CardMuted.TLabel", justify="left", wraplength=400)
        label.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        label.bind("<Configure>", lambda event: label.configure(wraplength=max(80, event.width - 4)))

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
        self.saved_device.set(fields.device)

    def load(self):
        try:
            self.populate(Fields.from_document(config.read(self.path)))
        except (OSError, ValueError) as error:
            self.baseline = None
            self.saved_device.set("")
            self.notice.set("")
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
        self.status.run(titles[action], lambda: bridge_action(action))
