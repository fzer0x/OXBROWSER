from typing import Dict, Any, List, Optional, Tuple
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QLineEdit, QComboBox, QCheckBox, QSpinBox, QTextEdit,
    QPushButton, QGroupBox, QFileDialog, QMessageBox, QDoubleSpinBox,
    QScrollArea, QFrame, QApplication, QTableWidget, QTableWidgetItem,
    QHeaderView, QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, QTimer
import qasync
import os
import sys
import random
import config
from storage.profile_manager import ProfileManager
from storage.proxy_manager import ProxyManager
from engine.proxy_checker import ProxyChecker
from engine.cookie_manager import CookieManager
from engine.sandbox import SandboxManager, SandboxInstaller
from engine.account_manager import AccountManager


class AccountEditorDialog(QDialog):
    """Modal dialog for adding or editing account credentials with live TOTP preview."""

    def __init__(self, account_data: Optional[Dict[str, Any]] = None, parent=None):
        super().__init__(parent)
        self.account_data = dict(account_data) if account_data else {}
        self.is_edit = bool(account_data)
        self.setWindowTitle(f"{'Edit Account' if self.is_edit else 'Add New Account'} - {config.APP_NAME}")
        self.resize(580, 600)
        self._init_ui()
        self._load_account()

        self.totp_timer = QTimer(self)
        self.totp_timer.timeout.connect(self._update_totp_preview)
        self.totp_timer.start(1000)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # Platform selector
        plat_row = QHBoxLayout()
        plat_row.addWidget(QLabel("Platform / Service:"))
        self.platform_combo = QComboBox()
        for p_key, p_info in AccountManager.PLATFORMS.items():
            self.platform_combo.addItem(f"{p_info['icon']} {p_info['name']}", p_key)
        self.platform_combo.currentIndexChanged.connect(self._on_platform_changed)
        plat_row.addWidget(self.platform_combo)
        layout.addLayout(plat_row)

        # Account Label / Name
        layout.addWidget(QLabel("Account Label / Description:"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. Main Google Account, IG Bot #1, GitHub Work")
        layout.addWidget(self.name_input)

        # Login URL
        layout.addWidget(QLabel("Login URL:"))
        self.url_input = QLineEdit()
        layout.addWidget(self.url_input)

        # Username / Email
        layout.addWidget(QLabel("Username / Email / Phone:"))
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("e.g. user@gmail.com or @username")
        layout.addWidget(self.user_input)

        # Password with Show/Hide toggle
        layout.addWidget(QLabel("Password:"))
        pass_row = QHBoxLayout()
        self.pass_input = QLineEdit()
        self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pass_input.setPlaceholderText("Account password")
        self.show_pass_btn = QPushButton("👁 Show")
        self.show_pass_btn.setFixedWidth(75)
        self.show_pass_btn.clicked.connect(self._toggle_password_visibility)
        pass_row.addWidget(self.pass_input)
        pass_row.addWidget(self.show_pass_btn)
        layout.addLayout(pass_row)

        # 2FA / TOTP Secret Key with live preview
        layout.addWidget(QLabel("2FA / TOTP Secret Key (Optional - Base32):"))
        self.totp_input = QLineEdit()
        self.totp_input.setPlaceholderText("e.g. JBSWY3DPEHPK3PXP")
        self.totp_input.textChanged.connect(self._update_totp_preview)
        layout.addWidget(self.totp_input)

        self.totp_preview_label = QLabel("🔑 Live 2FA Code: —")
        self.totp_preview_label.setStyleSheet("font-weight: bold; color: #4CAF50; font-size: 13px; margin-left: 2px;")
        layout.addWidget(self.totp_preview_label)

        # Cookies / Session Tokens
        layout.addWidget(QLabel("Session Cookies / Token (Optional JSON or string):"))
        self.cookies_input = QTextEdit()
        self.cookies_input.setMaximumHeight(70)
        self.cookies_input.setPlaceholderText("Optional cookie JSON or session token for instant 1-click authentication")
        layout.addWidget(self.cookies_input)

        # Auto-Login on Launch Checkbox
        self.autologin_cb = QCheckBox("🚀 Auto-Fill & Assist Login on Browser Launch")
        self.autologin_cb.setChecked(False)
        layout.addWidget(self.autologin_cb)

        # Notes
        layout.addWidget(QLabel("Notes (Optional):"))
        self.notes_input = QLineEdit()
        self.notes_input.setPlaceholderText("Optional recovery email, backup codes or notes")
        layout.addWidget(self.notes_input)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "SecondaryButton")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Save Account")
        save_btn.setProperty("class", "PrimaryButton")
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    def _toggle_password_visibility(self):
        if self.pass_input.echoMode() == QLineEdit.EchoMode.Password:
            self.pass_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.show_pass_btn.setText("🔒 Hide")
        else:
            self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.show_pass_btn.setText("👁 Show")

    def _on_platform_changed(self):
        plat_key = self.platform_combo.currentData() or "custom"
        plat_info = AccountManager.get_platform_info(plat_key)
        # Update URL if currently empty or default
        current_url = self.url_input.text().strip()
        if not current_url or any(p.get("login_url") == current_url for p in AccountManager.PLATFORMS.values()):
            self.url_input.setText(plat_info.get("login_url", ""))
        current_name = self.name_input.text().strip()
        if not current_name or any(f"{p['name']} Account" == current_name for p in AccountManager.PLATFORMS.values()):
            self.name_input.setText(f"{plat_info['name']} Account")

    def _update_totp_preview(self):
        secret = self.totp_input.text().strip()
        if not secret:
            self.totp_preview_label.setText("🔑 Live 2FA Code: —")
            self.totp_preview_label.setStyleSheet("color: #888888; font-size: 12px;")
            return
        code, rem = AccountManager.generate_totp_code(secret)
        if code:
            formatted = f"{code[:3]} {code[3:]}"
            self.totp_preview_label.setText(f"🔑 Live 2FA Code: {formatted}  (⏳ {rem}s remaining)")
            self.totp_preview_label.setStyleSheet("font-weight: bold; color: #4CAF50; font-size: 13px;")
        else:
            self.totp_preview_label.setText("⚠️ Invalid Base32 Secret Key")
            self.totp_preview_label.setStyleSheet("color: #FF9800; font-size: 12px;")

    def _load_account(self):
        d = self.account_data
        plat = d.get("platform", "google")
        idx = self.platform_combo.findData(plat)
        if idx >= 0:
            self.platform_combo.setCurrentIndex(idx)
        else:
            self.platform_combo.setCurrentIndex(0)

        plat_info = AccountManager.get_platform_info(plat)
        self.name_input.setText(d.get("name", f"{plat_info['name']} Account"))
        self.url_input.setText(d.get("login_url", plat_info.get("login_url", "")))
        self.user_input.setText(d.get("username", ""))
        self.pass_input.setText(d.get("password", ""))
        self.totp_input.setText(d.get("totp_secret", ""))
        self.cookies_input.setPlainText(d.get("cookies", ""))
        self.autologin_cb.setChecked(bool(d.get("auto_login_on_launch", False)))
        self.notes_input.setText(d.get("notes", ""))
        self._update_totp_preview()

    def _save(self):
        user = self.user_input.text().strip()
        pwd = self.pass_input.text().strip()
        if not user and not pwd and not self.cookies_input.toPlainText().strip():
            QMessageBox.warning(self, "Validation Error", "Please enter at least a username/email, password, or session cookies.")
            return

        plat = self.platform_combo.currentData() or "custom"
        self.account_data = AccountManager.create_account_record(
            platform=plat,
            username=user,
            password=pwd,
            name=self.name_input.text().strip(),
            totp_secret=self.totp_input.text().strip(),
            login_url=self.url_input.text().strip(),
            cookies=self.cookies_input.toPlainText().strip(),
            auto_login_on_launch=self.autologin_cb.isChecked(),
            notes=self.notes_input.text().strip()
        )
        if self.is_edit and self.account_data.get("id"):
            self.account_data["id"] = self.account_data.get("id")

        self.accept()

    def get_account_data(self) -> Dict[str, Any]:
        return self.account_data


class BatchImportAccountsDialog(QDialog):
    """Dialog for bulk credential import."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Batch Import Accounts - {config.APP_NAME}")
        self.resize(640, 500)
        self.imported_accounts: List[Dict[str, Any]] = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        layout.addWidget(QLabel("<b>Batch Import Account Credentials:</b>"))
        desc = QLabel(
            "Paste credentials in any of the following formats (one per line):<br>"
            "• <code>platform:username:password:totp_secret</code><br>"
            "• <code>platform:username:password</code><br>"
            "• <code>username:password:totp_secret</code><br>"
            "• <code>username:password</code> (separated by <code>:</code>, <code>|</code>, or <code>;</code>)<br>"
            "• JSON Array of account objects"
        )
        desc.setStyleSheet("color: #AAAAAA; font-size: 11px;")
        layout.addWidget(desc)

        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText(
            "Examples:\n"
            "google:user@gmail.com:MyPassword123:JBSWY3DPEHPK3PXP\n"
            "instagram:insta_growth_bot:MySecretPass!\n"
            "github:developer_acc:Pass987654:JBSWY3DPEHPK3PXP\n"
            "tiktok:tiktok_creator:DancePass2026\n"
            "twitter:x_user:TwitterSecret\n"
            "discord:chat_bot@gmail.com:DiscordPass1"
        )
        layout.addWidget(self.text_input)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "SecondaryButton")
        cancel_btn.clicked.connect(self.reject)
        import_btn = QPushButton("📥 Import Accounts")
        import_btn.setProperty("class", "PrimaryButton")
        import_btn.clicked.connect(self._do_import)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(import_btn)
        layout.addLayout(btn_layout)

    def _do_import(self):
        txt = self.text_input.toPlainText().strip()
        if not txt:
            QMessageBox.warning(self, "Import Error", "Please paste account credentials.")
            return

        res = AccountManager.parse_batch_credentials(txt)
        if not res:
            QMessageBox.warning(self, "Import Error", "Could not parse any accounts. Please check the format.")
            return

        self.imported_accounts = res
        QMessageBox.information(self, "Import Successful", f"Successfully parsed {len(res)} account(s).")
        self.accept()

    def get_accounts(self) -> List[Dict[str, Any]]:
        return self.imported_accounts


class ProfileDialog(QDialog):
    """High-Configurator Anti-Detect Profile Editor Dialog."""

    def __init__(self, profile_manager: ProfileManager, profile_data: dict | None = None, launcher=None, proxy_manager: Optional[ProxyManager] = None, parent=None):
        super().__init__(parent)
        self.profile_manager = profile_manager
        self.launcher = launcher
        self.proxy_manager = proxy_manager or ProxyManager()
        self.is_edit = profile_data is not None
        self._selected_proxy_id: Optional[str] = None
        self._populating_proxy_combo: bool = False
        self._updating_proxy_fields: bool = False

        if profile_data is not None:
            self.profile_data: dict = profile_data
        else:
            self.profile_data: dict = self.profile_manager.create_default_profile_data()

        self.loaded_cookies: list = []
        self.loaded_accounts: list = []
        self.setWindowTitle(f"{'Edit Profile' if self.is_edit else 'Create New Profile'} - {config.APP_NAME}")
        self.resize(1180, 870)
        self.setMinimumSize(780, 620)
        self._init_ui()
        self._load_data()

        # Timer to refresh live TOTP 2FA codes in accounts table
        self.totp_table_timer = QTimer(self)
        self.totp_table_timer.timeout.connect(self._update_live_totp_display)
        self.totp_table_timer.start(1000)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(14)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Tab 1: Overview
        self.tabs.addTab(self._create_general_tab(), "Overview")
        # Tab 2: Proxy & Geolocation
        self.tabs.addTab(self._create_proxy_geo_tab(), "Proxy & Location")
        # Tab 3: Hardware & Device
        self.tabs.addTab(self._create_hardware_tab(), "Hardware & Device")
        # Tab 4: Fingerprint & Stealth
        self.tabs.addTab(self._create_stealth_tab(), "Stealth & Fingerprint")
        # Tab 5: Timezone & Language
        self.tabs.addTab(self._create_tz_lang_tab(), "Timezone & Language")
        # Tab 6: Cookies & Extensions
        self.tabs.addTab(self._create_storage_tab(), "Cookies & Extensions")
        # Tab 7: Accounts & Logins (Google, Instagram, GitHub, TikTok, etc.)
        self.tabs.addTab(self._create_accounts_tab(), "Accounts & Logins")
        # Tab 8: Behavior & Privacy (History, Autofill, Cache)
        self.tabs.addTab(self._create_behavior_tab(), "Behavior & Privacy")
        # Tab 9: Sandbox & MicroVM Hardware
        self.tabs.addTab(self._create_sandbox_tab(), "Sandbox & MicroVM")

        self.tabs.currentChanged.connect(lambda idx: self._update_fingerprint_preview())

        # Bottom Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "SecondaryButton")
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("Save Profile")
        save_btn.setProperty("class", "PrimaryButton")
        save_btn.clicked.connect(self._save_and_accept)

        if self.launcher:
            save_launch_btn = QPushButton("▶ Save & Launch Browser")
            save_launch_btn.setProperty("class", "SuccessButton")
            save_launch_btn.clicked.connect(self._save_and_launch)
            btn_layout.addWidget(save_launch_btn)

        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        main_layout.addLayout(btn_layout)

    def _create_general_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(QLabel("Profile Name:"))
        self.name_input = QLineEdit()
        layout.addWidget(self.name_input)

        self.engine_combo = QComboBox()
        self.engine_combo.addItem("⍝ Camoufox (C++ Native Engine - Primary Default)", "camoufox")
        self.engine_combo.addItem("⭍ Playwright (Async Engine - Optional)", "playwright")
        self.engine_combo.addItem("⛟ Selenium Driverless (Optional)", "selenium_driverless")
        self.engine_combo.addItem("⫸ Nodriver (Stealth CDP Engine - Optional)", "nodriver")
        self.engine_combo.currentIndexChanged.connect(lambda: self._on_engine_changed())
        layout.addWidget(self.engine_combo)

        layout.addWidget(QLabel("Group / Folder:"))
        self.group_input = QLineEdit()
        layout.addWidget(self.group_input)

        layout.addWidget(QLabel("Tags (comma separated):"))
        self.tags_input = QLineEdit()
        layout.addWidget(self.tags_input)

        layout.addWidget(QLabel("Start URL / Homepage:"))
        self.start_url_input = QLineEdit()
        self.start_url_input.setPlaceholderText("e.g. https://google.com (optional)")
        layout.addWidget(self.start_url_input)

        # Quick Accounts & Auto-Login Section directly on Overview Tab
        acc_box = QGroupBox("🔑 Connected Accounts & Auto-Login (Google, Instagram, TikTok, GitHub...)")
        acc_layout = QVBoxLayout(acc_box)
        acc_layout.setSpacing(8)

        acc_sublabel = QLabel("Quick-Add social & platform credentials for automated 1-click stealth login:")
        acc_sublabel.setStyleSheet("color: #94a3b8; font-size: 11px;")
        acc_layout.addWidget(acc_sublabel)

        acc_quick_row = QHBoxLayout()
        acc_quick_row.setSpacing(6)
        for pk, title in [("google", "🌐 Google"), ("instagram", "📸 Instagram"), ("github", "🐙 GitHub"), ("tiktok", "🎵 TikTok"), ("twitter", "🐦 Twitter/X"), ("spotify", "🟢 Spotify"), ("custom", "➕ Custom")]:
            btn = QPushButton(title)
            btn.setProperty("class", "SecondaryButton")
            btn.setFixedHeight(26)
            btn.clicked.connect(lambda _, k=pk: self._quick_add_account(k))
            acc_quick_row.addWidget(btn)
        acc_quick_row.addStretch()
        acc_layout.addLayout(acc_quick_row)

        acc_manage_row = QHBoxLayout()
        self.overview_acc_summary_label = QLabel("No accounts configured yet.")
        self.overview_acc_summary_label.setStyleSheet("font-weight: 700; color: #38bdf8; font-size: 12px;")
        acc_manage_row.addWidget(self.overview_acc_summary_label)
        acc_manage_row.addStretch()
        open_acc_tab_btn = QPushButton("➔ Open Full Accounts & 2FA Manager Tab")
        open_acc_tab_btn.setProperty("class", "PrimaryButton")
        open_acc_tab_btn.setFixedHeight(26)
        open_acc_tab_btn.clicked.connect(lambda: self.tabs.setCurrentIndex(6))
        acc_manage_row.addWidget(open_acc_tab_btn)
        acc_layout.addLayout(acc_manage_row)

        layout.addWidget(acc_box)

        layout.addWidget(QLabel("Notes:"))
        self.notes_input = QTextEdit()
        layout.addWidget(self.notes_input)

        return widget

    def _create_proxy_geo_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.proxy_enable_cb = QCheckBox("Enable Proxy Connection")
        self.proxy_enable_cb.toggled.connect(self._on_proxy_enable_toggled)
        layout.addWidget(self.proxy_enable_cb)

        self.proxy_group = QGroupBox("Proxy Connection Details")
        form_layout = QVBoxLayout(self.proxy_group)

        # Proxy Pool Selection Row
        pool_row = QHBoxLayout()
        self.lbl_proxy_pool = QLabel("Select from Proxy Pool:")
        self.lbl_proxy_pool.setStyleSheet("font-weight: 600; color: #38bdf8;")
        pool_row.addWidget(self.lbl_proxy_pool)

        self.proxy_pool_combo = QComboBox()
        self.proxy_pool_combo.setMinimumWidth(340)
        self.proxy_pool_combo.currentIndexChanged.connect(self._on_proxy_pool_selection_changed)
        pool_row.addWidget(self.proxy_pool_combo, 1)

        self.btn_refresh_proxies = QPushButton("⟳ Refresh")
        self.btn_refresh_proxies.setToolTip("Reload proxies and active profile assignments from Proxy Pool")
        self.btn_refresh_proxies.setProperty("class", "SecondaryButton")
        self.btn_refresh_proxies.clicked.connect(self._on_refresh_proxies_clicked)
        pool_row.addWidget(self.btn_refresh_proxies)

        form_layout.addLayout(pool_row)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Type:"))
        self.proxy_type_combo = QComboBox()
        self.proxy_type_combo.addItems(["http", "socks5"])
        row1.addWidget(self.proxy_type_combo)

        row1.addWidget(QLabel("Host:"))
        self.proxy_host_input = QLineEdit()
        self.proxy_host_input.setPlaceholderText("e.g. 192.168.1.1 or proxy.com")
        row1.addWidget(self.proxy_host_input)

        row1.addWidget(QLabel("Port:"))
        self.proxy_port_spin = QSpinBox()
        self.proxy_port_spin.setRange(1, 65535)
        self.proxy_port_spin.setValue(8080)
        row1.addWidget(self.proxy_port_spin)
        form_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Username:"))
        self.proxy_user_input = QLineEdit()
        self.proxy_user_input.setPlaceholderText("Optional")
        row2.addWidget(self.proxy_user_input)

        row2.addWidget(QLabel("Password:"))
        self.proxy_pass_input = QLineEdit()
        self.proxy_pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.proxy_pass_input.setPlaceholderText("Optional")
        row2.addWidget(self.proxy_pass_input)
        form_layout.addLayout(row2)

        # Track manual edits to switch combo selection to Custom / Manual
        self.proxy_host_input.textChanged.connect(self._on_manual_proxy_field_edited)
        self.proxy_port_spin.valueChanged.connect(self._on_manual_proxy_field_edited)
        self.proxy_user_input.textChanged.connect(self._on_manual_proxy_field_edited)
        self.proxy_pass_input.textChanged.connect(self._on_manual_proxy_field_edited)
        self.proxy_type_combo.currentIndexChanged.connect(self._on_manual_proxy_field_edited)

        # Sync options
        self.auto_tz_cb = QCheckBox("Auto-Sync Timezone to Proxy IP Location")
        self.auto_lang_cb = QCheckBox("Auto-Sync Languages & Locale to Proxy IP Location")
        self.auto_geo_cb = QCheckBox("Auto-Sync Geolocation (Lat/Lon) to Proxy IP Location")
        self.auto_tz_cb.setChecked(True)
        self.auto_lang_cb.setChecked(True)
        self.auto_geo_cb.setChecked(True)
        self.killswitch_cb = QCheckBox("Enforce NetNS Egress Kill Switch (Block non-proxy traffic)")
        self.killswitch_cb.setToolTip("Creates an isolated Linux Network Namespace with nftables/iptables drop rules. Prevents IP leaks if proxy drops.")

        # Burst Protection & Anti-Rate-Limit Pacing
        burst_row = QHBoxLayout()
        self.burst_prot_cb = QCheckBox("⛊ Enable Proxy Burst Protection (Anti-429 Rate-Limit Micro-Staggering)")
        self.burst_prot_cb.setChecked(True)
        self.burst_prot_cb.setToolTip("Staggers rapid parallel TCP handshakes by a few milliseconds to prevent upstream proxy 429 rate limit drops.")
        burst_row.addWidget(self.burst_prot_cb)

        burst_row.addWidget(QLabel("Interval (ms):"))
        self.burst_ms_spin = QSpinBox()
        self.burst_ms_spin.setRange(0, 500)
        self.burst_ms_spin.setValue(20)
        self.burst_ms_spin.setSuffix(" ms")
        self.burst_ms_spin.setToolTip("Delay spacing between concurrent handshakes (default 20ms).")
        burst_row.addWidget(self.burst_ms_spin)
        
        form_layout.addWidget(self.auto_tz_cb)
        form_layout.addWidget(self.auto_lang_cb)
        form_layout.addWidget(self.auto_geo_cb)
        form_layout.addWidget(self.killswitch_cb)
        form_layout.addLayout(burst_row)

        # TLS JA3/JA4 Fingerprint Impersonation Preset
        tls_row = QHBoxLayout()
        tls_row.addWidget(QLabel("TLS (JA3/JA4) Impersonation:"))
        self.tls_preset_combo = QComboBox()
        self.tls_preset_combo.addItem("⛿ Auto (Match Target OS & Hardware)", "auto")
        self.tls_preset_combo.addItem("⭍ Chrome 131 / Edge 131 (Windows 11)", "chrome_131_win11")
        self.tls_preset_combo.addItem("⍝ Firefox 130 / Camoufox (Windows 11)", "firefox_130_win11")
        self.tls_preset_combo.addItem("〰 Microsoft Edge 131 (Windows 11)", "edge_131_win11")
        self.tls_preset_combo.addItem("[Apple] Chrome 131 (macOS / Apple Silicon M1-M3)", "chrome_131_mac")
        self.tls_preset_combo.addItem("[Apple] Safari 17 / 18 (macOS Sonoma)", "safari_17_mac")
        self.tls_preset_combo.addItem("⍟ Chrome 131 (Linux x86_64 / Mesa)", "chrome_131_linux")
        self.tls_preset_combo.addItem("⍝ Firefox 130 (Linux x86_64)", "firefox_130_linux")
        self.tls_preset_combo.addItem("[Mobile] Chrome Mobile 131 (Android 14 / Pixel 8)", "chrome_android_pixel8")
        self.tls_preset_combo.addItem("[Mobile] Mobile Safari 17.4 (iOS 17 / iPhone 15 Pro)", "safari_ios_iphone")
        self.tls_preset_combo.addItem("⭍ Chrome 120 (Legacy Win11)", "chrome_120_win11")
        tls_row.addWidget(self.tls_preset_combo)
        form_layout.addLayout(tls_row)

        # Check Proxy Button & Info Box
        check_btn_layout = QHBoxLayout()
        self.check_proxy_btn = QPushButton("Check Connection & Fetch IP Info")
        self.check_proxy_btn.setProperty("class", "SecondaryButton")
        self.check_proxy_btn.clicked.connect(self._on_check_proxy_clicked)
        check_btn_layout.addWidget(self.check_proxy_btn)
        form_layout.addLayout(check_btn_layout)

        self.proxy_info_label = QLabel("Proxy Status: Not Tested")
        self.proxy_info_label.setWordWrap(True)
        form_layout.addWidget(self.proxy_info_label)

        layout.addWidget(self.proxy_group)

        # Custom Geolocation Box
        geo_box = QGroupBox("Custom Location & Geolocation Overrides")
        geo_layout = QVBoxLayout(geo_box)

        geo_row1 = QHBoxLayout()
        geo_row1.addWidget(QLabel("Country:"))
        self.geo_country_input = QLineEdit()
        self.geo_country_input.setPlaceholderText("e.g. France")
        geo_row1.addWidget(self.geo_country_input)

        geo_row1.addWidget(QLabel("Region:"))
        self.geo_region_input = QLineEdit()
        self.geo_region_input.setPlaceholderText("e.g. Ile-de-France")
        geo_row1.addWidget(self.geo_region_input)

        geo_row1.addWidget(QLabel("City:"))
        self.geo_city_input = QLineEdit()
        self.geo_city_input.setPlaceholderText("e.g. Paris")
        geo_row1.addWidget(self.geo_city_input)
        geo_layout.addLayout(geo_row1)

        geo_row2 = QHBoxLayout()
        geo_row2.addWidget(QLabel("Postal Code:"))
        self.geo_zip_input = QLineEdit()
        self.geo_zip_input.setPlaceholderText("e.g. 75000")
        geo_row2.addWidget(self.geo_zip_input)

        geo_row2.addWidget(QLabel("Latitude:"))
        self.geo_lat_spin = QDoubleSpinBox()
        self.geo_lat_spin.setRange(-90.0, 90.0)
        self.geo_lat_spin.setDecimals(6)
        geo_row2.addWidget(self.geo_lat_spin)

        geo_row2.addWidget(QLabel("Longitude:"))
        self.geo_lon_spin = QDoubleSpinBox()
        self.geo_lon_spin.setRange(-180.0, 180.0)
        self.geo_lon_spin.setDecimals(6)
        geo_row2.addWidget(self.geo_lon_spin)
        geo_layout.addLayout(geo_row2)

        layout.addWidget(geo_box)
        layout.addStretch()
        return widget

    def _on_proxy_enable_toggled(self, enabled: bool):
        self.proxy_group.setEnabled(enabled)
        from engine.browser import get_system_timezone
        sys_tz = get_system_timezone()
        if hasattr(self, "tz_combo"):
            if enabled:
                self.tz_combo.setItemText(0, "⛿ Auto-Detect from Proxy IP")
                self.auto_tz_cb.setEnabled(True)
                self.auto_lang_cb.setEnabled(True)
                self.auto_geo_cb.setEnabled(True)
            else:
                self.tz_combo.setItemText(0, f"⛿ Auto-Detect System Timezone ({sys_tz})")
                self.auto_tz_cb.setEnabled(False)
                self.auto_lang_cb.setEnabled(False)
                self.auto_geo_cb.setEnabled(False)
        self._update_fingerprint_preview()

    @qasync.asyncSlot()
    async def _on_check_proxy_clicked(self):
        proxy_cfg = self._get_proxy_config_from_ui()

        self.proxy_info_label.setText("Checking proxy connection...")
        self.check_proxy_btn.setEnabled(False)

        success, info, latency = await ProxyChecker.check_proxy(proxy_cfg)
        self.check_proxy_btn.setEnabled(True)

        if success:
            self.profile_data["proxy_info"] = info
            from engine.geo_ip_aligner import GeoIPAligner
            geo_align = GeoIPAligner.align_from_proxy_info(info)

            self.proxy_info_label.setText(
                f"✓ Connected! IP: {info.get('ip')} | Country: {info.get('country')} ({info.get('country_code')}) | "
                f"City: {info.get('city')} | Lat/Lon: {info.get('lat')}, {info.get('lon')} | Timezone: {info.get('timezone')} | Latency: {latency} ms"
            )
            if self.auto_tz_cb.isChecked() and hasattr(self, "tz_combo"):
                self.tz_combo.blockSignals(True)
                self.tz_combo.setCurrentIndex(0)
                self.tz_combo.blockSignals(False)
            if self.auto_lang_cb.isChecked() and hasattr(self, "lang_input"):
                self.lang_input.setText(geo_align.accept_language)
            if self.auto_geo_cb.isChecked():
                self.geo_country_input.setText(info.get("country", ""))
                self.geo_city_input.setText(info.get("city", ""))
                self.geo_lat_spin.setValue(float(info.get("lat", 0.0)))
                self.geo_lon_spin.setValue(float(info.get("lon", 0.0)))
        else:
            err = info.get("error", "Failed")
            self.proxy_info_label.setText(f" Proxy Error: {err} ({latency} ms)")

    def _get_proxy_config_from_ui(self) -> dict:
        auto_tz_val = self.auto_tz_cb.isChecked() if hasattr(self, "auto_tz_cb") else True
        cfg = {
            "enabled": self.proxy_enable_cb.isChecked(),
            "type": self.proxy_type_combo.currentText(),
            "host": self.proxy_host_input.text().strip(),
            "port": self.proxy_port_spin.value(),
            "username": self.proxy_user_input.text().strip(),
            "password": self.proxy_pass_input.text().strip(),
            "auto_timezone": auto_tz_val,
            "auto_language": self.auto_lang_cb.isChecked(),
            "auto_geolocation": self.auto_geo_cb.isChecked(),
            "burst_protection": self.burst_prot_cb.isChecked(),
            "burst_stagger_ms": self.burst_ms_spin.value()
        }
        if getattr(self, "_selected_proxy_id", None):
            cfg["proxy_id"] = self._selected_proxy_id
        return cfg

    def _get_used_proxies(self) -> Dict[Any, str]:
        """Returns mapping of (host, port) and proxy_id to profile name for currently configured profiles."""
        used = {}
        try:
            current_pid = self.profile_data.get("id") if self.is_edit else None
            for prof in self.profile_manager.list_profiles():
                pid = prof.get("id")
                if current_pid and pid == current_pid:
                    continue
                p_cfg = prof.get("proxy", {})
                if not p_cfg or not p_cfg.get("enabled", False):
                    continue
                host = str(p_cfg.get("host", "")).strip().lower()
                port = p_cfg.get("port")
                prof_name = prof.get("name") or (pid[:8] if pid else "Profile")
                if host and port:
                    try:
                        used[(host, int(port))] = prof_name
                    except (ValueError, TypeError):
                        pass
                p_id = p_cfg.get("proxy_id")
                if p_id:
                    used[p_id] = prof_name
        except Exception:
            pass
        return used

    def _apply_proxy_to_inputs(self, proxy: dict):
        self._updating_proxy_fields = True
        try:
            self._selected_proxy_id = proxy.get("id", "")
            p_type = str(proxy.get("type", "http")).lower()
            idx = self.proxy_type_combo.findText(p_type)
            if idx >= 0:
                self.proxy_type_combo.setCurrentIndex(idx)
            else:
                self.proxy_type_combo.setCurrentText(p_type)

            self.proxy_host_input.setText(str(proxy.get("host", "")))
            self.proxy_port_spin.setValue(int(proxy.get("port", 8080)))
            self.proxy_user_input.setText(str(proxy.get("username", "")))
            self.proxy_pass_input.setText(str(proxy.get("password", "")))

            # If proxy has location info, pre-fill custom geolocation fields if empty
            country = proxy.get("country", "")
            city = proxy.get("city", "")
            if country and hasattr(self, "geo_country_input") and not self.geo_country_input.text().strip():
                self.geo_country_input.setText(country)
            if city and hasattr(self, "geo_city_input") and not self.geo_city_input.text().strip():
                self.geo_city_input.setText(city)

            # Update proxy info label
            status = proxy.get("status", "Untested")
            lat = proxy.get("latency_ms", -1)
            lat_str = f"{lat:.1f}ms" if isinstance(lat, (int, float)) and lat > 0 else "N/A"
            country_str = country or "Unknown"
            self.proxy_info_label.setText(
                f"Proxy: {proxy.get('host')}:{proxy.get('port')} | Location: {country_str} | Status: {status} | Latency: {lat_str}"
            )
            if "Active" in status or "✓" in status:
                self.proxy_info_label.setStyleSheet("color: #4ade80; font-weight: 500;")
            elif "Offline" in status:
                self.proxy_info_label.setStyleSheet("color: #f87171; font-weight: 500;")
            else:
                self.proxy_info_label.setStyleSheet("color: #94a3b8;")
        finally:
            self._updating_proxy_fields = False

    def _on_proxy_pool_selection_changed(self, index: int):
        if getattr(self, "_populating_proxy_combo", False) or getattr(self, "_updating_proxy_fields", False):
            return
        if index < 0:
            return
        item_data = self.proxy_pool_combo.itemData(index)
        if not isinstance(item_data, dict):
            return

        mode = item_data.get("mode")
        if mode == "auto_unused":
            proxy = item_data.get("proxy")
            if proxy:
                self._apply_proxy_to_inputs(proxy)
                self.proxy_enable_cb.setChecked(True)
        elif mode == "specific":
            proxy = item_data.get("proxy")
            if proxy:
                self._apply_proxy_to_inputs(proxy)
                self.proxy_enable_cb.setChecked(True)
        elif mode == "manual":
            self._selected_proxy_id = None
            self.proxy_enable_cb.setChecked(True)
            self.proxy_info_label.setText("Proxy Status: Manual Configuration")
            self.proxy_info_label.setStyleSheet("color: #94a3b8;")
        elif mode == "none":
            self._selected_proxy_id = None
            self.proxy_enable_cb.setChecked(False)
            self.proxy_info_label.setText("Proxy Status: Disabled (Direct Connection)")
            self.proxy_info_label.setStyleSheet("color: #94a3b8;")

    def _on_refresh_proxies_clicked(self):
        self._populate_proxy_pool_combo()

    def _on_manual_proxy_field_edited(self):
        if getattr(self, "_updating_proxy_fields", False) or getattr(self, "_populating_proxy_combo", False):
            return
        cur_data = self.proxy_pool_combo.currentData()
        if cur_data and cur_data.get("mode") in ("specific", "auto_unused"):
            proxy = cur_data.get("proxy")
            if proxy:
                cur_host = self.proxy_host_input.text().strip()
                cur_port = self.proxy_port_spin.value()
                cur_user = self.proxy_user_input.text().strip()
                cur_pass = self.proxy_pass_input.text().strip()
                cur_type = self.proxy_type_combo.currentText().lower()
                if (str(proxy.get("host", "")).strip().lower() != cur_host.lower() or
                    int(proxy.get("port", 0)) != cur_port or
                    str(proxy.get("username", "")).strip() != cur_user or
                    str(proxy.get("password", "")).strip() != cur_pass or
                    str(proxy.get("type", "http")).lower() != cur_type):
                    self._selected_proxy_id = None
                    self._select_combo_mode("manual")

    def _select_combo_mode(self, mode: str):
        for i in range(self.proxy_pool_combo.count()):
            d = self.proxy_pool_combo.itemData(i)
            if isinstance(d, dict) and d.get("mode") == mode:
                self._populating_proxy_combo = True
                try:
                    self.proxy_pool_combo.setCurrentIndex(i)
                finally:
                    self._populating_proxy_combo = False
                break

    def _populate_proxy_pool_combo(self):
        self._populating_proxy_combo = True
        try:
            self.proxy_pool_combo.clear()
            pool_proxies = self.proxy_manager.list_proxies(sort_speed=True)
            used_map = self._get_used_proxies()

            unused_proxies = []
            used_proxies = []
            for p in pool_proxies:
                h = str(p.get("host", "")).strip().lower()
                prt = int(p.get("port", 0))
                pid = p.get("id", "")
                if (h, prt) in used_map or pid in used_map:
                    pname = used_map.get((h, prt)) or used_map.get(pid)
                    used_proxies.append((p, pname))
                else:
                    unused_proxies.append(p)

            # 1. Auto Option (Item 0)
            if unused_proxies:
                best_proxy = unused_proxies[0]
                loc_txt = best_proxy.get("country") or "Pool"
                auto_title = f"⚡ Auto: Unused Proxy ({best_proxy.get('host')}:{best_proxy.get('port')} - {loc_txt})"
                auto_data = {"mode": "auto_unused", "proxy": best_proxy}
            elif pool_proxies:
                best_proxy = pool_proxies[0]
                auto_title = f"⚡ Auto: Next Available ({best_proxy.get('host')}:{best_proxy.get('port')} - All in use)"
                auto_data = {"mode": "auto_unused", "proxy": best_proxy}
            else:
                best_proxy = None
                auto_title = "⚡ Auto: No Proxies in Pool"
                auto_data = {"mode": "auto_unused", "proxy": None}

            self.proxy_pool_combo.addItem(auto_title, auto_data)
            self.proxy_pool_combo.insertSeparator(self.proxy_pool_combo.count())

            # 2. Individual Pool Proxies
            for p in pool_proxies:
                h = str(p.get("host", "")).strip()
                prt = p.get("port", 8080)
                ptype = str(p.get("type", "http")).upper()
                pcountry = p.get("country") or "Unknown"
                pname = p.get("name") or f"{h}:{prt}"

                h_lower = h.lower()
                is_used = False
                used_by_prof = ""
                if (h_lower, int(prt)) in used_map:
                    is_used = True
                    used_by_prof = used_map[(h_lower, int(prt))]
                elif p.get("id", "") in used_map:
                    is_used = True
                    used_by_prof = used_map[p.get("id", "")]

                if is_used:
                    title = f"🔴 {pname} ({ptype}) - {pcountry} [In Use: {used_by_prof}]"
                else:
                    title = f"🟢 {pname} ({ptype}) - {pcountry} [Available]"

                self.proxy_pool_combo.addItem(title, {"mode": "specific", "proxy": p})

            self.proxy_pool_combo.insertSeparator(self.proxy_pool_combo.count())

            # 3. Manual & No Proxy Options
            self.proxy_pool_combo.addItem("✏️ Custom / Manual Proxy", {"mode": "manual", "proxy": None})
            self.proxy_pool_combo.addItem("🚫 No Proxy (Direct Connection)", {"mode": "none", "proxy": None})

            # Update stats label
            self.lbl_proxy_pool.setText(f"Select from Proxy Pool ({len(unused_proxies)}/{len(pool_proxies)} available):")

            # 4. Determine initial selection
            if not self.is_edit:
                # New Profile default: Auto-assign unused proxy
                self.proxy_pool_combo.setCurrentIndex(0)
                if best_proxy:
                    self._apply_proxy_to_inputs(best_proxy)
                    self.proxy_enable_cb.setChecked(True)
                else:
                    self.proxy_enable_cb.setChecked(False)
            else:
                # Existing Profile: match current proxy
                cur_p = self.profile_data.get("proxy", {})
                if not cur_p.get("enabled", False):
                    self._select_combo_mode("none")
                else:
                    cur_host = str(cur_p.get("host", "")).strip().lower()
                    cur_port = cur_p.get("port")
                    cur_pid = cur_p.get("proxy_id")
                    matched_idx = -1
                    if cur_host and cur_port:
                        for idx in range(self.proxy_pool_combo.count()):
                            it = self.proxy_pool_combo.itemData(idx)
                            if it and it.get("mode") == "specific":
                                p_obj = it.get("proxy", {})
                                if ((cur_pid and p_obj.get("id") == cur_pid) or
                                    (str(p_obj.get("host", "")).strip().lower() == cur_host and int(p_obj.get("port", 0)) == int(cur_port))):
                                    matched_idx = idx
                                    break
                    if matched_idx >= 0:
                        self.proxy_pool_combo.setCurrentIndex(matched_idx)
                        cur_p_obj = self.proxy_pool_combo.itemData(matched_idx).get("proxy", {})
                        self._selected_proxy_id = cur_p_obj.get("id")
                    else:
                        self._select_combo_mode("manual")
        finally:
            self._populating_proxy_combo = False

    def _create_hardware_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Operating System:"))
        self.os_combo = QComboBox()
        self.os_combo.addItems(["windows", "mac", "linux", "android", "ios"])
        self.os_combo.currentTextChanged.connect(self._on_os_changed)
        row1.addWidget(self.os_combo)

        row1.addWidget(QLabel("Device Vendor:"))
        self.device_vendor_input = QLineEdit()
        self.device_vendor_input.setPlaceholderText("e.g. Apple / Google / Dell")
        row1.addWidget(self.device_vendor_input)

        row1.addWidget(QLabel("Device Model:"))
        self.device_model_input = QLineEdit()
        self.device_model_input.setPlaceholderText("e.g. Macintosh / PC / Pixel 8")
        row1.addWidget(self.device_model_input)
        layout.addLayout(row1)

        ua_layout = QHBoxLayout()
        self.custom_ua_cb = QCheckBox("Custom User-Agent (Override):")
        self.custom_ua_cb.setToolTip("When unchecked, Camoufox/Browser auto-generates a perfectly matched native User-Agent for the selected OS.")
        self.custom_ua_cb.toggled.connect(self._toggle_custom_ua)
        ua_layout.addWidget(self.custom_ua_cb)

        self.generate_ua_btn = QPushButton("⚄ Generate New UA")
        self.generate_ua_btn.setProperty("class", "SecondaryButton")
        self.generate_ua_btn.clicked.connect(self._generate_random_ua)
        ua_layout.addWidget(self.generate_ua_btn)
        layout.addLayout(ua_layout)

        self.ua_input = QLineEdit()
        self.ua_input.setPlaceholderText("Auto-generated natively by Camoufox / Browser Engine")
        layout.addWidget(self.ua_input)
        self._toggle_custom_ua(False)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Screen Resolution:"))
        self.res_combo = QComboBox()
        self.res_combo.addItems(config.SCREEN_RESOLUTIONS)
        row2.addWidget(self.res_combo)

        row2.addWidget(QLabel("Color Depth:"))
        self.color_depth_combo = QComboBox()
        self.color_depth_combo.addItems(["24", "30", "32"])
        row2.addWidget(self.color_depth_combo)

        row2.addWidget(QLabel("Max Touch Points:"))
        self.touch_points_spin = QSpinBox()
        self.touch_points_spin.setRange(0, 10)
        row2.addWidget(self.touch_points_spin)
        layout.addLayout(row2)

        hw_layout = QHBoxLayout()
        hw_layout.addWidget(QLabel("CPU Cores (Concurrency):"))
        self.cpu_spin = QSpinBox()
        self.cpu_spin.setRange(2, 64)
        hw_layout.addWidget(self.cpu_spin)

        hw_layout.addWidget(QLabel("RAM (Device Memory GB):"))
        self.ram_spin = QSpinBox()
        self.ram_spin.setRange(2, 128)
        hw_layout.addWidget(self.ram_spin)
        layout.addLayout(hw_layout)

        # Window & Startup Geometry Setup Box
        win_group = QGroupBox("Window Dimensions & Startup Position Setup")
        win_layout = QVBoxLayout(win_group)

        win_row1 = QHBoxLayout()
        win_row1.addWidget(QLabel("Window Mode:"))
        self.win_mode_combo = QComboBox()
        self.win_mode_combo.addItem("Auto Grid Tile Layout", "tile_grid")
        self.win_mode_combo.addItem("Custom Fixed Dimensions", "custom")
        self.win_mode_combo.addItem("Fullscreen / Maximize", "fullscreen")
        win_row1.addWidget(self.win_mode_combo)

        win_row1.addWidget(QLabel("Width (px):"))
        self.win_width_spin = QSpinBox()
        self.win_width_spin.setRange(400, 3840)
        self.win_width_spin.setValue(1280)
        win_row1.addWidget(self.win_width_spin)

        win_row1.addWidget(QLabel("Height (px):"))
        self.win_height_spin = QSpinBox()
        self.win_height_spin.setRange(300, 2160)
        self.win_height_spin.setValue(720)
        win_row1.addWidget(self.win_height_spin)
        win_layout.addLayout(win_row1)

        win_row2 = QHBoxLayout()
        win_row2.addWidget(QLabel("Start Pos X:"))
        self.win_pos_x_spin = QSpinBox()
        self.win_pos_x_spin.setRange(0, 3840)
        self.win_pos_x_spin.setValue(0)
        win_row2.addWidget(self.win_pos_x_spin)

        win_row2.addWidget(QLabel("Start Pos Y:"))
        self.win_pos_y_spin = QSpinBox()
        self.win_pos_y_spin.setRange(0, 2160)
        self.win_pos_y_spin.setValue(0)
        win_row2.addWidget(self.win_pos_y_spin)
        win_layout.addLayout(win_row2)

        layout.addWidget(win_group)

        layout.addStretch()
        return widget

    def _populate_webgl_presets(self, os_name: str, select_default: bool = True):
        if not hasattr(self, "webgl_combo"):
            return
        self.webgl_combo.blockSignals(True)
        self.webgl_combo.clear()
        
        # 1. Option: 100% Unspoofed Native WebGL
        self.webgl_combo.addItem("🚫 WebGL nicht spoofen (100% Original Hardware / Native Passthrough)", {"mode": "real", "vendor": "", "renderer": "", "is_unspoofed": True})

        # 2. Real / Native Host Hardware Option
        native_gpu = config.detect_native_webgl_info()
        self.webgl_combo.addItem(f"⚡ Native Host Hardware ({native_gpu['vendor']} | {native_gpu['renderer']})", native_gpu)

        # 3. OS-Harmonized Presets
        presets = config.get_webgl_presets_for_os(os_name)
        for preset in presets:
            self.webgl_combo.addItem(f"{preset['vendor']} | {preset['renderer']}", preset)

        if select_default and len(presets) > 0:
            self.webgl_combo.setCurrentIndex(2)
        self.webgl_combo.blockSignals(False)

    def _sync_webgl_combo_selection(self, vendor: str, renderer: str, spoof_enabled: bool = True):
        if not hasattr(self, "webgl_combo"):
            return
        self.webgl_combo.blockSignals(True)
        if not spoof_enabled or (not vendor and not renderer):
            self.webgl_combo.setCurrentIndex(0)
            self.webgl_combo.blockSignals(False)
            return

        matched_idx = -1
        for idx in range(self.webgl_combo.count()):
            data = self.webgl_combo.itemData(idx)
            if isinstance(data, dict):
                p_v = data.get("vendor", "")
                p_r = data.get("renderer", "")
                if p_v and p_r and p_v == vendor and p_r == renderer:
                    matched_idx = idx
                    break
        
        if matched_idx >= 0:
            self.webgl_combo.setCurrentIndex(matched_idx)
        else:
            for idx in range(self.webgl_combo.count()):
                data = self.webgl_combo.itemData(idx)
                if isinstance(data, dict):
                    p_r = data.get("renderer", "")
                    if p_r and (p_r == renderer or renderer in p_r or p_r in renderer):
                        matched_idx = idx
                        break
            if matched_idx >= 0:
                self.webgl_combo.setCurrentIndex(matched_idx)
            elif len(self.webgl_combo) > 2:
                self.webgl_combo.setCurrentIndex(2)
        self.webgl_combo.blockSignals(False)

    def _on_engine_changed(self):
        if hasattr(self, "custom_ua_cb") and not self.custom_ua_cb.isChecked():
            os_name = self.os_combo.currentText() if hasattr(self, "os_combo") else "windows"
            engine_type = self.engine_combo.currentData() if hasattr(self, "engine_combo") else "camoufox"
            self.ua_input.setText(config.get_default_user_agent(os_name, engine_type))
        self._update_fingerprint_preview()

    def _on_os_changed(self, os_name: str):
        engine_type = self.engine_combo.currentData() if hasattr(self, "engine_combo") else "camoufox"
        if not hasattr(self, "custom_ua_cb") or not self.custom_ua_cb.isChecked():
            self.ua_input.setText(config.get_default_user_agent(os_name, engine_type))
        if os_name == "mac":
            self.device_vendor_input.setText("Apple")
            self.device_model_input.setText("Macintosh")
            self.res_combo.setCurrentText("1920x1080")
            self.touch_points_spin.setValue(0)
        elif os_name == "android":
            self.device_vendor_input.setText("Google")
            self.device_model_input.setText("Pixel 8")
            self.res_combo.setCurrentText("412x915")
            self.touch_points_spin.setValue(10)
        elif os_name == "ios":
            self.device_vendor_input.setText("Apple")
            self.device_model_input.setText("iPhone")
            self.res_combo.setCurrentText("393x852")
            self.touch_points_spin.setValue(5)
        else:
            self.device_vendor_input.setText("Google")
            self.device_model_input.setText("PC")
            self.res_combo.setCurrentText("1920x1080")
            self.touch_points_spin.setValue(0)

        # Auto-Harmonize WebGL GPU presets with the chosen OS
        self._populate_webgl_presets(os_name, select_default=True)
        presets = config.get_webgl_presets_for_os(os_name)
        if presets and hasattr(self, "webgl_vendor_input") and hasattr(self, "webgl_renderer_input"):
            p = presets[0]
            self.webgl_vendor_input.setText(p["vendor"])
            self.webgl_renderer_input.setText(p["renderer"])
            self._sync_webgl_combo_selection(p["vendor"], p["renderer"], True)

    def _toggle_custom_ua(self, checked: bool):
        self.ua_input.setEnabled(checked)
        self.generate_ua_btn.setEnabled(checked)
        if not checked:
            os_name = self.os_combo.currentText() if hasattr(self, "os_combo") else "windows"
            engine_type = self.engine_combo.currentData() if hasattr(self, "engine_combo") else "camoufox"
            self.ua_input.setText(config.get_default_user_agent(os_name, engine_type))
            self.ua_input.setPlaceholderText("Auto-generated natively by Camoufox / Browser Engine")

    def _generate_random_ua(self):
        os_name = self.os_combo.currentText() if hasattr(self, "os_combo") else "windows"
        engine_type = self.engine_combo.currentData() if hasattr(self, "engine_combo") else "camoufox"
        if engine_type == "camoufox":
            ff_ver = random.randint(130, 135)
            if os_name == "windows":
                ua = f"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:{ff_ver}.0) Gecko/20100101 Firefox/{ff_ver}.0"
            elif os_name == "mac":
                ua = f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:{ff_ver}.0) Gecko/20100101 Firefox/{ff_ver}.0"
            elif os_name == "android":
                ua = f"Mozilla/5.0 (Android 14; Mobile; rv:{ff_ver}.0) Gecko/{ff_ver}.0 Firefox/{ff_ver}.0"
            elif os_name == "ios":
                ua = f"Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) FxiOS/{ff_ver}.0 Mobile/15E148 Safari/605.1.15"
            else:
                ua = f"Mozilla/5.0 (X11; Linux x86_64; rv:{ff_ver}.0) Gecko/20100101 Firefox/{ff_ver}.0"
        else:
            chrome_ver = random.randint(125, 133)
            if os_name == "windows":
                ua = f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_ver}.0.0.0 Safari/537.36"
            elif os_name == "mac":
                ua = f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_ver}.0.0.0 Safari/537.36"
            elif os_name == "android":
                ua = f"Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_ver}.0.0.0 Mobile Safari/537.36"
            elif os_name == "ios":
                ua = f"Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1"
            else:
                ua = f"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_ver}.0.0.0 Safari/537.36"
        self.ua_input.setText(ua)

    def _create_stealth_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 8, 4)
        layout.setSpacing(12)

        # 1. Active Fingerprint Live Matrix Inspector (Top Card)
        inspector_box = QGroupBox("⌕ Active Fingerprint Matrix (Aktuell gesetzter Fingerprint & Signatur)")
        insp_layout = QVBoxLayout(inspector_box)
        insp_layout.setSpacing(10)

        self.fp_status_card = QLabel()
        self.fp_status_card.setWordWrap(True)
        self.fp_status_card.setTextFormat(Qt.TextFormat.RichText)
        self.fp_status_card.setStyleSheet("""
            QLabel {
                background-color: rgba(15, 23, 42, 0.95);
                border: 1px solid rgba(56, 189, 248, 0.35);
                border-radius: 8px;
                padding: 12px;
                color: #e2e8f0;
                font-size: 11px;
            }
        """)
        insp_layout.addWidget(self.fp_status_card)

        # Quick Actions Row
        act_row = QHBoxLayout()
        act_row.setSpacing(8)

        self.btn_copy_fp_json = QPushButton("⎘ Copy Fingerprint JSON")
        self.btn_copy_fp_json.setProperty("class", "SecondaryButton")
        self.btn_copy_fp_json.clicked.connect(self._copy_fingerprint_json)
        act_row.addWidget(self.btn_copy_fp_json)

        self.btn_rand_seed = QPushButton("⚄ Randomize Seed / Hash")
        self.btn_rand_seed.setProperty("class", "SecondaryButton")
        self.btn_rand_seed.clicked.connect(self._randomize_noise_seed)
        act_row.addWidget(self.btn_rand_seed)

        self.btn_toggle_fp_raw = QPushButton("⚆ Show Raw JSON Matrix")
        self.btn_toggle_fp_raw.setProperty("class", "SecondaryButton")
        self.btn_toggle_fp_raw.clicked.connect(self._toggle_fp_raw_viewer)
        act_row.addWidget(self.btn_toggle_fp_raw)

        act_row.addStretch()
        insp_layout.addLayout(act_row)

        # Collapsible Raw JSON Viewer
        self.fp_raw_json_edit = QTextEdit()
        self.fp_raw_json_edit.setReadOnly(True)
        self.fp_raw_json_edit.setFixedHeight(180)
        self.fp_raw_json_edit.setStyleSheet("""
            QTextEdit {
                font-family: Consolas, 'Courier New', monospace;
                font-size: 11px;
                background-color: rgba(10, 13, 22, 0.98);
                color: #38bdf8;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 6px;
                padding: 8px;
            }
        """)
        self.fp_raw_json_edit.setVisible(False)
        insp_layout.addWidget(self.fp_raw_json_edit)

        layout.addWidget(inspector_box)

        # 2. Camoufox C++ Engine Group
        webgl_box = QGroupBox("Camoufox C++ Anti-Detect Motion Engine")
        webgl_layout = QVBoxLayout(webgl_box)

        webgl_layout.addWidget(QLabel("Fingerprint Generation Engine:"))
        self.fp_engine_combo = QComboBox()
        self.fp_engine_combo.addItem("★ Real In-The-Wild Presets (v150+ Scraped Traffic - Highly Recommended)", "real_presets")
        self.fp_engine_combo.addItem("⚄ Synthetic Statistical Distribution (BrowserForge)", "browserforge")
        self.fp_engine_combo.addItem("⛭ Custom Manual Configuration", "custom")
        self.fp_engine_combo.currentIndexChanged.connect(lambda: self._update_fingerprint_preview())
        webgl_layout.addWidget(self.fp_engine_combo)

        self.webgl_spoof_cb = QCheckBox("Enable WebGL Spoofing / Hardware Masking")
        self.webgl_spoof_cb.setChecked(True)
        self.webgl_spoof_cb.toggled.connect(self._on_webgl_spoof_toggled)
        webgl_layout.addWidget(self.webgl_spoof_cb)

        webgl_layout.addWidget(QLabel("Preset:"))
        self.webgl_combo = QComboBox()
        cur_os = self.os_combo.currentText() if hasattr(self, "os_combo") else "windows"
        self._populate_webgl_presets(cur_os, select_default=True)
        self.webgl_combo.currentIndexChanged.connect(self._on_webgl_preset_changed)
        webgl_layout.addWidget(self.webgl_combo)

        # Set default inputs from initial selection
        init_preset = self.webgl_combo.currentData()
        if init_preset and not init_preset.get("is_unspoofed"):
            self.webgl_vendor_input = QLineEdit(init_preset.get("vendor", "Google Inc. (NVIDIA)"))
            self.webgl_renderer_input = QLineEdit(init_preset.get("renderer", "ANGLE (NVIDIA, GeForce RTX 3060)"))
        else:
            self.webgl_vendor_input = QLineEdit()
            self.webgl_renderer_input = QLineEdit()

        self.btn_native_webgl = QPushButton("⚡ Echte / Originale WebGL-Hardware-Daten übernehmen")
        self.btn_native_webgl.setStyleSheet("font-weight: bold; padding: 6px; background-color: #1e3a5f; color: #60a5fa; border: 1px solid #3b82f6; border-radius: 4px;")
        self.btn_native_webgl.clicked.connect(self._apply_native_webgl_data)
        webgl_layout.addWidget(self.btn_native_webgl)

        webgl_layout.addWidget(QLabel("Unmasked Vendor:"))
        self.webgl_vendor_input.textChanged.connect(lambda: self._update_fingerprint_preview())
        webgl_layout.addWidget(self.webgl_vendor_input)

        webgl_layout.addWidget(QLabel("Unmasked Renderer:"))
        self.webgl_renderer_input.textChanged.connect(lambda: self._update_fingerprint_preview())
        webgl_layout.addWidget(self.webgl_renderer_input)

        self.webgpu_cb = QCheckBox("Enable WebGPU Support API")
        self.webgpu_cb.toggled.connect(lambda: self._update_fingerprint_preview())
        webgl_layout.addWidget(self.webgpu_cb)
        layout.addWidget(webgl_box)

        # 3. Fingerprint Noise Protection
        noise_box = QGroupBox("Fingerprint Noise Protection")
        noise_layout = QVBoxLayout(noise_box)

        self.canvas_noise_cb = QCheckBox("Enable Canvas 2D Fingerprint Noise")
        self.audio_noise_cb = QCheckBox("Enable AudioContext Fingerprint Noise")
        self.client_rects_noise_cb = QCheckBox("Enable ClientRects / BoundingBox Noise")
        self.font_noise_cb = QCheckBox("Enable Font Fingerprint Noise Injection")

        for cb in (self.canvas_noise_cb, self.audio_noise_cb, self.client_rects_noise_cb, self.font_noise_cb):
            cb.toggled.connect(lambda: self._update_fingerprint_preview())
            noise_layout.addWidget(cb)

        seed_layout = QHBoxLayout()
        seed_layout.addWidget(QLabel("Custom Fingerprint Seed (Visitor ID / Canvas Hash):"))
        self.noise_seed_input = QLineEdit()
        self.noise_seed_input.setPlaceholderText("Optional (leave empty for profile ID seed)")
        self.noise_seed_input.textChanged.connect(lambda: self._update_fingerprint_preview())
        seed_layout.addWidget(self.noise_seed_input)
        noise_layout.addLayout(seed_layout)

        layout.addWidget(noise_box)

        # 4. WebRTC Protection
        webrtc_box = QGroupBox("WebRTC Protection")
        webrtc_layout = QVBoxLayout(webrtc_box)
        webrtc_layout.addWidget(QLabel("WebRTC Mode:"))
        self.webrtc_combo = QComboBox()
        self.webrtc_combo.addItem("⛊ Protocol-Level IP Spoofing (C++ Native ICE - Undetectable)", "altered")
        self.webrtc_combo.addItem("Disabled (No WebRTC)", "disabled")
        self.webrtc_combo.addItem("Real (Leak Local IP)", "real")
        self.webrtc_combo.currentIndexChanged.connect(lambda: self._update_fingerprint_preview())
        webrtc_layout.addWidget(self.webrtc_combo)
        layout.addWidget(webrtc_box)

        layout.addStretch()
        scroll.setWidget(widget)
        return scroll

    def _on_webgl_spoof_toggled(self, checked: bool):
        self.webgl_vendor_input.setEnabled(checked)
        self.webgl_renderer_input.setEnabled(checked)
        self.btn_native_webgl.setEnabled(checked)
        if hasattr(self, "webgl_combo"):
            self.webgl_combo.setEnabled(checked)
            if not checked:
                self.webgl_combo.blockSignals(True)
                self.webgl_combo.setCurrentIndex(0)
                self.webgl_combo.blockSignals(False)
            else:
                if self.webgl_combo.currentIndex() == 0:
                    v = self.webgl_vendor_input.text().strip() if hasattr(self, "webgl_vendor_input") else ""
                    r = self.webgl_renderer_input.text().strip() if hasattr(self, "webgl_renderer_input") else ""
                    if v or r:
                        self._sync_webgl_combo_selection(v, r, True)
                    else:
                        cur_os = self.os_combo.currentText() if hasattr(self, "os_combo") else "windows"
                        presets = config.get_webgl_presets_for_os(cur_os)
                        if presets:
                            self.webgl_combo.blockSignals(True)
                            self.webgl_combo.setCurrentIndex(2)
                            self.webgl_combo.blockSignals(False)
                            self.webgl_vendor_input.setText(presets[0]["vendor"])
                            self.webgl_renderer_input.setText(presets[0]["renderer"])
        if not checked:
            self.webgl_vendor_input.setPlaceholderText("Original / Native Passthrough (Unspoofed)")
            self.webgl_renderer_input.setPlaceholderText("Original / Native Passthrough (Unspoofed)")
        else:
            self.webgl_vendor_input.setPlaceholderText("")
            self.webgl_renderer_input.setPlaceholderText("")
        self._update_fingerprint_preview()

    def _apply_native_webgl_data(self):
        self.webgl_spoof_cb.setChecked(True)
        native_gpu = config.detect_native_webgl_info()
        self.webgl_vendor_input.setText(native_gpu.get("vendor", ""))
        self.webgl_renderer_input.setText(native_gpu.get("renderer", ""))
        if hasattr(self, "webgl_combo"):
            self.webgl_combo.blockSignals(True)
            self.webgl_combo.setCurrentIndex(1)
            self.webgl_combo.blockSignals(False)
        self._update_fingerprint_preview()

    def _on_webgl_preset_changed(self, index: int):
        preset = self.webgl_combo.currentData()
        if preset:
            if preset.get("is_unspoofed") or preset.get("mode") == "real":
                self.webgl_spoof_cb.setChecked(False)
                self.webgl_vendor_input.clear()
                self.webgl_renderer_input.clear()
            else:
                self.webgl_spoof_cb.setChecked(True)
                self.webgl_vendor_input.setText(preset.get("vendor", ""))
                self.webgl_renderer_input.setText(preset.get("renderer", ""))
        self._update_fingerprint_preview()

    def _randomize_noise_seed(self):
        import secrets
        new_seed = secrets.token_hex(8)
        self.noise_seed_input.setText(new_seed)
        self._update_fingerprint_preview()

    def _toggle_fp_raw_viewer(self):
        is_vis = self.fp_raw_json_edit.isVisible()
        self.fp_raw_json_edit.setVisible(not is_vis)
        self.btn_toggle_fp_raw.setText("⚇ Hide Raw JSON Matrix" if not is_vis else "⚆ Show Raw JSON Matrix")

    def _copy_fingerprint_json(self):
        txt = self.fp_raw_json_edit.toPlainText().strip()
        if txt:
            cb = QApplication.clipboard()
            if cb:
                cb.setText(txt)
                QMessageBox.information(self, "Copied", "Full Fingerprint JSON matrix copied to clipboard!")

    def _get_active_fingerprint_dict(self) -> dict:
        os_name = self.os_combo.currentText() if hasattr(self, "os_combo") else "windows"
        engine_type = self.engine_combo.currentData() if hasattr(self, "engine_combo") else "camoufox"
        ua_val = self.ua_input.text().strip() if hasattr(self, "ua_input") else ""
        if not ua_val:
            ua_val = config.get_default_user_agent(os_name, engine_type)

        res_val = self.res_combo.currentText() if hasattr(self, "res_combo") else "1920x1080"
        color_depth = self.color_depth_combo.currentText() if hasattr(self, "color_depth_combo") else "24"
        touch_pts = self.touch_points_spin.value() if hasattr(self, "touch_points_spin") else 0
        cpu_cores = self.cpu_spin.value() if hasattr(self, "cpu_spin") else 8
        ram_gb = self.ram_spin.value() if hasattr(self, "ram_spin") else 8

        fp_engine_val = self.fp_engine_combo.currentData() if hasattr(self, "fp_engine_combo") else "real_presets"
        fp_engine_text = self.fp_engine_combo.currentText() if hasattr(self, "fp_engine_combo") else "Real In-The-Wild Presets"
        vendor = self.webgl_vendor_input.text().strip() if hasattr(self, "webgl_vendor_input") else "Google Inc. (NVIDIA)"
        renderer = self.webgl_renderer_input.text().strip() if hasattr(self, "webgl_renderer_input") else "ANGLE (NVIDIA, RTX 4090)"
        webgpu = self.webgpu_cb.isChecked() if hasattr(self, "webgpu_cb") else False

        canvas_n = self.canvas_noise_cb.isChecked() if hasattr(self, "canvas_noise_cb") else True
        audio_n = self.audio_noise_cb.isChecked() if hasattr(self, "audio_noise_cb") else True
        rects_n = self.client_rects_noise_cb.isChecked() if hasattr(self, "client_rects_noise_cb") else True
        font_n = self.font_noise_cb.isChecked() if hasattr(self, "font_noise_cb") else True
        seed = self.noise_seed_input.text().strip() if hasattr(self, "noise_seed_input") else ""

        prof_id = self.profile_data.get("id", "new_profile")
        effective_seed = seed if seed else f"profile_{str(prof_id)[:8]}"

        import hashlib
        sig_data = f"{os_name}_{ua_val}_{res_val}_{cpu_cores}_{ram_gb}_{vendor}_{renderer}_{effective_seed}_{fp_engine_val}"
        fp_hash = hashlib.sha256(sig_data.encode()).hexdigest()[:16].upper()

        webrtc_val = self.webrtc_combo.currentText() if hasattr(self, "webrtc_combo") else "Protocol-Level IP Spoofing"
        if hasattr(self, "tz_combo"):
            tz_data = self.tz_combo.currentData()
            if tz_data == "auto":
                if hasattr(self, "proxy_enable_cb") and self.proxy_enable_cb.isChecked():
                    tz_val = "Auto-Detect (Proxy IP)"
                else:
                    from engine.browser import get_system_timezone
                    tz_val = f"System Timezone ({get_system_timezone()})"
            else:
                tz_val = self.tz_combo.currentText().strip()
        else:
            tz_val = "Auto-Detect from Proxy IP"
        lang_val = self.lang_input.text().strip() if hasattr(self, "lang_input") else "en-US,en;q=0.9"

        platform_map = {"windows": "Win32", "mac": "MacIntel", "linux": "Linux x86_64", "android": "Linux armv8l", "ios": "iPhone"}
        platform_str = platform_map.get(os_name, "Win32")

        return {
            "fingerprint_id": f"FP-{fp_hash}",
            "engine": fp_engine_val,
            "engine_label": fp_engine_text,
            "platform": {
                "os": os_name,
                "navigator_platform": platform_str,
                "user_agent": ua_val
            },
            "screen_and_display": {
                "resolution": res_val,
                "color_depth": int(color_depth) if color_depth.isdigit() else 24,
                "max_touch_points": touch_pts
            },
            "hardware": {
                "concurrency_cpu_cores": cpu_cores,
                "device_memory_gb": ram_gb
            },
            "webgl_gpu": {
                "unmasked_vendor": vendor,
                "unmasked_renderer": renderer,
                "webgpu_supported": webgpu
            },
            "noise_protection": {
                "canvas_2d_noise": canvas_n,
                "audiocontext_noise": audio_n,
                "client_rects_noise": rects_n,
                "font_fingerprint_noise": font_n,
                "effective_seed": effective_seed
            },
            "cpp_native_seeds": {
                "audio_seed": (int(hashlib.sha256(f"audio_{effective_seed}".encode()).hexdigest()[:8], 16) % 4294967294) + 1 if audio_n else "Disabled",
                "fonts_spacing_seed": (int(hashlib.sha256(f"fonts_spacing_{effective_seed}".encode()).hexdigest()[:8], 16) % 4294967294) + 1 if font_n else "Disabled",
                "canvas_seed": (int(hashlib.sha256(f"canvas_{effective_seed}".encode()).hexdigest()[:8], 16) % 4294967294) + 1 if canvas_n else "Disabled"
            },
            "network_and_privacy": {
                "webrtc_mode": webrtc_val,
                "timezone": tz_val,
                "language": lang_val
            }
        }

    def _update_fingerprint_preview(self):
        if not hasattr(self, "fp_status_card"):
            return

        fp = self._get_active_fingerprint_dict()
        import json
        json_str = json.dumps(fp, indent=4, ensure_ascii=False)
        if hasattr(self, "fp_raw_json_edit"):
            self.fp_raw_json_edit.setText(json_str)

        noise_status = []
        if fp["noise_protection"]["canvas_2d_noise"]: noise_status.append("Canvas 2D")
        if fp["noise_protection"]["audiocontext_noise"]: noise_status.append("Audio")
        if fp["noise_protection"]["client_rects_noise"]: noise_status.append("ClientRects")
        if fp["noise_protection"]["font_fingerprint_noise"]: noise_status.append("Fonts")
        noise_str = " + ".join(noise_status) if noise_status else "Disabled"

        cpp_audio = fp.get("cpp_native_seeds", {}).get("audio_seed", "N/A")
        cpp_font = fp.get("cpp_native_seeds", {}).get("fonts_spacing_seed", "N/A")

        card_html = f"""
        <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;'>
            <span style='font-size: 13px; font-weight: 800; color: #38bdf8;'>⚿ Fingerprint Signature: <span style='color: #f8fafc; font-family: monospace;'>{fp['fingerprint_id']}</span></span>
            <span style='background-color: rgba(34, 197, 94, 0.2); color: #4ade80; border: 1px solid rgba(34, 197, 94, 0.4); padding: 2px 8px; border-radius: 4px; font-weight: 700; font-size: 10px;'>✓ Consistent & Undetectable</span>
        </div>
        <table style='width: 100%; border-collapse: collapse; font-size: 11px;'>
            <tr>
                <td style='color: #94a3b8; padding: 2px 0; width: 140px;'><b>Engine Mode:</b></td>
                <td style='color: #fbbf24;'>{fp['engine_label']}</td>
            </tr>
            <tr>
                <td style='color: #94a3b8; padding: 2px 0;'><b>OS & Platform:</b></td>
                <td style='color: #e2e8f0;'><b>{fp['platform']['os'].upper()}</b> ({fp['platform']['navigator_platform']})</td>
            </tr>
            <tr>
                <td style='color: #94a3b8; padding: 2px 0;'><b>GPU Hardware:</b></td>
                <td style='color: #a78bfa;'>{fp['webgl_gpu']['unmasked_vendor']} | {fp['webgl_gpu']['unmasked_renderer']}</td>
            </tr>
            <tr>
                <td style='color: #94a3b8; padding: 2px 0;'><b>Screen & Hardware:</b></td>
                <td style='color: #e2e8f0;'>{fp['screen_and_display']['resolution']} ({fp['screen_and_display']['color_depth']}-bit) &nbsp;|&nbsp; {fp['hardware']['concurrency_cpu_cores']} Cores CPU &nbsp;|&nbsp; {fp['hardware']['device_memory_gb']} GB RAM</td>
            </tr>
            <tr>
                <td style='color: #94a3b8; padding: 2px 0;'><b>C++ Native Seeds:</b></td>
                <td style='color: #38bdf8;'>Audio Seed: <code style='color: #fbbf24;'>{cpp_audio}</code> &nbsp;|&nbsp; Font Spacing: <code style='color: #fbbf24;'>{cpp_font}</code></td>
            </tr>
            <tr>
                <td style='color: #94a3b8; padding: 2px 0;'><b>Noise Shielding:</b></td>
                <td style='color: #34d399;'>⛊ {noise_str} &nbsp;(Profile Seed: <code style='color: #38bdf8;'>{fp['noise_protection']['effective_seed']}</code>)</td>
            </tr>
            <tr>
                <td style='color: #94a3b8; padding: 2px 0;'><b>WebRTC Shield:</b></td>
                <td style='color: #38bdf8;'>{fp['network_and_privacy']['webrtc_mode']}</td>
            </tr>
            <tr>
                <td style='color: #94a3b8; padding: 2px 0; vertical-align: top;'><b>User-Agent:</b></td>
                <td style='color: #cbd5e1; font-family: monospace; font-size: 10px; word-break: break-all;'>{fp['platform']['user_agent']}</td>
            </tr>
        </table>
        """
        self.fp_status_card.setText(card_html)

    def _create_tz_lang_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        from engine.browser import get_system_timezone
        sys_tz = get_system_timezone()
        is_proxy = hasattr(self, "proxy_enable_cb") and self.proxy_enable_cb.isChecked()
        auto_text = "⛿ Auto-Detect from Proxy IP" if is_proxy else f"⛿ Auto-Detect System Timezone ({sys_tz})"

        layout.addWidget(QLabel("Timezone Mode:"))
        self.tz_combo = QComboBox()
        self.tz_combo.setEditable(True)
        self.tz_combo.addItem(auto_text, "auto")
        timezones_list = [
            (" Europe/Berlin (Germany)", "Europe/Berlin"),
            (" Europe/Paris (France)", "Europe/Paris"),
            (" Europe/London (UK)", "Europe/London"),
            (" Europe/Amsterdam (Netherlands)", "Europe/Amsterdam"),
            (" Europe/Rome (Italy)", "Europe/Rome"),
            (" Europe/Madrid (Spain)", "Europe/Madrid"),
            (" Europe/Warsaw (Poland)", "Europe/Warsaw"),
            (" Europe/Kyiv (Ukraine)", "Europe/Kyiv"),
            (" Europe/Zurich (Switzerland)", "Europe/Zurich"),
            (" Europe/Vienna (Austria)", "Europe/Vienna"),
            (" America/New_York (US East)", "America/New_York"),
            (" America/Chicago (US Central)", "America/Chicago"),
            (" America/Denver (US Mountain)", "America/Denver"),
            (" America/Los_Angeles (US West)", "America/Los_Angeles"),
            (" America/Toronto (Canada)", "America/Toronto"),
            (" America/Sao_Paulo (Brazil)", "America/Sao_Paulo"),
            (" Asia/Tokyo (Japan)", "Asia/Tokyo"),
            (" Asia/Shanghai (China)", "Asia/Shanghai"),
            (" Asia/Singapore (Singapore)", "Asia/Singapore"),
            (" Asia/Bangkok (Thailand)", "Asia/Bangkok"),
            (" Asia/Dubai (UAE)", "Asia/Dubai"),
            (" Asia/Kolkata (India)", "Asia/Kolkata"),
            (" Australia/Sydney (Australia)", "Australia/Sydney"),
            ("⛿ UTC (Coordinated Universal Time)", "UTC"),
        ]
        for label, val in timezones_list:
            self.tz_combo.addItem(label, val)

        def _on_tz_changed(idx):
            data = self.tz_combo.currentData()
            if hasattr(self, "auto_tz_cb") and data and data != "auto":
                self.auto_tz_cb.blockSignals(True)
                self.auto_tz_cb.setChecked(False)
                self.auto_tz_cb.blockSignals(False)
            self._update_fingerprint_preview()

        self.tz_combo.currentIndexChanged.connect(_on_tz_changed)

        if hasattr(self, "auto_tz_cb"):
            def _on_auto_tz_toggled(checked):
                if checked:
                    self.tz_combo.blockSignals(True)
                    self.tz_combo.setCurrentIndex(0)
                    self.tz_combo.blockSignals(False)
                self._update_fingerprint_preview()
            self.auto_tz_cb.toggled.connect(_on_auto_tz_toggled)
        layout.addWidget(self.tz_combo)

        layout.addWidget(QLabel("Languages & Locale (Accept-Language):"))
        self.lang_input = QLineEdit()
        self.lang_input.setPlaceholderText("e.g. en-US,en;q=0.9 or de-DE,de;q=0.9")
        self.lang_input.textChanged.connect(self._update_fingerprint_preview)
        layout.addWidget(self.lang_input)

        layout.addWidget(QLabel("Do Not Track Header:"))
        self.dnt_combo = QComboBox()
        self.dnt_combo.addItem("null (Default - Unset)", "null")
        self.dnt_combo.addItem("1 (Do Not Track Enabled)", "1")
        self.dnt_combo.addItem("0 (Do Not Track Disabled)", "0")
        layout.addWidget(self.dnt_combo)

        layout.addStretch()
        return widget

    def _create_storage_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Tab Widget for Cookies vs Extensions
        self.storage_sub_tabs = QTabWidget()
        self.storage_sub_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
                background-color: rgba(15, 23, 42, 0.6);
            }
            QTabBar::tab {
                background-color: rgba(30, 41, 59, 0.7);
                color: #94a3b8;
                padding: 6px 14px;
                margin-right: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background-color: #3b82f6;
                color: #ffffff;
            }
        """)

        # -------------------------------------------------------------
        # SUB-TAB 1: Visual Cookie Table
        # -------------------------------------------------------------
        cookie_tab_widget = QWidget()
        cookie_tab_layout = QVBoxLayout(cookie_tab_widget)
        cookie_tab_layout.setContentsMargins(8, 8, 8, 8)
        cookie_tab_layout.setSpacing(8)

        # Top Control Bar
        top_bar = QHBoxLayout()
        self.cookie_status_label = QLabel("⚇ Active Cookies: 0 valid cookies")
        self.cookie_status_label.setStyleSheet("font-weight: 700; color: #38bdf8; font-size: 12px;")
        top_bar.addWidget(self.cookie_status_label)
        top_bar.addStretch()

        self.cookie_search_input = QLineEdit()
        self.cookie_search_input.setPlaceholderText("🔍 Filter cookies (Domain, Name, Value)...")
        self.cookie_search_input.setMaximumWidth(280)
        self.cookie_search_input.setStyleSheet("""
            background-color: rgba(10, 13, 22, 0.85);
            color: #e2e8f0;
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 6px;
            padding: 4px 8px;
            font-size: 11px;
        """)
        self.cookie_search_input.textChanged.connect(self._on_cookie_search_changed)
        top_bar.addWidget(self.cookie_search_input)

        btn_add_cookie = QPushButton("+ Add Cookie")
        btn_add_cookie.setProperty("class", "SecondaryButton")
        btn_add_cookie.clicked.connect(self._add_new_cookie_row)
        top_bar.addWidget(btn_add_cookie)

        btn_del_selected = QPushButton("🗑 Delete Selected")
        btn_del_selected.setProperty("class", "SecondaryButton")
        btn_del_selected.clicked.connect(self._delete_selected_cookie_rows)
        top_bar.addWidget(btn_del_selected)

        btn_clear_all = QPushButton("⎚ Clear All")
        btn_clear_all.setProperty("class", "SecondaryButton")
        btn_clear_all.clicked.connect(self._clear_all_cookies)
        top_bar.addWidget(btn_clear_all)

        btn_export = QPushButton("⭱ Export")
        btn_export.setProperty("class", "SecondaryButton")
        btn_export.clicked.connect(self._export_cookies_to_file)
        top_bar.addWidget(btn_export)

        cookie_tab_layout.addLayout(top_bar)

        # Interactive Cookie Table
        self.cookie_table = QTableWidget()
        self.cookie_table.setColumnCount(8)
        self.cookie_table.setHorizontalHeaderLabels([
            "Domain", "Name", "Value", "Path", "Secure", "HttpOnly", "Expiry (Unix)", "Action"
        ])
        header = self.cookie_table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
            header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(6, QHeaderView.ResizeMode.Interactive)
            header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
        self.cookie_table.setColumnWidth(7, 75)
        self.cookie_table.setAlternatingRowColors(True)
        self.cookie_table.setStyleSheet("""
            QTableWidget {
                background-color: rgba(10, 13, 22, 0.95);
                color: #e2e8f0;
                gridline-color: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 6px;
                font-size: 11px;
            }
            QHeaderView::section {
                background-color: rgba(30, 41, 59, 0.9);
                color: #cbd5e1;
                font-weight: 700;
                font-size: 11px;
                padding: 4px;
                border: 1px solid rgba(255, 255, 255, 0.05);
            }
        """)
        self.cookie_table.cellChanged.connect(self._on_cookie_table_cell_changed)
        cookie_tab_layout.addWidget(self.cookie_table)

        self.storage_sub_tabs.addTab(cookie_tab_widget, "🍪 Visual Cookie Manager")

        # -------------------------------------------------------------
        # SUB-TAB 2: Raw JSON & Netscape Code Editor
        # -------------------------------------------------------------
        code_tab_widget = QWidget()
        code_tab_layout = QVBoxLayout(code_tab_widget)
        code_tab_layout.setContentsMargins(8, 8, 8, 8)
        code_tab_layout.setSpacing(8)

        code_top_layout = QHBoxLayout()
        lbl_code_hint = QLabel("Raw JSON / Netscape Cookie Text Editor (Bi-directionally synced with Visual Table):")
        lbl_code_hint.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 600;")
        code_top_layout.addWidget(lbl_code_hint)
        code_top_layout.addStretch()

        paste_btn = QPushButton("⎘ Paste Clipboard")
        paste_btn.setProperty("class", "SecondaryButton")
        paste_btn.clicked.connect(self._paste_cookies_from_clipboard)
        code_top_layout.addWidget(paste_btn)

        import_file_btn = QPushButton("⭳ Load File")
        import_file_btn.setProperty("class", "SecondaryButton")
        import_file_btn.clicked.connect(self._import_cookie_file)
        code_top_layout.addWidget(import_file_btn)

        beautify_btn = QPushButton("★ Format JSON")
        beautify_btn.setProperty("class", "SecondaryButton")
        beautify_btn.clicked.connect(self._beautify_cookie_json)
        code_top_layout.addWidget(beautify_btn)

        clear_code_btn = QPushButton("⎚ Clear Editor")
        clear_code_btn.setProperty("class", "SecondaryButton")
        clear_code_btn.clicked.connect(self._clear_cookie_editor)
        code_top_layout.addWidget(clear_code_btn)

        code_tab_layout.addLayout(code_top_layout)

        self.cookie_text_edit = QTextEdit()
        self.cookie_text_edit.setPlaceholderText(
            "Paste or edit cookies here in JSON or Netscape HTTP Cookie format:\n\n"
            "[\n"
            "  {\n"
            '    "name": "session_id",\n'
            '    "value": "xyz123abc456",\n'
            '    "domain": ".example.com",\n'
            '    "path": "/",\n'
            '    "secure": true\n'
            "  }\n"
            "]"
        )
        self.cookie_text_edit.setStyleSheet("""
            QTextEdit {
                font-family: -apple-system, monospace, Consolas;
                font-size: 12px;
                background-color: rgba(10, 13, 22, 0.95);
                color: #34d399;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
                padding: 8px;
            }
        """)
        self.cookie_text_edit.textChanged.connect(self._on_cookie_text_changed)
        code_tab_layout.addWidget(self.cookie_text_edit)

        self.storage_sub_tabs.addTab(code_tab_widget, "💻 Raw JSON / Netscape Code")

        # -------------------------------------------------------------
        # SUB-TAB 3: Extensions Manager
        # -------------------------------------------------------------
        ext_tab_widget = QWidget()
        ext_tab_layout = QVBoxLayout(ext_tab_widget)
        ext_tab_layout.setContentsMargins(8, 8, 8, 8)
        ext_tab_layout.setSpacing(8)

        ext_top_bar = QHBoxLayout()
        lbl_ext_title = QLabel("🧩 Browser Extensions (.crx / .xpi / Unpacked Extension Folders):")
        lbl_ext_title.setStyleSheet("font-weight: 700; color: #38bdf8; font-size: 12px;")
        ext_top_bar.addWidget(lbl_ext_title)
        ext_top_bar.addStretch()

        btn_install_ext = QPushButton("+ Install Extension File")
        btn_install_ext.setProperty("class", "SecondaryButton")
        btn_install_ext.clicked.connect(self._install_extension_file)
        ext_top_bar.addWidget(btn_install_ext)

        btn_open_ext_dir = QPushButton("📁 Open Extensions Folder")
        btn_open_ext_dir.setProperty("class", "SecondaryButton")
        btn_open_ext_dir.clicked.connect(self._open_extensions_folder)
        ext_top_bar.addWidget(btn_open_ext_dir)

        btn_reload_ext = QPushButton("🔄 Refresh List")
        btn_reload_ext.setProperty("class", "SecondaryButton")
        btn_reload_ext.clicked.connect(self._load_extensions_list)
        ext_top_bar.addWidget(btn_reload_ext)

        ext_tab_layout.addLayout(ext_top_bar)

        self.extensions_list_widget = QListWidget()
        self.extensions_list_widget.setStyleSheet("""
            QListWidget {
                background-color: rgba(10, 13, 22, 0.95);
                color: #e2e8f0;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 6px;
                padding: 6px;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 6px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.04);
            }
            QListWidget::item:hover {
                background-color: rgba(59, 130, 246, 0.15);
            }
        """)
        ext_tab_layout.addWidget(self.extensions_list_widget)

        self.storage_sub_tabs.addTab(ext_tab_widget, "🧩 Browser Extensions")

        self.storage_sub_tabs.currentChanged.connect(self._on_storage_subtab_switched)
        layout.addWidget(self.storage_sub_tabs)
        return widget

    # -------------------------------------------------------------------------
    # COOKIE MANAGEMENT & SYNCHRONIZATION
    # -------------------------------------------------------------------------

    def _on_storage_subtab_switched(self, index: int):
        """Synchronizes data between visual table and code editor on tab switch."""
        if index == 0:
            # Switched to Visual Table: parse text into table
            txt = self.cookie_text_edit.toPlainText().strip()
            parsed = CookieManager.parse_cookie_text(txt)
            self._populate_cookie_table(parsed, update_text_edit=False)
        elif index == 1:
            # Switched to Code Editor: export table into JSON text
            cookies = self._get_cookies_from_table()
            import json
            self.cookie_text_edit.blockSignals(True)
            self.cookie_text_edit.setText(json.dumps(cookies, indent=4, ensure_ascii=False) if cookies else "")
            self.cookie_text_edit.blockSignals(False)
            self._on_cookie_text_changed()

    def _populate_cookie_table(self, cookies: List[Dict[str, Any]], update_text_edit: bool = True):
        self.cookie_table.blockSignals(True)
        self.cookie_table.setRowCount(0)
        
        for row_idx, c in enumerate(cookies):
            self.cookie_table.insertRow(row_idx)
            
            # Domain
            dom_item = QTableWidgetItem(str(c.get("domain", "")))
            self.cookie_table.setItem(row_idx, 0, dom_item)
            
            # Name
            name_item = QTableWidgetItem(str(c.get("name", "")))
            name_item.setForeground(Qt.GlobalColor.cyan)
            self.cookie_table.setItem(row_idx, 1, name_item)
            
            # Value
            val_item = QTableWidgetItem(str(c.get("value", "")))
            self.cookie_table.setItem(row_idx, 2, val_item)
            
            # Path
            path_item = QTableWidgetItem(str(c.get("path", "/")))
            self.cookie_table.setItem(row_idx, 3, path_item)
            
            # Secure
            sec_item = QTableWidgetItem("✓ True" if c.get("secure", False) else "False")
            sec_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.cookie_table.setItem(row_idx, 4, sec_item)
            
            # HttpOnly
            http_item = QTableWidgetItem("✓ True" if c.get("httpOnly", False) else "False")
            http_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.cookie_table.setItem(row_idx, 5, http_item)
            
            # Expiry
            exp_val = c.get("expiry")
            exp_str = str(exp_val) if exp_val is not None else "Session"
            exp_item = QTableWidgetItem(exp_str)
            self.cookie_table.setItem(row_idx, 6, exp_item)
            
            # Delete Action Button
            btn_del = QPushButton("🗑")
            btn_del.setStyleSheet("color: #fb7185; font-size: 11px; font-weight: 700; background: transparent; border: 1px solid rgba(251, 113, 133, 0.3); border-radius: 4px; padding: 2px 4px;")
            btn_del.clicked.connect(lambda _, r=row_idx: self._delete_single_cookie_row(r))
            self.cookie_table.setCellWidget(row_idx, 7, btn_del)

        self.cookie_table.blockSignals(False)
        self._update_cookie_count_label(len(cookies))

        if update_text_edit:
            import json
            self.cookie_text_edit.blockSignals(True)
            self.cookie_text_edit.setText(json.dumps(cookies, indent=4, ensure_ascii=False) if cookies else "")
            self.cookie_text_edit.blockSignals(False)

    def _get_cookies_from_table(self) -> List[Dict[str, Any]]:
        cookies = []
        for r in range(self.cookie_table.rowCount()):
            item_dom = self.cookie_table.item(r, 0)
            dom = item_dom.text().strip() if item_dom is not None else ""
            item_name = self.cookie_table.item(r, 1)
            name = item_name.text().strip() if item_name is not None else ""
            item_val = self.cookie_table.item(r, 2)
            val = item_val.text().strip() if item_val is not None else ""
            item_path = self.cookie_table.item(r, 3)
            path = item_path.text().strip() if item_path is not None else "/"
            item_sec = self.cookie_table.item(r, 4)
            sec_txt = item_sec.text().lower() if item_sec is not None else "false"
            item_http = self.cookie_table.item(r, 5)
            http_txt = item_http.text().lower() if item_http is not None else "false"
            item_exp = self.cookie_table.item(r, 6)
            exp_txt = item_exp.text().strip() if item_exp is not None else ""
            
            if name or dom:
                c_obj: Dict[str, Any] = {
                    "domain": dom,
                    "name": name,
                    "value": val,
                    "path": path or "/",
                    "secure": "true" in sec_txt or "✓" in sec_txt,
                    "httpOnly": "true" in http_txt or "✓" in http_txt
                }
                if exp_txt.isdigit():
                    c_obj["expiry"] = int(exp_txt)
                cookies.append(c_obj)
        return cookies

    def _on_cookie_table_cell_changed(self, row: int, col: int):
        cookies = self._get_cookies_from_table()
        self._update_cookie_count_label(len(cookies))
        import json
        self.cookie_text_edit.blockSignals(True)
        self.cookie_text_edit.setText(json.dumps(cookies, indent=4, ensure_ascii=False) if cookies else "")
        self.cookie_text_edit.blockSignals(False)

    def _on_cookie_search_changed(self, query: str):
        q = query.strip().lower()
        for r in range(self.cookie_table.rowCount()):
            item_dom = self.cookie_table.item(r, 0)
            dom = item_dom.text().lower() if item_dom is not None else ""
            item_name = self.cookie_table.item(r, 1)
            name = item_name.text().lower() if item_name is not None else ""
            item_val = self.cookie_table.item(r, 2)
            val = item_val.text().lower() if item_val is not None else ""
            matches = not q or q in dom or q in name or q in val
            self.cookie_table.setRowHidden(r, not matches)

    def _add_new_cookie_row(self):
        cookies = self._get_cookies_from_table()
        cookies.insert(0, {
            "domain": ".example.com",
            "name": "new_cookie",
            "value": "sample_value",
            "path": "/",
            "secure": True,
            "httpOnly": False
        })
        self._populate_cookie_table(cookies, update_text_edit=True)
        self.cookie_table.selectRow(0)

    def _delete_single_cookie_row(self, row: int):
        self.cookie_table.removeRow(row)
        # Re-assign lambda index bindings
        for r in range(self.cookie_table.rowCount()):
            btn_del = QPushButton("🗑")
            btn_del.setStyleSheet("color: #fb7185; font-size: 11px; font-weight: 700; background: transparent; border: 1px solid rgba(251, 113, 133, 0.3); border-radius: 4px; padding: 2px 4px;")
            btn_del.clicked.connect(lambda _, r_idx=r: self._delete_single_cookie_row(r_idx))
            self.cookie_table.setCellWidget(r, 7, btn_del)
        cookies = self._get_cookies_from_table()
        self._update_cookie_count_label(len(cookies))
        import json
        self.cookie_text_edit.blockSignals(True)
        self.cookie_text_edit.setText(json.dumps(cookies, indent=4, ensure_ascii=False) if cookies else "")
        self.cookie_text_edit.blockSignals(False)

    def _delete_selected_cookie_rows(self):
        selected_rows = sorted(set(index.row() for index in self.cookie_table.selectedIndexes()), reverse=True)
        if not selected_rows:
            QMessageBox.information(self, "Delete Cookie", "Please click on a cookie row in the table first.")
            return
        for r in selected_rows:
            self.cookie_table.removeRow(r)
        
        # Re-assign row bindings
        for r in range(self.cookie_table.rowCount()):
            btn_del = QPushButton("🗑")
            btn_del.setStyleSheet("color: #fb7185; font-size: 11px; font-weight: 700; background: transparent; border: 1px solid rgba(251, 113, 133, 0.3); border-radius: 4px; padding: 2px 4px;")
            btn_del.clicked.connect(lambda _, r_idx=r: self._delete_single_cookie_row(r_idx))
            self.cookie_table.setCellWidget(r, 7, btn_del)
            
        cookies = self._get_cookies_from_table()
        self._update_cookie_count_label(len(cookies))
        import json
        self.cookie_text_edit.blockSignals(True)
        self.cookie_text_edit.setText(json.dumps(cookies, indent=4, ensure_ascii=False) if cookies else "")
        self.cookie_text_edit.blockSignals(False)

    def _clear_all_cookies(self):
        ret = QMessageBox.question(
            self,
            "Clear All Cookies",
            "Are you sure you want to permanently delete ALL cookies for this profile?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if ret == QMessageBox.StandardButton.Yes:
            self.cookie_table.blockSignals(True)
            self.cookie_table.setRowCount(0)
            self.cookie_table.blockSignals(False)
            self.cookie_text_edit.blockSignals(True)
            self.cookie_text_edit.clear()
            self.cookie_text_edit.blockSignals(False)
            self._update_cookie_count_label(0)

    def _export_cookies_to_file(self):
        cookies = self._get_cookies_from_table()
        if not cookies:
            QMessageBox.information(self, "Export Cookies", "No cookies to export.")
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Cookies to JSON", "cookies.json", "JSON Files (*.json);;All Files (*)")
        if file_path:
            import json
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(cookies, f, indent=4, ensure_ascii=False)
                QMessageBox.information(self, "Export Successful", f"Exported {len(cookies)} cookies to {file_path}")
            except Exception as e:
                QMessageBox.warning(self, "Export Error", f"Failed to export cookies: {e}")

    def _update_cookie_count_label(self, count: int):
        if count > 0:
            self.cookie_status_label.setText(f"⚇ Active Cookies: {count} valid cookie(s)")
            self.cookie_status_label.setStyleSheet("font-weight: 700; color: #34d399; font-size: 12px;")
        else:
            self.cookie_status_label.setText("⚇ Active Cookies: 0 cookies (Clean)")
            self.cookie_status_label.setStyleSheet("font-weight: 700; color: #94a3b8; font-size: 12px;")

    def _on_cookie_text_changed(self):
        txt = self.cookie_text_edit.toPlainText().strip()
        if not txt:
            self._update_cookie_count_label(0)
            return
        parsed = CookieManager.parse_cookie_text(txt)
        count = len(parsed)
        if count > 0:
            self._update_cookie_count_label(count)
        else:
            self.cookie_status_label.setText("⚠ Invalid format (expected JSON array or Netscape format)")
            self.cookie_status_label.setStyleSheet("font-weight: 700; color: #fb7185; font-size: 12px;")

    def _paste_cookies_from_clipboard(self):
        cb = QApplication.clipboard()
        if cb:
            txt = cb.text()
            if txt:
                self.cookie_text_edit.setText(txt)
                parsed = CookieManager.parse_cookie_text(txt)
                if parsed:
                    self._populate_cookie_table(parsed, update_text_edit=False)

    def _import_cookie_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Import Cookie File", "", "Cookie Files (*.json *.txt);;All Files (*)")
        if file_path:
            cookies = CookieManager.import_cookies_from_file(file_path)
            if cookies:
                import json
                self.cookie_text_edit.setText(json.dumps(cookies, indent=4, ensure_ascii=False))
                self._populate_cookie_table(cookies, update_text_edit=False)
                QMessageBox.information(self, "Cookies Loaded", f"Loaded {len(cookies)} cookies into editor & table.")
            else:
                QMessageBox.warning(self, "Import Error", "Could not parse valid cookies from selected file.")

    def _beautify_cookie_json(self):
        txt = self.cookie_text_edit.toPlainText().strip()
        parsed = CookieManager.parse_cookie_text(txt)
        if parsed:
            import json
            self.cookie_text_edit.setText(json.dumps(parsed, indent=4, ensure_ascii=False))
            self._populate_cookie_table(parsed, update_text_edit=False)
        else:
            QMessageBox.information(self, "Format JSON", "No valid JSON or Netscape cookies to format.")

    def _clear_cookie_editor(self):
        self.cookie_text_edit.clear()
        self.cookie_table.blockSignals(True)
        self.cookie_table.setRowCount(0)
        self.cookie_table.blockSignals(False)
        self._update_cookie_count_label(0)

    # -------------------------------------------------------------------------
    # EXTENSIONS MANAGEMENT
    # -------------------------------------------------------------------------

    def _load_extensions_list(self):
        self.extensions_list_widget.clear()
        ext_folder = config.EXTENSIONS_DIR
        os.makedirs(ext_folder, exist_ok=True)
        
        assigned = self.profile_data.get("extensions", [])
        import glob
        files = glob.glob(os.path.join(ext_folder, "*.crx")) + glob.glob(os.path.join(ext_folder, "*.xpi")) + [
            d for d in glob.glob(os.path.join(ext_folder, "*")) if os.path.isdir(d)
        ]
        
        if not files:
            item = QListWidgetItem("No extensions found in extensions directory. Click '+ Install Extension File' to add one.")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            item.setForeground(Qt.GlobalColor.gray)
            self.extensions_list_widget.addItem(item)
            return

        for f in sorted(files):
            bname = os.path.basename(f)
            item = QListWidgetItem(f"🧩 {bname}")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            is_checked = bname in assigned or f in assigned
            item.setCheckState(Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, bname)
            self.extensions_list_widget.addItem(item)

    def _install_extension_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Extension File", "", "Browser Extensions (*.crx *.xpi *.zip);;All Files (*)")
        if file_path:
            import shutil
            ext_folder = config.EXTENSIONS_DIR
            os.makedirs(ext_folder, exist_ok=True)
            target = os.path.join(ext_folder, os.path.basename(file_path))
            try:
                shutil.copy2(file_path, target)
                QMessageBox.information(self, "Extension Installed", f"Installed {os.path.basename(file_path)} to extensions catalog.")
                self._load_extensions_list()
            except Exception as e:
                QMessageBox.warning(self, "Install Error", f"Failed to copy extension: {e}")

    def _open_extensions_folder(self):
        from engine.platform_helper import PlatformHelper
        ext_folder = config.EXTENSIONS_DIR
        os.makedirs(ext_folder, exist_ok=True)
        PlatformHelper.open_folder_or_file(ext_folder)

    def _get_selected_extensions(self) -> List[str]:
        selected = []
        for i in range(self.extensions_list_widget.count()):
            item = self.extensions_list_widget.item(i)
            if item and item.checkState() == Qt.CheckState.Checked:
                bname = item.data(Qt.ItemDataRole.UserRole)
                if bname:
                    selected.append(str(bname))
        return selected

    def _create_accounts_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)

        # 1. Header & Quick Presets Group
        top_box = QGroupBox("🔑 Accounts & Auto-Login Manager (Google, Instagram, GitHub, TikTok, etc.)")
        top_layout = QVBoxLayout(top_box)
        top_layout.setSpacing(8)

        desc_label = QLabel(
            "Configure social and platform accounts for this profile. "
            "Supports automated stealth login, 2FA/TOTP generation, and cookie session injection."
        )
        desc_label.setStyleSheet("color: #AAAAAA; font-size: 11px;")
        top_layout.addWidget(desc_label)

        # Quick Add Presets Bar
        quick_label = QLabel("<b>⚡ Quick Add Platform Account:</b>")
        top_layout.addWidget(quick_label)

        presets_flow = QHBoxLayout()
        presets_flow.setSpacing(6)

        presets_list = [
            ("google", "🌐 Google"),
            ("instagram", "📸 Instagram"),
            ("github", "🐙 GitHub"),
            ("tiktok", "🎵 TikTok"),
            ("twitter", "🐦 Twitter/X"),
            ("discord", "💬 Discord"),
            ("reddit", "🔴 Reddit"),
            ("spotify", "🟢 Spotify"),
            ("facebook", "👥 Facebook"),
            ("custom", "➕ Custom")
        ]

        for p_key, p_btn_title in presets_list:
            btn = QPushButton(p_btn_title)
            btn.setProperty("class", "SecondaryButton")
            btn.setFixedHeight(28)
            btn.clicked.connect(lambda checked, pk=p_key: self._quick_add_account(pk))
            presets_flow.addWidget(btn)

        presets_flow.addStretch()
        top_layout.addLayout(presets_flow)
        layout.addWidget(top_box)

        # 2. Accounts Table
        table_box = QGroupBox("Configured Profile Accounts")
        table_layout = QVBoxLayout(table_box)

        self.accounts_table = QTableWidget(0, 7)
        self.accounts_table.setHorizontalHeaderLabels([
            "Platform", "Label / Name", "Username / Email", "Password", "2FA / TOTP Live", "Auto-Login", "Actions"
        ])
        header = self.accounts_table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
            header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
            header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.accounts_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.accounts_table.setAlternatingRowColors(True)
        self.accounts_table.doubleClicked.connect(lambda idx: self._open_account_editor(row_idx=idx.row()))
        table_layout.addWidget(self.accounts_table)

        # 3. Action Buttons Bar
        action_layout = QHBoxLayout()
        action_layout.setSpacing(8)

        add_manual_btn = QPushButton("+ Add Account Manually")
        add_manual_btn.setProperty("class", "PrimaryButton")
        add_manual_btn.clicked.connect(lambda: self._open_account_editor())

        batch_import_btn = QPushButton("📥 Batch Import")
        batch_import_btn.setProperty("class", "SecondaryButton")
        batch_import_btn.clicked.connect(self._open_batch_import_accounts)

        export_btn = QPushButton("📤 Export Accounts")
        export_btn.setProperty("class", "SecondaryButton")
        export_btn.clicked.connect(self._export_accounts)

        clear_btn = QPushButton("🗑 Clear All")
        clear_btn.setProperty("class", "DangerButton")
        clear_btn.clicked.connect(self._clear_all_accounts)

        action_layout.addWidget(add_manual_btn)
        action_layout.addWidget(batch_import_btn)
        action_layout.addWidget(export_btn)
        action_layout.addStretch()
        action_layout.addWidget(clear_btn)

        table_layout.addLayout(action_layout)
        layout.addWidget(table_box)

        return widget

    def _quick_add_account(self, platform_key: str):
        plat_info = AccountManager.get_platform_info(platform_key)
        acc_stub = AccountManager.create_account_record(
            platform=platform_key,
            name=f"{plat_info['name']} Account",
            login_url=plat_info.get("login_url", "")
        )
        self._open_account_editor(account_data=acc_stub)

    def _open_account_editor(self, account_data: Optional[Dict[str, Any]] = None, row_idx: Optional[int] = None):
        if account_data is None and row_idx is not None:
            accounts = self._get_accounts_from_table()
            if 0 <= row_idx < len(accounts):
                account_data = accounts[row_idx]

        dlg = AccountEditorDialog(account_data=account_data, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            saved_acc = dlg.get_account_data()
            current_accounts = self._get_accounts_from_table()
            if row_idx is not None and 0 <= row_idx < len(current_accounts):
                current_accounts[row_idx] = saved_acc
            else:
                current_accounts.append(saved_acc)
            self._populate_accounts_table(current_accounts)

    def _open_batch_import_accounts(self):
        dlg = BatchImportAccountsDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            imported = dlg.get_accounts()
            if imported:
                current = self._get_accounts_from_table()
                current.extend(imported)
                self._populate_accounts_table(current)

    def _export_accounts(self):
        accounts = self._get_accounts_from_table()
        if not accounts:
            QMessageBox.information(self, "Export Accounts", "No accounts configured in this profile to export.")
            return
        text_data = AccountManager.export_accounts_text(accounts)
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(text_data)
            QMessageBox.information(self, "Export Successful", f"Exported {len(accounts)} account(s) to clipboard!\n\nFormat: platform:username:password:totp")

    def _clear_all_accounts(self):
        accounts = self._get_accounts_from_table()
        if not accounts:
            return
        ans = QMessageBox.question(
            self, "Clear Accounts", f"Are you sure you want to remove all {len(accounts)} account(s) from this profile?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if ans == QMessageBox.StandardButton.Yes:
            self._populate_accounts_table([])

    def _populate_accounts_table(self, accounts: List[Dict[str, Any]]):
        self.loaded_accounts = list(accounts)

        # Update Overview Tab Summary Label
        if hasattr(self, "overview_acc_summary_label"):
            count = len(accounts)
            if count == 0:
                self.overview_acc_summary_label.setText("No accounts configured yet.")
                self.overview_acc_summary_label.setStyleSheet("font-weight: 700; color: #94a3b8; font-size: 12px;")
            else:
                auto_count = sum(1 for a in accounts if a.get("auto_login_on_launch"))
                auto_str = f" ({auto_count} with Auto-Login on Launch)" if auto_count else ""
                names = ", ".join(AccountManager.get_platform_info(a.get("platform", "custom"))['name'] for a in accounts[:3])
                if count > 3:
                    names += f", +{count - 3} more"
                self.overview_acc_summary_label.setText(f"✓ {count} account(s) configured: {names}{auto_str}")
                self.overview_acc_summary_label.setStyleSheet("font-weight: 700; color: #4ade80; font-size: 12px;")

        if not hasattr(self, "accounts_table"):
            return
        self.accounts_table.setRowCount(0)

        for row_idx, acc in enumerate(accounts):
            self.accounts_table.insertRow(row_idx)
            plat = acc.get("platform", "custom")
            plat_info = AccountManager.get_platform_info(plat)

            # Col 0: Platform badge
            item_plat = QTableWidgetItem(f"{plat_info['icon']} {plat_info['name']}")
            item_plat.setFlags(item_plat.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.accounts_table.setItem(row_idx, 0, item_plat)

            # Col 1: Label / Name
            item_name = QTableWidgetItem(acc.get("name", ""))
            self.accounts_table.setItem(row_idx, 1, item_name)

            # Col 2: Username / Email
            item_user = QTableWidgetItem(acc.get("username", ""))
            self.accounts_table.setItem(row_idx, 2, item_user)

            # Col 3: Password (Masked with copy action)
            pwd_raw = acc.get("password", "")
            pwd_display = "••••••••" if pwd_raw else "—"
            item_pwd = QTableWidgetItem(pwd_display)
            item_pwd.setData(Qt.ItemDataRole.UserRole, pwd_raw)
            item_pwd.setToolTip("Double click row to edit or click copy")
            self.accounts_table.setItem(row_idx, 3, item_pwd)

            # Col 4: 2FA / TOTP Live Preview
            totp_secret = acc.get("totp_secret", "")
            totp_display = "—"
            if totp_secret:
                code, rem = AccountManager.generate_totp_code(totp_secret)
                if code:
                    totp_display = f"{code[:3]} {code[3:]} ({rem}s)"
                else:
                    totp_display = "Invalid TOTP"
            item_totp = QTableWidgetItem(totp_display)
            item_totp.setData(Qt.ItemDataRole.UserRole, totp_secret)
            item_totp.setFlags(item_totp.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if totp_secret and totp_display != "Invalid TOTP":
                item_totp.setForeground(Qt.GlobalColor.green)
            self.accounts_table.setItem(row_idx, 4, item_totp)

            # Col 5: Auto-Login Status
            item_auto = QTableWidgetItem("✓ Enabled" if acc.get("auto_login_on_launch") else "—")
            item_auto.setFlags(item_auto.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if acc.get("auto_login_on_launch"):
                item_auto.setForeground(Qt.GlobalColor.cyan)
            self.accounts_table.setItem(row_idx, 5, item_auto)

            # Col 6: Action buttons container widget
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(4)

            # Copy Credentials Button
            copy_btn = QPushButton("📋")
            copy_btn.setToolTip("Copy Username:Password to Clipboard")
            copy_btn.setFixedSize(26, 24)
            copy_btn.clicked.connect(lambda checked, a=acc: self._copy_account_credentials(a))
            actions_layout.addWidget(copy_btn)

            # Copy TOTP code button
            if totp_secret:
                totp_btn = QPushButton("🔑")
                totp_btn.setToolTip("Copy Live 2FA / TOTP Code")
                totp_btn.setFixedSize(26, 24)
                totp_btn.clicked.connect(lambda checked, s=totp_secret: self._copy_totp_code(s))
                actions_layout.addWidget(totp_btn)

            # Edit Button
            edit_btn = QPushButton("✏️")
            edit_btn.setToolTip("Edit Account Details")
            edit_btn.setFixedSize(26, 24)
            edit_btn.clicked.connect(lambda checked, r=row_idx: self._open_account_editor(row_idx=r))
            actions_layout.addWidget(edit_btn)

            # Delete Button
            del_btn = QPushButton("🗑")
            del_btn.setToolTip("Delete Account")
            del_btn.setFixedSize(26, 24)
            del_btn.setProperty("class", "DangerButton")
            del_btn.clicked.connect(lambda checked, r=row_idx: self._delete_account_at(r))
            actions_layout.addWidget(del_btn)

            self.accounts_table.setCellWidget(row_idx, 6, actions_widget)

    def _copy_account_credentials(self, account: Dict[str, Any]):
        u = account.get("username", "")
        p = account.get("password", "")
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(f"{u}:{p}")
            QMessageBox.information(self, "Copied", f"Copied credentials for '{account.get('name', u)}' to clipboard.")

    def _copy_totp_code(self, totp_secret: str):
        code, _ = AccountManager.generate_totp_code(totp_secret)
        if code:
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(code)
                QMessageBox.information(self, "2FA Copied", f"Copied 6-digit TOTP code: {code[:3]} {code[3:]}")
        else:
            QMessageBox.warning(self, "2FA Error", "Could not generate TOTP code. Check secret key.")

    def _update_live_totp_display(self):
        """Timer callback to refresh live TOTP codes in table every second."""
        if not hasattr(self, "accounts_table") or self.accounts_table.rowCount() == 0:
            return

        for row in range(self.accounts_table.rowCount()):
            item_totp = self.accounts_table.item(row, 4)
            if item_totp:
                secret = item_totp.data(Qt.ItemDataRole.UserRole)
                if secret:
                    code, rem = AccountManager.generate_totp_code(str(secret))
                    if code:
                        item_totp.setText(f"{code[:3]} {code[3:]} ({rem}s)")
                        item_totp.setForeground(Qt.GlobalColor.green)

    def _delete_account_at(self, row_idx: int):
        accounts = self._get_accounts_from_table()
        if 0 <= row_idx < len(accounts):
            acc_name = accounts[row_idx].get("name", "this account")
            ans = QMessageBox.question(
                self, "Delete Account", f"Are you sure you want to delete '{acc_name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if ans == QMessageBox.StandardButton.Yes:
                accounts.pop(row_idx)
                self._populate_accounts_table(accounts)

    def _get_accounts_from_table(self) -> List[Dict[str, Any]]:
        accounts = []
        if not hasattr(self, "accounts_table"):
            return self.loaded_accounts

        for r in range(self.accounts_table.rowCount()):
            base_acc = self.loaded_accounts[r] if r < len(self.loaded_accounts) else {}
            acc_dict = dict(base_acc)

            item_name = self.accounts_table.item(r, 1)
            item_user = self.accounts_table.item(r, 2)
            item_pwd = self.accounts_table.item(r, 3)
            item_totp = self.accounts_table.item(r, 4)

            if item_name:
                acc_dict["name"] = item_name.text().strip()
            if item_user:
                acc_dict["username"] = item_user.text().strip()
            if item_pwd:
                raw_p = item_pwd.data(Qt.ItemDataRole.UserRole)
                if raw_p is not None:
                    acc_dict["password"] = str(raw_p)
            if item_totp:
                raw_s = item_totp.data(Qt.ItemDataRole.UserRole)
                if raw_s is not None:
                    acc_dict["totp_secret"] = str(raw_s)

            accounts.append(acc_dict)

        return accounts

    def _create_behavior_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # 1. History & Session Group
        hist_box = QGroupBox("◷ Browser History & Session (Chronik & Sitzungsverwaltung)")
        hist_layout = QVBoxLayout(hist_box)
        hist_layout.setSpacing(8)

        self.save_history_cb = QCheckBox("Enable Browsing History (Browser-Chronik & besuchte Webseiten speichern)")
        self.save_history_cb.setToolTip("When disabled, browsing history is not retained across sessions.")
        self.save_history_cb.setChecked(False)
        hist_layout.addWidget(self.save_history_cb)

        self.search_suggestions_cb = QCheckBox("Enable Search & Address Bar Suggestions (Suchvorschläge & Autovervollständigung in Adressleiste)")
        self.search_suggestions_cb.setToolTip("Offers search and URL autocomplete suggestions in the address bar.")
        self.search_suggestions_cb.setChecked(False)
        hist_layout.addWidget(self.search_suggestions_cb)

        self.restore_session_cb = QCheckBox("Restore Open Tabs on Startup (Letzte geöffnete Tabs beim Start wiederherstellen)")
        self.restore_session_cb.setToolTip("Restores previous session tabs upon opening the browser profile.")
        self.restore_session_cb.setChecked(False)
        hist_layout.addWidget(self.restore_session_cb)

        layout.addWidget(hist_box)

        # 2. Autofill & Form History Group
        auto_box = QGroupBox(" Autofill & Form History (Autovervollständigung & Formulardaten)")
        auto_layout = QVBoxLayout(auto_box)
        auto_layout.setSpacing(8)

        self.form_autofill_cb = QCheckBox("Enable Form & Word Autocomplete (Wörter, E-Mails & Eingabeverlauf merken)")
        self.form_autofill_cb.setToolTip("Remembers entered words, emails, and form inputs to provide auto-suggestions.")
        self.form_autofill_cb.setChecked(False)
        auto_layout.addWidget(self.form_autofill_cb)

        self.password_manager_cb = QCheckBox("Enable Password Manager (Anmeldedaten & Passwörter speichern anbieten)")
        self.password_manager_cb.setToolTip("Offers to remember logins and passwords across websites.")
        self.password_manager_cb.setChecked(False)
        auto_layout.addWidget(self.password_manager_cb)

        row_auto = QHBoxLayout()
        self.address_autofill_cb = QCheckBox("Address Autofill (Postanschriften automatisch ausfüllen)")
        self.address_autofill_cb.setChecked(False)
        row_auto.addWidget(self.address_autofill_cb)

        self.credit_card_autofill_cb = QCheckBox("Credit Card Autofill (Zahlungsdaten automatisch ausfüllen)")
        self.credit_card_autofill_cb.setChecked(False)
        row_auto.addWidget(self.credit_card_autofill_cb)
        auto_layout.addLayout(row_auto)

        layout.addWidget(auto_box)

        # 3. Storage, Cache & Cleanup Group
        store_box = QGroupBox("⭳ Cache, Storage & Cleanup (Speicher & Bereinigung)")
        store_layout = QVBoxLayout(store_box)
        store_layout.setSpacing(8)

        row_store = QHBoxLayout()
        self.disk_cache_cb = QCheckBox("Disk Cache (Festplatten-Cache für schnellere Ladezeiten)")
        self.disk_cache_cb.setChecked(False)
        row_store.addWidget(self.disk_cache_cb)

        self.offline_storage_cb = QCheckBox("IndexedDB & Offline Storage (Webseiten-Speicher & Service Worker)")
        self.offline_storage_cb.setChecked(False)
        row_store.addWidget(self.offline_storage_cb)
        store_layout.addLayout(row_store)

        self.clear_on_close_cb = QCheckBox("⎚ Clear Temporary Cache on Browser Close (Automatisch bereinigen beim Beenden)")
        self.clear_on_close_cb.setToolTip("Automatically clears cache and temporary data upon closing the browser.")
        self.clear_on_close_cb.setChecked(False)
        store_layout.addWidget(self.clear_on_close_cb)

        layout.addWidget(store_box)

        # 4. Multimedia & Privacy Group
        media_box = QGroupBox("⛊ Multimedia & Telemetry Protection (Medien & Telemetrie)")
        media_layout = QVBoxLayout(media_box)
        media_layout.setSpacing(8)

        row_med = QHBoxLayout()
        self.block_telemetry_cb = QCheckBox("Block Mozilla / Google Telemetry & Crash Reports")
        self.block_telemetry_cb.setChecked(True)
        row_med.addWidget(self.block_telemetry_cb)

        self.drm_widevine_cb = QCheckBox("Enable DRM Widevine Sandbox (Spotify Web Player & DRM Media Decryption)")
        self.drm_widevine_cb.setToolTip("Enables isolated Widevine CDM within this profile directory behind the proxy tunnel. Leave disabled for maximum anti-detect privacy (TikTok and general video playback work natively without DRM).")
        self.drm_widevine_cb.setChecked(True)
        row_med.addWidget(self.drm_widevine_cb)
        media_layout.addLayout(row_med)

        row_ap = QHBoxLayout()
        row_ap.addWidget(QLabel("Media Autoplay Policy:"))
        self.autoplay_combo = QComboBox()
        self.autoplay_combo.addItem("Block All Media Autoplay (Standard)", "block_all")
        self.autoplay_combo.addItem("Block Audio Autoplay Only", "block_audio")
        self.autoplay_combo.addItem("Allow Autoplay", "allow")
        row_ap.addWidget(self.autoplay_combo)
        media_layout.addLayout(row_ap)

        layout.addWidget(media_box)
        layout.addStretch()

        return widget

    def _create_sandbox_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Host Capability Status Box
        status_box = QGroupBox("Host Virtualization & System Capability Detector")
        status_box_layout = QVBoxLayout(status_box)

        caps_layout = QHBoxLayout()

        self.caps_status_label = QLabel()
        self.caps_status_label.setStyleSheet("color: #a0aec0; font-family: monospace; font-size: 11px;")
        self._refresh_caps_label()
        caps_layout.addWidget(self.caps_status_label, stretch=1)

        btn_box = QVBoxLayout()
        btn_text = "⭍ Setup / Verify Sandbox Readiness" if sys.platform == "win32" else "⭍ Auto-Install Sandbox Dependencies"
        self.install_deps_btn = QPushButton(btn_text)
        self.install_deps_btn.setProperty("class", "PrimaryButton")
        self.install_deps_btn.clicked.connect(self._on_install_sandbox_deps_clicked)
        btn_box.addWidget(self.install_deps_btn)

        rescan_btn = QPushButton("⟳ Re-Scan System")
        rescan_btn.setProperty("class", "SecondaryButton")
        rescan_btn.clicked.connect(self._refresh_caps_label)
        btn_box.addWidget(rescan_btn)

        caps_layout.addLayout(btn_box)
        status_box_layout.addLayout(caps_layout)
        layout.addWidget(status_box)

        # Sandbox Mode Selection
        sb_group = QGroupBox("Sandbox Virtualization Mode")
        sb_layout = QVBoxLayout(sb_group)

        sb_layout.addWidget(QLabel("Isolation Type:"))
        self.sandbox_mode_combo = QComboBox()
        if sys.platform == "win32":
            self.sandbox_mode_combo.addItem("⊘ Native Windows Process Sandbox (Direct Local CDP - Default)", "off")
            self.sandbox_mode_combo.addItem("⛢ Container Sandbox (Docker Desktop / Podman - Optional)", "container")
            self.sandbox_mode_combo.addItem("⭍ MicroVM Hardware Virtualization (Linux / WSL2 Only)", "microvm")
        else:
            self.sandbox_mode_combo.addItem("⊘ Native Host Process (Direct Local CDP - Primary Default)", "off")
            self.sandbox_mode_combo.addItem("⭍ MicroVM Hardware Virtualization (Optional)", "microvm")
            self.sandbox_mode_combo.addItem("⛢ Container Sandbox (Podman / Docker - Optional)", "container")
        sb_layout.addWidget(self.sandbox_mode_combo)

        sb_layout.addWidget(QLabel("MicroVM Engine:"))
        self.microvm_engine_combo = QComboBox()
        self.microvm_engine_combo.addItem("☁ Cloud-Hypervisor (Recommended - Boot <50ms)", "cloud-hypervisor")
        self.microvm_engine_combo.addItem("⚑ Firecracker MicroVM (Hardware KVM Isolation)", "firecracker")
        self.microvm_engine_combo.addItem("⏣ QEMU MicroVM (Fallback)", "qemu")
        sb_layout.addWidget(self.microvm_engine_combo)

        self.use_virtiofs_cb = QCheckBox("⫸ Enable Virtiofs Daemon (virtiofsd) Zero-Copy Shared Filesystem")
        self.use_virtiofs_cb.setChecked(True)
        sb_layout.addWidget(self.use_virtiofs_cb)

        sb_layout.addWidget(QLabel("OCI Container Runtime Engine:"))
        self.oci_runtime_combo = QComboBox()
        self.oci_runtime_combo.addItem("⭍ Standard OCI Runtime (crun / runc)", "auto")
        self.oci_runtime_combo.addItem("⛊ gVisor Syscall Sandbox (runsc)", "runsc")
        sb_layout.addWidget(self.oci_runtime_combo)

        # Ephemeral RAM & Forensic Storage Group
        ephemeral_group = QGroupBox("⭳ Forensische Sicherheit & Flüchtiger Storage")
        eph_layout = QVBoxLayout(ephemeral_group)
        eph_layout.setSpacing(8)

        self.ephemeral_ram_cb = QCheckBox("⭳ Ephemeral RAM Profile (tmpfs RAM-Disk + Shredding / 0 Spuren auf NVMe)")
        self.ephemeral_ram_cb.setStyleSheet("font-weight: 700; color: #34d399;")
        eph_layout.addWidget(self.ephemeral_ram_cb)

        self.encrypted_cb = QCheckBox("⚿ Zero-Knowledge Profile Encryption (Argon2id KDF + AES-256-GCM AEAD)")
        self.encrypted_cb.setStyleSheet("font-weight: 700; color: #fbbf24;")
        eph_layout.addWidget(self.encrypted_cb)

        gpu_info_label = QLabel(
            "✜ Native GPU & Driver Emulation: Synchronized with 'Stealth & Fingerprint' tab (WebGL Vendor & Renderer).\n"
            "⛊ Zero Traces: Ephemeral RAM Profiles overwrite and shred memory prior to unmounting."
        )
        gpu_info_label.setStyleSheet("color: #38bdf8; font-size: 11px; background-color: rgba(14, 18, 29, 0.85); border: 1px solid rgba(255, 255, 255, 0.08); padding: 8px; border-radius: 6px;")
        eph_layout.addWidget(gpu_info_label)

        sb_layout.addWidget(ephemeral_group)

        self.isolate_net_cb = QCheckBox("Enforce Network Namespace Proxy Routing")
        self.isolate_net_cb.setChecked(True)
        sb_layout.addWidget(self.isolate_net_cb)

        layout.addWidget(sb_group)
        layout.addStretch()
        return widget

    def _refresh_caps_label(self):
        from engine.sandbox.sandbox_installer import SandboxInstaller
        caps = SandboxManager.check_system_capabilities()
        if sys.platform == "win32":
            has_oci = caps.get("podman") or caps.get("docker")
            has_wsl = caps.get("wsl")
            status_text = (
                f"• Windows Process Sandbox: ✓ Native Active (Direct Local CDP & Job Object)\n"
                f"• Ephemeral RAM Storage: {'✓ Available (Auto-Shredded Temp RAM)' if caps.get('tmpfs_ram') else ' Unsupported'}\n"
                f"• Camoufox C++ Engine: ✓ Stealth Hardened Native\n"
                f"• Docker Desktop / Podman: {'✓ Available' if has_oci else ' Optional (Not Installed)'}\n"
                f"• WSL2 Virtualization: {'✓ Supported' if has_wsl else ' Not Found'}\n"
                f"• Linux KVM MicroVMs: N/A on Windows (Windows Process & Docker used)"
            )
        else:
            has_runsc = SandboxInstaller.is_runsc_available()
            status_text = (
                f"• Cloud-Hypervisor: {'✓ Available' if caps.get('cloud_hypervisor') else ' Not Found'}\n"
                f"• Firecracker MicroVM: {'✓ Available' if caps.get('firecracker') else ' Not Found'}\n"
                f"• Virtiofs Daemon (virtiofsd): {'✓ Available' if caps.get('virtiofsd') else ' Not Found'}\n"
                f"• KVM Hardware Virtualization (/dev/kvm): {'✓ Supported' if caps['kvm'] else ' Unsupported / Disabled'}\n"
                f"• Ephemeral RAM Storage (tmpfs): {'✓ Available' if caps.get('tmpfs_ram') else ' Unsupported'}\n"
                f"• Podman / Docker: {'✓ Available' if caps['podman'] or caps['docker'] else ' Not Found'}\n"
                f"• gVisor Syscall Sandbox (runsc): {'✓ Available' if has_runsc else ' Not Found'}"
            )
        if hasattr(self, "caps_status_label"):
            self.caps_status_label.setText(status_text)

    @qasync.asyncSlot()
    async def _on_install_sandbox_deps_clicked(self):
        is_win = sys.platform == "win32"
        self.install_deps_btn.setEnabled(False)
        self.install_deps_btn.setText("⌛ Verifying Environment..." if is_win else "⌛ Installing Dependencies...")
        try:
            ok, msg = await SandboxInstaller.install_missing_dependencies()
            if ok:
                title = "Windows Sandbox Ready" if is_win else "Installation Completed"
                QMessageBox.information(self, title, f"Sandbox Status:\n\n{msg.replace(' | ', '\n')}")
            else:
                QMessageBox.warning(self, "Installation Status", f"Result: {msg}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to verify dependencies: {e}")
        finally:
            self.install_deps_btn.setEnabled(True)
            self.install_deps_btn.setText("⭍ Setup / Verify Sandbox Readiness" if is_win else "⭍ Auto-Install Sandbox Dependencies")
            self._refresh_caps_label()

    def _load_data(self):
        d = self.profile_data
        self.name_input.setText(d.get("name", ""))
        self.group_input.setText(d.get("group", "Default"))
        self.tags_input.setText(", ".join(d.get("tags", [])))
        self.start_url_input.setText(d.get("start_url", ""))
        self.notes_input.setText(d.get("notes", ""))

        engine_val = d.get("engine", "camoufox")
        idx = self.engine_combo.findData(engine_val)
        if idx >= 0:
            self.engine_combo.setCurrentIndex(idx)

        # Proxy & Geo
        p = d.get("proxy", {})
        self.proxy_enable_cb.setChecked(p.get("enabled", False))
        self._on_proxy_enable_toggled(p.get("enabled", False))
        self.proxy_type_combo.setCurrentText(p.get("type", "http"))
        self.proxy_host_input.setText(p.get("host", ""))
        self.proxy_port_spin.setValue(p.get("port", 8080))
        self.proxy_user_input.setText(p.get("username", ""))
        self.proxy_pass_input.setText(p.get("password", ""))
        self.auto_tz_cb.setChecked(p.get("auto_timezone", True))
        self.auto_lang_cb.setChecked(p.get("auto_language", True))
        self.auto_geo_cb.setChecked(p.get("auto_geolocation", True))
        self.killswitch_cb.setChecked(d.get("network_killswitch", True))
        self.burst_prot_cb.setChecked(p.get("burst_protection", True))
        self.burst_ms_spin.setValue(int(p.get("burst_stagger_ms", 20)))

        # Sync and populate Proxy Pool selection
        self._populate_proxy_pool_combo()

        tls_val = d.get("tls_ja3_preset", "auto")
        tls_idx = self.tls_preset_combo.findData(tls_val)
        if tls_idx >= 0:
            self.tls_preset_combo.setCurrentIndex(tls_idx)

        loc = d.get("location", {})
        self.geo_country_input.setText(loc.get("country", ""))
        self.geo_region_input.setText(loc.get("region", ""))
        self.geo_city_input.setText(loc.get("city", ""))
        self.geo_zip_input.setText(loc.get("postal_code", ""))
        self.geo_lat_spin.setValue(float(loc.get("lat", 0.0)))
        self.geo_lon_spin.setValue(float(loc.get("lon", 0.0)))

        # Hardware & OS
        self.os_combo.setCurrentText(d.get("os", "windows"))
        self.device_vendor_input.setText(d.get("device_vendor", "Google"))
        self.device_model_input.setText(d.get("device_model", "PC"))
        custom_ua = bool(d.get("custom_user_agent", False))
        self.custom_ua_cb.setChecked(custom_ua)
        self._toggle_custom_ua(custom_ua)
        if custom_ua:
            self.ua_input.setText(d.get("user_agent", ""))
        else:
            self.ua_input.setText(config.get_default_user_agent(d.get("os", "windows"), d.get("engine", "camoufox")))
        self.res_combo.setCurrentText(d.get("screen_resolution", "1920x1080"))
        self.color_depth_combo.setCurrentText(str(d.get("color_depth", 24)))
        self.touch_points_spin.setValue(d.get("max_touch_points", 0))
        self.cpu_spin.setValue(d.get("hardware_concurrency", 8))
        self.ram_spin.setValue(d.get("device_memory", 8))

        win_mode = d.get("window_mode", "tile_grid")
        win_idx = self.win_mode_combo.findData(win_mode)
        if win_idx >= 0:
            self.win_mode_combo.setCurrentIndex(win_idx)
        self.win_width_spin.setValue(int(d.get("window_width") or 1280))
        self.win_height_spin.setValue(int(d.get("window_height") or 720))
        self.win_pos_x_spin.setValue(int(d.get("window_pos_x") or 0))
        self.win_pos_y_spin.setValue(int(d.get("window_pos_y") or 0))

        # Stealth
        s = d.get("stealth", {})
        fp_engine = s.get("fp_engine", "real_presets")
        fp_idx = self.fp_engine_combo.findData(fp_engine)
        if fp_idx >= 0:
            self.fp_engine_combo.setCurrentIndex(fp_idx)

        # WebGL Hardware Spoofing & Presets
        prof_os = d.get("os", "windows").lower()
        self._populate_webgl_presets(prof_os, select_default=False)

        v = s.get("webgl_vendor") or d.get("webgl_vendor") or ""
        r = s.get("webgl_renderer") or d.get("webgl_renderer") or ""
        
        # Check explicit webgl_spoofing boolean
        if "webgl_spoofing" in s:
            webgl_spoof_enabled = bool(s["webgl_spoofing"])
        elif "webgl_spoofing" in d:
            webgl_spoof_enabled = bool(d["webgl_spoofing"])
        else:
            webgl_mode = str(s.get("webgl_mode") or d.get("webgl_mode") or "spoof").lower()
            webgl_spoof_enabled = webgl_mode not in ["real", "off", "disabled", "unspoofed"]

        if webgl_spoof_enabled and not v and not r:
            presets = config.get_webgl_presets_for_os(prof_os)
            if presets:
                v = presets[0]["vendor"]
                r = presets[0]["renderer"]

        self.webgl_spoof_cb.blockSignals(True)
        self.webgl_spoof_cb.setChecked(webgl_spoof_enabled)
        self.webgl_spoof_cb.blockSignals(False)

        self.webgl_vendor_input.setText(v)
        self.webgl_renderer_input.setText(r)
        self._on_webgl_spoof_toggled(webgl_spoof_enabled)
        self._sync_webgl_combo_selection(v, r, webgl_spoof_enabled)

        self.webgpu_cb.setChecked(s.get("webgpu_supported", False))
        self.canvas_noise_cb.setChecked(s.get("canvas_noise", True))
        self.audio_noise_cb.setChecked(s.get("audio_noise", True))
        self.client_rects_noise_cb.setChecked(s.get("client_rects_noise", True))
        self.font_noise_cb.setChecked(s.get("font_fingerprint_noise", True))
        self.noise_seed_input.setText(s.get("noise_seed", ""))
        
        raw_webrtc = s.get("webrtc_mode") or s.get("webrtc") or d.get("webrtc_mode") or d.get("webrtc") or "altered"
        if isinstance(raw_webrtc, bool):
            webrtc_val = "altered" if raw_webrtc else "disabled"
        else:
            raw_str = str(raw_webrtc).lower().strip()
            if raw_str in ["altered", "spoof", "spoofed", "protocol_spoofing", "proxy"]:
                webrtc_val = "altered"
            elif raw_str in ["disabled", "block", "blocked", "off", "disable", "none"]:
                webrtc_val = "disabled"
            elif raw_str in ["real", "raw", "leak", "enabled", "on", "default"]:
                webrtc_val = "real"
            else:
                webrtc_val = "altered"

        webrtc_idx = self.webrtc_combo.findData(webrtc_val)
        if webrtc_idx >= 0:
            self.webrtc_combo.setCurrentIndex(webrtc_idx)

        # Sandbox Settings
        sb = d.get("sandbox", {})
        sb_mode = sb.get("mode", "off")
        sb_idx = self.sandbox_mode_combo.findData(sb_mode)
        if sb_idx >= 0:
            self.sandbox_mode_combo.setCurrentIndex(sb_idx)

        m_engine = sb.get("microvm_engine", "cloud-hypervisor")
        m_idx = self.microvm_engine_combo.findData(m_engine)
        if m_idx >= 0:
            self.microvm_engine_combo.setCurrentIndex(m_idx)

        self.use_virtiofs_cb.setChecked(sb.get("use_virtiofs", True))

        oci_rt = sb.get("oci_runtime", "auto")
        oci_idx = self.oci_runtime_combo.findData(oci_rt)
        if oci_idx >= 0:
            self.oci_runtime_combo.setCurrentIndex(oci_idx)

        self.isolate_net_cb.setChecked(sb.get("isolate_network", True))

        # Ephemeral RAM & Zero-Knowledge Encryption Flags
        self.ephemeral_ram_cb.setChecked(d.get("ephemeral_ram", False))
        self.encrypted_cb.setChecked(d.get("encrypted", False))

        tz_val = d.get("timezone", "auto")
        tz_idx = self.tz_combo.findData(tz_val)
        if tz_idx < 0:
            tz_idx = self.tz_combo.findText(tz_val)
        if tz_idx < 0:
            for i in range(self.tz_combo.count()):
                item_data = str(self.tz_combo.itemData(i) or "")
                item_text = self.tz_combo.itemText(i)
                if tz_val and (tz_val.lower() == item_data.lower() or tz_val in item_text or item_data in tz_val):
                    tz_idx = i
                    break
        if tz_idx >= 0:
            self.tz_combo.setCurrentIndex(tz_idx)
        else:
            self.tz_combo.addItem(f" {tz_val}", tz_val)
            self.tz_combo.setCurrentIndex(self.tz_combo.count() - 1)

        self.lang_input.setText(d.get("language", "en-US,en;q=0.9"))
        # Load existing profile cookies (including live browser cookies) into In-App Editor & Table
        if d.get("id"):
            try:
                prof_path = self.profile_manager.get_profile_path(d["id"])
                c_list = CookieManager.get_profile_cookies(prof_path)
                if c_list:
                    self._populate_cookie_table(c_list, update_text_edit=True)
                else:
                    self._populate_cookie_table([], update_text_edit=True)
            except Exception:
                pass
        
        self._load_extensions_list()

        # Load existing profile accounts into visual Accounts & Logins table
        self._populate_accounts_table(d.get("accounts", []))

        # Behavior, History & Autofill
        beh = d.get("behavior", {})
        self.save_history_cb.setChecked(beh.get("save_history", False))
        self.search_suggestions_cb.setChecked(beh.get("search_suggestions", False))
        self.restore_session_cb.setChecked(beh.get("restore_session", False))
        self.form_autofill_cb.setChecked(beh.get("form_autofill", False))
        self.password_manager_cb.setChecked(beh.get("password_manager", False))
        self.address_autofill_cb.setChecked(beh.get("address_autofill", False))
        self.credit_card_autofill_cb.setChecked(beh.get("credit_card_autofill", False))
        self.disk_cache_cb.setChecked(beh.get("disk_cache", False))
        self.offline_storage_cb.setChecked(beh.get("offline_storage", False))
        self.clear_on_close_cb.setChecked(beh.get("clear_on_shutdown", False))
        self.block_telemetry_cb.setChecked(beh.get("block_telemetry", True))
        self.drm_widevine_cb.setChecked(beh.get("drm_widevine", True))
        ap_idx = self.autoplay_combo.findData(beh.get("autoplay_media", "block_all"))
        if ap_idx >= 0:
            self.autoplay_combo.setCurrentIndex(ap_idx)

        self._update_fingerprint_preview()

    def get_profile_data(self) -> Dict[str, Any]:
        d = dict(self.profile_data)
        d["name"] = self.name_input.text().strip() or "Unnamed Profile"
        engine_data = self.engine_combo.currentData()
        if not engine_data:
            txt = self.engine_combo.currentText().lower()
            if "nodriver" in txt:
                engine_data = "nodriver"
            elif "driverless" in txt:
                engine_data = "selenium_driverless"
            elif "playwright" in txt:
                engine_data = "playwright"
            else:
                engine_data = "camoufox"
        d["engine"] = engine_data
        d["group"] = self.group_input.text().strip() or "Default"
        d["tags"] = [t.strip() for t in self.tags_input.text().split(",") if t.strip()]
        d["start_url"] = self.start_url_input.text().strip()
        d["notes"] = self.notes_input.toPlainText()

        d["proxy"] = self._get_proxy_config_from_ui()
        if d["proxy"].get("enabled"):
            p_cfg = d["proxy"]
            p_info = dict(d.get("proxy_info") or {})
            if getattr(self, "_selected_proxy_id", None) and hasattr(self.proxy_manager, "get_proxy"):
                pool_p = self.proxy_manager.get_proxy(self._selected_proxy_id)
                if pool_p:
                    p_info.setdefault("ip", pool_p.get("ip") or pool_p.get("host"))
                    p_info.setdefault("country_code", pool_p.get("country", ""))
                    p_info.setdefault("country", pool_p.get("country", ""))
                    p_info.setdefault("city", pool_p.get("city", ""))
            if not p_info.get("ip"):
                p_info["ip"] = p_cfg.get("host", "")
            d["proxy_info"] = p_info
        else:
            d["proxy_info"] = {}
        d["network_killswitch"] = self.killswitch_cb.isChecked()
        d["tls_ja3_preset"] = self.tls_preset_combo.currentData() or "auto"

        d["ephemeral_ram"] = self.ephemeral_ram_cb.isChecked()
        d["encrypted"] = self.encrypted_cb.isChecked()

        d["accounts"] = self._get_accounts_from_table()

        d["location"] = {
            "country": self.geo_country_input.text().strip(),
            "region": self.geo_region_input.text().strip(),
            "city": self.geo_city_input.text().strip(),
            "postal_code": self.geo_zip_input.text().strip(),
            "lat": self.geo_lat_spin.value(),
            "lon": self.geo_lon_spin.value()
        }

        d["os"] = self.os_combo.currentText()
        d["device_vendor"] = self.device_vendor_input.text().strip()
        d["device_model"] = self.device_model_input.text().strip()
        d["custom_user_agent"] = self.custom_ua_cb.isChecked()
        if d["custom_user_agent"] and self.ua_input.text().strip():
            d["user_agent"] = self.ua_input.text().strip()
        else:
            d["user_agent"] = config.get_default_user_agent(d["os"], d["engine"])
        d["screen_resolution"] = self.res_combo.currentText()
        d["color_depth"] = int(self.color_depth_combo.currentText())
        d["max_touch_points"] = self.touch_points_spin.value()
        d["hardware_concurrency"] = self.cpu_spin.value()
        d["device_memory"] = self.ram_spin.value()
        d["window_mode"] = self.win_mode_combo.currentData() or "tile_grid"
        d["window_width"] = self.win_width_spin.value()
        d["window_height"] = self.win_height_spin.value()
        d["window_pos_x"] = self.win_pos_x_spin.value()
        d["window_pos_y"] = self.win_pos_y_spin.value()

        # Stealth & Fonts
        stealth = dict(d.get("stealth", {}))
        stealth["fp_engine"] = self.fp_engine_combo.currentData() or "real_presets"
        is_webgl_spoof = self.webgl_spoof_cb.isChecked()
        stealth["webgl_spoofing"] = is_webgl_spoof
        stealth["webgl_mode"] = "spoof" if is_webgl_spoof else "real"
        stealth["webgl_vendor"] = self.webgl_vendor_input.text().strip()
        stealth["webgl_renderer"] = self.webgl_renderer_input.text().strip()
        stealth["webgpu_supported"] = self.webgpu_cb.isChecked()
        stealth["canvas_noise"] = self.canvas_noise_cb.isChecked()
        stealth["audio_noise"] = self.audio_noise_cb.isChecked()
        stealth["client_rects_noise"] = self.client_rects_noise_cb.isChecked()
        stealth["font_fingerprint_noise"] = self.font_noise_cb.isChecked()
        stealth["noise_seed"] = self.noise_seed_input.text().strip()
        stealth["webrtc_mode"] = self.webrtc_combo.currentData() or "altered"

        d["stealth"] = stealth
        d["webgl_spoofing"] = is_webgl_spoof
        d["webgl_mode"] = "spoof" if is_webgl_spoof else "real"
        d["webgl_vendor"] = self.webgl_vendor_input.text().strip()
        d["webgl_renderer"] = self.webgl_renderer_input.text().strip()
        d["webrtc_mode"] = stealth["webrtc_mode"]

        # Sandbox
        d["sandbox"] = {
            "mode": self.sandbox_mode_combo.currentData() or "off",
            "microvm_engine": self.microvm_engine_combo.currentData() or "cloud-hypervisor",
            "use_virtiofs": self.use_virtiofs_cb.isChecked(),
            "oci_runtime": self.oci_runtime_combo.currentData() or "auto",
            "isolate_network": self.isolate_net_cb.isChecked()
        }

        auto_tz_val = self.auto_tz_cb.isChecked() if hasattr(self, "auto_tz_cb") else True
        d["auto_timezone"] = auto_tz_val
        p_info = getattr(self, "proxy_info", {}) or {}
        if auto_tz_val and getattr(self, "proxy_enable_cb", None) and self.proxy_enable_cb.isChecked() and p_info.get("timezone"):
            chosen_tz = p_info.get("timezone")
        else:
            chosen_tz = self.tz_combo.currentData()
            if not chosen_tz:
                raw_text = self.tz_combo.currentText().strip()
                if "(" in raw_text and ")" in raw_text:
                    for p in raw_text.split():
                        if "/" in p:
                            chosen_tz = p
                            break
                if not chosen_tz:
                    chosen_tz = raw_text or "auto"
        d["timezone"] = chosen_tz
        d["language"] = self.lang_input.text().strip() or "en-US,en;q=0.9"
        d["do_not_track"] = self.dnt_combo.currentData() or "null"

        # Extensions
        d["extensions"] = self._get_selected_extensions()

        # Behavior, History & Autofill
        d["behavior"] = {
            "save_history": self.save_history_cb.isChecked(),
            "search_suggestions": self.search_suggestions_cb.isChecked(),
            "restore_session": self.restore_session_cb.isChecked(),
            "form_autofill": self.form_autofill_cb.isChecked(),
            "password_manager": self.password_manager_cb.isChecked(),
            "address_autofill": self.address_autofill_cb.isChecked(),
            "credit_card_autofill": self.credit_card_autofill_cb.isChecked(),
            "disk_cache": self.disk_cache_cb.isChecked(),
            "offline_storage": self.offline_storage_cb.isChecked(),
            "clear_on_shutdown": self.clear_on_close_cb.isChecked(),
            "block_telemetry": self.block_telemetry_cb.isChecked(),
            "drm_widevine": self.drm_widevine_cb.isChecked(),
            "autoplay_media": self.autoplay_combo.currentData() or "allow"
        }
        return d

    def _save_and_accept(self):
        d = self.get_profile_data()
        self.profile_data.clear()
        self.profile_data.update(d)

        # Save profile
        success = self.profile_manager.save_profile(d)
        if not success:
            QMessageBox.warning(self, "Save Error", "Failed to save profile to disk.")
            return False

        # Extract active cookies (from visual table or raw text editor)
        cookies = self._get_cookies_from_table()
        if not cookies:
            raw_text = self.cookie_text_edit.toPlainText().strip()
            if raw_text:
                cookies = CookieManager.parse_cookie_text(raw_text)

        # Synchronize cookies to disk AND live SQLite databases in user_data
        prof_path = self.profile_manager.get_profile_path(d["id"])
        CookieManager.sync_cookies_to_profile(prof_path, cookies)

        self.accept()
        return True

    @qasync.asyncSlot()
    async def _save_and_launch(self):
        engine_type = self.profile_data.get("engine", "camoufox")
        from ui.views.browser_download_dialog import BrowserDownloadDialog
        if not BrowserDownloadDialog.ensure_engine_ready(self, engine_type):
            return

        if not self._save_and_accept():
            return
        if self.launcher and self.profile_data.get("id"):
            success, msg, _ = await self.launcher.launch_profile(self.profile_data["id"])
            if not success:
                QMessageBox.warning(self, "Launch Error", f"Could not launch profile: {msg}")
