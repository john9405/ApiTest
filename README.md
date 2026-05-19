# Pigeon

Pigeon is a desktop HTTP API testing tool built with Tkinter.

It provides a request editor, collection management, environment variables, request history, OAuth 1.0 support, pre-request and post-response scripts, and a group of small built-in utility tools.

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
- Built-in script editor with Python syntax highlighting and simple completion
- Built-in utility tools: AES, Base64, MD5, password generator, regex tools, RSA tools, timestamp tool, and draft paper

## Screens

The main window is divided into two work areas:

- Left sidebar: collections, environments, history, and tool list
- Right side: request tabs and tool tabs

Request tabs support custom canvas-based tab switching, tab closing, and quick new-tab actions.

## Requirements

- Python 3
- Tkinter available in the Python runtime

Project dependencies are listed in [requirements.txt](requirements.txt).

## Install

```bash
pip install -r requirements.txt
```

## Run

```bash
python __main__.py
```

## Data Storage

Pigeon creates and uses a working directory under:

```text
~/Postman
```

This path is defined in [src/__init__.py](src/__init__.py).

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

## Scripting

Each request can define:

- Pre-request script
- Post-response script

Scripts are plain Python snippets executed inside the app. The editor includes:

- Python syntax highlighting
- Simple identifier completion
- Standard library completion

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

```bash
pip install pyinstaller
pip install cryptojwt
pyinstaller __main__.py -n ApiTest -w -y --hidden-import cryptojwt --clean --onefile
```

### py2app

```bash
pip install py2app
pip install cryptojwt
python setup.py py2app -A
```

`py2app` packaging is configured in [setup.py](setup.py).

## Project Structure

```text
.
|-- __main__.py
|-- requirements.txt
|-- setup.py
`-- src
    |-- main.py        # main window and tab layout
    |-- req.py         # request editor and request execution
    |-- col.py         # collections and folders
    |-- env.py         # environment variables
    |-- his.py         # request history
    |-- utils.py       # shared widgets and editor helpers
    |-- help.py
    |-- about.py
    |-- dao/           # sqlite initialization and CRUD helpers
    `-- tools/         # built-in utility tools
```

## Notes

- The UI is implemented with Tkinter and uses several custom canvas-based widgets.
- Some optional request/auth dependencies may need platform-specific native support depending on your environment.
- The repository may include a local `example.db` for development or testing data.

## License

This project is licensed under the terms of the [LICENSE](LICENSE) file.
