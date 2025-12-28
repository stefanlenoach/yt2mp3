"""CLI interface for yt2mp3."""
import click
from pathlib import Path

from . import downloader


@click.group()
def cli():
    """Download YouTube videos as MP3 files.

    Usage: yt2mp3 download <youtube-url>

    Commands:
      download  Download a YouTube video as MP3
      list      List downloaded MP3 files
      set-dir   Set the default output directory
      config    Show current configuration
      open      Open the output directory in Finder
    """
    pass


@cli.command("download")
@click.argument("url")
@click.option("-o", "--output", type=click.Path(), help="Output directory for this download")
@click.option("-q", "--quality", type=click.Choice(["128", "192", "320"]), default="192", help="Audio quality in kbps")
@click.option("-n", "--name", help="Custom filename (without extension)")
@click.option("-s", "--start", "start_time", help="Start time (e.g., 12, 1:30, 1m30s)")
@click.option("-d", "--duration", help="Duration to capture (e.g., 20, 20s, 1:00)")
@click.option("-e", "--end", "end_time", help="End time (alternative to duration)")
def download(url, output, quality, name, start_time, duration, end_time):
    """Download a YouTube video as MP3.

    \b
    Examples:
      yt2mp3 download "URL"                    # Full video
      yt2mp3 download "URL" -s 12 -d 20        # 20 sec starting at 0:12
      yt2mp3 download "URL" -s 1:30 -e 2:00    # From 1:30 to 2:00
      yt2mp3 download "URL" -s 1m30s -d 30s    # Same as above
    """
    output_dir = Path(output) if output else None
    quality_int = int(quality)

    click.echo(f"Downloading: {url}")
    click.echo(f"Quality: {quality_int} kbps")
    if start_time or duration or end_time:
        time_info = f"Clip: start={start_time or '0'}"
        if duration:
            time_info += f", duration={duration}"
        elif end_time:
            time_info += f", end={end_time}"
        click.echo(time_info)
    click.echo(f"Output: {output_dir or downloader.get_output_dir()}")
    click.echo()

    with click.progressbar(length=100, label="Downloading") as bar:
        last_percent = [0]

        def progress_callback(downloaded, total, finished=False):
            if finished:
                bar.update(100 - last_percent[0])
            elif total > 0:
                percent = int((downloaded / total) * 100)
                delta = percent - last_percent[0]
                if delta > 0:
                    bar.update(delta)
                    last_percent[0] = percent

        try:
            result_path = downloader.download_as_mp3(
                url=url,
                output_dir=output_dir,
                quality=quality_int,
                filename=name,
                progress_callback=progress_callback,
                start_time=start_time,
                duration=duration,
                end_time=end_time,
            )
            click.echo()
            click.secho(f"Saved: {result_path}", fg="green")
        except Exception as e:
            click.echo()
            click.secho(f"Error: {e}", fg="red")
            raise SystemExit(1)


# Alias 'd' for download
@cli.command("d")
@click.argument("url")
@click.option("-o", "--output", type=click.Path(), help="Output directory for this download")
@click.option("-q", "--quality", type=click.Choice(["128", "192", "320"]), default="192", help="Audio quality in kbps")
@click.option("-n", "--name", help="Custom filename (without extension)")
@click.option("-s", "--start", "start_time", help="Start time (e.g., 12, 1:30, 1m30s)")
@click.option("-d", "--duration", help="Duration to capture (e.g., 20, 20s, 1:00)")
@click.option("-e", "--end", "end_time", help="End time (alternative to duration)")
@click.pass_context
def download_alias(ctx, url, output, quality, name, start_time, duration, end_time):
    """Shortcut for 'download' command."""
    ctx.invoke(download, url=url, output=output, quality=quality, name=name,
               start_time=start_time, duration=duration, end_time=end_time)


@cli.command("batch")
@click.argument("urls", nargs=-1)
@click.option("-f", "--file", "file_path", type=click.Path(exists=True), help="File containing URLs (one per line)")
@click.option("-o", "--output", type=click.Path(), help="Output directory for downloads")
@click.option("-q", "--quality", type=click.Choice(["128", "192", "320"]), default="192", help="Audio quality in kbps")
def batch(urls, file_path, output, quality):
    """Download multiple YouTube videos as MP3.

    Pass URLs directly or use a file:

    \b
    yt2mp3 batch "url1" "url2" "url3"
    yt2mp3 batch -f urls.txt
    """
    url_list = list(urls)

    if file_path:
        with open(file_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    url_list.append(line)

    if not url_list:
        click.echo("No URLs provided. Pass URLs as arguments or use -f/--file.")
        raise SystemExit(1)

    output_dir = Path(output) if output else None
    quality_int = int(quality)
    total = len(url_list)
    succeeded = []
    failed = []

    click.echo(f"Downloading {total} videos...")
    click.echo(f"Quality: {quality_int} kbps")
    click.echo(f"Output: {output_dir or downloader.get_output_dir()}")
    click.echo()

    for i, url in enumerate(url_list, 1):
        click.echo(f"[{i}/{total}] {url}")

        try:
            result_path = downloader.download_as_mp3(
                url=url,
                output_dir=output_dir,
                quality=quality_int,
            )
            click.secho(f"  -> {result_path.name}", fg="green")
            succeeded.append(url)
        except Exception as e:
            click.secho(f"  Error: {e}", fg="red")
            failed.append((url, str(e)))

    click.echo()
    click.echo(f"Completed: {len(succeeded)}/{total} succeeded")
    if failed:
        click.secho(f"Failed ({len(failed)}):", fg="red")
        for url, err in failed:
            click.echo(f"  {url}")


@cli.command("list")
@click.option("-n", "--count", default=20, help="Number of files to show")
def list_files(count):
    """List downloaded MP3 files."""
    files = downloader.list_downloads()

    if not files:
        click.echo(f"No MP3 files in {downloader.get_output_dir()}")
        return

    click.echo(f"MP3 files in {downloader.get_output_dir()}:\n")
    for f in files[:count]:
        click.echo(f"  {f['size_mb']:>6.1f} MB  {f['name']}")

    if len(files) > count:
        click.echo(f"\n  ... and {len(files) - count} more files")


@cli.command("set-dir")
@click.argument("path", type=click.Path())
def set_dir(path):
    """Set the default output directory."""
    path = Path(path).expanduser().resolve()
    downloader.set_output_dir(path)
    click.secho(f"Output directory set to: {path}", fg="green")


@cli.command("config")
def show_config():
    """Show current configuration."""
    output_dir = downloader.get_output_dir()
    click.echo(f"Output directory: {output_dir}")

    files = downloader.list_downloads()
    total_size = sum(f["size_mb"] for f in files)
    click.echo(f"Total files: {len(files)}")
    click.echo(f"Total size: {total_size:.1f} MB")


@cli.command("open")
def open_dir():
    """Open the output directory in Finder."""
    import subprocess
    output_dir = downloader.get_output_dir()
    subprocess.run(["open", str(output_dir)])
    click.echo(f"Opened: {output_dir}")


if __name__ == "__main__":
    cli()
