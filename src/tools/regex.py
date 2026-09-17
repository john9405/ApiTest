import re
import signal
import tempfile
import threading
import webbrowser
from html import escape
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFontDatabase, QGuiApplication
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QCheckBox,
    QPlainTextEdit,
    QGroupBox,
    QPushButton,
    QTextBrowser,
)

from ..qui import show_error
from ..theme import style_role

# A pathological pattern (nested quantifiers such as ``(a+)+b``) backtracks
# exponentially — measured at ~0.8 s for 23 input characters, doubling per
# character — so a single Search click could freeze the whole application with
# no way to recover.
#
# Moving the scan to a worker thread does NOT help: the re module's C loop
# holds the GIL for the whole match, and a measured 2-second catastrophic
# match left the main thread with zero time slices.  CPython's matcher does
# poll for pending signals, so a SIGALRM deadline unwinds it instead (verified
# to break the loop at the requested moment).  ``signal.setitimer`` and
# ``SIGALRM`` are POSIX-only and may only be installed from the main thread, so
# the deadline is applied only where that holds and the scan simply runs
# uninterrupted elsewhere.
SEARCH_TIMEOUT_SECONDS = 3.0


class _SearchTimeout(Exception):
    """Raised by the SIGALRM handler to abandon an over-long match."""


def _search(pattern, text):
    """Return [f"Match: {m}", ...] for `pattern`, with a wall-clock deadline."""
    use_deadline = (
        hasattr(signal, "SIGALRM")
        and hasattr(signal, "setitimer")
        and threading.current_thread() is threading.main_thread()
    )
    if not use_deadline:
        return [f"Match: {item}" for item in pattern.finditer(text)]

    def _on_alarm(signum, frame):
        raise _SearchTimeout()

    previous = signal.signal(signal.SIGALRM, _on_alarm)
    signal.setitimer(signal.ITIMER_REAL, SEARCH_TIMEOUT_SECONDS)
    try:
        return [f"Match: {item}" for item in pattern.finditer(text)]
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


class RegexWindow:
    def __init__(self, master=None) -> None:
        # 创建主窗口
        self.root = QWidget(master)
        outer = QVBoxLayout(self.root)
        outer.setContentsMargins(5, 5, 5, 5)

        options_frame = QWidget(self.root)
        options = QHBoxLayout(options_frame)
        options.setContentsMargins(0, 0, 0, 4)

        options.addWidget(QLabel("Expression:", options_frame))
        regex_entry = QLineEdit(options_frame)
        options.addWidget(regex_entry, 1)

        self.ignore_case_var = QCheckBox("Ignore case", options_frame)
        options.addWidget(self.ignore_case_var)
        self.multi_line_var = QCheckBox("Multiline", options_frame)
        options.addWidget(self.multi_line_var)

        find_button = QPushButton("Search", options_frame)
        style_role(find_button, "primary")
        find_button.clicked.connect(self.find_matches)
        options.addWidget(find_button)

        outer.addWidget(options_frame)

        text_group = QGroupBox("Input:", self.root)
        text_lay = QVBoxLayout(text_group)
        self.text_entry = QPlainTextEdit(text_group)
        self.text_entry.setMinimumHeight(120)
        text_lay.addWidget(self.text_entry)
        outer.addWidget(text_group, 1)

        result_group = QGroupBox("Output:", self.root)
        result_lay = QVBoxLayout(result_group)
        self.result_text = QPlainTextEdit(result_group)
        self.result_text.setMinimumHeight(120)
        result_lay.addWidget(self.result_text)
        outer.addWidget(result_group, 1)

        self.regex_entry = regex_entry

    def find_matches(self):
        regex = self.regex_entry.text()
        text = self.text_entry.toPlainText()
        flags = 0
        if self.ignore_case_var.isChecked():
            flags |= re.IGNORECASE
        if self.multi_line_var.isChecked():
            flags |= re.MULTILINE

        try:
            pattern = re.compile(regex, flags)
        except re.error as e:
            self.result_text.setPlainText(f"Error: {e}")
            return

        try:
            matches = _search(pattern, text)
        except _SearchTimeout:
            self.result_text.setPlainText(
                f"Error: no result within {SEARCH_TIMEOUT_SECONDS:g}s — the pattern "
                "is probably backtracking catastrophically."
            )
            return
        except Exception as e:  # noqa: BLE001
            self.result_text.setPlainText(f"Error: {e}")
            return

        self.result_text.clear()
        if not matches:
            self.result_text.setPlainText("No matches found.\n")
            return
        for line in matches:
            self.result_text.appendPlainText(line)


