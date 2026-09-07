import os
import asyncio
import json
import logging
from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QGroupBox, QSpinBox, QMessageBox, QTextEdit,
    QComboBox, QProgressBar, QCheckBox, QDoubleSpinBox,
    QFormLayout
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QIcon
import qasync
import config
from engine.ai_model_manager import AIModelManager

logger = logging.getLogger("AIConfigView")

class AISignalRelay(QObject):
    progress_signal = pyqtSignal(str, float)
    status_signal = pyqtSignal(str, bool)

class AIConfigView(QWidget):
    """Dedicated AI & Vision LLM Management, Configuration & Interactive DOM Resolution Sandbox View."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ai_mgr: AIModelManager = AIModelManager.get_instance()
        self.relay = AISignalRelay()
        self.relay.progress_signal.connect(self._on_progress)
        self.relay.status_signal.connect(self._on_status_updated)

        self._init_ui()
        self._check_server_status()

    def _get_icon(self, name):
        return QIcon(os.path.join(os.path.dirname(__file__), "..", "assets", "icons", f"{name}.svg"))

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(12)



        # -------------------------------------------------------------------------
        # SECTION 1: Model Manager & Local Ollama Server Control
        # -------------------------------------------------------------------------
        server_group = QGroupBox("Local AI Micro-LLM & Vision Model Manager (Ollama Server Engine)")
        server_layout = QVBoxLayout(server_group)
        server_layout.setSpacing(8)

        self.lbl_server_status = QLabel("Status: Checking local Ollama server (http://127.0.0.1:11434)...")
        self.lbl_server_status.setStyleSheet("color: #fbbf24; font-weight: 700; font-size: 12px;")
        server_layout.addWidget(self.lbl_server_status)

        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("Active AI Model:"))
        self.combo_models = QComboBox()
        self._populate_models_combo()
        self.combo_models.currentIndexChanged.connect(self._on_model_changed)
        model_row.addWidget(self.combo_models, stretch=1)
        server_layout.addLayout(model_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(20)
        server_layout.addWidget(self.progress_bar)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.btn_download = QPushButton(" Auto-Download & Setup")
        self.btn_download.setIcon(self._get_icon("download"))
        self.btn_download.setProperty("class", "PrimaryButton")
        self.btn_download.clicked.connect(self._download_and_setup)
        btn_row.addWidget(self.btn_download)

        self.btn_open_dl_mgr = QPushButton(" Model Download Center")
        self.btn_open_dl_mgr.setIcon(self._get_icon("folder-open"))
        self.btn_open_dl_mgr.setProperty("class", "SecondaryButton")
        self.btn_open_dl_mgr.clicked.connect(self._open_download_manager)
        btn_row.addWidget(self.btn_open_dl_mgr)

        self.btn_free_vram = QPushButton(" Free GPU VRAM")
        self.btn_free_vram.setIcon(self._get_icon("zap"))
        self.btn_free_vram.setProperty("class", "DangerButton")
        self.btn_free_vram.setToolTip("Unload all cached models from GPU memory immediately.")
        self.btn_free_vram.clicked.connect(self._free_vram_handler)
        btn_row.addWidget(self.btn_free_vram)

        self.btn_refresh = QPushButton(" Refresh Status")
        self.btn_refresh.setIcon(self._get_icon("refresh-cw"))
        self.btn_refresh.setProperty("class", "SecondaryButton")
        self.btn_refresh.clicked.connect(self._check_server_status)
        btn_row.addWidget(self.btn_refresh)

        self.btn_start_server = QPushButton(" Start Server")
        self.btn_start_server.setIcon(self._get_icon("play"))
        self.btn_start_server.setProperty("class", "SuccessButton")
        self.btn_start_server.clicked.connect(self._start_server)
        btn_row.addWidget(self.btn_start_server)

        server_layout.addLayout(btn_row)
        main_layout.addWidget(server_group)

        # -------------------------------------------------------------------------
        # SECTION 2: DOM Consent & LLM Hyperparameter Settings
        # -------------------------------------------------------------------------
        settings_group = QGroupBox("AI DOM Consent & Trajectory Hyperparameters")

        settings_layout = QVBoxLayout(settings_group)
        settings_layout.setSpacing(12)

        fields_row = QHBoxLayout()
        fields_row.setSpacing(12)

        form_left = QFormLayout()
        self.combo_strategy = QComboBox()
        self.combo_strategy.addItem("Strict Reject Non-Essential (GDPR / ePrivacy)", "strict_reject")
        self.combo_strategy.addItem("Smart Consent Hybrid (Reject default, fallback Necessary)", "smart_hybrid")
        self.combo_strategy.addItem("Accept All (Fast Track)", "accept_all")
        
        # Initialize with currently saved strategy
        idx = self.combo_strategy.findData(config.AI_CONSENT_STRATEGY)
        if idx >= 0:
            self.combo_strategy.setCurrentIndex(idx)
        form_left.addRow(QLabel("Consent Solving Strategy:"), self.combo_strategy)

        self.spin_shadow_depth = QSpinBox()
        self.spin_shadow_depth.setRange(1, 15)
        self.spin_shadow_depth.setValue(config.AI_SHADOW_DOM_DEPTH)
        form_left.addRow(QLabel("Shadow DOM v2 Max Depth:"), self.spin_shadow_depth)

        self.spin_temp = QDoubleSpinBox()
        self.spin_temp.setRange(0.0, 1.0)
        self.spin_temp.setSingleStep(0.05)
        self.spin_temp.setValue(config.AI_TEMPERATURE)
        form_left.addRow(QLabel("LLM Sampling Temperature:"), self.spin_temp)

        form_right = QVBoxLayout()
        form_right.addWidget(QLabel("Custom Reject Button Exclusion Regex Patterns:"))
        self.txt_exclusions = QTextEdit()
        self.txt_exclusions.setPlainText("\n".join(config.AI_CUSTOM_EXCLUSIONS))
        self.txt_exclusions.setMaximumHeight(80)
        self.txt_exclusions.setStyleSheet("background-color: rgba(10, 13, 22, 0.85); color: #a5b4fc; font-family: monospace; border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 6px; padding: 6px;")
        form_right.addWidget(self.txt_exclusions)

        fields_row.addLayout(form_left, stretch=1)
        fields_row.addLayout(form_right, stretch=1)
        settings_layout.addLayout(fields_row)

        # Save & Feedback Bar
        save_bar = QHBoxLayout()
        self.lbl_dom_save_status = QLabel("✓ Settings synchronized with encrypted vault")
        self.lbl_dom_save_status.setStyleSheet("color: #34d399; font-size: 11px; font-weight: 600;")
        save_bar.addWidget(self.lbl_dom_save_status)
        save_bar.addStretch()

        self.btn_save_dom_settings = QPushButton(" Save AI DOM Consent Settings")
        self.btn_save_dom_settings.setIcon(self._get_icon("check"))
        self.btn_save_dom_settings.setProperty("class", "PrimaryButton")
        self.btn_save_dom_settings.clicked.connect(lambda: self._save_dom_settings(notify_ui=True))
        save_bar.addWidget(self.btn_save_dom_settings)

        settings_layout.addLayout(save_bar)
        main_layout.addWidget(settings_group)

        # Auto-Save signal bindings
        self.combo_strategy.currentIndexChanged.connect(lambda: self._save_dom_settings(notify_ui=False))
        self.spin_shadow_depth.valueChanged.connect(lambda: self._save_dom_settings(notify_ui=False))
        self.spin_temp.valueChanged.connect(lambda: self._save_dom_settings(notify_ui=False))
        self.txt_exclusions.textChanged.connect(lambda: self._save_dom_settings(notify_ui=False))

        main_layout.addStretch()

    def _save_dom_settings(self, notify_ui: bool = False):
        """Persists AI DOM Consent and Trajectory settings to config and encrypted vault."""
        try:
            strat = self.combo_strategy.currentData()
            if strat:
                config.AI_CONSENT_STRATEGY = str(strat)
            config.AI_SHADOW_DOM_DEPTH = self.spin_shadow_depth.value()
            config.AI_TEMPERATURE = self.spin_temp.value()
            exclusions_text = self.txt_exclusions.toPlainText()
            config.AI_CUSTOM_EXCLUSIONS = [line.strip() for line in exclusions_text.splitlines() if line.strip()]

            config.save_app_config()
            self.lbl_dom_save_status.setText("✓ AI DOM Consent settings saved to encrypted vault")
            self.lbl_dom_save_status.setStyleSheet("color: #34d399; font-size: 11px; font-weight: 600;")

            if notify_ui:
                QMessageBox.information(
                    self, "AI Settings Saved",
                    f"AI DOM Consent & Trajectory settings have been saved successfully to the encrypted vault.\n\n"
                    f"• Strategy: {config.AI_CONSENT_STRATEGY}\n"
                    f"• Max Shadow Depth: {config.AI_SHADOW_DOM_DEPTH}\n"
                    f"• Temperature: {config.AI_TEMPERATURE}\n"
                    f"• Exclusion Patterns: {len(config.AI_CUSTOM_EXCLUSIONS)}"
                )
        except Exception as e:
            self.lbl_dom_save_status.setText(f"⚠ Failed to save settings: {e}")
            self.lbl_dom_save_status.setStyleSheet("color: #f87171; font-size: 11px; font-weight: 600;")
            if notify_ui:
                QMessageBox.warning(self, "Save Error", f"Could not save AI DOM settings: {e}")

    def _on_progress(self, msg: str, pct: float):
        self.lbl_server_status.setText(f"{msg}")
        self.lbl_server_status.setStyleSheet("color: #38bdf8; font-weight: 700; font-size: 12px;")
        val = max(0, min(100, int(pct)))
        self.progress_bar.setValue(val)
        self.progress_bar.setFormat(f"{val}% - {msg}")

    def _on_status_updated(self, msg: str, active: bool):
        self.lbl_server_status.setText(msg)
        if active:
            self.lbl_server_status.setStyleSheet("color: #34d399; font-weight: 700; font-size: 12px;")
            self.progress_bar.setValue(100)
            self.progress_bar.setFormat("100% - Server Active & Ready")
        else:
            self.lbl_server_status.setStyleSheet("color: #fbbf24; font-weight: 700; font-size: 12px;")

    def _check_server_status(self):
        async def check_task():
            try:
                from engine.ai_model_manager import AIModelManager
                mgr = AIModelManager.get_instance()
                running = await mgr.is_ollama_running()
                if running:
                    self.relay.status_signal.emit("Local Ollama AI Engine Active on http://127.0.0.1:11434", True)
                else:
                    self.relay.status_signal.emit("Local Ollama Server Offline (Click 'Auto-Download & Setup' to start)", False)
            except Exception as e:
                self.relay.status_signal.emit(f"AI Server Check Error: {e}", False)

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(check_task())
        except RuntimeError:
            pass

    def _populate_models_combo(self):
        """Populates model dropdown with all standard, cloud, and custom AI hybrid groups."""
        if not hasattr(self, "combo_models") or self.combo_models is None:
            return
        self.combo_models.blockSignals(True)
        self.combo_models.clear()
        for model_id, label in config.get_all_ai_model_options():
            self.combo_models.addItem(label, model_id)
        
        cur_active = self.ai_mgr.get_active_model()
        idx = self.combo_models.findData(cur_active)
        if idx >= 0:
            self.combo_models.setCurrentIndex(idx)
        self.combo_models.blockSignals(False)

    def showEvent(self, a0):
        super().showEvent(a0)
        self._populate_models_combo()
        self._check_server_status()

    def _on_model_changed(self, index: int):
        selected_model = self.combo_models.currentData()
        if selected_model:
            from engine.ai_model_manager import AIModelManager
            AIModelManager.get_instance().set_active_model(selected_model)

    def _download_and_setup(self):
        selected_model = self.combo_models.currentData() or config.DEFAULT_AI_MODEL
        from engine.ai_model_manager import AIModelManager
        AIModelManager.get_instance().set_active_model(selected_model)
        self.btn_download.setEnabled(False)
        self.progress_bar.setValue(5)
        self.lbl_server_status.setText(f"Initializing AI setup for '{selected_model}'...")

        async def setup_task():
            try:
                from engine.ai_model_manager import AIModelManager
                mgr = AIModelManager.get_instance()

                def progress_cb(msg: str, pct: float):
                    self.relay.progress_signal.emit(msg, pct)

                ok = await mgr.ensure_model_pulled(selected_model, progress_callback=progress_cb)
                if ok:
                    self.relay.status_signal.emit(f"Local AI Model '{selected_model}' Active & Ready!", True)
                    QMessageBox.information(
                        self, "AI Setup Complete",
                        f"Local AI Model '{selected_model}' successfully configured and active on http://127.0.0.1:11434!"
                    )
                else:
                    self.relay.status_signal.emit("AI setup failed. Check connection.", False)
            except Exception as e:
                self.relay.status_signal.emit(f"Error: {e}", False)
            finally:
                self.btn_download.setEnabled(True)

        asyncio.create_task(setup_task())

    def _open_download_manager(self):
        from ui.views.model_manager_dialog import ModelManagerDialog
        dialog = ModelManagerDialog(self)
        dialog.exec()

    def _start_server(self):
        async def start_task():
            try:
                from engine.ai_model_manager import AIModelManager
                mgr = AIModelManager.get_instance()
                self.lbl_server_status.setText("Starting local Ollama server process...")
                ok = await mgr.start_ollama_server()
                if ok:
                    self.relay.status_signal.emit("Local Ollama AI Server started successfully!", True)
                else:
                    self.relay.status_signal.emit("Failed to start Ollama server process.", False)
            except Exception as e:
                self.relay.status_signal.emit(f"Server start error: {e}", False)

        asyncio.create_task(start_task())

    def _free_vram_handler(self):
        self.btn_free_vram.setText(" Freeing VRAM...")
        self.btn_free_vram.setEnabled(False)

        async def _run():
            try:
                await self.ai_mgr.unload_all_models_from_vram()
                self.lbl_server_status.setText("Status: VRAM Cleared (All models unloaded from GPU)")
                self.lbl_server_status.setStyleSheet("color: #a6e3a1; font-weight: bold; font-size: 13px;")
                QMessageBox.information(self, "GPU VRAM Cleared", "All AI models were successfully unloaded from GPU VRAM.\nGPU memory has been freed.")
            except Exception as ex:
                QMessageBox.warning(self, "Error", f"Could not free VRAM: {ex}")
            finally:
                self.btn_free_vram.setText(" Free GPU VRAM")
                self.btn_free_vram.setEnabled(True)

        asyncio.create_task(_run())




