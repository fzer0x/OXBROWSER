import asyncio
import logging
from typing import Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QGroupBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QWidget, QFrame
)
from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QIcon, QDesktopServices
import qasync
import os
from typing import Optional, Dict, Any

from engine.ai_model_manager import AIModelManager
import config

logger = logging.getLogger("ModelManagerDialog")


DIRECT_MODEL_DOWNLOAD_REGISTRY: Dict[str, Dict[str, str]] = {
    "qwen2.5:1.5b": {
        "url": "https://ollama.com/library/qwen2.5:1.5b",
        "subfolder": "ollama_models"
    },
    "deepseek-r1:1.5b": {
        "url": "https://ollama.com/library/deepseek-r1:1.5b",
        "subfolder": "ollama_models"
    },
    "qwen2.5-coder:1.5b": {
        "url": "https://ollama.com/library/qwen2.5-coder:1.5b",
        "subfolder": "ollama_models"
    },
    "qwen2.5vl:3b": {
        "url": "https://ollama.com/library/qwen2.5vl:3b",
        "subfolder": "ollama_models"
    },
    "qwen2.5:3b": {
        "url": "https://ollama.com/library/qwen2.5:3b",
        "subfolder": "ollama_models"
    },
    "qwen2.5:0.5b": {
        "url": "https://ollama.com/library/qwen2.5:0.5b",
        "subfolder": "ollama_models"
    },
    "qwen2.5:7b": {
        "url": "https://ollama.com/library/qwen2.5:7b",
        "subfolder": "ollama_models"
    },
    "hermes-3:3b": {
        "url": "https://ollama.com/library/hermes3:3b",
        "subfolder": "ollama_models"
    },
    "granite3-dense:2b": {
        "url": "https://ollama.com/library/granite3-dense:2b",
        "subfolder": "ollama_models"
    },
    "llava:7b": {
        "url": "https://ollama.com/library/llava:7b",
        "subfolder": "ollama_models"
    },
    "moondream:v2": {
        "url": "https://ollama.com/library/moondream",
        "subfolder": "ollama_models"
    },
    "smolvlm": {
        "url": "https://huggingface.co/HuggingFaceTB/SmolVLM-Instruct",
        "subfolder": "ollama_models"
    },
    "florence-2-base": {
        "url": "https://huggingface.co/microsoft/Florence-2-base",
        "subfolder": "florence"
    },
    "got-ocr2": {
        "url": "https://huggingface.co/stepfun-ai/GOT-OCR2_0",
        "subfolder": "got_ocr"
    },
    "faster-whisper": {
        "url": "https://huggingface.co/Systran/faster-whisper-base",
        "subfolder": "whisper"
    },
    "sensevoice-small": {
        "url": "https://huggingface.co/FunAudioLLM/SenseVoiceSmall",
        "subfolder": "sensevoice"
    },
    "onnx-anomaly": {
        "url": "https://github.com/microsoft/onnxruntime/releases",
        "subfolder": ""
    },
    "mouse-trajectory-onnx": {
        "url": "https://github.com/microsoft/onnxruntime/releases",
        "subfolder": ""
    },
    "gemini-3.6-flash": {
        "url": "https://aistudio.google.com/app/apikey",
        "subfolder": ""
    }
}


