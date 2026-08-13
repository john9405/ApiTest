from tkinter import  messagebox
import ttkbootstrap as ttk
from tkinter.scrolledtext import ScrolledText
import base64

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad


class AesGui:
    """ aes Window """
    def __init__(self, master=None):
        self.root = ttk.Frame(master)
        self.root.pack(fill='both', expand=True, padx=5, pady=5)

        frame1 = ttk.Frame(self.root)
        label2 = ttk.Label(frame1, text="Key:")
        label2.grid(row=2, column=2, sticky='w', padx=3)
        self.entry2 = ttk.Entry(frame1)
        self.entry2.grid(row=2, column=3, sticky='w')

        label7 = ttk.Label(frame1, text="IV:")
        label7.grid(row=3, column=2, sticky='w', padx=3)
        self.entry3 = ttk.Entry(frame1)
        self.entry3.grid(row=3, column=3, sticky='w', pady=3)

        label3 = ttk.Label(frame1, text="Encryption:")
        label3.grid(row=2, column=0, sticky='w')
        self.mode_box = ttk.Combobox(frame1, values=("ECB", "CBC"))
        self.mode_box.current(0)
        self.mode_box.grid(row=2, column=1, sticky='w')

        label4 = ttk.Label(frame1, text="Padding:")
        label4.grid(row=3, column=0, sticky='w')
        self.padding_box = ttk.Combobox(frame1, values=("nopadding", "pkcs7", "iso7816", "x923"))
        self.padding_box.current(0)
        self.padding_box.grid(row=3, column=1, sticky='w', pady=3)

        label5 = ttk.Label(frame1, text="Block:")
        label5.grid(row=4, column=0, sticky='w')
        self.blocksize_box = ttk.Combobox(frame1, values=("128", "192", "256"))
        self.blocksize_box.current(0)
        self.blocksize_box.grid(row=4, column=1, sticky='w')

        # 创建输入框和标签
        label1 = ttk.LabelFrame(self.root, text="Input:")
        self.entry1 = ScrolledText(label1, width=50, height=10)
        self.entry1.pack(fill='both', expand=True)
        label1.pack(fill='both', expand=True, pady=(0, 3))
        frame1.pack(fill='x')
        # 创建加密和解密按钮
        encrypt_button = ttk.Button(frame1, text="Encrypt", command=self.encrypt, bootstyle="primary")
        encrypt_button.grid(row=5, column=1, sticky='e', pady=(3, 0))
        decrypt_button = ttk.Button(frame1, text="Decrypt", command=self.decrypt, bootstyle="secondary")
        decrypt_button.grid(row=5, column=3, sticky='w')
        # 创建输出框和标签
        label6 = ttk.LabelFrame(self.root, text="Output:")
        self.text = ScrolledText(label6, width=50, height=10)
        self.text.pack(fill='both', expand=True)
        label6.pack(fill='both', expand=True)

    # 加密函数
    def encrypt(self):
        try:
            # 获取输入框中的明文和密钥
            plaintext = self.entry1.get("1.0", 'end')
            key = self.entry2.get()
            iv = self.entry3.get()
            mode = self.mode_box.get()
            padding = self.padding_box.get()
            blocksize = self.blocksize_box.get()
            plaintext = plaintext.encode()
            blocksize = int(blocksize)

            # 将密钥填充到指定长度
            if len(key) < blocksize / 8:
                messagebox.showerror("Error", f"The password must contain at least {blocksize / 8} characters.")
                return

            key = key.encode()

            # 根据选择的加密模式和填充方式创建AES对象
            if mode == "ECB":
                cipher = AES.new(key, AES.MODE_ECB)
            elif mode == "CBC":
                if len(iv) < 16:
                    messagebox.showerror("Error", "The offset length must be 16 bits.")
                    return

                iv = iv.encode()
                cipher = AES.new(key, AES.MODE_CBC, iv=iv)
            else:
                messagebox.showerror("Error", "Unsupported encryption mode.")
                return

            # 将明文填充到指定长度
            if padding == "pkcs7":
                plaintext = pad(plaintext, AES.block_size)
            elif padding == "iso7816":
                plaintext = pad(plaintext, AES.block_size, "iso7816")
            elif padding == "x923":
                plaintext = pad(plaintext, AES.block_size, "x923")

            # 加密明文并将结果转换为base64格式
            ciphertext = cipher.encrypt(plaintext)
            ciphertext = base64.b64encode(ciphertext).decode()

            # 显示加密结果
            self.text.delete(1.0, 'end')
            self.text.insert('end', ciphertext)
        except Exception as e:
            messagebox.showerror("error", str(e))
            return

    # 解密函数
    def decrypt(self):
        try:
            # 获取输入框中的密文和密钥
            ciphertext = self.entry1.get("1.0", 'end')
            ciphertext = ciphertext.encode()
            key = self.entry2.get()
            iv = self.entry3.get()
            mode = self.mode_box.get()
            padding = self.padding_box.get()
            blocksize = self.blocksize_box.get()
            blocksize = int(blocksize)

            # 将密钥填充到指定长度
            if len(key) < blocksize / 8:
                messagebox.showerror("Error", f"The password must contain at least {blocksize / 8} characters.")
                return

            key = key.encode()

            # 根据选择的加密模式和填充方式创建AES对象
            if mode == "ECB":
                cipher = AES.new(key, AES.MODE_ECB)
            elif mode == "CBC":
                if len(iv) < 16:
                    messagebox.showerror("Error", "The offset length must be 16 bits")
                    return
                cipher = AES.new(key, AES.MODE_CBC, iv=iv)
            else:
                messagebox.showerror("Error", "Unsupported encryption mode.")
                return

            ciphertext = base64.b64decode(ciphertext)
            plaintext = cipher.decrypt(ciphertext)

            if padding == "pkcs7":
                plaintext = unpad(plaintext, AES.block_size)
            elif padding == "iso7816":
                plaintext = unpad(plaintext, AES.block_size, "iso7816")
            elif padding == "x923":
                plaintext = unpad(plaintext, AES.block_size, "x923")

            # 解密密文并去除填充
            plaintext = plaintext.decode()

            # 显示解密结果
            self.text.delete(1.0, 'end')
            self.text.insert('end', plaintext)
        except Exception as e:
            messagebox.showerror("error", str(e))
            return
