import base64
import secrets

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QPlainTextEdit,
    QGroupBox,
)

from ..qui import show_error
from ..theme import style_role
from PyQt5.QtWidgets import QPushButton

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

# AES always has a 128-bit block; these are the *key* sizes PyCryptodome
# accepts, and it picks the variant from the actual key length.
KEY_SIZES = {"128": 16, "192": 24, "256": 32}


class AesGui:
    """ aes Window """

    def __init__(self, master=None):
        self.root = QWidget(master)
        outer = QVBoxLayout(self.root)
        outer.setContentsMargins(5, 5, 5, 5)

        frame1 = QWidget(self.root)
        grid = QGridLayout(frame1)
        grid.setContentsMargins(0, 0, 0, 0)

        grid.addWidget(QLabel("Encryption:", frame1), 0, 0)
        self.mode_box = QComboBox(frame1)
        self.mode_box.addItems(("ECB", "CBC"))
        # CBC + pkcs7 works out of the box; the old ECB + nopadding default
        # rejected ordinary text with "Data must be aligned to block boundary".
        self.mode_box.setCurrentIndex(1)
        self.mode_box.currentTextChanged.connect(self._on_mode_changed)
        grid.addWidget(self.mode_box, 0, 1)

        grid.addWidget(QLabel("Key:", frame1), 0, 2)
        self.entry2 = QLineEdit(frame1)
        grid.addWidget(self.entry2, 0, 3)
        key_btn = QPushButton("Random", frame1)
        style_role(key_btn, "info")
        key_btn.setToolTip("Fill Key with random bytes for the selected key size")
        key_btn.clicked.connect(self._random_key)
        grid.addWidget(key_btn, 0, 4)

        grid.addWidget(QLabel("Padding:", frame1), 1, 0)
        self.padding_box = QComboBox(frame1)
        self.padding_box.addItems(("pkcs7", "nopadding", "iso7816", "x923"))
        self.padding_box.setCurrentIndex(0)
        grid.addWidget(self.padding_box, 1, 1)

        grid.addWidget(QLabel("IV:", frame1), 1, 2)
        self.entry3 = QLineEdit(frame1)
        grid.addWidget(self.entry3, 1, 3)
        iv_btn = QPushButton("Random", frame1)
        style_role(iv_btn, "info")
        iv_btn.setToolTip("Fill IV with 16 random bytes (CBC only)")
        iv_btn.clicked.connect(self._random_iv)
        grid.addWidget(iv_btn, 1, 4)

        grid.addWidget(QLabel("Key size:", frame1), 2, 0)
        self.blocksize_box = QComboBox(frame1)
        self.blocksize_box.addItems(tuple(KEY_SIZES))
        self.blocksize_box.setCurrentIndex(0)
        grid.addWidget(self.blocksize_box, 2, 1)

        buttons = QHBoxLayout()
        encrypt_button = QPushButton("Encrypt", frame1)
        style_role(encrypt_button, "primary")
        encrypt_button.clicked.connect(self.encrypt)
        buttons.addWidget(encrypt_button)
        decrypt_button = QPushButton("Decrypt", frame1)
        style_role(decrypt_button, "secondary")
        decrypt_button.clicked.connect(self.decrypt)
        buttons.addWidget(decrypt_button)
        buttons.addStretch(1)
        grid.addLayout(buttons, 3, 1, 1, 3)

        outer.addWidget(frame1)

        input_group = QGroupBox("Input:", self.root)
        in_lay = QVBoxLayout(input_group)
        self.entry1 = QPlainTextEdit(input_group)
        self.entry1.setMinimumHeight(120)
        in_lay.addWidget(self.entry1)
        outer.addWidget(input_group, 1)

        output_group = QGroupBox("Output:", self.root)
        out_lay = QVBoxLayout(output_group)
        self.text = QPlainTextEdit(output_group)
        self.text.setMinimumHeight(120)
        out_lay.addWidget(self.text)
        outer.addWidget(output_group, 1)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _on_mode_changed(self, mode):
        """The IV is only used by CBC; make that visible."""
        self.entry3.setEnabled(mode == "CBC")

    def _random_iv(self):
        self.entry3.setText(secrets.token_hex(8))

    def _random_key(self):
        """Fill the key with random bytes matching the selected key size.

        ``token_hex`` returns two characters per byte, so half the key length
        gives exactly 16, 24 or 32 ASCII characters — always valid UTF-8 and
        exactly what ``_resolve_key`` expects.
        """
        size = KEY_SIZES[self.blocksize_box.currentText()]
        self.entry2.setText(secrets.token_hex(size // 2))

    def _resolve_key(self):
        """Return the key bytes for the current settings, or None (dialog shown).

        The old check was `len(key) < blocksize / 8`, a lower bound on a value
        that is really the *key* length: a 24-character key with "128" selected
        silently ran AES-192, so the peer could not decrypt it.
        """
        key = self.entry2.text()
        expected = KEY_SIZES[self.blocksize_box.currentText()]
        key_bytes = key.encode("utf-8")
        if len(key_bytes) not in (16, 24, 32):
            show_error(
                self.root, "Error",
                f"The key must be 16, 24 or 32 characters "
                f"({len(key_bytes)} given).",
            )
            return None
        if len(key_bytes) != expected:
            show_error(
                self.root, "Error",
                f"Key size {self.blocksize_box.currentText()} selected, but the "
                f"key is {len(key_bytes) * 8} bits.",
            )
            return None
        return key_bytes

    def _build_cipher(self):
        """Return an AES cipher for the current settings, or None (dialog shown)."""
        key = self._resolve_key()
        if key is None:
            return None
        mode = self.mode_box.currentText()
        if mode == "CBC":
            iv = self.entry3.text()
            if len(iv.encode("utf-8")) != 16:
                show_error(self.root, "Error", "The offset length must be 16 bits.")
                return None
            return AES.new(key, AES.MODE_CBC, iv=iv.encode("utf-8"))
        return AES.new(key, AES.MODE_ECB)

    @staticmethod
    def _decode_b64(ciphertext):
        """Decode base64, refusing input that is not really base64.

        ``b64decode`` without ``validate=True`` just drops characters it does
        not recognise, so "aGVsbG8=@@@" decoded to "hello" and typo'd or
        truncated ciphertext silently produced a wrong plaintext.
        """
        compact = b"".join(ciphertext.encode("utf-8").split())
        return base64.b64decode(compact, validate=True)

    # 加密函数
    def encrypt(self):
        try:
            plaintext = self.entry1.toPlainText().encode("utf-8")
            padding = self.padding_box.currentText()
            cipher = self._build_cipher()
            if cipher is None:
                return

            if padding == "pkcs7":
                plaintext = pad(plaintext, AES.block_size)
            elif padding == "iso7816":
                plaintext = pad(plaintext, AES.block_size, "iso7816")
            elif padding == "x923":
                plaintext = pad(plaintext, AES.block_size, "x923")

            ciphertext = base64.b64encode(cipher.encrypt(plaintext)).decode()
            self.text.setPlainText(ciphertext)
        except Exception as e:
            self.text.clear()
            show_error(self.root, "error", str(e))

    # 解密函数
    def decrypt(self):
        try:
            ciphertext = self._decode_b64(self.entry1.toPlainText())
            padding = self.padding_box.currentText()
            cipher = self._build_cipher()
            if cipher is None:
                return

            plaintext = cipher.decrypt(ciphertext)

            if padding == "pkcs7":
                plaintext = unpad(plaintext, AES.block_size)
            elif padding == "iso7816":
                plaintext = unpad(plaintext, AES.block_size, "iso7816")
            elif padding == "x923":
                plaintext = unpad(plaintext, AES.block_size, "x923")

            self.text.setPlainText(plaintext.decode("utf-8"))
        except Exception as e:
            self.text.clear()
            show_error(self.root, "error", str(e))