class ModelDownloadRoutingDialog(QDialog):
    """
    Dialog asking the user whether to download the model internally via SoxBot
    or open the official download page in an external browser while automatically
    routing to and opening the local target models directory.
    """
    ROUTE_INTERNAL = "internal"
    ROUTE_EXTERNAL = "external"
    ROUTE_CANCEL = "cancel"

    def __init__(self, model_info: Dict[str, Any], models_dir: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.model_info = model_info
        self.models_dir = models_dir
        self.choice = self.ROUTE_CANCEL

        model_id = model_info.get("id", "")
        reg_info = DIRECT_MODEL_DOWNLOAD_REGISTRY.get(model_id, {})

        subfolder = reg_info.get("subfolder", "ollama_models")
        if subfolder:
            self.target_dir = os.path.join(models_dir, subfolder)
        else:
            self.target_dir = models_dir

        default_tag = model_id.replace("hermes-3", "hermes3")
        self.external_url = reg_info.get("url", f"https://ollama.com/library/{default_tag}")

        self.setWindowTitle(f"Download-Routing – {model_info.get('name', model_id)}")
        self.setFixedWidth(560)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header Info Card
        m_name = self.model_info.get("name", self.model_info.get("id", ""))
        m_id = self.model_info.get("id", "")
        m_size = self.model_info.get("size", "N/A")
        m_desc = self.model_info.get("desc", "")

        header_box = QFrame()
        header_box.setStyleSheet("""
            QFrame {
                background-color: #1e1e2e;
                border: 1px solid #313244;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        h_layout = QVBoxLayout(header_box)
        h_layout.setContentsMargins(10, 10, 10, 10)
        h_layout.setSpacing(6)

        title_row = QHBoxLayout()
        lbl_title = QLabel(f"🤖 {m_name}")
        lbl_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #cdd6f4;")
        badge_size = QLabel(f"📦 {m_size}")
        badge_size.setStyleSheet("background-color: #313244; color: #89b4fa; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;")
        
        title_row.addWidget(lbl_title)
        title_row.addStretch()
        title_row.addWidget(badge_size)
        h_layout.addLayout(title_row)

        lbl_id = QLabel(f"Modell-Tag: {m_id}")
        lbl_id.setStyleSheet("color: #a6adc8; font-size: 12px; font-family: monospace;")
        h_layout.addWidget(lbl_id)

        if m_desc:
            lbl_desc = QLabel(m_desc)
            lbl_desc.setWordWrap(True)
            lbl_desc.setStyleSheet("color: #bac2de; font-size: 12px;")
            h_layout.addWidget(lbl_desc)

        layout.addWidget(header_box)

        lbl_prompt = QLabel("Wie möchtest du das Modell beziehen?")
        lbl_prompt.setStyleSheet("font-weight: bold; font-size: 13px; color: #f8fafc; margin-top: 4px;")
        layout.addWidget(lbl_prompt)

        # Option 1: Internal Download Manager Card
        opt_internal = QFrame()
        opt_internal.setStyleSheet("""
            QFrame {
                background-color: rgba(99, 102, 241, 0.08);
                border: 1px solid rgba(99, 102, 241, 0.35);
                border-radius: 8px;
                padding: 10px;
            }
        """)
        opt1_layout = QVBoxLayout(opt_internal)
        opt1_layout.setContentsMargins(10, 10, 10, 10)
        opt1_layout.setSpacing(4)
        
        lbl_opt1_title = QLabel("📥 1. Interner Download Manager (Empfohlen)")
        lbl_opt1_title.setStyleSheet("font-weight: bold; font-size: 13px; color: #818cf8;")
        lbl_opt1_desc = QLabel(
            "• Vollautomatischer Download direkt in OXBROWSER über die lokale Ollama-Inferenz-Engine.\n"
            "• Live-Fortschrittsbalken, Bandbreitenmessung und ETA-Restzeitanzeige.\n"
            "• Sofortige Registrierung und Nutzung im AI Swarm & Chat Copilot."
        )
        lbl_opt1_desc.setStyleSheet("color: #cdd6f4; font-size: 11px;")
        opt1_layout.addWidget(lbl_opt1_title)
        opt1_layout.addWidget(lbl_opt1_desc)
        layout.addWidget(opt_internal)

        # Option 2: External Browser & Local Folder Auto-Route Card
        opt_external = QFrame()
        opt_external.setStyleSheet("""
            QFrame {
                background-color: rgba(56, 189, 248, 0.08);
                border: 1px solid rgba(56, 189, 248, 0.35);
                border-radius: 8px;
                padding: 10px;
            }
        """)
        opt2_layout = QVBoxLayout(opt_external)
        opt2_layout.setContentsMargins(10, 10, 10, 10)
        opt2_layout.setSpacing(4)

        lbl_opt2_title = QLabel("🌐 2. Externer Browser + Auto-Route zum Modell-Ordner")
        lbl_opt2_title.setStyleSheet("font-weight: bold; font-size: 13px; color: #38bdf8;")
        lbl_opt2_desc = QLabel(
            f"• Öffnet die offizielle Modell-Seite im Webbrowser:\n  {self.external_url}\n"
            f"• Öffnet gleichzeitig den lokalen Zielordner im Dateimanager:\n  {self.target_dir}\n"
            "• Ideal für manuelles Ablegen von GGUF-Gewichten oder Browser-Downloads."
        )
        lbl_opt2_desc.setStyleSheet("color: #cdd6f4; font-size: 11px;")
        opt2_layout.addWidget(lbl_opt2_title)
        opt2_layout.addWidget(lbl_opt2_desc)
        layout.addWidget(opt_external)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        btn_cancel = QPushButton("Abbrechen")
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 6px;
                padding: 8px 14px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #45475a; }
        """)
        btn_cancel.clicked.connect(self.reject)

        btn_ext = QPushButton("🌐 Browser & Ordner")
        btn_ext.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 8px 14px;
                font-weight: 700;
            }
            QPushButton:hover { background-color: #0369a1; }
        """)
        btn_ext.clicked.connect(self._select_external)

        btn_int = QPushButton("📥 Intern herunterladen")
        btn_int.setStyleSheet("""
            QPushButton {
                background-color: #4f46e5;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 8px 14px;
                font-weight: 700;
            }
            QPushButton:hover { background-color: #4338ca; }
        """)
        btn_int.clicked.connect(self._select_internal)

        btn_layout.addWidget(btn_cancel)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_ext)
        btn_layout.addWidget(btn_int)
        layout.addLayout(btn_layout)

    def _select_internal(self):
        self.choice = self.ROUTE_INTERNAL
        self.accept()

    def _select_external(self):
        self.choice = self.ROUTE_EXTERNAL
        self.accept()


class ModelManagerDialog(QDialog):
    """08/2026 AI Model & Vision LLM Download Manager Modal."""

    MODELS_CONFIG = [
        {
            "id": "qwen2.5:1.5b",
            "name": "Qwen 2.5 (1.5B)",
            "desc": "Fast Text Reasoning, DOM Consent & Topic Trajectory Engine (Recommended)",
            "size": "~980 MB"
        },
        {
            "id": "deepseek-r1:1.5b",
            "name": "DeepSeek R1 (1.5B)",
            "desc": "Chain-of-Thought Reasoning & Anti-Bot Defense Strategy Engine",
            "size": "~1.1 GB"
        },
        {
            "id": "qwen2.5-coder:1.5b",
            "name": "Qwen 2.5 Coder (1.5B)",
            "desc": "DOM Scripting, Shadow DOM Injection & Selector Engineering Tactician",
            "size": "~986 MB"
        },
        {
            "id": "qwen2.5vl:3b",
            "name": "Qwen 2.5 VL (3B)",
            "desc": "Next-Gen Multimodal Vision-Language Grounding & Subpixel Coordinate Model",
            "size": "~3.2 GB"
        },
        {
            "id": "qwen2.5:3b",
            "name": "Qwen 2.5 (3B)",
            "desc": "Deep Reasoning, Clickstream Modeling & Complex Intent Planner",
            "size": "~1.9 GB"
        },
        {
            "id": "qwen2.5:0.5b",
            "name": "Qwen 2.5 (0.5B)",
            "desc": "Ultra Fast & Lightweight Micro-LLM for Reading Dwell Time Estimation",
            "size": "~350 MB"
        },
        {
            "id": "qwen2.5:7b",
            "name": "Qwen 2.5 (7B)",
            "desc": "Heavyweight Desktop Copilot & Complex Anti-Detect Strategist",
            "size": "~4.5 GB"
        },
        {
            "id": "hermes-3:3b",
            "name": "Nous Hermes 3 (3B)",
            "desc": "Function-Calling & Autonomous Playwright Agentic Tool-Planner",
            "size": "~2.0 GB"
        },
        {
            "id": "granite3-dense:2b",
            "name": "IBM Granite 3 (2B)",
            "desc": "High-Reliability Structured DOM Schema & Code Extraktor",
            "size": "~1.5 GB"
        },
        {
            "id": "llava:7b",
            "name": "LLaVA (7B)",
            "desc": "Spatial Vision Model for 3x3/4x4 reCAPTCHA Classification & Grid Anomaly",
            "size": "~4.7 GB"
        },
        {
            "id": "moondream:v2",
            "name": "Moondream 2 (1.4GB)",
            "desc": "Fast Multimodal Vision Model for UI OCR & Banner Text Grounding",
            "size": "~1.4 GB"
        },
        {
            "id": "smolvlm",
            "name": "SmolVLM (1.1GB)",
            "desc": "Lightweight Vision Language Model for Fast Viewport Inspection",
            "size": "~1.1 GB"
        },
        {
            "id": "florence-2-base",
            "name": "Florence-2 Base (ONNX)",
            "desc": "Sub-80ms Spatial 2D Bounding Box UI Grounding & Real-Time Coordinates",
            "size": "~230 MB"
        },
        {
            "id": "got-ocr2",
            "name": "GOT-OCR 2.0",
            "desc": "General OCR Theory for Distorted Text Captchas & Obscured Banners",
            "size": "~1.4 GB"
        },
        {
            "id": "faster-whisper",
            "name": "Faster-Whisper (Base)",
            "desc": "Acoustic Speech-to-Text & reCAPTCHA Audio Challenge Solver",
            "size": "~145 MB"
        },
        {
            "id": "sensevoice-small",
            "name": "SenseVoice Small (Audio)",
            "desc": "Sub-30ms Ultra-Fast Multi-Lingual Speech Challenge & Number STT",
            "size": "~200 MB"
        },
        {
            "id": "onnx-anomaly",
            "name": "ONNX Stealth Sentinel",
            "desc": "Sub-millisecond mathematical feature tensor evaluation of browser profiles",
            "size": "~750 KB"
        },
        {
            "id": "mouse-trajectory-onnx",
            "name": "Mouse Trajectory CNN (ONNX)",
            "desc": "Biomechanical Human Fitts's Law Mouse Movement & Jitter Curve Generator",
            "size": "~21 MB"
        },
        {
            "id": "gemini-3.6-flash",
            "name": "Google Gemini 3.6 Flash (Cloud API)",
            "desc": "Zero-VRAM Ultra-Fast Cloud Multimodal Reasoning & One-Shot reCAPTCHA API",
            "size": "Cloud (0 MB)"
        }
    ]

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.ai_mgr = AIModelManager.get_instance()
        self.setWindowTitle("AI Model & Vision LLM Download Manager")
        self.resize(1180, 560)
        self.setMinimumSize(1080, 480)
        
        self.row_model_map = {}
        self.widget_map = {}
        self._init_ui()

        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self._refresh_status)
        self.timer.start()

        self._refresh_status()

    def _get_icon(self, name):
        return QIcon(os.path.join(os.path.dirname(__file__), "..", "assets", "icons", f"{name}.svg"))

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(14)

        # Header Title
        header_layout = QHBoxLayout()
        title_label = QLabel("Local AI & Vision Model Download Center")
        title_label.setStyleSheet("font-size: 17px; font-weight: 800; color: #f8fafc; letter-spacing: -0.3px;")
        
        self.status_lbl = QLabel("Checking Ollama status...")
        self.status_lbl.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: 700;")
        
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.status_lbl)
        main_layout.addLayout(header_layout)

        # Model Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Model", "Size", "Status / Download Progress", "Speed & ETA", "Actions"])
        
        v_header = self.table.verticalHeader()
        if v_header is not None:
            v_header.setVisible(False)
            v_header.setDefaultSectionSize(60)

        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)

        self._populate_table()

        header = self.table.horizontalHeader()
        if header is not None:
            header.setHighlightSections(False)
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
            header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(0, 230)
            self.table.setColumnWidth(1, 100)
            self.table.setColumnWidth(3, 180)
            self.table.setColumnWidth(4, 300)

        main_layout.addWidget(self.table)

        # Footer Actions
        footer_layout = QHBoxLayout()

        self.btn_free_vram = QPushButton(" Free GPU VRAM")
        self.btn_free_vram.setIcon(self._get_icon("zap"))
        self.btn_free_vram.setProperty("class", "DangerButton")
        self.btn_free_vram.setToolTip("Unload all AI models from GPU VRAM immediately.")
        self.btn_free_vram.clicked.connect(self._free_vram_clicked)
        footer_layout.addWidget(self.btn_free_vram)

        self.btn_close = QPushButton("Schließen")
        self.btn_close.setIcon(self._get_icon("x"))
        self.btn_close.setProperty("class", "SecondaryButton")
        self.btn_close.clicked.connect(self.close)
        footer_layout.addStretch()
        footer_layout.addWidget(self.btn_free_vram)
        footer_layout.addWidget(self.btn_close)
        main_layout.addLayout(footer_layout)

    def _free_vram_clicked(self):
        import asyncio
        self.btn_free_vram.setText(" Freeing...")
        self.btn_free_vram.setEnabled(False)

        async def _run():
            try:
                await self.ai_mgr.unload_all_models_from_vram()
                self.status_lbl.setText("GPU VRAM Cleared (All models unloaded)")
                self.status_lbl.setStyleSheet("color: #34d399; font-weight: 700;")
                self._refresh_status()
            except Exception:
                pass
            finally:
                self.btn_free_vram.setText(" Free GPU VRAM")
                self.btn_free_vram.setEnabled(True)

        asyncio.create_task(_run())

    def _populate_table(self):
        self.table.setRowCount(len(self.MODELS_CONFIG))
        for row, item in enumerate(self.MODELS_CONFIG):
            model_id = item["id"]
            self.row_model_map[model_id] = row

            # Col 0: Name & Desc
            name_widget = QWidget()
            n_layout = QVBoxLayout(name_widget)
            n_layout.setContentsMargins(8, 4, 8, 4)
            lbl_title = QLabel(item["name"])
            lbl_title.setStyleSheet("font-weight: 700; font-size: 13px; color: #f8fafc;")
            lbl_desc = QLabel(item["desc"])
            lbl_desc.setStyleSheet("font-size: 11px; color: #94a3b8;")
            n_layout.addWidget(lbl_title)
            n_layout.addWidget(lbl_desc)
            self.table.setCellWidget(row, 0, name_widget)

            # Col 1: Size
            size_item = QTableWidgetItem(item["size"])
            size_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 1, size_item)

            # Col 2: Progress Widget Container
            p_container = QWidget()
            p_layout = QVBoxLayout(p_container)
            p_layout.setContentsMargins(4, 8, 4, 8)
            p_bar = QProgressBar()
            p_bar.setRange(0, 100)
            p_bar.setValue(0)
            p_bar.setFixedHeight(24)
            p_bar.setFormat("Checking...")
            p_layout.addWidget(p_bar)
            self.table.setCellWidget(row, 2, p_container)

            # Col 3: Speed & ETA
            speed_item = QTableWidgetItem("-")
            speed_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 3, speed_item)

            # Col 4: Action Buttons Container
            btn_container = QWidget()
            b_layout = QHBoxLayout(btn_container)
            b_layout.setContentsMargins(4, 6, 4, 6)
            b_layout.setSpacing(6)
            b_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            btn_dl = QPushButton(" Download")
            btn_dl.setIcon(self._get_icon("download"))
            btn_dl.setProperty("class", "PrimaryButton")
            btn_dl.setMinimumHeight(30)
            btn_dl.setMinimumWidth(90)
            btn_dl.clicked.connect(lambda _, m=model_id: self._start_download(m))

            btn_cancel = QPushButton(" Cancel")
            btn_cancel.setIcon(self._get_icon("x-circle"))
            btn_cancel.setProperty("class", "DangerButton")
            btn_cancel.setMinimumHeight(30)
            btn_cancel.setMinimumWidth(85)
            btn_cancel.setEnabled(False)
            btn_cancel.clicked.connect(lambda _, m=model_id: self._cancel_download(m))

            btn_del = QPushButton(" Delete")
            btn_del.setIcon(self._get_icon("trash-2"))
            btn_del.setProperty("class", "SecondaryButton")
            btn_del.setMinimumHeight(30)
            btn_del.setMinimumWidth(85)
            btn_del.clicked.connect(lambda _, m=model_id: self._delete_model(m))

            b_layout.addWidget(btn_dl)
            b_layout.addWidget(btn_cancel)
            b_layout.addWidget(btn_del)
            self.table.setCellWidget(row, 4, btn_container)

            # Store direct widget references
            self.widget_map[model_id] = {
                "p_bar": p_bar,
                "speed_item": speed_item,
                "btn_dl": btn_dl,
                "btn_cancel": btn_cancel,
                "btn_del": btn_del
            }

    def _refresh_status(self):
        try:
            loop = asyncio.get_running_loop()
            if loop and loop.is_running() and not self.isHidden():
                if hasattr(self, "_refresh_task") and self._refresh_task and not self._refresh_task.done():
                    return
                self._refresh_task = loop.create_task(self._async_refresh_status())
        except (RuntimeError, Exception):
            pass

    async def _async_refresh_status(self):
        is_running = await self.ai_mgr.is_ollama_running()
        if not is_running:
            self.status_lbl.setText("⚠ Ollama offline (Local ONNX / Audio / HF active)")
            self.status_lbl.setStyleSheet("color: #fbbf24; font-weight: 700;")
            installed_models = []
        else:
            self.status_lbl.setText("✓ Ollama service active")
            self.status_lbl.setStyleSheet("color: #34d399; font-weight: 700;")
            installed_models = await self.ai_mgr.list_installed_models()

        installed_names = [m.get("name", "") for m in installed_models]
        active_dls = self.ai_mgr.get_active_downloads()

        for item in self.MODELS_CONFIG:
            model_id = item["id"]
            if model_id not in self.widget_map:
                continue

            w_info = self.widget_map[model_id]
            p_bar = w_info["p_bar"]
            speed_item = w_info["speed_item"]
            btn_dl = w_info["btn_dl"]
            btn_cancel = w_info["btn_cancel"]
            btn_del = w_info["btn_del"]

            dl_info = active_dls.get(model_id)

            if dl_info and dl_info.get("status") == "downloading":
                pct = int(dl_info.get("pct", 0.0))
                p_bar.setValue(pct)
                p_bar.setFormat(f"Downloading {pct}%")

                speed_mb = dl_info.get("speed_mbps", 0.0)
                eta = dl_info.get("eta_sec", 0)
                if eta > 60:
                    eta_str = f"{eta // 60}m {eta % 60}s left"
                elif eta > 0:
                    eta_str = f"{eta}s left"
                else:
                    eta_str = "calculating..."

                if speed_item:
                    speed_item.setText(f"{speed_mb:.1f} MB/s | {eta_str}")

                btn_dl.setEnabled(False)
                btn_cancel.setEnabled(True)
                btn_del.setEnabled(False)

            elif self.ai_mgr.is_model_installed(model_id) or any(m == model_id or m == f"{model_id}:latest" or (model_id == "smolvlm" and "moondream" in m) for m in installed_names):
                p_bar.setValue(100)
                p_bar.setFormat("Installed ✓")
                if speed_item:
                    speed_item.setText("Ready")

                btn_dl.setEnabled(False)
                btn_cancel.setEnabled(False)
                btn_del.setEnabled(True)

            else:
                p_bar.setValue(0)
                p_bar.setFormat("Not Installed")
                if speed_item:
                    speed_item.setText("-")

                btn_dl.setEnabled(True)
                btn_cancel.setEnabled(False)
                btn_del.setEnabled(False)

    def _start_download(self, model_id: str):
        # Retrieve model metadata from MODELS_CONFIG
        model_info = next((m for m in self.MODELS_CONFIG if m["id"] == model_id), {"id": model_id, "name": model_id, "size": "N/A", "desc": ""})

        dialog = ModelDownloadRoutingDialog(model_info, self.ai_mgr.models_dir, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if dialog.choice == ModelDownloadRoutingDialog.ROUTE_INTERNAL:
                asyncio.create_task(self._async_start_download(model_id))
            elif dialog.choice == ModelDownloadRoutingDialog.ROUTE_EXTERNAL:
                self._open_external_browser_and_folder(dialog.external_url, dialog.target_dir, model_info.get("name", model_id))

    def _open_external_browser_and_folder(self, url: str, target_dir: str, model_name: str):
        try:
            # 1. Open external web browser
            QDesktopServices.openUrl(QUrl(url))

            # 2. Auto-route / open local target models directory in OS file manager
            os.makedirs(target_dir, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(target_dir))

            QMessageBox.information(
                self,
                "Browser & Zielordner geöffnet",
                f"Die Download-Seite für '{model_name}' wurde im Webbrowser geöffnet.\n\n"
                f"Gleichzeitig wurde der Zielordner im Dateimanager geöffnet:\n{target_dir}\n\n"
                f"Du kannst manuell heruntergeladene Modelldateien (z.B. GGUF / Binaries) direkt in diesem Verzeichnis ablegen."
            )
        except Exception as e:
            QMessageBox.warning(self, "Fehler beim Öffnen", f"Konnte Webbrowser oder Zielordner nicht öffnen: {e}")

    async def _async_start_download(self, model_id: str):
        w_info = self.widget_map.get(model_id)
        if w_info:
            p_bar = w_info.get("p_bar")
            if p_bar:
                p_bar.setFormat(f"Starting download of {model_id}...")

        success = await self.ai_mgr.ensure_model_pulled(model_id)
        await self._async_refresh_status()
        if success:
            QMessageBox.information(self, "Download Complete", f"AI Model '{model_id}' was downloaded successfully!")
        else:
            dl_err = self.ai_mgr.get_active_downloads().get(model_id, {}).get("text", "Unknown error or invalid model tag")
            QMessageBox.warning(self, "Download Failed", f"Failed to download AI model '{model_id}'.\nDetails: {dl_err}")

    def _cancel_download(self, model_id: str):
        self.ai_mgr.cancel_download(model_id)
        QMessageBox.information(self, "Download Cancelled", f"Download for model '{model_id}' has been cancelled.")
        self._refresh_status()

    def _delete_model(self, model_id: str):
        reply = QMessageBox.question(
            self,
            "Confirm Model Deletion",
            f"Are you sure you want to delete local AI model '{model_id}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            asyncio.create_task(self._async_delete_model(model_id))

    async def _async_delete_model(self, model_id: str):
        success = await self.ai_mgr.delete_model(model_id)
        await self._async_refresh_status()
        if success:
            QMessageBox.information(self, "Model Deleted", f"Model '{model_id}' deleted from local storage.")
        else:
            QMessageBox.warning(self, "Deletion Failed", f"Could not delete model '{model_id}'.")

    def closeEvent(self, a0):
        event = a0
        if self.ai_mgr.is_any_download_active():
            reply = QMessageBox.question(
                self,
                " Active Model Download",
                "An AI model download is currently running in the background!\n\n"
                "Are you sure you want to close the Download Manager window?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                if event:
                    event.ignore()
                return
        if hasattr(self, "timer") and self.timer.isActive():
            self.timer.stop()
        if hasattr(self, "_refresh_task") and self._refresh_task and not self._refresh_task.done():
            self._refresh_task.cancel()
        if event:
            event.accept()
