"""Shared colors and native control states for the Windows workspace."""
from tkinter import ttk


BASE = "#1d1e22"
PANEL = "#2c2d32"
RAIL = "#26272b"
FIELD = "#1a1b1f"
EDGE = "#4d5058"
TEXT = "#f1f3f5"
MUTED = "#bcc1c9"
ACCENT = "#55dfce"
INK = "#11332f"
FONT = "Yu Gothic UI"


def apply(root):
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", background=BASE, foreground=TEXT, font=(FONT, 10),
                    troughcolor=FIELD, bordercolor=EDGE, focuscolor=ACCENT)
    style.configure("Card.TFrame", background=PANEL)
    for name, background, color, size, weight in (
        ("Card.TLabel", PANEL, TEXT, 10, "normal"),
        ("CardTitle.TLabel", PANEL, TEXT, 12, "bold"),
        ("CardMuted.TLabel", PANEL, MUTED, 10, "normal"),
        ("Page.TLabel", BASE, TEXT, 17, "bold"),
        ("Status.TLabel", FIELD, MUTED, 10, "normal"),
        ("Rail.TLabel", RAIL, MUTED, 10, "normal"),
        ("Brand.TLabel", FIELD, TEXT, 15, "bold"),
        ("BrandDetail.TLabel", FIELD, MUTED, 11, "normal"),
    ):
        style.configure(name, background=background, foreground=color, font=(FONT, size, weight))
    style.configure("Header.TFrame", background=FIELD)
    style.configure("Rail.TFrame", background=RAIL)
    style.configure("Status.TFrame", background=FIELD)
    style.configure("TEntry", padding=(8, 4), fieldbackground=FIELD, foreground=TEXT,
                    insertcolor=TEXT, selectbackground=ACCENT, selectforeground=INK,
                    bordercolor=EDGE, lightcolor=FIELD, darkcolor=FIELD)
    style.map("TEntry", bordercolor=[("focus", ACCENT)],
              lightcolor=[("focus", FIELD)], darkcolor=[("focus", FIELD)])
    for name, background, foreground, border, hover, pressed in (
        ("TButton", "#3a3c43", TEXT, "#50535b", "#474b52", "#323439"),
        ("Accent.TButton", ACCENT, INK, ACCENT, "#83eadf", "#39bcac"),
        ("Nav.TButton", RAIL, TEXT, RAIL, "#37393f", "#31353a"),
        ("Selected.Nav.TButton", "#193d3b", ACCENT, "#3b948b", "#214944", "#193d3b"),
    ):
        nav = name.endswith("Nav.TButton")
        style.configure(name, background=background, foreground=foreground, bordercolor=border,
                        lightcolor=background, darkcolor=background,
                        relief="solid" if name == "Selected.Nav.TButton" else "flat", borderwidth=1,
                        focuscolor=foreground, padding=(12, 8) if nav else (9, 4),
                        anchor="w" if nav else "center", width=-1,
                        font=(FONT, 10, "bold" if nav or name == "Accent.TButton" else "normal"))
        colors = [("disabled", "#34353a"), ("pressed", pressed), ("active", hover)]
        style.map(name, background=colors, lightcolor=colors, darkcolor=colors,
                  bordercolor=[("disabled", EDGE), ("focus", ACCENT), ("active", border)],
                  foreground=[("disabled", "#a4a7b0"), ("!disabled", foreground)])
    style.configure("TScrollbar", arrowsize=12, gripcount=0, background="#51545d",
                    troughcolor=BASE, bordercolor=BASE, lightcolor=BASE, darkcolor=BASE, arrowcolor=MUTED)
    style.map("TScrollbar", background=[("active", "#737881")])
    style.configure("TProgressbar", background=ACCENT, lightcolor=ACCENT, darkcolor=ACCENT,
                    troughcolor=PANEL, bordercolor=PANEL, thickness=5)
    root.configure(background=BASE)
