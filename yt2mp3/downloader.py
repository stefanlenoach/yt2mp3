"""Core download and conversion logic."""
import json
from pathlib import Path

import yt_dlp

CONFIG_FILE = Path.home() / ".yt2mp3_config.json"
DEFAULT_OUTPUT_DIR = Path.home() / "yt2mp3"


def get_output_dir() -> Path:
    """Get the configured output directory."""
    if CONFIG_FILE.exists():
        config = json.loads(CONFIG_FILE.read_text())
        return Path(config.get("output_dir", DEFAULT_OUTPUT_DIR))
    return DEFAULT_OUTPUT_DIR


def set_output_dir(path: Path) -> None:
    """Set the output directory."""
    path = path.expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    config = {"output_dir": str(path)}
    CONFIG_FILE.write_text(json.dumps(config, indent=2))


def list_downloads() -> list[dict]:
    """List all MP3 files in the output directory."""
    output_dir = get_output_dir()
    if not output_dir.exists():
        return []

    files = []
    for f in sorted(output_dir.glob("*.mp3"), key=lambda x: x.stat().st_mtime, reverse=True):
        stat = f.stat()
        files.append({
            "name": f.name,
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "path": str(f),
        })
    return files


def parse_time(time_str: str) -> float:
    """Parse time string to seconds.

    Supports formats:
    - "12" or "12s" -> 12 seconds
    - "1:30" or "1m30s" -> 90 seconds
    - "1:02:30" or "1h2m30s" -> 3750 seconds
    """
    if not time_str:
        return 0.0

    time_str = time_str.strip().lower()

    # Handle HH:MM:SS or MM:SS format
    if ":" in time_str:
        parts = time_str.split(":")
        if len(parts) == 2:
            mins, secs = parts
            return float(mins) * 60 + float(secs)
        elif len(parts) == 3:
            hours, mins, secs = parts
            return float(hours) * 3600 + float(mins) * 60 + float(secs)

    # Handle 1h2m30s format
    import re
    match = re.match(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+(?:\.\d+)?)s?)?$", time_str)
    if match:
        hours = float(match.group(1) or 0)
        mins = float(match.group(2) or 0)
        secs = float(match.group(3) or 0)
        return hours * 3600 + mins * 60 + secs

    # Plain number (seconds)
    return float(time_str.rstrip("s"))


def download_as_mp3(
    url: str,
    output_dir: Path | None = None,
    quality: int = 192,
    filename: str | None = None,
    progress_callback=None,
    start_time: str | None = None,
    duration: str | None = None,
    end_time: str | None = None,
) -> Path:
    """Download a YouTube video and convert to MP3.

    Time clipping:
    - start_time: Where to start (e.g., "12", "1:30", "1m30s")
    - duration: How long to capture (e.g., "20", "20s", "1:00")
    - end_time: Where to end (alternative to duration)
    """
    if output_dir is None:
        output_dir = get_output_dir()

    output_dir = Path(output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if filename:
        output_template = str(output_dir / f"{filename}.%(ext)s")
    else:
        output_template = str(output_dir / "%(title)s.%(ext)s")

    def progress_hook(d):
        if progress_callback and d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            downloaded = d.get("downloaded_bytes", 0)
            if total > 0:
                progress_callback(downloaded, total)
        elif progress_callback and d["status"] == "finished":
            progress_callback(1, 1, finished=True)

    # Build time range for clipping using yt-dlp's download_ranges
    clip_info = None
    if start_time or duration or end_time:
        start_secs = parse_time(start_time) if start_time else 0
        if duration:
            end_secs = start_secs + parse_time(duration)
        elif end_time:
            end_secs = parse_time(end_time)
        else:
            end_secs = None
        clip_info = (start_secs, end_secs)

    ydl_opts = {
        "format": "bestaudio/best",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": str(quality),
        }],
        "outtmpl": output_template,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [progress_hook],
    }

    # Use external_downloader_args for time-based clipping
    if clip_info:
        start_secs, end_secs = clip_info
        ffmpeg_args = []
        if start_secs > 0:
            ffmpeg_args.extend(["-ss", str(start_secs)])
        if end_secs is not None:
            ffmpeg_args.extend(["-to", str(end_secs)])
        if ffmpeg_args:
            ydl_opts["external_downloader"] = "ffmpeg"
            ydl_opts["external_downloader_args"] = {"ffmpeg_i": ffmpeg_args}

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get("title", "download")

        if filename:
            final_path = output_dir / f"{filename}.mp3"
        else:
            safe_title = ydl.prepare_filename(info)
            final_path = Path(safe_title).with_suffix(".mp3")

    return final_path
