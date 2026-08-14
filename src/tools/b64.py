import base64
import tkinter as tk
from tkinter import messagebox
from tkinter.scrolledtext import ScrolledText
import ttkbootstrap as ttk


class Base64GUI:
    """ base64 Window """
    def __init__(self, master=None) -> None:
        self.root = ttk.Frame(master)
        self.root.pack(fill='both', expand=True, padx=5, pady=5)
        input_frame = ttk.LabelFrame(self.root, text="Input")
        self.input_box = ScrolledText(input_frame, height=10)
        self.input_box.pack(fill="both", expand=True)
        input_frame.pack(fill="both", expand=True)

        bframe = ttk.Frame(self.root)
        ebtn = ttk.Button(bframe, text="Encrypt", command=self.encrypto, bootstyle="primary")
        ebtn.pack(side=tk.LEFT)
        dbtn = ttk.Button(bframe, text="Decrypt", command=self.decrypto, bootstyle="secondary")
        dbtn.pack(side=tk.LEFT)
        bframe.pack()

        output_frame = ttk.LabelFrame(self.root, text="Output")
        self.output_box = ScrolledText(output_frame, height=10)
        self.output_box.pack(fill="both", expand=True)
        output_frame.pack(fill="both", expand=True)

    def encrypto(self):
        input_text = self.input_box.get(1.0, tk.END)
        res = base64.b64encode(input_text.encode("utf-8")).decode("utf-8")
        self.output_box.delete(1.0, tk.END)
        self.output_box.insert(1.0, res)

    def decrypto(self):
        try:
            input_text = self.input_box.get(1.0, tk.END)
            res = base64.b64decode(input_text.encode("utf-8")).decode("utf-8")
            self.output_box.delete(1.0, tk.END)
            self.output_box.insert(1.0, res)
        except Exception as e:
            messagebox.showerror("Error", str(e))
