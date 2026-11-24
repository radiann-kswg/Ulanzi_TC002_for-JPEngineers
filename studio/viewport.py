"""A vertically scrollable settings page for a resizable Tk window."""
import tkinter as tk
from tkinter import font, ttk


def _viewport(widget):
    while widget is not None and not isinstance(widget, (Viewport, tk.Tk, tk.Toplevel)):
        widget = getattr(widget, "master", None)
    return widget if isinstance(widget, Viewport) else None


def _wheel(window, event):
    target = window.winfo_containing(event.x_root, event.y_root)
    view = _viewport(target)
    if view and view.canvas.yview() != (0.0, 1.0):
        # Windows reports 120 per wheel detent and smaller deltas on precision devices.
        view.scroll_by(-event.delta * view.line_height / 40)
        return "break"


def _focus(event):
    view = _viewport(event.widget)
    if view and event.widget not in (view, view.canvas, view.content, view.scrollbar):
        view.reveal(event.widget)


def bind_scrolling(window):
    # Windows can send the wheel to a focused field while the pointer is over another widget.
    window.bind("<MouseWheel>", lambda event: _wheel(window, event), add="+")
    window.bind("<FocusIn>", _focus, add="+")


class Viewport(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        background = ttk.Style(self).lookup("TFrame", "background", default="#242424")
        self.canvas = tk.Canvas(self, background=background, borderwidth=0, highlightthickness=0,
                                width=1, height=1, takefocus=False)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview, takefocus=False)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.content = ttk.Frame(self.canvas)
        self.item = self.canvas.create_window(0, 0, window=self.content, anchor="nw")
        self.pending_layout = None
        self.canvas.bind("<Map>", self.request_layout)
        self.canvas.bind("<Configure>", self.request_layout)
        self.content.bind("<Configure>", self.request_layout)
        # A page that shrinks above the visible area gets unmapped before it receives its new size.
        self.content.bind("<Unmap>", self.request_layout)
        self.line_height = font.nametofont("TkDefaultFont", root=self).metrics("linespace")

        self.bind("<Destroy>", self.cancel_layout)

    def cancel_layout(self, _event):
        if self.pending_layout is not None:
            self.after_cancel(self.pending_layout)

    def request_layout(self, _event):
        # Changing the scrollbar during a Windows grid Configure event can abort mapping the canvas.
        if self.pending_layout is None:
            self.pending_layout = self.after_idle(self.layout_content)

    def layout_content(self):
        self.pending_layout = None
        if not self.canvas.winfo_ismapped():
            return
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        if int(self.canvas.itemcget(self.item, "width")) != width:
            self.canvas.itemconfigure(self.item, width=width)
        content_height = self.content.winfo_reqheight()
        self.canvas.configure(scrollregion=(0, 0, width, max(content_height, height)))
        visible = bool(self.scrollbar.winfo_manager())
        if content_height > height and not visible:
            self.scrollbar.grid(row=0, column=1, sticky="ns")
        elif content_height <= height and visible:
            self.scrollbar.grid_remove()

    def scroll_by(self, pixels):
        height = max(self.canvas.winfo_height(), self.content.winfo_reqheight())
        self.canvas.yview_moveto(self.canvas.yview()[0] + pixels / height)

    def reveal(self, widget):
        offset = widget.winfo_rooty() - self.canvas.winfo_rooty()
        bottom = offset + widget.winfo_height()
        if offset < 0:
            self.scroll_by(offset - 4)
        elif bottom > self.canvas.winfo_height():
            self.scroll_by(bottom - self.canvas.winfo_height() + 4)
