from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QLineEdit, QComboBox, QCheckBox, QGroupBox,
    QFormLayout, QTextEdit, QMessageBox, QTabWidget, QWidget,
    QProgressBar
)
from PyQt6.QtGui import QIcon
import os
from PyQt6.QtCore import Qt
from typing import Optional, List, Dict
import random
import config
from storage.profile_manager import ProfileManager
from storage.proxy_manager import ProxyManager


class BatchProfileDialog(QDialog):
    """Advanced Batch Profile Generator Modal with customizable Random vs Fixed controls."""

    def __init__(self, profile_manager: ProfileManager, proxy_manager: Optional[ProxyManager] = None, parent=None):
        super().__init__(parent)
        self.profile_manager = profile_manager
        self.proxy_manager = proxy_manager or ProxyManager()

        self.setWindowTitle(f"Batch Profile Generator - {config.APP_NAME}")
        self.resize(780, 640)
        self.setMinimumSize(720, 580)
        self._init_ui()

    def _get_icon(self, name):
        return QIcon(os.path.join(os.path.dirname(__file__), "..", "assets", "icons", f"{name}.svg"))

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(14)

        # Header Title Banner
        header_layout = QHBoxLayout()
        title_label = QLabel("Batch Profile Creator & Fingerprint Generator")
        title_label.setStyleSheet("font-size: 17px; font-weight: 800; color: #f8fafc; letter-spacing: -0.3px;")
        
        subtitle = QLabel("Generate multiple isolated browser profiles with granular Fixed or Randomized parameters.")
        subtitle.setStyleSheet("color: #94a3b8; font-size: 11px;")
        
        header_vbox = QVBoxLayout()
        header_vbox.setSpacing(2)
        header_vbox.addWidget(title_label)
        header_vbox.addWidget(subtitle)
        main_layout.addLayout(header_vbox)

        tabs = QTabWidget()

        # Tab 1: General & Quantity
        tabs.addTab(self._create_general_tab(), "1. General & Naming")

        # Tab 2: OS, Engine & Resolution
        tabs.addTab(self._create_os_engine_tab(), "2. OS, Engine & Screen")

        # Tab 3: Hardware & WebGL
        tabs.addTab(self._create_hardware_tab(), "3. Hardware & GPU")

        # Tab 4: Proxy Assignment
        tabs.addTab(self._create_proxy_tab(), "4. Proxy Assignment")

        # Tab 5: Storage & Stealth
        tabs.addTab(self._create_storage_tab(), "5. Security & Storage")

        main_layout.addWidget(tabs)

        # Progress Bar for batch generation
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(18)
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        # Bottom Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "SecondaryButton")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        self.btn_generate = QPushButton(" Generate Profiles Now")
        self.btn_generate.setIcon(self._get_icon("zap"))
        self.btn_generate.setProperty("class", "PrimaryButton")
        self.btn_generate.clicked.connect(self._on_generate_clicked)
        btn_layout.addWidget(self.btn_generate)

        main_layout.addLayout(btn_layout)

    def _create_general_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # Quantity & Naming Group
        qty_group = QGroupBox("Quantity & Profile Naming Pattern")
        qty_layout = QFormLayout(qty_group)
        qty_layout.setSpacing(10)

        self.spin_count = QSpinBox()
        self.spin_count.setRange(1, 200)
        self.spin_count.setValue(5)
        self.spin_count.setSuffix(" Profiles")
        self.spin_count.valueChanged.connect(self._update_name_preview)
        qty_layout.addRow(QLabel("Profile Count:"), self.spin_count)

        self.txt_prefix = QLineEdit("Profile")
        self.txt_prefix.setPlaceholderText("e.g. Account, Worker, Scraping, Profile")
        self.txt_prefix.textChanged.connect(self._update_name_preview)
        qty_layout.addRow(QLabel("Name Prefix:"), self.txt_prefix)

        self.combo_naming_pattern = QComboBox()
        self.combo_naming_pattern.addItem("Prefix + #Number (z.B. Profile #1, Profile #2)", "num_hash")
        self.combo_naming_pattern.addItem("Prefix + 01, 02 Padded (z.B. Profile 01, Profile 02)", "num_pad")
        self.combo_naming_pattern.addItem("Prefix + Random Hex Hash (z.B. Profile-8a3f9e)", "hex_hash")
        self.combo_naming_pattern.addItem("Prefix + Random Persona Name (z.B. Profile Alex, Profile Jordan)", "persona")
        self.combo_naming_pattern.currentIndexChanged.connect(self._update_name_preview)
        qty_layout.addRow(QLabel("Naming Style:"), self.combo_naming_pattern)

        self.lbl_preview = QLabel("Preview: Profile #1 ... Profile #5")
        self.lbl_preview.setStyleSheet("color: #38bdf8; font-weight: 700; font-size: 11px;")
        qty_layout.addRow(QLabel("Name Preview:"), self.lbl_preview)

        layout.addWidget(qty_group)

        # Folder & Grouping Group
        grp_group = QGroupBox("Folder / Group & Organization")
        grp_layout = QFormLayout(grp_group)
        grp_layout.setSpacing(10)

        self.txt_group = QLineEdit("Default")
        self.txt_group.setPlaceholderText("e.g. Batch-2026, Socials, Scraping Pool")
        grp_layout.addRow(QLabel("Group / Folder:"), self.txt_group)

        self.txt_tags = QLineEdit("Batch")
        self.txt_tags.setPlaceholderText("Comma separated tags, e.g. batch, eu, verified")
        grp_layout.addRow(QLabel("Tags:"), self.txt_tags)

        self.txt_start_url = QLineEdit("")
        self.txt_start_url.setPlaceholderText("e.g. https://google.com (optional)")
        grp_layout.addRow(QLabel("Start URL / Homepage:"), self.txt_start_url)

        layout.addWidget(grp_group)
        layout.addStretch()
        return widget

    def _create_os_engine_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # OS & User Agent
        os_group = QGroupBox("Operating System & Platform Fingerprint")
        os_layout = QFormLayout(os_group)
        os_layout.setSpacing(10)

        self.combo_os = QComboBox()
        self.combo_os.addItem("Random (All: Windows / macOS / Linux / Android)", "random_all")
        self.combo_os.addItem("Random Desktop Only (Windows / macOS)", "random_desktop")
        self.combo_os.addItem("Fixed: Windows 11 (Desktop)", "windows")
        self.combo_os.addItem("[Apple] Fixed: macOS Sequoia (Desktop)", "mac")
        self.combo_os.addItem("Fixed: Linux x86_64 (Desktop)", "linux")
        self.combo_os.addItem("[Mobile] Fixed: Android 14 Mobile", "android")
        os_layout.addRow(QLabel("OS Selection:"), self.combo_os)

        layout.addWidget(os_group)

        # Browser Engine
        engine_group = QGroupBox("Browser Engine & Automation Framework")
        eng_layout = QFormLayout(engine_group)
        eng_layout.setSpacing(10)

        self.combo_engine = QComboBox()
        self.combo_engine.addItem("Fixed: Playwright (Async Stealth Engine - Recommended)", "playwright")
        self.combo_engine.addItem("Fixed: Camoufox (C++ Native Firefox Anti-Detect)", "camoufox")
        self.combo_engine.addItem("Fixed: Selenium Driverless", "selenium_driverless")
        self.combo_engine.addItem("Fixed: Nodriver (Stealth CDP Engine)", "nodriver")
        self.combo_engine.addItem("Random: Evenly distribute across Playwright & Camoufox", "random_dist")
        eng_layout.addRow(QLabel("Engine Mode:"), self.combo_engine)

        layout.addWidget(engine_group)

        # Screen Resolution
        res_group = QGroupBox("Screen Resolution & Viewport")
        res_layout = QFormLayout(res_group)
        res_layout.setSpacing(10)

        self.combo_res = QComboBox()
        self.combo_res.addItem("Random Realistic Resolutions (FHD, QHD, 1536x864, etc.)", "random")
        self.combo_res.addItem("Fixed: 1920x1080 (FHD Standard)", "1920x1080")
        self.combo_res.addItem("Fixed: 2560x1440 (2K / QHD)", "2560x1440")
        self.combo_res.addItem("Fixed: 1440x900 (MacBook Standard)", "1440x900")
        self.combo_res.addItem("Fixed: 1366x768 (Laptop Standard)", "1366x768")
        self.combo_res.addItem("Fixed: 3840x2160 (4K UHD)", "3840x2160")
        res_layout.addRow(QLabel("Screen Resolution:"), self.combo_res)

        layout.addWidget(res_group)
        layout.addStretch()
        return widget

    def _create_hardware_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        hw_group = QGroupBox("Hardware Concurrency & RAM Specs")
        hw_layout = QFormLayout(hw_group)
        hw_layout.setSpacing(10)

        self.combo_cpu = QComboBox()
        self.combo_cpu.addItem("Random Realistic (4, 8, 12, 16 Cores)", "random")
        self.combo_cpu.addItem("Fixed: 4 Cores", "4")
        self.combo_cpu.addItem("Fixed: 8 Cores (Recommended)", "8")
        self.combo_cpu.addItem("Fixed: 12 Cores", "12")
        self.combo_cpu.addItem("Fixed: 16 Cores", "16")
        hw_layout.addRow(QLabel("CPU Hardware Cores:"), self.combo_cpu)

        self.combo_ram = QComboBox()
        self.combo_ram.addItem("Random Realistic (8, 16, 32 GB RAM)", "random")
        self.combo_ram.addItem("Fixed: 8 GB RAM", "8")
        self.combo_ram.addItem("Fixed: 16 GB RAM (Recommended)", "16")
        self.combo_ram.addItem("Fixed: 32 GB RAM", "32")
        hw_layout.addRow(QLabel("Device Memory (RAM):"), self.combo_ram)

        layout.addWidget(hw_group)

        gpu_group = QGroupBox("WebGL Vendor & GPU Renderer Emulation")
        gpu_layout = QFormLayout(gpu_group)
        gpu_layout.setSpacing(10)

        self.combo_gpu = QComboBox()
        self.combo_gpu.addItem("🚫 Kein WebGL Spoofing (100% Original Hardware / Unmasked)", "unspoofed")
        self.combo_gpu.addItem("⚡ Native Host Hardware (Echte WebGL-Hardware-Daten)", "native")
        self.combo_gpu.addItem("Random Match based on OS (NVIDIA/AMD/Apple)", "random_matched")
        self.combo_gpu.addItem("Fixed: NVIDIA GeForce RTX 4090", "rtx4090")
        self.combo_gpu.addItem("Fixed: NVIDIA GeForce RTX 4080", "rtx4080")
        self.combo_gpu.addItem("Fixed: NVIDIA GeForce RTX 4070", "rtx4070")
        self.combo_gpu.addItem("Fixed: NVIDIA GeForce RTX 3060", "rtx3060")
        self.combo_gpu.addItem("[Apple] Fixed: Apple M3 Max", "m3max")
        self.combo_gpu.addItem("[Apple] Fixed: Apple M2 Max", "m2max")
        self.combo_gpu.addItem("Fixed: AMD Radeon RX 7900 XTX", "rx7900")
        self.combo_gpu.addItem("Fixed: Intel Iris Xe Graphics", "iris_xe")
        gpu_layout.addRow(QLabel("GPU Preset:"), self.combo_gpu)

        layout.addWidget(gpu_group)

        stealth_group = QGroupBox("Active Noise Injections & WebGPU (Anti-Fingerprinting)")
        st_layout = QVBoxLayout(stealth_group)
        st_layout.setSpacing(6)

        self.chk_canvas_noise = QCheckBox("Inject Canvas 2D Cryptographic Subpixel Noise")
        self.chk_canvas_noise.setChecked(True)
        self.chk_webgl_noise = QCheckBox("Inject WebGL 3D Shader Geometry & Float Noise")
        self.chk_webgl_noise.setChecked(True)
        self.chk_audio_noise = QCheckBox("Inject AudioContext Oscillator & Buffer Noise (natural_jitter)")
        self.chk_audio_noise.setChecked(True)
        self.chk_font_noise = QCheckBox("Inject C++ Font Spacing & Metric Noise (Subpixel Jitter)")
        self.chk_font_noise.setChecked(True)
        self.chk_client_rects_noise = QCheckBox("Inject ClientRects / DOM Bounding Box Noise")
        self.chk_client_rects_noise.setChecked(True)
        self.chk_webgpu = QCheckBox("Enable WebGPU API (Default: Disabled for Anti-Leak Protection)")
        self.chk_webgpu.setChecked(False)

        st_layout.addWidget(self.chk_canvas_noise)
        st_layout.addWidget(self.chk_webgl_noise)
        st_layout.addWidget(self.chk_audio_noise)
        st_layout.addWidget(self.chk_font_noise)
        st_layout.addWidget(self.chk_client_rects_noise)
        st_layout.addWidget(self.chk_webgpu)

        layout.addWidget(stealth_group)
        layout.addStretch()
        return widget

    def _create_proxy_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        p_group = QGroupBox("Proxy Assignment Strategy")
        p_layout = QFormLayout(p_group)
        p_layout.setSpacing(10)

        self.combo_proxy_mode = QComboBox()
        self.combo_proxy_mode.addItem("No Proxy (Direct Connection)", "none")
        self.combo_proxy_mode.addItem("Sequential from Proxy Pool (1 unique proxy per profile)", "pool_seq")
        self.combo_proxy_mode.addItem("Random from Proxy Pool", "pool_rand")
        self.combo_proxy_mode.addItem("Custom Paste Proxy List below", "custom_list")
        self.combo_proxy_mode.currentIndexChanged.connect(self._on_proxy_mode_changed)
        p_layout.addRow(QLabel("Assignment Mode:"), self.combo_proxy_mode)

        self.chk_auto_timezone = QCheckBox("Match Timezone automatically to Proxy Geolocation")
        self.chk_auto_timezone.setChecked(True)
        p_layout.addRow(self.chk_auto_timezone)

        self.chk_auto_geo = QCheckBox("Match Geolocation Lat/Lon automatically to Proxy IP")
        self.chk_auto_geo.setChecked(True)
        p_layout.addRow(self.chk_auto_geo)

        layout.addWidget(p_group)

        self.custom_proxy_box = QGroupBox("Paste Custom Proxy List (1 per line)")
        custom_layout = QVBoxLayout(self.custom_proxy_box)
        self.txt_custom_proxies = QTextEdit()
        self.txt_custom_proxies.setPlaceholderText(
            "Paste proxies (1 per line):\nhost:port\nhost:port:user:pass\nsocks5://user:pass@host:port"
        )
        self.txt_custom_proxies.setStyleSheet("background-color: rgba(10, 13, 22, 0.9); font-family: monospace; font-size: 11px;")
        custom_layout.addWidget(self.txt_custom_proxies)
        self.custom_proxy_box.setVisible(False)
        layout.addWidget(self.custom_proxy_box)

        layout.addStretch()
        return widget

    def _create_storage_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        sec_group = QGroupBox("Forensic Storage, TLS & WebRTC Mode")
        sec_layout = QFormLayout(sec_group)
        sec_layout.setSpacing(10)

        self.combo_storage = QComboBox()
        self.combo_storage.addItem("Standard Persistent Storage (NVMe / SSD UserData Directory)", "persistent")
        self.combo_storage.addItem("Ephemeral RAM Profile (tmpfs RAM-Disk / 0 traces on drive)", "ephemeral")
        self.combo_storage.addItem("Zero-Knowledge Encrypted (Argon2id + AES-256-GCM Vault)", "encrypted")
        sec_layout.addRow(QLabel("Storage Type:"), self.combo_storage)

        self.combo_tls = QComboBox()
        self.combo_tls.addItem("Auto-Match TLS JA3/JA4 Fingerprint to User-Agent", "auto")
        self.combo_tls.addItem("Chrome 132 TLS Profile", "chrome_132")
        self.combo_tls.addItem("Firefox 134 TLS Profile", "firefox_134")
        sec_layout.addRow(QLabel("TLS JA3/JA4 Profile:"), self.combo_tls)

        self.combo_webrtc = QComboBox()
        self.combo_webrtc.addItem("⛊ Protocol-Level IP Spoofing (C++ Native ICE - Undetectable)", "altered")
        self.combo_webrtc.addItem("Disabled (No WebRTC)", "disabled")
        self.combo_webrtc.addItem("Real (Leak Local IP)", "real")
        sec_layout.addRow(QLabel("WebRTC Protection:"), self.combo_webrtc)

        layout.addWidget(sec_group)

        # Behavioral Realism & Natural Persistence (Anti-Sterility V2)
        beh_group = QGroupBox("Browser Behavior & Natural Persistence (Anti-Sterility V2)")
        beh_layout = QVBoxLayout(beh_group)
        beh_layout.setSpacing(6)

        self.chk_save_history = QCheckBox("Enable Browsing History & Places Database (save_history)")
        self.chk_save_history.setChecked(True)
        self.chk_search_suggestions = QCheckBox("Enable Search & URL Bar Suggestions (search_suggestions)")
        self.chk_search_suggestions.setChecked(True)
        self.chk_form_autofill = QCheckBox("Enable Form Autofill API (form_autofill)")
        self.chk_form_autofill.setChecked(True)
        self.chk_disk_cache = QCheckBox("Enable Disk Cache Persistence (disk_cache)")
        self.chk_disk_cache.setChecked(True)
        self.chk_offline_storage = QCheckBox("Enable Offline Storage (IndexedDB & ServiceWorkers)")
        self.chk_offline_storage.setChecked(True)
        self.chk_drm_widevine = QCheckBox("Enable DRM Widevine CDM Media Decryption (drm_widevine)")
        self.chk_drm_widevine.setChecked(True)
        self.chk_block_telemetry = QCheckBox("Block Mozilla/Google Telemetry Uploads (block_telemetry)")
        self.chk_block_telemetry.setChecked(False)
        self.chk_clear_on_shutdown = QCheckBox("Clear Cache & Storage on Shutdown (clear_on_shutdown)")
        self.chk_clear_on_shutdown.setChecked(False)

        beh_layout.addWidget(self.chk_save_history)
        beh_layout.addWidget(self.chk_search_suggestions)
        beh_layout.addWidget(self.chk_form_autofill)
        beh_layout.addWidget(self.chk_disk_cache)
        beh_layout.addWidget(self.chk_offline_storage)
        beh_layout.addWidget(self.chk_drm_widevine)
        beh_layout.addWidget(self.chk_block_telemetry)
        beh_layout.addWidget(self.chk_clear_on_shutdown)

        layout.addWidget(beh_group)
        layout.addStretch()
        return widget

    def _on_proxy_mode_changed(self):
        mode = self.combo_proxy_mode.currentData()
        self.custom_proxy_box.setVisible(mode == "custom_list")
        has_proxy = mode != "none"
        self.chk_auto_timezone.setEnabled(has_proxy)
        self.chk_auto_geo.setEnabled(has_proxy)

    def _update_name_preview(self):
        count = self.spin_count.value()
        prefix = self.txt_prefix.text().strip() or "Profile"
        style = self.combo_naming_pattern.currentData()

        sample_names = []
        for i in range(1, min(count + 1, 4)):
            sample_names.append(self._generate_profile_name(prefix, i, style))

        if count > 3:
            last_name = self._generate_profile_name(prefix, count, style)
            preview_str = f"Preview: {', '.join(sample_names)} ... {last_name}"
        else:
            preview_str = f"Preview: {', '.join(sample_names)}"

        self.lbl_preview.setText(preview_str)

    def _generate_profile_name(self, prefix: str, index: int, style: str) -> str:
        if style == "num_pad":
            return f"{prefix} {index:02d}"
        elif style == "hex_hash":
            import hashlib
            h = hashlib.md5(f"{prefix}_{index}_{random.random()}".encode()).hexdigest()[:6]
            return f"{prefix}-{h}"
        elif style == "persona":
            names = ["Alex", "Jordan", "Taylor", "Morgan", "Sam", "Chris", "Casey", "Riley", "Jamie", "Robin"]
            name = names[(index - 1) % len(names)]
            return f"{prefix} {name} #{index}"
        return f"{prefix} #{index}"

    def _on_generate_clicked(self):
        count = self.spin_count.value()
        prefix = self.txt_prefix.text().strip() or "Profile"
        style = self.combo_naming_pattern.currentData()
        group = self.txt_group.text().strip() or "Default"
        tags_raw = self.txt_tags.text().strip()
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else ["Batch"]
        start_url = self.txt_start_url.text().strip()

        os_mode = self.combo_os.currentData()
        engine_mode = self.combo_engine.currentData()
        res_mode = self.combo_res.currentData()
        cpu_mode = self.combo_cpu.currentData()
        ram_mode = self.combo_ram.currentData()
        gpu_mode = self.combo_gpu.currentData()
        proxy_mode = self.combo_proxy_mode.currentData()
        storage_mode = self.combo_storage.currentData()
        tls_mode = self.combo_tls.currentData()

        # Gather proxies if requested
        pool_proxies: List[Dict] = []
        if proxy_mode in ("pool_seq", "pool_rand"):
            pool_proxies = self.proxy_manager.list_proxies(sort_speed=True)
            if not pool_proxies:
                QMessageBox.warning(self, "No Proxies Available", "Your proxy pool is empty! Please import or scrape proxies first, or choose 'No Proxy'.")
                return
            if proxy_mode == "pool_rand":
                random.shuffle(pool_proxies)

        custom_proxies: List[str] = []
        if proxy_mode == "custom_list":
            raw_lines = self.txt_custom_proxies.toPlainText().strip().split("\n")
            custom_proxies = [l.strip() for l in raw_lines if l.strip()]
            if not custom_proxies:
                QMessageBox.warning(self, "Missing Proxies", "Please paste at least one proxy into the list or choose another mode.")
                return

        self.btn_generate.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        created_count = 0

        for i in range(1, count + 1):
            p_name = self._generate_profile_name(prefix, i, style)
            pdata = self.profile_manager.create_default_profile_data(p_name)
            pdata["group"] = group
            pdata["tags"] = tags
            pdata["start_url"] = start_url

            # 1. OS & User Agent
            if os_mode == "random_all":
                chosen_os = random.choice(["windows", "mac", "linux", "android"])
            elif os_mode == "random_desktop":
                chosen_os = random.choice(["windows", "mac"])
            else:
                chosen_os = os_mode

            pdata["os"] = chosen_os
            pdata["custom_user_agent"] = False
            pdata["user_agent"] = config.DEFAULT_USER_AGENTS.get(chosen_os, config.DEFAULT_USER_AGENTS["windows"])

            # 2. Engine
            if engine_mode == "random_dist":
                pdata["engine"] = random.choice(["playwright", "camoufox"])
            else:
                pdata["engine"] = engine_mode

            # 3. Screen Resolution
            if res_mode == "random":
                desktop_res = ["1920x1080", "2560x1440", "1536x864", "1440x900", "1366x768", "3840x2160"]
                pdata["screen_resolution"] = random.choice(desktop_res if chosen_os != "android" else ["412x915", "393x852"])
            else:
                pdata["screen_resolution"] = res_mode

            # 4. Hardware CPU & RAM
            if cpu_mode == "random":
                pdata["hardware_concurrency"] = random.choice([4, 8, 12, 16])
            else:
                pdata["hardware_concurrency"] = int(cpu_mode)

            if ram_mode == "random":
                pdata["device_memory"] = random.choice([8, 16, 32])
            else:
                pdata["device_memory"] = int(ram_mode)

            # 5. WebGL GPU Presets (Guaranteed OS Tensor Harmony)
            os_presets = config.get_webgl_presets_for_os(chosen_os)
            if gpu_mode == "unspoofed":
                preset = {"vendor": "", "renderer": ""}
                pdata["webgl_spoofing"] = False
                pdata["webgl_mode"] = "real"
            elif gpu_mode == "native":
                preset = config.detect_native_webgl_info()
                pdata["webgl_spoofing"] = True
                pdata["webgl_mode"] = "spoof"
            elif gpu_mode == "random_matched":
                preset = random.choice(os_presets) if os_presets else config.WEBGL_PRESETS_BY_OS["windows"][0]
            elif gpu_mode == "rtx4090":
                preset = next((p for p in os_presets if "4090" in p["renderer"]), os_presets[0])
            elif gpu_mode == "rtx4080":
                preset = next((p for p in os_presets if "4080" in p["renderer"]), os_presets[0])
            elif gpu_mode == "rtx4070":
                preset = next((p for p in os_presets if "4070" in p["renderer"]), os_presets[0])
            elif gpu_mode == "rtx3060":
                preset = next((p for p in os_presets if "3060" in p["renderer"]), os_presets[0])
            elif gpu_mode == "m3max":
                preset = next((p for p in os_presets if "M3" in p["renderer"]), os_presets[0])
            elif gpu_mode == "m2max":
                preset = next((p for p in os_presets if "M2" in p["renderer"]), os_presets[0])
            elif gpu_mode == "rx7900":
                preset = next((p for p in os_presets if "7900" in p["renderer"] or "Radeon" in p["renderer"]), os_presets[0])
            else:
                preset = os_presets[0]

            pdata["webgl_vendor"] = preset["vendor"]
            pdata["webgl_renderer"] = preset["renderer"]

            # 6. Active Noise Injections & WebGPU
            pdata["canvas_noise"] = self.chk_canvas_noise.isChecked()
            pdata["webgl_noise"] = self.chk_webgl_noise.isChecked()
            pdata["audio_noise"] = self.chk_audio_noise.isChecked()

            if "stealth" not in pdata or not isinstance(pdata["stealth"], dict):
                pdata["stealth"] = {}
            pdata["stealth"]["canvas_noise"] = self.chk_canvas_noise.isChecked()
            pdata["stealth"]["canvas_mode"] = "aggressiveness_low"
            pdata["stealth"]["webgl_noise"] = self.chk_webgl_noise.isChecked()
            pdata["stealth"]["audio_noise"] = self.chk_audio_noise.isChecked()
            pdata["stealth"]["audio_mode"] = "natural_jitter"
            pdata["stealth"]["font_fingerprint_noise"] = self.chk_font_noise.isChecked()
            pdata["stealth"]["client_rects_noise"] = self.chk_client_rects_noise.isChecked()
            pdata["stealth"]["webgpu_supported"] = self.chk_webgpu.isChecked()
            pdata["stealth"]["webrtc_mode"] = self.combo_webrtc.currentData()

            # 7. Browser Behavior & Natural Persistence (Anti-Sterility V2)
            if "behavior" not in pdata or not isinstance(pdata["behavior"], dict):
                pdata["behavior"] = {}
            pdata["behavior"]["save_history"] = self.chk_save_history.isChecked()
            pdata["behavior"]["search_suggestions"] = self.chk_search_suggestions.isChecked()
            pdata["behavior"]["form_autofill"] = self.chk_form_autofill.isChecked()
            pdata["behavior"]["disk_cache"] = self.chk_disk_cache.isChecked()
            pdata["behavior"]["offline_storage"] = self.chk_offline_storage.isChecked()
            pdata["behavior"]["drm_widevine"] = self.chk_drm_widevine.isChecked()
            pdata["behavior"]["block_telemetry"] = self.chk_block_telemetry.isChecked()
            pdata["behavior"]["clear_on_shutdown"] = self.chk_clear_on_shutdown.isChecked()
            pdata["behavior"]["restore_session"] = False
            pdata["behavior"]["password_manager"] = False
            pdata["behavior"]["autoplay_media"] = "allow"

            # 8. Storage Mode
            pdata["ephemeral_ram"] = (storage_mode == "ephemeral")
            pdata["encrypted"] = (storage_mode == "encrypted")
            pdata["tls_ja3_preset"] = tls_mode

            # 8. Proxy Assignment
            if proxy_mode in ("pool_seq", "pool_rand") and pool_proxies:
                chosen_proxy = pool_proxies[(i - 1) % len(pool_proxies)]
                pdata["proxy"] = {
                    "enabled": True,
                    "type": chosen_proxy.get("type", "http"),
                    "host": chosen_proxy.get("host", ""),
                    "port": int(chosen_proxy.get("port", 8080)),
                    "username": chosen_proxy.get("username", ""),
                    "password": chosen_proxy.get("password", ""),
                    "auto_timezone": self.chk_auto_timezone.isChecked(),
                    "auto_geolocation": self.chk_auto_geo.isChecked(),
                    "network_killswitch": True,
                    "burst_protection": True,
                    "burst_stagger_ms": 20.0
                }
            elif proxy_mode == "custom_list" and custom_proxies:
                proxy_line = custom_proxies[(i - 1) % len(custom_proxies)]
                parsed_proxy = self._parse_single_proxy(proxy_line)
                if parsed_proxy:
                    parsed_proxy["auto_timezone"] = self.chk_auto_timezone.isChecked()
                    parsed_proxy["auto_geolocation"] = self.chk_auto_geo.isChecked()
                    parsed_proxy["network_killswitch"] = True
                    parsed_proxy["burst_protection"] = True
                    parsed_proxy["burst_stagger_ms"] = 20.0
                    pdata["proxy"] = parsed_proxy

            self.profile_manager.create_profile(pdata)
            created_count += 1
            self.progress_bar.setValue(int(i / count * 100))

        QMessageBox.information(
            self,
            "Batch Creation Complete",
            f"Successfully created {created_count} profiles with customized fingerprints!"
        )
        self.accept()

    def _parse_single_proxy(self, line: str) -> Optional[Dict]:
        try:
            line = line.strip()
            ptype = "http"
            if "://" in line:
                parts = line.split("://")
                ptype = parts[0].lower()
                line = parts[1]

            parts = line.split(":")
            if len(parts) == 2:
                return {"enabled": True, "type": ptype, "host": parts[0], "port": int(parts[1]), "username": "", "password": ""}
            elif len(parts) == 4:
                return {"enabled": True, "type": ptype, "host": parts[0], "port": int(parts[1]), "username": parts[2], "password": parts[3]}
        except Exception:
            pass
        return None
