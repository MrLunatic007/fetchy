#!/usr/bin/env python3
import argparse
import sys
import os
from pathlib import Path
from downloader import Downloader
from connection_manager import Connector
import json
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    DownloadColumn,
    TransferSpeedColumn,
)
from rich.table import Table
from rich.panel import Panel
import threading
import time
import requests
import math


console = Console()


class CLIDownloader:
    def __init__(self):
        self.queue_file = Path.home() / ".fetchy" / "queue.json"
        self.queue_file.parent.mkdir(exist_ok=True)

    def download_file(self, url, output=None, threads=4, quiet=False):
        """Download a single file with progress"""
        try:
            connector = Connector(url)
            content = connector.connect()

            if not content:
                console.print("[red]Failed to connect to URL[/red]")
                return False

            filename = output or content.get("filename", "download_file")
            total_size = int(content.get("size", 0))

            if not quiet:
                console.print(f"[cyan]Downloading:[/cyan] {filename}")
                console.print(f"[cyan]Size:[/cyan] {total_size / (1024*1024):.2f} MB")
                console.print(f"[cyan]Threads:[/cyan] {threads}")

            # Download with progress
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                DownloadColumn(),
                TransferSpeedColumn(),
            ) as progress:
                task = progress.add_task("[cyan]Downloading...", total=total_size)

                # Split and download
                ranges = self._split_ranges(total_size, threads)
                downloaded = [0] * threads
                threads_list = []

                for i, (start, end) in enumerate(ranges):
                    t = threading.Thread(
                        target=self._download_chunk,
                        args=(url, start, end, filename, i, downloaded),
                    )
                    t.start()
                    threads_list.append(t)

                # Update progress
                while any(t.is_alive() for t in threads_list):
                    total_downloaded = sum(downloaded)
                    progress.update(task, completed=total_downloaded)
                    time.sleep(0.1)

                for t in threads_list:
                    t.join()

                progress.update(task, completed=total_size)

            # Merge parts
            if not quiet:
                console.print("[yellow]Merging parts...[/yellow]")

            self._merge_parts(filename, threads)

            if not quiet:
                console.print(f"[green]✓ Download completed:[/green] {filename}")

            return True

        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            return False

    def _split_ranges(self, total_size, num_chunks):
        chunks = []
        chunk_size = math.ceil(total_size / num_chunks)
        for i in range(num_chunks):
            start = i * chunk_size
            end = min(start + chunk_size - 1, total_size - 1)
            chunks.append((start, end))
        return chunks

    def _download_chunk(self, url, start, end, filename, part_num, downloaded):
        headers = {"Range": f"bytes={start}-{end}"}
        part_path = f"{filename}.part{part_num}"

        try:
            r = requests.get(url, headers=headers, stream=True)
            if r.status_code in (200, 206):
                with open(part_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded[part_num] += len(chunk)
        except Exception as e:
            console.print(f"[red]Chunk {part_num} error: {e}[/red]")

    def _merge_parts(self, filename, num_threads):
        with open(filename, "wb") as outfile:
            for i in range(num_threads):
                part_path = f"{filename}.part{i}"
                if os.path.exists(part_path):
                    with open(part_path, "rb") as infile:
                        outfile.write(infile.read())
                    os.remove(part_path)

    def add_to_queue(self, url, output=None, threads=4):
        """Add download to queue"""
        queue = self._load_queue()

        download = {
            "url": url,
            "output": output,
            "threads": threads,
            "status": "pending",
        }

        queue.append(download)
        self._save_queue(queue)

        console.print(f"[green]Added to queue:[/green] {url}")

    def list_queue(self):
        """List all downloads in queue"""
        queue = self._load_queue()

        if not queue:
            console.print("[yellow]Queue is empty[/yellow]")
            return

        table = Table(title="Download Queue")
        table.add_column("ID", style="cyan")
        table.add_column("URL", style="blue")
        table.add_column("Output", style="green")
        table.add_column("Threads", style="magenta")
        table.add_column("Status", style="yellow")

        for i, item in enumerate(queue):
            table.add_row(
                str(i),
                item["url"][:50] + "..." if len(item["url"]) > 50 else item["url"],
                item.get("output", "auto") or "auto",
                str(item.get("threads", 4)),
                item.get("status", "pending"),
            )

        console.print(table)

    def process_queue(self):
        """Process all downloads in queue"""
        queue = self._load_queue()

        if not queue:
            console.print("[yellow]Queue is empty[/yellow]")
            return

        console.print(f"[cyan]Processing {len(queue)} downloads...[/cyan]\n")

        for i, item in enumerate(queue):
            if item["status"] == "completed":
                continue

            console.print(f"\n[bold cyan]Download {i+1}/{len(queue)}[/bold cyan]")
            success = self.download_file(
                item["url"], item.get("output"), item.get("threads", 4)
            )

            item["status"] = "completed" if success else "failed"
            self._save_queue(queue)

        console.print("\n[green]✓ Queue processing completed[/green]")

    def clear_queue(self):
        """Clear completed downloads from queue"""
        queue = self._load_queue()
        queue = [item for item in queue if item["status"] != "completed"]
        self._save_queue(queue)
        console.print("[green]Cleared completed downloads[/green]")

    def get_info(self, url):
        """Get information about a URL"""
        try:
            connector = Connector(url)
            content = connector.connect()

            if not content:
                console.print("[red]Failed to connect to URL[/red]")
                return

            info = Panel(
                f"""[cyan]URL:[/cyan] {url}
[cyan]Filename:[/cyan] {content.get('filename', 'N/A')}
[cyan]Size:[/cyan] {int(content.get('size', 0)) / (1024*1024):.2f} MB
[cyan]Type:[/cyan] {content.get('type', 'N/A')}
[cyan]Supports Range:[/cyan] {'Yes' if content.get('range') == 'bytes' else 'No'}""",
                title="Download Information",
                border_style="cyan",
            )

            console.print(info)

        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

    def _load_queue(self):
        """Load queue from file"""
        if self.queue_file.exists():
            with open(self.queue_file, "r") as f:
                return json.load(f)
        return []

    def _save_queue(self, queue):
        """Save queue to file"""
        with open(self.queue_file, "w") as f:
            json.dump(queue, f, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Fetchy - Advanced Download Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  fetchy download https://example.com/file.zip
  fetchy download https://example.com/file.zip -o myfile.zip -t 8
  fetchy add https://example.com/file.zip
  fetchy queue
  fetchy process
  fetchy info https://example.com/file.zip
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Download command
    download_parser = subparsers.add_parser("download", help="Download a file")
    download_parser.add_argument("url", help="URL to download")
    download_parser.add_argument("-o", "--output", help="Output filename")
    download_parser.add_argument(
        "-t", "--threads", type=int, default=4, help="Number of threads (default: 4)"
    )
    download_parser.add_argument(
        "-q", "--quiet", action="store_true", help="Quiet mode"
    )

    # Add to queue command
    add_parser = subparsers.add_parser("add", help="Add download to queue")
    add_parser.add_argument("url", help="URL to download")
    add_parser.add_argument("-o", "--output", help="Output filename")
    add_parser.add_argument(
        "-t", "--threads", type=int, default=4, help="Number of threads"
    )

    # Queue commands
    subparsers.add_parser("queue", help="List download queue")
    subparsers.add_parser("process", help="Process download queue")
    subparsers.add_parser("clear", help="Clear completed downloads")

    # Info command
    info_parser = subparsers.add_parser("info", help="Get download information")
    info_parser.add_argument("url", help="URL to check")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    cli = CLIDownloader()

    if args.command == "download":
        cli.download_file(args.url, args.output, args.threads, args.quiet)
    elif args.command == "add":
        cli.add_to_queue(args.url, args.output, args.threads)
    elif args.command == "queue":
        cli.list_queue()
    elif args.command == "process":
        cli.process_queue()
    elif args.command == "clear":
        cli.clear_queue()
    elif args.command == "info":
        cli.get_info(args.url)


if __name__ == "__main__":
    main()
