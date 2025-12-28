"""Clipboard watcher for YouTube URLs."""
import re
import subprocess
import time

YOUTUBE_PATTERNS = [
    r"https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+",
    r"https?://youtu\.be/[\w-]+",
    r"https?://(?:www\.)?youtube\.com/shorts/[\w-]+",
    r"https?://music\.youtube\.com/watch\?v=[\w-]+",
]

YOUTUBE_REGEX = re.compile("|".join(YOUTUBE_PATTERNS))


def get_clipboard() -> str:
    """Get current clipboard contents on macOS."""
    try:
        result = subprocess.run(
            ["pbpaste"],
            capture_output=True,
            text=True,
            timeout=1,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def extract_youtube_url(text: str) -> str | None:
    """Extract a YouTube URL from text if present."""
    match = YOUTUBE_REGEX.search(text)
    if match:
        return match.group(0)
    return None


def watch_clipboard(callback, interval: float = 1.0):
    """Watch clipboard for YouTube URLs.

    Args:
        callback: Function to call with (url, title) when URL detected
        interval: Seconds between clipboard checks
    """
    seen_urls = set()
    last_clipboard = ""

    while True:
        try:
            clipboard = get_clipboard()

            # Only process if clipboard changed
            if clipboard != last_clipboard:
                last_clipboard = clipboard
                url = extract_youtube_url(clipboard)

                if url and url not in seen_urls:
                    seen_urls.add(url)
                    callback(url)

        except KeyboardInterrupt:
            break
        except Exception:
            pass

        time.sleep(interval)
