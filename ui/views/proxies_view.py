from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QFileDialog, QInputDialog, QMessageBox, QHeaderView, QLabel,
    QProgressBar
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon
from typing import Dict, Any, List, Optional
import random
import os
import qasync
import asyncio

from storage.proxy_manager import ProxyManager
from storage.profile_manager import ProfileManager
from engine.proxy_checker import ProxyChecker
from engine.google_proxy_checker import GoogleProxyChecker
from ui.views.ai_proxy_config_dialog import AIProxyConfigDialog


class NumericTableWidgetItem(QTableWidgetItem):
    """QTableWidgetItem with numerical sorting support for latency ms values."""

    def __init__(self, text: str, sort_val: float):
        super().__init__(text)
        self.sort_val = sort_val

    def __lt__(self, other):
        if isinstance(other, NumericTableWidgetItem):
            return self.sort_val < other.sort_val
        return super().__lt__(other)


class ProxiesView(QWidget):
    """Proxy Pool Management Dashboard View with Speed Sorting and Configurable AI Google Camoufox Checker."""

    open_scraper_requested = pyqtSignal()

    def __init__(
        self,
        proxy_manager: Optional[ProxyManager] = None,
        profile_manager: Optional[ProfileManager] = None,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.proxy_manager = proxy_manager or ProxyManager()
        self.profile_manager = profile_manager or ProfileManager()
        self.proxies: List[Dict[str, Any]] = []
        self._is_checking_google = False
        self._cancel_event = asyncio.Event()
        self._current_check_task: Optional[asyncio.Task] = None
        
        # Default AI Proxy Checker Config
        self.checker_config: Dict[str, Any] = {
            "concurrency": 2,
            "headless": True,
            "profile_mode": "temp",
            "profile_id": "",
            "model_name": "auto",
            "timeout_sec": 25
        }

        self._init_ui()
        self.reload_proxies()

    def _get_icon(self, name):
        return QIcon(os.path.join(os.path.dirname(__file__), "..", "assets", "icons", f"{name}.svg"))

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Top Action Bar
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)
        
        import_btn = QPushButton(" Import Raw Proxies")
        import_btn.setIcon(self._get_icon("folder-open"))
        import_btn.setProperty("class", "PrimaryButton")
        import_btn.setToolTip("Import raw proxy lists in various formats")
        import_btn.clicked.connect(self._import_proxies_dialog)
        top_bar.addWidget(import_btn)

        scraper_btn = QPushButton(" Scrape Live Proxies")
        scraper_btn.setIcon(self._get_icon("radar"))
        scraper_btn.setProperty("class", "PrimaryButton")
        scraper_btn.setToolTip("Scrape free live proxies from verified lists")
        scraper_btn.clicked.connect(lambda: self.open_scraper_requested.emit())
        top_bar.addWidget(scraper_btn)

        test_btn = QPushButton(" Quick Test All")
        test_btn.setIcon(self._get_icon("zap"))
        test_btn.setProperty("class", "SecondaryButton")
        test_btn.setToolTip("Fast socket/HTTP ping test to check proxy availability")
        test_btn.clicked.connect(self._test_all_proxies)
        top_bar.addWidget(test_btn)

        # AI Google Camoufox Checker Button
        self.ai_google_btn = QPushButton(" AI Google Check")
        self.ai_google_btn.setIcon(self._get_icon("cpu"))
        self.ai_google_btn.setToolTip(
            "Opens AI Google Proxy Checker setup to configure threads, headless mode, profile mode and AI models."
        )
        self.ai_google_btn.setProperty("class", "PrimaryButton")
        self.ai_google_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #38bdf8);
                color: #ffffff;
                font-weight: 700;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-top: 1px solid rgba(255, 255, 255, 0.35);
                border-radius: 7px;
                padding: 7px 14px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #818cf8, stop:1 #67e8f9);
            }
            QPushButton:disabled {
                background: rgba(255, 255, 255, 0.05);
                color: #64748b;
                border: 1px solid rgba(255, 255, 255, 0.06);
            }
        """)
        self.ai_google_btn.clicked.connect(self._open_ai_google_check_dialog)
        top_bar.addWidget(self.ai_google_btn)

        # AI Google Checker Settings Gear Button
        self.ai_config_btn = QPushButton("")
        self.ai_config_btn.setIcon(self._get_icon("settings"))
        self.ai_config_btn.setFixedSize(34, 32)
        self.ai_config_btn.setProperty("class", "SecondaryButton")
        self.ai_config_btn.setToolTip("Configure AI Proxy Checker Settings (Threads, Headless, Profile, AI Model)")
        self.ai_config_btn.clicked.connect(self._open_config_only_dialog)
        top_bar.addWidget(self.ai_config_btn)

        # AI Google Checker Stop Button
        self.btn_stop_check = QPushButton(" Stop Check")
        self.btn_stop_check.setIcon(self._get_icon("square"))
        self.btn_stop_check.setProperty("class", "DangerButton")
        self.btn_stop_check.setToolTip("Immediately stop running AI Google verification")
        self.btn_stop_check.setVisible(False)
        self.btn_stop_check.clicked.connect(self._stop_google_check)
        top_bar.addWidget(self.btn_stop_check)

        sort_btn = QPushButton(" Sort by Speed")
        sort_btn.setIcon(self._get_icon("activity"))
        sort_btn.setProperty("class", "SecondaryButton")
        sort_btn.clicked.connect(lambda: self.reload_proxies(sort_speed=True))
        top_bar.addWidget(sort_btn)

        delete_all_btn = QPushButton(" Clear Pool")
        delete_all_btn.setIcon(self._get_icon("trash-2"))
        delete_all_btn.setProperty("class", "DangerButton")
        delete_all_btn.clicked.connect(self._clear_all_proxies)
        top_bar.addWidget(delete_all_btn)

        top_bar.addStretch()

        # Status & Progress indicator in top bar
        self.lbl_progress = QLabel("")
        self.lbl_progress.setStyleSheet("color: #34d399; font-weight: 700; font-size: 11px;")
        top_bar.addWidget(self.lbl_progress)

        layout.addLayout(top_bar)

        # Table Widget
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Proxy Name / Host:Port", "Type", "Status", "Tags", "IP", "Location / Country", "Latency (ms)", "Actions"
        ])
        
        v_header = self.table.verticalHeader()
        if v_header:
            v_header.setVisible(False)
            v_header.setDefaultSectionSize(44)

        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)

        header = self.table.horizontalHeader()
        if header:
            header.setHighlightSections(False)
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(7, 100)

        self.table.setSortingEnabled(True)
        layout.addWidget(self.table)

    def reload_proxies(self, sort_speed: bool = True):
        self.proxies = self.proxy_manager.list_proxies(sort_speed=sort_speed)
        self._populate_table()

    def _populate_table(self):
        sorting_was_enabled = self.table.isSortingEnabled()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)

        for p in self.proxies:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setRowHeight(row, 44)
            
            # 0. Host:Port
            self.table.setItem(row, 0, QTableWidgetItem(f"{p.get('host')}:{p.get('port')}"))
            
            # 1. Type
            self.table.setItem(row, 1, QTableWidgetItem(str(p.get('type', 'http')).upper()))
            
            # 2. Status
            status_str = str(p.get('status', 'Untested')).strip()
            
            if "Google Proxy" in status_str or "Google Clean" in status_str or "AI-Unlocked" in status_str:
                display_str = f"🟢 {status_str.replace('✓ ', '')}"
                color = "#34d399"
            elif "Google Captcha" in status_str:
                display_str = f"🟡 {status_str}"
                color = "#fbbf24"
            elif "Active" in status_str or "✓" in status_str:
                display_str = f"🟢 {status_str.replace('✓ ', '').replace(' ✓', '')}"
                color = "#34d399"
            elif "Offline" in status_str or "Failed" in status_str:
                display_str = f"🔴 {status_str}"
                color = "#fb7185"
            else:
                display_str = f"⚪ {status_str}"
                color = "#94a3b8"

            status_item = QTableWidgetItem(display_str)
            status_item.setForeground(QColor(color))
            self.table.setItem(row, 2, status_item)

            # 3. Tags
            tags_list = p.get('tags', [])
            tags_str = ", ".join(tags_list) if isinstance(tags_list, list) else str(tags_list)
            tag_item = QTableWidgetItem(tags_str)
            if "Google Proxy" in tags_str:
                tag_item.setForeground(QColor("#38bdf8"))
            self.table.setItem(row, 3, tag_item)

            # 4. IP
            self.table.setItem(row, 4, QTableWidgetItem(p.get('ip') or "-"))
            
            # 5. Location
            loc = f"{p.get('city')}, {p.get('country')}" if p.get('country') else "-"
            self.table.setItem(row, 5, QTableWidgetItem(loc))

            # 6. Latency
            lat_val = p.get('latency_ms', -1)
            lat_str = f"{lat_val} ms" if (isinstance(lat_val, (int, float)) and lat_val > 0) else "-"
            sort_val = float(lat_val) if (isinstance(lat_val, (int, float)) and lat_val > 0) else 999999.0
            self.table.setItem(row, 6, NumericTableWidgetItem(lat_str, sort_val))

            # 7. Actions (AI Test + Delete)
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(2, 2, 2, 2)
            actions_layout.setSpacing(4)
            actions_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            # Single AI Google Check Button
            ai_test_btn = QPushButton("")
            ai_test_btn.setIcon(self._get_icon("cpu"))
            ai_test_btn.setFixedSize(30, 28)
            ai_test_btn.setToolTip("Test with Google via Camoufox AI Sandbox (uses configured settings)")
            ai_test_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(99, 102, 241, 0.15);
                    border: 1px solid rgba(99, 102, 241, 0.3);
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #6366f1;
                }
            """)
            ai_test_btn.clicked.connect(lambda _, proxy_item=p: self._test_single_proxy_google(proxy_item))
            actions_layout.addWidget(ai_test_btn)

            # Delete Button
            del_btn = QPushButton("")
            del_btn.setIcon(self._get_icon("trash-2"))
            del_btn.setFixedSize(30, 28)
            del_btn.setProperty("class", "SecondaryButton")
            del_btn.setStyleSheet("border-radius: 5px; font-size: 11px;")
            del_btn.setToolTip("Delete proxy")
            del_btn.clicked.connect(lambda _, pid=p["id"]: self._delete_single_proxy(pid))
            actions_layout.addWidget(del_btn)

            self.table.setCellWidget(row, 7, actions_widget)

        self.table.setSortingEnabled(sorting_was_enabled)

    def _import_proxies_dialog(self):
        text, ok = QInputDialog.getMultiLineText(
            self, "Import Raw Proxies",
            "Paste proxies below (Formats: host:port, host:port:user:pass, socks5://user:pass@host:port):"
        )
        if ok and text.strip():
            count = self.proxy_manager.import_raw_proxies(text)
            self.reload_proxies(sort_speed=True)
            QMessageBox.information(self, "Import Success", f"Successfully imported {count} proxies into the pool.")

    def _delete_single_proxy(self, proxy_id: str):
        self.proxy_manager.delete_proxy(proxy_id)
        self.reload_proxies(sort_speed=True)

    def _clear_all_proxies(self):
        reply = QMessageBox.question(self, "Confirm Clear", "Clear all proxies from storage pool?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            for p in list(self.proxy_manager.list_proxies()):
                self.proxy_manager.delete_proxy(p["id"])
            self.reload_proxies(sort_speed=True)

    def _open_config_only_dialog(self):
        """Opens configuration dialog to adjust and persist AI Google Proxy Checker settings."""
        dlg = AIProxyConfigDialog(
            current_config=self.checker_config,
            profile_manager=self.profile_manager,
            parent=self
        )
        res = dlg.exec()
        if res in (1, 2):  # Accepted or Saved
            self.checker_config = dlg.get_config()
            self.lbl_progress.setText(" AI Checker Settings Updated")
            asyncio.create_task(self._clear_progress_after_delay())

    async def _clear_progress_after_delay(self, delay: float = 2.5):
        await asyncio.sleep(delay)
        if not self._is_checking_google:
            self.lbl_progress.setText("")

    def _open_ai_google_check_dialog(self):
        """Opens configuration dialog with option to immediately launch batch verification."""
        if self._is_checking_google:
            QMessageBox.warning(self, "Check Running", "AI Google Proxy validation is already running in background.")
            return

        proxies_list = self.proxy_manager.list_proxies(sort_speed=False)
        if not proxies_list:
            QMessageBox.information(self, "No Proxies", "No proxies in pool to test. Import or scrape proxies first.")
            return

        dlg = AIProxyConfigDialog(
            current_config=self.checker_config,
            profile_manager=self.profile_manager,
            parent=self
        )
        res = dlg.exec()
        if res == 1:  # Start AI Verification clicked
            self.checker_config = dlg.get_config()
            self._start_batch_google_check(self.checker_config)
        elif res == 2:  # Save & Apply clicked
            self.checker_config = dlg.get_config()
            self.lbl_progress.setText(" AI Checker Settings Saved")
            asyncio.create_task(self._clear_progress_after_delay())

    @qasync.asyncSlot()
    async def _test_all_proxies(self):
        """Standard Fast Ping / Socket Availability Checker."""
        proxies_list = self.proxy_manager.list_proxies(sort_speed=False)
        if not proxies_list:
            QMessageBox.information(self, "No Proxies", "No proxies in pool to test.")
            return

        self.lbl_progress.setText("⭍ Fast testing proxies...")
        sem = asyncio.Semaphore(5)

        async def _test_one(p):
            async with sem:
                p_cfg = {
                    "enabled": True,
                    "type": p.get("type", "http"),
                    "host": p.get("host"),
                    "port": p.get("port"),
                    "username": p.get("username", ""),
                    "password": p.get("password", "")
                }
                success, info, latency = await ProxyChecker.check_proxy(p_cfg)
                if success:
                    update_data = {
                        "status": "✓ Active",
                        "ip": info.get("ip", ""),
                        "country": info.get("country", ""),
                        "city": info.get("city", ""),
                        "timezone": info.get("timezone", ""),
                        "latency_ms": latency
                    }
                else:
                    update_data = {
                        "status": " Offline",
                        "latency_ms": -1
                    }
                self.proxy_manager.update_proxy(p["id"], update_data)
                self.reload_proxies(sort_speed=False)

        tasks = [_test_one(p) for p in proxies_list]
        await asyncio.gather(*tasks)
        self.lbl_progress.setText(" Fast testing completed")
        self.reload_proxies(sort_speed=True)
        await self._clear_progress_after_delay(2.5)

    def _get_active_profile_pool(self, cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Loads list of selected profile configs for rotation."""
        if cfg.get("profile_mode") == "custom":
            p_ids = cfg.get("profile_ids", [])
            profiles = []
            for pid in p_ids:
                p_data = self.profile_manager.load_profile(pid)
                if p_data:
                    profiles.append(p_data)
            return profiles
        return []

    @qasync.asyncSlot()
    async def _test_single_proxy_google(self, proxy_data: Dict):
        """Checks a single proxy with Google using Camoufox sandbox and AI question with current settings."""
        host = proxy_data.get("host")
        port = proxy_data.get("port")
        self.lbl_progress.setText(f"◈ Testing {host}:{port} with Camoufox AI...")

        p_cfg = {
            "enabled": True,
            "type": proxy_data.get("type", "http"),
            "host": host,
            "port": port,
            "username": proxy_data.get("username", ""),
            "password": proxy_data.get("password", "")
        }

        cfg = self.checker_config
        pool = self._get_active_profile_pool(cfg)
        profile_data = random.choice(pool) if pool else None

        success, status_msg, details = await GoogleProxyChecker.check_proxy_with_google(
            p_cfg,
            headless=cfg.get("headless", True),
            model_name=cfg.get("model_name"),
            profile_data=profile_data,
            timeout_sec=float(cfg.get("timeout_sec", 25)),
            captcha_strategy=cfg.get("captcha_strategy", "audio_first"),
            vision_model=cfg.get("vision_model", "auto"),
            enable_honeypot_shield=bool(cfg.get("enable_honeypot_shield", True))
        )
        
        if success:
            tags = list(proxy_data.get("tags", []))
            is_unlocked = details.get("ai_unlocked", False)
            main_tag = "AI-Unlocked" if is_unlocked else "Google Clean"
            
            if main_tag not in tags:
                tags.append(main_tag)
            if "Google Proxy" not in tags:
                tags.append("Google Proxy")
                
            status_text = "✓ AI-Unlocked" if is_unlocked else "✓ Google Clean"
            update_data = {
                "status": status_text,
                "tags": tags,
                "google_verified": True,
                "latency_ms": details.get("latency_ms", proxy_data.get("latency_ms", -1))
            }
            self.proxy_manager.update_proxy(proxy_data["id"], update_data)
            self.lbl_progress.setText(f" {host}:{port} -> {status_text}")
            QMessageBox.information(
                self,
                "Google Proxy Verified",
                f"Proxy {host}:{port} successfully validated on Google Search!\n\n"
                f"Result: {status_msg}\n"
                f"Query: \"{details.get('query')}\"\n"
                f"Latency: {details.get('latency_ms')} ms\n"
                f"Status: {status_text}"
            )
        else:
            if details.get("captcha"):
                update_data = {
                    "status": " Google Captcha",
                    "google_verified": False
                }
                self.lbl_progress.setText(f" {host}:{port} -> Captcha Blocked")
            else:
                update_data = {
                    "status": " Offline",
                    "google_verified": False
                }
                self.lbl_progress.setText(f" {host}:{port} -> Failed")
            
            self.proxy_manager.update_proxy(proxy_data["id"], update_data)
            QMessageBox.warning(
                self,
                "Google Check Result",
                f"Proxy {host}:{port} failed Google verification:\n\n"
                f"Result: {status_msg}\n"
                f"Query: \"{details.get('query', '-')}\""
            )

        self.reload_proxies(sort_speed=True)

    def _start_batch_google_check(self, cfg: Dict[str, Any]):
        """Launches background task for batch Google verification."""
        self._cancel_event.clear()
        self.btn_stop_check.setVisible(True)
        self.btn_stop_check.setEnabled(True)
        self._current_check_task = asyncio.create_task(self._run_batch_google_check(cfg))

    def _stop_google_check(self):
        """Immediately stops running AI Google verification."""
        if not self._is_checking_google:
            return
        self._cancel_event.set()
        if self._current_check_task and not self._current_check_task.done():
            self._current_check_task.cancel()
        self._is_checking_google = False
        self.ai_google_btn.setEnabled(True)
        self.btn_stop_check.setVisible(False)
        self.lbl_progress.setText("■ AI Google check stopped by user")
        self.reload_proxies(sort_speed=True)
        asyncio.create_task(self._clear_progress_after_delay(3.0))

    async def _run_batch_google_check(self, cfg: Dict[str, Any]):
        """Executes concurrent batch Google checks with custom configuration."""
        if self._is_checking_google:
            return

        proxies_list = self.proxy_manager.list_proxies(sort_speed=False)
        if not proxies_list:
            self.btn_stop_check.setVisible(False)
            return

        self._is_checking_google = True
        self.ai_google_btn.setEnabled(False)
        self.btn_stop_check.setVisible(True)

        is_random = bool(cfg.get("random_order", False))
        if is_random:
            import random
            # Shuffle list so proxies are checked in random order, each exactly once
            random.shuffle(proxies_list)
            self.lbl_progress.setText(f"⚄ Shuffled {len(proxies_list)} proxies for random-order check...")
        else:
            self.lbl_progress.setText("◈ Starting AI Google validation...")

        verified_count = 0
        total = len(proxies_list)
        profile_pool = self._get_active_profile_pool(cfg)

        def on_single_proxy_done(p: Dict, success: bool, msg: str, details: Dict):
            nonlocal verified_count
            if success:
                verified_count += 1
                tags = list(p.get("tags", []))
                is_unlocked = details.get("ai_unlocked", False)
                main_tag = "AI-Unlocked" if is_unlocked else "Google Clean"
                
                if main_tag not in tags:
                    tags.append(main_tag)
                if "Google Proxy" not in tags:
                    tags.append("Google Proxy")
                    
                status_text = "✓ AI-Unlocked" if is_unlocked else "✓ Google Clean"
                update_data = {
                    "status": status_text,
                    "tags": tags,
                    "google_verified": True,
                    "latency_ms": details.get("latency_ms", p.get("latency_ms", -1))
                }
            elif details.get("captcha"):
                update_data = {
                    "status": " Google Captcha",
                    "google_verified": False
                }
            else:
                update_data = {
                    "status": " Offline",
                    "google_verified": False
                }
            
            self.proxy_manager.update_proxy(p["id"], update_data)
            self.reload_proxies(sort_speed=False)

        def on_progress(completed: int, total_items: int, status_line: str):
            self.lbl_progress.setText(f"◈ [{completed}/{total_items}] {status_line}")

        try:
            concurrency = int(cfg.get("concurrency", 2))
            headless = bool(cfg.get("headless", True))
            model_name = cfg.get("model_name")
            timeout_sec = float(cfg.get("timeout_sec", 25))
            captcha_strat = cfg.get("captcha_strategy", "audio_first")
            vision_mod = cfg.get("vision_model", "auto")

            enable_hp = bool(cfg.get("enable_honeypot_shield", True))

            await GoogleProxyChecker.check_proxies_batch(
                proxies_list,
                max_concurrency=concurrency,
                headless=headless,
                model_name=model_name,
                profile_pool=profile_pool,
                timeout_sec=timeout_sec,
                captcha_strategy=captcha_strat,
                vision_model=vision_mod,
                enable_honeypot_shield=enable_hp,
                cancel_event=self._cancel_event,
                on_proxy_complete=on_single_proxy_done,
                progress_callback=on_progress
            )

            if not self._cancel_event.is_set():
                self.reload_proxies(sort_speed=True)
                self.lbl_progress.setText(f" Completed: {verified_count}/{total} Google Proxies verified!")
                QMessageBox.information(
                    self,
                    "AI Google Verification Complete",
                    f"AI Google Proxy check finished.\n\n"
                    f"Total Tested: {total}\n"
                    f"Declared Google Proxies: {verified_count}\n"
                    f"Blocked / Failed: {total - verified_count}\n\n"
                    f"Settings used:\n"
                    f"• Order: {'⚄ Random (Shuffled)' if is_random else '⎘ Sequential (Top-to-Bottom)'}\n"
                    f"• Threads: {concurrency}\n"
                    f"• Headless: {'Yes' if headless else 'No'}\n"
                    f"• Solver Strategy: {captcha_strat}\n"
                    f"• AI Model: {model_name or 'Auto'}"
                )

        except asyncio.CancelledError:
            self.lbl_progress.setText("■ AI Google check cancelled")
        except Exception as ex:
            QMessageBox.critical(self, "Check Error", f"An error occurred during batch Google check:\n{ex}")
        finally:
            self._is_checking_google = False
            self.ai_google_btn.setEnabled(True)
            self.btn_stop_check.setVisible(False)
            await self._clear_progress_after_delay(4.0)
