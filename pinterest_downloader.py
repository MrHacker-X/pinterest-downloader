#!/usr/bin/env python3
"""
Pinterest Guest Image Downloader
No login, no cookies, no API key.

Features:
- Keyword-based image search
- Highest available image resolution
- Pagination
- Multithreaded downloads
- Duplicate detection using SHA-256
- Resume support
- Minimum resolution filtering
- Graceful Ctrl+C interruption

Install:
    pip install -r requirements.txt

Usage:
    python pinterest_downloader.py
    python pinterest_downloader.py -q "nature wallpaper" -n 100
    python pinterest_downloader.py -q "dark aesthetics" -n 200 -o ./images
    python pinterest_downloader.py -q "cars" -n 100 --min-res 1080 --workers 8
    python pinterest_downloader.py -v
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import signal
import sys
import threading

from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from urllib.parse import quote

import requests
from PIL import Image, UnidentifiedImageError


__version__ = "1.0.0"
__author__ = "MrHacker-X"

SEARCH_URL = "https://www.pinterest.com/resource/BaseSearchResource/get/"
END_BOOKMARK = "-end-"
MAX_IMAGE_SIZE = 25 * 1024 * 1024

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*, q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
    "x-pinterest-pws-handler": "www/search/[scope].js",
    "x-pinterest-appstate": "active",
    "screen-density": "2",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s"
)

log = logging.getLogger("pinterest")


class PinterestGuestDownloader:

    def __init__(
        self,
        query,
        count,
        output=None,
        workers=6,
        min_res=0,
        page_size=25,
        delay=1.0
    ):
        self.query = query
        self.count = count
        self.workers = max(1, workers)
        self.min_res = max(0, min_res)
        self.page_size = max(1, page_size)
        self.delay = max(0, delay)

        self.output = output or os.path.join(
            "downloads",
            query.replace(" ", "_")
        )

        os.makedirs(self.output, exist_ok=True)

        self.state_file = os.path.join(
            self.output,
            ".download_session.json"
        )

        self.session = requests.Session()
        self.session.headers.update(HEADERS)

        search_path = f"/search/pins/?q={quote(query)}"

        self.session.headers.update({
            "Referer": f"https://www.pinterest.com{search_path}",
            "x-pinterest-source-url": search_path
        })

        self.lock = threading.Lock()
        self.stop = threading.Event()
        self._interrupted = False

        self.downloaded = 0
        self.skipped = 0

        self.seen_ids = set()
        self.seen_hashes = set()
        self.bookmark = None

        self._prev_sigint = None
        self._prev_sigterm = None

        self.load_state()

    def _handle_signal(self, signum, _frame):
        """Stop downloads cleanly on Ctrl+C or termination signals."""
        if self._interrupted:
            log.warning("\n[!] Force exit requested. Exiting immediately.")
            sys.exit(130 if signum == signal.SIGINT else 143)

        self._interrupted = True
        self.stop.set()

        sig_name = signal.Signals(signum).name
        log.warning(
            f"\n[!] {sig_name} received. Stopping gracefully "
            "(press Ctrl+C again to force quit)..."
        )

    def _install_signal_handlers(self):
        self._prev_sigint = signal.signal(signal.SIGINT, self._handle_signal)
        if hasattr(signal, "SIGTERM"):
            self._prev_sigterm = signal.signal(
                signal.SIGTERM,
                self._handle_signal
            )

    def _restore_signal_handlers(self):
        if self._prev_sigint is not None:
            signal.signal(signal.SIGINT, self._prev_sigint)
        if self._prev_sigterm is not None and hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, self._prev_sigterm)

    def load_state(self):
        if not os.path.exists(self.state_file):
            return

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            if data.get("query") != self.query:
                log.warning("Different query detected. Starting fresh.")
                return

            self.seen_ids = set(data.get("seen_ids", []))
            self.seen_hashes = set(data.get("seen_hashes", []))
            self.bookmark = data.get("bookmark")

            log.info(
                f"[+] Resumed: {len(self.seen_hashes)} existing images"
            )

        except (OSError, ValueError) as e:
            log.warning(f"[!] State loading failed: {e}")

    def save_state(self):
        with self.lock:
            data = {
                "query": self.query,
                "seen_ids": sorted(self.seen_ids),
                "seen_hashes": sorted(self.seen_hashes),
                "bookmark": self.bookmark
            }

        temp = self.state_file + ".tmp"

        with open(temp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        os.replace(temp, self.state_file)

    def request(self, url, params=None, stream=False):
        for attempt in range(4):
            if self.stop.is_set():
                return None

            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=20,
                    stream=stream
                )

                if response.status_code == 429:
                    wait = min(2 ** attempt * 3, 60)
                    log.warning(f"[!] Rate limited. Waiting {wait}s")
                    response.close()
                    self.stop.wait(wait)
                    continue

                response.raise_for_status()
                return response

            except requests.RequestException as e:
                log.warning(f"[!] Request failed: {e}")

                if attempt < 3:
                    self.stop.wait(2 ** attempt)

        return None

    def fetch_page(self, bookmark=None):
        options = {
            "isPrefetch": False,
            "query": self.query,
            "scope": "pins",
            "page_size": self.page_size
        }

        if bookmark:
            options["bookmarks"] = [bookmark]

        params = {
            "source_url": f"/search/pins/?q={self.query}",
            "data": json.dumps({
                "options": options,
                "context": {}
            })
        }

        response = self.request(SEARCH_URL, params=params)

        if response is None:
            return [], None

        try:
            data = response.json()
            resource = data.get("resource_response", {})

            pins = resource.get("data", {}).get("results", []) or []
            next_bookmark = resource.get("bookmark")

            return pins, next_bookmark

        except (ValueError, AttributeError) as e:
            log.warning(f"[!] Invalid search response: {e}")
            return [], None

        finally:
            response.close()

    @staticmethod
    def get_image_url(pin):
        images = pin.get("images", {}) or {}

        for size in (
            "orig",
            "1200x",
            "736x",
            "600x",
            "474x"
        ):
            url = images.get(size, {}).get("url")

            if url:
                return url

        return None

    def download_pin(self, pin):
        pin_id = str(pin.get("id", ""))

        if not pin_id:
            return False

        with self.lock:
            if self.downloaded >= self.count:
                return False

            if pin_id in self.seen_ids:
                self.skipped += 1
                return False

            # Reserve this ID to avoid duplicate concurrent downloads.
            self.seen_ids.add(pin_id)

        success = False

        try:
            if self.stop.is_set():
                return False

            url = self.get_image_url(pin)

            if not url:
                return False

            response = self.request(url, stream=True)

            if response is None:
                return False

            try:
                buffer = BytesIO()

                for chunk in response.iter_content(65536):
                    if self.stop.is_set():
                        return False

                    buffer.write(chunk)

                    if buffer.tell() > MAX_IMAGE_SIZE:
                        return False

                content = buffer.getvalue()

            finally:
                response.close()

            try:
                with Image.open(BytesIO(content)) as image:
                    image.verify()

                with Image.open(BytesIO(content)) as image:
                    width, height = image.size
                    extension = (image.format or "JPEG").lower()

            except (UnidentifiedImageError, OSError):
                return False

            if extension == "jpeg":
                extension = "jpg"

            if extension not in ("jpg", "png", "webp", "gif"):
                extension = "jpg"

            if self.min_res:
                if width < self.min_res or height < self.min_res:
                    return False

            digest = hashlib.sha256(content).hexdigest()

            with self.lock:
                if digest in self.seen_hashes:
                    self.skipped += 1
                    success = True
                    return False

                if self.downloaded >= self.count:
                    return False

                filename = f"pin_{pin_id}.{extension}"

                filepath = os.path.join(
                    self.output,
                    filename
                )

                temp = filepath + ".part"

                try:
                    with open(temp, "wb") as f:
                        f.write(content)

                    os.replace(temp, filepath)

                except OSError:
                    if os.path.exists(temp):
                        os.remove(temp)
                    raise

                self.seen_hashes.add(digest)
                self.downloaded += 1

                current = self.downloaded

            log.info(
                f"[{current}/{self.count}] "
                f"{filename} ({width}x{height})"
            )

            success = True
            return True

        finally:
            if not success:
                with self.lock:
                    self.seen_ids.discard(pin_id)

    def run(self):
        print("\n" + "=" * 55)
        print("          PINTEREST GUEST DOWNLOADER")
        print("=" * 55)

        print(f"Query       : {self.query}")
        print(f"Target      : {self.count} new images")
        print(f"Output      : {self.output}")
        print(f"Workers     : {self.workers}")
        print(f"Min Res     : {self.min_res or 'Any'}")
        print("Login       : Not Required")
        print("=" * 55 + "\n")

        bookmark = self.bookmark
        empty_pages = 0

        self._install_signal_handlers()

        try:
            with ThreadPoolExecutor(
                max_workers=self.workers
            ) as executor:

                while self.downloaded < self.count:

                    if self.stop.is_set():
                        break

                    pins, next_bookmark = self.fetch_page(
                        bookmark
                    )

                    if not pins:
                        empty_pages += 1

                        log.warning(
                            f"[!] Empty page ({empty_pages}/5)"
                        )

                        if empty_pages >= 5:
                            break

                        self.stop.wait(2)
                        continue

                    empty_pages = 0

                    futures = [
                        executor.submit(self.download_pin, pin)
                        for pin in pins
                    ]

                    for future in as_completed(futures):
                        if self.stop.is_set():
                            for pending in futures:
                                pending.cancel()
                            break

                        try:
                            future.result()
                        except Exception as e:
                            log.warning(
                                f"[!] Image download failed: {e}"
                            )

                    if self.stop.is_set():
                        break

                    # Only advance after the page has been processed.
                    self.bookmark = next_bookmark
                    self.save_state()

                    if not next_bookmark:
                        log.info("[+] No more pages available.")
                        break

                    if next_bookmark == END_BOOKMARK:
                        log.info("[+] Reached final page.")
                        break

                    if next_bookmark == bookmark:
                        log.info("[+] Pagination stopped advancing.")
                        break

                    bookmark = next_bookmark
                    self.stop.wait(self.delay)

        except KeyboardInterrupt:
            self.stop.set()
            log.warning("\n[!] Interrupted by user.")

        finally:
            self._restore_signal_handlers()
            self.save_state()

            status = "INTERRUPTED" if self._interrupted else "COMPLETE"

            print("\n" + "=" * 55)
            print(f"              SUMMARY ({status})")
            print("=" * 55)
            print(f"Downloaded : {self.downloaded}")
            print(f"Duplicates : {self.skipped}")
            print(f"Saved in   : {self.output}")
            if self._interrupted:
                print("Note       : Progress saved. Re-run to resume.")
            print("=" * 55 + "\n")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="pinterest_downloader.py",
        description=(
            "Pinterest Guest Image Downloader — download images by keyword "
            "without login, cookies, or an API key."
        ),
        epilog=(
            "Examples:\n"
            "  python pinterest_downloader.py -q \"nature wallpaper\" -n 100\n"
            "  python pinterest_downloader.py -q cars -n 50 --min-res 1080\n"
            "  python pinterest_downloader.py -v\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "-q", "--query",
        help="Pinterest image search keyword"
    )

    parser.add_argument(
        "-n", "--count",
        type=int,
        help="Number of images to download"
    )

    parser.add_argument(
        "-o", "--output",
        help="Output directory"
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=6,
        help="Number of parallel download workers (default: 6)"
    )

    parser.add_argument(
        "--min-res",
        type=int,
        default=0,
        help="Minimum width/height in pixels (default: 0 / any)"
    )

    parser.add_argument(
        "--page-size",
        type=int,
        default=25,
        help="Pins fetched per search page (default: 25)"
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay in seconds between search pages (default: 1.0)"
    )

    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show program version and exit"
    )

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    query = args.query
    count = args.count

    try:
        if not query:
            query = input("[?] Search keyword: ").strip()

        if not query:
            parser.error("Search keyword cannot be empty.")

        if count is None:
            try:
                count = int(input("[?] Number of images: "))
            except ValueError:
                parser.error("Image count must be an integer.")

    except (KeyboardInterrupt, EOFError):
        print("\n[!] Cancelled.")
        sys.exit(130)

    if count <= 0:
        parser.error("Image count must be greater than zero.")

    downloader = PinterestGuestDownloader(
        query=query,
        count=count,
        output=args.output,
        workers=args.workers,
        min_res=args.min_res,
        page_size=args.page_size,
        delay=args.delay
    )

    downloader.run()

    if downloader._interrupted:
        sys.exit(130)


if __name__ == "__main__":
    main()
