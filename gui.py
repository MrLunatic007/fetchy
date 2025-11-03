import sys
import os

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QProgressBar,
    QLabel,
    QFileDialog,
    QSpinBox,
    QMessageBox,
    QHeaderView,
    QMenu,
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QAction
import threading
import time
import requests
from connection_manager import Connector
import math


class DownloadWorker(QThread):
    progress = pyqtSignal(int, float, str)  # row, progress, speed
    finished = pyqtSignal(int, bool, str)  # row, success, message

    def __init__(self, url, save_path, num_threads, row):
        super().__init__()
        self.url = url
        self.save_path = save_path
        self.num_threads = num_threads
        self.row = row
        self.is_running = True
        self.is_paused = False
        self.downloaded = None
        self.lock = threading.Lock()

    def run(self):
        try:
            # Add User-Agent header
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
            }

            # Get file info with longer timeout
            connector = Connector(self.url)
            content = connector.connect()

            if not content:
                self.finished.emit(self.row, False, "Failed to connect")
                return

            total_size = int(content.get("size", 0))
            if total_size == 0:
                self.finished.emit(self.row, False, "Invalid file size")
                return

            # Check if server supports ranges
            supports_ranges = content.get("supports_resume", False)
            actual_threads = 1 if not supports_ranges else self.num_threads

            if actual_threads != self.num_threads:
                print(
                    f"Server doesn't support ranges, using 1 thread instead of {self.num_threads}"
                )

            # Download with progress tracking
            success = self._parallel_download(total_size, actual_threads)

            if success and self.is_running and not self.is_paused:
                # Merge files
                self._merge_parts(actual_threads)
                self.finished.emit(self.row, True, "Completed")
            elif not self.is_running:
                self._cleanup_parts(actual_threads)
                self.finished.emit(self.row, False, "Cancelled")

        except requests.exceptions.Timeout:
            self.finished.emit(self.row, False, "Connection timeout")
        except requests.exceptions.ConnectionError:
            self.finished.emit(self.row, False, "Connection error")
        except Exception as e:
            self.finished.emit(self.row, False, str(e))

    def _parallel_download(self, total_size, num_threads):
        ranges = self._split_ranges(total_size, num_threads)
        threads = []
        self.downloaded = [0] * num_threads
        start_time = time.time()
        last_update = start_time

        for i, (start, end) in enumerate(ranges):
            t = threading.Thread(target=self._download_chunk, args=(start, end, i))
            t.daemon = True
            t.start()
            threads.append(t)

        # Monitor progress
        while any(t.is_alive() for t in threads):
            if not self.is_running:
                break

            while self.is_paused and self.is_running:
                time.sleep(0.1)

            current_time = time.time()

            # Update progress every 0.5 seconds
            if current_time - last_update >= 0.5:
                with self.lock:
                    total_downloaded = sum(self.downloaded)

                progress = (total_downloaded / total_size) * 100

                elapsed = current_time - start_time
                speed = total_downloaded / elapsed if elapsed > 0 else 0
                speed_mb = speed / (1024 * 1024)

                self.progress.emit(self.row, progress, f"{speed_mb:.2f} MB/s")
                last_update = current_time

            time.sleep(0.1)

        for t in threads:
            t.join(timeout=1.0)

        return self.is_running and not self.is_paused

    def _split_ranges(self, total_size, num_chunks):
        chunks = []
        chunk_size = math.ceil(total_size / num_chunks)
        for i in range(num_chunks):
            start = i * chunk_size
            end = min(start + chunk_size - 1, total_size - 1)
            chunks.append((start, end))
        return chunks

    def _download_chunk(self, start, end, part_num):
        headers = {
            "Range": f"bytes={start}-{end}",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        }
        part_path = f"{self.save_path}.part{part_num}"

        try:
            # Increase timeout for GUI
            r = requests.get(self.url, headers=headers, stream=True, timeout=60)

            if r.status_code in (200, 206):
                with open(part_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if not self.is_running:
                            return

                        while self.is_paused and self.is_running:
                            time.sleep(0.1)

                        if chunk:
                            f.write(chunk)
                            with self.lock:
                                self.downloaded[part_num] += len(chunk)
            else:
                print(f"Chunk {part_num} failed with status {r.status_code}")

        except requests.exceptions.Timeout:
            print(f"Chunk {part_num} timeout")
        except Exception as e:
            print(f"Chunk {part_num} error: {e}")

    def _merge_parts(self, num_threads):
        try:
            with open(self.save_path, "wb") as outfile:
                for i in range(num_threads):
                    part_path = f"{self.save_path}.part{i}"
                    if os.path.exists(part_path):
                        with open(part_path, "rb") as infile:
                            outfile.write(infile.read())
                        os.remove(part_path)
        except Exception as e:
            print(f"Error merging: {e}")

    def _cleanup_parts(self, num_threads):
        for i in range(num_threads):
            part_path = f"{self.save_path}.part{i}"
            if os.path.exists(part_path):
                try:
                    os.remove(part_path)
                except:
                    pass

    def pause(self):
        self.is_paused = True

    def resume(self):
        self.is_paused = False

    def stop(self):
        self.is_running = False


class DownloadManagerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.downloads = []
        self.workers = {}
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Fetchy Download Manager")
        self.setGeometry(100, 100, 1000, 600)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # URL input section
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("URL:"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Enter download URL...")
        self.url_input.returnPressed.connect(self.add_download)
        url_layout.addWidget(self.url_input)

        url_layout.addWidget(QLabel("Threads:"))
        self.threads_spin = QSpinBox()
        self.threads_spin.setMinimum(1)
        self.threads_spin.setMaximum(16)
        self.threads_spin.setValue(4)
        url_layout.addWidget(self.threads_spin)

        self.add_btn = QPushButton("Add Download")
        self.add_btn.clicked.connect(self.add_download)
        url_layout.addWidget(self.add_btn)

        layout.addLayout(url_layout)

        # Download table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["Filename", "Size", "Progress", "Speed", "Status", "Actions"]
        )
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.table)

        # Control buttons
        btn_layout = QHBoxLayout()

        self.pause_btn = QPushButton("Pause Selected")
        self.pause_btn.clicked.connect(self.pause_selected)
        btn_layout.addWidget(self.pause_btn)

        self.resume_btn = QPushButton("Resume Selected")
        self.resume_btn.clicked.connect(self.resume_selected)
        btn_layout.addWidget(self.resume_btn)

        self.cancel_btn = QPushButton("Cancel Selected")
        self.cancel_btn.clicked.connect(self.cancel_selected)
        btn_layout.addWidget(self.cancel_btn)

        self.clear_btn = QPushButton("Clear Completed")
        self.clear_btn.clicked.connect(self.clear_completed)
        btn_layout.addWidget(self.clear_btn)

        layout.addLayout(btn_layout)

        # Status bar
        self.statusBar().showMessage("Ready")

    def add_download(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Error", "Please enter a URL")
            return

        if not url.startswith(("http://", "https://")):
            QMessageBox.warning(
                self, "Error", "URL must start with http:// or https://"
            )
            return

        self.statusBar().showMessage("Connecting to server...")
        QApplication.processEvents()

        try:
            # Get file info with timeout
            connector = Connector(url)
            content = connector.connect()

            if not content:
                QMessageBox.warning(
                    self,
                    "Error",
                    "Failed to connect to URL. Check your internet connection and try again.",
                )
                self.statusBar().showMessage("Connection failed")
                return

            filename = content.get("filename", "download_file")
            size = int(content.get("size", 0))
            size_mb = size / (1024 * 1024)

            # Ask for save location
            save_path, _ = QFileDialog.getSaveFileName(
                self, "Save File", filename, "All Files (*.*)"
            )

            if not save_path:
                self.statusBar().showMessage("Download cancelled")
                return

            # Add to table
            row = self.table.rowCount()
            self.table.insertRow(row)

            self.table.setItem(row, 0, QTableWidgetItem(os.path.basename(save_path)))
            self.table.setItem(row, 1, QTableWidgetItem(f"{size_mb:.2f} MB"))

            progress_bar = QProgressBar()
            self.table.setCellWidget(row, 2, progress_bar)

            self.table.setItem(row, 3, QTableWidgetItem("0 MB/s"))
            self.table.setItem(row, 4, QTableWidgetItem("Starting..."))

            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(0, 0, 0, 0)

            pause_btn = QPushButton("⏸")
            pause_btn.setMaximumWidth(40)
            pause_btn.clicked.connect(lambda: self.pause_download(row))
            action_layout.addWidget(pause_btn)

            stop_btn = QPushButton("⏹")
            stop_btn.setMaximumWidth(40)
            stop_btn.clicked.connect(lambda: self.cancel_download(row))
            action_layout.addWidget(stop_btn)

            self.table.setCellWidget(row, 5, action_widget)

            # Start download
            worker = DownloadWorker(url, save_path, self.threads_spin.value(), row)
            worker.progress.connect(self.update_progress)
            worker.finished.connect(self.download_finished)
            worker.start()

            self.workers[row] = worker
            self.url_input.clear()
            self.statusBar().showMessage(f"Download started: {filename}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error adding download: {str(e)}")
            self.statusBar().showMessage("Error occurred")

    def update_progress(self, row, progress, speed):
        if row < self.table.rowCount():
            progress_bar = self.table.cellWidget(row, 2)
            if progress_bar:
                progress_bar.setValue(int(progress))

            speed_item = self.table.item(row, 3)
            if speed_item:
                speed_item.setText(speed)

            status_item = self.table.item(row, 4)
            if status_item:
                status_item.setText("Downloading...")

    def download_finished(self, row, success, message):
        if row < self.table.rowCount():
            status = "Completed" if success else f"Failed: {message}"
            status_item = self.table.item(row, 4)
            if status_item:
                status_item.setText(status)

            if success:
                progress_bar = self.table.cellWidget(row, 2)
                if progress_bar:
                    progress_bar.setValue(100)
                self.statusBar().showMessage(
                    f"Download completed: {self.table.item(row, 0).text()}"
                )
            else:
                self.statusBar().showMessage(f"Download failed: {message}")

    def pause_download(self, row):
        if row in self.workers:
            self.workers[row].pause()
            status_item = self.table.item(row, 4)
            if status_item:
                status_item.setText("Paused")

    def resume_download(self, row):
        if row in self.workers:
            self.workers[row].resume()
            status_item = self.table.item(row, 4)
            if status_item:
                status_item.setText("Resuming...")

    def cancel_download(self, row):
        if row in self.workers:
            self.workers[row].stop()
            status_item = self.table.item(row, 4)
            if status_item:
                status_item.setText("Cancelled")

    def pause_selected(self):
        row = self.table.currentRow()
        if row >= 0:
            self.pause_download(row)

    def resume_selected(self):
        row = self.table.currentRow()
        if row >= 0:
            self.resume_download(row)

    def cancel_selected(self):
        row = self.table.currentRow()
        if row >= 0:
            self.cancel_download(row)

    def clear_completed(self):
        rows_to_remove = []
        for row in range(self.table.rowCount()):
            status_item = self.table.item(row, 4)
            if status_item:
                status = status_item.text()
                if "Completed" in status or "Failed" in status or "Cancelled" in status:
                    rows_to_remove.append(row)

        for row in reversed(rows_to_remove):
            self.table.removeRow(row)
            if row in self.workers:
                del self.workers[row]

        self.statusBar().showMessage(f"Cleared {len(rows_to_remove)} downloads")

    def show_context_menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row >= 0:
            menu = QMenu()
            pause_action = menu.addAction("Pause")
            resume_action = menu.addAction("Resume")
            cancel_action = menu.addAction("Cancel")

            action = menu.exec(self.table.viewport().mapToGlobal(pos))

            if action == pause_action:
                self.pause_download(row)
            elif action == resume_action:
                self.resume_download(row)
            elif action == cancel_action:
                self.cancel_download(row)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DownloadManagerGUI()
    window.show()
    sys.exit(app.exec())
