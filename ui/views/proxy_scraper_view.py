from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QCheckBox, QComboBox, QProgressBar, QLabel, QMessageBox,
    QHeaderView, QFileDialog, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon
import asyncio
import qasync
import json
import os
from typing import List, Dict, Optional
from storage.proxy_manager import ProxyManager
from engine.proxy_scraper import ProxyScraperEngine


class NumericTableWidgetItem(QTableWidgetItem):
    """QTableWidgetItem with numerical sorting support for latency ms values."""

    def __init__(self, text: str, sort_val: float):
        super().__init__(text)
        self.sort_val = sort_val

    def __lt__(self, other):
        if isinstance(other, NumericTableWidgetItem):
            return self.sort_val < other.sort_val
        return super().__lt__(other)


class ProxyScraperView(QWidget):
    """High-Performance Proxy Scraper, Latency Benchmarker & Exporter UI View."""

    proxies_imported = pyqtSignal()

    def __init__(self, proxy_manager: Optional[ProxyManager] = None, parent=None):
        super().__init__(parent)
        self.proxy_manager = proxy_manager or ProxyManager()
        self.engine = ProxyScraperEngine()
        self.raw_results: List[Dict] = []
        self.is_running = False
        self._init_ui()

    def _get_icon(self, name):
        return QIcon(os.path.join(os.path.dirname(__file__), "..", "assets", "icons", f"{name}.svg"))

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # 1. Top Controls Bar (Protocols, Threading, Filters)
        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)

        top_bar.addWidget(QLabel("<b>Protocols:</b>"))
        self.cb_http = QCheckBox("HTTP")
        self.cb_http.setChecked(True)
        self.cb_socks4 = QCheckBox("SOCKS4")
        self.cb_socks4.setChecked(True)
        self.cb_socks5 = QCheckBox("SOCKS5")
        self.cb_socks5.setChecked(True)
        top_bar.addWidget(self.cb_http)
        top_bar.addWidget(self.cb_socks4)
        top_bar.addWidget(self.cb_socks5)

        top_bar.addSpacing(15)
        top_bar.addWidget(QLabel("<b>Threads:</b>"))
        self.combo_threads = QComboBox()
        self.combo_threads.addItems(["25 Threads", "50 Threads", "100 Threads"])
        self.combo_threads.setCurrentIndex(1)
        top_bar.addWidget(self.combo_threads)

        top_bar.addSpacing(15)
        top_bar.addWidget(QLabel("<b>Max Latency:</b>"))
        self.combo_speed_filter = QComboBox()
        self.combo_speed_filter.addItems([
            "All Speeds",
            "< 500 ms (Ultra Fast)",
            "< 1500 ms (Fast)",
            "< 3000 ms (Medium)"
        ])
        self.combo_speed_filter.currentIndexChanged.connect(self._apply_filters)
        top_bar.addWidget(self.combo_speed_filter)

        top_bar.addStretch()

        # Action Buttons
        self.btn_start = QPushButton(" Start Scrape & Test")
        self.btn_start.setIcon(self._get_icon("play"))
        self.btn_start.setProperty("class", "PrimaryButton")
        self.btn_start.clicked.connect(self._start_scrape_and_check)
        top_bar.addWidget(self.btn_start)

        self.btn_stop = QPushButton(" Stop")
        self.btn_stop.setIcon(self._get_icon("square"))
        self.btn_stop.setProperty("class", "DangerButton")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop_scrape)
        top_bar.addWidget(self.btn_stop)

        layout.addLayout(top_bar)

        # 2. Progress & Status Summary Bar
        status_box = QHBoxLayout()
        status_box.setSpacing(12)
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(18)
        status_box.addWidget(self.progress_bar, 2)

        self.lbl_status = QLabel("Ready to scrape proxies.")
        self.lbl_status.setStyleSheet("font-weight: 700; color: #94a3b8; font-size: 11px;")
        status_box.addWidget(self.lbl_status, 3)

        layout.addLayout(status_box)

        # 3. Action Toolbar (Import to Proxies Tab, Copy, Export, Clear)
        action_bar = QHBoxLayout()
        action_bar.setSpacing(8)

        self.btn_import_all = QPushButton(" Import All Working")
        self.btn_import_all.setIcon(self._get_icon("folder-open"))
        self.btn_import_all.setProperty("class", "PrimaryButton")
        self.btn_import_all.clicked.connect(self._import_all_working)
        action_bar.addWidget(self.btn_import_all)

        self.btn_import_selected = QPushButton(" Import Selected")
        self.btn_import_selected.setIcon(self._get_icon("download"))
        self.btn_import_selected.setProperty("class", "SecondaryButton")
        self.btn_import_selected.clicked.connect(self._import_selected)
        action_bar.addWidget(self.btn_import_selected)

        self.btn_copy = QPushButton(" Copy Working")
        self.btn_copy.setIcon(self._get_icon("copy"))
        self.btn_copy.setProperty("class", "SecondaryButton")
        self.btn_copy.clicked.connect(self._copy_working)
        action_bar.addWidget(self.btn_copy)

        self.btn_export = QPushButton(" Export TXT")
        self.btn_export.setIcon(self._get_icon("file-text"))
        self.btn_export.setProperty("class", "SecondaryButton")
        self.btn_export.clicked.connect(self._export_to_file)
        action_bar.addWidget(self.btn_export)

        self.btn_clear = QPushButton(" Clear All")
        self.btn_clear.setIcon(self._get_icon("trash-2"))
        self.btn_clear.setProperty("class", "DangerButton")
        self.btn_clear.setToolTip("Clear all scraped results from the table")
        self.btn_clear.clicked.connect(self._clear_all)
        action_bar.addWidget(self.btn_clear)

        action_bar.addStretch()
        layout.addLayout(action_bar)

        # 4. Results QTableWidget with Speed Sorting
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Status", "Host:Port", "Type", "Latency (ms)", "Country", "City / ISP", "Anonymity"
        ])
        
        v_header = self.table.verticalHeader()
        if v_header:
            v_header.setVisible(False)
            v_header.setDefaultSectionSize(40)

        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)

        header = self.table.horizontalHeader()
        if header:
            header.setHighlightSections(False)
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(0, 110)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(2, 90)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(3, 110)

        self.table.setSortingEnabled(True)
        layout.addWidget(self.table)

    @qasync.asyncSlot()
    async def _start_scrape_and_check(self):
        if self.is_running:
            return

        protocols = []
        if self.cb_http.isChecked():
            protocols.append("http")
        if self.cb_socks4.isChecked():
            protocols.append("socks4")
        if self.cb_socks5.isChecked():
            protocols.append("socks5")

        if not protocols:
            QMessageBox.warning(self, "Warning", "Please select at least one protocol (HTTP, SOCKS4, or SOCKS5).")
            return

        threads_text = self.combo_threads.currentText()
        concurrency = 50
        if "25" in threads_text:
            concurrency = 25
        elif "100" in threads_text:
            concurrency = 100

        self.is_running = True
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress_bar.setValue(0)
        self.raw_results.clear()
        self.table.setRowCount(0)
        self.lbl_status.setText("⌕ Scraping live proxy sources...")

        # Step 1: Scrape Proxies
        scraped_list = await self.engine.scrape_proxies(protocols)
        if not scraped_list or not self.is_running:
            self.lbl_status.setText("No proxies scraped or process cancelled.")
            self._reset_buttons()
            return

        total_scraped = len(scraped_list)
        self.lbl_status.setText(f"Found {total_scraped} raw proxies. Testing latency & anonymity ({concurrency} workers)...")
        self.progress_bar.setMaximum(total_scraped)

        # Step 2: Batch Check Proxies with Live Progress
        checked_count = 0
        working_count = 0
        fastest_ms = 999999.0

        def on_progress(chk: int, tot: int, res: Dict):
            nonlocal checked_count, working_count, fastest_ms
            checked_count = chk
            if res.get("is_working"):
                working_count += 1
                lat = res.get("latency_ms", 999999.0)
                if 0 < lat < fastest_ms:
                    fastest_ms = lat
                self._add_proxy_row(res)

            self.raw_results.append(res)
            self.progress_bar.setValue(chk)
            fast_str = f"{fastest_ms:.1f}ms" if fastest_ms < 999999.0 else "N/A"
            self.lbl_status.setText(
                f"Scraped: {total_scraped} | Checked: {chk}/{tot} | Working: ⭍ {working_count} (Fastest: {fast_str})"
            )

        await self.engine.batch_check_proxies(scraped_list, concurrency=concurrency, progress_callback=on_progress)

        self.table.sortItems(3, Qt.SortOrder.AscendingOrder)
        self._apply_filters()
        self.lbl_status.setText(
            f"Done! Scraped: {total_scraped} | Working: ⭍ {working_count} proxies."
        )
        self._reset_buttons()

    def _stop_scrape(self):
        if self.is_running:
            self.engine.cancel()
            self.lbl_status.setText("Stopping scraper task...")
            self._reset_buttons()

    def _reset_buttons(self):
        self.is_running = False
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

    def _add_proxy_row(self, p: Dict):
        if not p.get("is_working"):
            return

        sorting_was_enabled = self.table.isSortingEnabled()
        self.table.setSortingEnabled(False)

        row = self.table.rowCount()
        self.table.insertRow(row)

        status_str = "🟢 Active"
        status_item = QTableWidgetItem(status_str)

        lat_ms = p.get("latency_ms", -1.0)
        lat_str = f"{lat_ms:.1f} ms" if lat_ms > 0 else "-"
        lat_item = NumericTableWidgetItem(lat_str, lat_ms if lat_ms > 0 else 999999.0)

        if lat_ms < 500:
            lat_item.setForeground(Qt.GlobalColor.green)
        elif lat_ms < 1500:
            lat_item.setForeground(Qt.GlobalColor.yellow)
        else:
            lat_item.setForeground(Qt.GlobalColor.darkYellow)

        self.table.setItem(row, 0, status_item)
        self.table.setItem(row, 1, QTableWidgetItem(f"{p.get('host')}:{p.get('port')}"))
        self.table.setItem(row, 2, QTableWidgetItem(p.get('type', 'http').upper()))
        self.table.setItem(row, 3, lat_item)
        self.table.setItem(row, 4, QTableWidgetItem(p.get('country', 'Unknown')))
        self.table.setItem(row, 5, QTableWidgetItem(f"{p.get('city', '')} {p.get('isp', '')}".strip()))
        self.table.setItem(row, 6, QTableWidgetItem(p.get('anonymity', 'Unknown')))

        if sorting_was_enabled:
            self.table.setSortingEnabled(True)

    def _apply_filters(self):
        filter_text = self.combo_speed_filter.currentText()
        max_lat = 999999.0
        if "< 500 ms" in filter_text:
            max_lat = 500.0
        elif "< 1500 ms" in filter_text:
            max_lat = 1500.0
        elif "< 3000 ms" in filter_text:
            max_lat = 3000.0

        for row in range(self.table.rowCount()):
            lat_item = self.table.item(row, 3)
            status_item = self.table.item(row, 0)

            lat_val = getattr(lat_item, "sort_val", 999999.0) if lat_item else 999999.0
            is_active = status_item and "Active" in status_item.text()

            if is_active and lat_val <= max_lat:
                self.table.setRowHidden(row, False)
            elif max_lat == 999999.0:
                self.table.setRowHidden(row, False)
            else:
                self.table.setRowHidden(row, True)

    def _import_all_working(self):
        working_proxies = [p for p in self.raw_results if p.get("is_working")]
        if not working_proxies:
            QMessageBox.information(self, "Info", "No working proxies available to import.")
            return

        imported_count = 0
        for p in working_proxies:
            self.proxy_manager.add_proxy({
                "host": p.get("host"),
                "port": p.get("port"),
                "type": p.get("type", "http"),
                "latency_ms": p.get("latency_ms", -1),
                "status": p.get("status", "🟢 Active")
            })
            imported_count += 1

        QMessageBox.information(self, "Success", f"Successfully imported {imported_count} working proxies to your Proxy Pool!")
        self.proxies_imported.emit()

    def _import_selected(self):
        selected_rows = set(index.row() for index in self.table.selectedIndexes())
        if not selected_rows:
            QMessageBox.information(self, "Info", "Please select proxy rows in the table first.")
            return

        imported_count = 0
        for row in selected_rows:
            host_port_item = self.table.item(row, 1)
            type_item = self.table.item(row, 2)
            lat_item = self.table.item(row, 3)

            if host_port_item and type_item:
                parts = host_port_item.text().split(":")
                if len(parts) == 2:
                    self.proxy_manager.add_proxy({
                        "host": parts[0],
                        "port": int(parts[1]),
                        "type": type_item.text().lower(),
                        "latency_ms": getattr(lat_item, "sort_val", -1),
                        "status": "🟢 Active"
                    })
                    imported_count += 1

        QMessageBox.information(self, "Success", f"Successfully imported {imported_count} selected proxies to your Proxy Pool!")
        self.proxies_imported.emit()

    def _copy_working(self):
        working_lines = [f"{p['host']}:{p['port']}" for p in self.raw_results if p.get("is_working")]
        if not working_lines:
            QMessageBox.information(self, "Info", "No working proxies to copy.")
            return

        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText("\n".join(working_lines))
            QMessageBox.information(self, "Success", f"Copied {len(working_lines)} working proxies to clipboard!")

    def _export_to_file(self):
        working_lines = [f"{p['host']}:{p['port']}" for p in self.raw_results if p.get("is_working")]
        if not working_lines:
            QMessageBox.information(self, "Info", "No working proxies to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Export Working Proxies", "scraped_proxies.txt", "Text Files (*.txt);;JSON Files (*.json)")
        if file_path:
            try:
                if file_path.endswith(".json"):
                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump([p for p in self.raw_results if p.get("is_working")], f, indent=4)
                else:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write("\n".join(working_lines))
                QMessageBox.information(self, "Success", f"Exported proxies to {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not export proxies: {e}")

    def _clear_all(self):
        if self.is_running:
            QMessageBox.warning(self, "Warning", "Please stop the active scraping process before clearing.")
            return

        self.raw_results.clear()
        self.table.setRowCount(0)
        self.progress_bar.setValue(0)
        self.lbl_status.setText("Tabelle geleert. Bereit zum Scrapen.")

