from tkinter import  messagebox
import ttkbootstrap as ttk
from tkinter.scrolledtext import ScrolledText
import hashlib


class MD5GUI:
    """ MD5 Window """
    def __init__(self, master=None):
        self.root = ttk.Frame(master)
        self.root.pack(fill='both', expand=True, padx=5, pady=5)
        init_data_label = ttk.LabelFrame(self.root, text="Input")
        self.init_data_text = ScrolledText(init_data_label, height=10)  # Raw data entry box
        self.init_data_text.pack(fill='both', expand=True)
        init_data_label.pack(fill='both', expand=True)
        ttk.Button(self.root, text="MD5", width=10, command=self.str_trans_to_md5, bootstyle="primary").pack()
        result_data_label = ttk.LabelFrame(self.root, text="Output")
        self.result_data_text = ScrolledText(result_data_label, height=10)  # Processing result presentation
        self.result_data_text.pack(fill='both', expand=True)
        result_data_label.pack(fill='both', expand=True)

    def str_trans_to_md5(self):
        src = self.init_data_text.get(1.0, "end").strip().replace("\n", "").encode()
        try:
            hasher = hashlib.md5()
            hasher.update(src)
            res = hasher.hexdigest()
            self.result_data_text.delete(1.0, "end")
            self.result_data_text.insert(1.0, res + "\n")
            self.result_data_text.insert("end", res.upper())
        except Exception as e:
            self.result_data_text.delete(1.0, "end")
            messagebox.showinfo("Error", str(e))
