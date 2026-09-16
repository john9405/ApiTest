# Pigeon

Pigeon is a desktop HTTP API testing tool built with PyQt5.

It provides a request editor, collection management, environment variables, request history, OAuth 1.0 support, pre-request and post-response scripts, a visual flow runner, and a group of small built-in utility tools.

## Features

- Send `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `HEAD`, and `OPTIONS` requests
- Organize requests in collections, folders, and projects
- Import and export collections as JSON
- Manage environments and global variables
- View request history and reopen past requests
- Support `No Auth`, `Basic`, `Digest`, and `OAuth 1.0`
- Edit request bodies as `none`, `urlencoded`, or `raw`
- Raw body presets: `Text`, `JSON`, `XML`, `HTML`
- Run pre-request and post-response scripts
- Inspect response body, cookies, headers, and console output
- Preview an HTML response in a built-in browser window
- Build and run request flows from a node canvas
- Built-in script editor with Python syntax highlighting and simple completion
- Built-in utility tools: AES, Base64, MD5, password generator, regex tools, RSA tools, timestamp tool, and draft paper

## Screens

The main window is divided into two work areas:

- Left sidebar (`QToolBox`): collections, history, environments, flows, and tools
- Right side: request tabs, flow editor tabs, and tool tabs

Request tabs support custom tab switching, tab closing, and quick new-tab actions.

## Requirements

- Python 3.11 or newer
- PyQt5

The interpreter floor is enforced at import time in [src/__init__.py](src/__init__.py), so an older Python fails with an explicit message instead of an obscure error inside a Qt callback.

Project dependencies are listed in [requirements.txt](requirements.txt) and declared in [pyproject.toml](pyproject.toml).

## Install

The project is developed against the `~/Base` virtual environment, which is a Python 3.11 environment:

```bash
~/Base/bin/python -m pip install -r requirements.txt
```

Or, with the environment activated:

```bash
source ~/Base/bin/activate
pip install -r requirements.txt
```

[requirements-optional.txt](requirements-optional.txt) holds the Kerberos and NTLM auth back ends. Nothing in the code imports them today, and both need native Kerberos/NTLM libraries, so they are not installed by default.

## Run

```bash
~/Base/bin/python __main__.py
```

With the environment activated, `python __main__.py` works the same way.

## Data Storage

Pigeon creates and uses a working directory under:

```text
~/.config/apitest
```

This path is defined in [src/__init__.py](src/__init__.py). It holds:

- `example.db` — the SQLite database with collections, environments, history, and flows
- `error.log` — tracebacks from unhandled exceptions in the UI thread

## Authentication Support

Pigeon currently supports:

- No Auth
- HTTP Basic Auth
- HTTP Digest Auth
- OAuth 1.0

OAuth 1.0 supports:

- HMAC-SHA1
- HMAC-SHA256
- HMAC-SHA512
- RSA-SHA1
- RSA-SHA256
- RSA-SHA512
- PLAINTEXT

Signature placement can be `auth_header`, `query`, or `body`.

## Scripting

Each request can define:

- Pre-request script
- Post-response script

Scripts are plain Python snippets executed inside the app. A pre-request script sees `req` (with `body`, `headers`, `url`), and a post-response script sees `res`, the `requests` response object. Both also get `globals`, `collectionVariables`, `environment`, and `console`.

The editor includes:

- Python syntax highlighting
- Standard library completion read from the running interpreter: module names
  come from `sys.stdlib_module_names` plus installed packages, and members come
  from the modules themselves, so a suggestion is never something the
  interpreter does not have
- Imports written in the buffer are honoured, aliases included: `import os as o`
  completes `o.path`, `import xml.etree.ElementTree as ET` completes `ET.parse`,
  and `from datetime import datetime` completes the *class* named `datetime`
  rather than the module of the same name
- Module completion after `import` / `from` (including installed packages),
  submodules of a package (`import xml.` → `etree`, `import urllib.` → `parse`,
  and `import os.pa` → `path`, for modules exposed as attributes rather than
  package files), and member completion (`os.pa` → `path`,
  `from os import pa` → `path`)
- Suggestions are ranked by the module's own public API (`__all__`), so internals
  such as the modules a stdlib module imported for its own use do not crowd out
  the names being looked for; matching ignores case, and each suggestion carries
  its signature and docstring as a tooltip
- `Tab` / `Enter` accepts a suggestion; `Esc` dismisses the list until the next
  keystroke

> Scripts run with the full interpreter; they are not sandboxed.

## HTML Response Preview

When a response is an HTML document, the response `Body` tab shows a `预览` (Preview) button above the source view. Clicking it renders the page in a separate, non-modal window, which is reused for later previews of the same request. The button stays hidden for every other response type, and an open preview closes when a new, non-HTML response arrives, so what is on screen always matches the response being inspected.

The `Body` tab keeps showing the indented source; the preview renders the original text, since re-indenting can change how whitespace-sensitive markup such as `<pre>` is displayed.

Rendering uses the best back end available:

| Back end | Provided by | Capability |
| --- | --- | --- |
| `webengine` | `PyQtWebEngine` | QtWebEngine (Chromium): full HTML, CSS, and JavaScript |
| `webkit` | a Qt build that still ships QtWebKit | the legacy `QWebView` |
| `textbrowser` | PyQt5 itself | Qt's rich-text engine: HTML/CSS subset, no JavaScript |

QtWebKit was removed from Qt in 5.6 and no PyQt5 wheel provides `QWebView`, so a plain PyQt5 environment uses the `textbrowser` back end. It renders static pages and says so in the window; install the optional Chromium-based back end for complete rendering:

```bash
~/Base/bin/python -m pip install PyQtWebEngine
```

This is a large download — it pulls the Qt WebEngine libraries — so it is deliberately not a runtime dependency, and it grows the PyInstaller bundle considerably. The back end is chosen when the module is imported, and the choice is reported in the Preview button's tooltip.

Relative links and images resolve against the response URL, and clicking a link opens it in the system browser instead of navigating the preview away from the response.

## Flows

The Flows section opens a node canvas for building request pipelines. Available node types are `api_request`, `condition`, `script`, `delay`, `log`, and `data_transform`. A flow runs on a background thread and reports progress on the canvas and in the flow console.

## Built-in Tools

The tool page in the left sidebar can open:

- AES
- Base64
- DraftPaper
- MD5
- Password Generator
- Regular Expression
- Regular Expression Example
- RSA Key
- RSA Public Key
- RSA Check
- RSA Encrypt
- RSA Decrypt
- Timestamp

## Package As Application

### PyInstaller

PyInstaller is not a runtime dependency; install it into the environment you build with.

```bash
~/Base/bin/python -m pip install pyinstaller
~/Base/bin/python -m PyInstaller ApiTest.spec --noconfirm --clean
```

[ApiTest.spec](ApiTest.spec) drives the build and writes the bundle to `dist/`. Build with the Python 3.11 environment so the shipped interpreter matches the one the project targets.

> If `dist/` already contains a bundle, check the interpreter it was built with before shipping it — a bundle built by an older Python keeps that older interpreter and its standard library.

## Project Structure

```text
.
|-- __main__.py            # entry point, Qt app boot, global exception hook
|-- pyproject.toml
|-- requirements.txt
|-- requirements-optional.txt
|-- ApiTest.spec           # PyInstaller build spec
`-- src
    |-- __init__.py        # paths, Python version floor
    |-- main.py            # main window and tab layout
    |-- req.py             # request editor and request execution
    |-- col.py             # collections and folders
    |-- env.py             # environment variables
    |-- his.py             # request history
    |-- utils.py           # shared widgets, code editor, console
    |-- qui.py             # Qt widgets exposing the legacy Tk-style API
    |-- webview.py         # rendered HTML preview window and its back ends
    |-- theme.py           # stylesheet and role-based widget styling
    |-- help.py
    |-- about.py
    |-- dao/               # sqlite initialization and CRUD helpers
    |-- flow/              # flow model, engine, canvas editor, node types
    `-- tools/             # built-in utility tools
```

## Notes

- The UI is implemented with PyQt5 and uses several custom canvas-based widgets.
- `src/qui.py` is a compatibility layer: it wraps Qt widgets in the small Tkinter/ttk API subset (`.bind()`, `.after()`, `TreeView`, `Canvas`) that the older modules were written against. New code should use Qt directly.
- Some optional request/auth dependencies may need platform-specific native support depending on your environment.
- The database lives outside the repository, at `~/.config/apitest/example.db`.

## License

This project is licensed under the terms of the [LICENSE](LICENSE) file.
