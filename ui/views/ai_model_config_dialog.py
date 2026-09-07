import os
import time
import asyncio
import logging
from typing import Dict, Any, Optional, List

from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTabWidget, QSlider, QDoubleSpinBox, QSpinBox,
    QLineEdit, QTextEdit, QComboBox, QCheckBox, QGroupBox,
    QFrame, QMessageBox, QProgressBar, QGridLayout, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon, QFont, QColor

from engine.ai_telemetry import AITelemetryBus
from engine.ai_model_manager import AIModelManager
from engine.ai_model_config import AIModelConfigManager, DEFAULT_MODEL_CONFIGS

logger = logging.getLogger("AIModelConfigDialog")


class AIModelConfigDialog(QDialog):
    """
    Highly Advanced AI Model Configuration & Hyperparameter Tuning Dialog.
    Features:
    - Deep sampling controls (Temperature, Top-P, Top-K, Mirostat, Penalties, Seed)
    - Hardware & VRAM management (Context window, GPU offload layers, Keep-Alive)
    - System Prompt & Anti-Bot Persona Directives with 1-Click Presets
    - Swarm Orchestration, Capability Assignment & Cascade Fallbacks
    - Real-Time Diagnostic Playground with Live Inference & Latency Tracking
    """
    config_saved = pyqtSignal(str)

    def __init__(self, model_id: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.telemetry = AITelemetryBus.get_instance()
        self.model_id = self.telemetry._normalize_model_id(model_id)
        self.ai_mgr = AIModelManager.get_instance()
        self.cfg_mgr = AIModelConfigManager.get_instance()
        
        self.meta = self.telemetry.models_meta.get(self.model_id, {
            "id": self.model_id,
            "display_name": self.model_id,
            "family": "Local-LLM",
            "color": "#38bdf8",
            "accent_rgb": "56, 189, 248",
            "icon": "◈",
            "role_title": "AI Specialist",
            "size_str": "Local",
            "typical_latency": "100ms"
        })
        self.config_data = self.cfg_mgr.get_model_config(self.model_id)

        self.setWindowTitle(f"AI Model Configurator: {self.meta.get('display_name', self.model_id)}")
        self.resize(760, 680)
        self.setMinimumSize(700, 600)
        
        self._init_ui()
        self._load_values_to_ui()

    def _get_icon(self, name: str) -> QIcon:
        p = os.path.join(os.path.dirname(__file__), "..", "assets", "icons", f"{name}.svg")
        if os.path.exists(p):
            return QIcon(p)
        return QIcon()

    def _init_ui(self):
        accent_color = self.meta.get("color", "#38bdf8")
        accent_rgb = self.meta.get("accent_rgb", "56, 189, 248")

        self.setStyleSheet(f"""
            QDialog {{
                background-color: #0b0e18;
                color: #f1f5f9;
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            }}
            QGroupBox {{
                background: rgba(18, 24, 40, 0.7);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
                margin-top: 18px;
                font-weight: bold;
                font-size: 11.5px;
                color: {accent_color};
                padding-top: 14px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                left: 10px;
            }}
            QLabel {{
                color: #cbd5e1;
                font-size: 11.5px;
            }}
            QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
                background-color: #121828;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 6px;
                color: #ffffff;
                padding: 5px 8px;
                font-size: 11.5px;
                selection-background-color: rgba({accent_rgb}, 0.5);
            }}
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
                border: 1px solid {accent_color};
            }}
            QSlider::groove:horizontal {{
                height: 5px;
                background: #1e293b;
                border-radius: 2px;
            }}
            QSlider::sub-page:horizontal {{
                background: {accent_color};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: #ffffff;
                border: 2px solid {accent_color};
                width: 14px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 7px;
            }}
            QTabWidget::pane {{
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
                background-color: rgba(14, 18, 30, 0.95);
            }}
            QTabBar::tab {{
                background: rgba(18, 24, 40, 0.8);
                color: #94a3b8;
                font-weight: 700;
                font-size: 11.5px;
                padding: 8px 16px;
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 4px;
            }}
            QTabBar::tab:selected {{
                background: rgba(25, 35, 60, 0.95);
                color: {accent_color};
                border: 1px solid rgba({accent_rgb}, 0.5);
                border-bottom: 2px solid {accent_color};
            }}
            QTabBar::tab:hover:!selected {{
                background: rgba(25, 35, 60, 0.8);
                color: #ffffff;
            }}
            QPushButton {{
                background: rgba(30, 41, 59, 0.8);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 6px;
                color: #ffffff;
                font-weight: 600;
                font-size: 11.5px;
                padding: 6px 14px;
            }}
            QPushButton:hover {{
                background: rgba(51, 65, 85, 0.9);
                border-color: rgba(255, 255, 255, 0.3);
            }}
            QPushButton#PrimaryAction {{
                background: {accent_color};
                color: #0b0e18;
                font-weight: 800;
                border: none;
            }}
            QPushButton#PrimaryAction:hover {{
                background: #ffffff;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        # -------------------------------------------------------------------------
        # 1. Header Banner & Identity Strip
        # -------------------------------------------------------------------------
        header_card = QFrame()
        header_card.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(18, 24, 40, 0.95), stop:1 rgba({accent_rgb}, 0.15));
                border: 1px solid rgba({accent_rgb}, 0.35);
                border-radius: 10px;
                padding: 10px 14px;
            }}
        """)
        h_layout = QHBoxLayout(header_card)
        h_layout.setContentsMargins(10, 8, 10, 8)
        h_layout.setSpacing(12)

        icon_lbl = QLabel(self.meta.get("icon", "◈"))
        icon_lbl.setStyleSheet(f"font-size: 24px; color: {accent_color};")
        h_layout.addWidget(icon_lbl)

        info_col = QVBoxLayout()
        info_col.setSpacing(2)

        title_row = QHBoxLayout()
        name_lbl = QLabel(self.meta.get("display_name", self.model_id))
        name_lbl.setStyleSheet("font-size: 15px; font-weight: 800; color: #ffffff;")
        title_row.addWidget(name_lbl)

        family_badge = QLabel(self.meta.get("family", "LLM"))
        family_badge.setStyleSheet(f"background: rgba({accent_rgb}, 0.2); color: {accent_color}; border: 1px solid rgba({accent_rgb}, 0.5); font-size: 10px; font-weight: 700; padding: 1px 6px; border-radius: 4px;")
        title_row.addWidget(family_badge)

        param_badge = QLabel(self.meta.get("size_str", "Local"))
        param_badge.setStyleSheet("background: rgba(51, 65, 85, 0.4); color: #94a3b8; font-size: 10px; font-weight: 600; padding: 1px 6px; border-radius: 4px;")
        title_row.addWidget(param_badge)

        title_row.addStretch()
        info_col.addLayout(title_row)

        desc_lbl = QLabel(self.meta.get("role_description", self.meta.get("role_title", "")))
        desc_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        info_col.addWidget(desc_lbl)

        h_layout.addLayout(info_col, stretch=1)

        # Quick Actions in Header
        self.btn_header_test = QPushButton(" Test Model")
        self.btn_header_test.setIcon(self._get_icon("play"))
        self.btn_header_test.clicked.connect(self._run_quick_test)
        h_layout.addWidget(self.btn_header_test)

        self.btn_header_vram = QPushButton(" Unload VRAM")
        self.btn_header_vram.setIcon(self._get_icon("zap"))
        self.btn_header_vram.clicked.connect(self._unload_model_vram)
        h_layout.addWidget(self.btn_header_vram)

        layout.addWidget(header_card)

        # -------------------------------------------------------------------------
        # 2. Main Tabbed Configuration Panel
        # -------------------------------------------------------------------------
        self.tabs = QTabWidget()

        # Tab 1: Hyperparameters & Sampling
        self.tabs.addTab(self._build_tab_hyperparameters(), "⚙️ Hyperparameters")

        # Tab 2: Context, VRAM & Hardware
        self.tabs.addTab(self._build_tab_hardware(), "🚀 Hardware & VRAM")

        # Tab 3: System Prompt & Directives
        self.tabs.addTab(self._build_tab_system_prompt(), "🛡️ System Directives")

        # Tab 4: Swarm Orchestration & Fallbacks
        self.tabs.addTab(self._build_tab_swarm(), "⎔ Swarm Cascade")

        # Tab 5: Diagnostic Playground
        self.tabs.addTab(self._build_tab_playground(), "🔬 Playground")

        layout.addWidget(self.tabs, stretch=1)

        # -------------------------------------------------------------------------
        # 3. Bottom Footer Action Bar
        # -------------------------------------------------------------------------
        footer = QHBoxLayout()
        footer.setSpacing(10)

        self.btn_reset = QPushButton(" Reset to Defaults")
        self.btn_reset.setIcon(self._get_icon("rotate-ccw"))
        self.btn_reset.clicked.connect(self._reset_to_defaults)
        footer.addWidget(self.btn_reset)

        footer.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        footer.addWidget(self.btn_cancel)

        self.btn_save = QPushButton(" Save & Apply Configuration")
        self.btn_save.setObjectName("PrimaryAction")
        self.btn_save.setIcon(self._get_icon("check"))
        self.btn_save.clicked.connect(self._save_and_apply)
        footer.addWidget(self.btn_save)

        layout.addLayout(footer)

    # -------------------------------------------------------------------------
    # TAB BUILDERS
    # -------------------------------------------------------------------------
    def _build_tab_hyperparameters(self) -> QWidget:
        widget = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; } QWidget#HypContent { background: transparent; }")

        content = QWidget()
        content.setObjectName("HypContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Sampling Group
        grp_sampling = QGroupBox("Core Generation & Sampling Parameters")
        grid = QGridLayout(grp_sampling)
        grid.setContentsMargins(12, 16, 12, 12)
        grid.setSpacing(10)

        # Temperature
        grid.addWidget(QLabel("Sampling Temperature:"), 0, 0)
        self.spin_temp = QDoubleSpinBox()
        self.spin_temp.setRange(0.0, 2.0)
        self.spin_temp.setSingleStep(0.05)
        self.slider_temp = QSlider(Qt.Orientation.Horizontal)
        self.slider_temp.setRange(0, 200)
        self.slider_temp.valueChanged.connect(lambda v: self.spin_temp.setValue(v / 100.0))
        self.spin_temp.valueChanged.connect(lambda v: self.slider_temp.setValue(int(v * 100)))
        
        temp_row = QHBoxLayout()
        temp_row.addWidget(self.slider_temp, stretch=1)
        temp_row.addWidget(self.spin_temp)
        grid.addLayout(temp_row, 0, 1)

        # Top-P
        grid.addWidget(QLabel("Top-P (Nucleus Sampling):"), 1, 0)
        self.spin_topp = QDoubleSpinBox()
        self.spin_topp.setRange(0.0, 1.0)
        self.spin_topp.setSingleStep(0.05)
        self.slider_topp = QSlider(Qt.Orientation.Horizontal)
        self.slider_topp.setRange(0, 100)
        self.slider_topp.valueChanged.connect(lambda v: self.spin_topp.setValue(v / 100.0))
        self.spin_topp.valueChanged.connect(lambda v: self.slider_topp.setValue(int(v * 100)))
        
        topp_row = QHBoxLayout()
        topp_row.addWidget(self.slider_topp, stretch=1)
        topp_row.addWidget(self.spin_topp)
        grid.addLayout(topp_row, 1, 1)

        # Top-K
        grid.addWidget(QLabel("Top-K (Vocabulary Truncation):"), 2, 0)
        self.spin_topk = QSpinBox()
        self.spin_topk.setRange(1, 200)
        grid.addWidget(self.spin_topk, 2, 1)

        # Repeat Penalty
        grid.addWidget(QLabel("Repetition Penalty:"), 3, 0)
        self.spin_repeat_pen = QDoubleSpinBox()
        self.spin_repeat_pen.setRange(0.5, 2.5)
        self.spin_repeat_pen.setSingleStep(0.05)
        grid.addWidget(self.spin_repeat_pen, 3, 1)

        # Presence & Frequency Penalty
        grid.addWidget(QLabel("Presence Penalty:"), 4, 0)
        self.spin_presence = QDoubleSpinBox()
        self.spin_presence.setRange(-2.0, 2.0)
        self.spin_presence.setSingleStep(0.1)
        grid.addWidget(self.spin_presence, 4, 1)

        grid.addWidget(QLabel("Frequency Penalty:"), 5, 0)
        self.spin_freq = QDoubleSpinBox()
        self.spin_freq.setRange(-2.0, 2.0)
        self.spin_freq.setSingleStep(0.1)
        grid.addWidget(self.spin_freq, 5, 1)

        layout.addWidget(grp_sampling)

        # Mirostat & Advanced Sampling
        grp_miro = QGroupBox("Mirostat Dynamic Entropy Sampling")
        grid_m = QGridLayout(grp_miro)
        grid_m.setContentsMargins(12, 16, 12, 12)
        grid_m.setSpacing(10)

        grid_m.addWidget(QLabel("Mirostat Mode:"), 0, 0)
        self.combo_mirostat = QComboBox()
        self.combo_mirostat.addItem("0 - Disabled (Standard Nucleus/Top-K)", 0)
        self.combo_mirostat.addItem("1 - Mirostat 1.0 (Target Entropy)", 1)
        self.combo_mirostat.addItem("2 - Mirostat 2.0 (Fast Entropy)", 2)
        grid_m.addWidget(self.combo_mirostat, 0, 1)

        grid_m.addWidget(QLabel("Mirostat Tau (Target Entropy):"), 1, 0)
        self.spin_miro_tau = QDoubleSpinBox()
        self.spin_miro_tau.setRange(0.0, 10.0)
        self.spin_miro_tau.setSingleStep(0.5)
        grid_m.addWidget(self.spin_miro_tau, 1, 1)

        grid_m.addWidget(QLabel("Mirostat Eta (Learning Rate):"), 2, 0)
        self.spin_miro_eta = QDoubleSpinBox()
        self.spin_miro_eta.setRange(0.01, 1.0)
        self.spin_miro_eta.setSingleStep(0.05)
        grid_m.addWidget(self.spin_miro_eta, 2, 1)

        layout.addWidget(grp_miro)

        # Stop Sequences & Seed
        grp_stop = QGroupBox("Seed & Custom Stop Sequences")
        grid_s = QGridLayout(grp_stop)
        grid_s.setContentsMargins(12, 16, 12, 12)
        grid_s.setSpacing(10)

        grid_s.addWidget(QLabel("RNG Random Seed (-1 for Auto):"), 0, 0)
        self.spin_seed = QSpinBox()
        self.spin_seed.setRange(-1, 999999999)
        grid_s.addWidget(self.spin_seed, 0, 1)

        grid_s.addWidget(QLabel("Stop Tokens (Comma Separated):"), 1, 0)
        self.txt_stop_seqs = QLineEdit()
        self.txt_stop_seqs.setPlaceholderText("<|im_end|>, </s>, Human:, Observation:")
        grid_s.addWidget(self.txt_stop_seqs, 1, 1)

        layout.addWidget(grp_stop)
        layout.addStretch()

        scroll.setWidget(content)
        w_layout = QVBoxLayout(widget)
        w_layout.setContentsMargins(0, 0, 0, 0)
        w_layout.addWidget(scroll)
        return widget

    def _build_tab_hardware(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(14)

        # Context Window & Tokens
        grp_ctx = QGroupBox("Context Window Length & Max Predictions")
        grid = QGridLayout(grp_ctx)
        grid.setContentsMargins(12, 16, 12, 12)
        grid.setSpacing(10)

        grid.addWidget(QLabel("Context Length (`num_ctx` tokens):"), 0, 0)
        self.combo_ctx = QComboBox()
        self.combo_ctx.setEditable(True)
        for ctx_val in [512, 1024, 2048, 4096, 8192, 16384, 32768, 65536]:
            self.combo_ctx.addItem(f"{ctx_val} tokens", ctx_val)
        grid.addWidget(self.combo_ctx, 0, 1)

        grid.addWidget(QLabel("Max Generation Length (`num_predict`):"), 1, 0)
        self.combo_predict = QComboBox()
        self.combo_predict.setEditable(True)
        for p_val in [64, 128, 256, 512, 1024, 2048, 4096, 8192, -1]:
            label = "Unlimited (-1)" if p_val == -1 else f"{p_val} tokens"
            self.combo_predict.addItem(label, p_val)
        grid.addWidget(self.combo_predict, 1, 1)

        layout.addWidget(grp_ctx)

        # GPU / CPU Offloading
        grp_hw = QGroupBox("Hardware Layer Offloading & Threading")
        grid_hw = QGridLayout(grp_hw)
        grid_hw.setContentsMargins(12, 16, 12, 12)
        grid_hw.setSpacing(10)

        grid_hw.addWidget(QLabel("GPU Offload Layers (`num_gpu`):"), 0, 0)
        self.spin_gpu_layers = QSpinBox()
        self.spin_gpu_layers.setRange(-1, 200)
        self.spin_gpu_layers.setSpecialValueText("Auto / All Layers (-1)")
        grid_hw.addWidget(self.spin_gpu_layers, 0, 1)

        grid_hw.addWidget(QLabel("CPU Inference Threads (`num_thread`):"), 1, 0)
        self.spin_cpu_threads = QSpinBox()
        self.spin_cpu_threads.setRange(0, 64)
        self.spin_cpu_threads.setSpecialValueText("Auto (All Cores)")
        grid_hw.addWidget(self.spin_cpu_threads, 1, 1)

        grid_hw.addWidget(QLabel("VRAM Cache Keep-Alive Duration:"), 2, 0)
        self.combo_keep_alive = QComboBox()
        self.combo_keep_alive.addItem("5 Minutes ('5m')", "5m")
        self.combo_keep_alive.addItem("15 Minutes ('15m')", "15m")
        self.combo_keep_alive.addItem("30 Minutes ('30m')", "30m")
        self.combo_keep_alive.addItem("1 Hour ('1h')", "1h")
        self.combo_keep_alive.addItem("24 Hours ('24h')", "24h")
        self.combo_keep_alive.addItem("Persistent in GPU Memory ('-1')", "-1")
        self.combo_keep_alive.addItem("Immediate Unload after Task ('0s')", "0s")
        grid_hw.addWidget(self.combo_keep_alive, 2, 1)

        self.chk_flash_att = QCheckBox("Enable Flash Attention & KV-Cache FP16 Acceleration")
        self.chk_flash_att.setStyleSheet("color: #38bdf8; font-weight: 700;")
        grid_hw.addWidget(self.chk_flash_att, 3, 0, 1, 2)

        layout.addWidget(grp_hw)
        layout.addStretch()
        return widget

    def _build_tab_system_prompt(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Preset Buttons Strip
        lbl_presets = QLabel("<b>One-Click Specialized Anti-Bot & Task Presets:</b>")
        layout.addWidget(lbl_presets)

        preset_row = QHBoxLayout()
        preset_row.setSpacing(6)

        presets = [
            ("🛡️ Anti-Bot Evasion", "You are an Anti-Bot & Evasion Strategist. Perform deep cognitive reasoning and synthesize stealthy browsing actions to bypass Cloudflare Turnstile, DataDome, and Kasada."),
            ("⚇ GDPR Strict Reject", "You are a high-precision GDPR/ePrivacy cookie solver. Detect buttons representing strict rejection or necessary-only consent. Always output candidate index in valid JSON."),
            ("👁 Multimodal Grounding", "You are an expert multimodal UI coordinate grounder. Return precise bounding boxes [ymin, xmin, ymax, xmax] or grid indexes for target UI elements."),
            ("⚡ Tool-Calling Schema", "You are an autonomous function-calling agent. Analyze the DOM and user intentions, then formulate exact JSON Playwright tool-call actions."),
            ("☊ Audio STT Decoder", "Acoustic speech-to-text decoder. Decipher distorted captcha voice recordings and extract numeric sequences.")
        ]

        for p_title, p_prompt in presets:
            btn = QPushButton(p_title)
            btn.setStyleSheet("font-size: 10.5px; padding: 4px 8px;")
            btn.clicked.connect(lambda _, pr=p_prompt: self.txt_system_prompt.setPlainText(pr))
            preset_row.addWidget(btn)

        layout.addLayout(preset_row)

        # System Prompt Text Edit
        lbl_prompt = QLabel("Active System Prompt / Persona Directive:")
        layout.addWidget(lbl_prompt)

        self.txt_system_prompt = QTextEdit()
        self.txt_system_prompt.setStyleSheet("""
            background-color: #0d111d;
            border: 1px solid rgba(56, 189, 248, 0.3);
            border-radius: 8px;
            color: #a5b4fc;
            font-family: 'JetBrains Mono', 'Fira Code', monospace;
            font-size: 11.5px;
            padding: 8px;
        """)
        layout.addWidget(self.txt_system_prompt, stretch=1)

        # Output Formatting
        fmt_row = QHBoxLayout()
        self.chk_json_mode = QCheckBox("Enforce Strict JSON Schema Format (`format: json`)")
        self.chk_json_mode.setStyleSheet("color: #10b981; font-weight: 700;")
        fmt_row.addWidget(self.chk_json_mode)

        fmt_row.addStretch()
        layout.addLayout(fmt_row)

        return widget

    def _build_tab_swarm(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        grp_role = QGroupBox("Swarm Pipeline Assignment & Priority")
        grid = QGridLayout(grp_role)
        grid.setContentsMargins(12, 16, 12, 12)
        grid.setSpacing(10)

        grid.addWidget(QLabel("Swarm Role Priority:"), 0, 0)
        self.combo_swarm_priority = QComboBox()
        self.combo_swarm_priority.addItem("Primary (First-Line Execution)", "Primary")
        self.combo_swarm_priority.addItem("Secondary (Assisting / Parallel)", "Secondary")
        self.combo_swarm_priority.addItem("Fallback (Only on Primary Timeout/Error)", "Fallback")
        self.combo_swarm_priority.addItem("Disabled (Excluded from Swarm)", "Disabled")
        grid.addWidget(self.combo_swarm_priority, 0, 1)

        grid.addWidget(QLabel("Inference Timeout Threshold:"), 1, 0)
        self.spin_timeout = QSpinBox()
        self.spin_timeout.setRange(1, 120)
        self.spin_timeout.setSuffix(" seconds")
        grid.addWidget(self.spin_timeout, 1, 1)

        grid.addWidget(QLabel("Cascade Fallback Target Model:"), 2, 0)
        self.combo_fallback_model = QComboBox()
        for m_id, m_meta in self.telemetry.models_meta.items():
            if m_id != self.model_id:
                self.combo_fallback_model.addItem(f"{m_meta.get('icon', '')} {m_meta.get('display_name', m_id)}", m_id)
        grid.addWidget(self.combo_fallback_model, 2, 1)

        layout.addWidget(grp_role)

        # Capabilities Checkboxes
        grp_caps = QGroupBox("Assigned Capabilities & Task Delegation")
        vbox_caps = QVBoxLayout(grp_caps)
        vbox_caps.setContentsMargins(12, 16, 12, 12)
        vbox_caps.setSpacing(8)

        self.cap_checkboxes: Dict[str, QCheckBox] = {}
        all_caps = [
            "Reading Dwell Time", "Content Density", "Micro-DOM Parsing",
            "GDPR Consent Resolution", "Shadow DOM Parsing", "Navigation Filtering",
            "Topic Intent Coherence", "Search Query Synthesis", "Clickstream Trajectory",
            "CoT Anti-Bot Reasoning", "Countermeasure Strategy", "JS Injection Synthesis",
            "Structured Tool Execution", "Multimodal Coordinate Grounding", "reCAPTCHA Tile Analysis",
            "Fast Viewport OCR", "reCAPTCHA Audio STT", "Fingerprint Anomaly Detection",
            "Biomechanical Fitts's Law Curves", "One-Shot reCAPTCHA Grid Solver"
        ]

        grid_caps = QGridLayout()
        grid_caps.setSpacing(6)
        for i, cap in enumerate(all_caps):
            chk = QCheckBox(cap)
            self.cap_checkboxes[cap] = chk
            grid_caps.addWidget(chk, i // 2, i % 2)

        vbox_caps.addLayout(grid_caps)
        layout.addWidget(grp_caps)
        layout.addStretch()

        return widget

    def _build_tab_playground(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        layout.addWidget(QLabel("<b>Live Interactive Inference & Latency Diagnostic Sandbox:</b>"))

        # Input Prompt Field
        self.txt_play_input = QTextEdit()
        self.txt_play_input.setPlaceholderText("Enter test prompt or JSON schema context here...")
        self.txt_play_input.setMaximumHeight(90)
        self.txt_play_input.setPlainText("Analyze Cloudflare Turnstile bot detection and summarize evasion rule in JSON.")
        layout.addWidget(self.txt_play_input)

        # Run Test Row
        run_row = QHBoxLayout()
        self.btn_run_diag = QPushButton(" Run Inference Diagnostic")
        self.btn_run_diag.setIcon(self._get_icon("play"))
        self.btn_run_diag.setProperty("class", "PrimaryButton")
        self.btn_run_diag.clicked.connect(self._run_playground_diagnostic)
        run_row.addWidget(self.btn_run_diag)

        self.lbl_diag_latency = QLabel("⏱ Latency: -")
        self.lbl_diag_latency.setStyleSheet("color: #a855f7; font-weight: 700;")
        run_row.addWidget(self.lbl_diag_latency)

        self.lbl_diag_status = QLabel("● Standby")
        self.lbl_diag_status.setStyleSheet("color: #94a3b8; font-weight: 700;")
        run_row.addWidget(self.lbl_diag_status)

        run_row.addStretch()
        layout.addLayout(run_row)

        # Output Display
        layout.addWidget(QLabel("Diagnostic Response & Token Output:"))
        self.txt_play_output = QTextEdit()
        self.txt_play_output.setReadOnly(True)
        self.txt_play_output.setStyleSheet("""
            background-color: #070a13;
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 8px;
            color: #34d399;
            font-family: 'JetBrains Mono', 'Fira Code', monospace;
            font-size: 11.5px;
            padding: 8px;
        """)
        layout.addWidget(self.txt_play_output, stretch=1)

        return widget

    # -------------------------------------------------------------------------
    # DATA BINDING & SAVE LOGIC
    # -------------------------------------------------------------------------
    def _load_values_to_ui(self):
        cfg = self.config_data

        # Tab 1: Hyperparameters
        temp = float(cfg.get("temperature", 0.1))
        self.spin_temp.setValue(temp)
        self.slider_temp.setValue(int(temp * 100))

        topp = float(cfg.get("top_p", 0.9))
        self.spin_topp.setValue(topp)
        self.slider_topp.setValue(int(topp * 100))

        self.spin_topk.setValue(int(cfg.get("top_k", 40)))
        self.spin_repeat_pen.setValue(float(cfg.get("repeat_penalty", 1.1)))
        self.spin_presence.setValue(float(cfg.get("presence_penalty", 0.0)))
        self.spin_freq.setValue(float(cfg.get("frequency_penalty", 0.0)))

        # Mirostat
        miro_mode = int(cfg.get("mirostat", 0))
        idx_m = self.combo_mirostat.findData(miro_mode)
        if idx_m >= 0:
            self.combo_mirostat.setCurrentIndex(idx_m)
        self.spin_miro_tau.setValue(float(cfg.get("mirostat_tau", 5.0)))
        self.spin_miro_eta.setValue(float(cfg.get("mirostat_eta", 0.1)))

        # Seed & Stop
        self.spin_seed.setValue(int(cfg.get("seed", -1)))
        stops = cfg.get("stop_sequences", [])
        self.txt_stop_seqs.setText(", ".join(stops) if isinstance(stops, list) else str(stops))

        # Tab 2: Hardware
        ctx = int(cfg.get("num_ctx", 8192))
        idx_c = self.combo_ctx.findData(ctx)
        if idx_c >= 0:
            self.combo_ctx.setCurrentIndex(idx_c)
        else:
            self.combo_ctx.setEditText(str(ctx))

        pred = int(cfg.get("num_predict", 1024))
        idx_p = self.combo_predict.findData(pred)
        if idx_p >= 0:
            self.combo_predict.setCurrentIndex(idx_p)
        else:
            self.combo_predict.setEditText(str(pred))

        self.spin_gpu_layers.setValue(int(cfg.get("num_gpu", -1)))
        self.spin_cpu_threads.setValue(int(cfg.get("num_thread", 0)))

        keep = str(cfg.get("keep_alive", "15m"))
        idx_k = self.combo_keep_alive.findData(keep)
        if idx_k >= 0:
            self.combo_keep_alive.setCurrentIndex(idx_k)

        self.chk_flash_att.setChecked(bool(cfg.get("flash_attention", True)))

        # Tab 3: System Prompt
        self.txt_system_prompt.setPlainText(str(cfg.get("system_prompt", "")))
        self.chk_json_mode.setChecked(bool(cfg.get("json_mode", False)))

        # Tab 4: Swarm
        priority = str(cfg.get("swarm_priority", "Primary"))
        idx_pr = self.combo_swarm_priority.findData(priority)
        if idx_pr >= 0:
            self.combo_swarm_priority.setCurrentIndex(idx_pr)

        self.spin_timeout.setValue(int(cfg.get("timeout_seconds", 15)))

        fallback = str(cfg.get("fallback_model", "qwen2.5:1.5b"))
        idx_fb = self.combo_fallback_model.findData(fallback)
        if idx_fb >= 0:
            self.combo_fallback_model.setCurrentIndex(idx_fb)

        caps = cfg.get("capabilities", [])
        for cap_name, chk_box in self.cap_checkboxes.items():
            chk_box.setChecked(cap_name in caps)

    def _collect_ui_to_dict(self) -> Dict[str, Any]:
        # Parse context
        try:
            ctx_text = self.combo_ctx.currentText().split(" ")[0].strip()
            num_ctx = int(ctx_text)
        except Exception:
            num_ctx = 8192

        # Parse predict
        try:
            pred_text = self.combo_predict.currentText().split(" ")[0].strip()
            if "Unlimited" in self.combo_predict.currentText() or pred_text == "-1":
                num_predict = -1
            else:
                num_predict = int(pred_text)
        except Exception:
            num_predict = 1024

        # Parse stop tokens
        raw_stops = self.txt_stop_seqs.text().strip()
        stop_list = [s.strip() for s in raw_stops.split(",") if s.strip()]

        selected_caps = [name for name, chk in self.cap_checkboxes.items() if chk.isChecked()]

        return {
            "temperature": round(self.spin_temp.value(), 2),
            "top_p": round(self.spin_topp.value(), 2),
            "top_k": self.spin_topk.value(),
            "repeat_penalty": round(self.spin_repeat_pen.value(), 2),
            "presence_penalty": round(self.spin_presence.value(), 2),
            "frequency_penalty": round(self.spin_freq.value(), 2),
            "mirostat": self.combo_mirostat.currentData() or 0,
            "mirostat_tau": round(self.spin_miro_tau.value(), 2),
            "mirostat_eta": round(self.spin_miro_eta.value(), 2),
            "seed": self.spin_seed.value(),
            "stop_sequences": stop_list,
            "num_ctx": num_ctx,
            "num_predict": num_predict,
            "num_gpu": self.spin_gpu_layers.value(),
            "num_thread": self.spin_cpu_threads.value(),
            "keep_alive": self.combo_keep_alive.currentData() or "15m",
            "flash_attention": self.chk_flash_att.isChecked(),
            "system_prompt": self.txt_system_prompt.toPlainText().strip(),
            "json_mode": self.chk_json_mode.isChecked(),
            "swarm_priority": self.combo_swarm_priority.currentData() or "Primary",
            "timeout_seconds": self.spin_timeout.value(),
            "fallback_model": self.combo_fallback_model.currentData() or "qwen2.5:1.5b",
            "capabilities": selected_caps
        }

    def _save_and_apply(self):
        new_cfg = self._collect_ui_to_dict()
        self.cfg_mgr.save_model_config(self.model_id, new_cfg)
        self.config_saved.emit(self.model_id)
        QMessageBox.information(
            self,
            "Configuration Saved",
            f"Configuration for '{self.meta.get('display_name', self.model_id)}' saved and applied to AI Swarm runtime!"
        )
        self.accept()

    def _reset_to_defaults(self):
        confirm = QMessageBox.question(
            self,
            "Reset Configuration",
            f"Are you sure you want to reset all parameters for '{self.meta.get('display_name', self.model_id)}' to default baseline?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.config_data = self.cfg_mgr.reset_model_config(self.model_id)
            self._load_values_to_ui()
            QMessageBox.information(self, "Reset", "Model parameters reset to factory defaults.")

    def _unload_model_vram(self):
        async def vram_task():
            try:
                ok = await self.ai_mgr.unload_all_models_from_vram()
                if ok:
                    QMessageBox.information(self, "VRAM Released", f"Model '{self.model_id}' purged from GPU memory.")
                else:
                    QMessageBox.warning(self, "VRAM", "Ollama server offline or VRAM already clear.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to unload VRAM: {e}")

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(vram_task())
        except RuntimeError:
            pass

    def _run_quick_test(self):
        self.tabs.setCurrentIndex(4)  # Switch to Playground tab
        self._run_playground_diagnostic()

    def _run_playground_diagnostic(self):
        self.btn_run_diag.setEnabled(False)
        self.lbl_diag_status.setText("⭍ INFERENCING...")
        self.lbl_diag_status.setStyleSheet("color: #38bdf8; font-weight: 700;")
        self.txt_play_output.setPlainText("Sending inference request to model with current hyperparameters...")

        prompt = self.txt_play_input.toPlainText().strip()
        sys_prompt = self.txt_system_prompt.toPlainText().strip()
        is_json = self.chk_json_mode.isChecked()

        async def diag_task():
            t0 = time.time()
            try:
                if "gemini" in self.model_id:
                    from engine.ai_gemini_client import GeminiApiClient
                    g_client = GeminiApiClient.get_instance()
                    if g_client.is_configured():
                        resp = await g_client.generate_text(
                            prompt=prompt,
                            system_prompt=sys_prompt,
                            model=self.model_id,
                            json_mode=is_json
                        )
                    else:
                        resp = "Gemini API key not configured. Please set in Settings."
                elif "whisper" in self.model_id:
                    resp = f"Whisper STT Diagnostic: Audio challenge pipeline ready (Simulated decode: '4 8 2 9 0 1')"
                elif "onnx" in self.model_id:
                    from engine.ml_fingerprint_evaluator import MLFingerprintEvaluator
                    dummy_fp = {
                        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/132.0.0.0",
                        "webgl_vendor": "Google Inc. (NVIDIA)",
                        "webgl_renderer": "ANGLE (NVIDIA RTX 4090)",
                        "hardware_concurrency": 16,
                        "device_memory": 32,
                        "screen_res": "1920x1080"
                    }
                    score, anoms, recs = MLFingerprintEvaluator.evaluate(dummy_fp)
                    resp = f"ONNX Isolation Forest Anomaly Score: {score:.4f}\nAnomalies: {anoms}\nRecommendations: {recs}"
                else:
                    resp = await self.ai_mgr.generate_response(
                        prompt=prompt,
                        system_prompt=sys_prompt,
                        model_name=self.model_id,
                        json_mode=is_json,
                        operation="🔬 Playground Diagnostic Test"
                    )

                dur_ms = int((time.time() - t0) * 1000.0)
                self.lbl_diag_latency.setText(f"⏱ Latency: {dur_ms} ms")
                self.lbl_diag_status.setText("● SUCCESS")
                self.lbl_diag_status.setStyleSheet("color: #34d399; font-weight: 700;")
                self.txt_play_output.setPlainText(resp or "Empty response received.")
            except Exception as e:
                self.lbl_diag_status.setText("● ERROR")
                self.lbl_diag_status.setStyleSheet("color: #f87171; font-weight: 700;")
                self.txt_play_output.setPlainText(f"Diagnostic test error:\n{e}")
            finally:
                self.btn_run_diag.setEnabled(True)

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(diag_task())
        except RuntimeError:
            pass
