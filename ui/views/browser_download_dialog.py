"""
Browser Engine Download & Progress Dialog for OXBROWSER.
Provides modern, styled real-time progress feedback when downloading
browser engines (Camoufox, Chromium) on first launch.
"""

import os
import sys
import logging
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QFrame, QWidget
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont

from engine.browser_downloader import BrowserDownloader, CancellationToken

logger = logging.getLogger("BrowserDownloadDialog")


class _DownloadWorker(QThread):
    """Background worker thread to perform streaming engine downloads without UI stutter."""
    progress_signal = pyqtSignal(int, int, float, str, str)  # downloaded, total, speed, eta, phase
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, engine_type: str = "camoufox", cancel_token: Optional[CancellationToken] = None):
        super().__init__()
        self.engine_type = engine_type.lower().strip()
        self.cancel_token = cancel_token or CancellationToken()

    def run(self):
        def cb(downloaded: int, total: int, speed: float, eta: str, phase: str):
            self.progress_signal.emit(downloaded, total, speed, eta, phase)

        try:
            if self.engine_type in ["camoufox", "firefox"]:
                success, msg = BrowserDownloader.download_camoufox(
                    progress_callback=cb,
                    cancel_token=self.cancel_token
                )
            elif self.engine_type == "playwright":
                success, msg = BrowserDownloader.download_playwright_chromium(
                    progress_callback=cb,
                    cancel_token=self.cancel_token
                )
            else:
                success, msg = True, f"No download needed for engine '{self.engine_type}'."

            self.finished_signal.emit(success, msg)
        except Exception as e:
            logger.error(f"[_DownloadWorker] Unhandled download error: {e}", exc_info=True)
            self.finished_signal.emit(False, str(e))


