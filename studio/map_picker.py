"""Choose a weather location with a Japanese address search and a map pin."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
import webbrowser

from bridge import geocoding
from . import theme
from .map_canvas import MapCanvas


class MapPicker(tk.Toplevel):
    def __init__(self, parent, name, lat, lon, on_apply):
        super().__init__(parent)
        self.title("天気の地点を選ぶ")
        self.transient(parent.winfo_toplevel())
        self.configure(background=theme.BASE)
        scale = self.winfo_fpixels("1i") / 96
        width = min(round(780 * scale), self.winfo_screenwidth() - 24)
        height = min(round(690 * scale), self.winfo_screenheight() - 85)
        self.geometry(f"{width}x{height}")
        self.minsize(min(width, round(560 * scale)), min(height, round(460 * scale)))
        self.on_apply = on_apply
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gsi-place")
        self.future = self.poll_id = None
        self.places = []
        self.point = None
        self.searching = False
        self.query = tk.StringVar(self, name)
        self.name = tk.StringVar(self)
        self.coordinates = tk.StringVar(self, "地点を選んでください")
        self.message = tk.StringVar(self)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", lambda _event: self.close())
        self.bind("<Destroy>", self.dispose)

        body = ttk.Frame(self, padding=(14, 10))
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(3, weight=1)
        search_row = ttk.Frame(body)
        search_row.grid(row=0, column=0, sticky="ew")
        search_row.columnconfigure(1, weight=1)
        ttk.Label(search_row, text="地名・住所").grid(row=0, column=0, padx=(0, 8))
        self.search_entry = ttk.Entry(search_row, textvariable=self.query)
        self.search_entry.grid(row=0, column=1, sticky="ew")
        self.search_entry.bind("<Return>", self.search)
        ttk.Button(search_row, text="検索", command=self.search).grid(row=0, column=2, padx=(8, 0))
        self.result_row = ttk.Frame(body)
        self.result_row.columnconfigure(1, weight=1)
        ttk.Label(self.result_row, text="検索候補").grid(row=0, column=0, padx=(0, 8))
        self.results_box = ttk.Combobox(self.result_row, state="readonly", width=28)
        self.results_box.grid(row=0, column=1, sticky="ew")
        self.results_box.bind("<<ComboboxSelected>>", self.choose_result)
        self.query.trace_add("write", self.query_edited)

        tools = ttk.Frame(body)
        tools.grid(row=2, column=0, sticky="ew", pady=(8, 4))
        tools.columnconfigure(0, weight=1)
        ttk.Label(tools, text="ドラッグで移動、クリックで地点を選択").grid(row=0, column=0, sticky="w")
        for column, (label, delta) in enumerate((("縮小 −", -1), ("拡大 ＋", 1)), 1):
            ttk.Button(tools, text=label, command=lambda d=delta: self.map.zoom_by(d)).grid(
                row=0, column=column, padx=(6, 0))
        self.map = MapCanvas(body, self.pick)
        self.map.grid(row=3, column=0, sticky="nsew")
        credits = ttk.Frame(body)
        credits.grid(row=4, column=0, sticky="ew", pady=(2, 4))
        for label, url in (("出典：地理院タイル", "https://maps.gsi.go.jp/development/ichiran.html"),
                           ("CSISシンプルジオコーディング実験を利用", "https://geocode.csis.u-tokyo.ac.jp/")):
            ttk.Button(credits, text=label, style="Link.TButton",
                       command=lambda link=url: webbrowser.open(link)).pack(side="left", padx=(0, 8))
        ttk.Button(credits, text="広域図の出典", style="Link.TButton",
                   command=self.show_credits).pack(side="left")
        self.feedback = ttk.Label(body, justify="left", wraplength=480)
        self.feedback.grid(row=5, column=0, sticky="ew", pady=(0, 4))
        self.feedback.bind("<Configure>", lambda e: self.feedback.configure(wraplength=max(140, e.width - 4)))
        self.message.trace_add("write", self.update_feedback)
        self.map.notice.trace_add("write", self.update_feedback)

        selection = ttk.Frame(body, style="Card.TFrame", padding=(12, 8))
        selection.grid(row=6, column=0, sticky="ew")
        selection.columnconfigure(1, weight=1)
        ttk.Label(selection, text="時計での表示名", style="Card.TLabel").grid(row=0, column=0, padx=(0, 8))
        ttk.Entry(selection, textvariable=self.name).grid(row=0, column=1, sticky="ew")
        ttk.Label(selection, textvariable=self.coordinates, style="CardMuted.TLabel").grid(
            row=1, column=1, sticky="w", pady=(4, 0))
        buttons = ttk.Frame(body)
        buttons.grid(row=7, column=0, sticky="e", pady=(8, 0))
        ttk.Button(buttons, text="キャンセル", command=self.close).pack(side="left", padx=(0, 8))
        self.apply_button = ttk.Button(buttons, text="この地点を使う", style="Accent.TButton", command=self.apply)
        self.apply_button.pack(side="left")
        self.name.trace_add("write", self.update_apply)
        try:
            lat, lon = float(lat), float(lon)
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                self.select_point(lat, lon, name, center=True)
        except (TypeError, ValueError):
            pass
        self.update_apply()
        self.bind("<Map>", self.activate)

    def activate(self, event):
        if event.widget is self:
            self.grab_set()
            self.search_entry.focus_set()
            self.unbind("<Map>")

    def update_feedback(self, *_):
        self.feedback.configure(text="  ".join(filter(None, (self.message.get(), self.map.notice.get()))))

    def show_credits(self):
        text = (Path(__file__).with_name("assets") / "map-credits.txt").read_text(encoding="utf-8")
        messagebox.showinfo("広域図の出典", text, parent=self)

    def update_apply(self, *_):
        ready = self.point is not None and self.name.get().strip()
        self.apply_button.state(["!disabled" if ready else "disabled"])

    def select_point(self, lat, lon, name, *, center):
        self.point = (lat, lon)
        self.map.set_marker(lat, lon)
        if center:
            zoom = 13 if 20 <= lat <= 46 and 122 <= lon <= 154 else 6
            self.map.center_at(lat, lon, zoom)
        self.coordinates.set(f"緯度  {lat:.6f}     経度  {lon:.6f}")
        self.name.set(name)

    def cancel_lookup(self):
        self.searching = False
        if self.future is not None:
            self.future.cancel()
            self.future = None
        if self.poll_id is not None:
            self.after_cancel(self.poll_id)
            self.poll_id = None

    def request(self, function, args, done, error_message):
        self.cancel_lookup()
        self.future = self.executor.submit(function, *args)

        def poll():
            self.poll_id = None
            if not self.future.done():
                self.poll_id = self.after(75, poll)
                return
            self.searching = False
            try:
                value = self.future.result()
            except (OSError, ValueError, RuntimeError) as error:
                self.message.set(f"{error_message}（{error}）")
            else:
                done(value)
        self.poll_id = self.after(75, poll)

    def query_edited(self, *_):
        self.places = []
        self.result_row.grid_remove()
        if self.searching:
            self.cancel_lookup()
            self.message.set("")

    def search(self, _event=None):
        query = self.query.get().strip()
        if query:
            self.places = []
            self.result_row.grid_remove()
            self.message.set("地名・住所を検索しています…")
            self.request(geocoding.search, (query,), self.show_results, "検索できませんでした")
            self.searching = True
        else:
            self.message.set("検索する地名または住所を入力してください。")
        return "break"

    def show_results(self, places):
        self.places = places
        if not places:
            self.message.set("候補がありません。別の地名・住所で検索するか、地図から選んでください。")
            return
        self.results_box.configure(values=[f"{p.name} （{p.latitude:.4f}, {p.longitude:.4f}）" for p in places])
        self.result_row.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self.results_box.current(0)
        self.choose_result()

    def choose_result(self, _event=None):
        index = self.results_box.current()
        if 0 <= index < len(self.places):
            self.cancel_lookup()
            place = self.places[index]
            self.select_point(place.latitude, place.longitude, place.name, center=True)
            self.message.set("候補を選ぶか、地図をクリックして位置を微調整できます。")

    def pick(self, lat, lon):
        self.select_point(lat, lon, "", center=False)
        self.message.set("選んだ位置の地名を取得しています…")

        def show_name(name):
            if not self.name.get().strip():
                self.name.set(name)
            self.message.set("表示名を編集できます。" if name else "この位置の地名が見つかりません。表示名を入力してください。")
        self.request(geocoding.reverse, (lat, lon), show_name, "地名を取得できません。表示名を入力してください")

    def apply(self):
        if self.point is not None and self.name.get().strip():
            self.on_apply(self.name.get().strip(), *self.point)
            self.close()

    def dispose(self, event):
        if event.widget is self:
            self.cancel_lookup()
            self.executor.shutdown(wait=False, cancel_futures=True)

    def close(self):
        self.map.close()
        self.destroy()
