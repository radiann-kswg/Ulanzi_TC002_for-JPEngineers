"""Windows controls for building and running the TC002 device application."""
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import setup
from .card_panel import add_card_panel
from .jobs import TaskStatus


def add_setup_tab(notebook, config_path):
    page = ttk.Frame(notebook, padding=12)
    notebook.add(page, text="OS セットアップ")
    page.columnconfigure(0, weight=1)
    status = TaskStatus(page)
    buttons = []

    def run(label, worker):
        status.run(label, worker, buttons=tuple(buttons))

    def button(parent, text, cmd):
        control = ttk.Button(parent, text=text, command=cmd)
        control.pack(side="left", padx=(0, 6), pady=2)
        buttons.append(control)

    paths = ttk.LabelFrame(page, text="FlyThings 開発環境", padding=10)
    paths.grid(row=0, column=0, sticky="ew")
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
        ttk.Label(paths, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(paths, textvariable=var).grid(row=row, column=1, sticky="ew", pady=2)
        ttk.Button(paths, text="参照…", command=lambda v=var: browse(v)).grid(row=row, column=2, padx=(6, 0))
    ttk.Label(paths, text="公式ソースが空欄なら、固定版を初回に取得します。").grid(
        row=2, column=0, columnspan=3, sticky="w")

    def build(prepare):
        selected = ide.get().strip(), sample.get().strip()
        run("プロジェクトを生成中…" if prepare else "ARM ビルド中…",
            lambda: setup.build_project(*selected, prepare_only=prepare))

    def launch():
        selected = ide.get().strip()
        run("FlyThings を起動中…", lambda: setup.open_ide(selected))

    def install_tools():
        selected = ide.get().strip(), sample.get().strip()
        run("依存パッケージを準備中…", lambda: setup.setup_tools(*selected))

    project = ttk.Frame(paths)
    project.grid(row=3, column=0, columnspan=3, sticky="w", pady=(6, 0))
    button(project, "PC 用ツールを準備", install_tools)
    button(project, "プロジェクトを生成", lambda: build(True))
    button(project, "ARM ビルド", lambda: build(False))
    button(project, "IDE を開く", launch)

    trial = ttk.LabelFrame(page, text="一時実行", padding=10)
    trial.grid(row=1, column=0, sticky="ew", pady=(8, 0))
    ttk.Label(trial, text="設定タブで保存した時計に接続します。再起動すると常設のアプリに戻ります。").pack(anchor="w")
    actions = ttk.Frame(trial)
    actions.pack(anchor="w", pady=(4, 0))

    def trial_action(restore):
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
            run(action + "中…", lambda: setup.debug_device(address, adb, restore))

    button(actions, "時計で一時実行", lambda: trial_action(False))
    button(actions, "一時実行を終了", lambda: trial_action(True))
    add_card_panel(page, status, buttons)
    status.grid(row=3, column=0, sticky="ew", pady=(10, 0))
