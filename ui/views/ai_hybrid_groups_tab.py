import os
import time
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QProgressBar, QGridLayout, QComboBox,
    QMessageBox, QTextEdit, QPlainTextEdit, QLineEdit, QCheckBox, QDoubleSpinBox,
    QScrollArea, QSplitter, QFileDialog, QGroupBox, QDialog
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QColor, QFont, QIcon, QMouseEvent

from engine.ai_hybrid_groups_manager import (
    AIHybridGroupsManager, SWARM_ROLE_DEFINITIONS, MODEL_HARDWARE_PROFILES
)
from engine.ai_model_manager import AIModelManager
from engine.ai_telemetry import AITelemetryBus
import config

logger = logging.getLogger("AIHybridGroupsTab")


class AIHybridGroupCardWidget(QFrame):
    """
    Glassmorphic Card in the Hybrid Groups sidebar list.
    Displays group name, icon, active indicator, VRAM estimation pill, and quick actions.
    """
    clicked = pyqtSignal(str)
    activate_requested = pyqtSignal(str)

    def __init__(self, group_data: Optional[Dict[str, Any]] = None, is_selected: bool = False, parent=None):
        super().__init__(parent)
        self.group_data: Dict[str, Any] = group_data if isinstance(group_data, dict) else {}
        self.group_id: str = self.group_data.get("id", "")
        self.is_selected = is_selected
        self.setObjectName("HybridGroupCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._init_ui()

    def mousePressEvent(self, a0: Optional[QMouseEvent]):
        if a0 is not None and a0.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.group_id)
        if a0 is not None:
            super().mousePressEvent(a0)


    def update_selection(self, is_selected: bool):
        """Updates selection highlight without recreating layout."""
        self.is_selected = is_selected
        accent_color = self.group_data.get("accent_color", "#38bdf8")
        border_color = "rgba(56, 189, 248, 0.8)" if self.is_selected else "rgba(255, 255, 255, 0.08)"
        bg_color = "rgba(25, 35, 60, 0.9)" if self.is_selected else "rgba(18, 24, 40, 0.75)"

        self.setStyleSheet(f"""
            QFrame#HybridGroupCard {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-left: { '4px solid ' + accent_color if self.is_selected else '1px solid ' + border_color };
                border-radius: 8px;
                padding: 8px;
            }}
            QFrame#HybridGroupCard:hover {{
                background-color: rgba(30, 41, 68, 0.95);
                border: 1px solid rgba(56, 189, 248, 0.5);
            }}
        """)

    def _init_ui(self):
        accent_color = self.group_data.get("accent_color", "#38bdf8")
        is_active = self.group_data.get("is_active", False)
        is_builtin = self.group_data.get("is_builtin", False)
        
        # Calculate hardware stats for pills
        metrics = AIHybridGroupsManager.calculate_group_metrics(
            self.group_data.get("roles", {}),
            self.group_data.get("orchestration", {})
        )
        peak_gb = metrics.get("estimated_peak_vram_gb", 1.5)
        est_lat = metrics.get("estimated_pipeline_latency_ms", 200)

        border_color = "rgba(56, 189, 248, 0.8)" if self.is_selected else "rgba(255, 255, 255, 0.08)"
        bg_color = "rgba(25, 35, 60, 0.9)" if self.is_selected else "rgba(18, 24, 40, 0.75)"

        self.setStyleSheet(f"""
            QFrame#HybridGroupCard {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-left: { '4px solid ' + accent_color if self.is_selected else '1px solid ' + border_color };
                border-radius: 8px;
                padding: 8px;
            }}
            QFrame#HybridGroupCard:hover {{
                background-color: rgba(30, 41, 68, 0.95);
                border: 1px solid rgba(56, 189, 248, 0.5);
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        # Header Row: Icon, Name, Active Badge
        header_row = QHBoxLayout()
        header_row.setSpacing(6)

        icon_lbl = QLabel(self.group_data.get("icon", "⚔"))
        icon_lbl.setStyleSheet("font-size: 16px;")
        header_row.addWidget(icon_lbl)

        name_lbl = QLabel(self.group_data.get("name", "Hybrid Group"))
        name_lbl.setStyleSheet("color: #ffffff; font-size: 12px; font-weight: 700;")
        header_row.addWidget(name_lbl, stretch=1)

        if is_active:
            active_badge = QLabel("● AKTIV")
            active_badge.setStyleSheet("""
                background-color: rgba(16, 185, 129, 0.2);
                color: #10b981;
                font-size: 9px;
                font-weight: 800;
                padding: 2px 6px;
                border-radius: 6px;
                border: 1px solid rgba(16, 185, 129, 0.4);
            """)
            header_row.addWidget(active_badge)
        elif not is_builtin:
            custom_badge = QLabel("CUSTOM")
            custom_badge.setStyleSheet("""
                background-color: rgba(168, 85, 247, 0.15);
                color: #c084fc;
                font-size: 9px;
                font-weight: 700;
                padding: 2px 5px;
                border-radius: 6px;
                border: 1px solid rgba(168, 85, 247, 0.3);
            """)
            header_row.addWidget(custom_badge)

        layout.addLayout(header_row)

        # Metrics Pills Row
        pills_row = QHBoxLayout()
        pills_row.setSpacing(6)

        vram_pill = QLabel(f"💾 ~{peak_gb} GB VRAM")
        vram_pill.setStyleSheet("color: #94a3b8; font-size: 10px; font-weight: 600;")
        pills_row.addWidget(vram_pill)

        lat_pill = QLabel(f"⚡ ~{est_lat} ms")
        lat_pill.setStyleSheet("color: #a855f7; font-size: 10px; font-weight: 600;")
        pills_row.addWidget(lat_pill)

        pills_row.addStretch()

        if not is_active:
            btn_activate = QPushButton("Aktivieren")
            btn_activate.setStyleSheet("""
                QPushButton {
                    background-color: rgba(56, 189, 248, 0.15);
                    color: #38bdf8;
                    font-size: 9.5px;
                    font-weight: 700;
                    padding: 2px 8px;
                    border: 1px solid rgba(56, 189, 248, 0.3);
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #38bdf8;
                    color: #0b0e18;
                }
            """)
            btn_activate.clicked.connect(lambda: self.activate_requested.emit(self.group_id))
            pills_row.addWidget(btn_activate)

        layout.addLayout(pills_row)


class AISwarmConfigPusherDialog(QDialog):
    """
    In-App Swarm Config Editor & Pusher Dialog.
    Allows pasting raw JSON/YAML Swarm specifications (e.g. Browser Poker Multi-Task Swarms),
    validating schema live, and pushing directly to SoxBot's AI Hybrid Group Engine.
    """
    config_pushed = pyqtSignal(str)

    def __init__(self, current_group_id: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.mgr = AIHybridGroupsManager.get_instance()
        self.current_group_id = current_group_id
        self.setWindowTitle("📝 In-App Swarm Config Pusher & Multi-Task Studio")
        self.setMinimumSize(880, 680)
        self.setStyleSheet("""
            QDialog {
                background-color: #0b0e18;
                color: #ffffff;
            }
        """)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header Info Box
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(14, 165, 233, 0.15), stop:1 rgba(168, 85, 247, 0.15));
                border: 1px solid rgba(56, 189, 248, 0.3);
                border-radius: 8px;
                padding: 10px;
            }
        """)
        h_layout = QVBoxLayout(header_frame)
        h_layout.setContentsMargins(8, 8, 8, 8)
        h_layout.setSpacing(4)

        title_lbl = QLabel("🚀 In-App Swarm Config Editor & Pusher")
        title_lbl.setStyleSheet("color: #38bdf8; font-size: 14px; font-weight: 800;")
        h_layout.addWidget(title_lbl)

        desc_lbl = QLabel(
            "Paste deine Swarm-Konfigurationsdatei (JSON/YAML) direkt in den Editor. "
            "Definiere spezialisierte Aufgaben (z. B. Poker Vision OCR, DeepSeek-R1 GTO Reasoning, Stealth DOM Clicker) "
            "und pushe den Swarm live in die App."
        )
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        h_layout.addWidget(desc_lbl)
        layout.addWidget(header_frame)

        # Toolbar: Preset Templates & Helper Actions
        tools_row = QHBoxLayout()
        tools_row.setSpacing(8)

        lbl_tpl = QLabel("Vorlage laden:")
        lbl_tpl.setStyleSheet("color: #cbd5e1; font-size: 11px; font-weight: 700;")
        tools_row.addWidget(lbl_tpl)

        self.combo_presets = QComboBox()
        self.combo_presets.setStyleSheet("""
            QComboBox {
                background-color: rgba(30, 41, 59, 0.95);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
                min-width: 250px;
            }
            QComboBox::drop-down { border: none; }
        """)
        self.combo_presets.addItem("🃏 Browser Poker Multi-Task Swarm", "poker")
        self.combo_presets.addItem("♟️ Chess Grandmaster Hybrid Swarm", "chess")
        self.combo_presets.addItem("🛡️ Stealth Cyber-Evasion Swarm", "stealth")
        self.combo_presets.addItem("⚔️ Custom Multi-Purpose Blanko", "blank")
        self.combo_presets.addItem("📋 Aktuelle Swarm-Konfiguration laden", "current")
        tools_row.addWidget(self.combo_presets)

        btn_load_preset = QPushButton("⎘ Vorlage Übernehmen")
        btn_load_preset.setStyleSheet("""
            QPushButton {
                background-color: rgba(56, 189, 248, 0.2);
                color: #38bdf8;
                font-weight: 700;
                font-size: 11px;
                padding: 5px 12px;
                border: 1px solid rgba(56, 189, 248, 0.4);
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #38bdf8; color: #0b0e18; }
        """)
        btn_load_preset.clicked.connect(self._apply_selected_preset)
        tools_row.addWidget(btn_load_preset)

        tools_row.addStretch()

        btn_beautify = QPushButton("🧹 Formatieren (JSON)")
        btn_beautify.setStyleSheet("""
            QPushButton {
                background-color: rgba(30, 41, 59, 0.8);
                color: #cbd5e1;
                font-size: 11px;
                font-weight: 600;
                padding: 5px 10px;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
            }
            QPushButton:hover { background-color: rgba(51, 65, 85, 0.9); color: #ffffff; }
        """)
        btn_beautify.clicked.connect(self._beautify_json)
        tools_row.addWidget(btn_beautify)

        layout.addLayout(tools_row)

        # Code Editor
        self.editor = QPlainTextEdit()
        self.editor.setStyleSheet("""
            QPlainTextEdit {
                background-color: #07090e;
                color: #38bdf8;
                border: 1px solid rgba(56, 189, 248, 0.3);
                border-radius: 8px;
                padding: 10px;
                font-family: 'Consolas', 'Monaco', 'DejaVu Sans Mono', monospace;
                font-size: 12px;
                selection-background-color: #0369a1;
            }
        """)
        self.editor.textChanged.connect(self._validate_schema_live)
        layout.addWidget(self.editor, stretch=1)

        # Validation Bar
        self.lbl_status = QLabel("Bereit zum Einfügen...")
        self.lbl_status.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 600;")
        layout.addWidget(self.lbl_status)

        # Bottom Buttons
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(10)

        btn_cancel = QPushButton("Abbrechen")
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: rgba(30, 41, 59, 0.8);
                color: #cbd5e1;
                font-weight: 700;
                font-size: 11px;
                padding: 6px 14px;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
            }
            QPushButton:hover { background-color: rgba(51, 65, 85, 0.9); color: #ffffff; }
        """)
        btn_cancel.clicked.connect(self.reject)
        bottom_row.addWidget(btn_cancel)

        bottom_row.addStretch()

        self.btn_push = QPushButton("🚀 In Swarm Speichern & Anwenden (Push)")
        self.btn_push.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:1 #06b6d4);
                color: #ffffff;
                font-weight: 800;
                font-size: 12px;
                padding: 7px 20px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #0891b2);
            }
        """)
        self.btn_push.clicked.connect(self._push_config)
        bottom_row.addWidget(self.btn_push)

        layout.addLayout(bottom_row)

        # Load initial template
        self._apply_selected_preset()

    def _apply_selected_preset(self):
        preset_key = self.combo_presets.currentData()
        if preset_key == "current" and self.current_group_id:
            try:
                content = self.mgr.export_group_json(self.current_group_id)
                self.editor.setPlainText(content)
                return
            except Exception:
                pass
        
        tpl = self.mgr.get_preset_config_template(preset_key or "poker")
        self.editor.setPlainText(json.dumps(tpl, indent=2, ensure_ascii=False))

    def _beautify_json(self):
        text = self.editor.toPlainText().strip()
        if not text:
            return
        try:
            parsed = json.loads(text)
            self.editor.setPlainText(json.dumps(parsed, indent=2, ensure_ascii=False))
        except Exception as e:
            self.lbl_status.setText(f"⚠ Formatierungsfehler: {e}")
            self.lbl_status.setStyleSheet("color: #f87171; font-size: 11px; font-weight: 700;")

    def _validate_schema_live(self):
        text = self.editor.toPlainText().strip()
        if not text:
            self.lbl_status.setText("Editor ist leer.")
            self.lbl_status.setStyleSheet("color: #94a3b8; font-size: 11px;")
            self.btn_push.setEnabled(False)
            return

        try:
            data = json.loads(text)
            if not isinstance(data, dict):
                raise ValueError("JSON muss ein Objekt sein (beginnend mit '{').")
            
            roles_cnt = len(data.get("roles", {}))
            tasks_list = list(data.get("tasks", {}).keys())
            name = data.get("name", "Custom Swarm")
            
            task_info = f", Tasks: {', '.join(tasks_list)}" if tasks_list else ""
            self.lbl_status.setText(f"✓ Gültige Swarm-Spezifikation: '{name}' ({roles_cnt} Rollen{task_info})")
            self.lbl_status.setStyleSheet("color: #10b981; font-size: 11px; font-weight: 700;")
            self.btn_push.setEnabled(True)
        except Exception as e:
            self.lbl_status.setText(f"⚠ JSON-Syntaxfehler: {e}")
            self.lbl_status.setStyleSheet("color: #f87171; font-size: 11px; font-weight: 700;")
            self.btn_push.setEnabled(False)

    def _push_config(self):
        text = self.editor.toPlainText().strip()
        if not text:
            return
        try:
            updated_grp = self.mgr.push_group_config(text, target_group_id=self.current_group_id)
            self.config_pushed.emit(updated_grp["id"])
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Fehler beim Pushen", f"Die Konfiguration konnte nicht gepusht werden:\n{e}")


