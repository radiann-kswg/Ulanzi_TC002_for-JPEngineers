"""Windows controls for building and running the TC002 device application."""
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import webbrowser

from . import setup
from .card_panel import add_card_panel, path_field


def create_setup_page(parent, config_path, status):
    page = ttk.Frame(parent)
    page.columnconfigure(0, weight=1)

    def section(row, title, description):
        card = ttk.Frame(page, style="Card.TFrame", padding=(18, 13))
        card.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(card, text=title, style="CardTitle.TLabel").pack(anchor="w")
        hint = ttk.Label(card, text=description, style="CardMuted.TLabel", wraplength=450, justify="left")
        hint.pack(fill="x", pady=(2, 8))
        hint.bind("<Configure>", lambda event: hint.configure(wraplength=max(80, event.width - 2)))
        body = ttk.Frame(card, style="Card.TFrame")
        body.pack(fill="x")
        return body

    def button(row, text, cmd, *, primary=False):
        control = ttk.Button(row, text=text, command=cmd, style="Accent.TButton" if primary else "TButton")
        control.pack(side="left", padx=(0, 8))
        status.register(control)

    paths = section(0, "FlyThings 開発環境",
                    "bin/ide.exe を含むフォルダーを指定します。公式ソースが空欄なら、固定版を初回に取得します。")
    paths.columnconfigure(1, weight=1)
    try:
        ide_path, sample_path = setup.load_paths()
    except (ValueError, OSError, AttributeError) as exc:
        ide_path, sample_path = "", ""
        status.message(f"保存したフォルダーを読み込めませんでした。{exc}")
    ide, sample = tk.StringVar(page, ide_path), tk.StringVar(page, sample_path)

    def browse(var):
        path = filedialog.askdirectory(parent=page, mustexist=True)
        if path:
            var.set(path)

    for row, (label, var) in enumerate((("IDE フォルダー", ide), ("公式ソース（任意）", sample))):
        path_field(paths, row, label, var, lambda value=var: browse(value))

    def build(prepare):
        selected = ide.get().strip(), sample.get().strip()
        status.run("プロジェクトを生成中…" if prepare else "ARM ビルド中…",
            lambda: setup.build_project(*selected, prepare_only=prepare))

    def launch():
        selected = ide.get().strip()
        status.run("FlyThings を起動中…", lambda: setup.open_ide(selected))

    def install_tools():
        selected = ide.get().strip(), sample.get().strip()
        status.run("依存パッケージを準備中…", lambda: setup.setup_tools(*selected))

    project = ttk.Frame(paths, style="Card.TFrame")
    project.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(9, 0))
    prepare_actions = ttk.Frame(project, style="Card.TFrame")
    prepare_actions.grid(row=0, column=0, sticky="w")
    build_actions = ttk.Frame(project, style="Card.TFrame")
    build_actions.grid(row=0, column=1, sticky="w")
    button(prepare_actions, "PC 用ツールを準備", install_tools)
    button(prepare_actions, "プロジェクトを生成", lambda: build(True))
    button(build_actions, "ARM ビルド", lambda: build(False), primary=True)
    button(build_actions, "IDE を開く", launch)

    def fit_actions(event):
        split = prepare_actions.winfo_reqwidth() + build_actions.winfo_reqwidth() > event.width
        build_actions.grid(row=int(split), column=0 if split else 1, sticky="w", pady=(6 if split else 0, 0))

    project.bind("<Configure>", fit_actions)

    trial = section(1, "一時実行", "「接続と表示」で保存した時計を使います。再起動すると常設のアプリに戻ります。")

    def trial_action(restore):
        if status.busy:
            return
        try:
            address, adb = setup.device_target(config_path, ide.get().strip())
        except (OSError, ValueError, AttributeError) as exc:
            status.message(str(exc))
            return
        action = "一時実行を終了" if restore else "独自時計を一時実行"
        prompt = f"{address} で{action}しますか？"
        if not restore:
            try:
                built = (setup.PROJECT / "Release/libzkgui.so").stat().st_mtime
            except OSError:
                status.message("先に「ARM ビルド」を実行してください。")
                return
            prompt += "\n実行するビルドの更新日時　" + datetime.fromtimestamp(built).strftime("%Y-%m-%d %H:%M:%S")
        if messagebox.askokcancel(action, prompt, parent=page):
            status.run(action + "中…", lambda: setup.debug_device(address, adb, restore))

    button(trial, "時計で一時実行", lambda: trial_action(False))
    button(trial, "一時実行を終了", lambda: trial_action(True))
    install = section(2, "Wi-Fi で常設する",
                      "プロジェクト生成後、Image Build の前に時計の標準の秒針音を取り込みます。")
    def import_tick():
        try:
            address, adb = setup.device_target(config_path, ide.get().strip())
        except (OSError, ValueError, AttributeError) as exc:
            status.message(str(exc))
            return
        status.run("標準の秒針音を取り込み中…", lambda: setup.import_clock_tick(address, adb))

    button(install, "標準の秒針音を取り込む", import_tick)
    button(install, "GitHub で更新手順を開く", lambda: webbrowser.open(
        "https://github.com/radiann-kswg/Ulanzi_TC002_for-JPEngineers/blob/main/docs/wifi-update.md"))
    card = section(3, "TF カードへのコピー（任意）",
                   "PC 上の update.img を FAT32 のカードに保存して照合します。")
    add_card_panel(card, status)
    return page
