import math
import threading
import time
import requests
import os
from pathlib import Path
from connection_manager import Connector


class Downloader:
    def __init__(self, url: str = None) -> None:
        self.url = url
        self.connector = Connector(url) if url else None
        self.is_paused = False
        self.is_cancelled = False
        self.downloaded_bytes = []
        self.lock = threading.Lock()

    def _initializer(self):
        """Initialize connection and get file metadata"""
        if not self.connector:
            raise ValueError("No URL provided")

        content = self.connector.connect()
        if not content:
            raise ConnectionError("Failed to connect to URL")

        return content

    def _splitter(self, total_size: int, num_chunks: int):
        """Split file into chunks for parallel downloading"""
        chunks = []
        chunk_size = math.ceil(total_size / num_chunks)

        for i in range(num_chunks):
            start = i * chunk_size
            end = min(start + chunk_size - 1, total_size - 1)
            chunks.append((start, end))

        return chunks

    def _threaded_download(
        self, url: str, start: int, end: int, part_num: int, output_dir: str = "."
    ):
        """Download a specific chunk of the file"""
        headers = {"Range": f"bytes={start}-{end}"}
        part_path = os.path.join(output_dir, f"part_{part_num}.tmp")

        print(f"[Thread-{part_num}] Downloading bytes {start}-{end}")

        try:
            r = requests.get(url, headers=headers, stream=True, timeout=30)

            if r.status_code in (200, 206):
                with open(part_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        # Check if download is cancelled
                        if self.is_cancelled:
                            print(f"[Thread-{part_num}] Cancelled.")
                            return

                        # Pause handling
                        while self.is_paused and not self.is_cancelled:
                            time.sleep(0.1)

                        if chunk:
                            f.write(chunk)

                            # Update downloaded bytes
                            with self.lock:
                                self.downloaded_bytes[part_num] += len(chunk)

                print(f"[Thread-{part_num}] Finished.")
            else:
                print(f"[Thread-{part_num}] Failed with status {r.status_code}")

        except requests.exceptions.Timeout:
            print(f"[Thread-{part_num}] Timeout error")
        except requests.exceptions.RequestException as e:
            print(f"[Thread-{part_num}] Request error: {e}")
        except Exception as e:
            print(f"[Thread-{part_num}] Error: {e}")

    def _parallel_downloader(
        self, url: str, total_size: int, output_dir: str = ".", num_threads: int = 4
    ):
        """Download file using multiple threads"""
        ranges = self._splitter(total_size, num_threads)
        threads = []

        # Initialize downloaded bytes tracker
        self.downloaded_bytes = [0] * num_threads

        start_time = time.time()

        # Start all download threads
        for i, (start, end) in enumerate(ranges):
            t = threading.Thread(
                target=self._threaded_download, args=(url, start, end, i, output_dir)
            )
            t.start()
            threads.append(t)

        # Wait for all threads to complete
        for t in threads:
            t.join()

        if not self.is_cancelled:
            elapsed_time = time.time() - start_time
            print(f"✅ Download completed in {elapsed_time:.2f} seconds.")
            return True
        else:
            print("❌ Download cancelled.")
            return False

    def _merger(self, output_path: str, num_threads: int, output_dir: str = "."):
        """Merge downloaded parts into final file"""
        try:
            print(f"Merging {num_threads} parts...")

            with open(output_path, "wb") as outfile:
                for i in range(num_threads):
                    part_path = os.path.join(output_dir, f"part_{i}.tmp")

                    if os.path.exists(part_path):
                        with open(part_path, "rb") as part:
                            outfile.write(part.read())

                        # Remove part file after merging
                        os.remove(part_path)
                    else:
                        print(f"Warning: Part {i} not found at {part_path}")

            print(f"✅ File merged successfully as {output_path}")
            return True

        except Exception as e:
            print(f"Error merging files: {e}")
            return False

    def _cleanup_parts(self, num_threads: int, output_dir: str = "."):
        """Clean up temporary part files"""
        for i in range(num_threads):
            part_path = os.path.join(output_dir, f"part_{i}.tmp")
            if os.path.exists(part_path):
                try:
                    os.remove(part_path)
                except Exception as e:
                    print(f"Warning: Could not remove {part_path}: {e}")

    def download(self, output_path: str = None, num_threads: int = 4):
        """
        Main download method

        Args:
            output_path: Path where file should be saved
            num_threads: Number of parallel download threads
        """
        try:
            # Get file info
            content = self._initializer()
            total_size = int(content.get("size", 0))

            if total_size == 0:
                print(
                    "Warning: Could not determine file size. Attempting single-threaded download..."
                )
                num_threads = 1

            # Determine output path
            if not output_path:
                output_path = content.get("filename", "downloaded_file")

            # Create output directory if it doesn't exist
            output_dir = os.path.dirname(output_path) or "."
            if output_dir != ".":
                os.makedirs(output_dir, exist_ok=True)

            # Print download info
            size_mb = total_size / (1024 * 1024) if total_size > 0 else 0
            print(f"\n{'='*60}")
            print(f"Starting Download")
            print(f"{'='*60}")
            print(f"URL:      {self.url}")
            print(f"File:     {os.path.basename(output_path)}")
            print(f"Size:     {size_mb:.2f} MB")
            print(f"Threads:  {num_threads}")
            print(f"Output:   {output_path}")
            print(f"{'='*60}\n")

            # Check if server supports range requests
            if not content.get("supports_resume") and total_size > 0:
                print(
                    "Warning: Server doesn't support range requests. Using single thread."
                )
                num_threads = 1

            # Download file
            success = self._parallel_downloader(
                self.url, total_size, output_dir, num_threads
            )

            if success and not self.is_cancelled:
                # Merge parts
                merge_success = self._merger(output_path, num_threads, output_dir)

                if merge_success:
                    # Verify file size
                    if os.path.exists(output_path):
                        actual_size = os.path.getsize(output_path)
                        if total_size > 0 and actual_size != total_size:
                            print(
                                f"Warning: File size mismatch. Expected: {total_size}, Got: {actual_size}"
                            )
                        else:
                            print(f"\n✅ Download successful: {output_path}")
                    return True
            else:
                # Clean up parts if cancelled
                self._cleanup_parts(num_threads, output_dir)
                return False

        except Exception as e:
            print(f"Error during download: {e}")
            self._cleanup_parts(num_threads, output_dir)
            return False

    def pause(self):
        """Pause the download"""
        self.is_paused = True
        print("Download paused")

    def resume(self):
        """Resume the download"""
        self.is_paused = False
        print("Download resumed")

    def cancel(self):
        """Cancel the download"""
        self.is_cancelled = True
        print("Download cancelled")

    def get_progress(self):
        """Get current download progress"""
        with self.lock:
            return sum(self.downloaded_bytes)


# Legacy method name for backward compatibility
def downloader(url: str, output_path: str = None, num_threads: int = 4):
    """
    Legacy function for backward compatibility
    """
    dl = Downloader(url)
    return dl.download(output_path, num_threads)
