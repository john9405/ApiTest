from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QGroupBox,
    QPushButton,
    QComboBox,
)

from ..qui import show_error
from ..theme import style_role

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


def _load_private_key(pem_text, pwd):
    """Load a PKCS#8/PKCS#1 RSA private key.

    Returns (key, None) or (None, error_message).  ``load_pem_private_key``
    happily returns EC/Ed25519 keys too, which then blow up with AttributeError
    the moment ``.decrypt()`` is called, so the type is checked here.
    """
    try:
        key = serialization.load_pem_private_key(pem_text.encode(), password=pwd)
    except TypeError:
        return None, "Password is incorrect"
    except ValueError as error:
        # cryptography only raises TypeError for a missing/extra password; a
        # *wrong* password surfaces as ValueError("Bad decrypt...").
        if "decrypt" in str(error).lower():
            return None, "Password is incorrect"
        return None, "Private key is incorrect"
    except Exception:
        return None, "Private key is incorrect"
    if not isinstance(key, rsa.RSAPrivateKey):
        return None, "Not an RSA private key"
    return key, None


def _load_public_key(pem_text):
    """Load an RSA public key.  Returns (key, None) or (None, error_message)."""
    try:
        key = serialization.load_pem_public_key(pem_text.encode())
    except ValueError:
        return None, "Public key is incorrect"
    except Exception:
        return None, "Public key is incorrect"
    if not isinstance(key, rsa.RSAPublicKey):
        return None, "Not an RSA public key"
    return key, None


def oaep_plaintext_limit(public_key):
    """Largest plaintext OAEP-SHA256 can encrypt with this key, in bytes."""
    return public_key.key_size // 8 - 2 * hashes.SHA256().digest_size - 2


def _text_group(parent, title, height=120):
    """A QGroupBox titled `title` containing a QPlainTextEdit."""
    group = QGroupBox(title, parent)
    lay = QVBoxLayout(group)
    text = QPlainTextEdit(group)
    text.setMinimumHeight(height)
    lay.addWidget(text)
    return group, text


def _bar(parent):
    """A horizontal row of widgets."""
    bar = QWidget(parent)
    bar.setLayout(QHBoxLayout(bar))
    bar.layout().setContentsMargins(0, 4, 0, 4)
    return bar


class RSAKeyFrame:
    def __init__(self, master=None):
        self.root = QWidget(master)
        outer = QVBoxLayout(self.root)
        outer.setContentsMargins(3, 3, 3, 3)

        bar = _bar(self.root)
        bar.layout().addWidget(QLabel("Length:", bar))
        self.combobox = QComboBox(bar)
        self.combobox.addItems(("1024", "2048", "4096", "8192"))
        self.combobox.setCurrentIndex(1)
        bar.layout().addWidget(self.combobox)
        bar.layout().addWidget(QLabel("Password:", bar))
        self.pwd = QLineEdit(bar)
        self.pwd.setEchoMode(QLineEdit.Password)
        bar.layout().addWidget(self.pwd)
        btn = QPushButton("Generate", bar)
        style_role(btn, "primary")
        btn.clicked.connect(self.generate)
        bar.layout().addWidget(btn)
        bar.layout().addStretch(1)
        outer.addWidget(bar)

        group1, self.private_key_text = _text_group(self.root, "Private key")
        outer.addWidget(group1, 1)
        group2, self.public_key_text = _text_group(self.root, "Public key")
        outer.addWidget(group2, 1)

    def generate(self):
        key_size = int(self.combobox.currentText())
        pwd = self.pwd.text()
        pwd = None if pwd == "" else pwd.encode()
        private_key, public_key = generate_keys(key_size)
        self.private_key_text.setPlainText(serialize_private_key(private_key, pwd))
        self.public_key_text.setPlainText(serialize_public_key(public_key))


class RsaPublicKey:
    def __init__(self, master=None):
        self.root = QWidget(master)
        outer = QVBoxLayout(self.root)
        outer.setContentsMargins(3, 3, 3, 3)

        group1, self.private_key_text = _text_group(self.root, "Private key")
        outer.addWidget(group1, 1)

        bar = _bar(self.root)
        bar.layout().addWidget(QLabel("Password:", bar))
        self.pwd = QLineEdit(bar)
        self.pwd.setEchoMode(QLineEdit.Password)
        bar.layout().addWidget(self.pwd)
        btn = QPushButton("Generate", bar)
        style_role(btn, "primary")
        btn.clicked.connect(self.generate)
        bar.layout().addWidget(btn)
        bar.layout().addStretch(1)
        outer.addWidget(bar)

        group3, self.public_key_text = _text_group(self.root, "Public key")
        outer.addWidget(group3, 1)

    def generate(self):
        pwd = self.pwd.text()
        pwd = None if pwd == "" else pwd.encode()
        private_pem = self.private_key_text.toPlainText()
        private_key, error = _load_private_key(private_pem, pwd)
        if error is not None:
            show_error(self.root, "Error", error)
            return
        public_key = private_key.public_key()
        self.public_key_text.setPlainText(serialize_public_key(public_key))


