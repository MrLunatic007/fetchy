#!/usr/bin/env python3
import argparse
import json
import threading
import time
from pathlib import Path

from downloader import Downloader
from connection_manager import Connector
from rich.console import Console
from rich.progress import (
    Progress, SpinnerColumn, BarColumn, TextColumn,
    DownloadColumn, TransferSpeedColumn
)
from rich.table import Table
from rich.panel import Panel


console = Console()


class DownloadQueue:
    """Manages download queue persistence"""
    
    def __init__(self):
        self.queue_file = Path.home() / ".fetchy" / "queue.json"
        self.queue_file.parent.mkdir(exist_ok=True)

    def load(self):
        """Load queue from disk"""
        if self.queue_file.exists():
            with open(self.queue_file, "r") as f:
                return json.load(f)
        return []

    def save(self, queue):
        """Save queue to disk"""
        with open(self.queue_file, "w") as f:
            json.dump(queue, f, indent=2)

    def add(self, url, output=None, threads=4):
        """Add item to queue"""
        queue = self.load()
        queue.append({
            "url": url,
            "output": output,
            "threads": threads,
            "status": "pending"
        })
        self.save(queue)

    def remove(self, url):
        """Remove item from queue"""
        queue = self.load()
        new_queue = [item for item in queue if item["url"] != url]
        
        if len(new_queue) == len(queue):
            return False
        
        self.save(new_queue)
        return True

    def clear_completed(self):
        """Remove completed items"""
        queue = self.load()
        queue = [item for item in queue if item["status"] != "completed"]
        self.save(queue)


class CLIDownloader:
    """CLI interface for downloads"""
    
    def __init__(self):
        self.queue = DownloadQueue()

    def download_file(self, url, output=None, threads=4, quiet=False):
        """Download a single file with progress"""
        try:
            # Get file info
            connector = Connector(url)
            content = connector.connect()

            if not content:
                console.print("[red]Failed to connect to URL[/red]")
                return False

            filename = output or content.get("filename", "download_file")
            
            # Handle None size
            size = content.get("size")
            total_size = int(size) if size else 0
            
            if total_size == 0:
                console.print("[yellow]Warning: Could not determine file size. Download may not show accurate progress.[/yellow]")

            if not quiet:
                size_display = f"{total_size / (1024*1024):.2f} MB" if total_size > 0 else "Unknown"
                console.print(f"[cyan]File:[/cyan] {filename}")
                console.print(f"[cyan]Size:[/cyan] {size_display}")
                console.print(f"[cyan]Threads:[/cyan] {threads}\n")

            # Create downloader
            downloader = Downloader(url)

            # Progress tracking
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                DownloadColumn(),
                TransferSpeedColumn(),
            ) as progress:
                # Use None for total if size is unknown
                task = progress.add_task(
                    "[cyan]Downloading...", 
                    total=total_size if total_size > 0 else None
                )

                # Start download in thread
                download_thread = threading.Thread(
                    target=downloader.download,
                    args=(filename, threads)
                )
                download_thread.start()

                # Update progress
                while download_thread.is_alive():
                    downloaded = downloader.get_progress()
                    progress.update(task, completed=downloaded)
                    time.sleep(0.1)

                download_thread.join()
                if total_size > 0:
                    progress.update(task, completed=total_size)

            if not quiet:
                console.print(f"[green]✓ Download completed:[/green] {filename}")

            return True

        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            return False

    def add_to_queue(self, url, output=None, threads=4):
        """Add download to queue"""
        self.queue.add(url, output, threads)
        console.print(f"[green]Added to queue:[/green] {url}")

    def remove_from_queue(self, url):
        """Remove download from queue"""
        if self.queue.remove(url):
            console.print(f"[green]Removed from queue:[/green] {url}")
        else:
            console.print(f"[red]URL not found in queue[/red]")

    def list_queue(self):
        """Display queue contents"""
        queue = self.queue.load()

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
            url_display = item["url"][:50] + "..." if len(item["url"]) > 50 else item["url"]
            table.add_row(
                str(i),
                url_display,
                item.get("output") or "auto",
                str(item.get("threads", 4)),
                item.get("status", "pending")
            )

        console.print(table)

    def process_queue(self):
        """Process all pending downloads"""
        queue = self.queue.load()

        if not queue:
            console.print("[yellow]Queue is empty[/yellow]")
            return

        pending = [item for item in queue if item["status"] == "pending"]
        console.print(f"[cyan]Processing {len(pending)} downloads...[/cyan]\n")

        for i, item in enumerate(queue):
            if item["status"] != "pending":
                continue

            console.print(f"\n[bold cyan]Download {i+1}/{len(pending)}[/bold cyan]")
            success = self.download_file(
                item["url"],
                item.get("output"),
                item.get("threads", 4)
            )

            item["status"] = "completed" if success else "failed"
            self.queue.save(queue)

        console.print("\n[green]✓ Queue processing completed[/green]")

    def clear_completed(self):
        """Clear completed downloads"""
        self.queue.clear_completed()
        console.print("[green]Cleared completed downloads[/green]")

    def get_info(self, url):
        """Display file information"""
        try:
            connector = Connector(url)
            content = connector.connect()

            if not content:
                console.print("[red]Failed to connect to URL[/red]")
                return

            # Handle None size
            size = content.get("size")
            if size:
                size_mb = int(size) / (1024 * 1024)
                size_display = f"{size_mb:.2f} MB"
            else:
                size_display = "Unknown"

            supports_range = "Yes" if content.get("supports_resume") else "No"

            info = Panel(
                f"""[cyan]URL:[/cyan] {url}
[cyan]Filename:[/cyan] {content.get('filename', 'N/A')}
[cyan]Size:[/cyan] {size_display}
[cyan]Type:[/cyan] {content.get('type', 'N/A')}
[cyan]Supports Range:[/cyan] {supports_range}""",
                title="Download Information",
                border_style="cyan"
            )

            console.print(info)

        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


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
  fetchy drop https://example.com/file.zip
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Download command
    download_parser = subparsers.add_parser("download", help="Download a file")
    download_parser.add_argument("url", help="URL to download")
    download_parser.add_argument("-o", "--output", help="Output filename")
    download_parser.add_argument("-t", "--threads", type=int, default=4, help="Number of threads")
    download_parser.add_argument("-q", "--quiet", action="store_true", help="Quiet mode")

    # Queue commands
    add_parser = subparsers.add_parser("add", help="Add download to queue")
    add_parser.add_argument("url", help="URL to download")
    add_parser.add_argument("-o", "--output", help="Output filename")
    add_parser.add_argument("-t", "--threads", type=int, default=4, help="Number of threads")

    drop_parser = subparsers.add_parser("drop", help="Remove URL from queue")
    drop_parser.add_argument("url", help="URL to remove")

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

    try:
        if args.command == "download":
            cli.download_file(args.url, args.output, args.threads, args.quiet)
        elif args.command == "add":
            cli.add_to_queue(args.url, args.output, args.threads)
        elif args.command == "drop":
            cli.remove_from_queue(args.url)
        elif args.command == "queue":
            cli.list_queue()
        elif args.command == "process":
            cli.process_queue()
        elif args.command == "clear":
            cli.clear_completed()
        elif args.command == "info":
            cli.get_info(args.url)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


if __name__ == "__main__":
    main()
