from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QStackedWidget, QLabel, QFrame, QMessageBox
)
from PyQt6.QtGui import QIcon
import os
from PyQt6.QtCore import Qt, pyqtSignal
import config
from storage.profile_manager import ProfileManager
from engine.browser import BrowserLauncher
from storage.proxy_manager import ProxyManager
from engine.ai_model_manager import AIModelManager
from ui.components.custom_widgets import MetricCard, SystemResourceWidget
from ui.views.profiles_view import ProfilesView
from ui.views.proxies_view import ProxiesView
from ui.views.proxy_scraper_view import ProxyScraperView
from ui.views.ai_chat_view import AIChatView
from ui.views.ai_operations_matrix_view import AIOperationsMatrixView
from ui.views.ai_config_view import AIConfigView
from ui.views.settings_view import SettingsView
from ui.views.model_manager_dialog import ModelManagerDialog

from ui.views.workflow_builder_view import WorkflowBuilderView

class MainWindow(QMainWindow):
    """Main Application Window for OXBROWSER."""

    closing = pyqtSignal()

    def __init__(self, profile_manager: ProfileManager, launcher: BrowserLauncher, proxy_manager: ProxyManager | None = None):
        super().__init__()
        self.profile_manager = profile_manager
        self.launcher = launcher
        self.proxy_manager = proxy_manager or ProxyManager()

        self.setWindowTitle(f"{config.APP_NAME} v{config.APP_VERSION}")
        self.setWindowIcon(self._get_icon("logo"))
        self.setMinimumSize(1200, 720)
        self.resize(1800, 860)
        self._init_ui()

    def closeEvent(self, event):
        ai_mgr = AIModelManager.get_instance()
        if ai_mgr.is_any_download_active():
            reply = QMessageBox.question(
                self,
                " Active AI Model Download",
                "An AI Model download (SmolVLM / Vision LLM) is currently running in the Download Manager!\n\n"
                f"Closing {config.APP_NAME} will cancel the active download.\n"
                "Are you sure you want to exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                if event:
                    event.ignore()
                return

        self.closing.emit()
        super().closeEvent(event)

    def open_model_manager(self):
        dialog = ModelManagerDialog(self)
        dialog.exec()
        
    def _get_icon(self, name):
        return QIcon(os.path.join(os.path.dirname(__file__), "assets", "icons", f"{name}.svg"))

    def _init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Sidebar Navigation
        self.sidebar = QWidget()
        self.sidebar.setObjectName("SidebarWidget")
        self.sidebar.setFixedWidth(235)
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(0, 0, 0, 12)
        self.sidebar_layout.setSpacing(4)

        # Sidebar Header Branding
        self.sidebar_header = QWidget()
        self.sidebar_header.setObjectName("SidebarHeader")
        header_layout = QVBoxLayout(self.sidebar_header)
        header_layout.setContentsMargins(14, 14, 14, 10)
        header_layout.setSpacing(6)

        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(0, 0, 0, 0)
        brand_row.setSpacing(8)
        brand_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        # OXBROWSER Brand Logo
        logo_label = QLabel()
        logo_label.setObjectName("SidebarLogo")
        logo_label.setFixedSize(26, 26)
        logo_label.setScaledContents(True)
        logo_label.setPixmap(self._get_icon("logo").pixmap(26, 26))
        brand_row.addWidget(logo_label)

        self.app_title = QLabel(config.APP_NAME)
        self.app_title.setObjectName("SidebarTitle")
        brand_row.addWidget(self.app_title)
        brand_row.addStretch()

        self.badge_ver = QLabel(f"v{config.APP_VERSION}")
        self.badge_ver.setObjectName("SidebarBadge")
        brand_row.addWidget(self.badge_ver)
        header_layout.addLayout(brand_row)

        self.app_subtitle = QLabel("Anti-Detect & Stealth Suite")
        self.app_subtitle.setObjectName("SidebarSubtitle")
        header_layout.addWidget(self.app_subtitle)

        self.sidebar_layout.addWidget(self.sidebar_header)

        # Nav Category: Core Management
        self.lbl_cat_core = QLabel("  CORE PLATFORM")
        self.lbl_cat_core.setStyleSheet("color: #888888; font-size: 10px; font-weight: 700; letter-spacing: 0.8px; margin-top: 6px;")
        self.sidebar_layout.addWidget(self.lbl_cat_core)

        self.btn_profiles = QPushButton(" Profiles Manager")
        self.btn_profiles.setIcon(self._get_icon("folder-open"))
        self.btn_profiles.setProperty("class", "NavButton")
        self.btn_profiles.setCheckable(True)
        self.btn_profiles.setChecked(True)
        self.btn_profiles.clicked.connect(lambda: self.switch_view(0))

        self.btn_proxies = QPushButton(" Proxy Pool")
        self.btn_proxies.setIcon(self._get_icon("shield"))
        self.btn_proxies.setProperty("class", "NavButton")
        self.btn_proxies.setCheckable(True)
        self.btn_proxies.clicked.connect(lambda: self.switch_view(1))

        self.btn_scraper = QPushButton(" Proxy Scraper")
        self.btn_scraper.setIcon(self._get_icon("radar"))
        self.btn_scraper.setProperty("class", "NavButton")
        self.btn_scraper.setCheckable(True)
        self.btn_scraper.clicked.connect(lambda: self.switch_view(2))

        self.sidebar_layout.addWidget(self.btn_profiles)
        self.sidebar_layout.addWidget(self.btn_proxies)
        self.sidebar_layout.addWidget(self.btn_scraper)

        # Nav Category: AI & Automation
        self.lbl_cat_ai = QLabel("  INTELLIGENCE & AI")
        self.lbl_cat_ai.setStyleSheet("color: #888888; font-size: 10px; font-weight: 700; letter-spacing: 0.8px; margin-top: 10px;")
        self.sidebar_layout.addWidget(self.lbl_cat_ai)

        self.btn_ai_chat = QPushButton(" AI Swarm & Chat Copilot")
        self.btn_ai_chat.setIcon(self._get_icon("bot"))
        self.btn_ai_chat.setProperty("class", "NavButton")
        self.btn_ai_chat.setCheckable(True)
        self.btn_ai_chat.clicked.connect(lambda: self.switch_view(3))

        self.btn_ai_matrix = QPushButton(" AI Swarm Matrix")
        self.btn_ai_matrix.setIcon(self._get_icon("cpu"))
        self.btn_ai_matrix.setProperty("class", "NavButton")
        self.btn_ai_matrix.setCheckable(True)
        self.btn_ai_matrix.clicked.connect(lambda: self.switch_view(4))

        self.btn_workflow = QPushButton(" Visual Workflow Builder")
        self.btn_workflow.setIcon(self._get_icon("activity"))
        self.btn_workflow.setProperty("class", "NavButton")
        self.btn_workflow.setCheckable(True)
        self.btn_workflow.clicked.connect(lambda: self.switch_view(5))

        self.btn_ai_config = QPushButton(" AI & Vision Config")
        self.btn_ai_config.setIcon(self._get_icon("settings"))
        self.btn_ai_config.setProperty("class", "NavButton")
        self.btn_ai_config.setCheckable(True)
        self.btn_ai_config.clicked.connect(lambda: self.switch_view(6))

        self.btn_dl_manager = QPushButton(" AI Model Downloads")
        self.btn_dl_manager.setIcon(self._get_icon("download"))
        self.btn_dl_manager.setProperty("class", "NavButton")
        self.btn_dl_manager.clicked.connect(self.open_model_manager)

        self.sidebar_layout.addWidget(self.btn_ai_chat)
        self.sidebar_layout.addWidget(self.btn_ai_matrix)
        self.sidebar_layout.addWidget(self.btn_workflow)
        self.sidebar_layout.addWidget(self.btn_ai_config)
        self.sidebar_layout.addWidget(self.btn_dl_manager)

        # Nav Category: System & Config
        self.lbl_cat_sys = QLabel("  CONFIGURATION")
        self.lbl_cat_sys.setStyleSheet("color: #888888; font-size: 10px; font-weight: 700; letter-spacing: 0.8px; margin-top: 10px;")
        self.sidebar_layout.addWidget(self.lbl_cat_sys)

        self.btn_settings = QPushButton(" Settings & API")
        self.btn_settings.setIcon(self._get_icon("settings"))
        self.btn_settings.setProperty("class", "NavButton")
        self.btn_settings.setCheckable(True)
        self.btn_settings.clicked.connect(lambda: self.switch_view(7))

        self.sidebar_layout.addWidget(self.btn_settings)

        self.nav_items = [
            (self.btn_profiles, " Profiles Manager"),
            (self.btn_proxies, " Proxy Pool"),
            (self.btn_scraper, " Proxy Scraper"),
            (self.btn_ai_chat, " AI Swarm & Chat Copilot"),
            (self.btn_ai_matrix, " AI Swarm Matrix"),
            (self.btn_workflow, " Visual Workflow Builder"),
            (self.btn_ai_config, " AI & Vision Config"),
            (self.btn_settings, " Settings & API")
        ]

        self.nav_buttons = [item[0] for item in self.nav_items]

        self.sidebar_layout.addStretch()

        # Sidebar Footer
        self.footer_widget = QWidget()
        footer_layout = QHBoxLayout(self.footer_widget)
        footer_layout.setContentsMargins(14, 8, 14, 4)
        lbl_status = QLabel("Engine Ready")
        lbl_status.setStyleSheet("color: #10b981; font-size: 11px; font-weight: 600;")
        
        status_icon_lbl = QLabel()
        status_icon_lbl.setPixmap(self._get_icon("activity").pixmap(12, 12))
        
        footer_layout.addWidget(status_icon_lbl)
        footer_layout.addWidget(lbl_status)
        footer_layout.addStretch()
        self.sidebar_layout.addWidget(self.footer_widget)

        main_layout.addWidget(self.sidebar)

        # 2. Right Content Area (Header + Stacked Pages)
        content_area = QWidget()
        self.content_layout = QVBoxLayout(content_area)
        self.content_layout.setContentsMargins(16, 16, 16, 16)
        self.content_layout.setSpacing(14)

        # Metrics Header (Live Telemetry & Profile Overview)
        self.metrics_container = QWidget()
        metrics_layout = QHBoxLayout(self.metrics_container)
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        metrics_layout.setSpacing(12)
        self.card_total = MetricCard("TOTAL PROFILES", "0")
        self.card_active = MetricCard("ACTIVE BROWSERS", "0")
        self.card_version = MetricCard("ENGINE VERSION", config.APP_VERSION)
        self.card_resources = SystemResourceWidget()

        metrics_layout.addWidget(self.card_total, 1)
        metrics_layout.addWidget(self.card_active, 1)
        metrics_layout.addWidget(self.card_version, 1)
        metrics_layout.addWidget(self.card_resources, 2)
        self.content_layout.addWidget(self.metrics_container)

        # Stacked Views
        self.stacked_widget = QStackedWidget()
        self.profiles_view = ProfilesView(self.profile_manager, self.launcher, proxy_manager=self.proxy_manager)
        self.profiles_view.profiles_changed.connect(self.update_metrics)
        
        self.proxies_view = ProxiesView(self.proxy_manager, profile_manager=self.profile_manager)
        self.proxies_view.open_scraper_requested.connect(lambda: self.switch_view(2))
        self.proxies_view.proxy_assigned.connect(lambda: self.profiles_view.reload_profiles(force=True))

        self.scraper_view = ProxyScraperView(self.proxy_manager)
        self.scraper_view.proxies_imported.connect(lambda: self.proxies_view.reload_proxies(sort_speed=True))

        self.ai_chat_view = AIChatView(self.profile_manager, launcher=self.launcher)
        self.profiles_view.profiles_changed.connect(self.ai_chat_view.reload_profiles)

        self.ai_matrix_view = AIOperationsMatrixView()
        self.workflow_view = WorkflowBuilderView(profile_manager=self.profile_manager, launcher=self.launcher)
        self.profiles_view.profiles_changed.connect(self.workflow_view.reload_profiles)
        self.ai_view = AIConfigView()
        self.settings_view = SettingsView()

        self.stacked_widget.addWidget(self.profiles_view)      # 0
        self.stacked_widget.addWidget(self.proxies_view)       # 1
        self.stacked_widget.addWidget(self.scraper_view)       # 2
        self.stacked_widget.addWidget(self.ai_chat_view)       # 3
        self.stacked_widget.addWidget(self.ai_matrix_view)     # 4
        self.stacked_widget.addWidget(self.workflow_view)      # 5
        self.stacked_widget.addWidget(self.ai_view)            # 6
        self.stacked_widget.addWidget(self.settings_view)       # 7

        self.content_layout.addWidget(self.stacked_widget, 1)
        main_layout.addWidget(content_area, 1)

        self.update_metrics()

    def _set_compact_sidebar(self, is_compact: bool):
        """Collapses or expands the main left navigation drawer to maximize workspace space."""
        if is_compact:
            self.sidebar.setFixedWidth(56)
            self.sidebar_header.setVisible(False)
            self.lbl_cat_core.setVisible(False)
            self.lbl_cat_ai.setVisible(False)
            self.lbl_cat_sys.setVisible(False)
            self.footer_widget.setVisible(False)
            for btn, full_text in self.nav_items:
                btn.setText("")
                btn.setToolTip(full_text.strip())
        else:
            self.sidebar.setFixedWidth(235)
            self.sidebar_header.setVisible(True)
            self.lbl_cat_core.setVisible(True)
            self.lbl_cat_ai.setVisible(True)
            self.lbl_cat_sys.setVisible(True)
            self.footer_widget.setVisible(True)
            for btn, full_text in self.nav_items:
                btn.setText(full_text)
                btn.setToolTip("")

    def switch_view(self, index: int):
        self.stacked_widget.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)
        
        # When Workflow Builder is open (index 5), shrink drawer & hide top metrics bar for maximum canvas space
        if index == 5:
            self._set_compact_sidebar(True)
            self.metrics_container.setVisible(False)
            self.content_layout.setContentsMargins(4, 4, 4, 4)
            self.content_layout.setSpacing(0)
        else:
            self._set_compact_sidebar(False)
            self.metrics_container.setVisible(True)
            self.content_layout.setContentsMargins(16, 16, 16, 16)
            self.content_layout.setSpacing(14)

        if index == 0:
            self.profiles_view.reload_profiles(force=True)
        elif index == 3:
            self.ai_chat_view.reload_profiles()
        self.update_metrics()

    def update_metrics(self):
        profiles = self.profile_manager.list_profiles()
        self.card_total.set_value(str(len(profiles)))
        running_count = sum(1 for p in profiles if p.get("status") == "Running")
        self.card_active.set_value(str(running_count))

