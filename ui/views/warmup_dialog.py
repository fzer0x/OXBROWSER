import asyncio
import logging
from typing import List, Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox, QTextEdit, QLineEdit,
    QProgressBar, QGroupBox, QFormLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QWidget, QSplitter
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QIcon
import qasync
import os

from engine.browser import BrowserLauncher
from engine.cookie_warmup import CookieWarmupRobot, WarmupConfig, PERSONA_PROFILES, WARMUP_CATEGORIES, WarmupKnowledgeStore

logger = logging.getLogger("WarmupDialog")


class LogSignalRelay(QObject):
    """Signal relay to send log updates from async tasks safely to Qt GUI thread."""
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(str, float, str, int)  # msg, percent, current_url, cookie_count
    profile_progress_signal = pyqtSignal(str, str, float, str, int)  # pid, msg, percent, current_url, cookie_count


class WarmupDialog(QDialog):
    """Interactive WarmUp Control Modal for configuring and monitoring background profile warmup."""

    def __init__(self, parent: Optional[QWidget], profile_ids: List[str], launcher: BrowserLauncher):
        super().__init__(parent)
        self.initial_profile_ids = profile_ids or []
        self.launcher = launcher
        self.robot = CookieWarmupRobot(launcher)
        self.relay = LogSignalRelay()
        self.is_running = False
        self.row_pid_map = {}

        self.setWindowTitle("AI Multi-Profile Cookie & History Warmup")
        self.resize(1320, 1080)
        self.setMinimumSize(820, 580)

        self._setup_ui()
        self._connect_signals()
        self._populate_profile_table()

    def _get_icon(self, name):
        return QIcon(os.path.join(os.path.dirname(__file__), "..", "assets", "icons", f"{name}.svg"))

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(14)

        # Header Title Banner
        header_layout = QHBoxLayout()
        title_label = QLabel("AI Multi-Profile Warmup")
        title_label.setStyleSheet("font-size: 17px; font-weight: 800; color: #f8fafc; letter-spacing: -0.3px;")
        
        self.lbl_profile_count = QLabel("Selected: 0 profiles")
        self.lbl_profile_count.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: 700;")
        
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.lbl_profile_count)
        main_layout.addLayout(header_layout)

        # Splitter between Settings and Live Progress
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Top Section: Settings Panel
        settings_box = QGroupBox("AI Behavioral Strategy & Motor Control Configuration")
        settings_layout = QHBoxLayout(settings_box)
        settings_layout.setSpacing(12)

        # Form Column 1: Persona & Execution Metrics
        form_col1 = QFormLayout()
        self.persona_combo = QComboBox()
        self.persona_combo.addItems([
            "General Consumer (Balanced Persona)",
            "Tech Enthusiast & Developer Persona",
            "E-Commerce & Shopping Buyer Persona",
            "News & Media Outlets Reader",
            "Social Media & Community Explorer",
            "Fingerprint & Leak Auditor (browserscan, browserleaks, dnsleak)",
            "Google Search & Top-5 Deep Reader (Exklusiv Google-Suche + 5 Top-Links)"
        ])
        
        self.spin_max_pages = QSpinBox()
        self.spin_max_pages.setRange(1, 50)
        self.spin_max_pages.setValue(5)
        self.spin_max_pages.setSuffix(" sites")

        self.spin_dwell_time = QDoubleSpinBox()
        self.spin_dwell_time.setRange(2.0, 60.0)
        self.spin_dwell_time.setValue(8.0)
        self.spin_dwell_time.setSingleStep(1.0)
        self.spin_dwell_time.setSuffix(" sec base")

        self.spin_concurrency = QSpinBox()
        self.spin_concurrency.setRange(1, 10)
        self.spin_concurrency.setValue(2)
        self.spin_concurrency.setSuffix(" parallel")
        self.spin_concurrency.setToolTip("Number of browser profiles to run concurrently in parallel.")

        import config
        self.ai_model_combo = QComboBox()
        for model_id, label in config.get_all_ai_model_options():
            self.ai_model_combo.addItem(label, model_id)

        self.chk_headless = QCheckBox("Headless Mode (Silent Virtual Display / Xvfb)")
        self.chk_headless.setChecked(False)
        self.chk_headless.setToolTip("Runs browser instances silently in the background using Camoufox/Playwright's isolated virtual display.")

        form_col1.addRow(QLabel("AI Persona Strategy:"), self.persona_combo)
        form_col1.addRow(QLabel("Local AI Micro-LLM:"), self.ai_model_combo)
        form_col1.addRow(QLabel("Max Sites / Profile:"), self.spin_max_pages)
        form_col1.addRow(QLabel("Base Dwell Time / Page:"), self.spin_dwell_time)
        form_col1.addRow(QLabel("Max Parallel Browsers:"), self.spin_concurrency)
        form_col1.addRow(self.chk_headless)

        # Form Column 2: Advanced Behavioral AI Toggles
        form_col2 = QFormLayout()
        self.spin_click_depth = QSpinBox()
        self.spin_click_depth.setRange(0, 3)
        self.spin_click_depth.setValue(1)
        self.spin_click_depth.setToolTip("Sub-navigation click depth for internal links on visited domains.")

        self.chk_min_jerk = QCheckBox("Biomechanical Min-Jerk Motor & Tremor")
        self.chk_min_jerk.setChecked(True)
        self.chk_min_jerk.setToolTip("Uses 5th-order polynomial minimum jerk motor trajectories with Fitts's Law duration and physiological micro-tremors.")

        self.chk_wpm_dwell = QCheckBox("Content-Aware WPM Reading Engine")
        self.chk_wpm_dwell.setChecked(True)
        self.chk_wpm_dwell.setToolTip("Dynamically adjusts reading pause based on visible DOM text word count and image density.")

        self.chk_bigram_typing = QCheckBox("Gaussian Bi-Gram Typing & Mistypes")
        self.chk_bigram_typing.setChecked(True)
        self.chk_bigram_typing.setToolTip("Simulates QWERTY spatial key delays, shift hesitations, and 3% human mistype + Backspace corrections.")

        self.chk_organic_search = QCheckBox("Organic Search Queries (Google/DuckDuckGo)")
        self.chk_organic_search.setChecked(True)

        self.chk_no_google = QCheckBox("🚫 NoGoogle Mode (DuckDuckGo / Bing statt Google)")
        self.chk_no_google.setChecked(False)
        self.chk_no_google.setStyleSheet("color: #fb923c; font-weight: 600;")
        self.chk_no_google.setToolTip("Verbietet jegliche Google-Suchen und Google-Domains im Warmup. Es wird stattdessen über DuckDuckGo und Bing gesucht, um Captchas & Google-Bot-Traps komplett zu umgehen.")
        self.chk_no_google.toggled.connect(self._on_no_google_toggled)

        self.chk_cookie_banners = QCheckBox("Multi-Lingual Semantic Consent Solver")
        self.chk_cookie_banners.setChecked(True)

        self.chk_auto_evade = QCheckBox("Self-Learning Auth Trap Evasion & Memory")
        self.chk_auto_evade.setChecked(True)
        self.chk_auto_evade.setToolTip("Automatically detects login/auth/paywall traps, executes humanoid back-retreats, and learns safe domain trajectories.")

        self.chk_honeypot_shield = QCheckBox("AI Honeypot & Click-Trap Shield")
        self.chk_honeypot_shield.setChecked(True)
        self.chk_honeypot_shield.setToolTip("Actively scans DOM elements on every page for invisible links, transparent overlays, and decoy bot traps to prevent accidental clicks.")

        self.chk_verification_audit = QCheckBox("Real-Time Fingerprint & Leak Audit Test Suite")
        self.chk_verification_audit.setChecked(True)
        self.chk_verification_audit.setToolTip("Scans verification sites (browserscan, sannysoft, browserleaks, dnsleak) during visits to detect WebDriver flags & WebRTC/DNS leaks.")

        form_col2.addRow(QLabel("Internal Link Depth:"), self.spin_click_depth)
        form_col2.addRow(self.chk_min_jerk)
        form_col2.addRow(self.chk_wpm_dwell)
        form_col2.addRow(self.chk_bigram_typing)
        form_col2.addRow(self.chk_organic_search)
        form_col2.addRow(self.chk_no_google)
        form_col2.addRow(self.chk_cookie_banners)
        form_col2.addRow(self.chk_auto_evade)
        form_col2.addRow(self.chk_honeypot_shield)
        form_col2.addRow(self.chk_verification_audit)

        # Form Column 3: AI Captcha Solver & Custom Intent / Target Websites
        form_col3 = QFormLayout()
        
        # Local AI Captcha Solver Controls
        self.chk_solve_captchas = QCheckBox("Solve Barriers (reCAPTCHA v2 / sorry/index)")
        self.chk_solve_captchas.setChecked(True)
        self.chk_solve_captchas.setToolTip("Autonomously bypasses Google / sorry/index & reCAPTCHA challenges using local AI models during warmup.")
        
        self.combo_captcha_strategy = QComboBox()
        self.combo_captcha_strategy.addItem("Audio Whisper  Vision Fallback (Empfohlen)", "audio_first")
        self.combo_captcha_strategy.addItem("Vision VLM  Audio Fallback", "vision_first")
        self.combo_captcha_strategy.addItem("Audio Whisper Only", "audio_only")
        self.combo_captcha_strategy.addItem("Vision VLM Only", "vision_only")
        self.combo_captcha_strategy.addItem("Disabled", "disabled")
        
        self.combo_captcha_vision = QComboBox()
        self.combo_captcha_vision.addItem("⚡ 50/50 Hybrid Co-Pilot (50% Gemini Cloud + 50% Local VLM)", "hybrid_50_50_gemini")
        self.combo_captcha_vision.addItem("qwen2.5vl:3b (Next-Gen 3.2B Vision - Recommended)", "qwen2.5vl:3b")
        self.combo_captcha_vision.addItem("florence-2-base (Microsoft 0.23B Fast Grounding)", "florence-2-base")
        self.combo_captcha_vision.addItem("got-ocr2 (StepFun 0.5B Dense OCR & Text)", "got-ocr2")
        self.combo_captcha_vision.addItem("llava:7b (Local 7B Spatial Vision)", "llava:7b")
        self.combo_captcha_vision.addItem("moondream:v2 (Fast 1.4B Vision)", "moondream:v2")
        self.combo_captcha_vision.addItem("smolvlm:1.1b (Ultra-Light Vision)", "smolvlm:1.1b")
        self.combo_captcha_vision.addItem("gemini-3.6-flash (Cloud Vision API - 100% Cloud)", "gemini-3.6-flash")

        self.chk_gemini_vision_assist = QCheckBox("⚡ Gemini Cloud 50/50 Co-Pilot Unterstützung")
        self.chk_gemini_vision_assist.setStyleSheet("color: #38bdf8; font-weight: 600; font-size: 11px;")
        self.chk_gemini_vision_assist.setChecked(False)
        self.chk_gemini_vision_assist.setToolTip("Aktiviert intelligente 50/50 Lastenverteilung: Die Hälfte der Tiles übernimmt Gemini Cloud, die andere das gewählte lokale VLM.")

        self.chk_solve_captchas.toggled.connect(self._on_captcha_solver_toggled)

        self.txt_custom_keywords = QTextEdit()
        self.txt_custom_keywords.setMaximumHeight(45)
        self.txt_custom_keywords.setPlaceholderText("Comma-separated keywords (e.g. python programming, pyqt6, web scraping)")
        self.txt_custom_keywords.setStyleSheet("background-color: rgba(10, 13, 22, 0.85); color: #a5b4fc; font-family: monospace; border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 6px; padding: 4px;")
        self.txt_custom_keywords.setToolTip("Establishes a coherent thematic focus ('Roter Faden') for searches, Copilot questions & articles.")

        self.txt_custom_websites = QTextEdit()
        self.txt_custom_websites.setMaximumHeight(45)
        self.txt_custom_websites.setPlaceholderText("Custom target URLs, 1 per line (e.g. https://news.ycombinator.com\nhttps://pypi.org)")
        self.txt_custom_websites.setStyleSheet("background-color: rgba(10, 13, 22, 0.85); color: #a5b4fc; font-family: monospace; border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 6px; padding: 4px;")
        self.txt_custom_websites.setToolTip("Prioritizes visiting these specific target websites during warmup.")

        form_col3.addRow(self.chk_solve_captchas)
        form_col3.addRow(QLabel("Solver Priority:"), self.combo_captcha_strategy)
        form_col3.addRow(QLabel("Vision VLM Model:"), self.combo_captcha_vision)
        form_col3.addRow(self.chk_gemini_vision_assist)
        form_col3.addRow(QLabel("Custom Keywords ('Roter Faden'):"), self.txt_custom_keywords)
        form_col3.addRow(QLabel("Custom Target Websites:"), self.txt_custom_websites)

        settings_layout.addLayout(form_col1, stretch=1)
        settings_layout.addLayout(form_col2, stretch=1)
        settings_layout.addLayout(form_col3, stretch=1)
        splitter.addWidget(settings_box)

        # Bottom Section: Profile Selector & Live Monitor
        monitor_widget = QWidget()
        monitor_layout = QVBoxLayout(monitor_widget)
        monitor_layout.setContentsMargins(0, 8, 0, 0)
        monitor_layout.setSpacing(10)

        # Progress Bar & Active Action Label
        progress_layout = QVBoxLayout()
        self.status_label = QLabel("Ready to start AI warmup task.")
        self.status_label.setStyleSheet("color: #94a3b8; font-weight: 700; font-size: 11px;")

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(18)

        # Dedicated AI Model Download/Setup Progress Card
        self.ai_card = QGroupBox("Local AI Model Engine Telemetry")
        ai_card_layout = QVBoxLayout(self.ai_card)
        ai_card_layout.setContentsMargins(10, 8, 10, 8)
        ai_card_layout.setSpacing(6)

        self.ai_status_lbl = QLabel("AI Engine Status: Ready")
        self.ai_status_lbl.setStyleSheet("color: #34d399; font-weight: 700; font-size: 11px;")

        self.ai_progress_bar = QProgressBar()
        self.ai_progress_bar.setRange(0, 100)
        self.ai_progress_bar.setValue(100)
        self.ai_progress_bar.setFixedHeight(18)

        ai_card_layout.addWidget(self.ai_status_lbl)
        ai_card_layout.addWidget(self.ai_progress_bar)
        progress_layout.addWidget(self.ai_card)

        progress_layout.addWidget(self.status_label)
        progress_layout.addWidget(self.progress_bar)
        monitor_layout.addLayout(progress_layout)

        # Profile selection action bar
        profile_bar = QHBoxLayout()
        profile_bar.setSpacing(8)
        self.btn_select_all = QPushButton(" Select All Profiles")
        self.btn_select_all.setIcon(self._get_icon("check-circle"))
        self.btn_select_all.setProperty("class", "SecondaryButton")
        self.btn_deselect_all = QPushButton(" Deselect All")
        self.btn_deselect_all.setIcon(self._get_icon("x-circle"))
        self.btn_deselect_all.setProperty("class", "SecondaryButton")
        profile_bar.addWidget(self.btn_select_all)
        profile_bar.addWidget(self.btn_deselect_all)
        profile_bar.addStretch()
        monitor_layout.addLayout(profile_bar)

        # Split log terminal and profile table side-by-side
        bottom_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Profiles Status Table with Checkboxes
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Run", "Profile Name", "Status", "Cookies"])
        
        v_header = self.table.verticalHeader()
        if v_header:
            v_header.setVisible(False)
            v_header.setDefaultSectionSize(36)

        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)

        header = self.table.horizontalHeader()
        if header:
            header.setHighlightSections(False)
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        # Log Terminal Output
        self.log_terminal = QTextEdit()
        self.log_terminal.setReadOnly(True)
        self.log_terminal.setPlaceholderText("Live AI WarmUp execution log output will appear here...")
        self.log_terminal.setStyleSheet("""
            QTextEdit {
                background-color: rgba(10, 13, 22, 0.95);
                color: #34d399;
                font-family: -apple-system, monospace, Consolas;
                font-size: 11px;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
                padding: 8px;
            }
        """)

        bottom_splitter.addWidget(self.table)
        bottom_splitter.addWidget(self.log_terminal)
        bottom_splitter.setSizes([380, 520])

        monitor_layout.addWidget(bottom_splitter)
        splitter.addWidget(monitor_widget)

        main_layout.addWidget(splitter)

        # Footer Action Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.btn_start = QPushButton(" Start AI Warmup")
        self.btn_start.setIcon(self._get_icon("play"))
        self.btn_start.setProperty("class", "PrimaryButton")

        self.btn_stop = QPushButton(" Stop")
        self.btn_stop.setIcon(self._get_icon("square"))
        self.btn_stop.setProperty("class", "DangerButton")
        self.btn_stop.setEnabled(False)

        self.btn_close = QPushButton("Close")
        self.btn_close.setProperty("class", "SecondaryButton")

        button_layout.addWidget(self.btn_start)
        button_layout.addWidget(self.btn_stop)
        button_layout.addStretch()
        button_layout.addWidget(self.btn_close)

        main_layout.addLayout(button_layout)

    def _populate_profile_table(self):
        self.table.blockSignals(True)
        all_profiles = self.launcher.profile_manager.list_profiles()
        self.table.setRowCount(len(all_profiles))
        self.row_pid_map.clear()

        for row, prof in enumerate(all_profiles):
            pid = prof.get("id", "")
            name = prof.get("name", pid[:8])
            self.row_pid_map[pid] = row

            # Checkbox item
            item_check = QTableWidgetItem()
            item_check.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            
            # Pre-check if in initial selection or if initial selection is empty (select all by default)
            is_checked = (pid in self.initial_profile_ids) if self.initial_profile_ids else True
            item_check.setCheckState(Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked)
            item_check.setData(Qt.ItemDataRole.UserRole, pid)

            item_name = QTableWidgetItem(name)
            item_status = QTableWidgetItem("Queued")
            item_cookies = QTableWidgetItem("-")

            item_status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_cookies.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            self.table.setItem(row, 0, item_check)
            self.table.setItem(row, 1, item_name)
            self.table.setItem(row, 2, item_status)
            self.table.setItem(row, 3, item_cookies)

        self.table.blockSignals(False)
        self._update_profile_count_label()

    def _update_profile_count_label(self):
        selected = self._get_selected_profile_ids()
        total = self.table.rowCount()
        self.lbl_profile_count.setText(f"Selected: {len(selected)} / {total} profiles")

    def _get_selected_profile_ids(self) -> List[str]:
        selected = []
        for row in range(self.table.rowCount()):
            item_check = self.table.item(row, 0)
            if item_check and item_check.checkState() == Qt.CheckState.Checked:
                pid = item_check.data(Qt.ItemDataRole.UserRole)
                if pid:
                    selected.append(pid)
        return selected

    def _on_select_all(self):
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(Qt.CheckState.Checked)
        self.table.blockSignals(False)
        self._update_profile_count_label()

    def _on_deselect_all(self):
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(Qt.CheckState.Unchecked)
        self.table.blockSignals(False)
        self._update_profile_count_label()

    def _connect_signals(self):
        self.btn_start.clicked.connect(self._on_start_clicked)
        self.btn_stop.clicked.connect(self._on_stop_clicked)
        self.btn_close.clicked.connect(self.close)
        self.btn_select_all.clicked.connect(self._on_select_all)
        self.btn_deselect_all.clicked.connect(self._on_deselect_all)

        self.table.itemChanged.connect(self._on_table_item_changed)

        self.relay.log_signal.connect(self._append_log)
        self.relay.progress_signal.connect(self._update_progress_ui)
        self.relay.profile_progress_signal.connect(self._update_profile_row_ui)

    def _on_table_item_changed(self, item: QTableWidgetItem):
        if item.column() == 0:
            self._update_profile_count_label()

    def _append_log(self, text: str):
        self.log_terminal.append(text)
        sb = self.log_terminal.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())

    def _update_progress_ui(self, msg: str, percent: float, current_url: str, cookies: int):
        self.status_label.setText(f"Status: {msg}")
        self.progress_bar.setValue(int(percent))

    def _update_profile_row_ui(self, pid: str, msg: str, percent: float, current_url: str, cookies: int):
        try:
            if pid in self.row_pid_map:
                row = self.row_pid_map[pid]
                status_text = "Done" if percent >= 100.0 else "Running"
                self.table.setItem(row, 2, QTableWidgetItem(status_text))
                self.table.setItem(row, 3, QTableWidgetItem(str(cookies)))
        except Exception:
            pass

    def _on_no_google_toggled(self, checked: bool):
        if checked:
            self.chk_organic_search.setText("Organic Search Queries (DuckDuckGo / Bing)")
        else:
            self.chk_organic_search.setText("Organic Search Queries (Google / DuckDuckGo)")

    def _on_captcha_solver_toggled(self, checked: bool):
        self.combo_captcha_strategy.setEnabled(checked)
        self.combo_captcha_vision.setEnabled(checked)
        if hasattr(self, "chk_gemini_vision_assist"):
            self.chk_gemini_vision_assist.setEnabled(checked)

    def _get_selected_persona_key(self) -> str:
        idx = self.persona_combo.currentIndex()
        mapping = {
            0: "general",
            1: "tech",
            2: "ecommerce",
            3: "news",
            4: "social",
            5: "fingerprint",
            6: "google_search"
        }
        return mapping.get(idx, "general")

    def _on_start_clicked(self, *args, **kwargs):
        if self.is_running:
            return
        asyncio.create_task(self._run_warmup_queue())

    async def _run_warmup_queue(self):
        selected_pids = self._get_selected_profile_ids()
        if not selected_pids:
            QMessageBox.warning(self, "No Profiles Selected", "Please select at least one profile to warm up.")
            return

        self.is_running = True
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_close.setEnabled(False)
        self.persona_combo.setEnabled(False)
        self.spin_max_pages.setEnabled(False)
        self.spin_dwell_time.setEnabled(False)
        self.spin_concurrency.setEnabled(False)
        self.spin_click_depth.setEnabled(False)
        self.chk_solve_captchas.setEnabled(False)
        self.combo_captcha_strategy.setEnabled(False)
        self.combo_captcha_vision.setEnabled(False)
        if hasattr(self, "chk_gemini_vision_assist"):
            self.chk_gemini_vision_assist.setEnabled(False)
        self.btn_select_all.setEnabled(False)
        self.btn_deselect_all.setEnabled(False)
        self.table.setEnabled(False)

        persona_key = self._get_selected_persona_key()
        selected_ai_model = self.ai_model_combo.currentData() if hasattr(self, "ai_model_combo") else "qwen2.5:0.5b"
        solve_captchas_enabled = self.chk_solve_captchas.isChecked()
        selected_captcha_strategy = self.combo_captcha_strategy.currentData() if solve_captchas_enabled else "disabled"
        selected_vision_model = self.combo_captcha_vision.currentData() or "qwen2.5vl:3b"
        
        # Apply 50/50 Gemini Cloud Assist split if checkbox is active
        if hasattr(self, "chk_gemini_vision_assist") and self.chk_gemini_vision_assist.isChecked():
            if selected_vision_model != "hybrid_50_50_gemini" and not selected_vision_model.startswith("gemini"):
                selected_vision_model = f"hybrid_50_50_gemini:{selected_vision_model}"
            elif selected_vision_model.startswith("gemini"):
                selected_vision_model = "hybrid_50_50_gemini:qwen2.5vl:3b"

        # Parse custom keywords & websites
        raw_kw = self.txt_custom_keywords.toPlainText().strip()
        custom_kw_list = [k.strip() for k in raw_kw.replace("\n", ",").split(",") if k.strip()]

        raw_web = self.txt_custom_websites.toPlainText().strip()
        custom_web_list = [w.strip() for w in raw_web.replace("\n", ",").split(",") if w.strip()]
        if custom_web_list:
            formatted_web = []
            for w in custom_web_list:
                if not w.startswith("http://") and not w.startswith("https://"):
                    w = "https://" + w
                formatted_web.append(w)
            custom_web_list = formatted_web

        cfg = WarmupConfig(
            persona=persona_key,
            category=persona_key,
            mode="google_search_only" if persona_key == "google_search" else "standard",
            ai_model=selected_ai_model,
            motor_model="min_jerk" if self.chk_min_jerk.isChecked() else "bezier",
            typing_model="bigram" if self.chk_bigram_typing.isChecked() else "uniform",
            content_aware_dwell=self.chk_wpm_dwell.isChecked(),
            auto_evade_traps=self.chk_auto_evade.isChecked(),
            enable_honeypot_shield=self.chk_honeypot_shield.isChecked(),
            self_learning_memory=self.chk_auto_evade.isChecked(),
            enable_verification_audit=self.chk_verification_audit.isChecked(),
            enable_captcha_solver=solve_captchas_enabled,
            captcha_strategy=selected_captcha_strategy,
            captcha_vision_model=selected_vision_model,
            max_pages=self.spin_max_pages.value(),
            dwell_time=self.spin_dwell_time.value(),
            click_depth=self.spin_click_depth.value(),
            concurrency=self.spin_concurrency.value(),
            enable_search=self.chk_organic_search.isChecked(),
            no_google=self.chk_no_google.isChecked(),
            dismiss_banners=self.chk_cookie_banners.isChecked(),
            custom_keywords=custom_kw_list,
            custom_websites=custom_web_list,
            headless=self.chk_headless.isChecked()
        )

        k_stats = WarmupKnowledgeStore.get_instance().get_stats()
        persona_name = PERSONA_PROFILES.get(persona_key, {}).get("name", persona_key)
        self._append_log(f"--- Starting 08/2026 AI WarmUp Task [{len(selected_pids)} profile(s), Persona: '{persona_name}', Model: '{selected_ai_model}'] ---")
        if self.chk_no_google.isChecked():
            self._append_log("--- 🚫 NoGoogle Mode ACTIVE (Google forbidden -> Routing via DuckDuckGo & Bing) ---")
        if self.chk_headless.isChecked():
            self._append_log("--- ⛑ Headless Mode ACTIVE (Silent Background Virtual Display / Xvfb) ---")
        if self.chk_honeypot_shield.isChecked():
            self._append_log("--- ⛉ AI Honeypot & Click-Trap Shield ACTIVE (Deep DOM Trap Neutralization) ---")
        if solve_captchas_enabled:
            self._append_log(f"--- ⎘ Local AI Captcha Solver ACTIVE (Strategy: {selected_captcha_strategy}, Vision: {selected_vision_model}) ---")
        self._append_log(f"--- Knowledge Base Active: {k_stats['total_learned_domains']} Learned Domains | {k_stats['total_traps_avoided']} Traps Evaded ---")

        # Auto-ensure AI Model is downloaded & running before warmup begins
        try:
            from engine.ai_model_manager import AIModelManager
            ai_mgr = AIModelManager.get_instance()
            self.ai_status_lbl.setText(f"Initializing Local AI Model '{selected_ai_model}'...")
            self.ai_status_lbl.setStyleSheet("color: #89dceb; font-weight: bold; font-size: 13px;")

            def ai_progress_cb(msg: str, pct: float):
                self.relay.log_signal.emit(f"[AI Setup] {msg}")
                self.ai_status_lbl.setText(f"AI Setup: {msg}")
                self.ai_status_lbl.setStyleSheet("color: #89dceb; font-weight: bold; font-size: 13px;")
                val = max(0, min(100, int(pct)))
                self.ai_progress_bar.setValue(val)
                self.ai_progress_bar.setFormat(f"{val}% - {msg}")

            await ai_mgr.ensure_model_pulled(selected_ai_model, progress_callback=ai_progress_cb)
            self.ai_status_lbl.setText(f"✓ AI Micro-LLM '{selected_ai_model}' Active & Ready")
            self.ai_status_lbl.setStyleSheet("color: #a6e3a1; font-weight: bold; font-size: 13px;")
            self.ai_progress_bar.setValue(100)
            self.ai_progress_bar.setFormat("100% - Ready")
        except Exception as ai_err:
            self._append_log(f"[AI Model Note] {ai_err}")

        def batch_cb(pid: str, msg: str, pct: float, current_url: str, cookie_cnt: int):
            self.relay.profile_progress_signal.emit(pid, msg, pct, current_url, cookie_cnt)
            self.relay.log_signal.emit(f"[{pid[:8]}] {msg}")

        await self.robot.run_warmup_batch(selected_pids, config=cfg, progress_callback=batch_cb)

        self.is_running = False
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_close.setEnabled(True)
        self.persona_combo.setEnabled(True)
        self.spin_max_pages.setEnabled(True)
        self.spin_dwell_time.setEnabled(True)
        self.spin_concurrency.setEnabled(True)
        self.spin_click_depth.setEnabled(True)
        self.chk_solve_captchas.setEnabled(True)
        self._on_captcha_solver_toggled(self.chk_solve_captchas.isChecked())
        self.btn_select_all.setEnabled(True)
        self.btn_deselect_all.setEnabled(True)
        self.table.setEnabled(True)

        self.status_label.setText("AI Warmup queue finished.")
        self.progress_bar.setValue(100)
        self._append_log("--- AI Warmup Queue Completed ---")

    def _on_stop_clicked(self):
        if self.is_running:
            self.robot.request_stop()
            self._append_log("Stop requested. Finishing current step...")
            self.btn_stop.setEnabled(False)
