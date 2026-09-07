import os
import re
import json
import time
import base64
import logging
from typing import Optional, Dict, Any, List, Callable

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QComboBox, QTextEdit, QScrollArea, QFileDialog,
    QMessageBox, QDialog, QLineEdit, QSplitter, QProgressBar,
    QApplication, QLayout, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QTimer, QSize, QEvent
from PyQt6.QtGui import QIcon, QFont, QPixmap, QKeySequence, QShortcut, QTextCursor, QKeyEvent
import qasync

import config
from storage.profile_manager import ProfileManager
from engine.browser import BrowserLauncher
from engine.ai_chat_engine import (
    AIChatEngine, ChatMessage, SwarmAgentResponse,
    SYSTEM_PERSONAS, SWARM_MODES, SUPPORTED_CHAT_LANGUAGES
)
from engine.ai_model_manager import AIModelManager
from engine.ai_gemini_client import GeminiApiClient
from engine.browser_copilot_bridge import BrowserCopilotBridge
from engine.ai_voice_copilot import AIVoiceCopilot
from ui.components.custom_widgets import StatusBadge

logger = logging.getLogger("AIChatView")


def format_markdown_to_rich_html(md_text: str) -> str:
    """Converts standard Markdown headings, lists, bold/italic, codes, and horizontal rules into dark theme Rich HTML."""
    if not md_text:
        return ""

    lines = md_text.split('\n')
    out = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            out.append('<div style="height: 6px;"></div>')
            continue

        # Horizontal Rule (---, ***, ___)
        if re.match(r'^(?:---|\*\*\*|___)$', stripped):
            out.append('<hr style="border: none; border-top: 1px solid rgba(255,255,255,0.12); margin: 8px 0;"/>')
            continue

        # Headings (#, ##, ###, ####, #####, ######)
        h_match = re.match(r'^(#{1,6})\s+(.*)$', stripped)
        if h_match:
            level = len(h_match.group(1))
            htext = h_match.group(2)
            sizes = {1: '16px', 2: '15px', 3: '14px', 4: '13px', 5: '12.5px', 6: '12px'}
            colors = {1: '#60a5fa', 2: '#93c5fd', 3: '#38bdf8', 4: '#e2e8f0', 5: '#cbd5e1', 6: '#94a3b8'}
            size = sizes.get(level, '14px')
            color = colors.get(level, '#60a5fa')
            out.append(f'<div style="font-size: {size}; font-weight: 700; color: {color}; margin: 8px 0 3px 0;">{htext}</div>')
            continue

        # Bullet List Items (*, -, +)
        list_match = re.match(r'^[\*\-\+]\s+(.*)$', stripped)
        if list_match:
            item_text = list_match.group(1)
            out.append(f'<div style="margin-left: 12px; margin-bottom: 3px;"><span style="color: #38bdf8; font-weight: bold;">•</span> {item_text}</div>')
            continue

        # Numbered List Items (1., 2.)
        num_match = re.match(r'^(\d+)\.\s+(.*)$', stripped)
        if num_match:
            num = num_match.group(1)
            item_text = num_match.group(2)
            out.append(f'<div style="margin-left: 12px; margin-bottom: 3px;"><span style="color: #a78bfa; font-weight: bold;">{num}.</span> {item_text}</div>')
            continue

        # Blockquote (> )
        if stripped.startswith('>'):
            qtext = stripped.lstrip('> ').strip()
            out.append(f'<div style="border-left: 3px solid #38bdf8; padding-left: 8px; color: #94a3b8; font-style: italic; margin: 4px 0;">{qtext}</div>')
            continue

        out.append(f'<div style="margin-bottom: 3px; line-height: 1.45;">{stripped}</div>')

    res = ''.join(out)

    # Inline Markdown Transformations
    # Bold + Italic (***text*** or ___text___)
    res = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong style="color: #f8fafc;"><em>\1</em></strong>', res)
    res = re.sub(r'___(.+?)___', r'<strong style="color: #f8fafc;"><em>\1</em></strong>', res)
    # Bold (**text** or __text__)
    res = re.sub(r'\*\*(.+?)\*\*', r'<strong style="color: #f8fafc; font-weight: 700;">\1</strong>', res)
    res = re.sub(r'__(.+?)__', r'<strong style="color: #f8fafc; font-weight: 700;">\1</strong>', res)
    # Italic (*text* or _text_)
    res = re.sub(r'\*(.+?)\*', r'<em>\1</em>', res)
    res = re.sub(r'(?<!\w)_(.+?)_(?!\w)', r'<em>\1</em>', res)
    # Inline code (`code`)
    res = re.sub(r'`([^`]+)`', r'<code style="background: #0f172a; color: #38bdf8; border: 1px solid #1e293b; padding: 1px 5px; border-radius: 4px; font-family: monospace; font-size: 11.5px;">\1</code>', res)
    # Strikethrough (~~text~~)
    res = re.sub(r'~~(.+?)~~', r'<s>\1</s>', res)
    # Links [text](url)
    res = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" style="color: #60a5fa; text-decoration: underline;">\1</a>', res)

    return res


class ChatRelaySignals(QObject):
    chunk_received = pyqtSignal(str)
    swarm_step_received = pyqtSignal(object)
    status_updated = pyqtSignal(str)
    generation_finished = pyqtSignal(object)


