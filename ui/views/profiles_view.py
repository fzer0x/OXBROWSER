from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLineEdit, QComboBox, QPushButton, QHeaderView, QMessageBox, QLabel
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon
from typing import List, Set, Dict, Optional
import asyncio
import qasync
import time
import os
from storage.profile_manager import ProfileManager
from storage.proxy_manager import ProxyManager
from engine.browser import BrowserLauncher
from engine.account_manager import AccountManager
from ui.components.custom_widgets import StatusBadge, TagBadge
from ui.views.profile_dialog import ProfileDialog

class ProfilesView(QWidget):
    """Profiles Manager Dashboard View."""

    profiles_changed = pyqtSignal()

    def __init__(self, profile_manager: ProfileManager, launcher: BrowserLauncher, proxy_manager: Optional[ProxyManager] = None, parent=None):
        super().__init__(parent)
        self.profile_manager = profile_manager
        self.launcher = launcher
        self.proxy_manager = proxy_manager or ProxyManager()
        self.selected_profile_ids = set()

        self._init_ui()
        self.reload_profiles()

        # Timer to auto-refresh status when browser is closed by user
        self.auto_refresh_timer = QTimer(self)
        self.auto_refresh_timer.setInterval(2000)
        self.auto_refresh_timer.timeout.connect(self.reload_profiles)
        self.auto_refresh_timer.start()

    def _get_icon(self, name):
        return QIcon(os.path.join(os.path.dirname(__file__), "..", "assets", "icons", f"{name}.svg"))

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # 1. Top Control Bar (Search & Primary Creation Actions)
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search profiles by name, tag, group, or IP...")
        self.search_input.setMinimumWidth(260)
        self.search_input.textChanged.connect(self._filter_profiles)
        top_bar.addWidget(self.search_input, 1)

        batch_btn = QPushButton(" Batch Create")
        batch_btn.setIcon(self._get_icon("copy"))
        batch_btn.setProperty("class", "SecondaryButton")
        batch_btn.clicked.connect(self._on_batch_create)
        top_bar.addWidget(batch_btn)

        import_bundle_btn = QPushButton(" Import")
        import_bundle_btn.setIcon(self._get_icon("download"))
        import_bundle_btn.setProperty("class", "SecondaryButton")
        import_bundle_btn.clicked.connect(self._on_import_bundle)
        top_bar.addWidget(import_bundle_btn)

        create_btn = QPushButton(" Create Profile")
        create_btn.setIcon(self._get_icon("file-text"))
        create_btn.setProperty("class", "PrimaryButton")
        create_btn.clicked.connect(self._on_create_profile)
        top_bar.addWidget(create_btn)

        layout.addLayout(top_bar)

        # 2. Multi-Profile Selection Action Bar
        self.sel_bar = QHBoxLayout()
        self.sel_bar.setSpacing(8)

        self.btn_select_all = QPushButton(" Select All")
        self.btn_select_all.setIcon(self._get_icon("check-circle"))
        self.btn_select_all.setProperty("class", "SecondaryButton")
        self.btn_select_all.setFixedHeight(28)
        self.btn_select_all.clicked.connect(self._select_all_profiles)
        self.sel_bar.addWidget(self.btn_select_all)

        self.btn_deselect_all = QPushButton(" Deselect All")
        self.btn_deselect_all.setIcon(self._get_icon("x-circle"))
        self.btn_deselect_all.setProperty("class", "SecondaryButton")
        self.btn_deselect_all.setFixedHeight(28)
        self.btn_deselect_all.clicked.connect(self._deselect_all_profiles)
        self.sel_bar.addWidget(self.btn_deselect_all)

        self.lbl_sel_count = QLabel("Selected: 0 profiles")
        self.lbl_sel_count.setStyleSheet("color: #94a3b8; font-weight: 700; font-size: 11px; margin-left: 4px;")
        self.sel_bar.addWidget(self.lbl_sel_count)

        self.sel_bar.addStretch()

        self.btn_launch_selected = QPushButton(" Launch Selected (0)")
        self.btn_launch_selected.setIcon(self._get_icon("play"))
        self.btn_launch_selected.setProperty("class", "SuccessButton")
        self.btn_launch_selected.setFixedHeight(28)
        self.btn_launch_selected.clicked.connect(self._on_launch_selected)
        self.sel_bar.addWidget(self.btn_launch_selected)

        self.btn_stop_selected = QPushButton(" Stop Selected (0)")
        self.btn_stop_selected.setIcon(self._get_icon("square"))
        self.btn_stop_selected.setProperty("class", "DangerButton")
        self.btn_stop_selected.setFixedHeight(28)
        self.btn_stop_selected.clicked.connect(self._on_stop_selected)
        self.sel_bar.addWidget(self.btn_stop_selected)

        self.btn_warmup_selected = QPushButton(" AI Warmup (0)")
        self.btn_warmup_selected.setIcon(self._get_icon("zap"))
        self.btn_warmup_selected.setProperty("class", "SecondaryButton")
        self.btn_warmup_selected.setFixedHeight(28)
        self.btn_warmup_selected.clicked.connect(self._on_warmup_selected)
        self.sel_bar.addWidget(self.btn_warmup_selected)

        self.btn_assign_proxy = QPushButton(" Assign Proxy (0)")
        self.btn_assign_proxy.setIcon(self._get_icon("shield"))
        self.btn_assign_proxy.setProperty("class", "SecondaryButton")
        self.btn_assign_proxy.setFixedHeight(28)
        self.btn_assign_proxy.clicked.connect(self._on_assign_proxy_selected)
        self.sel_bar.addWidget(self.btn_assign_proxy)

        self.btn_delete_selected = QPushButton(" Delete Selected (0)")
        self.btn_delete_selected.setIcon(self._get_icon("trash-2"))
        self.btn_delete_selected.setProperty("class", "DangerButton")
        self.btn_delete_selected.setFixedHeight(28)
        self.btn_delete_selected.clicked.connect(self._on_delete_selected)
        self.sel_bar.addWidget(self.btn_delete_selected)

        layout.addLayout(self.sel_bar)

        # 3. Profiles Table
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "", "Action", "Profile Name", "Accounts & Logins", "Group & Tags", "Status", "Proxy / Location", "OS & Engine", "Manage"
        ])
        
        v_header = self.table.verticalHeader()
        if v_header:
            v_header.setVisible(False)
            v_header.setDefaultSectionSize(46)

        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)

        header = self.table.horizontalHeader()
        if header:
            header.setHighlightSections(False)
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(0, 42)

            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(1, 115)

            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
            self.table.setColumnWidth(2, 160)

            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
            self.table.setColumnWidth(3, 190)

            header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
            self.table.setColumnWidth(4, 150)

            header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(5, 120)

            header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
            self.table.setColumnWidth(6, 230)

            header.setSectionResizeMode(7, QHeaderView.ResizeMode.Interactive)
            self.table.setColumnWidth(7, 240)

            header.setSectionResizeMode(8, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(8, 380)

        self.table.itemChanged.connect(self._on_table_item_changed)
        self.table.itemSelectionChanged.connect(self._on_table_selection_changed)
        layout.addWidget(self.table)

    def reload_profiles(self):
        # Capture scroll position
        v_bar = self.table.verticalScrollBar()
        scroll_v = v_bar.value() if v_bar is not None else 0

        self.profiles = self.profile_manager.list_profiles()
        
        # Check if we can do a fast in-place update (same profile IDs in same order)
        if self._can_update_in_place(self.profiles):
            self._update_in_place(self.profiles)
        else:
            self._populate_table(self.profiles)

        # Restore scroll position
        curr_v_bar = self.table.verticalScrollBar()
        if curr_v_bar is not None:
            curr_v_bar.setValue(scroll_v)

        self.profiles_changed.emit()

    def _can_update_in_place(self, profiles_list: list) -> bool:
        if self.table.rowCount() != len(profiles_list):
            return False
        for r, p in enumerate(profiles_list):
            item = self.table.item(r, 0)
            if not item or item.data(Qt.ItemDataRole.UserRole) != p.get("id"):
                return False
        return True

    def _update_in_place(self, profiles_list: list):
        for r, profile in enumerate(profiles_list):
            pid = profile.get("id", "")
            is_running = profile.get("status") == "Running"

            # Update Action Button if needed
            run_widget = self.table.cellWidget(r, 1)
            if run_widget:
                btn = run_widget.findChild(QPushButton)
                if btn:
                    current_text = btn.text()
                    if is_running and "RUN" in current_text:
                        btn.setText(" STOP")
                        btn.setIcon(self._get_icon("square"))
                        btn.setProperty("class", "DangerButton")
                        btn.setStyleSheet("font-weight: 700; font-size: 11px; padding: 4px 12px; border-radius: 6px;")
                        btn.clicked.disconnect()
                        btn.clicked.connect(lambda _, p_id=pid: self._on_stop_profile(p_id))
                    elif not is_running and "STOP" in current_text:
                        btn.setText(" RUN")
                        btn.setIcon(self._get_icon("play"))
                        btn.setProperty("class", "SuccessButton")
                        btn.setStyleSheet("font-weight: 700; font-size: 11px; padding: 4px 12px; border-radius: 6px;")
                        btn.clicked.disconnect()
                        btn.clicked.connect(lambda _, p_id=pid: self._on_start_profile(p_id))

            # Update Status Badge (Col 5)
            status_container = self.table.cellWidget(r, 5)
            if status_container:
                badge = status_container.findChild(StatusBadge)
                if badge and badge.text != profile.get("status", "Stopped"):
                    badge.set_status(profile.get("status", "Stopped"))

    def _populate_table(self, profiles_list: list):
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        
        all_ids = {p.get("id") for p in profiles_list}
        self.selected_profile_ids = {pid for pid in self.selected_profile_ids if pid in all_ids}

        for profile in profiles_list:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setRowHeight(row, 46)
            pid = profile.get("id", "")

            # Col 0: Multi-Select Checkbox
            check_item = QTableWidgetItem()
            check_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            is_checked = pid in self.selected_profile_ids
            check_item.setCheckState(Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked)
            check_item.setData(Qt.ItemDataRole.UserRole, pid)
            self.table.setItem(row, 0, check_item)

            # Col 1: Prominent Run/Stop Button
            run_widget = QWidget()
            run_layout = QHBoxLayout(run_widget)
            run_layout.setContentsMargins(4, 4, 4, 4)
            run_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            is_running = profile.get("status") == "Running"
            if is_running:
                stop_btn = QPushButton(" STOP")
                stop_btn.setIcon(self._get_icon("square"))
                stop_btn.setProperty("class", "DangerButton")
                stop_btn.setStyleSheet("font-weight: 700; font-size: 11px; padding: 4px 12px; border-radius: 6px;")
                stop_btn.clicked.connect(lambda _, p_id=pid: self._on_stop_profile(p_id))
                run_layout.addWidget(stop_btn)
            else:
                run_btn = QPushButton(" RUN")
                run_btn.setIcon(self._get_icon("play"))
                run_btn.setProperty("class", "SuccessButton")
                run_btn.setStyleSheet("font-weight: 700; font-size: 11px; padding: 4px 12px; border-radius: 6px;")
                run_btn.clicked.connect(lambda _, p_id=pid: self._on_start_profile(p_id))
                run_layout.addWidget(run_btn)
            self.table.setCellWidget(row, 1, run_widget)

            # Col 2: Name
            name_item = QTableWidgetItem(profile.get("name", "Unnamed"))
            name_item.setData(Qt.ItemDataRole.UserRole, pid)
            self.table.setItem(row, 2, name_item)

            # Col 3: Accounts & Auto-Login Badges
            acc_list = profile.get("accounts", [])
            acc_widget = QWidget()
            acc_layout = QHBoxLayout(acc_widget)
            acc_layout.setContentsMargins(4, 2, 4, 2)
            acc_layout.setSpacing(4)
            acc_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            
            if not acc_list:
                no_acc_btn = QPushButton("+ Add Account")
                no_acc_btn.setProperty("class", "SecondaryButton")
                no_acc_btn.setStyleSheet("font-size: 10px; padding: 2px 6px; border-radius: 4px; color: #94a3b8;")
                no_acc_btn.clicked.connect(lambda _, p_id=pid: self._on_manage_accounts(p_id))
                acc_layout.addWidget(no_acc_btn)
            else:
                for a in acc_list[:2]:
                    plat = a.get("platform", "custom")
                    plat_info = AccountManager.get_platform_info(plat)
                    lbl = QLabel(f"{plat_info['icon']} {plat_info['name']}")
                    is_auto = a.get("auto_login_on_launch")
                    border_col = "#38bdf8" if is_auto else "#475569"
                    bg_col = "rgba(56, 189, 248, 0.15)" if is_auto else "rgba(71, 85, 105, 0.2)"
                    txt_col = "#7dd3fc" if is_auto else "#cbd5e1"
                    tip = f"{plat_info['name']}: {a.get('username', '')}" + (" (Auto-Login ON)" if is_auto else "")
                    lbl.setToolTip(tip)
                    lbl.setStyleSheet(f"background: {bg_col}; color: {txt_col}; border: 1px solid {border_col}; border-radius: 4px; padding: 2px 6px; font-size: 10px; font-weight: 600;")
                    acc_layout.addWidget(lbl)
                if len(acc_list) > 2:
                    more_lbl = QLabel(f"+{len(acc_list) - 2}")
                    more_lbl.setStyleSheet("background: rgba(100, 116, 139, 0.2); color: #94a3b8; border-radius: 4px; padding: 2px 5px; font-size: 10px; font-weight: 600;")
                    acc_layout.addWidget(more_lbl)
            self.table.setCellWidget(row, 3, acc_widget)

            # Col 4: Group, Tags & Trust Score
            grp = profile.get("group", "Default")
            tags = ", ".join(profile.get("tags", []))
            tag_str = f" ({tags})" if tags else ""
            t_score = profile.get("trust_score")
            trust_str = f" | {t_score}%" if t_score is not None else ""
            self.table.setItem(row, 4, QTableWidgetItem(f"{grp}{tag_str}{trust_str}"))

            # Col 5: Status Badge
            status_container = QWidget()
            status_layout = QHBoxLayout(status_container)
            status_layout.setContentsMargins(4, 4, 4, 4)
            status_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            status_badge = StatusBadge(profile.get("status", "Stopped"))
            status_layout.addWidget(status_badge)
            self.table.setCellWidget(row, 5, status_container)

            # Col 6: Proxy & IP
            p = profile.get("proxy", {})
            p_info = profile.get("proxy_info", {})
            if p.get("enabled"):
                ip_str = p_info.get("ip") or f"{p.get('host')}:{p.get('port')}"
                country = p_info.get("country_code", "")
                cntry_str = f" [{country}]" if country else ""
                proxy_text = f"🟢 {p.get('type', 'HTTP').upper()}{cntry_str} {ip_str}"
            else:
                proxy_text = "⚪ Direct (No Proxy)"
            self.table.setItem(row, 6, QTableWidgetItem(proxy_text))

            # Col 7: Fingerprint OS & Engine
            os_name = profile.get("os", "windows").capitalize()
            res = profile.get("screen_resolution", "1920x1080")
            eng_val = str(profile.get("engine", "camoufox")).lower()
            if eng_val == "camoufox":
                engine_str = "Camoufox"
            elif eng_val == "nodriver":
                engine_str = "Nodriver"
            elif eng_val == "selenium_driverless":
                engine_str = "Driverless"
            else:
                engine_str = "Playwright"
            self.table.setItem(row, 7, QTableWidgetItem(f"{os_name} ({res}) | {engine_str}"))

            # Col 8: Secondary Action Buttons (Accounts, Edit, Clone, Export, Delete)
            action_widget = QWidget()
            act_layout = QHBoxLayout(action_widget)
            act_layout.setContentsMargins(2, 2, 2, 2)
            act_layout.setSpacing(4)
            act_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            btn_style = "padding: 3px 8px; font-size: 11px; border-radius: 5px;"

            acc_manage_btn = QPushButton(" Accounts")
            acc_manage_btn.setProperty("class", "SecondaryButton")
            acc_manage_btn.setStyleSheet(btn_style)
            acc_manage_btn.setToolTip("Manage Accounts, 2FA & Auto-Login")
            acc_manage_btn.clicked.connect(lambda _, p_id=pid: self._on_manage_accounts(p_id))
            act_layout.addWidget(acc_manage_btn)

            edit_btn = QPushButton(" Edit")
            edit_btn.setIcon(self._get_icon("settings"))
            edit_btn.setProperty("class", "SecondaryButton")
            edit_btn.setStyleSheet(btn_style)
            edit_btn.clicked.connect(lambda _, p_id=pid: self._on_edit_profile(p_id))
            act_layout.addWidget(edit_btn)

            clone_btn = QPushButton(" Clone")
            clone_btn.setIcon(self._get_icon("copy"))
            clone_btn.setProperty("class", "SecondaryButton")
            clone_btn.setStyleSheet(btn_style)
            clone_btn.clicked.connect(lambda _, p_id=pid: self._on_clone_profile(p_id))
            act_layout.addWidget(clone_btn)

            export_btn = QPushButton(" Export")
            export_btn.setIcon(self._get_icon("file-text"))
            export_btn.setProperty("class", "SecondaryButton")
            export_btn.setStyleSheet(btn_style)
            export_btn.setToolTip("Export Profile Archive (.soxprofile)")
            export_btn.clicked.connect(lambda _, p_id=pid: self._on_export_bundle(p_id))
            act_layout.addWidget(export_btn)

            del_btn = QPushButton("")
            del_btn.setIcon(self._get_icon("trash-2"))
            del_btn.setProperty("class", "SecondaryButton")
            del_btn.setStyleSheet(btn_style)
            del_btn.clicked.connect(lambda _, p_id=pid: self._on_delete_profile(p_id))
            act_layout.addWidget(del_btn)

            self.table.setCellWidget(row, 8, action_widget)

            # Restore row selection highlight
            if is_checked:
                self.table.selectRow(row)

        self.table.blockSignals(False)
        self._update_selection_ui()

    def _on_table_item_changed(self, item: QTableWidgetItem):
        if item.column() == 0:
            pid = item.data(Qt.ItemDataRole.UserRole)
            if pid:
                if item.checkState() == Qt.CheckState.Checked:
                    self.selected_profile_ids.add(pid)
                    self.table.selectRow(item.row())
                else:
                    self.selected_profile_ids.discard(pid)
                self._update_selection_ui()

    def _on_table_selection_changed(self):
        sel_model = self.table.selectionModel()
        if not sel_model:
            return

        selected_rows = {idx.row() for idx in sel_model.selectedRows()}
        if not selected_rows:
            return

        self.table.blockSignals(True)
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item:
                pid = item.data(Qt.ItemDataRole.UserRole)
                if r in selected_rows:
                    item.setCheckState(Qt.CheckState.Checked)
                    if pid:
                        self.selected_profile_ids.add(pid)
        self.table.blockSignals(False)
        self._update_selection_ui()

    def _select_all_profiles(self):
        self.table.blockSignals(True)
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item:
                item.setCheckState(Qt.CheckState.Checked)
                pid = item.data(Qt.ItemDataRole.UserRole)
                if pid:
                    self.selected_profile_ids.add(pid)
            self.table.selectRow(r)
        self.table.blockSignals(False)
        self._update_selection_ui()

    def _deselect_all_profiles(self):
        self.table.blockSignals(True)
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item:
                item.setCheckState(Qt.CheckState.Unchecked)
        self.selected_profile_ids.clear()
        sel_model = self.table.selectionModel()
        if sel_model:
            sel_model.clearSelection()
        self.table.blockSignals(False)
        self._update_selection_ui()

    def _update_selection_ui(self):
        count = len(self.selected_profile_ids)
        total = self.table.rowCount()
        self.lbl_sel_count.setText(f"Selected: {count} / {total} profiles")
        self.btn_launch_selected.setText(f" Launch Selected ({count})")
        self.btn_stop_selected.setText(f" Stop Selected ({count})")
        self.btn_warmup_selected.setText(f" AI Warmup ({count})")
        self.btn_assign_proxy.setText(f" Assign Proxy ({count})")
        self.btn_delete_selected.setText(f" Delete Selected ({count})")

    def _get_selected_ids(self) -> List[str]:
        # Merge checked items and highlight-selected rows
        ids = set(self.selected_profile_ids)
        sel_model = self.table.selectionModel()
        if sel_model:
            for idx in sel_model.selectedRows():
                name_item = self.table.item(idx.row(), 2)
                if name_item:
                    pid = name_item.data(Qt.ItemDataRole.UserRole)
                    if pid:
                        ids.add(pid)
        return list(ids)


    def _filter_profiles(self, text: str):
        query = text.lower().strip()
        if not query:
            self._populate_table(self.profiles)
            return

        filtered = [
            p for p in self.profiles
            if query in p.get("name", "").lower()
            or query in p.get("group", "").lower()
            or any(query in tag.lower() for tag in p.get("tags", []))
        ]
        self._populate_table(filtered)

    @qasync.asyncSlot()
    async def _on_launch_selected(self):
        selected_profile_ids = self._get_selected_ids()
        if not selected_profile_ids:
            QMessageBox.information(self, "Select Profile", "Please select at least one profile using checkboxes or table selection.")
            return

        # Pre-flight engine readiness check across selected profiles
        from ui.views.browser_download_dialog import BrowserDownloadDialog
        checked_engines = set()
        for pid in selected_profile_ids:
            p_data = self.profile_manager.load_profile(pid)
            if p_data:
                e_type = p_data.get("engine", "camoufox").lower()
                if e_type not in checked_engines:
                    if not BrowserDownloadDialog.ensure_engine_ready(self, e_type):
                        return
                    checked_engines.add(e_type)

        from engine.window_grid import WindowGridCalculator
        positions = WindowGridCalculator.calculate_grid_positions(len(selected_profile_ids))

        async def launch_worker(pid: str, x: int, y: int, w: int, h: int):
            await self.launcher.launch_profile(
                pid,
                window_override_pos=(x, y),
                window_override_size=(w, h)
            )

        tasks = []
        for idx, pid in enumerate(selected_profile_ids):
            x, y, w, h = positions[idx]
            tasks.append(asyncio.create_task(launch_worker(pid, x, y, w, h)))

        await asyncio.gather(*tasks, return_exceptions=True)
        self.reload_profiles()

    def _on_create_profile(self):
        dialog = ProfileDialog(self.profile_manager, launcher=self.launcher, proxy_manager=self.proxy_manager, parent=self)
        if dialog.exec() == ProfileDialog.DialogCode.Accepted:
            self.reload_profiles()

    def _on_manage_accounts(self, profile_id: str):
        profile = self.profile_manager.load_profile(profile_id)
        if profile:
            dialog = ProfileDialog(self.profile_manager, profile_data=profile, launcher=self.launcher, proxy_manager=self.proxy_manager, parent=self)
            dialog.tabs.setCurrentIndex(6)  # Direct jump to Tab 7: Accounts & Logins
            if dialog.exec() == ProfileDialog.DialogCode.Accepted:
                self.reload_profiles()

    def _on_edit_profile(self, profile_id: str):
        profile = self.profile_manager.load_profile(profile_id)
        if profile:
            dialog = ProfileDialog(self.profile_manager, profile_data=profile, launcher=self.launcher, proxy_manager=self.proxy_manager, parent=self)
            if dialog.exec() == ProfileDialog.DialogCode.Accepted:
                self.reload_profiles()

    def _on_clone_profile(self, profile_id: str):
        cloned = self.profile_manager.clone_profile(profile_id)
        if cloned:
            self.reload_profiles()

    @qasync.asyncSlot()
    async def _on_start_profile(self, profile_id: str):
        prof = self.profile_manager.load_profile(profile_id)
        if prof:
            e_type = prof.get("engine", "camoufox")
            from ui.views.browser_download_dialog import BrowserDownloadDialog
            if not BrowserDownloadDialog.ensure_engine_ready(self, e_type):
                return

        success, msg, _ = await self.launcher.launch_profile(profile_id)
        if not success:
            QMessageBox.warning(self, "Launch Error", f"Could not launch profile: {msg}")
        self.reload_profiles()

    @qasync.asyncSlot()
    async def _on_stop_profile(self, profile_id: str):
        await self.launcher.stop_profile(profile_id)
        self.reload_profiles()

    def _on_delete_profile(self, profile_id: str):
        reply = QMessageBox.question(self, "Confirm Delete", "Are you sure you want to delete this profile?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.profile_manager.delete_profile(profile_id)
            self.reload_profiles()

    def _on_batch_create(self):
        from ui.views.batch_profile_dialog import BatchProfileDialog
        dlg = BatchProfileDialog(self.profile_manager, self.proxy_manager, parent=self)
        if dlg.exec():
            self.reload_profiles()

    @qasync.asyncSlot()
    async def _on_stop_selected(self):
        selected_profile_ids = self._get_selected_ids()
        if not selected_profile_ids:
            QMessageBox.information(self, "Select Profile", "Please select profile(s) to stop.")
            return

        tasks = [asyncio.create_task(self.launcher.stop_profile(pid)) for pid in selected_profile_ids]
        await asyncio.gather(*tasks, return_exceptions=True)
        self.reload_profiles()

    def _on_delete_selected(self):
        selected_profile_ids = self._get_selected_ids()
        if not selected_profile_ids:
            QMessageBox.information(self, "Select Profile", "Please select profile(s) to delete.")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Batch Delete",
            f"Are you sure you want to delete {len(selected_profile_ids)} selected profile(s)?\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            for pid in selected_profile_ids:
                self.profile_manager.delete_profile(pid)
            self.selected_profile_ids.clear()
            self.reload_profiles()
            QMessageBox.information(self, "Profiles Deleted", f"Successfully deleted {len(selected_profile_ids)} profiles.")

    @qasync.asyncSlot()
    async def _on_warmup_selected(self, *args, **kwargs):
        selected_profile_ids = self._get_selected_ids()
        if not selected_profile_ids:
            QMessageBox.information(self, "Select Profile", "Please select at least one profile row or checkbox first to warm up cookies.")
            return

        from ui.views.warmup_dialog import WarmupDialog
        self._warmup_dialog = WarmupDialog(self, selected_profile_ids, self.launcher)
        self._warmup_dialog.finished.connect(self.reload_profiles)
        self._warmup_dialog.show()
        self._warmup_dialog.raise_()
        self._warmup_dialog.activateWindow()

    def _on_export_bundle(self, profile_id: str):
        from PyQt6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Profile Archive", f"profile_{profile_id[:8]}.soxprofile", "SoxProfile (*.soxprofile);;Zip Files (*.zip)")
        if file_path:
            ok = self.profile_manager.export_profile_bundle(profile_id, file_path)
            if ok:
                QMessageBox.information(self, "Export Complete", f"Profile exported successfully to:\n{file_path}")
            else:
                QMessageBox.warning(self, "Export Failed", "Failed to export profile bundle.")

    def _on_import_bundle(self):
        from PyQt6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getOpenFileName(self, "Import Profile Archive", "", "SoxProfile (*.soxprofile *.zip);;All Files (*)")
        if file_path:
            imported = self.profile_manager.import_profile_bundle(file_path)
            if imported:
                self.reload_profiles()
                QMessageBox.information(self, "Import Complete", f"Imported profile '{imported.get('name')}' successfully.")
            else:
                QMessageBox.warning(self, "Import Failed", "Failed to import profile archive.")

    def _on_assign_proxy_selected(self):
        selected_profile_ids = self._get_selected_ids()
        if not selected_profile_ids:
            QMessageBox.information(self, "Select Profile", "Please select profile(s) via checkbox or table selection first.")
            return

        from storage.proxy_manager import ProxyManager
        pm = ProxyManager()
        proxies = pm.list_proxies()
        if not proxies:
            QMessageBox.warning(self, "No Proxies", "No proxies available in the Proxy Pool. Please add proxies in the Proxies tab first.")
            return

        proxy_options = []
        for p in proxies:
            lat = p.get("latency_ms", -1)
            lat_str = f"⭍ {lat:.1f}ms" if (isinstance(lat, (int, float)) and lat > 0) else "Untested"
            
            status_val = str(p.get("status", ""))
            if "Active" in status_val or "✓" in status_val or "🟢" in status_val:
                status_icon = "🟢"
            elif "Captcha" in status_val or "🟡" in status_val:
                status_icon = "🟡"
            elif "Offline" in status_val or "Failed" in status_val or "🔴" in status_val:
                status_icon = "🔴"
            else:
                status_icon = "⚪"
            country = p.get("country", "")
            loc_str = f"[{country}]" if country else ""
            proxy_options.append(f"{p.get('type','http').upper()}://{p.get('host')}:{p.get('port')} {loc_str} ({lat_str}) {status_icon}".strip())
        from PyQt6.QtWidgets import QInputDialog
        item, ok = QInputDialog.getItem(self, "Assign Proxy from Pool", "Select a proxy from the pool:", proxy_options, 0, False)
        if ok and item:
            idx = proxy_options.index(item)
            chosen_proxy = proxies[idx]

            proxy_cfg = {
                "enabled": True,
                "type": chosen_proxy.get("type", "http"),
                "host": chosen_proxy.get("host"),
                "port": chosen_proxy.get("port"),
                "username": chosen_proxy.get("username", ""),
                "password": chosen_proxy.get("password", ""),
                "auto_timezone": True,
                "auto_geolocation": True
            }

            for pid in selected_profile_ids:
                pdata = self.profile_manager.load_profile(pid)
                if pdata:
                    pdata["proxy"] = proxy_cfg
                    self.profile_manager.save_profile(pdata)

            self.reload_profiles()
            QMessageBox.information(self, "Proxy Assigned", f"Assigned proxy to {len(selected_profile_ids)} selected profile(s).")


