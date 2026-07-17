from tkinter import ttk
from tkinter.scrolledtext import ScrolledText


class DraftPaper:
    def __init__(self, master=None):
        root = ttk.Frame(master)
        root.pack(fill="both", expand=True)
        ttk.Label(root, text='No content will be saved').pack(anchor='w')
        ScrolledText(root).pack(fill="both", expand=True)
