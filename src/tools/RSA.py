import tkinter as tk
from tkinter import messagebox
from tkinter.scrolledtext import ScrolledText
import ttkbootstrap as ttk

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
import base64


# 生成RSA密钥对
def generate_keys(key_size: int = 2048):
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
    )
    public_key = private_key.public_key()
    return private_key, public_key


# 将RSA私钥转换为字符串
def serialize_private_key(private_key, password=None):
    ea = serialization.BestAvailableEncryption(password) if password else serialization.NoEncryption()
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=ea
    )
    return pem.decode('utf-8')


# 将RSA公钥转换为字符串
def serialize_public_key(public_key):
    pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return pem.decode('utf-8')


# 使用公钥加密数据
def encrypt_message(public_key, message):
    ciphertext = public_key.encrypt(
        message,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return base64.b64encode(ciphertext)


# 使用私钥解密数据
def decrypt_message(private_key, encrypted_message):
    original_message = private_key.decrypt(
        base64.b64decode(encrypted_message),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return original_message


class RSAKeyFrame:
    def __init__(self, master=None):
        self.root = ttk.Frame(master)
        self.root.pack(fill='both', expand=True, padx=3, pady=3)

        frame = ttk.Frame(self.root)
        frame.pack(fill='x')

        ttk.Label(frame, text='Length:').pack(side="left")
        self.combobox = ttk.Combobox(frame, values=("1024", "2048", "4096", "8192"), state="readonly")
        self.combobox.current(1)
        self.combobox.pack(side="left")
        ttk.Label(frame, text='Password:').pack(side="left")
        self.pwd = ttk.Entry(frame)
        self.pwd.pack(side="left")
        ttk.Button(frame, text="Generate", command=self.generate, bootstyle="primary").pack(side="left")
        lf1 = ttk.LabelFrame(self.root, text="Private key")
        self.private_key_text = ScrolledText(lf1, width=50, height=10)
        self.private_key_text.pack(fill='both', expand=True)
        lf1.pack(fill='both', expand=True)
        lf2 = ttk.LabelFrame(self.root, text="Public key")
        self.public_key_text = ScrolledText(lf2, width=50, height=10)
        self.public_key_text.pack(fill='both', expand=True)
        lf2.pack(fill='both', expand=True)

    def generate(self):
        key_size = self.combobox.get()
        key_size = int(key_size)
        pwd = self.pwd.get()
        pwd = None if pwd == "" else pwd.encode()
        private_key, public_key = generate_keys(key_size)
        self.private_key_text.delete("1.0", tk.END)
        self.public_key_text.delete("1.0", tk.END)
        self.private_key_text.insert(tk.END, serialize_private_key(private_key, pwd))
        self.public_key_text.insert(tk.END, serialize_public_key(public_key))


class RsaPublicKey:
    def __init__(self, master=None):
        self.root = ttk.Frame(master)
        self.root.pack(fill='both', expand=True, padx=3, pady=3)

        lf1 = ttk.LabelFrame(self.root, text="Private key")
        self.private_key_text = ScrolledText(lf1, width=50, height=10)
        self.private_key_text.pack(fill='both', expand=True)
        lf1.pack(fill='both', expand=True)
        frame = ttk.Frame(self.root)
        ttk.Label(frame, text="Password:").pack(side='left')
        self.pwd = ttk.Entry(frame)
        self.pwd.pack(side='left')
        ttk.Button(frame, text="Generate", command=self.generate, bootstyle="primary").pack(side='left')
        frame.pack(fill='x')
        lf3 = ttk.LabelFrame(self.root, text="Public key")
        self.public_key_text = ScrolledText(lf3, width=50, height=10)
        self.public_key_text.pack(fill='both', expand=True)
        lf3.pack(fill='both', expand=True)

    def generate(self):
        pwd = self.pwd.get()
        pwd = None if pwd == "" else pwd.encode()
        private_pem = self.private_key_text.get('1.0', 'end')
        try:
            private_key = serialization.load_pem_private_key(private_pem.encode(), password=pwd)
        except TypeError:
            messagebox.showerror("Error", "Password is incorrect")
            return
        except ValueError:
            messagebox.showerror("Error", "Private key is incorrect")
            return
        public_key = private_key.public_key()
        self.public_key_text.delete("1.0", tk.END)
        self.public_key_text.insert(tk.END, serialize_public_key(public_key))


class RSACheck:
    def __init__(self, master=None):
        self.root = ttk.Frame(master)
        self.root.pack(fill='both', expand=True, padx=3, pady=3)

        frame = ttk.Frame(self.root)
        frame.pack(side='bottom', fill='x')
        ttk.Label(frame, text="Password:").pack(side='left')
        self.pwd = ttk.Entry(frame)
        self.pwd.pack(side='left')
        ttk.Button(frame, text="Check", command=self.check, bootstyle="primary").pack(side='left')
        self.res = ttk.Label(frame)
        self.res.pack(side='left', padx=3)
        lf1 = ttk.LabelFrame(self.root, text='Private Key')
        self.private_key_text = ScrolledText(lf1, width=50, height=10)
        self.private_key_text.pack(fill='both', expand=True)
        lf1.pack(fill='both', expand=True)
        lf2 = ttk.LabelFrame(self.root, text='Public Key')
        self.public_key_text = ScrolledText(lf2, width=50, height=10)
        self.public_key_text.pack(fill='both', expand=True)
        lf2.pack(fill='both', expand=True)

    def check(self):
        pwd = self.pwd.get()
        pwd = None if pwd == "" else pwd.encode()
        private_pem = self.private_key_text.get('1.0', 'end')
        public_pem = self.public_key_text.get('1.0', 'end')

        try:
            private_key = serialization.load_pem_private_key(private_pem.encode(), password=pwd)
        except TypeError:
            self.res.config(text="Result: Password is incorrect")
            return
        except ValueError:
            self.res.config(text="Result: Private key is incorrect")
            return
        try:
            public_key = serialization.load_pem_public_key(public_pem.encode())
        except ValueError:
            self.res.config(text="Result: Public key is incorrect")
            return
        message = b"Hello, RSA encryption!"
        encrypted_message = encrypt_message(public_key, message)
        try:
            decrypted_message = decrypt_message(private_key, encrypted_message)
        except ValueError:
            self.res.config(text="Result: Check failed")
            return
        if decrypted_message == message:
            self.res.config(text="Result: Check success")
        else:
            self.res.config(text="Result: Check failed")


class RSAEncrypt:
    def __init__(self, master=None):
        self.root = ttk.Frame(master)
        self.root.pack(fill='both', expand=True, padx=3, pady=3)

        lf1 = ttk.LabelFrame(self.root, text="Raw text")
        self.raw_text = ScrolledText(lf1, width=50, height=5)
        self.raw_text.pack(fill='both', expand=True)
        lf1.pack(fill='both', expand=True)
        lf2 = ttk.LabelFrame(self.root, text="Public key")
        self.public_key_text = ScrolledText(lf2, width=50, height=5)
        self.public_key_text.pack(fill='both', expand=True)
        lf2.pack(fill='both', expand=True)
        ttk.Button(self.root, text="Encrypt", command=lambda: self.encrypt(), bootstyle="primary").pack()
        lf4 = ttk.LabelFrame(self.root, text="Encrypted text")
        self.encrypt_text = ScrolledText(lf4, width=50, height=5)
        self.encrypt_text.pack(fill='both', expand=True)
        lf4.pack(fill='both', expand=True)

    def encrypt(self):
        public_pem = self.public_key_text.get('1.0', 'end')
        try:
            public_key = serialization.load_pem_public_key(public_pem.encode())
        except ValueError:
            messagebox.showerror("Error", "Public key is incorrect")
            return
        message = self.raw_text.get("1.0", "end")
        encrypted_message = encrypt_message(public_key, message.encode())
        self.encrypt_text.delete("1.0", tk.END)
        self.encrypt_text.insert(tk.END, encrypted_message.decode())


class RSADecrypt:
    def __init__(self, master=None):
        self.root = ttk.Frame(master)
        self.root.pack(fill='both', expand=True, padx=3, pady=3)
        lf1 = ttk.LabelFrame(self.root, text="Encrypted text")
        self.encrypt_text = ScrolledText(lf1, width=50, height=5)
        self.encrypt_text.pack(fill='both', expand=True)
        lf1.pack(fill='both', expand=True)
        lf2 = ttk.LabelFrame(self.root, text="Private key")
        self.private_key_text = ScrolledText(lf2, width=50, height=5)
        self.private_key_text.pack(fill='both', expand=True)
        lf2.pack(fill='both', expand=True)
        f3 = ttk.Frame(self.root)
        ttk.Label(f3, text="Password:").pack(side="left")
        self.pwd = ttk.Entry(f3)
        self.pwd.pack(side="left")
        ttk.Button(f3, text="Decrypt", command=self.decrypt, bootstyle="primary").pack(side="left")
        f3.pack(fill='x')
        lf4 = ttk.LabelFrame(self.root, text="Decrypted text")
        self.raw_text = ScrolledText(lf4, width=50, height=5)
        self.raw_text.pack(fill='both', expand=True)
        lf4.pack(fill='both', expand=True)

    def decrypt(self):
        pwd = self.pwd.get()
        pwd = None if pwd == "" else pwd.encode()
        private_pem = self.private_key_text.get('1.0', 'end')
        encrypted_message = self.encrypt_text.get('1.0', 'end')
        try:
            private_key = serialization.load_pem_private_key(private_pem.encode(), password=pwd)
        except TypeError:
            messagebox.showerror("Error", "Password is incorrect")
            return
        except ValueError:
            messagebox.showerror("Error", "Private key is incorrect")
            return
        try:
            decrypted_message = decrypt_message(private_key, encrypted_message.encode())
        except ValueError as e:
            messagebox.showerror("Error", str(e))
            return
        self.raw_text.delete("1.0", tk.END)
        self.raw_text.insert(tk.END, decrypted_message.decode())
