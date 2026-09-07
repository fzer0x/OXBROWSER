import os
import subprocess
from PyQt6.QtWidgets import QLabel, QFrame, QVBoxLayout, QHBoxLayout, QPushButton, QProgressBar
from PyQt6.QtCore import Qt

class StatusBadge(QLabel):
    """Refined Professional Status Badge."""

    def __init__(self, status: str = "Stopped", parent=None):
        super().__init__(parent)
        self.set_status(status)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_status(self, status: str):
        status_clean = (status or "STOPPED").upper()
        status_lower = status.lower() if status else "stopped"
        
        if status_lower == "running":
            bg = "rgba(16, 185, 129, 0.15)"
            fg = "#10b981"
            border = "rgba(16, 185, 129, 0.3)"
            icon = "● "
        elif status_lower == "checking":
            bg = "rgba(245, 158, 11, 0.15)"
            fg = "#f59e0b"
            border = "rgba(245, 158, 11, 0.3)"
            icon = "◌ "
        elif status_lower == "error":
            bg = "rgba(239, 68, 68, 0.15)"
            fg = "#ef4444"
            border = "rgba(239, 68, 68, 0.3)"
            icon = "▲ "
        else:
            bg = "rgba(107, 114, 128, 0.15)"
            fg = "#9ca3af"
            border = "rgba(107, 114, 128, 0.3)"
            icon = "○ "

        self.setText(f"{icon}{status_clean}")
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {bg};
                color: {fg};
                border: 1px solid {border};
                font-weight: 600;
                font-size: 11px;
                border-radius: 4px;
                padding: 3px 8px;
                letter-spacing: 0.3px;
            }}
        """)

class MetricCard(QFrame):
    """Solid Professional Metric Card."""

    def __init__(self, title: str, value: str = "0", parent=None):
        super().__init__(parent)
        self.setObjectName("MetricCard")
        self.setProperty("class", "MetricCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("MetricTitle")
        self.title_label.setProperty("class", "MetricTitle")
        self.title_label.setStyleSheet("color: #888888; font-size: 11px; font-weight: 600; letter-spacing: 0.4px;")

        self.value_label = QLabel(value)
        self.value_label.setObjectName("MetricValue")
        self.value_label.setProperty("class", "MetricValue")
        self.value_label.setStyleSheet("color: #ffffff; font-size: 22px; font-weight: 700; letter-spacing: -0.2px;")

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)

    def set_value(self, value: str):
        self.value_label.setText(value)

class TagBadge(QLabel):
    """Subtle flat tag badge widget for profiles."""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setStyleSheet("""
            QLabel {
                background-color: #232325;
                color: #d1d5db;
                border: 1px solid #333333;
                font-size: 11px;
                font-weight: 500;
                padding: 2px 7px;
                border-radius: 4px;
            }
        """)


class SystemResourceWidget(QFrame):
    """Clean, flat real-time telemetry card for CPU, GPU, and RAM load."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SystemResourceCard")
        self.setProperty("class", "MetricCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        # Header Title Row
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        self.lbl_title = QLabel("SYSTEM TELEMETRY")
        self.lbl_title.setStyleSheet("font-size: 11px; font-weight: 600; color: #888888; letter-spacing: 0.4px;")
        
        self.lbl_live_indicator = QLabel("● LIVE")
        self.lbl_live_indicator.setStyleSheet("""
            background-color: rgba(16, 185, 129, 0.15);
            color: #10b981;
            border: 1px solid rgba(16, 185, 129, 0.3);
            border-radius: 4px;
            padding: 1px 6px;
            font-size: 9px;
            font-weight: 700;
            letter-spacing: 0.3px;
        """)
        
        self.btn_free_vram = QPushButton("⎚ Free VRAM")
        self.btn_free_vram.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_free_vram.setToolTip("Unload cached AI models from GPU VRAM immediately.")
        self.btn_free_vram.setStyleSheet("""
            QPushButton {
                background-color: #232325;
                color: #e5e5e5;
                border: 1px solid #333333;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 10px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: rgba(239, 68, 68, 0.15);
                color: #ef4444;
                border-color: rgba(239, 68, 68, 0.4);
            }
        """)
        self.btn_free_vram.clicked.connect(self._on_free_vram_clicked)

        header_layout.addWidget(self.lbl_title)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_free_vram)
        header_layout.addSpacing(6)
        header_layout.addWidget(self.lbl_live_indicator)
        layout.addLayout(header_layout)

        # Grid / Row Layout for CPU, RAM, GPU
        stats_layout = QHBoxLayout()
        stats_layout.setContentsMargins(0, 2, 0, 0)
        stats_layout.setSpacing(14)

        # 1. CPU Section
        self.cpu_layout, self.lbl_cpu_val, self.bar_cpu = self._create_metric_column("CPU", "0%")
        stats_layout.addLayout(self.cpu_layout)

        # 2. RAM Section
        self.ram_layout, self.lbl_ram_val, self.bar_ram = self._create_metric_column("RAM", "0%")
        stats_layout.addLayout(self.ram_layout)

        # 3. GPU Section
        self.gpu_layout, self.lbl_gpu_val, self.bar_gpu = self._create_metric_column("GPU", "0%")
        stats_layout.addLayout(self.gpu_layout)

        layout.addLayout(stats_layout)

        self.gpu_compute_ema = 0.0

        # Background update timer (1000ms for smooth live updates)
        from PyQt6.QtCore import QTimer
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.update_telemetry)
        self.timer.start()

        self.update_telemetry()

    def _on_free_vram_clicked(self):
        import asyncio
        from engine.ai_model_manager import AIModelManager
        self.btn_free_vram.setText("⧖ Freeing...")
        self.btn_free_vram.setEnabled(False)

        async def _do_unload():
            try:
                ai_mgr = AIModelManager.get_instance()
                await ai_mgr.unload_all_models_from_vram()
                await asyncio.sleep(0.5)
                self.update_telemetry()
                self.btn_free_vram.setText(" VRAM Freed")
                await asyncio.sleep(1.5)
            except Exception:
                pass
            finally:
                self.btn_free_vram.setText("⎚ Free VRAM")
                self.btn_free_vram.setEnabled(True)

        asyncio.create_task(_do_unload())

    def _create_metric_column(self, label_text: str, default_val: str):
        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(3)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        lbl_tag = QLabel(label_text)
        lbl_tag.setStyleSheet("font-size: 11px; font-weight: 600; color: #888888;")
        
        lbl_val = QLabel(default_val)
        lbl_val.setStyleSheet("font-size: 11px; font-weight: 600; color: #e5e5e5;")
        
        top_row.addWidget(lbl_tag)
        top_row.addStretch()
        top_row.addWidget(lbl_val)
        col.addLayout(top_row)

        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(0)
        bar.setFixedHeight(4)
        bar.setTextVisible(False)
        bar.setStyleSheet(self._get_bar_style("#2563eb"))
        col.addWidget(bar)

        return col, lbl_val, bar

    def _get_bar_style(self, color_hex: str) -> str:
        return f"""
            QProgressBar {{
                background-color: #232325;
                border: 1px solid #2d2d2f;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background-color: {color_hex};
                border-radius: 1px;
            }}
        """

    def _pick_color(self, percent: float) -> str:
        if percent >= 85.0:
            return "#ef4444"  # Red
        elif percent >= 65.0:
            return "#f59e0b"  # Amber
        elif percent >= 40.0:
            return "#3b82f6"  # Blue
        return "#10b981"      # Green

    def update_telemetry(self):
        import psutil
        import subprocess

        # 1. CPU Usage
        try:
            cpu_pct = psutil.cpu_percent(interval=None)
        except Exception:
            cpu_pct = 0.0
        
        cpu_color = self._pick_color(cpu_pct)
        self.lbl_cpu_val.setText(f"{cpu_pct:.0f}%")
        self.lbl_cpu_val.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {cpu_color};")
        self.bar_cpu.setValue(int(cpu_pct))
        self.bar_cpu.setStyleSheet(self._get_bar_style(cpu_color))

        # 2. RAM Usage
        try:
            mem = psutil.virtual_memory()
            ram_pct = mem.percent
            used_gb = mem.used / (1024 ** 3)
            ram_text = f"{ram_pct:.0f}% ({used_gb:.1f}G)"
        except Exception:
            ram_pct = 0.0
            ram_text = "0%"

        ram_color = self._pick_color(ram_pct)
        self.lbl_ram_val.setText(ram_text)
        self.lbl_ram_val.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {ram_color};")
        self.bar_ram.setValue(int(ram_pct))
        self.bar_ram.setStyleSheet(self._get_bar_style(ram_color))

        # 3. Smart GPU Usage (Persistent VRAM % + Peak-Hold AI Compute Activity)
        gpu_display_pct = 0.0
        gpu_text = "0%"
        tooltip_info = "GPU: Detecting..."
        try:
            from engine.platform_helper import PlatformHelper
            flags = PlatformHelper.get_subprocess_creation_flags()
            nvsmi_bin = "nvidia-smi"
            if PlatformHelper.is_windows():
                win_nvsmi = r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe"
                if os.path.isfile(win_nvsmi):
                    nvsmi_bin = win_nvsmi

            res = subprocess.run(
                [nvsmi_bin, '--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,name', '--format=csv,noheader,nounits'],
                capture_output=True, text=True, timeout=0.6, creationflags=flags
            )
            if res.returncode == 0 and res.stdout.strip():
                parts = [p.strip() for p in res.stdout.strip().split(',')]
                if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit() and parts[2].isdigit():
                    raw_compute = float(parts[0])
                    vram_used = float(parts[1])
                    vram_total = float(parts[2])
                    vram_pct = (vram_used / vram_total * 100.0) if vram_total > 0 else 0.0
                    temp = parts[3] if len(parts) > 3 else "N/A"
                    gpu_name = parts[4] if len(parts) > 4 else "NVIDIA GPU"

                    # Smooth Exponential Moving Average & Peak Decay for short AI compute spikes
                    if raw_compute > self.gpu_compute_ema:
                        self.gpu_compute_ema = raw_compute
                    else:
                        self.gpu_compute_ema = max(0.0, self.gpu_compute_ema * 0.72)

                    # Primary bar displays allocated VRAM percentage
                    gpu_display_pct = vram_pct
                    vram_gb = vram_used / 1024.0

                    if self.gpu_compute_ema >= 8.0:
                        gpu_text = f"{vram_pct:.0f}% ({vram_gb:.1f}G) ⭍{int(self.gpu_compute_ema)}%"
                    else:
                        gpu_text = f"{vram_pct:.0f}% ({vram_gb:.1f}G)"

                    tooltip_info = f"{gpu_name}\nVRAM: {vram_used:.0f}MB / {vram_total:.0f}MB ({vram_pct:.1f}%)\nAI Compute Load: {raw_compute:.0f}%\nTemp: {temp}°C"
        except Exception:
            pass

        if not gpu_text or gpu_text == "0%":
            # Fallback: check /sys/class/drm for Linux or config.detect_native_webgl_info() for Windows
            try:
                import glob
                busy_files = glob.glob('/sys/class/drm/card*/device/gpu_busy_percent')
                if busy_files:
                    with open(busy_files[0], 'r') as f:
                        gpu_display_pct = float(f.read().strip())
                        gpu_text = f"{gpu_display_pct:.0f}%"
                else:
                    import config
                    hw = config.detect_native_webgl_info()
                    if hw and hw.get("renderer"):
                        gpu_text = "Active"
                        tooltip_info = f"Host GPU: {hw.get('renderer')}\nVendor: {hw.get('vendor')}"
                    else:
                        gpu_text = "Active"
            except Exception:
                gpu_text = "N/A"

        gpu_color = self._pick_color(gpu_display_pct) if isinstance(gpu_display_pct, (int, float)) else "#2563eb"
        self.lbl_gpu_val.setText(gpu_text)
        self.lbl_gpu_val.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {gpu_color};")
        self.lbl_gpu_val.setToolTip(tooltip_info)
        self.bar_gpu.setValue(int(gpu_display_pct))
        self.bar_gpu.setStyleSheet(self._get_bar_style(gpu_color))
        self.bar_gpu.setToolTip(tooltip_info)


