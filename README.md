# yt2mp3

A command-line tool to download YouTube videos as MP3 files.

## Installation

Requires Python 3.10+ and ffmpeg.

```bash
# Install ffmpeg (if not already installed)
brew install ffmpeg

# Clone and install
git clone https://github.com/stefanlenoach/yt2mp3.git
cd yt2mp3
pip install -e .
```

## Usage

### Download a video

```bash
yt2mp3 download "https://youtube.com/watch?v=..."

# Or use the shortcut
yt2mp3 d "https://youtube.com/watch?v=..."
```

### Options

```bash
-o, --output PATH    Output directory for this download
-q, --quality        Audio quality: 128, 192 (default), or 320 kbps
-n, --name           Custom filename (without extension)
-s, --start          Start time (e.g., 12, 1:30, 1m30s)
-d, --duration       Duration to capture (e.g., 20, 20s, 1:00)
-e, --end            End time (alternative to duration)
```

### Time clipping

Extract a specific portion of the audio:

```bash
# 20 seconds starting at 0:12
yt2mp3 d "URL" -s 12 -d 20

# From 1:30 to 2:00
yt2mp3 d "URL" -s 1:30 -e 2:00

# Various time formats work
yt2mp3 d "URL" -s 1m30s -d 30s
yt2mp3 d "URL" -s 1:02:30 -e 1:05:00
```

### Batch downloads

Download multiple videos at once:

```bash
# Multiple URLs as arguments
yt2mp3 batch "url1" "url2" "url3"

# From a file (one URL per line)
yt2mp3 batch -f urls.txt

# Combine both
yt2mp3 batch "url1" -f more_urls.txt -q 320
```

### Clipboard watcher

Auto-detect YouTube URLs when you copy them:

```bash
# Interactive mode - prompts before each download
yt2mp3 watch

# Auto-download mode - no prompts
yt2mp3 watch -y

# With options
yt2mp3 watch -y -q 320
```

Keep a terminal running with `yt2mp3 watch`, then just copy any YouTube URL from your browser. It will automatically detect and download it.

### Trim silence

Remove silence from the beginning and end of tracks:

```bash
# Trim a specific file
yt2mp3 trim "song.mp3"

# Trim all files in output directory
yt2mp3 trim --all

# Only trim start (keep ending)
yt2mp3 trim song.mp3 --no-end

# More aggressive threshold (-40dB instead of -50dB)
yt2mp3 trim song.mp3 -t -40
```

### Manage downloads

```bash
# List downloaded files
yt2mp3 list

# Show current config
yt2mp3 config

# Change default output directory (default: ~/yt2mp3)
yt2mp3 set-dir ~/Music/YouTube

# Open output folder in Finder
yt2mp3 open
```

## All Commands

| Command | Description |
|---------|-------------|
| `download` / `d` | Download a YouTube video as MP3 |
| `batch` | Download multiple videos |
| `watch` | Watch clipboard for YouTube URLs |
| `trim` | Remove silence from start/end of files |
| `list` | List downloaded MP3 files |
| `config` | Show current configuration |
| `set-dir` | Set default output directory |
| `open` | Open output directory in Finder |
