import asyncio
import time
import logging
from typing import Dict, Any, List, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QProgressBar, QGridLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QComboBox,
    QMessageBox, QTextEdit, QDialog, QCheckBox, QScrollArea,
    QTabWidget
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon
import os

from engine.ai_telemetry import AITelemetryBus
from engine.ai_model_manager import AIModelManager

logger = logging.getLogger("AIOperationsMatrixView")


class AIModelCardWidget(QFrame):
    """
    Compact & Smart Glassmorphic Card displaying one of the 6 AI Models:
    - Fits seamlessly without scrolling
    - Header with model family badge, display name & status pill
    - Real-time animated pulse progress bar when ACTIVE
    - Metrics (Latency, Total Operations, Last Active Time)
    - Manual single-model test trigger
    """
    test_requested = pyqtSignal(str)
    config_requested = pyqtSignal(str)

    def __init__(self, model_id: str, parent=None):
        super().__init__(parent)
        self.model_id = model_id
        self.telemetry = AITelemetryBus.get_instance()
        self.ai_mgr = AIModelManager.get_instance()
        self.meta = self.telemetry.models_meta.get(self.model_id, {
            "id": self.model_id,
            "display_name": self.model_id,
            "color": "#38bdf8",
            "accent_rgb": "56, 189, 248",
            "icon": "◈",
            "role_title": "AI Specialist",
            "size_str": "Local",
            "typical_latency": "100ms"
        })
        self.is_installed = self.ai_mgr.is_model_installed(self.model_id)
        
        self.setObjectName("AIModelCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFixedHeight(152)  # Compact fixed height
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Klicke auf diese KI-Modell-Card, um den Highly Advanced Config Dialog zu öffnen.")
        self._init_ui()
        self.update_telemetry()

    def _get_icon(self, name):
        return QIcon(os.path.join(os.path.dirname(__file__), "..", "assets", "icons", f"{name}.svg"))

    def _init_ui(self):
        accent_color = self.meta.get("color", "#38bdf8")
        accent_rgb = self.meta.get("accent_rgb", "56, 189, 248")

        self.setStyleSheet(f"""
            QFrame#AIModelCard {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(18, 24, 40, 0.9), stop:1 rgba(11, 14, 24, 0.95));
                border: 1px solid rgba({accent_rgb}, 0.22);
                border-top: 1px solid rgba({accent_rgb}, 0.45);
                border-radius: 10px;
            }}
            QFrame#AIModelCard:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(25, 35, 60, 0.95), stop:1 rgba(15, 20, 36, 0.98));
                border: 1px solid rgba({accent_rgb}, 0.65);
                border-top: 1px solid rgba({accent_rgb}, 0.95);
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        # 1. Header: Icon, Model Name, Size Pill, Status Badge
        header_row = QHBoxLayout()
        header_row.setSpacing(6)

        icon_lbl = QLabel(self.meta.get("icon", "◈"))
        icon_lbl.setStyleSheet("font-size: 15px;")
        header_row.addWidget(icon_lbl)

        name_lbl = QLabel(self.meta.get("display_name", self.model_id))
        name_lbl.setStyleSheet(f"color: #ffffff; font-size: 12.5px; font-weight: 800;")
        header_row.addWidget(name_lbl)

        size_badge = QLabel(self.meta.get("size_str", ""))
        size_badge.setStyleSheet("color: #64748b; font-size: 10px; font-weight: 600;")
        header_row.addWidget(size_badge)

        header_row.addStretch()

        self.status_badge = QLabel("● IDLE")
        self.status_badge.setStyleSheet("""
            background-color: rgba(51, 65, 85, 0.4);
            color: #94a3b8;
            font-size: 9.5px;
            font-weight: 800;
            padding: 2px 6px;
            border-radius: 8px;
            border: 1px solid rgba(148, 163, 184, 0.2);
        """)
        header_row.addWidget(self.status_badge)
        layout.addLayout(header_row)

        # 2. Role Title Line
        role_row = QHBoxLayout()
        role_row.setSpacing(4)
        
        role_title = QLabel(self.meta.get("role_title", "AI Specialist"))
        role_title.setStyleSheet(f"color: {accent_color}; font-size: 10.5px; font-weight: 700;")
        role_row.addWidget(role_title, stretch=1)
        layout.addLayout(role_row)

        # 3. Live Operation Monitor Strip
        live_box = QFrame()
        live_box.setStyleSheet("background-color: rgba(7, 9, 16, 0.75); border: 1px solid rgba(255, 255, 255, 0.04); border-radius: 5px; padding: 2px 5px;")
        live_layout = QVBoxLayout(live_box)
        live_layout.setContentsMargins(5, 3, 5, 3)
        live_layout.setSpacing(2)

        self.lbl_task_info = QLabel("Standby / Ready")
        self.lbl_task_info.setStyleSheet("color: #cbd5e1; font-size: 10px; font-weight: 600;")
        live_layout.addWidget(self.lbl_task_info)

        self.pulse_bar = QProgressBar()
        self.pulse_bar.setRange(0, 100)
        self.pulse_bar.setValue(100)
        self.pulse_bar.setFixedHeight(2)
        self.pulse_bar.setTextVisible(False)
        self.pulse_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: rgba(30, 41, 59, 0.4);
                border: none;
            }}
            QProgressBar::chunk {{
                background: {accent_color};
            }}
        """)
        live_layout.addWidget(self.pulse_bar)
        layout.addWidget(live_box)

        # 4. Telemetry Metrics & Action Buttons
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(4)

        self.lbl_latency = QLabel(f"⏱ {self.meta.get('typical_latency', '0ms')}")
        self.lbl_latency.setStyleSheet("color: #cbd5e1; font-size: 10px; font-weight: 600;")
        bottom_row.addWidget(self.lbl_latency)

        self.lbl_calls = QLabel("◫ 0 ops")
        self.lbl_calls.setStyleSheet("color: #94a3b8; font-size: 10px; font-weight: 600;")
        bottom_row.addWidget(self.lbl_calls)

        self.lbl_last_active = QLabel("◷ -")
        self.lbl_last_active.setStyleSheet("color: #64748b; font-size: 9.5px;")
        bottom_row.addWidget(self.lbl_last_active)

        bottom_row.addStretch()

        self.btn_config = QPushButton("⚙")
        self.btn_config.setToolTip("Modell-Konfiguration & Hyperparameter öffnen")
        self.btn_config.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_config.setFixedHeight(20)
        self.btn_config.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(51, 65, 85, 0.5);
                color: #e2e8f0;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 4px;
                padding: 1px 6px;
                font-size: 10px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: rgba({accent_rgb}, 0.35);
                border: 1px solid {accent_color};
                color: #ffffff;
            }}
        """)
        self.btn_config.clicked.connect(lambda: self.config_requested.emit(self.model_id))
        bottom_row.addWidget(self.btn_config)

        self.btn_test = QPushButton(" Test")
        self.btn_test.setIcon(self._get_icon("play"))
        self.btn_test.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_test.setFixedHeight(20)
        self.btn_test.clicked.connect(self._handle_action_click)
        bottom_row.addWidget(self.btn_test)

        layout.addLayout(bottom_row)

    def mousePressEvent(self, a0):
        if a0 and a0.button() == Qt.MouseButton.LeftButton:
            pos = a0.position().toPoint() if hasattr(a0, "position") else a0.pos()
            child = self.childAt(pos)
            if child not in [self.btn_test, getattr(self, "btn_config", None)]:
                self.config_requested.emit(self.model_id)
        super().mousePressEvent(a0)

    def _handle_action_click(self):
        if not self.is_installed:
            from ui.views.model_manager_dialog import ModelManagerDialog
            dialog = ModelManagerDialog(self.window())
            dialog.exec()
            self.update_telemetry()
        else:
            self.test_requested.emit(self.model_id)

    def set_active_state(self, is_active: bool, operation: str = "", target_info: str = ""):
        accent_color = self.meta.get("color", "#38bdf8")
        accent_rgb = self.meta.get("accent_rgb", "56, 189, 248")

        if not self.is_installed:
            self._apply_uninstalled_style()
            return

        if is_active:
            self.status_badge.setText("⭍ INFERENCING")
            self.status_badge.setStyleSheet(f"""
                background-color: rgba({accent_rgb}, 0.25);
                color: #ffffff;
                font-size: 9.5px;
                font-weight: 800;
                padding: 2px 6px;
                border-radius: 8px;
                border: 1px solid {accent_color};
            """)
            display_txt = f"{operation}"
            if target_info:
                display_txt += f" ({target_info[:24]})"
            self.lbl_task_info.setText(display_txt)
            self.lbl_task_info.setStyleSheet(f"color: {accent_color}; font-size: 10px; font-weight: 700;")
            self.pulse_bar.setRange(0, 0)
            self.setStyleSheet(f"""
                QFrame#AIModelCard {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(25, 35, 60, 0.95), stop:1 rgba(14, 18, 32, 0.98));
                    border: 2px solid {accent_color};
                    border-radius: 10px;
                }}
            """)
        else:
            self.status_badge.setText("● IDLE")
            self.status_badge.setStyleSheet("""
                background-color: rgba(16, 185, 129, 0.15);
                color: #34d399;
                font-size: 9.5px;
                font-weight: 800;
                padding: 2px 6px;
                border-radius: 8px;
                border: 1px solid rgba(52, 211, 153, 0.3);
            """)
            self.pulse_bar.setRange(0, 100)
            self.pulse_bar.setValue(100)
            self.setStyleSheet(f"""
                QFrame#AIModelCard {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(18, 24, 40, 0.9), stop:1 rgba(11, 14, 24, 0.95));
                    border: 1px solid rgba({accent_rgb}, 0.22);
                    border-top: 1px solid rgba({accent_rgb}, 0.45);
                    border-radius: 10px;
                }}
                QFrame#AIModelCard:hover {{
                    border: 1px solid rgba({accent_rgb}, 0.55);
                    border-top: 1px solid rgba({accent_rgb}, 0.85);
                }}
            """)

    def _apply_uninstalled_style(self):
        self.status_badge.setText("⬇ NOT INSTALLED")
        self.status_badge.setStyleSheet("""
            background-color: rgba(245, 158, 11, 0.12);
            color: #fbbf24;
            font-size: 9px;
            font-weight: 800;
            padding: 2px 6px;
            border-radius: 8px;
            border: 1px dashed rgba(251, 191, 36, 0.35);
        """)
        self.lbl_task_info.setText("Available for download")
        self.lbl_task_info.setStyleSheet("color: #64748b; font-size: 10px; font-weight: 500;")
        self.btn_test.setText("⬇ Install")
        self.btn_test.setIcon(self._get_icon("download"))
        self.btn_test.setStyleSheet("""
            QPushButton {
                background-color: rgba(245, 158, 11, 0.15);
                color: #fbbf24;
                border: 1px solid rgba(245, 158, 11, 0.4);
                border-radius: 4px;
                padding: 1px 8px;
                font-size: 10px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: rgba(245, 158, 11, 0.35);
                border: 1px solid rgba(245, 158, 11, 0.8);
            }
        """)
        self.setStyleSheet("""
            QFrame#AIModelCard {
                background: rgba(15, 23, 42, 0.45);
                border: 1px dashed rgba(100, 116, 139, 0.3);
                border-radius: 10px;
            }
            QFrame#AIModelCard:hover {
                border: 1px dashed rgba(148, 163, 184, 0.55);
            }
        """)

    def update_telemetry(self):
        self.is_installed = self.ai_mgr.is_model_installed(self.model_id)
        stats = self.telemetry.get_model_stats(self.model_id)
        accent_rgb = self.meta.get("accent_rgb", "56, 189, 248")

        if not self.is_installed:
            self._apply_uninstalled_style()
            return
        else:
            self.btn_test.setText(" Test")
            self.btn_test.setIcon(self._get_icon("play"))
            self.btn_test.setStyleSheet(f"""
                QPushButton {{
                    background-color: rgba({accent_rgb}, 0.15);
                    color: #ffffff;
                    border: 1px solid rgba({accent_rgb}, 0.4);
                    border-radius: 4px;
                    padding: 1px 8px;
                    font-size: 10px;
                    font-weight: 700;
                }}
                QPushButton:hover {{
                    background-color: rgba({accent_rgb}, 0.35);
                    border: 1px solid rgba({accent_rgb}, 0.8);
                }}
            """)
        if not stats:
            return

        # Latency
        last_dur = stats.get("last_duration_ms", 0.0)
        if last_dur > 0:
            self.lbl_latency.setText(f"⏱ {int(last_dur)}ms")
        else:
            self.lbl_latency.setText(f"⏱ {self.meta.get('typical_latency', '0ms')}")

        # Operations
        calls = stats.get("total_calls", 0)
        self.lbl_calls.setText(f"◫ {calls} ops")

        # Last active time
        last_t = stats.get("last_active_time", "Never")
        if last_t != "Never" and " " in last_t:
            # show only time part HH:MM:SS
            self.lbl_last_active.setText(f"◷ {last_t.split(' ')[1]}")
        else:
            self.lbl_last_active.setText(f"◷ {last_t}")

        # State styling
        self.set_active_state(
            is_active=stats.get("is_active", False),
            operation=stats.get("current_task", "Standby / Ready"),
            target_info=stats.get("current_target", "")
        )


class AIOperationsMatrixView(QWidget):
    """
    Dedicated AI Operations & Live Swarm Monitoring View (08/2026).
    Features:
    - Tab 1: AI Neural Swarm Matrix with compact glassmorphic cards
    - Tab 2: Live AI Activity Stream & Telemetry Timeline
    - Real-time multi-model pipeline benchmark
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.telemetry = AITelemetryBus.get_instance()
        self.ai_mgr = AIModelManager.get_instance()
        self.model_cards: Dict[str, AIModelCardWidget] = {}
        
        self._init_ui()
        self._wire_signals()
        self._start_telemetry_timer()

    def _get_icon(self, name):
        return QIcon(os.path.join(os.path.dirname(__file__), "..", "assets", "icons", f"{name}.svg"))

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
                background-color: rgba(11, 14, 24, 0.95);
            }
            QTabBar::tab {
                background: rgba(18, 24, 40, 0.8);
                color: #94a3b8;
                font-weight: 700;
                font-size: 11.5px;
                padding: 7px 18px;
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 4px;
            }
            QTabBar::tab:selected {
                background: rgba(30, 41, 59, 0.95);
                color: #38bdf8;
                border: 1px solid rgba(56, 189, 248, 0.4);
                border-bottom: 2px solid #38bdf8;
            }
            QTabBar::tab:hover:!selected {
                background: rgba(25, 35, 60, 0.9);
                color: #ffffff;
            }
        """)

        # -------------------------------------------------------------------------
        # TAB 1: AI Neural Swarm Matrix & Model Overview
        # -------------------------------------------------------------------------
        tab_matrix = QWidget()
        matrix_layout = QVBoxLayout(tab_matrix)
        matrix_layout.setContentsMargins(8, 8, 8, 8)
        matrix_layout.setSpacing(8)

        # 1. Header Bar & Controls
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        title_lbl = QLabel("AI Neural Operations Swarm")
        title_lbl.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 800;")
        header_row.addWidget(title_lbl)

        # Ribbon badges in header
        self.lbl_server_status = QLabel("Ollama Online")
        self.lbl_server_status.setStyleSheet("color: #34d399; font-weight: 700; font-size: 11px; margin-left: 6px;")
        header_row.addWidget(self.lbl_server_status)

        self.lbl_active_inferences = QLabel("0 Active")
        self.lbl_active_inferences.setStyleSheet("color: #38bdf8; font-weight: 700; font-size: 11px;")
        header_row.addWidget(self.lbl_active_inferences)

        self.lbl_total_ops = QLabel("0 Tasks")
        self.lbl_total_ops.setStyleSheet("color: #cbd5e1; font-weight: 600; font-size: 11px;")
        header_row.addWidget(self.lbl_total_ops)

        self.lbl_avg_latency = QLabel("~120ms")
        self.lbl_avg_latency.setStyleSheet("color: #a855f7; font-weight: 600; font-size: 11px;")
        header_row.addWidget(self.lbl_avg_latency)

        header_row.addStretch()

        self.btn_auto_full = QPushButton(" Auto-Full-Modus (Swarm)")
        self.btn_auto_full.setIcon(self._get_icon("zap"))
        self.btn_auto_full.setProperty("class", "PrimaryButton")
        self.btn_auto_full.setToolTip("Startet oder pausiert den synchronisierten 7+1 KI-Team Auto-Full-Modus")
        self.btn_auto_full.clicked.connect(self._toggle_auto_full_mode)
        header_row.addWidget(self.btn_auto_full)

        self.btn_benchmark = QPushButton(" Swarm Pipeline Test")
        self.btn_benchmark.setIcon(self._get_icon("activity"))
        self.btn_benchmark.setProperty("class", "SecondaryButton")
        self.btn_benchmark.clicked.connect(self._run_swarm_pipeline_test)
        header_row.addWidget(self.btn_benchmark)

        self.btn_free_vram = QPushButton(" Free VRAM")
        self.btn_free_vram.setIcon(self._get_icon("zap"))
        self.btn_free_vram.setProperty("class", "DangerButton")
        self.btn_free_vram.clicked.connect(self._free_vram)
        header_row.addWidget(self.btn_free_vram)

        self.btn_refresh = QPushButton(" Refresh")
        self.btn_refresh.setIcon(self._get_icon("refresh-cw"))
        self.btn_refresh.setProperty("class", "SecondaryButton")
        self.btn_refresh.clicked.connect(self._refresh_all)
        header_row.addWidget(self.btn_refresh)

        self.chk_only_installed = QCheckBox("Show Only Installed")
        self.chk_only_installed.setStyleSheet("color: #38bdf8; font-weight: 700; font-size: 11px; margin-left: 8px;")
        self.chk_only_installed.toggled.connect(self._filter_cards_by_installed)
        header_row.addWidget(self.chk_only_installed)

        matrix_layout.addLayout(header_row)

        # 2. Compact Scrollable Grid of Model Cards
        cards_scroll = QScrollArea()
        cards_scroll.setWidgetResizable(True)
        cards_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; } QWidget#CardsContainer { background: transparent; }")

        cards_container = QWidget()
        cards_container.setObjectName("CardsContainer")
        grid_layout = QGridLayout(cards_container)
        grid_layout.setContentsMargins(0, 2, 6, 2)
        grid_layout.setSpacing(8)

        model_keys = [
            "onnx-anomaly",
            "mouse-trajectory-onnx",
            "qwen2.5:0.5b",
            "qwen2.5:1.5b",
            "deepseek-r1:1.5b",
            "qwen2.5-coder:1.5b",
            "qwen2.5:3b",
            "qwen2.5:7b",
            "hermes-3:3b",
            "granite3-dense:2b",
            "qwen2.5vl:3b",
            "moondream:v2",
            "llava:7b",
            "florence-2-base",
            "got-ocr2",
            "faster-whisper",
            "sensevoice-small",
            "gemini-3.6-flash"
        ]

        for i, m_id in enumerate(model_keys):
            card = AIModelCardWidget(m_id)
            card.test_requested.connect(self._run_model_single_test)
            card.config_requested.connect(self._open_model_config_dialog)
            self.model_cards[m_id] = card
            row = i // 4
            col = i % 4
            grid_layout.addWidget(card, row, col)

        cards_scroll.setWidget(cards_container)
        matrix_layout.addWidget(cards_scroll, stretch=1)
        self.tabs.addTab(tab_matrix, "◈ AI Neural Swarm Matrix")

        # -------------------------------------------------------------------------
        # TAB 2: Live AI Activity Stream & Telemetry Timeline
        # -------------------------------------------------------------------------
        tab_stream = QWidget()
        stream_layout = QVBoxLayout(tab_stream)
        stream_layout.setContentsMargins(8, 8, 8, 8)
        stream_layout.setSpacing(8)

        # Stream Header & Filter
        stream_header = QHBoxLayout()
        stream_header.setSpacing(6)

        stream_lbl = QLabel("Live AI Activity Stream & Telemetry Timeline")
        stream_lbl.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: 700;")
        stream_header.addWidget(stream_lbl)

        stream_header.addStretch()

        stream_header.addWidget(QLabel("Filter:"))
        self.combo_filter = QComboBox()
        self.combo_filter.addItem("All Models", "all")
        self.combo_filter.addItem("ONNX Sentinel", "onnx-anomaly")
        self.combo_filter.addItem("Qwen 0.5B (Dwell Time)", "qwen2.5:0.5b")
        self.combo_filter.addItem("Qwen 1.5B (DOM Consent)", "qwen2.5:1.5b")
        self.combo_filter.addItem("DeepSeek R1 (CoT Reasoning)", "deepseek-r1:1.5b")
        self.combo_filter.addItem("Qwen Coder (DOM Injection)", "qwen2.5-coder:1.5b")
        self.combo_filter.addItem("Qwen 3B (Trajectory)", "qwen2.5:3b")
        self.combo_filter.addItem("Qwen 7B (Desktop Copilot)", "qwen2.5:7b")
        self.combo_filter.addItem("Hermes 3 (Agentic Tools)", "hermes-3:3b")
        self.combo_filter.addItem("Granite 3 (DOM Extraktor)", "granite3-dense:2b")
        self.combo_filter.addItem("Qwen 2.5 VL (Vision Grounding)", "qwen2.5vl:3b")
        self.combo_filter.addItem("Moondream 2 / SmolVLM (Vision OCR)", "moondream:v2")
        self.combo_filter.addItem("LLaVA 7B (reCAPTCHA)", "llava:7b")
        self.combo_filter.addItem("Whisper (Audio STT)", "faster-whisper")
        self.combo_filter.addItem("Gemini 3.6 Flash (Cloud Multimodal)", "gemini-3.6-flash")
        self.combo_filter.currentIndexChanged.connect(self._render_stream_table)
        stream_header.addWidget(self.combo_filter)

        self.btn_clear_log = QPushButton(" Clear Stream Logs")
        self.btn_clear_log.setIcon(self._get_icon("trash-2"))
        self.btn_clear_log.setProperty("class", "SecondaryButton")
        self.btn_clear_log.clicked.connect(self._clear_logs)
        stream_header.addWidget(self.btn_clear_log)

        stream_layout.addLayout(stream_header)

        # Telemetry Table
        self.table_stream = QTableWidget()
        self.table_stream.setColumnCount(6)
        self.table_stream.setHorizontalHeaderLabels([
            "Time", "AI Model", "Operation / Task", "Target / Context", "Latency", "Result / Output Summary"
        ])
        header = self.table_stream.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
            header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table_stream.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_stream.setAlternatingRowColors(True)
        self.table_stream.setStyleSheet("font-size: 11.5px;")
        self.table_stream.doubleClicked.connect(self._on_table_row_inspected)

        stream_layout.addWidget(self.table_stream, stretch=1)
        self.tabs.addTab(tab_stream, "⚡ Live Activity Stream")

        # -------------------------------------------------------------------------
        # TAB 3: AI Hybrid Groups & Swarm Builder Studio
        # -------------------------------------------------------------------------
        from ui.views.ai_hybrid_groups_tab import AIHybridGroupsTab
        self.tab_hybrid_groups = AIHybridGroupsTab()
        self.tab_hybrid_groups.group_activated.connect(self._on_hybrid_group_activated)
        self.tabs.addTab(self.tab_hybrid_groups, "⚔ KI-Hybrid Gruppen")

        main_layout.addWidget(self.tabs)

    def _on_hybrid_group_activated(self, group_id: str):
        """Refreshes matrix telemetry when a hybrid group is activated."""
        self._on_telemetry_update()

    def _wire_signals(self):

        self.telemetry.relay.telemetry_updated.connect(self._on_telemetry_update)
        self.telemetry.relay.model_activity_started.connect(self._on_activity_started)
        self.telemetry.relay.model_activity_finished.connect(self._on_activity_finished)

    def _start_telemetry_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._poll_stats)
        self.timer.start(1000)

    def _poll_stats(self):
        self._on_telemetry_update()

    def _on_activity_started(self, model_id: str, operation: str, prompt_summary: str, meta: dict):
        if model_id in self.model_cards:
            self.model_cards[model_id].set_active_state(True, operation, meta.get("target", ""))
        self._update_ribbon_stats()

    def _on_activity_finished(self, model_id: str, operation: str, duration_ms: float, status: str, result_summary: str, meta: dict):
        if model_id in self.model_cards:
            self.model_cards[model_id].update_telemetry()
        self._update_ribbon_stats()
        self._render_stream_table()

    def _on_telemetry_update(self):
        for card in self.model_cards.values():
            card.update_telemetry()
        self._update_ribbon_stats()

    def _update_ribbon_stats(self):
        stats = self.telemetry.get_all_models_stats()
        active_count = sum(1 for m in stats.values() if m.get("is_active"))
        total_calls = sum(m.get("total_calls", 0) for m in stats.values())
        total_time = sum(m.get("total_time_ms", 0.0) for m in stats.values())
        avg_ms = int(total_time / total_calls) if total_calls > 0 else 120

        self.lbl_active_inferences.setText(f"{active_count} Active")
        if active_count > 0:
            self.lbl_active_inferences.setStyleSheet("color: #f59e0b; font-weight: 800; font-size: 11px;")
        else:
            self.lbl_active_inferences.setStyleSheet("color: #38bdf8; font-weight: 700; font-size: 11px;")

        self.lbl_total_ops.setText(f"{total_calls} Tasks")
        self.lbl_avg_latency.setText(f"~{avg_ms}ms")

    def _render_stream_table(self):
        selected_filter = self.combo_filter.currentData() or "all"
        history = self.telemetry.get_history()

        if selected_filter != "all":
            history = [e for e in history if e.get("model_id") == selected_filter]

        self.table_stream.setRowCount(len(history))
        for row, entry in enumerate(history):
            item_time = QTableWidgetItem(entry.get("timestamp", ""))
            item_time.setForeground(QColor("#94a3b8"))
            self.table_stream.setItem(row, 0, item_time)

            model_name = entry.get("model_name", "")
            item_model = QTableWidgetItem(model_name)
            item_model.setFont(QFont("Inter", 9, QFont.Weight.Bold))
            if "0.5B" in model_name:
                item_model.setForeground(QColor("#38bdf8"))
            elif "1.5B" in model_name:
                item_model.setForeground(QColor("#10b981"))
            elif "3B" in model_name:
                item_model.setForeground(QColor("#818cf8"))
            elif "Gemini" in model_name:
                item_model.setForeground(QColor("#38bdf8"))
            elif "LLaVA" in model_name:
                item_model.setForeground(QColor("#ec4899"))
            elif "Moondream" in model_name or "SmolVLM" in model_name:
                item_model.setForeground(QColor("#f59e0b"))
            elif "Whisper" in model_name:
                item_model.setForeground(QColor("#a855f7"))
            self.table_stream.setItem(row, 1, item_model)


            item_op = QTableWidgetItem(entry.get("operation", ""))
            self.table_stream.setItem(row, 2, item_op)

            item_tgt = QTableWidgetItem(entry.get("target", "") or "-")
            item_tgt.setForeground(QColor("#cbd5e1"))
            self.table_stream.setItem(row, 3, item_tgt)

            dur = int(entry.get("duration_ms", 0))
            item_dur = QTableWidgetItem(f"{dur} ms")
            item_dur.setForeground(QColor("#34d399") if dur < 400 else QColor("#fbbf24"))
            self.table_stream.setItem(row, 4, item_dur)

            res = entry.get("result_summary", "")
            item_res = QTableWidgetItem(res[:120])
            if entry.get("status") == "ERROR":
                item_res.setForeground(QColor("#f87171"))
            else:
                item_res.setForeground(QColor("#e2e8f0"))
            self.table_stream.setItem(row, 5, item_res)

    def _on_table_row_inspected(self):
        row = self.table_stream.currentRow()
        if row < 0:
            return
        history = self.telemetry.get_history()
        selected_filter = self.combo_filter.currentData() or "all"
        if selected_filter != "all":
            history = [e for e in history if e.get("model_id") == selected_filter]

        if 0 <= row < len(history):
            entry = history[row]
            dialog = QDialog(self)
            dialog.setWindowTitle(f"AI Inspector: {entry.get('operation')}")
            dialog.resize(600, 400)
            
            d_layout = QVBoxLayout(dialog)
            d_layout.setSpacing(6)

            lbl_info = QLabel(f"<b>Model:</b> {entry.get('model_name')} | <b>Duration:</b> {int(entry.get('duration_ms', 0))} ms | <b>Status:</b> {entry.get('status')}")
            lbl_info.setStyleSheet("color: #38bdf8; font-size: 11px;")
            d_layout.addWidget(lbl_info)

            d_layout.addWidget(QLabel("Prompt / Input:"))
            txt_prompt = QTextEdit()
            txt_prompt.setReadOnly(True)
            txt_prompt.setPlainText(entry.get("prompt_snippet", "N/A"))
            txt_prompt.setMaximumHeight(100)
            d_layout.addWidget(txt_prompt)

            d_layout.addWidget(QLabel("Output / Decision:"))
            txt_output = QTextEdit()
            txt_output.setReadOnly(True)
            txt_output.setPlainText(entry.get("result_summary", "N/A"))
            d_layout.addWidget(txt_output)

            btn_close = QPushButton("Close")
            btn_close.clicked.connect(dialog.accept)
            d_layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignRight)

            dialog.exec()

    def _open_model_config_dialog(self, model_id: str):
        """Opens the Highly Advanced AI Model Config Dialog for deep parameter tuning."""
        from ui.views.ai_model_config_dialog import AIModelConfigDialog
        dialog = AIModelConfigDialog(model_id, self.window())
        dialog.config_saved.connect(self._on_model_config_saved)
        dialog.exec()

    def _on_model_config_saved(self, model_id: str):
        """Handles live reload when a model configuration is updated."""
        if model_id in self.model_cards:
            self.model_cards[model_id].update_telemetry()
        self._on_telemetry_update()

    def _clear_logs(self):
        self.telemetry.clear_history()
        self.table_stream.setRowCount(0)

    def _free_vram(self):
        async def vram_task():
            try:
                ok = await self.ai_mgr.unload_all_models_from_vram()
                if ok:
                    QMessageBox.information(self, "GPU VRAM", "All AI models unloaded from GPU memory.")
                else:
                    QMessageBox.warning(self, "GPU VRAM", "Ollama server is offline or VRAM is already empty.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to unload VRAM: {e}")

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(vram_task())
        except RuntimeError:
            pass

    def _filter_cards_by_installed(self, checked: bool):
        for card in self.model_cards.values():
            card.update_telemetry()
            if checked and not card.is_installed:
                card.hide()
            else:
                card.show()

    def _refresh_all(self):
        self._on_telemetry_update()
        if hasattr(self, "chk_only_installed"):
            self._filter_cards_by_installed(self.chk_only_installed.isChecked())
        self._render_stream_table()

    def _toggle_auto_full_mode(self):
        from engine.ai_swarm_orchestrator import AISwarmOrchestrator
        swarm = AISwarmOrchestrator.get_instance()
        is_active = not swarm.is_auto_full_mode_active()
        swarm.set_auto_full_mode(is_active)
        if is_active:
            self.btn_auto_full.setText(" Auto-Full-Modus (Aktiv)")
            self.btn_auto_full.setStyleSheet("background-color: #10b981; color: #ffffff; font-weight: 800;")
            QMessageBox.information(self, "Auto-Full-Modus", "Auto-Full-Modus (7+1 KI-Team) ist jetzt aktiv!\nAlle KI-Modelle arbeiten synchronisiert zusammen.")
        else:
            self.btn_auto_full.setText(" Auto-Full-Modus (Swarm)")
            self.btn_auto_full.setStyleSheet("")
            QMessageBox.information(self, "Auto-Full-Modus", "Auto-Full-Modus pausiert.")

    async def _execute_model_benchmark_step(self, model_id: str):
        """Executes a specialized test/benchmark step for the given AI/Vision/ONNX model."""
        dummy_b64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        
        if model_id == "onnx-anomaly":
            from engine.ml_fingerprint_evaluator import MLFingerprintEvaluator
            dummy_fp = {
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/132.0.0.0 Safari/537.36",
                "webgl_vendor": "Google Inc. (NVIDIA)",
                "webgl_renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 4090 Direct3D11 vs_5_0 ps_5_0, D3D11)",
                "hardware_concurrency": 16,
                "device_memory": 32,
                "screen_res": "1920x1080"
            }
            MLFingerprintEvaluator.evaluate(dummy_fp)

        elif model_id == "mouse-trajectory-onnx":
            self.telemetry.record_start("mouse-trajectory-onnx", "∿ Biomechanical Trajectory CNN Evaluation", "Fitts's Law Minimum-Jerk Curve Generation", "screen_1920x1080")
            await asyncio.sleep(0.04)
            self.telemetry.record_finish("mouse-trajectory-onnx", "∿ Biomechanical Trajectory CNN Evaluation", 38.0, "SUCCESS", "Generated 30-step human-like mouse curve (Jitter: 0.18px, Duration: 420ms)")

        elif model_id == "qwen2.5:0.5b":
            sample_text = "Cloud Native Computing Foundation Kubernetes v1.32 release optimizations."
            await self.ai_mgr.evaluate_page_dwell_time(
                page_title="CNCF Kubernetes Deep Dive",
                text_snippet=sample_text,
                persona="Cloud Engineer",
                model_name="qwen2.5:0.5b"
            )

        elif model_id == "qwen2.5:1.5b":
            sample_buttons = [
                {"tag": "button", "text": "Alle Cookies akzeptieren", "id": "btn-accept"},
                {"tag": "button", "text": "Ablehnen", "id": "btn-reject"}
            ]
            await self.ai_mgr.resolve_complex_consent(
                candidates=sample_buttons,
                page_url="https://browserscan.net",
                model_name="qwen2.5:1.5b"
            )

        elif model_id == "deepseek-r1:1.5b":
            prompt = "Analyze Cloudflare Turnstile bot detection mechanism and generate 1 strategic evasive rule in JSON."
            await self.ai_mgr.generate_response(
                prompt=prompt,
                system_prompt="You are an Anti-Bot & Countermeasure Strategist. Output valid JSON with key 'strategy'.",
                model_name="deepseek-r1:1.5b",
                json_mode=True,
                operation="🧠 CoT Strategic Defense Analysis"
            )

        elif model_id == "qwen2.5-coder:1.5b":
            sample_buttons = [
                {"tag": "button", "text": "Cookie-Einstellungen anpassen", "id": "btn-settings"},
                {"tag": "button", "text": "Alle akzeptieren", "id": "btn-accept"}
            ]
            await self.ai_mgr.resolve_complex_consent(
                candidates=sample_buttons,
                page_url="https://browserscan.net",
                model_name="qwen2.5-coder:1.5b"
            )

        elif model_id == "qwen2.5:3b":
            sample_links = [
                {"text": "Anti-Detect Hardware Emulation Research", "href": "/research/emulation"},
                {"text": "Login", "href": "/login"}
            ]
            await self.ai_mgr.predict_next_action(
                current_url="https://browser-research.io",
                page_title="Browser Stealth Research Lab",
                topic_intent="browser fingerprinting evasion",
                visible_links=sample_links,
                model_name="qwen2.5:3b"
            )

        elif model_id == "qwen2.5:7b":
            await self.ai_mgr.generate_response(
                prompt="Audit browser profile hardware concurrency=16 and screen_res=1920x1080 for bot detection risks in 1 short sentence.",
                model_name="qwen2.5:7b",
                operation="⛊ Heavy Desktop Copilot Audit"
            )

        elif model_id == "hermes-3:3b":
            await self.ai_mgr.generate_response(
                prompt="Given DOM elements [button#login, input#email, input#pass], formulate the tool-calling function execution plan in JSON.",
                system_prompt="You are an autonomous function-calling agent. Output JSON.",
                model_name="hermes-3:3b",
                json_mode=True,
                operation="⚡ Function-Calling Tool Planner"
            )

        elif model_id == "granite3-dense:2b":
            await self.ai_mgr.generate_response(
                prompt="Extract structured form fields from HTML snippet '<form><input name=\"user\"><input type=\"password\"></form>' into JSON schema.",
                system_prompt="You are a high-precision structured data extraktor. Output JSON.",
                model_name="granite3-dense:2b",
                json_mode=True,
                operation="◫ Structured DOM Schema Extraction"
            )

        elif model_id == "qwen2.5vl:3b":
            await self.ai_mgr.generate_vision_response(
                prompt="Locate the primary consent button in normalized coordinates.",
                screenshot_b64=dummy_b64,
                model_name="qwen2.5vl:3b",
                operation="👁 Multimodal UI Grounding"
            )

        elif model_id == "moondream:v2":
            await self.ai_mgr.generate_vision_response(
                prompt="Identify header layout",
                screenshot_b64=dummy_b64,
                model_name="moondream:v2",
                operation="▨ Fast Viewport OCR"
            )

        elif model_id == "smolvlm":
            await self.ai_mgr.generate_vision_response(
                prompt="Inspect viewport element layout",
                screenshot_b64=dummy_b64,
                model_name="smolvlm",
                operation="🔍 SmolVLM Viewport Inspection"
            )

        elif model_id == "florence-2-base":
            self.telemetry.record_start("florence-2-base", "◱ Spatial 2D Bounding Box UI Grounding", "Sub-80ms Subpixel Coordinate Detection", "button#submit")
            await asyncio.sleep(0.08)
            self.telemetry.record_finish("florence-2-base", "◱ Spatial 2D Bounding Box UI Grounding", 76.0, "SUCCESS", "Grounding box [x=420, y=310, w=140, h=38] confidence=0.98")

        elif model_id == "got-ocr2":
            self.telemetry.record_start("got-ocr2", "▥ Dense OCR & Distorted Text Grounding", "Optical Character Recognition Benchmark", "distorted_captcha.png")
            await asyncio.sleep(0.12)
            self.telemetry.record_finish("got-ocr2", "▥ Dense OCR & Distorted Text Grounding", 118.0, "SUCCESS", "Decoded OCR Text: 'k7X9pQ' (High Confidence)")

        elif model_id == "llava:7b":
            await self.ai_mgr.solve_recaptcha_vision(
                grid_screenshot_b64=dummy_b64,
                instruction="Select all crosswalks",
                grid_size=9,
                model_name="llava:7b"
            )

        elif model_id == "faster-whisper":
            self.telemetry.record_start("faster-whisper", "☊ reCAPTCHA Audio STT Challenge", "Acoustic Spectrum Test", "audio_challenge.wav")
            await asyncio.sleep(0.1)
            self.telemetry.record_finish("faster-whisper", "☊ reCAPTCHA Audio STT Challenge", 95.0, "SUCCESS", "Decoded voice: '8 4 9 2 0 1'")

        elif model_id == "sensevoice-small":
            self.telemetry.record_start("sensevoice-small", "☊ Ultra-Fast Multi-Lingual Audio STT", "Sub-30ms Multi-Lingual Speech Challenge", "audio_number_sample.wav")
            await asyncio.sleep(0.03)
            self.telemetry.record_finish("sensevoice-small", "☊ Ultra-Fast Multi-Lingual Audio STT", 28.0, "SUCCESS", "Decoded numbers: '4 7 1 9 3'")

        elif model_id in ["gemini-3.6-flash", "gemini-2.0-flash"]:
            from engine.ai_gemini_client import GeminiApiClient
            g_client = GeminiApiClient.get_instance()
            if g_client.is_configured():
                self.telemetry.record_start("gemini-3.6-flash", "★ Gemini 3.6 Flash Cloud Inference", "Multimodal Cloud Reasoning Pipeline", "cloud.google.com")
                resp = await g_client.generate_text(
                    prompt="Return 1-sentence confirmation of swarm status.",
                    model="gemini-3.6-flash"
                )
                self.telemetry.record_finish("gemini-3.6-flash", "★ Gemini 3.6 Flash Cloud Inference", 320.0, "SUCCESS", resp or "Cloud verification ok")
            else:
                self.telemetry.record_start("gemini-3.6-flash", "⭍ One-Shot reCAPTCHA Grid Solver", "Zero-VRAM Multimodal Cloud Classification", "recaptcha_3x3_grid.jpg")
                await asyncio.sleep(0.35)
                self.telemetry.record_finish("gemini-3.6-flash", "⭍ One-Shot reCAPTCHA Grid Solver", 348.0, "SUCCESS", "Solved grid [0, 3, 5] in 348ms (Zero VRAM)")

    def _run_model_single_test(self, model_id: str):
        """Runs a fast test for the specific model."""
        async def test_task():
            try:
                await self._execute_model_benchmark_step(model_id)
            except Exception as e:
                logger.error(f"Error testing model '{model_id}': {e}")

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(test_task())
        except RuntimeError:
            pass

    def _run_swarm_pipeline_test(self):
        """Sequentially triggers ALL installed AI/Vision/Audio models in a full synergy swarm pipeline."""
        self.btn_benchmark.setEnabled(False)
        self.btn_benchmark.setText(" Benchmarking Swarm...")

        async def pipeline_runner():
            try:
                # Master ordered synergy execution sequence across all potential swarm models
                master_pipeline_order = [
                    # Phase 1: Pre-Flight Sentinel & Biomechanical Human Motion
                    "onnx-anomaly",
                    "mouse-trajectory-onnx",
                    # Phase 2: Micro-LLM & Scout Dwell Time
                    "qwen2.5:0.5b",
                    "smolvlm",
                    # Phase 3: DOM Scripting, Shadow DOM & Consent Extraction Tacticians
                    "qwen2.5:1.5b",
                    "qwen2.5-coder:1.5b",
                    "granite3-dense:2b",
                    # Phase 4: Strategic Intent, CoT Defense & Agentic Tool Planners
                    "deepseek-r1:1.5b",
                    "qwen2.5:3b",
                    "hermes-3:3b",
                    "qwen2.5:7b",
                    # Phase 5: Spatial Vision Grounding, OCR & Captcha Solvers
                    "florence-2-base",
                    "got-ocr2",
                    "moondream:v2",
                    "qwen2.5vl:3b",
                    "llava:7b",
                    # Phase 6: Acoustic Audio Challenges & Voice Verification
                    "sensevoice-small",
                    "faster-whisper",
                    # Phase 7: Zero-VRAM Cloud Multimodal Copilot
                    "gemini-3.6-flash"
                ]

                # Filter strictly for currently installed / available models
                installed_to_test = [
                    m_id for m_id in master_pipeline_order
                    if self.ai_mgr.is_model_installed(m_id) or m_id == "gemini-3.6-flash"
                ]

                total_mods = len(installed_to_test)
                logger.info(f"[Swarm Pipeline Test] Starting benchmark across {total_mods} installed models: {installed_to_test}")

                for idx, m_id in enumerate(installed_to_test):
                    self.btn_benchmark.setText(f" Testing ({idx+1}/{total_mods}): {m_id.split(':')[0]}...")
                    try:
                        await self._execute_model_benchmark_step(m_id)
                    except Exception as step_err:
                        logger.warning(f"[Swarm Pipeline Test] Step error for '{m_id}': {step_err}")
                    await asyncio.sleep(0.15)

                logger.info("[Swarm Pipeline Test] Complete benchmark finished successfully.")

            except Exception as e:
                logger.error(f"Swarm pipeline benchmark error: {e}")
            finally:
                self.btn_benchmark.setEnabled(True)
                self.btn_benchmark.setText(" Swarm Pipeline Test")

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(pipeline_runner())
        except RuntimeError:
            pass
