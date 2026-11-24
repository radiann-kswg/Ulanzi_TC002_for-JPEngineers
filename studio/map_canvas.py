"""Interactive Web Mercator map using GSI's public raster tiles."""
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPException
import math
import struct
import tkinter as tk
from urllib.request import Request, urlopen

from . import theme


TILE = 256
MIN_ZOOM, MAX_ZOOM = 2, 18
MAX_LATITUDE = math.degrees(math.atan(math.sinh(math.pi)))
TILE_WORKERS = 3


def _project(lat, lon, zoom):
    size = TILE << zoom
    lat = max(-MAX_LATITUDE, min(MAX_LATITUDE, lat))
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) * size / 2
    return ((lon + 180) / 360 * size) % size, max(0, min(size, y))


def _coordinates(x, y, zoom):
    size = TILE << zoom
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * max(0, min(size, y)) / size))))
    return lat, (x % size) / size * 360 - 180


def _fetch_tile(key):
    zoom, x, y = key
    layer = "std" if zoom <= 8 else "pale"
    url = f"https://cyberjapandata.gsi.go.jp/xyz/{layer}/{zoom}/{x}/{y}.png"
    request = Request(url, headers={"User-Agent": "Ulanzi-TC002-for-JPEngineers/1.0 (weather location picker)"})
    limit = 512 * 1024
    with urlopen(request, timeout=5) as reply:
        data = reply.read(limit + 1)
    if (len(data) > limit or data[:16] != b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
            or data[16:24] != struct.pack(">II", TILE, TILE)):
        raise ValueError("Unexpected tile image")
    return data