# ---------------------------------------------------------------------------
# Commonly used expressions, shown as a rendered HTML page
# ---------------------------------------------------------------------------

# The reference text stays the source of truth: it is what the tab showed
# before, and the page below is generated from it rather than hand-copied, so
# no expression can be lost or misspelled in translation.
COMMON_REGEX_TEXT = r"""常用正则表达式
一、校验数字的表达式
数字：^[0-9]*$
n位的数字：^\d{n}$
至少n位的数字：^\d{n,}$
m-n位的数字：^\d{m,n}$
零和非零开头的数字：^(0|[1-9][0-9]*)$
非零开头的最多带两位小数的数字：^([1-9][0-9]*)+(\.[0-9]{1,2})?$
带1-2位小数的正数或负数：^(\-)?\d+(\.\d{1,2})$
正数、负数、和小数：^(\-|\+)?\d+(\.\d+)?$
有两位小数的正实数：^[0-9]+(\.[0-9]{2})?$
有1~3位小数的正实数：^[0-9]+(\.[0-9]{1,3})?$
非零的正整数：^[1-9]\d*$ 或 ^([1-9][0-9]*){1,3}$ 或 ^\+?[1-9][0-9]*$
非零的负整数：^\-[1-9][]0-9"*$ 或 ^-[1-9]\d*$
非负整数：^\d+$ 或 ^[1-9]\d*|0$
非正整数：^-[1-9]\d*|0$ 或 ^((-\d+)|(0+))$
非负浮点数：^\d+(\.\d+)?$ 或 ^[1-9]\d*\.\d*|0\.\d*[1-9]\d*|0?\.0+|0$
非正浮点数：^((-\d+(\.\d+)?)|(0+(\.0+)?))$ 或 ^(-([1-9]\d*\.\d*|0\.\d*[1-9]\d*))|0?\.0+|0$
正浮点数：^[1-9]\d*\.\d*|0\.\d*[1-9]\d*$ 或 ^(([0-9]+\.[0-9]*[1-9][0-9]*)|([0-9]*[1-9][0-9]*\.[0-9]+)|([0-9]*[1-9][0-9]*))$
负浮点数：^-([1-9]\d*\.\d*|0\.\d*[1-9]\d*)$ 或 ^(-(([0-9]+\.[0-9]*[1-9][0-9]*)|([0-9]*[1-9][0-9]*\.[0-9]+)|([0-9]*[1-9][0-9]*)))$
浮点数：^(-?\d+)(\.\d+)?$ 或 ^-?([1-9]\d*\.\d*|0\.\d*[1-9]\d*|0?\.0+|0)$
校验字符的表达式
汉字：^[\u4e00-\u9fa5]{0,}$
英文和数字：^[A-Za-z0-9]+$ 或 ^[A-Za-z0-9]{4,40}$
长度为3-20的所有字符：^.{3,20}$
由26个英文字母组成的字符串：^[A-Za-z]+$
由26个大写英文字母组成的字符串：^[A-Z]+$
由26个小写英文字母组成的字符串：^[a-z]+$
由数字和26个英文字母组成的字符串：^[A-Za-z0-9]+$
由数字、26个英文字母或者下划线组成的字符串：^\w+$ 或 ^\w{3,20}$
中文、英文、数字包括下划线：^[\u4E00-\u9FA5A-Za-z0-9_]+$
中文、英文、数字但不包括下划线等符号：^[\u4E00-\u9FA5A-Za-z0-9]+$ 或 ^[\u4E00-\u9FA5A-Za-z0-9]{2,20}$
可以输入含有^%&',;=?$\"等字符：[^%&',;=?$\x22]+
禁止输入含有~的字符：[^~]+
三、特殊需求表达式
Email地址：^\w+([-+.]\w+)*@\w+([-.]\w+)*\.\w+([-.]\w+)*$
域名：[a-zA-Z0-9][-a-zA-Z0-9]{0,62}(\.[a-zA-Z0-9][-a-zA-Z0-9]{0,62})+\.?
InternetURL：[a-zA-z]+://[^\s]* 或 ^http://([\w-]+\.)+[\w-]+(/[\w-./?%&=]*)?$
手机号码：^(13[0-9]|14[01456879]|15[0-35-9]|16[2567]|17[0-8]|18[0-9]|19[0-35-9])\d{8}$
电话号码("XXX-XXXXXXX"、"XXXX-XXXXXXXX"、"XXX-XXXXXXX"、"XXX-XXXXXXXX"、"XXXXXXX"和"XXXXXXXX)：^(\(\d{3,4}-)|\d{3.4}-)?\d{7,8}$
国内电话号码(0511-4405222、021-87888822)：\d{3}-\d{8}|\d{4}-\d{7}
电话号码正则表达式（支持手机号码，3-4位区号，7-8位直播号码，1－4位分机号）: ((\d{11})|^((\d{7,8})|(\d{4}|\d{3})-(\d{7,8})|(\d{4}|\d{3})-(\d{7,8})-(\d{4}|\d{3}|\d{2}|\d{1})|(\d{7,8})-(\d{4}|\d{3}|\d{2}|\d{1}))$)
身份证号(15位、18位数字)，最后一位是校验位，可能为数字或字符X：(^\d{15}$)|(^\d{18}$)|(^\d{17}(\d|X|x)$)
帐号是否合法(字母开头，允许5-16字节，允许字母数字下划线)：^[a-zA-Z][a-zA-Z0-9_]{4,15}$
密码(以字母开头，长度在6~18之间，只能包含字母、数字和下划线)：^[a-zA-Z]\w{5,17}$
强密码(必须包含大小写字母和数字的组合，不能使用特殊字符，长度在 8-10 之间)：^(?=.*\d)(?=.*[a-z])(?=.*[A-Z])[a-zA-Z0-9]{8,10}$
强密码(必须包含大小写字母和数字的组合，可以使用特殊字符，长度在8-10之间)：^(?=.*\d)(?=.*[a-z])(?=.*[A-Z]).{8,10}$
日期格式：^\d{4}-\d{1,2}-\d{1,2}
一年的12个月(01～09和1～12)：^(0?[1-9]|1[0-2])$
一个月的31天(01～09和1～31)：^((0?[1-9])|((1|2)[0-9])|30|31)$
钱的输入格式：
有四种钱的表示形式我们可以接受:"10000.00" 和 "10,000.00", 和没有 "分" 的 "10000" 和 "10,000"：^[1-9][0-9]*$
这表示任意一个不以0开头的数字,但是,这也意味着一个字符"0"不通过,所以我们采用下面的形式：^(0|[1-9][0-9]*)$
一个0或者一个不以0开头的数字.我们还可以允许开头有一个负号：^(0|-?[1-9][0-9]*)$
这表示一个0或者一个可能为负的开头不为0的数字.让用户以0开头好了.把负号的也去掉,因为钱总不能是负的吧。下面我们要加的是说明可能的小数部分：^[0-9]+(.[0-9]+)?$
必须说明的是,小数点后面至少应该有1位数,所以"10."是不通过的,但是 "10" 和 "10.2" 是通过的：^[0-9]+(.[0-9]{2})?$
这样我们规定小数点后面必须有两位,如果你认为太苛刻了,可以这样：^[0-9]+(.[0-9]{1,2})?$
这样就允许用户只写一位小数.下面我们该考虑数字中的逗号了,我们可以这样：^[0-9]{1,3}(,[0-9]{3})*(.[0-9]{1,2})?$
1到3个数字,后面跟着任意个 逗号+3个数字,逗号成为可选,而不是必须：^([0-9]+|[0-9]{1,3}(,[0-9]{3})*)(.[0-9]{1,2})?$
备注：这就是最终结果了,别忘了"+"可以用"*"替代如果你觉得空字符串也可以接受的话(奇怪,为什么?)最后,别忘了在用函数时去掉去掉那个反斜杠,一般的错误都在这里
xml文件：^([a-zA-Z]+-?)+[a-zA-Z0-9]+\.[x|X][m|M][l|L]$
中文字符的正则表达式：[\u4e00-\u9fa5]
双字节字符：[^\x00-\xff] (包括汉字在内，可以用来计算字符串的长度(一个双字节字符长度计2，ASCII字符计1))
空白行的正则表达式：\n\s*\r (可以用来删除空白行)
HTML标记的正则表达式：<(\S*?)[^>]*>.*?|<.*? />
首尾空白字符的正则表达式：^\s*|\s*$ 或 (^\s*)|(\s*$) (可以用来删除行首行尾的空白字符(包括空格、制表符、换页符等等)，非常有用的表达式)
腾讯QQ号：[1-9][0-9]{4,} (腾讯QQ号从10000开始)
中国邮政编码：[1-9]\d{5}(?!\d) (中国邮政编码为6位数字)
IPv4地址：((2(5[0-5]|[0-4]\d))|[0-1]?\d{1,2})(\.((2(5[0-5]|[0-4]\d))|[0-1]?\d{1,2})){3}"""

