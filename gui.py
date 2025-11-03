#!/usr/bin/env python3
import sys
import os
import threading
import time
import math
import requests
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
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QAction

from connection_manager import Connector


class DownloadWorker(QThread):
    """Worker thread for downloading files"""

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
        """Execute download"""
        try:
            # Get file info
            connector = Connector(self.url, timeout=60)
            content = connector.connect()

            if not content:
                self.finished.emit(self.row, False, "Connection failed")
                return

            # Handle None size
            size = content.get("size")
            total_size = int(size) if size else 0

            if total_size == 0:
                self.finished.emit(self.row, False, "Invalid file size")
                return

            # Adjust threads based on server support
            supports_ranges = content.get("supports_resume", False)
            num_threads = 1 if not supports_ranges else self.num_threads

            # Download
            if self._parallel_download(total_size, num_threads):
                self._merge_parts(num_threads)
                self.finished.emit(self.row, True, "Completed")
            else:
                self._cleanup_parts(num_threads)
                self.finished.emit(self.row, False, "Cancelled")

        except requests.exceptions.Timeout:
            self.finished.emit(self.row, False, "Connection timeout")
        except Exception as e:
            self.finished.emit(self.row, False, str(e))

    def _parallel_download(self, total_size, num_threads):
        """Download file in parallel chunks"""
        ranges = self._split_ranges(total_size, num_threads)
        threads = []
        self.downloaded = [0] * num_threads
        start_time = time.time()
        last_update = start_time

        # Start download threads
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
            if current_time - last_update >= 0.5:
                with self.lock:
                    total_downloaded = sum(self.downloaded)

                progress_pct = (total_downloaded / total_size) * 100
                elapsed = current_time - start_time
                speed_mbps = (
                    (total_downloaded / elapsed / (1024 * 1024)) if elapsed > 0 else 0
                )

                self.progress.emit(self.row, progress_pct, f"{speed_mbps:.2f} MB/s")
                last_update = current_time

            time.sleep(0.1)

        for t in threads:
            t.join(timeout=1.0)

        return self.is_running and not self.is_paused

    def _split_ranges(self, total_size, num_chunks):
        """Split file into byte ranges"""
        chunk_size = math.ceil(total_size / num_chunks)
        return [
            (i * chunk_size, min((i + 1) * chunk_size - 1, total_size - 1))
            for i in range(num_chunks)
        ]

    def _download_chunk(self, start, end, part_num):
        """Download a specific byte range"""
        headers = {
            "Range": f"bytes={start}-{end}",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        }
        part_path = f"{self.save_path}.part{part_num}"

        try:
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

        except Exception as e:
            print(f"Chunk {part_num} error: {e}")

    def _merge_parts(self, num_threads):
        """Merge downloaded parts"""
        with open(self.save_path, "wb") as outfile:
            for i in range(num_threads):
                part_path = f"{self.save_path}.part{i}"
                if os.path.exists(part_path):
                    with open(part_path, "rb") as infile:
                        outfile.write(infile.read())
                    os.remove(part_path)

    def _cleanup_parts(self, num_threads):
        """Remove temporary files"""
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
    """Main GUI window for download manager"""

    def __init__(self):
        super().__init__()
        self.workers = {}
        self.init_ui()

    def init_ui(self):
        """Initialize user interface"""
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
        self.threads_spin.setRange(1, 16)
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

        buttons = [
            ("Pause Selected", self.pause_selected),
            ("Resume Selected", self.resume_selected),
            ("Cancel Selected", self.cancel_selected),
            ("Clear Completed", self.clear_completed),
        ]

        for text, handler in buttons:
            btn = QPushButton(text)
            btn.clicked.connect(handler)
            btn_layout.addWidget(btn)

        layout.addLayout(btn_layout)

        self.statusBar().showMessage("Ready")

    def add_download(self):
        """Add new download to table"""
        url = self.url_input.text().strip()

        if not url:
            QMessageBox.warning(self, "Error", "Please enter a URL")
            return

        if not url.startswith(("http://", "https://")):
            QMessageBox.warning(
                self, "Error", "URL must start with http:// or https://"
            )
            return

        self.statusBar().showMessage("Connecting...")
        QApplication.processEvents()

        try:
            # Get file info
            connector = Connector(url)
            content = connector.connect()

            if not content:
                QMessageBox.warning(self, "Error", "Failed to connect to URL")
                self.statusBar().showMessage("Connection failed")
                return

            filename = content.get("filename", "download_file")
            size_mb = int(content.get("size", 0)) / (1024 * 1024)

            # Choose save location
            save_path, _ = QFileDialog.getSaveFileName(
                self, "Save File", filename, "All Files (*.*)"
            )

            if not save_path:
                self.statusBar().showMessage("Cancelled")
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

            # Action buttons
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
            QMessageBox.critical(self, "Error", f"Failed to add download: {str(e)}")
            self.statusBar().showMessage("Error")

    def update_progress(self, row, progress, speed):
        """Update download progress in table"""
        if row < self.table.rowCount():
            if progress_bar := self.table.cellWidget(row, 2):
                progress_bar.setValue(int(progress))

            if speed_item := self.table.item(row, 3):
                speed_item.setText(speed)

            if status_item := self.table.item(row, 4):
                status_item.setText("Downloading...")

    def download_finished(self, row, success, message):
        """Handle download completion"""
        if row < self.table.rowCount():
            status = "Completed" if success else f"Failed: {message}"

            if status_item := self.table.item(row, 4):
                status_item.setText(status)

            if success:
                if progress_bar := self.table.cellWidget(row, 2):
                    progress_bar.setValue(100)
                filename = self.table.item(row, 0).text()
                self.statusBar().showMessage(f"Completed: {filename}")
            else:
                self.statusBar().showMessage(f"Failed: {message}")

    def pause_download(self, row):
        if row in self.workers:
            self.workers[row].pause()
            if item := self.table.item(row, 4):
                item.setText("Paused")

    def resume_download(self, row):
        if row in self.workers:
            self.workers[row].resume()
            if item := self.table.item(row, 4):
                item.setText("Resuming...")

    def cancel_download(self, row):
        if row in self.workers:
            self.workers[row].stop()
            if item := self.table.item(row, 4):
                item.setText("Cancelled")

    def pause_selected(self):
        if (row := self.table.currentRow()) >= 0:
            self.pause_download(row)

    def resume_selected(self):
        if (row := self.table.currentRow()) >= 0:
            self.resume_download(row)

    def cancel_selected(self):
        if (row := self.table.currentRow()) >= 0:
            self.cancel_download(row)

    def clear_completed(self):
        """Remove completed/failed downloads"""
        rows_to_remove = []
        for row in range(self.table.rowCount()):
            if item := self.table.item(row, 4):
                if any(s in item.text() for s in ["Completed", "Failed", "Cancelled"]):
                    rows_to_remove.append(row)

        for row in reversed(rows_to_remove):
            self.table.removeRow(row)
            if row in self.workers:
                del self.workers[row]

        self.statusBar().showMessage(f"Cleared {len(rows_to_remove)} downloads")

    def show_context_menu(self, pos):
        """Show right-click context menu"""
        if (row := self.table.rowAt(pos.y())) >= 0:
            menu = QMenu()
            actions = {
                "Pause": lambda: self.pause_download(row),
                "Resume": lambda: self.resume_download(row),
                "Cancel": lambda: self.cancel_download(row),
            }

            for name, handler in actions.items():
                action = menu.addAction(name)
                action.triggered.connect(handler)

            menu.exec(self.table.viewport().mapToGlobal(pos))


def main():
    app = QApplication(sys.argv)
    window = DownloadManagerGUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