class MapCanvas(tk.Canvas):
    def __init__(self, parent, on_pick):
        super().__init__(parent, width=520, height=290, takefocus=True, cursor="crosshair",
                         borderwidth=0, highlightthickness=2, background=theme.FIELD,
                         highlightbackground=theme.EDGE, highlightcolor=theme.ACCENT)
        self.notice = tk.StringVar(self)
        self.on_pick = on_pick
        self.zoom = 5
        self.center = _project(36.5, 137.5, self.zoom)
        self.marker = None
        self.press = None
        self.dragged = False
        self.wheel_delta = 0
        self.photos = OrderedDict()
        self.failed = set()
        self.visible = {}
        self.executor = ThreadPoolExecutor(max_workers=TILE_WORKERS, thread_name_prefix="gsi-tile")
        self.requests = {}
        self.redraw_id = self.poll_id = None
        self.closed = False
        self.bind("<Configure>", self._request_draw)
        self.bind("<Map>", self._request_draw)
        self.bind("<Destroy>", lambda _: self.close())
        self.bind("<ButtonPress-1>", self._start_drag)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<MouseWheel>", self._wheel)
        self.bind("<KeyPress>", self._key)

    def center_at(self, lat, lon, zoom=None):
        if zoom is not None:
            self.zoom = max(MIN_ZOOM, min(MAX_ZOOM, int(zoom)))
        self.center = _project(lat, lon, self.zoom)
        self._request_draw()

    def set_marker(self, lat, lon):
        self.marker = (lat, lon)
        self._request_draw()

    def zoom_by(self, delta, point=None):
        zoom = max(MIN_ZOOM, min(MAX_ZOOM, self.zoom + delta))
        if zoom == self.zoom:
            return
        dx, dy = (0, 0) if point is None else self._offset(*point)
        scale = 2 ** (zoom - self.zoom)
        x, y = self.center
        self.zoom = zoom
        self._move_to((x + dx) * scale - dx, (y + dy) * scale - dy)

    def close(self):
        if self.closed:
            return
        self.closed = True
        for callback in (self.redraw_id, self.poll_id):
            if callback is not None:
                self.after_cancel(callback)
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.requests.clear()
        self.photos.clear()

    def _offset(self, x, y):
        return x - self.winfo_width() / 2, y - self.winfo_height() / 2

    def _move_to(self, x, y):
        size = TILE << self.zoom
        self.center = (x % size, max(0, min(size, y)))
        self._request_draw()

    def _start_drag(self, event):
        self.focus_set()
        self.press = (event.x, event.y, *self.center)
        self.dragged = False

    def _drag(self, event):
        if self.press is None:
            return
        x, y, cx, cy = self.press
        dx, dy = event.x - x, event.y - y
        if not self.dragged and max(abs(dx), abs(dy)) < 4:
            return
        self.dragged = True
        self.configure(cursor="fleur")
        self._move_to(cx - dx, cy - dy)

    def _release(self, event):
        if self.press is None:
            return
        self._drag(event)
        self.press = None
        self.configure(cursor="crosshair")
        if not self.dragged and 0 <= event.x < self.winfo_width() and 0 <= event.y < self.winfo_height():
            self._pick(*self._offset(event.x, event.y))

    def _pick(self, dx, dy):
        x, y = self.center
        if not 0 <= y + dy <= TILE << self.zoom:
            return
        point = _coordinates(x + dx, y + dy, self.zoom)
        self.set_marker(*point)
        self.on_pick(*point)

    def _wheel(self, event):
        self.wheel_delta += event.delta
        steps = math.trunc(self.wheel_delta / 120)
        if steps:
            self.wheel_delta -= steps * 120
            self.zoom_by(steps, (event.x, event.y))
        return "break"

    def _key(self, event):
        key = event.keysym
        shifts = {"Left": (-48, 0), "Right": (48, 0), "Up": (0, -48), "Down": (0, 48)}
        if key in shifts:
            dx, dy = shifts[key]
            x, y = self.center
            self._move_to(x + dx, y + dy)
        elif key in ("plus", "equal", "KP_Add"):
            self.zoom_by(1)
        elif key in ("minus", "KP_Subtract"):
            self.zoom_by(-1)
        elif key in ("Return", "space"):
            self._pick(0, 0)
        elif key.lower() == "r":
            self.failed.clear()
            self._request_draw()
        else:
            return
        return "break"

    def _request_draw(self, _event=None):
        if not self.closed and self.redraw_id is None:
            self.redraw_id = self.after_idle(self._draw)

    def _draw(self):
        self.redraw_id = None
        if not self.winfo_ismapped():
            return
        width, height = self.winfo_width(), self.winfo_height()
        cx, cy = self.center
        left, top = cx - width / 2, cy - height / 2
        count = 1 << self.zoom
        self.delete("all")
        self.visible = {}
        for row in range(max(0, math.floor(top / TILE)), min(count, math.ceil((top + height) / TILE))):
            for col in range(math.floor(left / TILE), math.ceil((left + width) / TILE)):
                key = (self.zoom, col % count, row)
                x, y = round(col * TILE - left), round(row * TILE - top)
                distance = (x + TILE / 2 - width / 2) ** 2 + (y + TILE / 2 - height / 2) ** 2
                self.visible[key] = min(distance, self.visible.get(key, math.inf))
                if key in self.photos:
                    self.create_image(x, y, image=self.photos[key], anchor="nw")
                    self.photos.move_to_end(key)
                else:
                    self.create_rectangle(x, y, x + TILE, y + TILE, outline=theme.EDGE)
                    lat, lon = _coordinates(col * TILE, row * TILE, self.zoom)
                    self.create_text(x + 8, y + 6, anchor="nw", fill=theme.MUTED, font=(theme.FONT, 9),
                                     text=f"{lat:.3f}°, {lon:.3f}°")
        if self.marker is not None:
            mx, my = _project(*self.marker, self.zoom)
            size = count * TILE
            x = width / 2 + ((mx - cx + size / 2) % size - size / 2)
            y = my - top
            self.create_oval(x - 8, y - 8, x + 8, y + 8, fill=theme.ACCENT, outline=theme.INK, width=3)
        x, y = width / 2, height / 2
        for color, stroke in ((theme.TEXT, 3), (theme.FIELD, 1)):
            for dx, dy in ((6, 0), (0, 6)):
                self.create_line(x - dx, y - dy, x + dx, y + dy, fill=color, width=stroke)
        self.failed.intersection_update(self.visible)
        self._load_visible()

    def _load_visible(self):
        for key in sorted(self.visible, key=self.visible.get):
            if len(self.requests) >= TILE_WORKERS:
                break
            if key not in self.photos and key not in self.failed and key not in self.requests:
                self.requests[key] = self.executor.submit(_fetch_tile, key)
        if self.requests and self.poll_id is None:
            self.poll_id = self.after(60, self._poll)
        if self.failed:
            message = "地図の一部を取得できません。縮小するか、地図上で R キーを押して再試行してください。"
        elif self.requests:
            message = "地図を読み込んでいます…"
        else:
            message = ""
        if self.notice.get() != message:
            self.notice.set(message)

    def _poll(self):
        self.poll_id = None
        finished = False
        for key, future in list(self.requests.items()):
            if not future.done():
                continue
            finished = True
            del self.requests[key]
            if key not in self.visible:
                continue
            try:
                self.photos[key] = tk.PhotoImage(master=self, data=future.result(), format="png")
            except (OSError, HTTPException, ValueError, tk.TclError):
                self.failed.add(key)
            # All visible tiles plus a small recently visited area stay in memory.
            while len(self.photos) > len(self.visible) + 40:
                self.photos.popitem(last=False)
        if finished:
            self._request_draw()
        elif self.requests:
            self.poll_id = self.after(60, self._poll)