# Expressions that are really a sentence with an expression glued on the end
# ("备注：这就是最终结果了…") carry nothing to copy; they become page notes.
_NOTE_NAMES = {"备注"}

# One line often offers several spellings of the same expression.
_ALTERNATIVE_RE = re.compile(r"\s+或\s+")


def _is_balanced(text):
    """True when every '(' in `text` is closed, in order."""
    depth = 0
    for char in text:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def _trailing_note(body):
    """Split a trailing '(...)' remark off an expression body.

    A greedy ``\\s+\\((.*)\\)$`` gets this wrong twice over: the remark is not
    always the outermost group (``双字节字符：[^\\x00-\\xff] (包括…(一个双字节
    字符长度计2，ASCII字符计1))``) and an expression may itself contain a
    space before a group (``首尾空白字符的正则表达式：^\\s*|\\s*$ 或 (^\\s*)|(\\s*$)
    (可以用来…）``), which the greedy form swallowed into the note.  The
    rightmost *balanced* group is taken instead, and the remark is only
    stripped when the text after it is balanced — i.e. when it really is a
    remark and not the tail of an expression.
    """
    for match in reversed(list(re.finditer(r"\s+\(", body))):
        tail = body[match.start() + 1 :]
        if tail.endswith(")") and _is_balanced(tail):
            return body[: match.start()].strip(), tail[1:-1].strip()
    return body.strip(), ""


