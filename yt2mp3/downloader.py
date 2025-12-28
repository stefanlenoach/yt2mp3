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


def trim_silence(
    input_path: Path,
    output_path: Path | None = None,
    threshold_db: float = -50,
    min_silence_duration: float = 0.1,
    trim_start: bool = True,
    trim_end: bool = True,
) -> Path:
    """Remove silence from the beginning and/or end of an audio file.

    Args:
        input_path: Path to the input audio file
        output_path: Path for output file (defaults to overwriting input)
        threshold_db: Volume threshold in dB below which is considered silence (default -50dB)
        min_silence_duration: Minimum duration of silence to detect (default 0.1s)
        trim_start: Whether to trim silence from the start
        trim_end: Whether to trim silence from the end

    Returns:
        Path to the output file
    """
    import subprocess
    import tempfile

    input_path = Path(input_path).resolve()
    if output_path is None:
        output_path = input_path
    else:
        output_path = Path(output_path).resolve()

    # Build the silenceremove filter
    filters = []

    if trim_start:
        # Remove silence from start: stop after first non-silence
        filters.append(
            f"silenceremove=start_periods=1:start_duration={min_silence_duration}:start_threshold={threshold_db}dB"
        )

    if trim_end:
        # Remove silence from end: reverse, remove from "start", reverse back
        filters.append(
            f"areverse,silenceremove=start_periods=1:start_duration={min_silence_duration}:start_threshold={threshold_db}dB,areverse"
        )

    if not filters:
        return input_path

    filter_chain = ",".join(filters)

    # Use temp file if overwriting
    if output_path == input_path:
        temp_fd, temp_path = tempfile.mkstemp(suffix=".mp3")
        temp_path = Path(temp_path)
    else:
        temp_path = output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(input_path),
            "-af", filter_chain,
            "-acodec", "libmp3lame",
            "-q:a", "2",
            str(temp_path),
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr}")

        # If overwriting, replace the original
        if output_path == input_path:
            import shutil
            shutil.move(str(temp_path), str(output_path))

    finally:
        # Clean up temp file if it still exists
        if output_path == input_path and temp_path.exists():
            temp_path.unlink()

    return output_path


def get_audio_duration(path: Path) -> float:
    """Get the duration of an audio file in seconds."""
    import subprocess

    result = subprocess.run(
        [
            "ffprobe",
            "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")

    return float(result.stdout.strip())


def search_youtube(query: str, max_results: int = 10) -> list[dict]:
    """Search YouTube and return video info.

    Returns list of dicts with: id, title, duration, channel, url
    """
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        search_url = f"ytsearch{max_results}:{query}"
        info = ydl.extract_info(search_url, download=False)

        results = []
        for entry in info.get("entries", []):
            duration = entry.get("duration", 0)
            if duration:
                mins, secs = divmod(int(duration), 60)
                duration_str = f"{mins}:{secs:02d}"
            else:
                duration_str = "?"

            results.append({
                "id": entry.get("id"),
                "title": entry.get("title", "Unknown"),
                "duration": duration_str,
                "duration_secs": duration,
                "channel": entry.get("channel") or entry.get("uploader", "Unknown"),
                "url": entry.get("url") or f"https://youtube.com/watch?v={entry.get('id')}",
            })

        return results


def get_playlist_info(url: str) -> dict:
    """Get info about a playlist without downloading.

    Returns dict with: title, channel, count, entries (list of video info)
    """
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

        entries = []
        for entry in info.get("entries", []):
            if entry is None:
                continue
            duration = entry.get("duration", 0)
            if duration:
                mins, secs = divmod(int(duration), 60)
                duration_str = f"{mins}:{secs:02d}"
            else:
                duration_str = "?"

            entries.append({
                "id": entry.get("id"),
                "title": entry.get("title", "Unknown"),
                "duration": duration_str,
                "duration_secs": duration or 0,
                "url": entry.get("url") or f"https://youtube.com/watch?v={entry.get('id')}",
            })

        return {
            "title": info.get("title", "Unknown Playlist"),
            "channel": info.get("channel") or info.get("uploader", "Unknown"),
            "count": len(entries),
            "entries": entries,
        }


def download_playlist(
    url: str,
    output_dir: Path | None = None,
    quality: int = 192,
    max_downloads: int | None = None,
    progress_callback=None,
) -> list[Path]:
    """Download all videos from a playlist as MP3.

    Args:
        url: Playlist URL
        output_dir: Output directory
        quality: Audio quality in kbps
        max_downloads: Max number of videos to download (None = all)
        progress_callback: Called with (index, total, title, path_or_error)

    Returns:
        List of successfully downloaded file paths
    """
    if output_dir is None:
        output_dir = get_output_dir()

    output_dir = Path(output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # First get playlist info
    playlist_info = get_playlist_info(url)
    entries = playlist_info["entries"]

    if max_downloads:
        entries = entries[:max_downloads]

    downloaded = []
    total = len(entries)

    for i, entry in enumerate(entries, 1):
        video_url = entry["url"]
        title = entry["title"]

        try:
            path = download_as_mp3(
                url=video_url,
                output_dir=output_dir,
                quality=quality,
            )
            downloaded.append(path)
            if progress_callback:
                progress_callback(i, total, title, path)
        except Exception as e:
            if progress_callback:
                progress_callback(i, total, title, e)

    return downloaded