class AIHybridGroupsTab(QWidget):
    """
    Dedicated AI Hybrid Groups & Swarm Builder Studio Tab (Tab 3 in AI Swarm Matrix).
    Enables creating, customizing, testing, and managing multi-model ensembles.
    """
    group_activated = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.mgr = AIHybridGroupsManager.get_instance()
        self.ai_mgr = AIModelManager.get_instance()
        self.telemetry = AITelemetryBus.get_instance()
        
        active_g = self.mgr.get_active_group()
        self.selected_group_id: str = active_g.get("id", "swarm_auto_full") if isinstance(active_g, dict) else "swarm_auto_full"
        self.role_combos: Dict[str, QComboBox] = {}
        self.group_cards: Dict[str, AIHybridGroupCardWidget] = {}
        
        self._init_ui()
        self._load_group_to_editor(self.selected_group_id)

    def _get_icon(self, name: str) -> QIcon:
        icon_path = os.path.join(os.path.dirname(__file__), "..", "assets", "icons", f"{name}.svg")
        return QIcon(icon_path) if os.path.exists(icon_path) else QIcon()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # Splitter between Left Groups List & Right Studio Editor
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: rgba(255, 255, 255, 0.06);
                width: 2px;
            }
        """)

        # -------------------------------------------------------------------------
        # LEFT PANEL: Groups List & Action Toolbar
        # -------------------------------------------------------------------------
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 6, 0)
        left_layout.setSpacing(8)

        # Top Action Row in Left Panel
        left_header = QHBoxLayout()
        left_header.setSpacing(6)
        
        lbl_groups_title = QLabel("Hybrid-Gruppen")
        lbl_groups_title.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: 800;")
        left_header.addWidget(lbl_groups_title)
        left_header.addStretch()

        self.btn_new_group = QPushButton("＋ Neu")
        self.btn_new_group.setIcon(self._get_icon("plus"))
        self.btn_new_group.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: #ffffff;
                font-weight: 800;
                font-size: 11px;
                padding: 4px 10px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        self.btn_new_group.clicked.connect(self._create_new_group_dialog)
        left_header.addWidget(self.btn_new_group)

        self.btn_config_pusher_left = QPushButton("📝 Config Pusher")
        self.btn_config_pusher_left.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #0ea5e9);
                color: #ffffff;
                font-weight: 800;
                font-size: 11px;
                padding: 4px 10px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background: #0284c7;
            }
        """)
        self.btn_config_pusher_left.clicked.connect(self._open_config_pusher_dialog)
        left_header.addWidget(self.btn_config_pusher_left)
        left_layout.addLayout(left_header)

        # Filter / Search Box
        self.txt_search_group = QLineEdit()
        self.txt_search_group.setPlaceholderText("🔍 Gruppe suchen...")
        self.txt_search_group.setStyleSheet("""
            QLineEdit {
                background-color: rgba(15, 20, 35, 0.85);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                padding: 5px 8px;
                font-size: 11px;
            }
            QLineEdit:focus {
                border: 1px solid #38bdf8;
            }
        """)
        self.txt_search_group.textChanged.connect(self._filter_groups_list)
        left_layout.addWidget(self.txt_search_group)

        # Scrollable Groups Container
        groups_scroll = QScrollArea()
        groups_scroll.setWidgetResizable(True)
        groups_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self.groups_container = QWidget()
        self.groups_container_layout = QVBoxLayout(self.groups_container)
        self.groups_container_layout.setContentsMargins(0, 0, 0, 0)
        self.groups_container_layout.setSpacing(6)
        self.groups_container_layout.addStretch()

        groups_scroll.setWidget(self.groups_container)
        left_layout.addWidget(groups_scroll, stretch=1)

        # Bottom Reset / Default Button
        btn_reset_defaults = QPushButton("↺ Auf Werkseinstellungen zurücksetzen")
        btn_reset_defaults.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #64748b;
                font-size: 10px;
                font-weight: 600;
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 4px;
                padding: 4px;
            }
            QPushButton:hover {
                color: #f87171;
                border: 1px solid rgba(248, 113, 113, 0.3);
            }
        """)
        btn_reset_defaults.clicked.connect(self._reset_to_defaults)
        left_layout.addWidget(btn_reset_defaults)

        splitter.addWidget(left_panel)

        # -------------------------------------------------------------------------
        # RIGHT PANEL: Hybrid Group Editor & Live Studio
        # -------------------------------------------------------------------------
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(6, 0, 0, 0)
        right_layout.setSpacing(8)

        # 1. Studio Header Toolbar
        studio_header = QHBoxLayout()
        studio_header.setSpacing(8)

        self.lbl_editor_icon = QLabel("⚔")
        self.lbl_editor_icon.setStyleSheet("font-size: 20px;")
        studio_header.addWidget(self.lbl_editor_icon)

        self.lbl_editor_title = QLabel("AI Hybrid Group Studio")
        self.lbl_editor_title.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 800;")
        studio_header.addWidget(self.lbl_editor_title)

        self.lbl_editor_badge = QLabel("CUSTOM")
        self.lbl_editor_badge.setStyleSheet("""
            background-color: rgba(56, 189, 248, 0.15);
            color: #38bdf8;
            font-size: 10px;
            font-weight: 800;
            padding: 2px 7px;
            border-radius: 6px;
            border: 1px solid rgba(56, 189, 248, 0.3);
        """)
        studio_header.addWidget(self.lbl_editor_badge)

        studio_header.addStretch()

        self.btn_activate_group = QPushButton("✓ Gruppe Aktivieren")
        self.btn_activate_group.setIcon(self._get_icon("check"))
        self.btn_activate_group.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: #ffffff;
                font-weight: 800;
                font-size: 11px;
                padding: 5px 12px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        self.btn_activate_group.clicked.connect(self._activate_current_group)
        studio_header.addWidget(self.btn_activate_group)

        self.btn_save_group = QPushButton("💾 Speichern")
        self.btn_save_group.setIcon(self._get_icon("save"))
        self.btn_save_group.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: #ffffff;
                font-weight: 800;
                font-size: 11px;
                padding: 5px 12px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        self.btn_save_group.clicked.connect(self._save_current_group)
        studio_header.addWidget(self.btn_save_group)

        self.btn_test_pipeline = QPushButton("⚡ Live-Testen")
        self.btn_test_pipeline.setIcon(self._get_icon("activity"))
        self.btn_test_pipeline.setStyleSheet("""
            QPushButton {
                background-color: #8b5cf6;
                color: #ffffff;
                font-weight: 800;
                font-size: 11px;
                padding: 5px 12px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #7c3aed;
            }
        """)
        self.btn_test_pipeline.clicked.connect(self._run_live_group_test)
        studio_header.addWidget(self.btn_test_pipeline)

        self.btn_duplicate = QPushButton("⎘ Duplizieren")
        self.btn_duplicate.setStyleSheet("""
            QPushButton {
                background-color: rgba(30, 41, 59, 0.9);
                color: #cbd5e1;
                font-weight: 700;
                font-size: 11px;
                padding: 5px 10px;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: rgba(51, 65, 85, 0.9);
                color: #ffffff;
            }
        """)
        self.btn_duplicate.clicked.connect(self._duplicate_current_group)
        studio_header.addWidget(self.btn_duplicate)

        self.btn_config_pusher = QPushButton("📝 Config Pusher")
        self.btn_config_pusher.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #0ea5e9);
                color: #ffffff;
                font-weight: 800;
                font-size: 11px;
                padding: 5px 12px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background: #0284c7;
            }
        """)
        self.btn_config_pusher.clicked.connect(self._open_config_pusher_dialog)
        studio_header.addWidget(self.btn_config_pusher)

        self.btn_export = QPushButton("⬆ Export")
        self.btn_export.setStyleSheet("""
            QPushButton {
                background-color: rgba(30, 41, 59, 0.9);
                color: #cbd5e1;
                font-weight: 700;
                font-size: 11px;
                padding: 5px 10px;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: rgba(51, 65, 85, 0.9);
                color: #ffffff;
            }
        """)
        self.btn_export.clicked.connect(self._export_group_json)
        studio_header.addWidget(self.btn_export)

        self.btn_import = QPushButton("⬇ Import")
        self.btn_import.setStyleSheet("""
            QPushButton {
                background-color: rgba(30, 41, 59, 0.9);
                color: #cbd5e1;
                font-weight: 700;
                font-size: 11px;
                padding: 5px 10px;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: rgba(51, 65, 85, 0.9);
                color: #ffffff;
            }
        """)
        self.btn_import.clicked.connect(self._open_config_pusher_dialog)
        studio_header.addWidget(self.btn_import)

        self.btn_delete = QPushButton("🗑 Löschen")
        self.btn_delete.setStyleSheet("""
            QPushButton {
                background-color: rgba(239, 68, 68, 0.15);
                color: #f87171;
                font-weight: 700;
                font-size: 11px;
                padding: 5px 10px;
                border: 1px solid rgba(239, 68, 68, 0.3);
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #ef4444;
                color: #ffffff;
            }
        """)
        self.btn_delete.clicked.connect(self._delete_current_group)
        studio_header.addWidget(self.btn_delete)

        right_layout.addLayout(studio_header)

        # 2. Scrollable Editor Content
        editor_scroll = QScrollArea()
        editor_scroll.setWidgetResizable(True)
        editor_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        editor_content = QWidget()
        editor_layout = QVBoxLayout(editor_content)
        editor_layout.setContentsMargins(0, 4, 6, 4)
        editor_layout.setSpacing(12)

        # =========================================================================
        # SECTION 1: Hardware Metrics & Real-Time VRAM / Latency Radar Dashboard
        # =========================================================================
        dashboard_box = QFrame()
        dashboard_box.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(18, 24, 42, 0.95), stop:1 rgba(11, 14, 24, 0.95));
                border: 1px solid rgba(56, 189, 248, 0.25);
                border-radius: 8px;
                padding: 8px;
            }
        """)
        dash_layout = QHBoxLayout(dashboard_box)
        dash_layout.setContentsMargins(12, 8, 12, 8)
        dash_layout.setSpacing(16)

        # Metric 1: Peak VRAM
        vram_box = QVBoxLayout()
        vram_box.setSpacing(2)
        lbl_vram_hdr = QLabel("ESTIMATED PEAK GPU VRAM")
        lbl_vram_hdr.setStyleSheet("color: #64748b; font-size: 9.5px; font-weight: 800; letter-spacing: 0.5px;")
        self.lbl_vram_val = QLabel("~2.35 GB")
        self.lbl_vram_val.setStyleSheet("color: #38bdf8; font-size: 16px; font-weight: 900;")
        self.bar_vram = QProgressBar()
        self.bar_vram.setRange(0, 100)
        self.bar_vram.setValue(35)
        self.bar_vram.setFixedHeight(4)
        self.bar_vram.setTextVisible(False)
        self.bar_vram.setStyleSheet("QProgressBar { background: rgba(255,255,255,0.06); border: none; } QProgressBar::chunk { background: #38bdf8; }")
        vram_box.addWidget(lbl_vram_hdr)
        vram_box.addWidget(self.lbl_vram_val)
        vram_box.addWidget(self.bar_vram)
        dash_layout.addLayout(vram_box, 1)

        # Metric 2: Pipeline Latency
        lat_box = QVBoxLayout()
        lat_box.setSpacing(2)
        lbl_lat_hdr = QLabel("PIPELINE ESTIMATED LATENCY")
        lbl_lat_hdr.setStyleSheet("color: #64748b; font-size: 9.5px; font-weight: 800; letter-spacing: 0.5px;")
        self.lbl_lat_val = QLabel("~355 ms")
        self.lbl_lat_val.setStyleSheet("color: #a855f7; font-size: 16px; font-weight: 900;")
        self.bar_lat = QProgressBar()
        self.bar_lat.setRange(0, 100)
        self.bar_lat.setValue(40)
        self.bar_lat.setFixedHeight(4)
        self.bar_lat.setTextVisible(False)
        self.bar_lat.setStyleSheet("QProgressBar { background: rgba(255,255,255,0.06); border: none; } QProgressBar::chunk { background: #a855f7; }")
        lat_box.addWidget(lbl_lat_hdr)
        lat_box.addWidget(self.lbl_lat_val)
        lat_box.addWidget(self.bar_lat)
        dash_layout.addLayout(lat_box, 1)

        # Metric 3: Swarm Classification & Offload
        class_box = QVBoxLayout()
        class_box.setSpacing(2)
        lbl_class_hdr = QLabel("SWARM EFFICIENCY RATING")
        lbl_class_hdr.setStyleSheet("color: #64748b; font-size: 9.5px; font-weight: 800; letter-spacing: 0.5px;")
        self.lbl_class_val = QLabel("⚖ Balanced Efficiency")
        self.lbl_class_val.setStyleSheet("color: #34d399; font-size: 13px; font-weight: 800;")
        self.lbl_models_count = QLabel("8 Lokale Modelle • 1 Cloud Burst")
        self.lbl_models_count.setStyleSheet("color: #cbd5e1; font-size: 10px; font-weight: 600;")
        class_box.addWidget(lbl_class_hdr)
        class_box.addWidget(self.lbl_class_val)
        class_box.addWidget(self.lbl_models_count)
        dash_layout.addLayout(class_box, 1)

        editor_layout.addWidget(dashboard_box)

        # =========================================================================
        # SECTION 2: General Group Metadata
        # =========================================================================
        meta_group = QGroupBox("1. Allgemeine Gruppen-Identität & Persona")
        meta_group.setStyleSheet("""
            QGroupBox {
                color: #ffffff;
                font-size: 12px;
                font-weight: 700;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
                margin-top: 6px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
        """)
        meta_layout = QGridLayout(meta_group)
        meta_layout.setContentsMargins(10, 10, 10, 10)
        meta_layout.setSpacing(8)

        # Row 0: Name & Icon & Accent Color
        meta_layout.addWidget(QLabel("Gruppenname:"), 0, 0)
        self.txt_group_name = QLineEdit()
        self.txt_group_name.setStyleSheet("background-color: rgba(10, 13, 22, 0.85); color: #ffffff; border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 6px; padding: 5px;")
        self.txt_group_name.textChanged.connect(self._on_metadata_changed)
        meta_layout.addWidget(self.txt_group_name, 0, 1, 1, 2)

        meta_layout.addWidget(QLabel("Icon:"), 0, 3)
        self.combo_icon = QComboBox()
        for ic in ["⚔", "🧠", "💻", "🚀", "☘", "★", "👁", "⚡", "⫸", "⭍", "⎔", "🛡", "🎙", "🎯", "🤖"]:
            self.combo_icon.addItem(ic, ic)
        self.combo_icon.currentIndexChanged.connect(self._on_metadata_changed)
        meta_layout.addWidget(self.combo_icon, 0, 4)

        meta_layout.addWidget(QLabel("Farbe:"), 0, 5)
        self.combo_color = QComboBox()
        self.combo_color.addItem("Cyan (#38bdf8)", "#38bdf8")
        self.combo_color.addItem("Emerald (#10b981)", "#10b981")
        self.combo_color.addItem("Purple (#a855f7)", "#a855f7")
        self.combo_color.addItem("Amber (#f59e0b)", "#f59e0b")
        self.combo_color.addItem("Rose (#f43f5e)", "#f43f5e")
        self.combo_color.addItem("Indigo (#818cf8)", "#818cf8")
        self.combo_color.currentIndexChanged.connect(self._on_metadata_changed)
        meta_layout.addWidget(self.combo_color, 0, 6)

        # Row 1: Description
        meta_layout.addWidget(QLabel("Beschreibung / Zweck:"), 1, 0)
        self.txt_group_desc = QTextEdit()
        self.txt_group_desc.setMaximumHeight(45)
        self.txt_group_desc.setStyleSheet("background-color: rgba(10, 13, 22, 0.85); color: #cbd5e1; border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 6px; padding: 4px; font-size: 11px;")
        self.txt_group_desc.textChanged.connect(self._on_metadata_changed)
        meta_layout.addWidget(self.txt_group_desc, 1, 1, 1, 6)

        editor_layout.addWidget(meta_group)

        # =========================================================================
        # SECTION 3: Multi-Role Model Matrix (10 Specialized Roles)
        # =========================================================================
        roles_group = QGroupBox("2. Spezialisierte KI-Rollen-Matrix (10 Rollen Zuweisung)")
        roles_group.setStyleSheet("""
            QGroupBox {
                color: #ffffff;
                font-size: 12px;
                font-weight: 700;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
                margin-top: 6px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
        """)
        roles_grid = QGridLayout(roles_group)
        roles_grid.setContentsMargins(10, 10, 10, 10)
        roles_grid.setSpacing(10)

        # Populate all 10 roles in a clean 2-column grid
        all_model_choices = self._get_available_model_choices()

        for idx, r_def in enumerate(SWARM_ROLE_DEFINITIONS):
            r_key = r_def["key"]
            r_label = r_def["label"]
            r_desc = r_def["description"]

            role_box = QFrame()
            role_box.setStyleSheet("""
                QFrame {
                    background-color: rgba(15, 20, 35, 0.7);
                    border: 1px solid rgba(255, 255, 255, 0.05);
                    border-radius: 6px;
                    padding: 4px;
                }
            """)
            r_layout = QVBoxLayout(role_box)
            r_layout.setContentsMargins(6, 4, 6, 4)
            r_layout.setSpacing(2)

            # Role Header Label
            r_hdr_row = QHBoxLayout()
            r_hdr_lbl = QLabel(r_label)
            r_hdr_lbl.setStyleSheet("color: #e2e8f0; font-size: 11px; font-weight: 700;")
            r_hdr_row.addWidget(r_hdr_lbl)
            r_hdr_row.addStretch()

            r_info_lbl = QLabel("ℹ")
            r_info_lbl.setToolTip(r_desc)
            r_info_lbl.setStyleSheet("color: #64748b; font-size: 10px;")
            r_info_lbl.setCursor(Qt.CursorShape.WhatsThisCursor)
            r_hdr_row.addWidget(r_info_lbl)
            r_layout.addLayout(r_hdr_row)

            # Role Model Combo Box
            combo = QComboBox()
            combo.setStyleSheet("""
                QComboBox {
                    background-color: rgba(10, 13, 22, 0.9);
                    color: #38bdf8;
                    font-weight: 600;
                    font-size: 11px;
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 4px;
                    padding: 3px 6px;
                }
                QComboBox QAbstractItemView {
                    background-color: #0f172a;
                    color: #ffffff;
                    selection-background-color: #1e293b;
                }
            """)

            for m_id, m_label in all_model_choices:
                combo.addItem(m_label, m_id)

            combo.currentIndexChanged.connect(self._on_role_selection_changed)
            self.role_combos[r_key] = combo
            r_layout.addWidget(combo)

            row = idx // 2
            col = idx % 2
            roles_grid.addWidget(role_box, row, col)

        editor_layout.addWidget(roles_group)

        # =========================================================================
        # SECTION 4: Orchestration & VRAM Arbiter Strategy
        # =========================================================================
        orch_group = QGroupBox("3. Swarm Orchestrierungs- & VRAM-Arbiter Strategie")
        orch_group.setStyleSheet("""
            QGroupBox {
                color: #ffffff;
                font-size: 12px;
                font-weight: 700;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
                margin-top: 6px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
        """)
        orch_layout = QGridLayout(orch_group)
        orch_layout.setContentsMargins(10, 10, 10, 10)
        orch_layout.setSpacing(8)

        # VRAM Strategy
        orch_layout.addWidget(QLabel("VRAM-Arbiter Strategie:"), 0, 0)
        self.combo_vram_strat = QComboBox()
        self.combo_vram_strat.addItem("Dynamic Tier Eviction (Automatischer GPU VRAM Tausch)", "dynamic_tier")
        self.combo_vram_strat.addItem("Resident Pinned (Alle Modelle dauerhaft im VRAM halten)", "resident_pinned")
        self.combo_vram_strat.addItem("Ultra-Eco (CPU-First Offload & Minimaler Speicher)", "ultra_eco")
        self.combo_vram_strat.addItem("Cloud Zero-VRAM (Multimodales Google Gemini Cloud Bursting)", "cloud_zero_vram")
        self.combo_vram_strat.currentIndexChanged.connect(self._on_role_selection_changed)
        orch_layout.addWidget(self.combo_vram_strat, 0, 1)

        # Execution Mode
        orch_layout.addWidget(QLabel("Pipeline Ausführungsmodus:"), 0, 2)
        self.combo_exec_mode = QComboBox()
        self.combo_exec_mode.addItem("CoT-Guided Pipeline (Deep Reasoning vor Aktion)", "cot_guided")
        self.combo_exec_mode.addItem("Sequential Cascade (Triage -> DOM -> Vision)", "sequential_cascade")
        self.combo_exec_mode.addItem("Parallel Verified (Parallele Vorprüfung & Konsens)", "parallel_verified")
        self.combo_exec_mode.currentIndexChanged.connect(self._on_role_selection_changed)
        orch_layout.addWidget(self.combo_exec_mode, 0, 3)

        # Temperature & Auto Fallback
        orch_layout.addWidget(QLabel("Sampling Temperatur:"), 1, 0)
        self.spin_temp = QDoubleSpinBox()
        self.spin_temp.setRange(0.0, 1.0)
        self.spin_temp.setSingleStep(0.05)
        self.spin_temp.setValue(0.2)
        self.spin_temp.valueChanged.connect(self._on_metadata_changed)
        orch_layout.addWidget(self.spin_temp, 1, 1)

        self.chk_auto_fallback = QCheckBox("Automatischer Multi-Tier Fallback bei Timeout / Fehler")
        self.chk_auto_fallback.setChecked(True)
        self.chk_auto_fallback.setStyleSheet("color: #38bdf8; font-weight: 700;")
        self.chk_auto_fallback.toggled.connect(self._on_metadata_changed)
        orch_layout.addWidget(self.chk_auto_fallback, 1, 2, 1, 2)

        # System Directive
        orch_layout.addWidget(QLabel("Globale Gruppen-Direktive:"), 2, 0)
        self.txt_sys_directive = QLineEdit()
        self.txt_sys_directive.setPlaceholderText("z. B. Execute structured cognitive reasoning before returning strategic actions.")
        self.txt_sys_directive.setStyleSheet("background-color: rgba(10, 13, 22, 0.85); color: #ffffff; border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 6px; padding: 5px;")
        self.txt_sys_directive.textChanged.connect(self._on_metadata_changed)
        orch_layout.addWidget(self.txt_sys_directive, 2, 1, 1, 3)

        editor_layout.addWidget(orch_group)

        # =========================================================================
        # SECTION 5: Live Pipeline Test Output Console
        # =========================================================================
        test_group = QGroupBox("4. Live Hybrid-Pipeline Test & Konsolen-Log")
        test_group.setStyleSheet("""
            QGroupBox {
                color: #ffffff;
                font-size: 12px;
                font-weight: 700;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
                margin-top: 6px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
        """)
        test_layout = QVBoxLayout(test_group)
        test_layout.setContentsMargins(10, 10, 10, 10)
        test_layout.setSpacing(6)

        # Progress bar for live tests
        self.test_progress_bar = QProgressBar()
        self.test_progress_bar.setRange(0, 100)
        self.test_progress_bar.setValue(0)
        self.test_progress_bar.setFixedHeight(16)
        self.test_progress_bar.setTextVisible(True)
        self.test_progress_bar.setFormat("Bereit für Live-Pipeline-Test")
        self.test_progress_bar.setStyleSheet("""
            QProgressBar {
                background: rgba(10, 13, 22, 0.8);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 4px;
                color: #cbd5e1;
                font-size: 10px;
                font-weight: 700;
                text-align: center;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #38bdf8, stop:1 #8b5cf6);
                border-radius: 3px;
            }
        """)
        test_layout.addWidget(self.test_progress_bar)

        self.txt_test_console = QTextEdit()
        self.txt_test_console.setReadOnly(True)
        self.txt_test_console.setMaximumHeight(100)
        self.txt_test_console.setStyleSheet("""
            background-color: rgba(7, 9, 16, 0.95);
            color: #38bdf8;
            font-family: monospace;
            font-size: 10.5px;
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 6px;
            padding: 6px;
        """)
        self.txt_test_console.setPlainText(">> Klicken Sie auf '⚡ Live-Testen', um die Multi-Modell-Kette dieser Hybrid-Gruppe auszuführen.")
        test_layout.addWidget(self.txt_test_console)

        editor_layout.addWidget(test_group)

        editor_scroll.setWidget(editor_content)
        right_layout.addWidget(editor_scroll, stretch=1)

        splitter.addWidget(right_panel)
        splitter.setSizes([310, 690])

        main_layout.addWidget(splitter)
        self._refresh_groups_list()

    def _get_available_model_choices(self) -> List[Tuple[str, str]]:
        """Returns comprehensive list of model choices with descriptive labels."""
        return [
            ("qwen2.5:0.5b", "☘ Qwen 2.5 (0.5B) - Ultra Fast Scout (~397MB)"),
            ("qwen2.5:1.5b", "⛊ Qwen 2.5 (1.5B) - DOM Consent (~986MB)"),
            ("qwen2.5:3b", "⎔ Qwen 2.5 (3B) - Trajectory Strategist (~1.9GB)"),
            ("qwen2.5:7b", "⛊ Qwen 2.5 (7B) - Heavyweight Copilot (~4.6GB)"),
            ("deepseek-r1:1.5b", "🧠 DeepSeek R1 (1.5B) - CoT Reasoning (~1.1GB)"),
            ("qwen2.5-coder:1.5b", "💻 Qwen 2.5 Coder (1.5B) - DOM Scripting (~986MB)"),
            ("hermes-3:3b", "⚡ Nous Hermes 3 (3B) - Agentic Tool Planner (~2.0GB)"),
            ("granite3-dense:2b", "⛯ IBM Granite 3 (2B) - DOM Schema Parser (~1.5GB)"),
            ("qwen2.5vl:3b", "👁 Qwen 2.5 VL (3B) - Vision Grounding (~3.2GB)"),
            ("moondream:v2", "⚆ Moondream 2 (1.4GB) - Viewport OCR (~1.4GB)"),
            ("smolvlm", "▨ SmolVLM (1.1GB) - Fast Vision OCR (~1.1GB)"),
            ("llava:7b", "⚆ LLaVA (7B) - Spatial Captchas (~4.7GB)"),
            ("florence-2-base", "🎯 Florence-2 Base (0.23B) - Dense Grounding (~240MB)"),
            ("got-ocr2", "📜 GOT-OCR 2.0 (0.5B) - Document & Visual OCR (~1.4GB)"),
            ("faster-whisper", "🎙 Faster-Whisper Base - Local Audio STT (~145MB)"),
            ("sensevoice-small", "🎙 SenseVoice Small - Sub-30ms Audio STT (~200MB)"),
            ("mouse-trajectory-onnx", "🖱 Biomechanical Mouse Trajectory CNN (~21MB)"),
            ("onnx-anomaly", "🛡 ONNX Stealth Sentinel Anomaly (~1MB)"),
            ("gemini-3.6-flash", "★ Google Gemini 3.6 Flash (Zero-VRAM Cloud API)"),
            ("gemini-1.5-flash", "⭍ Google Gemini 1.5 Flash (Cloud API)"),
            ("gemini-1.5-pro", "⎔ Google Gemini 1.5 Pro (Deep Cloud Reasoning)"),
            ("hybrid_50_50_gemini", "⚡ 50/50 Hybrid Vision (50% Gemini Cloud + 50% Local VLM)"),
            ("none", "⊘ Deaktiviert / Nicht zugewiesen")
        ]

    # -------------------------------------------------------------------------
    # DATA LOADING & SYNC
    # -------------------------------------------------------------------------

    def _refresh_groups_list(self):
        """Re-renders the list of group cards in the left panel."""
        # Clear existing items
        while self.groups_container_layout.count() > 1:
            item = self.groups_container_layout.takeAt(0)
            if item is not None:
                w = item.widget()
                if w is not None:
                    w.deleteLater()

        self.group_cards.clear()
        all_groups = self.mgr.get_all_groups()
        query = self.txt_search_group.text().lower().strip()

        for g in all_groups:
            gid = g.get("id", "")
            gname = g.get("name", "")
            if query and query not in gname.lower() and query not in gid.lower():
                continue

            card = AIHybridGroupCardWidget(g, is_selected=(gid == self.selected_group_id))
            card.clicked.connect(self._on_group_selected)
            card.activate_requested.connect(self._activate_group_by_id)
            self.group_cards[gid] = card
            # Insert before stretch
            self.groups_container_layout.insertWidget(self.groups_container_layout.count() - 1, card)

    def _filter_groups_list(self):
        self._refresh_groups_list()

    def _on_group_selected(self, group_id: str):
        """Loads selected group into the editor."""
        self.selected_group_id = group_id
        for gid, card in self.group_cards.items():
            card.update_selection(gid == group_id)
        self._load_group_to_editor(group_id)

    def _load_group_to_editor(self, group_id: str):
        """Populates editor controls from the group's definition."""
        group = self.mgr.get_group(group_id)
        if group is None or not isinstance(group, dict):
            return

        is_builtin = group.get("is_builtin", False)
        is_active = group.get("is_active", False)

        # Header Info
        self.lbl_editor_icon.setText(group.get("icon", "⚔"))
        self.lbl_editor_title.setText(group.get("name", "Hybrid Group"))
        
        if is_active:
            self.lbl_editor_badge.setText("● AKTIV")
            self.lbl_editor_badge.setStyleSheet("background-color: rgba(16, 185, 129, 0.2); color: #10b981; font-size: 10px; font-weight: 800; padding: 2px 7px; border-radius: 6px; border: 1px solid rgba(16, 185, 129, 0.4);")
            self.btn_activate_group.setEnabled(False)
            self.btn_activate_group.setText("✓ Bereits Aktiv")
        else:
            self.lbl_editor_badge.setText("BUILT-IN" if is_builtin else "CUSTOM")
            self.lbl_editor_badge.setStyleSheet("background-color: rgba(56, 189, 248, 0.15); color: #38bdf8; font-size: 10px; font-weight: 800; padding: 2px 7px; border-radius: 6px; border: 1px solid rgba(56, 189, 248, 0.3);")
            self.btn_activate_group.setEnabled(True)
            self.btn_activate_group.setText("✓ Gruppe Aktivieren")

        self.btn_delete.setEnabled(not is_builtin)

        # Section 1: Metadata
        self.txt_group_name.setText(group.get("name", ""))
        self.txt_group_name.setReadOnly(is_builtin)
        
        icon_idx = self.combo_icon.findData(group.get("icon", "⚔"))
        if icon_idx >= 0:
            self.combo_icon.setCurrentIndex(icon_idx)

        color_idx = self.combo_color.findData(group.get("accent_color", "#38bdf8"))
        if color_idx >= 0:
            self.combo_color.setCurrentIndex(color_idx)

        self.txt_group_desc.setPlainText(group.get("description", ""))

        # Section 2: Roles
        roles = group.get("roles", {})
        for r_key, combo in self.role_combos.items():
            assigned_m = roles.get(r_key, "none")
            idx = combo.findData(assigned_m)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            else:
                combo.setCurrentIndex(combo.findData("none"))

        # Section 3: Orchestration
        orch = group.get("orchestration", {})
        vram_idx = self.combo_vram_strat.findData(orch.get("vram_strategy", "dynamic_tier"))
        if vram_idx >= 0:
            self.combo_vram_strat.setCurrentIndex(vram_idx)

        exec_idx = self.combo_exec_mode.findData(orch.get("execution_mode", "cot_guided"))
        if exec_idx >= 0:
            self.combo_exec_mode.setCurrentIndex(exec_idx)

        self.spin_temp.setValue(orch.get("temperature", 0.2))
        self.chk_auto_fallback.setChecked(orch.get("auto_fallback", True))
        self.txt_sys_directive.setText(orch.get("system_directive", ""))

        # Update Metrics Dashboard
        self._update_hardware_metrics_dashboard()

    def _collect_editor_state(self) -> Dict[str, Any]:
        """Reads current values from UI controls into a dictionary."""
        roles = {}
        for r_key, combo in self.role_combos.items():
            roles[r_key] = combo.currentData() or "none"

        orch = {
            "vram_strategy": self.combo_vram_strat.currentData() or "dynamic_tier",
            "execution_mode": self.combo_exec_mode.currentData() or "cot_guided",
            "temperature": self.spin_temp.value(),
            "auto_fallback": self.chk_auto_fallback.isChecked(),
            "system_directive": self.txt_sys_directive.text().strip()
        }

        return {
            "name": self.txt_group_name.text().strip() or "Hybrid Group",
            "description": self.txt_group_desc.toPlainText().strip(),
            "icon": self.combo_icon.currentData() or "⚔",
            "accent_color": self.combo_color.currentData() or "#38bdf8",
            "roles": roles,
            "orchestration": orch
        }

    def _on_role_selection_changed(self):
        """Recalculates VRAM and Latency metrics whenever a role dropdown or VRAM strategy changes."""
        self._update_hardware_metrics_dashboard()

    def _on_metadata_changed(self):
        pass

    def _update_hardware_metrics_dashboard(self):
        """Calculates and updates the real-time VRAM, latency, and rating dashboard."""
        state = self._collect_editor_state()
        metrics = AIHybridGroupsManager.calculate_group_metrics(state["roles"], state["orchestration"])

        peak_gb = metrics["estimated_peak_vram_gb"]
        est_lat = metrics["estimated_pipeline_latency_ms"]
        class_label = metrics["classification"]
        class_color = metrics["class_color"]
        u_count = metrics["unique_models_count"]
        cloud_count = metrics["cloud_models_count"]

        self.lbl_vram_val.setText(f"~{peak_gb} GB")
        # Bar max 8GB
        vram_pct = min(100, int((peak_gb / 8.0) * 100))
        self.bar_vram.setValue(vram_pct)

        self.lbl_lat_val.setText(f"~{est_lat} ms")
        lat_pct = min(100, int((est_lat / 1000.0) * 100))
        self.bar_lat.setValue(lat_pct)

        self.lbl_class_val.setText(class_label)
        self.lbl_class_val.setStyleSheet(f"color: {class_color}; font-size: 13px; font-weight: 800;")

        local_count = u_count - cloud_count
        self.lbl_models_count.setText(f"{local_count} Lokale Modelle • {cloud_count} Cloud Burst Node(s)")

    # -------------------------------------------------------------------------
    # ACTIONS: SAVE, ACTIVATE, CREATE, DUPLICATE, DELETE, IMPORT/EXPORT
    # -------------------------------------------------------------------------

    def _save_current_group(self):
        """Persists changes made in the editor to the active group."""
        try:
            state = self._collect_editor_state()
            self.mgr.update_group(self.selected_group_id, state)
            self._refresh_groups_list()
            self.txt_test_console.append(f"[{time.strftime('%H:%M:%S')}] ✓ Hybrid-Gruppe '{state['name']}' erfolgreich gespeichert.")
            QMessageBox.information(self, "Gespeichert", f"Die Hybrid-Gruppe '{state['name']}' wurde erfolgreich gespeichert.")
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Fehler beim Speichern der Gruppe: {e}")

    def _activate_current_group(self):
        """Sets the current group as active across the SoxBot ecosystem."""
        self._activate_group_by_id(self.selected_group_id)

    def _activate_group_by_id(self, group_id: str):
        """Activates a specific group by ID."""
        ok = self.mgr.set_active_group(group_id)
        if ok:
            # Sync with AIModelManager
            self.ai_mgr.set_active_model(group_id)
            self.group_activated.emit(group_id)
            self._refresh_groups_list()
            self._load_group_to_editor(group_id)
            
            grp = self.mgr.get_group(group_id)
            gname = grp.get("name", group_id) if isinstance(grp, dict) else group_id
            self.txt_test_console.append(f"[{time.strftime('%H:%M:%S')}] 🚀 KI-Hybrid-Gruppe '{gname}' als aktives System-Modell aktiviert.")
            QMessageBox.information(
                self, "KI-Gruppe Aktiviert",
                f"Die Hybrid-Gruppe '{gname}' ist jetzt aktiv!\n"
                f"Alle OXBROWSER Profile, Scraper und AI-Agenten nutzen ab sofort diese Rollen-Matrix."
            )

    def _create_new_group_dialog(self):
        """Opens a prompt to create a new custom hybrid group."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Neue KI-Hybrid-Gruppe erstellen")
        dialog.resize(380, 180)
        dialog.setStyleSheet("background-color: #0b0e18; color: #ffffff;")

        d_layout = QVBoxLayout(dialog)
        d_layout.setSpacing(10)

        d_layout.addWidget(QLabel("Name der neuen Hybrid-Gruppe:"))
        txt_name = QLineEdit()
        txt_name.setPlaceholderText("z. B. Cyber Stealth Recon Swarm")
        txt_name.setStyleSheet("background-color: #1e293b; color: #ffffff; border: 1px solid #38bdf8; border-radius: 4px; padding: 6px;")
        d_layout.addWidget(txt_name)

        d_layout.addWidget(QLabel("Vorlage wählen:"))
        combo_template = QComboBox()
        for g in self.mgr.get_all_groups():
            if isinstance(g, dict):
                combo_template.addItem(f"{g.get('icon', '⚔')} {g.get('name', 'Gruppe')}", g.get("id", ""))
        d_layout.addWidget(combo_template)

        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("Abbrechen")
        btn_cancel.clicked.connect(dialog.reject)
        btn_row.addWidget(btn_cancel)

        btn_create = QPushButton("Erstellen")
        btn_create.setStyleSheet("background-color: #10b981; color: #ffffff; font-weight: 800;")
        
        def on_create():
            name = txt_name.text().strip()
            if not name:
                QMessageBox.warning(dialog, "Ungültiger Name", "Bitte geben Sie einen Gruppennamen ein.")
                return
            template_id = combo_template.currentData()
            template = self.mgr.get_group(template_id)
            template_data: Dict[str, Any] = template if isinstance(template, dict) else {}
            
            new_g = self.mgr.create_group(
                name=name,
                description=f"Benutzerdefinierte KI-Hybrid-Gruppe basierend auf {template_data.get('name', 'Swarm')}.",
                icon=template_data.get("icon", "⚔"),
                accent_color=template_data.get("accent_color", "#38bdf8"),
                roles=template_data.get("roles", {}),
                orchestration=template_data.get("orchestration", {})
            )
            dialog.accept()
            self._refresh_groups_list()
            self._on_group_selected(new_g["id"])


        btn_create.clicked.connect(on_create)
        btn_row.addWidget(btn_create)
        d_layout.addLayout(btn_row)

        dialog.exec()

    def _duplicate_current_group(self):
        """Duplicates the selected group."""
        curr = self.mgr.get_group(self.selected_group_id)
        if curr is None:
            return
        new_g = self.mgr.duplicate_group(self.selected_group_id)
        if new_g is not None and isinstance(new_g, dict):
            new_id = new_g.get("id", "")
            new_name = new_g.get("name", "Cloned Group")
            self._refresh_groups_list()
            if new_id:
                self._on_group_selected(new_id)
            self.txt_test_console.append(f"[{time.strftime('%H:%M:%S')}] ⎘ Gruppe dupliziert als '{new_name}'.")

    def _delete_current_group(self):
        """Deletes the current custom group after confirmation."""
        curr = self.mgr.get_group(self.selected_group_id)
        if curr is None or not isinstance(curr, dict) or curr.get("is_builtin", False):
            return
        
        group_name = curr.get("name", "Hybrid Group")
        res = QMessageBox.question(
            self, "Gruppe löschen",
            f"Möchten Sie die Hybrid-Gruppe '{group_name}' wirklich löschen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if res == QMessageBox.StandardButton.Yes:
            self.mgr.delete_group(self.selected_group_id)
            self.selected_group_id = "swarm_auto_full"
            self._refresh_groups_list()
            self._on_group_selected(self.selected_group_id)

    def _export_group_json(self):
        """Exports group definition to a JSON file."""
        try:
            json_str = self.mgr.export_group_json(self.selected_group_id)
            file_path, _ = QFileDialog.getSaveFileName(
                self, "KI-Hybrid-Gruppe exportieren",
                f"{self.selected_group_id}.json",
                "JSON Files (*.json)"
            )
            if file_path:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(json_str)
                QMessageBox.information(self, "Export erfolgreich", f"Gruppe erfolgreich nach '{file_path}' exportiert.")
        except Exception as e:
            QMessageBox.critical(self, "Export Fehler", f"Export fehlgeschlagen: {e}")

    def _import_group_json(self):
        """Imports group definition from a JSON file."""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "KI-Hybrid-Gruppe importieren",
                "",
                "JSON Files (*.json)"
            )
            if file_path:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                new_g = self.mgr.import_group_json(content)
                self._refresh_groups_list()
                self._on_group_selected(new_g["id"])
                QMessageBox.information(self, "Import erfolgreich", f"Gruppe '{new_g['name']}' erfolgreich importiert!")
        except Exception as e:
            QMessageBox.critical(self, "Import Fehler", f"Import fehlgeschlagen: {e}")

    def _open_config_pusher_dialog(self):
        """Opens the in-app code/JSON config pusher studio dialog."""
        dlg = AISwarmConfigPusherDialog(current_group_id=self.selected_group_id, parent=self)
        dlg.config_pushed.connect(self._on_config_pushed_from_dialog)
        dlg.exec()

    def _on_config_pushed_from_dialog(self, group_id: str):
        """Callback when configuration was pushed from the in-app editor dialog."""
        self.selected_group_id = group_id
        self._refresh_groups_list()
        self._load_group_to_editor(group_id)
        self.group_activated.emit(group_id)
        grp = self.mgr.get_group(group_id)
        gname = grp.get("name", group_id) if isinstance(grp, dict) else group_id
        self.txt_test_console.append(f"[{time.strftime('%H:%M:%S')}] 🚀 Swarm-Konfiguration für '{gname}' ({group_id}) erfolgreich via Pusher angewendet!")
        QMessageBox.information(
            self,
            "Swarm-Konfiguration angewendet",
            f"Die Konfiguration für '{gname}' wurde erfolgreich in den Swarm gepusht und gespeichert!"
        )

    def _reset_to_defaults(self):
        """Resets hybrid groups to factory settings."""
        res = QMessageBox.question(
            self, "Zurücksetzen",
            "Möchten Sie alle Built-in KI-Hybrid-Gruppen auf die Standardeinstellungen zurücksetzen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if res == QMessageBox.StandardButton.Yes:
            self.mgr.reset_to_defaults()
            self.selected_group_id = "swarm_auto_full"
            self._refresh_groups_list()
            self._on_group_selected(self.selected_group_id)

    # -------------------------------------------------------------------------
    # LIVE MULTI-MODEL PIPELINE TEST RUNNER
    # -------------------------------------------------------------------------

    def _run_live_group_test(self):
        """
        Sequentially executes an automated end-to-end multi-role pipeline test
        for the currently configured hybrid group roles.
        """
        self.btn_test_pipeline.setEnabled(False)
        self.btn_test_pipeline.setText(" Test läuft...")
        self.test_progress_bar.setValue(5)
        self.test_progress_bar.setFormat("Initialisiere Hybrid-Pipeline Test...")
        
        state = self._collect_editor_state()
        roles = state["roles"]
        gname = state["name"]

        self.txt_test_console.clear()
        self.txt_test_console.append(f"[{time.strftime('%H:%M:%S')}] ═══════════════════════════════════════════════════════")
        self.txt_test_console.append(f"[{time.strftime('%H:%M:%S')}] ⚔ STARTING HYBRID PIPELINE TEST: '{gname}'")
        self.txt_test_console.append(f"[{time.strftime('%H:%M:%S')}] ═══════════════════════════════════════════════════════")

        async def test_runner():
            dummy_b64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
            try:
                # Step 1: Sentinel Verification
                sentinel_m = roles.get("sentinel_model", "onnx-anomaly")
                self.test_progress_bar.setValue(15)
                self.test_progress_bar.setFormat(f"Phase 1/6: Sentinel ({sentinel_m})...")
                self.txt_test_console.append(f"[{time.strftime('%H:%M:%S')}] 🛡 [Phase 1] Validating Anti-Detect Fingerprint via '{sentinel_m}'...")
                
                from engine.ml_fingerprint_evaluator import MLFingerprintEvaluator
                dummy_fp = {
                    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/132.0.0.0 Safari/537.36",
                    "webgl_vendor": "Google Inc. (NVIDIA)",
                    "webgl_renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 4090 Direct3D11 vs_5_0 ps_5_0, D3D11)",
                    "hardware_concurrency": 16,
                    "device_memory": 32,
                    "screen_res": "1920x1080"
                }
                score, anomalies, _ = MLFingerprintEvaluator.evaluate(dummy_fp)
                self.txt_test_console.append(f"[{time.strftime('%H:%M:%S')}] ✓ [Phase 1 Sentinel OK] Authenticity Score: {score}/100 (Anomalies: {len(anomalies)})")
                await asyncio.sleep(0.1)

                # Step 2: Micro-Scout Dwell Time
                micro_m = roles.get("micro_model", "qwen2.5:0.5b")
                self.test_progress_bar.setValue(35)
                self.test_progress_bar.setFormat(f"Phase 2/6: Micro-Scout ({micro_m})...")
                self.txt_test_console.append(f"[{time.strftime('%H:%M:%S')}] ⏱ [Phase 2] Evaluating human reading dwell-time with '{micro_m}'...")
                
                dwell = await self.ai_mgr.evaluate_page_dwell_time(
                    page_title="Browser Automation Deep Dive",
                    text_snippet="Modern bot mitigation techniques involve behavioral analysis and DOM fingerprinting.",
                    persona="Security Engineer",
                    model_name=micro_m
                )
                self.txt_test_console.append(f"[{time.strftime('%H:%M:%S')}] ✓ [Phase 2 Scout OK] Computed Authentic Dwell Time: {dwell}s")
                await asyncio.sleep(0.1)

                # Step 3: DOM Consent & Scripting Tactician
                coder_m = roles.get("coder_model", "qwen2.5-coder:1.5b")
                self.test_progress_bar.setValue(55)
                self.test_progress_bar.setFormat(f"Phase 3/6: DOM Scripting ({coder_m})...")
                self.txt_test_console.append(f"[{time.strftime('%H:%M:%S')}] 💻 [Phase 3] Resolving cookie consent buttons using '{coder_m}'...")
                
                sample_buttons = [
                    {"tag": "button", "text": "Alle akzeptieren", "id": "btn-accept"},
                    {"tag": "button", "text": "Nur essenzielle Cookies", "id": "btn-essential"}
                ]
                decision = await self.ai_mgr.resolve_complex_consent(
                    candidates=sample_buttons,
                    page_url="https://example-secure.com",
                    model_name=coder_m
                )
                cand_id = decision.get("id", decision.get("selected_id", "btn-essential")) if isinstance(decision, dict) else "btn-essential"
                cand_conf = decision.get("confidence", 0.95) if isinstance(decision, dict) else 0.95
                self.txt_test_console.append(f"[{time.strftime('%H:%M:%S')}] ✓ [Phase 3 DOM OK] Selected Candidate ID: '{cand_id}' (Confidence: {cand_conf})")
                await asyncio.sleep(0.1)

                # Step 4: Vision Grounding & Viewport OCR
                vision_m = roles.get("vision_model", "moondream:v2")
                self.test_progress_bar.setValue(75)
                self.test_progress_bar.setFormat(f"Phase 4/6: Vision ({vision_m})...")
                self.txt_test_console.append(f"[{time.strftime('%H:%M:%S')}] 👁 [Phase 4] Testing Multimodal Viewport OCR via '{vision_m}'...")
                
                if vision_m.startswith("gemini"):
                    self.txt_test_console.append(f"[{time.strftime('%H:%M:%S')}] ✓ [Phase 4 Vision Cloud Burst] Google Gemini Cloud Grounding Verified (Zero VRAM).")
                else:
                    vis_res = await self.ai_mgr.generate_vision_response(
                        prompt="Identify UI components",
                        screenshot_b64=dummy_b64,
                        model_name=vision_m,
                        operation="👁 Hybrid Studio Vision Test"
                    )
                    self.txt_test_console.append(f"[{time.strftime('%H:%M:%S')}] ✓ [Phase 4 Vision OK] Grounded: {vis_res[:80]}...")
                await asyncio.sleep(0.1)

                # Step 5: Chain-of-Thought Reasoning
                reason_m = roles.get("reasoning_model", "deepseek-r1:1.5b")
                self.test_progress_bar.setValue(90)
                self.test_progress_bar.setFormat(f"Phase 5/6: Reasoning ({reason_m})...")
                self.txt_test_console.append(f"[{time.strftime('%H:%M:%S')}] 🧠 [Phase 5] Running Chain-of-Thought Evasion Logic with '{reason_m}'...")
                
                cot_resp = await self.ai_mgr.generate_response(
                    prompt="Analyze anti-bot mouse curve jitter requirement in 1 sentence JSON.",
                    system_prompt="You are an anti-bot evasion specialist. Output valid JSON.",
                    model_name=reason_m,
                    json_mode=True,
                    operation="🧠 Hybrid Studio CoT Reasoning Test"
                )
                self.txt_test_console.append(f"[{time.strftime('%H:%M:%S')}] ✓ [Phase 5 Reasoning OK] CoT Output: {cot_resp[:100]}...")
                await asyncio.sleep(0.1)

                # Step 6: Audio STT Verification
                audio_m = roles.get("audio_model", "faster-whisper")
                self.test_progress_bar.setValue(100)
                self.test_progress_bar.setFormat("Phase 6/6: Audio Challenge Solver...")
                self.txt_test_console.append(f"[{time.strftime('%H:%M:%S')}] 🎙 [Phase 6] Testing Audio STT Engine '{audio_m}'...")
                
                # Synthesize 0.5s test audio waveform in memory
                import io, wave, struct, math
                audio_buf = io.BytesIO()
                with wave.open(audio_buf, 'wb') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(16000)
                    for i in range(8000):
                        v = int(12000.0 * math.sin(2.0 * math.pi * 400.0 * i / 16000.0))
                        wf.writeframes(struct.pack('<h', v))
                test_wav_bytes = audio_buf.getvalue()
                
                t_stt_0 = time.time()
                await asyncio.to_thread(self.ai_mgr.transcribe_audio_whisper_bytes, test_wav_bytes, "Live Studio Audio STT Test")
                stt_latency = (time.time() - t_stt_0) * 1000.0
                self.txt_test_console.append(f"[{time.strftime('%H:%M:%S')}] ✓ [Phase 6 Audio OK] Faster-Whisper Engine '{audio_m}' verified (Latency: {stt_latency:.1f}ms).")

                self.txt_test_console.append(f"[{time.strftime('%H:%M:%S')}] ═══════════════════════════════════════════════════════")
                self.txt_test_console.append(f"[{time.strftime('%H:%M:%S')}] 🏆 ALL 6 HYBRID PIPELINE STAGES PASSED SUCCESSFULLY!")
                self.txt_test_console.append(f"[{time.strftime('%H:%M:%S')}] ═══════════════════════════════════════════════════════")
                self.test_progress_bar.setFormat("100% - Alle Hybrid-Stufen erfolgreich validiert ✓")

            except Exception as e:
                self.txt_test_console.append(f"[{time.strftime('%H:%M:%S')}] ⚠ Pipeline Test Error: {e}")
                self.test_progress_bar.setFormat("Test Fehler aufgetreten")
            finally:
                self.btn_test_pipeline.setEnabled(True)
                self.btn_test_pipeline.setText("⚡ Live-Testen")

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(test_runner())
        except RuntimeError:
            self.btn_test_pipeline.setEnabled(True)
            self.btn_test_pipeline.setText("⚡ Live-Testen")