def _split_head(line):
    """Return (name, body) for a '名称：正则' line, or None for a heading.

    The full-width colon is searched over the whole line before the half-width
    one: in ``有四种钱的表示形式我们可以接受:"10000.00" 和 "10,000.00"…：^[1-9][0-9]*$``
    a left-to-right search for either colon would cut the line at the colon
    inside the prose (position 15) instead of the real separator (position 70).
    """
    for separator in ("：", ":"):
        index = line.find(separator)
        if index >= 0:
            name, body = line[:index].strip(), line[index + 1 :].strip()
            return (name, body) if body else None
    return None


def parse_common_regexes(text=COMMON_REGEX_TEXT):
    """Group the reference text into sections of copyable expressions.

    Returns ``[{"title": str, "items": [{"name", "patterns", "note"}], "notes": [str]}, ...]``.
    """
    sections = []
    current = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        head = _split_head(line)
        if head is None:
            # A heading: the document title, "一、校验数字的表达式", or
            # "钱的输入格式：" (a heading whose colon is followed by nothing).
            current = {"title": line, "items": [], "notes": []}
            sections.append(current)
            continue
        if current is None:
            current = {"title": "", "items": [], "notes": []}
            sections.append(current)
        name, body = head
        if name in _NOTE_NAMES:
            current["notes"].append(body)
            continue
        body, note = _trailing_note(body)
        patterns = [part for part in (p.strip() for p in _ALTERNATIVE_RE.split(body)) if part]
        current["items"].append({"name": name, "patterns": patterns, "note": note})
    return sections


# ---------------------------------------------------------------------------
# Building the page
# ---------------------------------------------------------------------------
# The page is rendered by Qt's rich-text engine in the tab (and by a real
# browser on request), so the markup sticks to what both understand: tables,
# bgcolor, inline styles and anchors.  No JavaScript is needed in the tab —
# a copy button is an ordinary `copy:<index>` link whose click is handled in
# Python, which is what makes the buttons work without a Chromium backend.
def _mono_style(for_browser):
    """A monospace style for one expression.

    The two renderers want different things: a browser resolves font fallbacks
    itself, while Qt treats an unknown family as a request to populate its font
    aliases — measured at ~1 s on macOS for "Consolas" or even the generic
    "Monospace" — so the page rendered in the tab names the platform's real
    fixed font instead.
    """
    if for_browser:
        return "font-family:Menlo,Consolas,'Courier New',monospace;"
    # No QApplication (the page can be built without one) means no font
    # database, and an empty family would emit a useless `font-family:'';`.
    family = QFontDatabase.systemFont(QFontDatabase.FixedFont).family()
    return f"font-family:'{family}';" if family else ""