class RSACheck:
    def __init__(self, master=None):
        self.root = QWidget(master)
        outer = QVBoxLayout(self.root)
        outer.setContentsMargins(3, 3, 3, 3)

        group1, self.private_key_text = _text_group(self.root, "Private Key")
        outer.addWidget(group1, 1)
        group2, self.public_key_text = _text_group(self.root, "Public Key")
        outer.addWidget(group2, 1)

        bar = _bar(self.root)
        bar.layout().addWidget(QLabel("Password:", bar))
        self.pwd = QLineEdit(bar)
        self.pwd.setEchoMode(QLineEdit.Password)
        bar.layout().addWidget(self.pwd)
        btn = QPushButton("Check", bar)
        style_role(btn, "primary")
        btn.clicked.connect(self.check)
        bar.layout().addWidget(btn)
        self.res = QLabel("", bar)
        bar.layout().addWidget(self.res)
        bar.layout().addStretch(1)
        outer.addWidget(bar)

    def check(self):
        pwd = self.pwd.text()
        pwd = None if pwd == "" else pwd.encode()
        private_pem = self.private_key_text.toPlainText()
        public_pem = self.public_key_text.toPlainText()

        private_key, error = _load_private_key(private_pem, pwd)
        if error is not None:
            self.res.setText(f"Result: {error}")
            return
        public_key, error = _load_public_key(public_pem)
        if error is not None:
            self.res.setText(f"Result: {error}")
            return
        message = b"Hello, RSA encryption!"
        try:
            encrypted_message = encrypt_message(public_key, message)
            decrypted_message = decrypt_message(private_key, encrypted_message)
        except Exception:
            self.res.setText("Result: Check failed")
            return
        if decrypted_message == message:
            self.res.setText("Result: Check success")
        else:
            self.res.setText("Result: Check failed")


class RSAEncrypt:
    def __init__(self, master=None):
        self.root = QWidget(master)
        outer = QVBoxLayout(self.root)
        outer.setContentsMargins(3, 3, 3, 3)

        group1, self.raw_text = _text_group(self.root, "Raw text", 90)
        outer.addWidget(group1, 1)
        group2, self.public_key_text = _text_group(self.root, "Public key", 90)
        outer.addWidget(group2, 1)

        btn = QPushButton("Encrypt", self.root)
        style_role(btn, "primary")
        btn.clicked.connect(self.encrypt)
        outer.addWidget(btn, 0, alignment=Qt.AlignHCenter)

        group4, self.encrypt_text = _text_group(self.root, "Encrypted text", 90)
        outer.addWidget(group4, 1)

    def encrypt(self):
        public_pem = self.public_key_text.toPlainText()
        public_key, error = _load_public_key(public_pem)
        if error is not None:
            show_error(self.root, "Error", error)
            return
        message = self.raw_text.toPlainText()
        data = message.encode()
        # OAEP-SHA256 can only encrypt key_size/8 - 66 bytes; cryptography's
        # ValueError used to escape this slot for anything longer.
        limit = oaep_plaintext_limit(public_key)
        if len(data) > limit:
            show_error(
                self.root, "Error",
                f"Message is too long for this key: {len(data)} bytes, "
                f"maximum {limit} bytes with a {public_key.key_size}-bit key.",
            )
            return
        self.encrypt_text.clear()
        try:
            encrypted_message = encrypt_message(public_key, data)
        except Exception as e:
            show_error(self.root, "Error", str(e))
            return
        self.encrypt_text.setPlainText(encrypted_message.decode())


class RSADecrypt:
    def __init__(self, master=None):
        self.root = QWidget(master)
        outer = QVBoxLayout(self.root)
        outer.setContentsMargins(3, 3, 3, 3)

        group1, self.encrypt_text = _text_group(self.root, "Encrypted text", 90)
        outer.addWidget(group1, 1)
        group2, self.private_key_text = _text_group(self.root, "Private key", 90)
        outer.addWidget(group2, 1)

        bar = _bar(self.root)
        bar.layout().addWidget(QLabel("Password:", bar))
        self.pwd = QLineEdit(bar)
        self.pwd.setEchoMode(QLineEdit.Password)
        bar.layout().addWidget(self.pwd)
        btn = QPushButton("Decrypt", bar)
        style_role(btn, "primary")
        btn.clicked.connect(self.decrypt)
        bar.layout().addWidget(btn)
        bar.layout().addStretch(1)
        outer.addWidget(bar)

        group4, self.raw_text = _text_group(self.root, "Decrypted text", 90)
        outer.addWidget(group4, 1)

    def decrypt(self):
        pwd = self.pwd.text()
        pwd = None if pwd == "" else pwd.encode()
        private_pem = self.private_key_text.toPlainText()
        encrypted_message = self.encrypt_text.toPlainText()
        private_key, error = _load_private_key(private_pem, pwd)
        if error is not None:
            show_error(self.root, "Error", error)
            return
        try:
            decrypted_message = decrypt_message(private_key, encrypted_message.encode())
        except ValueError as e:
            self.raw_text.clear()
            show_error(self.root, "Error", str(e))
            return
        except Exception as e:
            self.raw_text.clear()
            show_error(self.root, "Error", str(e))
            return
        # The plaintext need not be UTF-8 (it may have been produced by another
        # system), and .decode() sat outside the try, so those raised
        # UnicodeDecodeError straight out of the slot.
        self.raw_text.setPlainText(decrypted_message.decode("utf-8", errors="replace"))
