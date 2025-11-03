import math
import threading
import time
import requests
import os
from connection_manager import Connector


class Downloader:
    """Handles multi-threaded file downloads"""

    def __init__(self, url: str):
        self.url = url
        self.connector = Connector(url)
        self.is_paused = False
        self.is_cancelled = False
        self.downloaded_bytes = []
        self.lock = threading.Lock()

    def download(self, output_path: str = None, num_threads: int = 4):
        """
        Download file with multi-threading support

        Args:
            output_path: Where to save the file
            num_threads: Number of parallel download threads
        """
        # Get file metadata
        content = self.connector.connect()
        if not content:
            raise ConnectionError("Failed to connect to URL")

        # Handle None size
        size = content.get("size")
        total_size = int(size) if size else 0

        if total_size == 0:
            num_threads = 1

        # Determine output path
        output_path = output_path or content.get("filename", "downloaded_file")
        output_dir = os.path.dirname(output_path) or "."

        if output_dir != ".":
            os.makedirs(output_dir, exist_ok=True)

        # Adjust threads if server doesn't support ranges
        if not content.get("supports_resume") and total_size > 0:
            num_threads = 1

        # Download
        self.downloaded_bytes = [0] * num_threads
        ranges = self._split_ranges(total_size, num_threads)
        threads = []

        start_time = time.time()

        for i, (start, end) in enumerate(ranges):
            t = threading.Thread(
                target=self._download_chunk, args=(start, end, i, output_dir)
            )
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        if self.is_cancelled:
            self._cleanup_parts(num_threads, output_dir)
            return False

        # Merge parts
        self._merge_parts(output_path, num_threads, output_dir)

        # Verify (only if we know the expected size)
        if os.path.exists(output_path) and total_size > 0:
            actual_size = os.path.getsize(output_path)
            if actual_size != total_size:
                print(
                    f"Warning: Size mismatch. Expected: {total_size}, Got: {actual_size}"
                )

        return True

    def _split_ranges(self, total_size: int, num_chunks: int):
        """Split file into byte ranges for parallel downloading"""
        chunk_size = math.ceil(total_size / num_chunks)
        return [
            (i * chunk_size, min((i + 1) * chunk_size - 1, total_size - 1))
            for i in range(num_chunks)
        ]

    def _download_chunk(self, start: int, end: int, part_num: int, output_dir: str):
        """Download a specific byte range"""
        headers = {"Range": f"bytes={start}-{end}"}
        part_path = os.path.join(output_dir, f"part_{part_num}.tmp")

        try:
            r = requests.get(self.url, headers=headers, stream=True, timeout=30)

            if r.status_code in (200, 206):
                with open(part_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if self.is_cancelled:
                            return

                        while self.is_paused and not self.is_cancelled:
                            time.sleep(0.1)

                        if chunk:
                            f.write(chunk)
                            with self.lock:
                                self.downloaded_bytes[part_num] += len(chunk)

        except Exception as e:
            print(f"[Thread-{part_num}] Error: {e}")

    def _merge_parts(self, output_path: str, num_threads: int, output_dir: str):
        """Merge downloaded parts into final file"""
        with open(output_path, "wb") as outfile:
            for i in range(num_threads):
                part_path = os.path.join(output_dir, f"part_{i}.tmp")
                if os.path.exists(part_path):
                    with open(part_path, "rb") as part:
                        outfile.write(part.read())
                    os.remove(part_path)

    def _cleanup_parts(self, num_threads: int, output_dir: str):
        """Remove temporary part files"""
        for i in range(num_threads):
            part_path = os.path.join(output_dir, f"part_{i}.tmp")
            if os.path.exists(part_path):
                try:
                    os.remove(part_path)
                except:
                    pass

    def pause(self):
        """Pause download"""
        self.is_paused = True

    def resume(self):
        """Resume download"""
        self.is_paused = False

    def cancel(self):
        """Cancel download"""
        self.is_cancelled = True

    def get_progress(self):
        """Get total bytes downloaded"""
        with self.lock:
            return sum(self.downloaded_bytes)