_CHIP = (
    "text-decoration:none; color:#0a5ad6; background-color:#e8f0fe;"
    "white-space:nowrap;"
)
_MUTED = "color:#57606a;"
# Only the header row carries a background.  Qt's rich-text engine applies a
# background to the block it is written on and not to nested inline tags — a
# background on a cell or a `<div>` disappears behind a `<b>`, verified against
# the document's fragment formats — so a shaded description column rendered as
# a highlighter smear in the tab while looking like a full column in a browser.
_HEAD_BG = "#eef1f4"


def _copy_link(index, pattern, for_browser):
    """A '复制' chip for one expression, as a link the Python side intercepts."""
    if for_browser:
        # In a browser there is no Python to catch the click, so the same
        # anchor carries a JS handler; `copy:` stays as a harmless fallback.
        return (
            f'<a href="copy:{index}" data-pattern="{escape(pattern, quote=True)}"'
            f' onclick="copyPattern(this); return false;" style="{_CHIP}">&nbsp;复制&nbsp;</a>'
        )
    return f'<a href="copy:{index}" style="{_CHIP}">&nbsp;复制&nbsp;</a>'


_BROWSER_SCRIPT = """
<script>
function copyPattern(el) {
  var text = el.getAttribute('data-pattern');
  var done = function () {
    el.textContent = '已复制';
    setTimeout(function () { el.textContent = '复制'; }, 1200);
  };
  var legacy = function () {
    var area = document.createElement('textarea');
    area.value = text;
    area.setAttribute('readonly', '');
    area.style.position = 'fixed';
    area.style.top = '-1000px';
    document.body.appendChild(area);
    area.select();
    var ok = false;
    // file:// pages are not a secure context everywhere, so the clipboard API
    // is not always available and the old selection trick is the fallback.
    try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
    document.body.removeChild(area);
    el.textContent = ok ? '已复制' : '复制失败';
    setTimeout(function () { el.textContent = '复制'; }, 1200);
  };
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(done, legacy);
  } else {
    legacy();
  }
}
</script>
"""


def build_common_regex_page(for_browser=False):
    """Return ``(html, patterns)``: the reference page, and its expressions.

    ``patterns[i]`` is the text copied by the ``copy:i`` link, which keeps
    long or quote-laden expressions out of the href.
    """
    sections = parse_common_regexes()
    patterns = []
    mono = _mono_style(for_browser)

    # The first block is the document title ("常用正则表达式") — a heading with
    # nothing under it — and becomes the page heading rather than a section.
    title = "常用正则表达式"
    if sections and not sections[0]["items"] and not sections[0]["notes"]:
        title = sections[0]["title"] or title

    blocks = [
        f'<div style="font-size:18px; font-weight:bold; color:#1f2328;">{escape(title)}</div>'
    ]
    body = []
    for section in sections:
        if not section["items"] and not section["notes"]:
            continue
        heading = section["title"].rstrip("：:").strip()
        body.append(
            f'<div style="font-size:15px; font-weight:bold; color:#1f2328;'
            f' margin-top:18px; margin-bottom:6px;">{escape(heading)}</div>'
        )
        rows = [
            f'<tr bgcolor="{_HEAD_BG}">'
            f'<td width="34%"><div style="background-color:{_HEAD_BG}; {_MUTED}">说明</div></td>'
            f'<td><div style="background-color:{_HEAD_BG}; {_MUTED}">正则表达式</div></td></tr>'
        ]
        for item in section["items"]:
            cells = []
            for pattern in item["patterns"]:
                index = len(patterns)
                patterns.append(pattern)
                cells.append(
                    f'<div style="{mono} font-size:12px; margin-bottom:2px;">'
                    f"{escape(pattern)}&nbsp;&nbsp;{_copy_link(index, pattern, for_browser)}</div>"
                )
            name = escape(item["name"])
            note = f'<div style="{_MUTED} font-size:11px;">{escape(item["note"])}</div>' if item["note"] else ""
            rows.append(
                f'<tr><td width="34%"><div><b>{name}</b>{note}</div></td>'
                f'<td>{"".join(cells)}</td></tr>'
            )
        for note in section["notes"]:
            rows.append(
                f'<tr><td colspan="2"><div style="{_MUTED} font-size:12px;">{escape(note)}</div>'
                "</td></tr>"
            )
        body.append(
            '<table width="100%" cellspacing="0" cellpadding="6">' + "".join(rows) + "</table>"
        )

    blocks.append(
        f'<div style="{_MUTED} margin-bottom:10px;">共 {len(patterns)} 条表达式，'
        f"点击每条后面的“复制”即可复制该正则。</div>"
    )
    blocks.extend(body)

    if for_browser:
        # A standalone document: the browser needs the charset and the script.
        html = (
            "<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n"
            '<meta charset="utf-8">\n'
            f"<title>{escape(title)}</title>\n"
            f"{_BROWSER_SCRIPT}"
            "<style>body{max-width:1000px;margin:24px auto;padding:0 16px;"
            "font-family:-apple-system,'Helvetica Neue','PingFang SC','Microsoft YaHei',sans-serif;"
            "color:#1f2328;}table{border-collapse:collapse;}"
            "td{padding:6px 8px;vertical-align:top;}a:hover{background:#d3e3fd;}"
            "</style>\n</head>\n<body>\n"
            + "\n".join(blocks)
            + "\n</body>\n</html>\n"
        )
    else:
        html = "\n".join(blocks)
    return html, patterns


