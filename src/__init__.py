import os
import sys

# This project targets Python 3.11+.  The check is deliberately early: several
# modules rely on 3.10/3.11-only stdlib behaviour (``sys.stdlib_module_names``,
# the re module's atomic grouping), and on an older interpreter those failures
# surface as obscure AttributeError/ImportError deep inside a Qt slot rather
# than as an actionable message.
if sys.version_info < (3, 11):
    raise RuntimeError(
        "ApiTest requires Python 3.11 or newer; this interpreter is "
        f"{sys.version.split()[0]} ({sys.executable})."
    )

USER_DIR = os.path.expanduser("~")
WORK_DIR = os.path.join(USER_DIR, ".config", "apitest")
BASE_DIR = os.path.dirname(os.path.dirname(__file__))

# Single place for the version, so the About pane cannot drift from the
# packaged metadata in pyproject.toml.
__version__ = "1.0.0"

if not os.path.exists(WORK_DIR):
    os.makedirs(WORK_DIR, exist_ok=True)
