# Pinterest Downloader

**Guest-mode image downloader for Pinterest — no login, no cookies, no API key.**

Search by keyword, fetch the highest available resolution, download in parallel, skip duplicates, and resume interrupted sessions.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-1.0.0-brightgreen.svg)](pinterest_downloader.py)

---

## Features

| Feature | Description |
| --- | --- |
| Guest access | Works without Pinterest authentication |
| Keyword search | Download images for any search query |
| Best resolution | Prefers `orig` → `1200x` → `736x` and lower fallbacks |
| Parallel downloads | Configurable worker pool |
| Deduplication | SHA-256 content hashing plus pin-ID tracking |
| Resume support | Session state saved under the output directory |
| Resolution filter | Optional minimum width/height |
| Graceful interrupt | Ctrl+C stops cleanly and preserves progress |
| Version flag | `-v` / `--version` |

---

## Requirements

- Python **3.9+**
- Dependencies listed in [`requirements.txt`](requirements.txt):
  - `requests`
  - `Pillow`

---

## Installation

```bash
git clone https://github.com/MrHacker-X/pinterest-downloader.git
cd pinterest-downloader

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

---

## Quick start

Interactive mode:

```bash
python pinterest_downloader.py
```

Non-interactive:

```bash
python pinterest_downloader.py -q "nature wallpaper" -n 100
```

Show version:

```bash
python pinterest_downloader.py -v
# or
python pinterest_downloader.py --version
```

---

## Usage

```text
usage: pinterest_downloader.py [-h] [-q QUERY] [-n COUNT] [-o OUTPUT]
                               [--workers WORKERS] [--min-res MIN_RES]
                               [--page-size PAGE_SIZE] [--delay DELAY]
                               [-v]
```

### Options

| Option | Description | Default |
| --- | --- | --- |
| `-q`, `--query` | Search keyword | prompt |
| `-n`, `--count` | Number of **new** images to download | prompt |
| `-o`, `--output` | Output directory | `downloads/<query>` |
| `--workers` | Parallel download threads | `6` |
| `--min-res` | Minimum width **and** height (pixels) | `0` (any) |
| `--page-size` | Pins requested per search page | `25` |
| `--delay` | Seconds to wait between search pages | `1.0` |
| `-v`, `--version` | Print version and exit | — |
| `-h`, `--help` | Show help | — |

### Examples

```bash
# Basic download
python pinterest_downloader.py -q "dark aesthetics" -n 200 -o ./images

# High-resolution only, more workers
python pinterest_downloader.py -q "cars" -n 100 --min-res 1080 --workers 8

# Slower paging (gentler on the network)
python pinterest_downloader.py -q "architecture" -n 50 --delay 2.0
```

---

## How it works

1. Queries Pinterest’s public guest search resource (no account required).
2. Walks paginated results using bookmarks until the target count is met or results end.
3. Selects the best image URL available for each pin.
4. Downloads with a thread pool, verifies image data with Pillow, and writes atomically (`.part` → final file).
5. Records pin IDs and content hashes in `.download_session.json` so re-runs skip duplicates and can resume.

### Output layout

```text
downloads/
└── nature_wallpaper/
    ├── pin_123456789.jpg
    ├── pin_987654321.png
    └── .download_session.json
```

---

## Interrupting and resuming

Press **Ctrl+C** once to stop gracefully:

- In-flight workers are signalled to stop
- Session state is saved
- Re-running the same query and output directory resumes from saved progress

Press **Ctrl+C** a second time to force an immediate exit.

---

## Project structure

```text
pinterest-downloader/
├── pinterest_downloader.py   # Main CLI application
├── requirements.txt          # Runtime dependencies
├── LICENSE                   # MIT
├── README.md
├── CONTRIBUTING.md
└── .gitignore
```

---

## Contributing

Contributions are welcome. Please read [`CONTRIBUTING.md`](CONTRIBUTING.md) before opening an issue or pull request.

---

## Disclaimer

This project is provided for educational and personal use. You are responsible for complying with [Pinterest’s Terms of Service](https://policy.pinterest.com/terms-of-service), copyright law, and any applicable regulations. The authors are not liable for misuse.

Downloaded images remain the property of their respective rights holders.

---

## License

This project is licensed under the [MIT License](LICENSE).

```text
Copyright (c) 2026 MrHacker-X
```

---

## Author

**MrHacker-X**

- GitHub: [https://github.com/MrHacker-X](https://github.com/MrHacker-X)
- Repository: [https://github.com/MrHacker-X/pinterest-downloader](https://github.com/MrHacker-X/pinterest-downloader)