class CodeBlockWidget(QFrame):
    """Clean syntax code block with language header, copy button, and interactive in-browser sandbox runner."""
    def __init__(self, code_text: str, language: str = "python", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.code_text = code_text
        self.language = (language or "code").lower().strip()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(0)
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            QFrame {
                background-color: #0d1117;
                border: 1px solid #30363d;
                border-radius: 6px;
                margin-top: 4px;
                margin-bottom: 4px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 8)
        layout.setSpacing(4)

        # Header with language, run button, and copy button
        hdr = QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 0)
        lbl_lang = QLabel(self.language.upper())
        lbl_lang.setStyleSheet("color: #8b949e; font-size: 10px; font-weight: 700; letter-spacing: 0.5px;")
        hdr.addWidget(lbl_lang)
        hdr.addStretch()

        # In-Browser Run Button (for Python/Playwright/JS snippets)
        if self.language in ["python", "py", "playwright", "javascript", "js"]:
            self.btn_run = QPushButton("▶ Run in Active Tab")
            self.btn_run.setFixedHeight(22)
            self.btn_run.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_run.setStyleSheet("""
                QPushButton {
                    background-color: #238636;
                    color: #ffffff;
                    border: 1px solid #2ea043;
                    border-radius: 4px;
                    font-size: 10px;
                    font-weight: 700;
                    padding: 1px 8px;
                }
                QPushButton:hover {
                    background-color: #2ea043;
                }
            """)
            self.btn_run.clicked.connect(self._run_in_sandbox)
            hdr.addWidget(self.btn_run)

        self.btn_copy = QPushButton("📋 Copy")
        self.btn_copy.setFixedHeight(22)
        self.btn_copy.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 4px;
                font-size: 10px;
                padding: 1px 8px;
            }
            QPushButton:hover {
                background-color: #30363d;
                color: #ffffff;
            }
        """)
        self.btn_copy.clicked.connect(self._copy_code)
        hdr.addWidget(self.btn_copy)
        layout.addLayout(hdr)

        # Code text display
        txt = QTextEdit()
        txt.setReadOnly(True)
        txt.setPlainText(self.code_text)
        txt.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        txt.setMinimumWidth(0)
        txt.setStyleSheet("""
            QTextEdit {
                background-color: transparent;
                color: #e6edf3;
                font-family: 'JetBrains Mono', 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                border: none;
            }
        """)
        lines = len(self.code_text.splitlines())
        calc_h = min(max(lines * 19 + 20, 60), 380)
        txt.setFixedHeight(calc_h)
        layout.addWidget(txt)

        # Expandable Execution Console
        self.console_box = QTextEdit()
        self.console_box.setReadOnly(True)
        self.console_box.setFixedHeight(80)
        self.console_box.setStyleSheet("""
            QTextEdit {
                background-color: #030712;
                color: #4ade80;
                font-family: monospace;
                font-size: 11px;
                border: 1px solid #1f2937;
                border-radius: 4px;
                padding: 4px;
            }
        """)
        self.console_box.hide()
        layout.addWidget(self.console_box)

    @qasync.asyncSlot()
    async def _run_in_sandbox(self):
        self.btn_run.setText("⏳ Running...")
        self.btn_run.setEnabled(False)
        self.console_box.show()
        self.console_box.setPlainText("⚡ Executing script in active browser sandbox...")

        bridge = BrowserCopilotBridge.get_instance()
        res = await bridge.execute_in_sandbox(self.code_text, timeout_sec=30.0)

        if res.get("success"):
            out = res.get("output") or res.get("result") or "Execution finished without output."
            self.console_box.setPlainText(f"✓ Success ({res.get('duration_ms')}ms):\n{out}")
            self.console_box.setStyleSheet("background-color: #030712; color: #4ade80; font-family: monospace; font-size: 11px; border: 1px solid #166534; border-radius: 4px;")
            self.btn_run.setText("✓ Done")
        else:
            err = res.get("error") or "Unknown error"
            self.console_box.setPlainText(f"✗ Failed ({res.get('duration_ms')}ms):\n{err}")
            self.console_box.setStyleSheet("background-color: #030712; color: #f87171; font-family: monospace; font-size: 11px; border: 1px solid #991b1b; border-radius: 4px;")
            self.btn_run.setText("✗ Failed")

        QTimer.singleShot(3000, lambda: [self.btn_run.setText("▶ Run in Active Tab"), self.btn_run.setEnabled(True)])

    def _copy_code(self):
        cb = QApplication.clipboard()
        if cb:
            cb.setText(self.code_text)
            self.btn_copy.setText("✓ Copied!")
            QTimer.singleShot(1500, lambda: self.btn_copy.setText("📋 Copy"))


class SwarmThoughtBox(QFrame):
    """Collapsible panel showing multi-agent reasoning steps, latency, and confidence."""
    def __init__(self, steps: List[Dict[str, Any]], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.steps = steps
        self.is_expanded = False
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            QFrame#SwarmBox {
                background-color: rgba(30, 41, 59, 0.45);
                border: 1px solid rgba(99, 102, 241, 0.35);
                border-radius: 8px;
                margin-top: 4px;
                margin-bottom: 6px;
            }
        """)
        self.setObjectName("SwarmBox")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # Header button to toggle collapse
        self.btn_toggle = QPushButton()
        self.btn_toggle.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #a5b4fc;
                font-size: 11.5px;
                font-weight: 700;
                text-align: left;
                border: none;
                padding: 0px;
            }
            QPushButton:hover {
                color: #c7d2fe;
            }
        """)
        self.btn_toggle.clicked.connect(self._toggle_expand)
        layout.addWidget(self.btn_toggle)

        # Container for sub-agent steps
        self.content_container = QWidget()
        c_layout = QVBoxLayout(self.content_container)
        c_layout.setContentsMargins(4, 4, 4, 4)
        c_layout.setSpacing(6)

        for step in self.steps:
            step_frame = QFrame()
            step_frame.setStyleSheet("""
                QFrame {
                    background-color: rgba(15, 23, 42, 0.6);
                    border: 1px solid rgba(148, 163, 184, 0.15);
                    border-radius: 6px;
                    padding: 4px;
                }
            """)
            s_layout = QVBoxLayout(step_frame)
            s_layout.setContentsMargins(6, 4, 6, 4)
            s_layout.setSpacing(2)

            role_lbl = QLabel(f"◈ {step.get('role_name', 'Agent')} ({step.get('model_name', 'LLM')}) • {step.get('latency_ms', 0):.0f}ms")
            role_lbl.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: 700;")
            s_layout.addWidget(role_lbl)

            thought_text = step.get('thought_process') or step.get('response_text', '')
            if thought_text:
                th_lbl = QLabel(thought_text)
                th_lbl.setWordWrap(True)
                th_lbl.setStyleSheet("color: #cbd5e1; font-size: 11px; margin-top: 2px;")
                s_layout.addWidget(th_lbl)

            c_layout.addWidget(step_frame)

        layout.addWidget(self.content_container)
        self._update_toggle_state()

    def _toggle_expand(self):
        self.is_expanded = not self.is_expanded
        self._update_toggle_state()

    def _update_toggle_state(self):
        count = len(self.steps)
        if self.is_expanded:
            self.btn_toggle.setText(f"▼ 🧠 Swarm Multi-Agent Reasoning ({count} Sub-Agents)")
            self.content_container.show()
        else:
            self.btn_toggle.setText(f"▶ 🧠 Swarm Multi-Agent Reasoning ({count} Sub-Agents) — Click to view thoughts")
            self.content_container.hide()


class AgentProfileCard(QFrame):
    """Interactive visual card for AI-synthesized browser profile creation."""
    def __init__(self, profile_data: Dict[str, Any], on_created_callback: Optional[Callable] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.profile_data = profile_data
        self.on_created_callback = on_created_callback
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(0)
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            QFrame#AgentProfileCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #111827, stop:1 #1e1b4b);
                border: 1px solid #6366f1;
                border-radius: 8px;
                margin-top: 6px;
                margin-bottom: 6px;
            }
        """)
        self.setObjectName("AgentProfileCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        hdr = QHBoxLayout()
        hdr_lbl = QLabel("⚡ AGENT ACTION: Synthesized Profile")
        hdr_lbl.setStyleSheet("color: #a5b4fc; font-weight: 700; font-size: 11.5px;")
        hdr.addWidget(hdr_lbl)
        hdr.addStretch()

        eng = str(self.profile_data.get('engine', 'camoufox')).upper()
        os_name = str(self.profile_data.get('os', 'windows')).upper()
        badge = QLabel(f"{eng} | {os_name}")
        badge.setStyleSheet("background: rgba(99, 102, 241, 0.25); color: #c7d2fe; border: 1px solid #6366f1; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 700;")
        hdr.addWidget(badge)
        layout.addLayout(hdr)

        p_name = self.profile_data.get("name", "Harmonized Profile")
        p_res = self.profile_data.get("screen_resolution", "1920x1080")
        p_cores = self.profile_data.get("hardware_concurrency", 8)
        p_ram = self.profile_data.get("device_memory", 8)
        p_country = self.profile_data.get("location", {}).get("country") or self.profile_data.get("country", "DE")
        p_gpu = self.profile_data.get("stealth", {}).get("webgl_renderer", "Mesa UHD Graphics")

        grid_text = (
            f'<div style="font-size: 12px; color: #e2e8f0; line-height: 1.5;">'
            f'<b>Name:</b> <span style="color: #38bdf8;">{p_name}</span> &nbsp;|&nbsp; '
            f'<b>Specs:</b> {p_cores} Cores / {p_ram} GB RAM &nbsp;|&nbsp; '
            f'<b>Resolution:</b> {p_res}<br/>'
            f'<b>Region:</b> {p_country} &nbsp;|&nbsp; '
            f'<b>GPU:</b> <span style="color: #94a3b8;">{p_gpu[:45]}...</span>'
            f'</div>'
        )
        lbl_info = QLabel()
        lbl_info.setTextFormat(Qt.TextFormat.RichText)
        lbl_info.setText(grid_text)
        lbl_info.setWordWrap(True)
        layout.addWidget(lbl_info)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_create = QPushButton("✨ Profil in OXBROWSER anlegen")
        self.btn_create.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_create.setStyleSheet("""
            QPushButton {
                background-color: #4f46e5;
                color: #ffffff;
                border: 1px solid #6366f1;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 700;
                font-size: 11.5px;
            }
            QPushButton:hover {
                background-color: #4338ca;
            }
        """)
        self.btn_create.clicked.connect(self._create_profile)
        btn_row.addWidget(self.btn_create)
        layout.addLayout(btn_row)

    def _create_profile(self):
        from engine.ai_agent_actions import AIAgentActionEngine
        engine = AIAgentActionEngine.get_instance()
        success, pid, msg = engine.create_profile(self.profile_data)
        if success:
            self.btn_create.setText("✓ Profil erfolgreich angelegt!")
            self.btn_create.setEnabled(False)
            self.btn_create.setStyleSheet("background-color: #059669; color: #ffffff; border: 1px solid #10b981; border-radius: 6px; padding: 6px 14px; font-weight: 700; font-size: 11.5px;")
            if self.on_created_callback:
                self.on_created_callback(pid)


class AgentBatchProfileCard(QFrame):
    """Interactive visual card for AI-synthesized batch profile creation."""
    def __init__(self, profiles_list: List[Dict[str, Any]], on_created_callback: Optional[Callable] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.profiles_list = profiles_list if isinstance(profiles_list, list) else []
        self.on_created_callback = on_created_callback
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(0)
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            QFrame#AgentBatchProfileCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #111827, stop:1 #1e1b4b);
                border: 1px solid #818cf8;
                border-radius: 8px;
                margin-top: 6px;
                margin-bottom: 6px;
            }
        """)
        self.setObjectName("AgentBatchProfileCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # Header
        hdr = QHBoxLayout()
        hdr_lbl = QLabel(f"⚡ AGENT ACTION: Synthesized Profile Batch ({len(self.profiles_list)} Profiles)")
        hdr_lbl.setStyleSheet("color: #a5b4fc; font-weight: 700; font-size: 12px;")
        hdr.addWidget(hdr_lbl)
        hdr.addStretch()

        badge = QLabel("BATCH SYNTHESIS")
        badge.setStyleSheet("background: rgba(99, 102, 241, 0.3); color: #c7d2fe; border: 1px solid #818cf8; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 700;")
        hdr.addWidget(badge)
        layout.addLayout(hdr)

        # Overview Table / Items Preview
        items_html = ['<div style="font-size: 11.5px; color: #e2e8f0; line-height: 1.45;">']
        for i, p in enumerate(self.profiles_list[:10], 1):
            p_name = p.get("name", f"Profile_{i}")
            p_os = str(p.get("os", "windows")).capitalize()
            p_cores = p.get("hardware_concurrency", 8)
            p_ram = p.get("device_memory", 8)
            p_res = p.get("screen_resolution", "1920x1080")
            p_country = p.get("location", {}).get("country") or p.get("country", "DE")
            items_html.append(f'<b>{i}. {p_name}</b> <span style="color: #94a3b8;">({p_os} | {p_country} | {p_cores}C/{p_ram}GB | {p_res})</span>')

        if len(self.profiles_list) > 10:
            items_html.append(f'<i style="color: #94a3b8;">... und {len(self.profiles_list) - 10} weitere Profile</i>')
        items_html.append('</div>')

        lbl_list = QLabel()
        lbl_list.setTextFormat(Qt.TextFormat.RichText)
        lbl_list.setText("<br/>".join(items_html))
        lbl_list.setWordWrap(True)
        layout.addWidget(lbl_list)

        # Action Button Row
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_create_all = QPushButton(f"✨ Alle {len(self.profiles_list)} Profile in OXBROWSER anlegen")
        self.btn_create_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_create_all.setStyleSheet("""
            QPushButton {
                background-color: #4f46e5;
                color: #ffffff;
                border: 1px solid #6366f1;
                border-radius: 6px;
                padding: 7px 16px;
                font-weight: 700;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #4338ca;
            }
        """)
        self.btn_create_all.clicked.connect(self._create_all_profiles)
        btn_row.addWidget(self.btn_create_all)
        layout.addLayout(btn_row)

    def _create_all_profiles(self):
        from engine.ai_agent_actions import AIAgentActionEngine
        engine = AIAgentActionEngine.get_instance()
        success, ids, msg = engine.create_batch_profiles(self.profiles_list)
        if success:
            self.btn_create_all.setText(f"✓ {len(ids)} Profile erfolgreich angelegt!")
            self.btn_create_all.setEnabled(False)
            self.btn_create_all.setStyleSheet("background-color: #059669; color: #ffffff; border: 1px solid #10b981; border-radius: 6px; padding: 7px 16px; font-weight: 700; font-size: 12px;")
            if self.on_created_callback:
                self.on_created_callback(ids)


class AgentWarmupCard(QFrame):
    """Interactive visual card for AI-synthesized Warmup Campaigns with 1-click execution."""
    def __init__(self, campaign_data: Dict[str, Any], on_start_callback: Optional[Callable] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.campaign_data = campaign_data
        self.on_start_callback = on_start_callback
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(0)
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            QFrame#AgentWarmupCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #18181b, stop:1 #064e3b);
                border: 1px solid #10b981;
                border-radius: 8px;
                margin-top: 6px;
                margin-bottom: 6px;
            }
        """)
        self.setObjectName("AgentWarmupCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        hdr = QHBoxLayout()
        hdr_lbl = QLabel("🎭 AGENT ACTION: Warmup Campaign Execution")
        hdr_lbl.setStyleSheet("color: #34d399; font-weight: 700; font-size: 12px;")
        hdr.addWidget(hdr_lbl)
        hdr.addStretch()

        cat = str(self.campaign_data.get('category') or self.campaign_data.get('geo_target') or 'UK & TECH').upper()
        persona = str(self.campaign_data.get('persona') or self.campaign_data.get('execution_mode') or 'AUTONOMOUS AGENT').upper()
        badge = QLabel(f"{cat} | {persona}")
        badge.setStyleSheet("background: rgba(16, 185, 129, 0.25); color: #6ee7b7; border: 1px solid #10b981; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 700;")
        hdr.addWidget(badge)
        layout.addLayout(hdr)

        c_name = self.campaign_data.get("campaign_name") or self.campaign_data.get("name") or "UK Google Search & Tech Trajectory"
        c_steps = self.campaign_data.get("total_steps") or self.campaign_data.get("max_pages") or 30
        c_dwell = self.campaign_data.get("dwell_time") or 45.0
        p_name = self.campaign_data.get("profile_name") or self.campaign_data.get("profile_id") or "Target Profile"
        p_proxy = self.campaign_data.get("proxy_binding") or self.campaign_data.get("proxy") or "Attached Proxy / Direct"
        c_stealth = self.campaign_data.get("stealth_profile") or "Camoufox Linux Engine with Minimum-Jerk Motion"

        grid_text = (
            f'<div style="font-size: 12px; color: #e2e8f0; line-height: 1.6;">'
            f'<b>Kampagne:</b> <span style="color: #34d399; font-weight: 700;">{c_name}</span> &nbsp;|&nbsp; '
            f'<b>Stufen:</b> <span style="color: #6ee7b7;">{c_steps} Schritte</span><br/>'
            f'<b>Ziel-Profil:</b> <span style="color: #38bdf8; font-weight: 600;">{p_name}</span> &nbsp;|&nbsp; '
            f'<b>Proxy-Route:</b> <span style="color: #cbd5e1;">{p_proxy}</span><br/>'
            f'<b>Stealth-Modus:</b> <span style="color: #94a3b8; font-size: 11px;">{c_stealth}</span>'
            f'</div>'
        )
        lbl_info = QLabel()
        lbl_info.setTextFormat(Qt.TextFormat.RichText)
        lbl_info.setText(grid_text)
        lbl_info.setWordWrap(True)
        layout.addWidget(lbl_info)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_save = QPushButton("💾 Kampagne speichern")
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.setStyleSheet("""
            QPushButton {
                background-color: #27272a;
                color: #e4e4e7;
                border: 1px solid #3f3f46;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 600;
                font-size: 11.5px;
            }
            QPushButton:hover {
                background-color: #3f3f46;
            }
        """)
        self.btn_save.clicked.connect(self._save_campaign)
        btn_row.addWidget(self.btn_save)

        self.btn_start = QPushButton(f"🚀 Warmup direkt ausführen ({c_steps} Steps)")
        self.btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10b981);
                color: #ffffff;
                border: 1px solid #34d399;
                border-radius: 6px;
                padding: 6px 18px;
                font-weight: 700;
                font-size: 12px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #047857, stop:1 #059669);
            }
        """)
        self.btn_start.clicked.connect(self._start_warmup)
        btn_row.addWidget(self.btn_start)

        layout.addLayout(btn_row)

    def _save_campaign(self):
        from storage.warmup_campaign_manager import WarmupCampaignManager
        c_mgr = WarmupCampaignManager.get_instance()
        name = self.campaign_data.get("campaign_name") or self.campaign_data.get("name") or self.campaign_data.get("id") or "campaign"
        c_mgr.save_campaign(name, self.campaign_data)
        self.btn_save.setText("✓ Gespeichert!")
        self.btn_save.setEnabled(False)

    def _start_warmup(self):
        if self.on_start_callback:
            self.on_start_callback(self.campaign_data)


class AgentLaunchControlCard(QFrame):
    """Interactive visual card for AI-driven Browser Launch & Stop operations."""
    def __init__(self, action_data: Dict[str, Any], on_action_callback: Optional[Callable] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.action_data = action_data
        self.on_action_callback = on_action_callback
        self.target = action_data.get("target") or action_data.get("profile_id") or action_data.get("name", "Target Profile")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(0)
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            QFrame#AgentLaunchCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #181b22, stop:1 #1e293b);
                border: 1px solid #3b82f6;
                border-radius: 8px;
                margin-top: 6px;
                margin-bottom: 6px;
            }
        """)
        self.setObjectName("AgentLaunchCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        hdr = QHBoxLayout()
        hdr_lbl = QLabel("🚀 AGENT ACTION: Browser Lifecycle Control")
        hdr_lbl.setStyleSheet("color: #60a5fa; font-weight: 700; font-size: 11.5px;")
        hdr.addWidget(hdr_lbl)
        hdr.addStretch()

        badge = QLabel(f"Target: {self.target}")
        badge.setStyleSheet("background: rgba(59, 130, 246, 0.2); color: #93c5fd; border: 1px solid #3b82f6; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 700;")
        hdr.addWidget(badge)
        layout.addLayout(hdr)

        lbl_desc = QLabel(f"Der AI Copilot hat eine Lifecycle-Aktion für Profil <b>{self.target}</b> vorbereitet.")
        lbl_desc.setStyleSheet("color: #e2e8f0; font-size: 12px;")
        layout.addWidget(lbl_desc)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_stop = QPushButton("🛑 Stoppen")
        self.btn_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stop.setStyleSheet("""
            QPushButton {
                background-color: #27272a;
                color: #f87171;
                border: 1px solid #ef4444;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #3f3f46; }
        """)
        self.btn_stop.clicked.connect(self._stop_profile)
        btn_row.addWidget(self.btn_stop)

        self.btn_launch = QPushButton("🚀 Jetzt starten")
        self.btn_launch.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_launch.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                border: 1px solid #3b82f6;
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: 700;
                font-size: 11.5px;
            }
            QPushButton:hover { background-color: #1d4ed8; }
        """)
        self.btn_launch.clicked.connect(self._launch_profile)
        btn_row.addWidget(self.btn_launch)

        layout.addLayout(btn_row)

    def _launch_profile(self):
        from engine.ai_agent_actions import AIAgentActionEngine
        engine = AIAgentActionEngine.get_instance()
        success, msg = engine.launch_profile(self.target)
        if success:
            self.btn_launch.setText("✓ Profil läuft")
            self.btn_launch.setEnabled(False)
            self.btn_launch.setStyleSheet("background-color: #059669; color: #ffffff; border: 1px solid #10b981; border-radius: 6px; padding: 6px 16px; font-weight: 700; font-size: 11.5px;")
        else:
            self.btn_launch.setText("Fehler beim Start")

    def _stop_profile(self):
        from engine.ai_agent_actions import AIAgentActionEngine
        engine = AIAgentActionEngine.get_instance()
        if str(self.target).lower() == "all":
            engine.stop_all_profiles()
        else:
            engine.stop_profile(self.target)
        self.btn_stop.setText("✓ Gestoppt")
        self.btn_stop.setEnabled(False)


class AgentAuditReportCard(QFrame):
    """Interactive visual card for Senior Security & Tensor Audits with 1-Click Auto-Patching."""
    def __init__(self, action_data: Dict[str, Any], on_action_callback: Optional[Callable] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.action_data = action_data
        self.on_action_callback = on_action_callback
        self.target = action_data.get("target") or action_data.get("profile_id") or action_data.get("name", "Profil 1")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(0)
        self._init_ui()

    def _init_ui(self):
        from engine.ai_agent_actions import AIAgentActionEngine
        engine = AIAgentActionEngine.get_instance()
        success, audit_res, _ = engine.audit_profile(self.target)

        self.audit_res = audit_res if success else {}
        health_score = self.audit_res.get("health_score", 80.0)
        ml_score = self.audit_res.get("ml_tensor_score", 85.0)
        anomalies = self.audit_res.get("anomalies", [])

        color = "#10b981" if health_score >= 90 else ("#f59e0b" if health_score >= 70 else "#ef4444")

        self.setStyleSheet(f"""
            QFrame#AgentAuditCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #181b22, stop:1 #1e1e24);
                border: 1px solid {color};
                border-radius: 8px;
                margin-top: 6px;
                margin-bottom: 6px;
            }}
        """)
        self.setObjectName("AgentAuditCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        hdr = QHBoxLayout()
        hdr_lbl = QLabel("🛡️ SENIOR AUDIT & TENSOR VERIFICATION")
        hdr_lbl.setStyleSheet(f"color: {color}; font-weight: 700; font-size: 11.5px;")
        hdr.addWidget(hdr_lbl)
        hdr.addStretch()

        badge = QLabel(f"Score: {health_score}% | ML Tensor: {ml_score}%")
        badge.setStyleSheet(f"background: rgba(16, 185, 129, 0.15); color: {color}; border: 1px solid {color}; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 700;")
        hdr.addWidget(badge)
        layout.addLayout(hdr)

        p_name = self.audit_res.get("profile_name", self.target)
        if not anomalies:
            info_html = f"<div style='font-size: 12px; color: #34d399;'>✓ Profil <b>{p_name}</b> ist zu 100% mathematisch und hardware-harmonisiert. Keine Anomalien gefunden.</div>"
        else:
            items = []
            for an in anomalies[:4]:
                sev = an.get("severity", "HIGH")
                s_color = "#f87171" if sev == "CRITICAL" else ("#fbbf24" if sev == "HIGH" else "#93c5fd")
                items.append(f"<li style='margin-bottom: 3px;'><b style='color: {s_color};'>[{sev}]</b> {an.get('message')}</li>")
            info_html = (
                f"<div style='font-size: 12px; color: #e2e8f0;'>"
                f"Gefundene Optimierungen für <b>{p_name}</b>:"
                f"<ul style='margin-top: 4px; margin-bottom: 4px; padding-left: 18px;'>{''.join(items)}</ul>"
                f"</div>"
            )

        lbl_info = QLabel()
        lbl_info.setTextFormat(Qt.TextFormat.RichText)
        lbl_info.setText(info_html)
        lbl_info.setWordWrap(True)
        layout.addWidget(lbl_info)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_patch = QPushButton("⚡ 1-Klick Auto-Patch anwenden")
        self.btn_patch.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_patch.setStyleSheet("""
            QPushButton {
                background-color: #8b5cf6;
                color: #ffffff;
                border: 1px solid #a78bfa;
                border-radius: 6px;
                padding: 7px 16px;
                font-weight: 700;
                font-size: 11.5px;
            }
            QPushButton:hover { background-color: #7c3aed; }
        """)
        self.btn_patch.clicked.connect(self._apply_patches)
        if not anomalies:
            self.btn_patch.setText("✓ Keine Patches nötig")
            self.btn_patch.setEnabled(False)
            self.btn_patch.setStyleSheet("background-color: #27272a; color: #71717a; border: 1px solid #3f3f46; border-radius: 6px; padding: 7px 16px; font-weight: 600; font-size: 11.5px;")

        btn_row.addWidget(self.btn_patch)
        layout.addLayout(btn_row)

    def _apply_patches(self):
        from engine.ai_agent_actions import AIAgentActionEngine
        engine = AIAgentActionEngine.get_instance()
        success, msg, changes = engine.apply_audit_patches(self.target)
        if success:
            self.btn_patch.setText(f"✓ {len(changes)} Patches angewendet (100% Score)")
            self.btn_patch.setEnabled(False)
            self.btn_patch.setStyleSheet("background-color: #059669; color: #ffffff; border: 1px solid #10b981; border-radius: 6px; padding: 7px 16px; font-weight: 700; font-size: 11.5px;")


class AgentBenchmarkCard(QFrame):
    """Interactive visual card for Senior Stealth Environment Benchmarks."""
    def __init__(self, action_data: Dict[str, Any], on_action_callback: Optional[Callable] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.action_data = action_data
        self.target = action_data.get("target", "Profil 1")
        self.benchmark = str(action_data.get("benchmark", "creepjs")).upper()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(0)
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            QFrame#AgentBenchCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #181b22, stop:1 #1e293b);
                border: 1px solid #06b6d4;
                border-radius: 8px;
                margin-top: 6px;
                margin-bottom: 6px;
            }
        """)
        self.setObjectName("AgentBenchCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        hdr = QHBoxLayout()
        hdr_lbl = QLabel(f"🔬 ENVIRONMENT BENCHMARK: {self.benchmark}")
        hdr_lbl.setStyleSheet("color: #22d3ee; font-weight: 700; font-size: 11.5px;")
        hdr.addWidget(hdr_lbl)
        hdr.addStretch()

        badge = QLabel(f"Target: {self.target}")
        badge.setStyleSheet("background: rgba(6, 182, 212, 0.2); color: #67e8f9; border: 1px solid #06b6d4; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 700;")
        hdr.addWidget(badge)
        layout.addLayout(hdr)

        lbl_desc = QLabel(f"Startet automatisierten Fingerprint & Anti-Detection Benchmark (<b>{self.benchmark}</b>) für <b>{self.target}</b>.")
        lbl_desc.setStyleSheet("color: #e2e8f0; font-size: 12px;")
        layout.addWidget(lbl_desc)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_run = QPushButton(f"🔬 {self.benchmark} Test starten")
        self.btn_run.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_run.setStyleSheet("""
            QPushButton {
                background-color: #0891b2;
                color: #ffffff;
                border: 1px solid #06b6d4;
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: 700;
                font-size: 11.5px;
            }
            QPushButton:hover { background-color: #0e7490; }
        """)
        self.btn_run.clicked.connect(self._run_benchmark)
        btn_row.addWidget(self.btn_run)
        layout.addLayout(btn_row)

    def _run_benchmark(self):
        from engine.ai_agent_actions import AIAgentActionEngine
        engine = AIAgentActionEngine.get_instance()
        engine.launch_profile(self.target)
        self.btn_run.setText("✓ Test gestartet")
        self.btn_run.setEnabled(False)


class ChatBubble(QFrame):
    """Renders a single message bubble for user or assistant."""
    def __init__(
        self,
        message: ChatMessage,
        is_streaming: bool = False,
        on_action_callback: Optional[Callable] = None,
        on_warmup_callback: Optional[Callable] = None,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.msg = message
        self.is_streaming = is_streaming
        self.on_action_callback = on_action_callback
        self.on_warmup_callback = on_warmup_callback
        self.streaming_label: Optional[QLabel] = None
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setMinimumWidth(0)
        self._init_ui()

    def _init_ui(self):
        is_user = self.msg.role == "user"
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        if is_user:
            self.setStyleSheet("""
                QFrame#UserBubble {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1e3a8a, stop:1 #1e293b);
                    border: 1px solid rgba(59, 130, 246, 0.4);
                    border-radius: 12px;
                    margin-left: 80px;
                    margin-right: 4px;
                }
            """)
            self.setObjectName("UserBubble")
        else:
            self.setStyleSheet("""
                QFrame#AssistantBubble {
                    background-color: #1a1d24;
                    border: 1px solid #2d333b;
                    border-left: 3px solid #3b82f6;
                    border-radius: 10px;
                    margin-left: 4px;
                    margin-right: 60px;
                }
            """)
            self.setObjectName("AssistantBubble")

        # Top line: Avatar/Role, Model Pill, Timestamp, Copy Button
        top_row = QHBoxLayout()
        top_row.setSpacing(6)
        
        avatar_icon = "👤" if is_user else "🤖"
        title = "You" if is_user else (self.msg.model or "AI Assistant")
        lbl_role = QLabel(f"{avatar_icon} {title}")
        lbl_role.setStyleSheet("color: #ffffff; font-size: 11.5px; font-weight: 700;")
        top_row.addWidget(lbl_role)

        top_row.addStretch()

        ts = time.strftime('%H:%M:%S', time.localtime(self.msg.timestamp))
        lbl_time = QLabel(ts)
        lbl_time.setStyleSheet("color: #64748b; font-size: 10px;")
        top_row.addWidget(lbl_time)

        self.btn_copy_msg = QPushButton("📋")
        self.btn_copy_msg.setFixedSize(24, 20)
        self.btn_copy_msg.setToolTip("Copy this message to clipboard")
        self.btn_copy_msg.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.06);
                color: #94a3b8;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                font-size: 11px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.18);
                color: #ffffff;
                border-color: #38bdf8;
            }
        """)
        self.btn_copy_msg.clicked.connect(self._copy_message)
        top_row.addWidget(self.btn_copy_msg)

        layout.addLayout(top_row)

        # Image thumbnail if present
        if self.msg.image_b64:
            try:
                img_data = base64.b64decode(self.msg.image_b64)
                pix = QPixmap()
                pix.loadFromData(img_data)
                if not pix.isNull():
                    thumb = QLabel()
                    thumb.setPixmap(pix.scaled(240, 160, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                    thumb.setStyleSheet("border: 1px solid #475569; border-radius: 6px; padding: 2px;")
                    layout.addWidget(thumb)
            except Exception as e:
                logger.debug(f"Thumbnail render error: {e}")

        # Swarm breakdown if present
        if self.msg.swarm_breakdown:
            swarm_box = SwarmThoughtBox(self.msg.swarm_breakdown)
            layout.addWidget(swarm_box)

        # Content parsing: extract code blocks and text segments
        if self.is_streaming:
            self.streaming_label = QLabel()
            self.streaming_label.setTextFormat(Qt.TextFormat.PlainText)
            self.streaming_label.setWordWrap(True)
            self.streaming_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.streaming_label.setStyleSheet("color: #e2e8f0; font-size: 13px; line-height: 1.45;")
            self.streaming_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            self.streaming_label.setMinimumWidth(0)
            layout.addWidget(self.streaming_label)
        else:
            self._render_content(layout, self.msg.content)

    def _copy_message(self):
        cb = QApplication.clipboard()
        if cb and self.msg.content:
            cb.setText(self.msg.content)
            self.btn_copy_msg.setText("✓")
            QTimer.singleShot(1500, lambda: self.btn_copy_msg.setText("📋"))

    def _render_content(self, parent_layout: Optional[QLayout], raw_content: str):
        if parent_layout is None:
            return

        if "```" not in raw_content:
            lbl = QLabel()
            lbl.setTextFormat(Qt.TextFormat.RichText)
            lbl.setText(format_markdown_to_rich_html(raw_content))
            lbl.setWordWrap(True)
            lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.LinksAccessibleByMouse)
            lbl.setOpenExternalLinks(True)
            lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            lbl.setMinimumWidth(0)
            lbl.setStyleSheet("color: #e2e8f0; font-size: 13px; line-height: 1.45;")
            parent_layout.addWidget(lbl)
            return

        # Split markdown code blocks
        parts = raw_content.split("```")
        for i, part in enumerate(parts):
            if i % 2 == 0:
                # Normal text
                t = part.strip()
                if t:
                    lbl = QLabel()
                    lbl.setTextFormat(Qt.TextFormat.RichText)
                    lbl.setText(format_markdown_to_rich_html(t))
                    lbl.setWordWrap(True)
                    lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.LinksAccessibleByMouse)
                    lbl.setOpenExternalLinks(True)
                    lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
                    lbl.setMinimumWidth(0)
                    lbl.setStyleSheet("color: #e2e8f0; font-size: 13px; line-height: 1.45;")
                    parent_layout.addWidget(lbl)
            else:
                # Code block or Action block
                raw_block = part.strip()
                action_type = None
                action_json_str = None

                # Check if block starts with action: in header or first line
                lines = part.split("\n")
                if lines and lines[0].strip().lower().startswith("action:"):
                    action_type = lines[0].strip().lower().replace("action:", "").strip()
                    action_json_str = "\n".join(lines[1:]).strip()
                elif len(lines) > 1:
                    # Check if second line is action: (e.g. ```json \n action:save_campaign)
                    first_line = lines[0].strip().lower()
                    second_line = lines[1].strip().lower()
                    if second_line.startswith("action:"):
                        action_type = second_line.replace("action:", "").strip()
                        action_json_str = "\n".join(lines[2:]).strip()
                    elif "action:" in raw_block:
                        for idx, l in enumerate(lines):
                            if l.strip().lower().startswith("action:"):
                                action_type = l.strip().lower().replace("action:", "").strip()
                                action_json_str = "\n".join(lines[idx+1:]).strip()
                                break

                if action_type and action_json_str:
                    try:
                        # Extract JSON between first '{' or '[' and last '}' or ']'
                        first_brace = min([p for p in [action_json_str.find('{'), action_json_str.find('[')] if p != -1], default=-1)
                        last_brace = max(action_json_str.rfind('}'), action_json_str.rfind(']'))
                        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                            json_payload = action_json_str[first_brace:last_brace+1]
                        else:
                            json_payload = action_json_str

                        action_data = json.loads(json_payload)
                        if action_type in ["create_batch_profiles", "create_profiles", "batch_profiles"] or (action_type == "create_profile" and isinstance(action_data, list)):
                            profiles = action_data.get("profiles", action_data) if isinstance(action_data, dict) else action_data
                            card = AgentBatchProfileCard(profiles, on_created_callback=self.on_action_callback)
                            parent_layout.addWidget(card)
                            continue
                        elif action_type == "create_profile":
                            if isinstance(action_data, dict) and "profiles" in action_data and isinstance(action_data["profiles"], list):
                                card = AgentBatchProfileCard(action_data["profiles"], on_created_callback=self.on_action_callback)
                                parent_layout.addWidget(card)
                                continue
                            card = AgentProfileCard(action_data, on_created_callback=self.on_action_callback)
                            parent_layout.addWidget(card)
                            continue
                        elif action_type in ["launch_profile", "start_profile", "stop_profile"]:
                            card = AgentLaunchControlCard(action_data if isinstance(action_data, dict) else {"target": str(action_data)}, on_action_callback=self.on_action_callback)
                            parent_layout.addWidget(card)
                            continue
                        elif action_type in ["audit_profile", "apply_audit_patches", "patch_profile", "audit"]:
                            card = AgentAuditReportCard(action_data if isinstance(action_data, dict) else {"target": str(action_data)}, on_action_callback=self.on_action_callback)
                            parent_layout.addWidget(card)
                            continue
                        elif action_type in ["run_benchmark", "benchmark"]:
                            card = AgentBenchmarkCard(action_data if isinstance(action_data, dict) else {"target": str(action_data)}, on_action_callback=self.on_action_callback)
                            parent_layout.addWidget(card)
                            continue
                        elif action_type in ["save_campaign", "start_warmup", "warmup_campaign"]:
                            card = AgentWarmupCard(action_data, on_start_callback=self.on_warmup_callback)
                            parent_layout.addWidget(card)
                            continue
                    except Exception as ex:
                        logger.debug(f"Action card render error: {ex}")

                lines_split = part.split("\n", 1)
                header = lines_split[0].strip()
                body = lines_split[1] if len(lines_split) > 1 else ""
                lang = header if len(lines_split) > 1 and len(header) < 15 else "code"
                code_body = body if len(lines_split) > 1 and len(header) < 15 else part
                cb_widget = CodeBlockWidget(code_body.strip(), language=lang)
                parent_layout.addWidget(cb_widget)

    def append_chunk(self, chunk: str):
        """Live updates content for streaming assistant bubble without destroying/recreating layout on every chunk."""
        self.msg.content += chunk
        if self.streaming_label is not None:
            self.streaming_label.setText(self.msg.content)
        else:
            lay = self.layout()
            if lay is not None:
                while lay.count() > 1:
                    item = lay.takeAt(1)
                    if item is not None:
                        w = item.widget()
                        if w is not None:
                            w.deleteLater()
                self._render_content(lay, self.msg.content)

    def finalize_render(self):
        """Called once when generation is complete: converts raw streamed text to rich formatting and interactive code blocks."""
        self.is_streaming = False
        lay = self.layout()
        if lay is not None:
            if self.streaming_label is not None:
                lay.removeWidget(self.streaming_label)
                self.streaming_label.deleteLater()
                self.streaming_label = None
            self._render_content(lay, self.msg.content)


class AIChatView(QWidget):
    """
    State-of-the-Art AI Copilot & Swarm Chat Interactive View:
    - Chat with any individual local or cloud model
    - Chat with Multi-Agent Swarm (Consensus, Specialist, Auto-Full)
    - Active Profile Context binding & live anti-detect interactions
    - Real-time token streaming & typing effects
    - Multimodal image attachments
    - Quick Action prompt chips
    """

    def __init__(self, profile_manager: Optional[ProfileManager] = None, launcher: Optional[BrowserLauncher] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.profile_manager = profile_manager or ProfileManager()
        self.launcher = launcher or BrowserLauncher.get_instance(self.profile_manager)
        BrowserCopilotBridge.get_instance(self.launcher)
        self.chat_engine = AIChatEngine.get_instance()
        self.signals = ChatRelaySignals()
        
        self._is_streaming = False
        self._current_assistant_bubble: Optional[ChatBubble] = None
        self._attached_image_b64: Optional[str] = None

        self._init_signals()
        self._init_ui()
        self.reload_profiles()

    def _get_icon(self, name: str) -> QIcon:
        return QIcon(os.path.join(os.path.dirname(__file__), "..", "assets", "icons", f"{name}.svg"))

    def _init_signals(self):
        self.signals.chunk_received.connect(self._on_chunk)
        self.signals.swarm_step_received.connect(self._on_swarm_step)
        self.signals.status_updated.connect(self._on_status)
        self.signals.generation_finished.connect(self._on_finished)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(8)

        # ---------------------------------------------------------------------
        # 1. TOP HEADER TOOLBAR (Model, Persona, Profile Context, Actions)
        # ---------------------------------------------------------------------
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background-color: #181b22;
                border: 1px solid #282e38;
                border-radius: 8px;
            }
        """)
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(12, 8, 12, 8)
        header_layout.setSpacing(10)

        # Model / Swarm Selector
        lbl_mod = QLabel("Model / Swarm:")
        lbl_mod.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 700;")
        header_layout.addWidget(lbl_mod)

        self.combo_model = QComboBox()
        self.combo_model.setMinimumWidth(220)
        self._populate_model_options()
        header_layout.addWidget(self.combo_model)

        # Persona Selector
        lbl_per = QLabel("Persona:")
        lbl_per.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 700; margin-left: 6px;")
        header_layout.addWidget(lbl_per)

        self.combo_persona = QComboBox()
        self.combo_persona.setMinimumWidth(160)
        for key, p_data in SYSTEM_PERSONAS.items():
            self.combo_persona.addItem(p_data["name"], key)
        self.combo_persona.addItem("✏️ Custom System Prompt...", "custom")
        self.combo_persona.currentIndexChanged.connect(self._on_persona_changed)
        header_layout.addWidget(self.combo_persona)

        # Language Selector
        lbl_lang = QLabel("Language:")
        lbl_lang.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 700; margin-left: 6px;")
        header_layout.addWidget(lbl_lang)

        self.combo_language = QComboBox()
        self.combo_language.setMinimumWidth(130)
        for code, l_data in SUPPORTED_CHAT_LANGUAGES.items():
            self.combo_language.addItem(f"{l_data['flag']} {l_data['name']}", code)
        cur_lang = self.chat_engine.get_preferred_language()
        idx = self.combo_language.findData(cur_lang)
        if idx >= 0:
            self.combo_language.setCurrentIndex(idx)
        self.combo_language.currentIndexChanged.connect(self._on_language_changed)
        header_layout.addWidget(self.combo_language)

        # Active Profile Context Selector
        lbl_prof = QLabel("Context Profile:")
        lbl_prof.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 700; margin-left: 6px;")
        header_layout.addWidget(lbl_prof)

        self.combo_profile = QComboBox()
        self.combo_profile.setMinimumWidth(150)
        header_layout.addWidget(self.combo_profile)

        header_layout.addStretch()

        # Status Badge (fixed width to prevent header resizing on status changes)
        self.status_badge = StatusBadge("Ready")
        self.status_badge.setFixedWidth(145)
        header_layout.addWidget(self.status_badge)

        # Quick Action Buttons
        self.btn_copy_all = QPushButton(" Copy All")
        self.btn_copy_all.setIcon(self._get_icon("copy"))
        self.btn_copy_all.setProperty("class", "SecondaryButton")
        self.btn_copy_all.setFixedHeight(30)
        self.btn_copy_all.setToolTip("Copy entire conversation to clipboard (Markdown)")
        self.btn_copy_all.clicked.connect(self._copy_all_chat)
        header_layout.addWidget(self.btn_copy_all)

        self.btn_export = QPushButton(" Export")
        self.btn_export.setIcon(self._get_icon("file-text"))
        self.btn_export.setProperty("class", "SecondaryButton")
        self.btn_export.setFixedHeight(30)
        self.btn_export.clicked.connect(self._export_chat)
        header_layout.addWidget(self.btn_export)

        self.btn_clear = QPushButton(" Clear")
        self.btn_clear.setIcon(self._get_icon("trash-2"))
        self.btn_clear.setProperty("class", "DangerButton")
        self.btn_clear.setFixedHeight(30)
        self.btn_clear.clicked.connect(self._clear_chat)
        header_layout.addWidget(self.btn_clear)

        main_layout.addWidget(header_frame)

        # ---------------------------------------------------------------------
        # 2. CHAT SCROLL AREA & MESSAGE CONTAINER
        # ---------------------------------------------------------------------
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #0f1117;
                border: 1px solid #232834;
                border-radius: 8px;
            }
        """)

        self.chat_container = QWidget()
        self.chat_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(14, 14, 14, 14)
        self.chat_layout.setSpacing(12)
        self.chat_layout.addStretch()

        self.scroll_area.setWidget(self.chat_container)
        main_layout.addWidget(self.scroll_area, stretch=1)

        # Welcome message
        self._add_welcome_message()

        # ---------------------------------------------------------------------
        # 3. INTERACTIVE QUICK PROMPT CHIPS
        # ---------------------------------------------------------------------
        chips_frame = QFrame()
        chips_layout = QHBoxLayout(chips_frame)
        chips_layout.setContentsMargins(4, 0, 4, 0)
        chips_layout.setSpacing(8)

        lbl_chips = QLabel("Quick Actions:")
        lbl_chips.setStyleSheet("color: #64748b; font-size: 11px; font-weight: 700;")
        chips_layout.addWidget(lbl_chips)

        chip_prof = QPushButton("✨ Profil erstellen")
        chip_prof.setStyleSheet(self._chip_style())
        chip_prof.clicked.connect(lambda: self._quick_action("create_profile"))
        chips_layout.addWidget(chip_prof)

        chip_audit = QPushButton("🔍 Profil Audit")
        chip_audit.setStyleSheet(self._chip_style())
        chip_audit.clicked.connect(lambda: self._quick_action("audit"))
        chips_layout.addWidget(chip_audit)

        chip_pentest = QPushButton("🎯 OWASP & Pentest Audit")
        chip_pentest.setStyleSheet(self._chip_style())
        chip_pentest.clicked.connect(lambda: self._quick_action("pentest"))
        chips_layout.addWidget(chip_pentest)

        chip_evasion = QPushButton("⚔️ WAF & Bot Evasion")
        chip_evasion.setStyleSheet(self._chip_style())
        chip_evasion.clicked.connect(lambda: self._quick_action("evasion"))
        chips_layout.addWidget(chip_evasion)

        chip_forensics = QPushButton("🔬 TLS & Network Forensic")
        chip_forensics.setStyleSheet(self._chip_style())
        chip_forensics.clicked.connect(lambda: self._quick_action("forensics"))
        chips_layout.addWidget(chip_forensics)

        chip_script = QPushButton("⚡ Playwright PoC")
        chip_script.setStyleSheet(self._chip_style())
        chip_script.clicked.connect(lambda: self._quick_action("playwright"))
        chips_layout.addWidget(chip_script)

        chip_warmup = QPushButton("🔥 Warmup Kampagne")
        chip_warmup.setStyleSheet(self._chip_style())
        chip_warmup.clicked.connect(lambda: self._quick_action("create_warmup"))
        chips_layout.addWidget(chip_warmup)

        chips_layout.addStretch()
        main_layout.addWidget(chips_frame)

        # ---------------------------------------------------------------------
        # 4. INPUT & ATTACHMENT CONTROL BAR
        # ---------------------------------------------------------------------
        input_card = QFrame()
        input_card.setStyleSheet("""
            QFrame {
                background-color: #181b22;
                border: 1px solid #282e38;
                border-radius: 8px;
            }
        """)
        input_layout = QVBoxLayout(input_card)
        input_layout.setContentsMargins(10, 8, 10, 8)
        input_layout.setSpacing(6)

        # Attachment preview bar (hidden by default)
        self.attach_preview_frame = QFrame()
        self.attach_preview_frame.setStyleSheet("background-color: #21262d; border-radius: 6px; padding: 4px;")
        ap_layout = QHBoxLayout(self.attach_preview_frame)
        ap_layout.setContentsMargins(6, 2, 6, 2)
        
        self.lbl_attach_name = QLabel("📎 image.png attached")
        self.lbl_attach_name.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: 600;")
        ap_layout.addWidget(self.lbl_attach_name)
        ap_layout.addStretch()

        btn_remove_attach = QPushButton("✕ Remove")
        btn_remove_attach.setFixedHeight(20)
        btn_remove_attach.setStyleSheet("background: transparent; color: #ef4444; border: none; font-size: 11px; font-weight: 700;")
        btn_remove_attach.clicked.connect(self._clear_attachment)
        ap_layout.addWidget(btn_remove_attach)

        self.attach_preview_frame.hide()
        input_layout.addWidget(self.attach_preview_frame)

        # Input Row: Text Input + Buttons
        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        self.txt_input = QTextEdit()
        self.txt_input.setPlaceholderText("Ask a question, enter instructions, or pick a Quick Action above... (Enter to send, Shift+Enter for newline)")
        self.txt_input.setFixedHeight(54)
        self.txt_input.setStyleSheet("""
            QTextEdit {
                background-color: #0d1117;
                color: #ffffff;
                font-size: 13px;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 6px 10px;
            }
            QTextEdit:focus {
                border: 1px solid #3b82f6;
            }
        """)
        self.txt_input.installEventFilter(self)
        input_row.addWidget(self.txt_input, stretch=1)

        # Buttons
        self.btn_tab_shot = QPushButton("📸 Tab Shot")
        self.btn_tab_shot.setProperty("class", "SecondaryButton")
        self.btn_tab_shot.setFixedHeight(48)
        self.btn_tab_shot.setToolTip("Capture live active browser tab screenshot [Ctrl+Shift+S]")
        self.btn_tab_shot.clicked.connect(self._capture_tab_screenshot)
        input_row.addWidget(self.btn_tab_shot)

        self.btn_dom_inspect = QPushButton("🔍 DOM")
        self.btn_dom_inspect.setProperty("class", "SecondaryButton")
        self.btn_dom_inspect.setFixedHeight(48)
        self.btn_dom_inspect.setToolTip("Flatten & inject active tab DOM elements for Copilot analysis")
        self.btn_dom_inspect.clicked.connect(self._inspect_live_dom)
        input_row.addWidget(self.btn_dom_inspect)

        self.btn_attach = QPushButton(" Attach")
        self.btn_attach.setIcon(self._get_icon("external-link"))
        self.btn_attach.setProperty("class", "SecondaryButton")
        self.btn_attach.setFixedHeight(48)
        self.btn_attach.setToolTip("Attach an image or screenshot for Multimodal AI Vision analysis.")
        self.btn_attach.clicked.connect(self._attach_image)
        input_row.addWidget(self.btn_attach)

        # Global Shortcut for Instant Tab Viewport Capture
        self.shortcut_tab_shot = QShortcut(QKeySequence("Ctrl+Shift+S"), self)
        self.shortcut_tab_shot.activated.connect(self._capture_tab_screenshot)

        self.btn_send = QPushButton(" Send")
        self.btn_send.setIcon(self._get_icon("zap"))
        self.btn_send.setProperty("class", "PrimaryButton")
        self.btn_send.setFixedSize(90, 48)
        self.btn_send.clicked.connect(self._send_message)
        input_row.addWidget(self.btn_send)

        self.btn_stop = QPushButton(" Stop")
        self.btn_stop.setIcon(self._get_icon("square"))
        self.btn_stop.setProperty("class", "DangerButton")
        self.btn_stop.setFixedSize(90, 48)
        self.btn_stop.hide()
        self.btn_stop.clicked.connect(self._stop_generation)
        input_row.addWidget(self.btn_stop)

        input_layout.addLayout(input_row)
        main_layout.addWidget(input_card)

    def _chip_style(self) -> str:
        return """
            QPushButton {
                background-color: #1e2430;
                color: #cbd5e1;
                border: 1px solid #334155;
                border-radius: 14px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #2d3748;
                color: #ffffff;
                border-color: #60a5fa;
            }
        """

    def _populate_model_options(self):
        cur_selected = self.combo_model.currentData() if hasattr(self, "combo_model") and self.combo_model is not None else None
        self.combo_model.blockSignals(True)
        self.combo_model.clear()

        # 1. Swarm Multi-Agent Reasoning Modes
        self.combo_model.addItem("🧠 Swarm Consensus & Council (Multi-Agent)", "swarm_consensus")
        self.combo_model.addItem("⚔️ Swarm Adversarial Council (Red vs. Blue Debate)", "swarm_adversarial")
        self.combo_model.addItem("🎯 Swarm Dynamic Specialist Router", "swarm_specialist")

        # 2. Hybrid Swarm Groups (Built-in + Custom User Hybrid Groups)
        try:
            from engine.ai_hybrid_groups_manager import AIHybridGroupsManager
            hg_mgr = AIHybridGroupsManager.get_instance()
            for g in hg_mgr.get_all_groups():
                gid = g.get("id", "")
                gname = g.get("name", "Hybrid Group")
                icon = g.get("icon", "⚔")
                is_custom = not g.get("is_builtin", False)
                tag = " [Custom Hybrid]" if is_custom else " [Swarm Apex]"
                self.combo_model.addItem(f"{icon} {gname}{tag}", gid)
        except Exception:
            self.combo_model.addItem("⫸ Auto-Full-Modus (7+1 Swarm Apex)", "swarm_auto_full")

        # 3. Gemini Cloud Models
        self.combo_model.addItem("★ Google Gemini Flash Lite (Cloud Ultra-Fast) [Empfohlen]", "gemini-flash-lite-latest")
        self.combo_model.addItem("★ Google Gemini 3.8 Flash (Cloud High-Capacity)", "gemini-3.8-flash")
        self.combo_model.addItem("⭍ Google Gemini 3.7 Flash (Cloud API)", "gemini-3.7-flash")
        self.combo_model.addItem("⭍ Google Gemini 3.6 Flash (Legacy Flash Endpoint)", "gemini-3.6-flash")
        self.combo_model.addItem("★ Google Gemini 1.5 Flash (Cloud API)", "gemini-1.5-flash")
        self.combo_model.addItem("⎔ Google Gemini 1.5 Pro (Deep Reasoning Cloud)", "gemini-1.5-pro")

        # 4. Local Specialized LLM, Vision, STT & ONNX Models
        self.combo_model.addItem("🧠 DeepSeek R1 (1.5B) - Chain-of-Thought Reasoning", "deepseek-r1:1.5b")
        self.combo_model.addItem("💻 Qwen 2.5 Coder (1.5B) - DOM & Automation Scripting", "qwen2.5-coder:1.5b")
        self.combo_model.addItem("👁 Qwen 2.5 VL (3B) - Next-Gen Multimodal Vision", "qwen2.5vl:3b")
        self.combo_model.addItem("⎔ Qwen 2.5 (7B) - Heavyweight Desktop Copilot", "qwen2.5:7b")
        self.combo_model.addItem("⚡ Nous Hermes 3 (3B) - Function-Calling & Agentic Tools", "hermes-3:3b")
        self.combo_model.addItem("⛯ IBM Granite 3 (2B) - DOM & Structured Playwright Extraktor", "granite3-dense:2b")
        self.combo_model.addItem("⭍ Qwen 2.5 (1.5B) - Local Text & Reasoning", "qwen2.5:1.5b")
        self.combo_model.addItem("⎔ Qwen 2.5 (3B) - Local Deep Reasoning", "qwen2.5:3b")
        self.combo_model.addItem("☘ Qwen 2.5 (0.5B) - Ultra Fast Micro-LLM", "qwen2.5:0.5b")
        self.combo_model.addItem("⚆ LLaVA (7B) - Spatial Vision & Grounding", "llava:7b")
        self.combo_model.addItem("⚆ Moondream 2 (1.4B) - Local Vision Model", "moondream:v2")
        self.combo_model.addItem("▨ SmolVLM (1.1GB) - Compact DOM & Vision OCR", "smolvlm")
        self.combo_model.addItem("🎯 Microsoft Florence-2 Base (0.23B) - Dense Vision Grounding", "florence-2-base")
        self.combo_model.addItem("📜 StepFun GOT-OCR 2.0 (0.5B) - Ultra-Dense Document OCR", "got-ocr2")
        self.combo_model.addItem("🎙 FunAudioLLM SenseVoice Small - Multi-Lingual Audio STT", "sensevoice-small")
        self.combo_model.addItem("🎙 Faster-Whisper Base - Local Audio STT Engine", "faster-whisper")
        self.combo_model.addItem("🖱 Biomechanical Mouse Trajectory CNN (ONNX)", "mouse-trajectory-onnx")
        self.combo_model.addItem("🛡 ONNX Stealth Sentinel - Tensor Anomaly Detector", "onnx-anomaly")

        if cur_selected:
            idx = self.combo_model.findData(cur_selected)
            if idx >= 0:
                self.combo_model.setCurrentIndex(idx)
        self.combo_model.blockSignals(False)

    def reload_profiles(self):
        """Populates profile dropdown with current active / stored profiles."""
        cur_data = self.combo_profile.currentData()
        self.combo_profile.clear()
        self.combo_profile.addItem("None (No Profile Context)", None)
        
        profiles = self.profile_manager.list_profiles()
        for p in profiles:
            p_name = p.get("name", "Profile")
            p_status = p.get("status", "Stopped")
            badge = "🟢" if p_status == "Running" else "⚪"
            self.combo_profile.addItem(f"{badge} {p_name}", p)

        if cur_data is not None:
            idx = self.combo_profile.findData(cur_data)
            if idx >= 0:
                self.combo_profile.setCurrentIndex(idx)

    def _add_welcome_message(self):
        welcome_text = (
            "**Welcome to the OXBROWSER AI Swarm & Copilot!** 🤖\n\n"
            "You can interact with individual local/cloud AI models or leverage our **Multi-Agent Swarm Intelligence** "
            "(Consensus Council, Specialist Routing, or 7+1 Synergy).\n\n"
            "• **Context-Aware:** Bind a browser profile from the dropdown to audit fingerprints, plan organic warmups, or diagnose anti-detection risks.\n"
            "• **Multimodal:** Click **Attach** to upload screenshots or UI captures for visual analysis with LLaVA or Gemini.\n"
            "• **Live Code:** Generate and copy complete Playwright / Camoufox stealth automation scripts instantly."
        )
        msg = ChatMessage(role="assistant", content=welcome_text, model="OXBROWSER AI Engine", timestamp=time.time())
        bubble = ChatBubble(msg)
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, bubble)

    def eventFilter(self, a0: Optional[QObject], a1: Optional[QEvent]) -> bool:
        if a0 == self.txt_input and a1 is not None and a1.type() == QEvent.Type.KeyPress:
            if isinstance(a1, QKeyEvent):
                if a1.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    if not (a1.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                        self._send_message()
                        return True
        return super().eventFilter(a0, a1)

    def _attach_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Attach Image / Screenshot", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp);;All Files (*)"
        )
        if file_path and os.path.exists(file_path):
            try:
                with open(file_path, "rb") as f:
                    raw = f.read()
                self._attached_image_b64 = base64.b64encode(raw).decode("ascii")
                self.lbl_attach_name.setText(f"📎 {os.path.basename(file_path)} ({len(raw)//1024} KB)")
                self.attach_preview_frame.show()
            except Exception as e:
                QMessageBox.warning(self, "Attachment Error", f"Failed to load image: {e}")

    def _clear_attachment(self):
        self._attached_image_b64 = None
        self.attach_preview_frame.hide()

    @qasync.asyncSlot()
    async def _capture_tab_screenshot(self):
        selected_prof = self.combo_profile.currentData()
        target_pid = selected_prof.get("id") if selected_prof else None
        
        self._on_status("Capturing active tab viewport...")
        bridge = BrowserCopilotBridge.get_instance()
        b64_str, name_or_err = await bridge.capture_viewport_base64(profile_id=target_pid)

        if b64_str:
            self._attached_image_b64 = b64_str
            self.lbl_attach_name.setText(f"📸 Live Tab Viewport [{name_or_err}]")
            self.attach_preview_frame.show()
            self._on_status("Viewport attached")
        else:
            self._on_status(f"Error: {name_or_err}")
            QMessageBox.information(self, "Tab Screenshot", f"Could not capture viewport: {name_or_err}\nMake sure a browser profile is actively running.")

    @qasync.asyncSlot()
    async def _inspect_live_dom(self):
        selected_prof = self.combo_profile.currentData()
        target_pid = selected_prof.get("id") if selected_prof else None

        self._on_status("Flattening active tab DOM...")
        bridge = BrowserCopilotBridge.get_instance()
        dom_data = await bridge.inspect_live_dom(profile_id=target_pid)

        if "error" in dom_data:
            self._on_status("DOM error")
            QMessageBox.information(self, "DOM Inspect", f"DOM Inspect note: {dom_data['error']}\nMake sure a browser profile is running.")
            return

        elems = dom_data.get("interactive_elements", [])
        snippet_lines = [f"[LIVE DOM INSPECTION: {dom_data.get('title', 'Page')} ({dom_data.get('url', '')})]"]
        for el in elems[:15]:
            snippet_lines.append(f"- <{el['tag']}> id='{el.get('id')}' text='{el.get('text')}' selector='{el.get('selector')}' pos=({el['rect']['x']},{el['rect']['y']})")
        
        dom_text = "\n".join(snippet_lines)
        curr_text = self.txt_input.toPlainText()
        if curr_text:
            self.txt_input.setPlainText(f"{curr_text}\n\n{dom_text}")
        else:
            self.txt_input.setPlainText(f"Analyze this live page and tell me how to interact with it:\n\n{dom_text}")
        self._on_status(f"Injected {len(elems)} DOM elements")

    def _on_persona_changed(self):
        data = self.combo_persona.currentData()
        if data == "custom":
            dialog = QDialog(self)
            dialog.setWindowTitle("Custom System Persona")
            dialog.resize(500, 300)
            d_layout = QVBoxLayout(dialog)
            
            lbl = QLabel("Enter custom system prompt for the AI:")
            lbl.setStyleSheet("font-weight: 700;")
            d_layout.addWidget(lbl)

            txt = QTextEdit()
            txt.setPlainText(self.chat_engine.get_effective_system_prompt())
            d_layout.addWidget(txt)

            btn_box = QHBoxLayout()
            btn_save = QPushButton("Save Persona")
            btn_save.clicked.connect(lambda: (self.chat_engine.set_system_persona("custom", txt.toPlainText()), dialog.accept()))
            btn_box.addWidget(btn_save)
            d_layout.addLayout(btn_box)
            dialog.exec()
        else:
            self.chat_engine.set_system_persona(str(data))

    def _on_language_changed(self, index: int):
        lang_code = self.combo_language.currentData()
        if lang_code:
            self.chat_engine.set_preferred_language(str(lang_code))

    def _on_warmup_triggered_from_card(self, campaign_data: Dict[str, Any]):
        target_pid = campaign_data.get("profile_id")
        target_pname = campaign_data.get("profile_name")
        selected_prof = self.combo_profile.currentData()

        # If campaign data explicitly specifies a profile_id or name, auto-resolve it
        if target_pid:
            p = self.profile_manager.get_profile(target_pid)
            if p:
                selected_prof = p
        elif target_pname and not selected_prof:
            for p in self.profile_manager.list_profiles():
                if p.get("name", "").lower() == str(target_pname).lower():
                    selected_prof = p
                    break

        if not selected_prof:
            # Fallback to first profile if available
            all_profs = self.profile_manager.list_profiles()
            if all_profs:
                selected_prof = all_profs[0]

        if not selected_prof:
            QMessageBox.warning(self, "Kein Profil gefunden", "Es wurde kein gültiges Profil für diese Kampagne gefunden. Bitte erstelle zuerst ein Profil.")
            return

        from engine.ai_agent_actions import AIAgentActionEngine
        engine = AIAgentActionEngine.get_instance()
        p_id = selected_prof.get("id")
        p_name = selected_prof.get("name", "Profil")
        c_title = campaign_data.get("campaign_name") or campaign_data.get("name") or "Warmup Trajectory"
        success, msg = engine.start_warmup_campaign(campaign_data, [p_id])
        if success:
            QMessageBox.information(
                self,
                "Warmup Gestartet",
                f"🚀 Die Warmup-Kampagne <b>'{c_title}'</b> wurde erfolgreich für Profil <b>'{p_name}'</b> (ID: {p_id[:8]}...) gestartet!"
            )
        else:
            QMessageBox.warning(self, "Warmup Fehler", msg)

    def _quick_action(self, action_type: str):
        selected_prof = self.combo_profile.currentData()
        p_name = selected_prof.get("name", "Active Profile") if selected_prof else "Active Profile"

        if action_type == "create_profile":
            self.txt_input.setPlainText("Erstelle mir ein einzigartiges, 100% harmonisiertes Camoufox Browser-Profil (Name: 'Stealth_Agent_01', OS: Windows/Linux) mit unentdeckbaren Hardware- und WebGL-Werten.")
        elif action_type == "create_warmup":
            self.txt_input.setPlainText(f"Erstelle eine maßgeschneiderte 6-stufige Warmup-Kampagne (Thema: E-Commerce & Tech) für '{p_name}' mit realistischen URLs, Suchbegriffen und Dwell-Zeiten.")
        elif action_type == "list_campaigns":
            self.txt_input.setPlainText("Zeige mir alle verfügbaren und gespeicherten Warmup-Kampagnen mit ihren Spezifikationen an.")
        elif action_type == "audit":
            if not selected_prof:
                self.txt_input.setPlainText("Audit current browser anti-detect security, Canvas/WebGL noise, and TLS fingerprint evasion.")
            else:
                self.txt_input.setPlainText(f"Audit the stealth configuration of profile '{p_name}'. Are there any tensor anomalies, WebRTC leaks, or fingerprint inconsistencies?")
        elif action_type == "pentest":
            if not selected_prof:
                self.txt_input.setPlainText("Führe ein strukturiertes Web Application Security & OWASP Pentesting Audit durch: Analysiere Authentifizierungs-Flaws, IDOR, SSRF, XSS, CSRF, CSP & Security Headers und erstelle PoC Exploit-Vorlagen.")
            else:
                self.txt_input.setPlainText(f"Führe ein tiefgehendes Penetration Testing & Vulnerability Assessment für die Zielumgebung von Profil '{p_name}' durch. Prüfe Auth-Tokens, DOM-Sicherheit, Cookie-Flags und WebSocket-Endpunkte.")
        elif action_type == "evasion":
            if not selected_prof:
                self.txt_input.setPlainText("Analysiere WAF- & Anti-Bot-Abwehrmechanismen (Cloudflare Turnstile, DataDome, Kasada, Akamai BMP). Erstelle eine lückenlose Evasion-Strategie für TLS JA3/JA4, C++ Canvas/Audio Jitter und Minimum-Jerk Entropie.")
            else:
                self.txt_input.setPlainText(f"Analysiere Bot-Mitigation & WAF-Regeln für Profil '{p_name}'. Wie umgehen wir Cloudflare / DataDome Challenges mit C++ Native Jitter und humanisiertem Dwell-Time-Verhalten?")
        elif action_type == "forensics":
            if not selected_prof:
                self.txt_input.setPlainText("Führe eine Low-Level Network & Browser Forensic-Analyse durch: Untersuche TLS 1.3 Handshake, HTTP/2 Frames, WebRTC ICE STUN Candidates, C++ FontConfig Sandbox und unmaskierte GPU Tensor-Signaturen.")
            else:
                self.txt_input.setPlainText(f"Führe eine Low-Level Forensik-Analyse für Profil '{p_name}' durch: Prüfe Host-Font-Leckagen, WebRTC mDNS Obfuscation, AudioContext DSP FFT-Signaturen und DNS-over-HTTPS.")
        elif action_type == "playwright":
            self.txt_input.setPlainText("Write a stealth-hardened Camoufox / Playwright Python script that connects to an active OXBROWSER profile and navigates humanely with minimum-jerk Bezier curves and anti-detection safeguards.")

        self._send_message()

    @qasync.asyncSlot()
    async def _send_message(self):
        text = self.txt_input.toPlainText().strip()
        if not text and not self._attached_image_b64:
            return

        if self._is_streaming:
            return

        self._is_streaming = True
        self.btn_send.hide()
        self.btn_stop.show()
        self.status_badge.set_status("Checking")
        self.txt_input.clear()

        # Render user bubble
        img_b64 = self._attached_image_b64
        self._clear_attachment()

        user_msg = ChatMessage(
            role="user",
            content=text,
            image_b64=img_b64,
            timestamp=time.time()
        )
        user_bubble = ChatBubble(user_msg)
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, user_bubble)

        # Prepare streaming assistant bubble
        target_model = str(self.combo_model.currentData())
        selected_prof = self.combo_profile.currentData()

        assistant_msg = ChatMessage(
            role="assistant",
            content="",
            model=target_model,
            timestamp=time.time()
        )
        self._current_assistant_bubble = ChatBubble(
            assistant_msg,
            is_streaming=True,
            on_action_callback=lambda pid: self.reload_profiles(),
            on_warmup_callback=self._on_warmup_triggered_from_card
        )
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, self._current_assistant_bubble)
        self._scroll_to_bottom()

        # Execute async chat streaming
        try:
            await self.chat_engine.stream_chat(
                prompt=text,
                model_or_swarm=target_model,
                image_b64=img_b64,
                profile_data=selected_prof,
                on_chunk=lambda c: self.signals.chunk_received.emit(c),
                on_swarm_step=lambda s: self.signals.swarm_step_received.emit(s),
                on_status=lambda st: self.signals.status_updated.emit(st)
            )
        except Exception as e:
            logger.error(f"[AIChatView] Chat streaming error: {e}")
            if self._current_assistant_bubble:
                self._current_assistant_bubble.append_chunk(f"\n⚠️ Error: {e}")
        finally:
            self.signals.generation_finished.emit(None)

    def _on_chunk(self, chunk: str):
        if self._current_assistant_bubble:
            self._current_assistant_bubble.append_chunk(chunk)
            self._scroll_to_bottom()

    def _on_swarm_step(self, step: SwarmAgentResponse):
        logger.info(f"[AIChatView] Swarm Sub-agent: {step.role_name} ({step.latency_ms:.0f}ms)")

    def _on_status(self, status_text: str):
        self.status_badge.setText(f"◌ {status_text[:28]}...")

    def _on_finished(self, _):
        self._is_streaming = False
        if self._current_assistant_bubble:
            bubble = self._current_assistant_bubble
            self._current_assistant_bubble = None
            try:
                bubble.finalize_render()
            except (RuntimeError, Exception) as e:
                logger.debug(f"[AIChatView] finalize_render ignored exception: {e}")
        self.btn_stop.hide()
        self.btn_send.show()
        self.status_badge.set_status("Running")
        self.status_badge.setText("● READY")
        self._scroll_to_bottom()

    def _stop_generation(self):
        self.chat_engine.abort_generation()
        self.status_badge.set_status("Error")
        self.status_badge.setText("■ ABORTED")

    def _scroll_to_bottom(self):
        vsb = self.scroll_area.verticalScrollBar()
        if vsb is not None:
            QTimer.singleShot(20, lambda: vsb.setValue(vsb.maximum()))

    def _clear_chat(self):
        reply = QMessageBox.question(
            self, "Clear Chat", "Are you sure you want to clear the entire conversation history?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            if self._is_streaming:
                self.chat_engine.abort_generation()
                self._is_streaming = False
            self._current_assistant_bubble = None
            self.chat_engine.clear_history()
            while self.chat_layout.count() > 1:
                item = self.chat_layout.takeAt(0)
                if item is not None:
                    w = item.widget()
                    if w is not None:
                        w.deleteLater()
            self._add_welcome_message()

    def _copy_all_chat(self):
        md_text = self.chat_engine.export_to_markdown()
        cb = QApplication.clipboard()
        if cb:
            cb.setText(md_text)
            self.btn_copy_all.setText(" ✓ Copied!")
            QTimer.singleShot(1500, lambda: self.btn_copy_all.setText(" Copy All"))

    def _export_chat(self):
        md_text = self.chat_engine.export_to_markdown()
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Conversation to Markdown",
            f"OXBROWSER_AI_Chat_{time.strftime('%Y%m%d_%H%M%S')}.md",
            "Markdown (*.md);;JSON (*.json);;All Files (*)"
        )
        if file_path:
            try:
                if file_path.endswith(".json"):
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(self.chat_engine.export_to_json())
                else:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(md_text)
                QMessageBox.information(self, "Export Successful", f"Chat exported successfully to:\n{file_path}")
            except Exception as e:
                QMessageBox.warning(self, "Export Error", f"Failed to export chat: {e}")
