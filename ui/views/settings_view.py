import asyncio
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QGroupBox, QSpinBox, QMessageBox, QTextEdit,
    QComboBox, QProgressBar, QCheckBox, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QUrl
from PyQt6.QtGui import QIcon, QDesktopServices
import qasync
import config
import os



class SettingsView(QWidget):
    """Settings and Automation Plugins Manager View."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._refresh_server_ui()

    def _get_icon(self, name):
        return QIcon(os.path.join(os.path.dirname(__file__), "..", "assets", "icons", f"{name}.svg"))



    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)



        # 2. Google Gemini AI Cloud Provider & API-Key Configuration Group
        gemini_group = QGroupBox("Google Gemini Cloud AI & API-Key Configuration (Zero VRAM & Fast Captchas)")
        gemini_layout = QVBoxLayout(gemini_group)
        gemini_layout.setSpacing(10)

        # API Key Row (Masked Password with Toggle)
        key_row = QHBoxLayout()
        key_row.addWidget(QLabel("Gemini API Key:"))
        self.gemini_key_input = QLineEdit()
        self.gemini_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.gemini_key_input.setPlaceholderText("Enter Google AI Studio Gemini API Key (AIzaSy...)")
        self.gemini_key_input.setText(getattr(config, "GEMINI_API_KEY", ""))
        key_row.addWidget(self.gemini_key_input, stretch=1)

        self.btn_toggle_gemini_key = QPushButton(" Show")
        self.btn_toggle_gemini_key.setIcon(self._get_icon("eye"))
        self.btn_toggle_gemini_key.setProperty("class", "SecondaryButton")
        self.btn_toggle_gemini_key.setFixedWidth(80)
        self.btn_toggle_gemini_key.clicked.connect(self._toggle_gemini_key_visibility)
        key_row.addWidget(self.btn_toggle_gemini_key)
        gemini_layout.addLayout(key_row)

        # Model & Strategy Selection Row
        sel_row = QHBoxLayout()
        sel_row.setSpacing(12)

        sel_row.addWidget(QLabel("Default Model:"))
        self.gemini_model_combo = QComboBox()
        self.gemini_model_combo.addItem("Gemini Flash Lite (Ultra-Fast Cloud API) [Empfohlen]", "gemini-flash-lite-latest")
        self.gemini_model_combo.addItem("Gemini 3.8 Flash (High-Capacity Cloud)", "gemini-3.8-flash")
        self.gemini_model_combo.addItem("Gemini 3.7 Flash (Cloud Multimodal API)", "gemini-3.7-flash")
        self.gemini_model_combo.addItem("Gemini 3 Flash Preview (Experimental)", "gemini-3-flash-preview")
        self.gemini_model_combo.addItem("Gemini 3.1 Pro Preview (Deep Multimodal)", "gemini-3.1-pro-preview")
        cur_mod = getattr(config, "GEMINI_DEFAULT_MODEL", "gemini-flash-lite-latest")
        m_idx = self.gemini_model_combo.findData(cur_mod)
        if m_idx >= 0:
            self.gemini_model_combo.setCurrentIndex(m_idx)
        sel_row.addWidget(self.gemini_model_combo, stretch=1)


        sel_row.addWidget(QLabel("Strategy:"))
        self.gemini_strategy_combo = QComboBox()
        self.gemini_strategy_combo.addItem("Hybrid Fallback (Local + Gemini Fallback)", "hybrid_fallback")
        self.gemini_strategy_combo.addItem("Hybrid Vision (Local Text + Gemini Vision)", "hybrid_gemini_vision")
        self.gemini_strategy_combo.addItem("Gemini Cloud Only (0 MB VRAM)", "gemini_only")
        self.gemini_strategy_combo.addItem("Local Ollama Only", "local_only")
        cur_strat = getattr(config, "AI_PROVIDER_STRATEGY", "hybrid_fallback")
        st_idx = self.gemini_strategy_combo.findData(cur_strat)
        if st_idx >= 0:
            self.gemini_strategy_combo.setCurrentIndex(st_idx)
        sel_row.addWidget(self.gemini_strategy_combo, stretch=1)

        gemini_layout.addLayout(sel_row)

        # Action Buttons & Status
        gemini_btn_row = QHBoxLayout()
        gemini_btn_row.setSpacing(8)

        self.btn_test_gemini = QPushButton(" Test Gemini Connection")
        self.btn_test_gemini.setIcon(self._get_icon("zap"))
        self.btn_test_gemini.setProperty("class", "PrimaryButton")
        self.btn_test_gemini.clicked.connect(self._test_gemini_connection)
        gemini_btn_row.addWidget(self.btn_test_gemini)

        self.btn_save_gemini = QPushButton(" Save Gemini Settings")
        self.btn_save_gemini.setIcon(self._get_icon("check"))
        self.btn_save_gemini.setProperty("class", "SuccessButton")
        self.btn_save_gemini.clicked.connect(self._save_gemini_settings)
        gemini_btn_row.addWidget(self.btn_save_gemini)

        self.gemini_status_lbl = QLabel("Ready (Enter API Key and click Save)")
        self.gemini_status_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; margin-left: 8px;")
        gemini_btn_row.addWidget(self.gemini_status_lbl, stretch=1)

        gemini_layout.addLayout(gemini_btn_row)
        layout.addWidget(gemini_group)

        # 3. REST API Group

        api_group = QGroupBox("Local Automation REST API & Backend Gateway")
        api_layout = QVBoxLayout(api_group)
        api_layout.setSpacing(10)

        # Server Status and Control Row
        status_row = QHBoxLayout()
        self.api_status_lbl = QLabel(f"Server Status: Checking...")
        self.api_status_lbl.setStyleSheet("color: #34d399; font-weight: 700; font-size: 12px;")
        status_row.addWidget(self.api_status_lbl)
        status_row.addStretch()

        self.btn_start_api = QPushButton(" ▶ Start Backend")
        self.btn_start_api.setIcon(self._get_icon("play"))
        self.btn_start_api.setProperty("class", "PrimaryButton")
        self.btn_start_api.clicked.connect(self._start_backend_server)
        status_row.addWidget(self.btn_start_api)

        self.btn_stop_api = QPushButton(" ⏹ Stop Backend")
        self.btn_stop_api.setIcon(self._get_icon("square"))
        self.btn_stop_api.setProperty("class", "DangerButton")
        self.btn_stop_api.clicked.connect(self._stop_backend_server)
        status_row.addWidget(self.btn_stop_api)

        self.btn_restart_api = QPushButton(" 🔄 Restart Backend")
        self.btn_restart_api.setIcon(self._get_icon("refresh-cw"))
        self.btn_restart_api.setProperty("class", "SecondaryButton")
        self.btn_restart_api.clicked.connect(self._restart_backend_server)
        status_row.addWidget(self.btn_restart_api)

        api_layout.addLayout(status_row)

        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(QLabel("API Host:"))
        self.host_input = QLineEdit(config.API_HOST)
        row.addWidget(self.host_input, stretch=2)

        row.addWidget(QLabel("API Port:"))
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1024, 65535)
        self.port_spin.setValue(config.API_PORT)
        row.addWidget(self.port_spin, stretch=1)

        api_layout.addLayout(row)

        api_key_row = QHBoxLayout()
        api_key_row.addWidget(QLabel("Local API Key:"))
        self.api_key_input = QLineEdit(config.API_BEARER_TOKEN)
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("Enter API Token")
        api_key_row.addWidget(self.api_key_input, stretch=1)

        self.btn_toggle_api_key = QPushButton(" Show")
        self.btn_toggle_api_key.setIcon(self._get_icon("eye"))
        self.btn_toggle_api_key.setProperty("class", "SecondaryButton")
        self.btn_toggle_api_key.setFixedWidth(80)
        self.btn_toggle_api_key.clicked.connect(self._toggle_api_key_visibility)
        api_key_row.addWidget(self.btn_toggle_api_key)

        api_layout.addLayout(api_key_row)

        api_btn_row = QHBoxLayout()
        api_btn_row.setSpacing(8)

        self.btn_open_browser = QPushButton(" In externem Browser öffnen")
        self.btn_open_browser.setToolTip("Öffnet die REST-API Endpunkte im Standard-Browser (ohne Token in URL)")
        self.btn_open_browser.setIcon(self._get_icon("external-link"))
        self.btn_open_browser.setProperty("class", "SecondaryButton")
        self.btn_open_browser.clicked.connect(self._open_api_in_browser)
        api_btn_row.addWidget(self.btn_open_browser)

        self.btn_copy_token = QPushButton(" Token kopieren")
        self.btn_copy_token.setToolTip("Kopiert den API-Token in die Zwischenablage (sicherer als URL-Parameter)")
        self.btn_copy_token.setIcon(self._get_icon("copy"))
        self.btn_copy_token.setProperty("class", "SecondaryButton")
        self.btn_copy_token.clicked.connect(self._copy_api_token)
        api_btn_row.addWidget(self.btn_copy_token)

        self.btn_save_api = QPushButton(" Save API Settings")
        self.btn_save_api.setIcon(self._get_icon("check"))
        self.btn_save_api.setProperty("class", "SuccessButton")
        self.btn_save_api.clicked.connect(self._save_api_settings)
        api_btn_row.addWidget(self.btn_save_api)

        api_layout.addLayout(api_btn_row)

        layout.addWidget(api_group)


        layout.addStretch()



    def _toggle_gemini_key_visibility(self):
        if self.gemini_key_input.echoMode() == QLineEdit.EchoMode.Password:
            self.gemini_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.btn_toggle_gemini_key.setText(" Hide")
            self.btn_toggle_gemini_key.setIcon(self._get_icon("eye-off"))
        else:
            self.gemini_key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.btn_toggle_gemini_key.setText(" Show")
            self.btn_toggle_gemini_key.setIcon(self._get_icon("eye"))

    def _toggle_api_key_visibility(self):
        if self.api_key_input.echoMode() == QLineEdit.EchoMode.Password:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.btn_toggle_api_key.setText(" Hide")
            self.btn_toggle_api_key.setIcon(self._get_icon("eye-off"))
        else:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.btn_toggle_api_key.setText(" Show")
            self.btn_toggle_api_key.setIcon(self._get_icon("eye"))

    def _open_api_in_browser(self):
        import webbrowser
        host = self.host_input.text().strip() or "127.0.0.1"
        port = self.port_spin.value() or 59200

        # SECURITY: Token is NOT appended to URL — it would appear in browser
        # history, server access logs, and Referer headers.
        # Use the 'Copy Token' button and paste it manually into your API client.
        url = f"http://{host}:{port}/api/v1"

        # 1. Primary: QDesktopServices (Qt's native system browser launcher)
        opened = QDesktopServices.openUrl(QUrl(url))

        # 2. Secondary: Cross-platform fallback via PlatformHelper
        if not opened:
            from engine.platform_helper import PlatformHelper
            PlatformHelper.open_url(url)

    def _copy_api_token(self):
        """Copies the API token to clipboard — the safe alternative to URL tokens."""
        token = self.api_key_input.text().strip()
        if not token:
            QMessageBox.warning(self, "Kein Token", "Bitte zuerst einen API-Token eingeben und speichern.")
            return
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(token)
            QMessageBox.information(
                self,
                "Token kopiert",
                "API-Token wurde in die Zwischenablage kopiert.\n\n"
                "Verwendung im API-Client:\n"
                "  Header: Authorization: Bearer <TOKEN>\n"
                "  Header: X-API-Key: <TOKEN>"
            )

    def _save_api_settings(self):
        import os
        host = self.host_input.text().strip()
        port = self.port_spin.value()
        api_key = self.api_key_input.text().strip()

        config.API_HOST = host
        config.API_PORT = port
        config.API_BEARER_TOKEN = api_key

        config.save_app_config()
        self._refresh_server_ui()

        # If server is running and settings changed, ask or restart
        from api.server import RestApiServer
        server = RestApiServer.get_instance()
        if server and server.is_running():
            asyncio.create_task(server.restart(host=host, port=port))

        QMessageBox.information(
            self,
            "API Settings Saved",
            f"Local API Server settings saved!\n\n"
            f"Host: {host}\n"
            f"Port: {port}\n"
            f"API Key: {'[HIDDEN]' if api_key else '[NONE]'}"
        )

    def _refresh_server_ui(self):
        from api.server import RestApiServer
        server = RestApiServer.get_instance()
        is_running = server.is_running() if server else False
        host = self.host_input.text().strip() or config.API_HOST
        port = self.port_spin.value() or config.API_PORT

        if is_running:
            self.api_status_lbl.setText(f"🟢 Backend Server: Active (http://{host}:{port})")
            self.api_status_lbl.setStyleSheet("color: #34d399; font-weight: 700; font-size: 12px;")
            self.btn_start_api.setEnabled(False)
            self.btn_stop_api.setEnabled(True)
            self.btn_restart_api.setEnabled(True)
        else:
            self.api_status_lbl.setText(f"⚪ Backend Server: Stopped")
            self.api_status_lbl.setStyleSheet("color: #94a3b8; font-weight: 700; font-size: 12px;")
            self.btn_start_api.setEnabled(True)
            self.btn_stop_api.setEnabled(False)
            self.btn_restart_api.setEnabled(False)

    def _start_backend_server(self):
        self.api_status_lbl.setText("Starting Backend Server...")
        self.api_status_lbl.setStyleSheet("color: #fbbf24; font-weight: 700; font-size: 12px;")
        self.btn_start_api.setEnabled(False)

        async def _run():
            from api.server import RestApiServer
            server = RestApiServer.get_instance()
            host = self.host_input.text().strip() or config.API_HOST
            port = self.port_spin.value() or config.API_PORT
            if server:
                ok = await server.start(host=host, port=port)
            else:
                ok = False
            self._refresh_server_ui()
            if ok:
                QMessageBox.information(self, "Backend Server", f"REST API Server successfully started on http://{host}:{port}")
            else:
                QMessageBox.warning(self, "Backend Server", f"Could not start REST API Server on port {port}.\nPort may be already in use.")

        asyncio.create_task(_run())

    def _stop_backend_server(self):
        self.api_status_lbl.setText("Stopping Backend Server...")
        self.btn_stop_api.setEnabled(False)

        async def _run():
            from api.server import RestApiServer
            server = RestApiServer.get_instance()
            if server:
                await server.stop()
            self._refresh_server_ui()
            QMessageBox.information(self, "Backend Server", "REST API Server stopped.")

        asyncio.create_task(_run())

    def _restart_backend_server(self):
        self.api_status_lbl.setText("Restarting Backend Server...")
        self.btn_restart_api.setEnabled(False)

        async def _run():
            from api.server import RestApiServer
            server = RestApiServer.get_instance()
            host = self.host_input.text().strip() or config.API_HOST
            port = self.port_spin.value() or config.API_PORT
            if server:
                ok = await server.restart(host=host, port=port)
            else:
                ok = False
            self._refresh_server_ui()
            if ok:
                QMessageBox.information(self, "Backend Server", f"REST API Server restarted on http://{host}:{port}")
            else:
                QMessageBox.warning(self, "Backend Server", f"Could not restart REST API Server on port {port}.")

        asyncio.create_task(_run())

    @qasync.asyncSlot()
    async def _test_gemini_connection(self):
        key = self.gemini_key_input.text().strip()
        if not key:
            QMessageBox.warning(self, "Missing API Key", "Please enter a valid Google Gemini API Key first.")
            return

        target_model = self.gemini_model_combo.currentData() or "gemini-3.6-flash"
        self.btn_test_gemini.setText(" Testing...")
        self.btn_test_gemini.setEnabled(False)
        self.gemini_status_lbl.setText(f"Testing connection to Google Gemini ({target_model})...")
        self.gemini_status_lbl.setStyleSheet("color: #fbbf24; font-size: 11px;")

        try:
            from engine.ai_gemini_client import GeminiApiClient
            client = GeminiApiClient.get_instance()
            client.set_api_key(key)
            ok, msg = await client.test_connection(key, model=target_model)

            if ok:
                self.gemini_status_lbl.setText(f"✓ Connected ({target_model})")
                self.gemini_status_lbl.setStyleSheet("color: #34d399; font-weight: 700; font-size: 11px;")
                QMessageBox.information(
                    self,
                    "Gemini API Connected",
                    f"Successfully connected to Google Gemini Cloud API!\n\n"
                    f"{msg}\n\n"
                    f"Status: Active & Ready for Ultra-Fast Captchas & Reasoning."
                )
            else:
                self.gemini_status_lbl.setText(f"✗ Connection Failed: {msg[:40]}")
                self.gemini_status_lbl.setStyleSheet("color: #f87171; font-weight: 700; font-size: 11px;")
                QMessageBox.critical(
                    self,
                    "Gemini API Connection Failed",
                    f"Could not connect to Gemini API:\n\n{msg}"
                )
        except Exception as e:
            err_msg = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
            self.gemini_status_lbl.setText(f"✗ Error: {err_msg[:40]}")
            self.gemini_status_lbl.setStyleSheet("color: #f87171; font-weight: 700; font-size: 11px;")
            QMessageBox.critical(self, "Gemini API Connection Failed", f"Could not connect to Gemini API:\n\n{err_msg}")
        finally:
            self.btn_test_gemini.setText(" Test Gemini Connection")
            self.btn_test_gemini.setEnabled(True)

    def _save_gemini_settings(self):
        import os
        key = self.gemini_key_input.text().strip()
        model = self.gemini_model_combo.currentData() or "gemini-3.6-flash"
        strat = self.gemini_strategy_combo.currentData() or "hybrid_fallback"

        config.GEMINI_API_KEY = key
        config.GEMINI_DEFAULT_MODEL = model
        config.AI_PROVIDER_STRATEGY = strat
        os.environ["GEMINI_API_KEY"] = key

        from engine.ai_gemini_client import GeminiApiClient
        client = GeminiApiClient.get_instance()
        client.set_api_key(key)

        config.save_app_config()

        self.gemini_status_lbl.setText(f"Saved successfully (Strategy: {strat})")
        self.gemini_status_lbl.setStyleSheet("color: #34d399; font-weight: 700; font-size: 11px;")
        QMessageBox.information(
            self,
            "Settings Saved",
            f"Google Gemini API Key and settings saved securely!\n\n"
            f"Model: {model}\n"
            f"Strategy: {strat}\n"
            f"Stored in: Encrypted Vault (AES-256-GCM, Argon2id)"
        )




