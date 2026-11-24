"""Run one device or setup operation at a time, keeping all Tk calls on the UI thread."""
from queue import Empty, Queue
from threading import Thread
import tkinter as tk
from tkinter import ttk


class TaskStatus(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, style="Status.TFrame", padding=(18, 8))
        self.busy = False
        self.buttons = []
        self.columnconfigure(0, weight=1)
        self.text = tk.StringVar(self)
        self.label = ttk.Label(self, textvariable=self.text, justify="left", style="Status.TLabel")
        self.label.grid(row=0, column=0, sticky="ew")
        self.label.bind("<Configure>", lambda event: self.label.configure(wraplength=max(160, event.width - 4)))
        self.bar = ttk.Progressbar(self, mode="indeterminate", length=72)
        self.bar.grid(row=0, column=1, padx=(12, 0), sticky="e")
        self.bar.grid_remove()

    def register(self, *buttons):
        self.buttons.extend(buttons)
        if self.busy:
            for button in buttons:
                button.state(["disabled"])

    def set_busy(self, busy):
        self.busy = busy
        for button in self.buttons:
            button.state(["disabled" if busy else "!disabled"])

    def message(self, text):
        if not self.busy:
            self.text.set(text)

    def run(self, title, worker):
        if self.busy:
            return False
        self.set_busy(True)
        self.text.set(title)
        self.bar.grid()
        self.bar.start(35)
        result = Queue(maxsize=1)

        def work():
            try:
                result.put(worker())
            except Exception as error:
                result.put(str(error) or type(error).__name__)

        def collect():
            try:
                value = result.get_nowait()
            except Empty:
                self.after(90, collect)
                return
            self.bar.stop()
            self.bar.grid_remove()
            self.set_busy(False)
            self.message(value)

        Thread(target=work, daemon=True).start()
        self.after(90, collect)
        return True
