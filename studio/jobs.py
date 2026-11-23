"""Run one device or setup operation at a time, keeping all Tk calls on the UI thread."""
from queue import Empty, Queue
from threading import Thread
import tkinter as tk
from tkinter import ttk


def active_task(widget):
    return getattr(widget.winfo_toplevel(), "_tc002_task", None)


class TaskStatus(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        self.text = tk.StringVar(self)
        self.label = ttk.Label(self, textvariable=self.text, justify="left")
        self.label.grid(row=0, column=0, sticky="ew")
        self.label.bind("<Configure>", lambda event: self.label.configure(wraplength=max(160, event.width - 4)))
        self.bar = ttk.Progressbar(self, mode="indeterminate", length=72)
        self.bar.grid(row=0, column=1, padx=(12, 0), sticky="e")
        self.bar.grid_remove()

    @property
    def busy(self):
        return active_task(self) is not None

    def message(self, text):
        self.text.set(text)

    def run(self, title, worker, buttons=(), on_success=None):
        if self.busy:
            if active_task(self) is not self:
                self.message("ほかのタブの処理が完了するまでお待ちください。")
            return False
        root = self.winfo_toplevel()
        root._tc002_task = self
        enabled = [button for button in buttons if button.instate(["!disabled"])]
        for button in enabled:
            button.state(["disabled"])
        self.message(title)
        self.bar.grid()
        self.bar.start(35)
        result = Queue(maxsize=1)

        def work():
            try:
                result.put((True, worker()))
            except Exception as error:
                result.put((False, str(error) or type(error).__name__))

        def collect():
            try:
                ok, value = result.get_nowait()
            except Empty:
                self.after(90, collect)
                return
            root._tc002_task = None
            self.bar.stop()
            self.bar.grid_remove()
            for button in enabled:
                button.state(["!disabled"])
            self.message(value)
            if ok and on_success:
                on_success(value)

        Thread(target=work, daemon=True).start()
        self.after(90, collect)
        return True