class CommonlyUsed:
    """Common regular expressions, shown as a rendered HTML page.

    Every expression is followed by a 复制 button.  The click is handled here
    (``copy:`` links, see :meth:`_on_anchor_clicked`) instead of in JavaScript so
    that the buttons work in Qt's rich-text engine too, where no script runs.
    """

    def __init__(self, master=None):
        self.root = QWidget(master)
        outer = QVBoxLayout(self.root)
        outer.setContentsMargins(5, 5, 5, 5)
        outer.setSpacing(4)

        # Kept: the page's copy links index into this list.
        html, self.patterns = build_common_regex_page()

        bar = QHBoxLayout()
        bar.addStretch(1)
        browser_button = QPushButton("在浏览器中打开", self.root)
        style_role(browser_button, "secondary")
        browser_button.setToolTip("把同一页面写入临时 HTML 文件，并用系统默认浏览器打开")
        browser_button.clicked.connect(self.open_in_browser)
        bar.addWidget(browser_button)
        outer.addLayout(bar)

        view = QTextBrowser(self.root)
        view.setReadOnly(True)
        # Both off: a `copy:` click must reach anchorClicked() instead of being
        # treated as navigation the view cannot perform.
        view.setOpenLinks(False)
        view.setOpenExternalLinks(False)
        view.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        view.anchorClicked.connect(self._on_anchor_clicked)
        view.setHtml(html)
        outer.addWidget(view, 1)

        self.view = view
        self.status = QLabel("", self.root)
        self.status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        outer.addWidget(self.status)

    # ------------------------------------------------------------------
    # Copy buttons
    # ------------------------------------------------------------------
    def _on_anchor_clicked(self, url):
        """Copy the expression behind a ``copy:<index>`` link."""
        if url.scheme() != "copy":
            if url.scheme() in ("http", "https"):
                webbrowser.open(url.toString())
            return
        try:
            index = int(url.path())
        except ValueError:
            return
        if not 0 <= index < len(self.patterns):
            return
        pattern = self.patterns[index]
        QGuiApplication.clipboard().setText(pattern)
        self.status.setText(f"已复制：{pattern}")

    # ------------------------------------------------------------------
    # Full-fidelity page in a real browser
    # ------------------------------------------------------------------
    def browser_page_path(self):
        """Write the browser edition of the page and return its path.

        The file is left on disk on purpose: the browser reads it after this
        call returns, so it cannot be removed here.  The name is unique per
        process, so repeated clicks do not collide with a page still loading.
        """
        html, _ = build_common_regex_page(for_browser=True)
        handle = tempfile.NamedTemporaryFile(
            "w", suffix=".html", prefix="apitest-common-regex-",
            delete=False, encoding="utf-8",
        )
        with handle:
            handle.write(html)
        return handle.name

    def open_in_browser(self):
        try:
            path = self.browser_page_path()
        except OSError as e:
            show_error(self.root, "Error", str(e))
            return
        webbrowser.open(Path(path).as_uri())
        self.status.setText(f"已在浏览器中打开：{path}")
