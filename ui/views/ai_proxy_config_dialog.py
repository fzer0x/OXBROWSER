import asyncio
from typing import Dict, Any, List, Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QComboBox, QCheckBox, QRadioButton, QGroupBox,
    QWidget, QListWidget, QListWidgetItem, QButtonGroup, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
import qasync
import os

from storage.profile_manager import ProfileManager
from engine.ai_model_manager import AIModelManager
import config


class AIProxyConfigDialog(QDialog):
    """Configuration modal for AI-assisted Google Proxy Checker with multi-profile selection."""

    def __init__(
        self,
        current_config: Optional[Dict[str, Any]] = None,
        profile_manager: Optional[ProfileManager] = None,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.setWindowTitle("AI Google Proxy Checker Configuration")
        self.setMinimumWidth(540)
        self.profile_manager = profile_manager or ProfileManager()
        self.config: Dict[str, Any] = current_config or {
            "concurrency": 2,
            "headless": True,
            "profile_mode": "temp",
            "profile_ids": [],
            "model_name": "auto",
            "timeout_sec": 25
        }
        self._init_ui()
        self._load_async_data()

    def _get_icon(self, name):
        return QIcon(os.path.join(os.path.dirname(__file__), "..", "assets", "icons", f"{name}.svg"))

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(18, 18, 18, 18)

        # Header Info Banner
        header = QLabel(
            "Configure Camoufox Anti-Detect Sandbox, parallel threads, custom multi-profile selection, and AI models."
        )
        header.setWordWrap(True)
        header.setStyleSheet("color: #94a3b8; font-size: 11px; margin-bottom: 2px;")
        layout.addWidget(header)

        # Group 1: Concurrency & Browser Engine Execution
        exec_group = QGroupBox("Execution & Concurrency")
        exec_layout = QVBoxLayout(exec_group)
        exec_layout.setSpacing(10)

        # 1. Threads / Concurrency
        thread_row = QHBoxLayout()
        lbl_threads = QLabel("Concurrent Browsers / Threads:")
        lbl_threads.setStyleSheet("color: #e2e8f0; font-weight: 600;")
        self.spin_concurrency = QSpinBox()
        self.spin_concurrency.setRange(1, 10)
        self.spin_concurrency.setValue(int(self.config.get("concurrency", 2)))
        self.spin_concurrency.setToolTip("Number of parallel Camoufox instances to run (Recommended: 2-4)")
        self.spin_concurrency.setFixedWidth(80)
        thread_row.addWidget(lbl_threads)
        thread_row.addStretch()
        thread_row.addWidget(self.spin_concurrency)
        exec_layout.addLayout(thread_row)

        # 2. Headless Mode
        headless_row = QHBoxLayout()
        lbl_headless = QLabel("Browser Mode:")
        lbl_headless.setStyleSheet("color: #e2e8f0; font-weight: 600;")
        self.combo_headless = QComboBox()
        self.combo_headless.addItem("Headless (Background - Fast & Stealth)", True)
        self.combo_headless.addItem("Visible GUI (Watch Camoufox AI live)", False)
        is_headless = self.config.get("headless", True)
        self.combo_headless.setCurrentIndex(0 if is_headless else 1)
        headless_row.addWidget(lbl_headless)
        headless_row.addStretch()
        headless_row.addWidget(self.combo_headless)
        exec_layout.addLayout(headless_row)

        # 3. Timeout
        timeout_row = QHBoxLayout()
        lbl_timeout = QLabel("Request Timeout (Seconds):")
        lbl_timeout.setStyleSheet("color: #e2e8f0; font-weight: 600;")
        self.spin_timeout = QSpinBox()
        self.spin_timeout.setRange(10, 90)
        self.spin_timeout.setValue(int(self.config.get("timeout_sec", 25)))
        self.spin_timeout.setFixedWidth(80)
        timeout_row.addWidget(lbl_timeout)
        timeout_row.addStretch()
        timeout_row.addWidget(self.spin_timeout)
        exec_layout.addLayout(timeout_row)

        # 4. Check Random Proxy
        random_row = QHBoxLayout()
        self.chk_random_proxy = QCheckBox("Check Random Proxy (Shuffle pool, test in random order – each exactly 1x)")
        self.chk_random_proxy.setStyleSheet("color: #38bdf8; font-weight: 700; font-size: 11px;")
        self.chk_random_proxy.setToolTip(
            "Shuffles the proxy pool so proxies are checked in random order instead of top-to-bottom.\n"
            "Every single proxy in the pool is still tested exactly once."
        )
        self.chk_random_proxy.setChecked(bool(self.config.get("random_order", False)))
        random_row.addWidget(self.chk_random_proxy)
        exec_layout.addLayout(random_row)

        # 5. AI Honeypot Shield
        honeypot_row = QHBoxLayout()
        self.chk_honeypot_shield = QCheckBox("AI Honeypot & Click-Trap Shield (Scan Google entry & submit for invisible traps)")
        self.chk_honeypot_shield.setStyleSheet("color: #38bdf8; font-weight: 700; font-size: 11px;")
        self.chk_honeypot_shield.setToolTip(
            "Actively checks the Google page and search results for deceptive overlays, invisible links,\n"
            "and decoy bot traps before clicking or interacting."
        )
        self.chk_honeypot_shield.setChecked(bool(self.config.get("enable_honeypot_shield", True)))
        honeypot_row.addWidget(self.chk_honeypot_shield)
        exec_layout.addLayout(honeypot_row)

        layout.addWidget(exec_group)


        # Group 2: Profile & Fingerprint Strategy (Multi-Selection)
        profile_group = QGroupBox("Profile & Fingerprint Selection")
        profile_layout = QVBoxLayout(profile_group)
        profile_layout.setSpacing(8)

        self.radio_temp = QRadioButton("Fresh Temporary Sandboxed Profiles (Randomized Clean Fingerprints)")
        self.radio_custom = QRadioButton("Use Selected Saved Profiles (Rotates fingerprints, replaces active proxy with test target)")
        
        self.profile_btn_group = QButtonGroup(self)
        self.profile_btn_group.addButton(self.radio_temp)
        self.profile_btn_group.addButton(self.radio_custom)

        current_mode = self.config.get("profile_mode", "temp")
        if current_mode == "custom":
            self.radio_custom.setChecked(True)
        else:
            self.radio_temp.setChecked(True)

        profile_layout.addWidget(self.radio_temp)
        profile_layout.addWidget(self.radio_custom)

        # Multi-Profile Selection List
        self.profile_list_widget = QListWidget()
        self.profile_list_widget.setFixedHeight(120)
        self.profile_list_widget.setStyleSheet("""
            QListWidget {
                background-color: rgba(14, 18, 29, 0.85);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 4px;
                color: #f1f5f9;
            }
            QListWidget::item {
                padding: 4px 8px;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background-color: rgba(255, 255, 255, 0.05);
            }
            QListWidget::item:selected {
                background-color: rgba(99, 102, 241, 0.25);
            }
        """)

        saved_profiles = self.profile_manager.list_profiles()
        selected_ids = set(self.config.get("profile_ids", []))
        if not selected_ids and self.config.get("profile_id"):
            selected_ids.add(self.config.get("profile_id"))

        for p in saved_profiles:
            p_name = p.get("name", "Unnamed Profile")
            p_id = p.get("id", "")
            p_os = p.get("os", "windows").capitalize()
            p_res = p.get("screen_resolution", "1920x1080")
            item = QListWidgetItem(f"{p_name} ({p_os}, {p_res})")
            item.setData(Qt.ItemDataRole.UserRole, p_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            
            if p_id in selected_ids or (current_mode == "custom" and not selected_ids):
                item.setCheckState(Qt.CheckState.Checked)
            else:
                item.setCheckState(Qt.CheckState.Unchecked)
            self.profile_list_widget.addItem(item)

        profile_layout.addWidget(self.profile_list_widget)

        # Selection Helpers
        sel_btn_row = QHBoxLayout()
        sel_btn_row.setSpacing(8)
        self.btn_select_all = QPushButton(" Select All")
        self.btn_select_all.setIcon(self._get_icon("check-circle"))
        self.btn_select_all.setProperty("class", "SecondaryButton")
        self.btn_select_all.setFixedHeight(26)
        self.btn_select_all.clicked.connect(self._select_all_profiles)
        
        self.btn_deselect_all = QPushButton(" Deselect All")
        self.btn_deselect_all.setIcon(self._get_icon("x-circle"))
        self.btn_deselect_all.setProperty("class", "SecondaryButton")
        self.btn_deselect_all.setFixedHeight(26)
        self.btn_deselect_all.clicked.connect(self._deselect_all_profiles)

        sel_btn_row.addWidget(self.btn_select_all)
        sel_btn_row.addWidget(self.btn_deselect_all)
        sel_btn_row.addStretch()
        profile_layout.addLayout(sel_btn_row)

        self.radio_temp.toggled.connect(self._toggle_profile_list_state)
        self._toggle_profile_list_state()

        layout.addWidget(profile_group)

        # Group 3: Local AI Captcha Solver & Prioritization
        captcha_group = QGroupBox("Local AI Captcha Solver & Prioritization")
        captcha_layout = QVBoxLayout(captcha_group)
        captcha_layout.setSpacing(10)

        # 1. Strategy Row
        strat_row = QHBoxLayout()
        lbl_strat = QLabel("Solver Strategy & Priority:")
        lbl_strat.setStyleSheet("color: #e2e8f0; font-weight: 600;")
        self.combo_captcha_strategy = QComboBox()
        self.combo_captcha_strategy.addItem("Auto-Full-Modus (7+1 KI-Team Swarm: Whisper CPU + Moondream + LLaVA/Gemini)", "swarm_auto")
        self.combo_captcha_strategy.addItem("Gemini Vision First  Audio Whisper Fallback (<500ms One-Shot)", "gemini_first")
        self.combo_captcha_strategy.addItem("Audio Whisper First  Vision Fallback (Fast & Reliable)", "audio_first")
        self.combo_captcha_strategy.addItem("Vision VLM First  Audio Fallback (Image Grids)", "vision_first")
        self.combo_captcha_strategy.addItem("Audio Whisper Only", "audio_only")
        self.combo_captcha_strategy.addItem("Vision VLM Only", "vision_only")
        self.combo_captcha_strategy.addItem("Disabled (Immediate failure on Captcha)", "disabled")

        current_strat = self.config.get("captcha_strategy", "swarm_auto")
        strat_idx = self.combo_captcha_strategy.findData(current_strat)
        if strat_idx >= 0:
            self.combo_captcha_strategy.setCurrentIndex(strat_idx)

        strat_row.addWidget(lbl_strat)
        strat_row.addStretch()
        strat_row.addWidget(self.combo_captcha_strategy)
        captcha_layout.addLayout(strat_row)

        # 2. Vision Model Row
        vision_row = QHBoxLayout()
        lbl_vision = QLabel("Vision Model for Captcha:")
        lbl_vision.setStyleSheet("color: #e2e8f0; font-weight: 600;")
        self.combo_captcha_vision = QComboBox()
        self.combo_captcha_vision.addItem("Auto-Full-Modus (7+1 KI-Team Swarm)", "swarm_auto")
        self.combo_captcha_vision.addItem("⚡ 50/50 Hybrid Co-Pilot (50% Gemini Cloud + 50% Local VLM)", "hybrid_50_50_gemini")
        self.combo_captcha_vision.addItem("Auto (SmolVLM / Moondream / LLaVA / Gemini)", "auto")
        self.combo_captcha_vision.addItem("Qwen 2.5 VL 3B (qwen2.5vl:3b)", "qwen2.5vl:3b")
        self.combo_captcha_vision.addItem("Microsoft Florence-2 Base (florence-2-base)", "florence-2-base")
        self.combo_captcha_vision.addItem("StepFun GOT-OCR 2.0 (got-ocr2)", "got-ocr2")
        self.combo_captcha_vision.addItem("Google Gemini 3.6 Flash (Cloud Ultra-Fast <500ms)", "gemini-3.6-flash")
        self.combo_captcha_vision.addItem("Google Gemini 1.5 Flash (Cloud Multimodal)", "gemini-1.5-flash")
        self.combo_captcha_vision.addItem("Google Gemini 1.5 Pro (Cloud Deep Multimodal)", "gemini-1.5-pro")
        self.combo_captcha_vision.addItem("LLaVA 7B (llava:7b)", "llava:7b")
        self.combo_captcha_vision.addItem("Moondream 2 (moondream:v2)", "moondream:v2")
        self.combo_captcha_vision.addItem("SmolVLM (smolvlm)", "smolvlm")

        current_v_model = self.config.get("vision_model", "swarm_auto")
        v_idx = self.combo_captcha_vision.findData(current_v_model)
        if v_idx >= 0:
            self.combo_captcha_vision.setCurrentIndex(v_idx)

        vision_row.addWidget(lbl_vision)
        vision_row.addStretch()
        vision_row.addWidget(self.combo_captcha_vision)
        captcha_layout.addLayout(vision_row)

        layout.addWidget(captcha_group)

        # Group 4: AI Model Selection
        ai_group = QGroupBox("AI Question Generation Model")
        ai_layout = QVBoxLayout(ai_group)
        ai_layout.setSpacing(10)

        lbl_ai_model = QLabel("Select Model for Human Google Queries:")
        lbl_ai_model.setStyleSheet("color: #e2e8f0; font-weight: 600;")
        ai_layout.addWidget(lbl_ai_model)

        self.combo_ai_model = QComboBox()
        self.combo_ai_model.addItem("Auto-Full-Modus (7+1 KI-Team Swarm: ONNX + Whisper + Qwen + Moondream + LLaVA + Gemini)", "swarm_auto_full")
        self.combo_ai_model.addItem("Auto (Qwen 2.5 1.5B / Fallback Organic Pool)", "auto")
        
        for model_id, model_label in config.get_all_ai_model_options():
            if model_id not in ["hybrid_auto", "swarm_auto_full"]:
                self.combo_ai_model.addItem(model_label, model_id)

        current_model = self.config.get("model_name", "swarm_auto_full")
        model_idx = self.combo_ai_model.findData(current_model)
        if model_idx >= 0:
            self.combo_ai_model.setCurrentIndex(model_idx)

        ai_layout.addWidget(self.combo_ai_model)
        layout.addWidget(ai_group)

        # Bottom Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "SecondaryButton")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton(" Save & Apply")
        save_btn.setIcon(self._get_icon("check"))
        save_btn.setProperty("class", "SecondaryButton")
        save_btn.clicked.connect(self._save_only)
        btn_layout.addWidget(save_btn)

        start_btn = QPushButton(" Start AI Verification")
        start_btn.setIcon(self._get_icon("play"))
        start_btn.setProperty("class", "PrimaryButton")
        start_btn.clicked.connect(self._start_and_accept)
        btn_layout.addWidget(start_btn)

        layout.addLayout(btn_layout)

    def _toggle_profile_list_state(self):
        is_custom = self.radio_custom.isChecked()
        self.profile_list_widget.setEnabled(is_custom)
        self.btn_select_all.setEnabled(is_custom)
        self.btn_deselect_all.setEnabled(is_custom)

    def _select_all_profiles(self):
        for i in range(self.profile_list_widget.count()):
            item = self.profile_list_widget.item(i)
            if item is not None:
                item.setCheckState(Qt.CheckState.Checked)

    def _deselect_all_profiles(self):
        for i in range(self.profile_list_widget.count()):
            item = self.profile_list_widget.item(i)
            if item is not None:
                item.setCheckState(Qt.CheckState.Unchecked)

    def _load_async_data(self):
        """Asynchronously queries Ollama for installed models to enrich the dropdown."""
        async def _fetch():
            try:
                ai_mgr = AIModelManager.get_instance()
                installed = await ai_mgr.list_installed_models()
                if installed:
                    existing_data = [self.combo_ai_model.itemData(i) for i in range(self.combo_ai_model.count())]
                    for m in installed:
                        m_name = m.get("name", "")
                        if m_name and m_name not in existing_data:
                            self.combo_ai_model.addItem(f"{m_name} (Installed)", m_name)
            except Exception:
                pass

        asyncio.create_task(_fetch())

    def _get_current_settings(self) -> Dict[str, Any]:
        is_custom = self.radio_custom.isChecked()
        selected_ids: List[str] = []
        if is_custom:
            for i in range(self.profile_list_widget.count()):
                item = self.profile_list_widget.item(i)
                if item is not None and item.checkState() == Qt.CheckState.Checked:
                    p_id = item.data(Qt.ItemDataRole.UserRole)
                    if p_id:
                        selected_ids.append(str(p_id))

        return {
            "concurrency": self.spin_concurrency.value(),
            "headless": bool(self.combo_headless.currentData()),
            "random_order": self.chk_random_proxy.isChecked(),
            "enable_honeypot_shield": self.chk_honeypot_shield.isChecked(),
            "profile_mode": "custom" if is_custom else "temp",
            "profile_ids": selected_ids,
            "captcha_strategy": str(self.combo_captcha_strategy.currentData() or "audio_first"),
            "vision_model": str(self.combo_captcha_vision.currentData() or "auto"),
            "model_name": str(self.combo_ai_model.currentData() or "auto"),
            "timeout_sec": self.spin_timeout.value()
        }



    def _save_only(self):
        self.config = self._get_current_settings()
        self.done(2)

    def _start_and_accept(self):
        self.config = self._get_current_settings()
        self.accept()

    def get_config(self) -> Dict[str, Any]:
        return self.config