class BrowserDownloadDialog(QDialog):
    """
    Modern modal dialog displaying real-time download progress, speed,
    and extraction status for browser engines.
    """

    def __init__(self, engine_type: str = "camoufox", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.engine_type = engine_type.lower().strip()
        self.cancel_token = CancellationToken()
        self.download_success: bool = False
        self.worker: Optional[_DownloadWorker] = None

        self._init_ui()
        self._start_download()

    def _init_ui(self):
        engine_title = "Camoufox Stealth Engine" if self.engine_type in ["camoufox", "firefox"] else "Playwright Chromium"
        self.setWindowTitle("OXBROWSER - Engine Setup")
        self.setFixedSize(540, 270)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        # Main styling container
        self.setStyleSheet("""
            QDialog {
                background-color: #161618;
                border: 1px solid #2d2d2f;
                border-radius: 10px;
            }
            QLabel {
                color: #e5e5e5;
            }
            QPushButton.SecondaryButton {
                background-color: #232325;
                color: #e5e5e5;
                font-weight: 500;
                border: 1px solid #333333;
                border-radius: 6px;
                padding: 7px 18px;
                font-size: 12px;
            }
            QPushButton.SecondaryButton:hover {
                background-color: #2a2a2d;
                color: #ffffff;
                border-color: #404040;
            }
            QProgressBar {
                background-color: #202022;
                border: 1px solid #333333;
                border-radius: 6px;
                text-align: center;
                color: #ffffff;
                font-size: 11px;
                font-weight: 700;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #00adb5);
                border-radius: 5px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Header Badge & Title
        header_layout = QVBoxLayout()
        header_layout.setSpacing(4)

        badge_row = QHBoxLayout()
        self.lbl_badge = QLabel("⚡ BROWSER RUNTIME SETUP")
        self.lbl_badge.setStyleSheet("""
            background-color: rgba(37, 99, 235, 0.2);
            color: #60a5fa;
            border: 1px solid rgba(59, 130, 246, 0.35);
            border-radius: 4px;
            padding: 2px 7px;
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 0.5px;
        """)
        badge_row.addWidget(self.lbl_badge)
        badge_row.addStretch()
        header_layout.addLayout(badge_row)

        self.lbl_title = QLabel(f"Downloading {engine_title}")
        font_title = QFont()
        font_title.setPointSize(14)
        font_title.setBold(True)
        self.lbl_title.setFont(font_title)
        self.lbl_title.setStyleSheet("color: #ffffff;")
        header_layout.addWidget(self.lbl_title)

        self.lbl_desc = QLabel(
            "First-time setup: Hardened anti-detect browser binaries are required (~470 MB). "
            "Please wait while the engine is downloaded and verified."
        )
        self.lbl_desc.setStyleSheet("color: #9ca3af; font-size: 11px;")
        self.lbl_desc.setWordWrap(True)
        header_layout.addWidget(self.lbl_desc)

        layout.addLayout(header_layout)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(22)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # Metrics Row (Size & Speed/ETA)
        metrics_layout = QHBoxLayout()
        self.lbl_size = QLabel("0.0 MB / -- MB (0%)")
        self.lbl_size.setStyleSheet("color: #d1d5db; font-size: 11px; font-weight: 600;")
        metrics_layout.addWidget(self.lbl_size)

        metrics_layout.addStretch()

        self.lbl_speed = QLabel("⚡ Connecting...")
        self.lbl_speed.setStyleSheet("color: #00adb5; font-size: 11px; font-weight: 600;")
        metrics_layout.addWidget(self.lbl_speed)
        layout.addLayout(metrics_layout)

        # Activity/Phase status box
        self.status_box = QFrame()
        self.status_box.setStyleSheet("background-color: #121214; border: 1px solid #262629; border-radius: 6px;")
        box_layout = QHBoxLayout(self.status_box)
        box_layout.setContentsMargins(10, 8, 10, 8)

        self.lbl_status = QLabel("Initializing download stream...")
        self.lbl_status.setStyleSheet("color: #9ca3af; font-size: 11px; font-family: monospace;")
        box_layout.addWidget(self.lbl_status)
        layout.addWidget(self.status_box)

        # Bottom Button Row
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setProperty("class", "SecondaryButton")
        self.btn_cancel.setFixedWidth(90)
        self.btn_cancel.clicked.connect(self._on_cancel_clicked)
        btn_layout.addWidget(self.btn_cancel)

        layout.addLayout(btn_layout)

    def _start_download(self):
        self.worker = _DownloadWorker(engine_type=self.engine_type, cancel_token=self.cancel_token)
        self.worker.progress_signal.connect(self._on_progress)
        self.worker.finished_signal.connect(self._on_finished)
        self.worker.start()

    def _on_progress(self, downloaded: int, total: int, speed: float, eta: str, phase: str):
        if total > 0:
            pct = int((downloaded / total) * 100)
            self.progress_bar.setValue(pct)
            dl_mb = downloaded / (1024 * 1024)
            tot_mb = total / (1024 * 1024)
            self.lbl_size.setText(f"{dl_mb:.1f} MB / {tot_mb:.1f} MB ({pct}%)")
        else:
            self.lbl_size.setText(f"{downloaded / (1024 * 1024):.1f} MB")

        if speed > 0:
            sp_mb = speed / (1024 * 1024)
            self.lbl_speed.setText(f"⚡ {sp_mb:.2f} MB/s • ETA: {eta}")
        elif eta != "--":
            self.lbl_speed.setText(f"ETA: {eta}")

        self.lbl_status.setText(phase)

    def _on_finished(self, success: bool, message: str):
        self.download_success = success
        if success:
            self.progress_bar.setValue(100)
            self.lbl_speed.setText("⚡ Finished")
            self.lbl_status.setText(f"✓ {message}")
            self.lbl_status.setStyleSheet("color: #10b981; font-size: 11px; font-weight: 600;")
            self.btn_cancel.setEnabled(False)
            QTimer.singleShot(700, self.accept)
        else:
            self.lbl_speed.setText("Error")
            self.lbl_status.setText(f"✕ {message}")
            self.lbl_status.setStyleSheet("color: #ef4444; font-size: 11px; font-weight: 600;")
            self.btn_cancel.setText("Close")
            self.btn_cancel.setEnabled(True)

    def _on_cancel_clicked(self):
        if not self.download_success and self.worker and self.worker.isRunning():
            self.lbl_status.setText("Aborting download...")
            self.cancel_token.cancel()
            self.worker.wait(2000)
        self.reject()

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.cancel_token.cancel()
            self.worker.wait(1500)
        super().closeEvent(event)

    @classmethod
    def ensure_engine_ready(cls, parent: Optional[QWidget] = None, engine_type: str = "camoufox") -> bool:
        """
        Pre-flight check:
        1. If engine is already downloaded and verified on disk, returns True immediately (zero delay).
        2. If engine is missing or outdated, displays the modal progress dialog and executes download.
        3. Returns True if engine is ready, or False if user cancelled / download failed.
        """
        is_ready, msg = BrowserDownloader.is_engine_installed(engine_type)
        if is_ready:
            logger.debug(f"[BrowserDownloadDialog] Engine '{engine_type}' is ready: {msg}")
            return True

        logger.info(f"[BrowserDownloadDialog] Engine '{engine_type}' requires download: {msg}. Opening progress dialog...")
        dlg = cls(engine_type=engine_type, parent=parent)
        result = dlg.exec()
        return bool(dlg.download_success or result == QDialog.DialogCode.Accepted)
