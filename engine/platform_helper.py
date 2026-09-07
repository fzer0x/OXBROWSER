"""
platform_helper.py - Cross-Platform OS Detection & Environment Abstraction Layer for SoxBot.

Provides autonomous host OS detection (Windows, Linux, macOS) and uniform interfaces for:
- Host OS identification & normalization
- Native timezone discovery (Windows Registry, /etc/timezone, /etc/localtime)
- Binary executable resolution (.exe on Windows vs ELF on Linux/macOS)
- Cross-platform file/folder opener (os.startfile, QDesktopServices, xdg-open, open)
- Windows subprocess creationflags (CREATE_NO_WINDOW for background workers)
- Environment variable harmonization (PATH, LD_LIBRARY_PATH, tempdir)
"""

import os
import sys
import shutil
import platform
import subprocess
import webbrowser
import logging
from typing import Optional, List

logger = logging.getLogger("PlatformHelper")

# Subprocess creation flag for Windows to prevent console flashing on background CLI tools
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


class PlatformHelper:
    """Central cross-platform helper with autonomous host OS detection."""

    @staticmethod
    def safe_which(cmd: str) -> Optional[str]:
        """Exception-safe wrapper around shutil.which."""
        try:
            return shutil.which(cmd)
        except Exception:
            return None

    @staticmethod
    def get_current_platform() -> str:
        """
        Returns normalized host OS identifier:
        - 'windows'
        - 'linux'
        - 'mac'
        """
        sys_name = sys.platform.lower()
        if sys_name.startswith("win"):
            return "windows"
        elif sys_name.startswith("darwin"):
            return "mac"
        return "linux"

    @classmethod
    def is_windows(cls) -> bool:
        return cls.get_current_platform() == "windows"

    @classmethod
    def is_linux(cls) -> bool:
        return cls.get_current_platform() == "linux"

    @classmethod
    def is_mac(cls) -> bool:
        return cls.get_current_platform() == "mac"

    @classmethod
    def get_platform_display_name(cls) -> str:
        """Returns human-friendly OS name with version details."""
        system = platform.system()
        release = platform.release()
        if cls.is_windows():
            return f"Windows {release}"
        elif cls.is_mac():
            return f"macOS {release} ({platform.machine()})"
        return f"Linux ({platform.release()})"

    @classmethod
    def get_subprocess_creation_flags(cls) -> int:
        """Returns CREATE_NO_WINDOW on Windows, 0 on other OSes."""
        if cls.is_windows():
            return getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        return 0

    @classmethod
    def get_system_timezone(cls) -> str:
        """
        Autonomously detects host operating system timezone:
        - On Windows: Queries Windows Registry or zoneinfo / time.tzname
        - On Linux: Reads /etc/timezone or /etc/localtime symlink
        - On macOS: Reads /etc/localtime or systemsetup
        Falls back to 'Europe/Berlin' if unresolved.
        """
        # 1. Windows Detection via winreg (dynamic import for cross-platform static analysis)
        if cls.is_windows():
            try:
                import importlib
                winreg_mod = importlib.import_module("winreg")
                key_path = r"SYSTEM\CurrentControlSet\Control\TimeZoneInformation"
                hklm = getattr(winreg_mod, "HKEY_LOCAL_MACHINE", None)
                open_key = getattr(winreg_mod, "OpenKey", None)
                query_val = getattr(winreg_mod, "QueryValueEx", None)
                if hklm is not None and open_key is not None and query_val is not None:
                    with open_key(hklm, key_path) as key:
                        try:
                            tz_name, _ = query_val(key, "TimeZoneKeyName")
                            if tz_name and str(tz_name).strip():
                                # Map standard Windows time zone names to IANA if possible
                                return cls._map_windows_tz_to_iana(str(tz_name).strip())
                        except Exception:
                            pass
            except Exception:
                pass

        # 2. Linux / Unix Detection
        try:
            if os.path.exists("/etc/timezone"):
                with open("/etc/timezone", "r", encoding="utf-8", errors="ignore") as f:
                    tz = f.read().strip()
                    if tz:
                        return tz
            if os.path.islink("/etc/localtime"):
                target = os.readlink("/etc/localtime")
                parts = target.split("/zoneinfo/")
                if len(parts) > 1 and parts[1].strip():
                    return parts[1].strip()
        except Exception:
            pass

        # 3. Standard library zoneinfo or tzlocal fallback
        try:
            import time
            if hasattr(time, "tzname") and time.tzname:
                # E.g. ('CET', 'CEST') or ('W. Europe Standard Time')
                first_tz = time.tzname[0]
                if "/" in first_tz:
                    return first_tz
        except Exception:
            pass

        # 4. Universal Default Fallback
        return "Europe/Berlin"

    @staticmethod
    def _map_windows_tz_to_iana(win_tz: str) -> str:
        """Maps common Windows TimeZoneKeyName to IANA timezone identifier."""
        mapping = {
            "W. Europe Standard Time": "Europe/Berlin",
            "Central Europe Standard Time": "Europe/Berlin",
            "Romance Standard Time": "Europe/Paris",
            "GMT Standard Time": "Europe/London",
            "UTC": "UTC",
            "Eastern Standard Time": "America/New_York",
            "Central Standard Time": "America/Chicago",
            "Mountain Standard Time": "America/Denver",
            "Pacific Standard Time": "America/Los_Angeles",
            "Tokyo Standard Time": "Asia/Tokyo",
            "China Standard Time": "Asia/Shanghai",
            "Singapore Standard Time": "Asia/Singapore",
            "E. Europe Standard Time": "Europe/Bucharest",
            "Russian Standard Time": "Europe/Moscow",
            "India Standard Time": "Asia/Kolkata",
            "AUS Eastern Standard Time": "Australia/Sydney",
            "Hawaiian Standard Time": "Pacific/Honolulu"
        }
        return mapping.get(win_tz, win_tz if "/" in win_tz else "Europe/Berlin")

    @classmethod
    def open_folder_or_file(cls, path: str) -> bool:
        """
        Opens a folder or file in the native system file explorer / default app.
        Works seamlessly across Windows Explorer, macOS Finder, and Linux XDG.
        """
        if not path:
            return False
        
        path = os.path.abspath(path)
        os.makedirs(os.path.dirname(path) if os.path.isfile(path) else path, exist_ok=True)

        # 1. Try PyQt6 QDesktopServices if GUI is running
        try:
            from PyQt6.QtGui import QDesktopServices
            from PyQt6.QtCore import QUrl
            if QDesktopServices.openUrl(QUrl.fromLocalFile(path)):
                return True
        except Exception:
            pass

        # 2. Native OS Dispatch
        try:
            if cls.is_windows():
                if hasattr(os, "startfile"):
                    os.startfile(path)
                    return True
                subprocess.Popen(["explorer", path], creationflags=cls.get_subprocess_creation_flags())
                return True
            elif cls.is_mac():
                subprocess.Popen(["open", path])
                return True
            else:
                subprocess.Popen(["xdg-open", path])
                return True
        except Exception as e:
            logger.warning(f"Failed to open path '{path}': {e}")
            return False

    @classmethod
    def open_url(cls, url: str) -> bool:
        """Opens a URL in the user's default system browser."""
        if not url:
            return False

        try:
            from PyQt6.QtGui import QDesktopServices
            from PyQt6.QtCore import QUrl
            if QDesktopServices.openUrl(QUrl(url)):
                return True
        except Exception:
            pass

        try:
            if webbrowser.open(url, new=2):
                return True
        except Exception:
            pass

        try:
            if cls.is_windows():
                if hasattr(os, "startfile"):
                    os.startfile(url)
                    return True
                subprocess.Popen(["cmd.exe", "/c", "start", "", url], creationflags=cls.get_subprocess_creation_flags())
                return True
            elif cls.is_mac():
                subprocess.Popen(["open", url])
                return True
            else:
                subprocess.Popen(["xdg-open", url])
                return True
        except Exception as e:
            logger.warning(f"Failed to open URL '{url}': {e}")
            return False

    @classmethod
    def find_camoufox_binary(cls, base_dir: str) -> Optional[str]:
        """
        Finds Camoufox executable across Windows, Linux, and macOS:
        - Checks official pkgman cache
        - Checks local project camoufox directory (.exe on Windows, ELF on Linux)
        - Checks system PATH / user AppData
        """
        # 1. Official pkgman cache
        try:
            from camoufox import pkgman
            p = pkgman.launch_path()
            if p and os.path.isfile(p):
                if cls.is_windows() or os.access(p, os.X_OK):
                    return p
        except Exception:
            pass

        # 2. Local workspace directory
        candidate_names = ["camoufox.exe", "firefox.exe"] if cls.is_windows() else ["camoufox", "camoufox-bin", "firefox"]
        subdirs = [
            os.path.join(base_dir, "camoufox", "camoufox"),
            os.path.join(base_dir, "camoufox"),
            os.path.join(base_dir, "camoufox-bin"),
        ]

        for sdir in subdirs:
            for cname in candidate_names:
                full_p = os.path.join(sdir, cname)
                if os.path.isfile(full_p):
                    if cls.is_windows() or os.access(full_p, os.X_OK):
                        return full_p

        # 3. Windows AppData / System PATH search
        if cls.is_windows():
            local_appdata = os.environ.get("LOCALAPPDATA", "")
            if local_appdata:
                win_paths = [
                    os.path.join(local_appdata, "camoufox", "camoufox.exe"),
                    os.path.join(local_appdata, "camoufox", "camoufox", "camoufox.exe"),
                    os.path.join(os.environ.get("PROGRAMFILES", "C:\\Program Files"), "Mozilla Firefox", "firefox.exe"),
                    os.path.join(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)"), "Mozilla Firefox", "firefox.exe"),
                ]
                for p in win_paths:
                    if os.path.isfile(p):
                        return p

        # 4. System PATH
        for cname in candidate_names:
            sys_found = cls.safe_which(cname)
            if sys_found:
                return sys_found

        return None

    @classmethod
    def find_chromium_binary(cls, base_dir: str) -> Optional[str]:
        """
        Finds Chrome / Chromium / Edge / Brave binary across Windows, Linux, and macOS.
        """
        if cls.is_windows():
            # Check local chrome-win64 if bundled
            local_chrome = os.path.join(base_dir, "chrome-win64", "chrome.exe")
            if os.path.isfile(local_chrome):
                return local_chrome

            prog_files = os.environ.get("PROGRAMFILES", "C:\\Program Files")
            prog_files_x86 = os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")
            local_appdata = os.environ.get("LOCALAPPDATA", "")

            candidates = [
                os.path.join(prog_files, "Google", "Chrome", "Application", "chrome.exe"),
                os.path.join(prog_files_x86, "Google", "Chrome", "Application", "chrome.exe"),
                os.path.join(local_appdata, "Google", "Chrome", "Application", "chrome.exe"),
                os.path.join(prog_files, "Microsoft", "Edge", "Application", "msedge.exe"),
                os.path.join(prog_files_x86, "Microsoft", "Edge", "Application", "msedge.exe"),
                os.path.join(prog_files, "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
            ]
            for p in candidates:
                if os.path.isfile(p):
                    return p

            for bname in ["chrome.exe", "chrome", "msedge.exe", "msedge", "brave.exe", "brave"]:
                found = cls.safe_which(bname)
                if found:
                    return found
        else:
            local_chrome = os.path.join(base_dir, "chrome-linux64", "chrome")
            if os.path.isfile(local_chrome) and os.access(local_chrome, os.X_OK):
                return local_chrome

            for bname in ["google-chrome", "chromium", "chromium-browser", "brave-browser", "chrome"]:
                found = cls.safe_which(bname)
                if found:
                    return found

        return None

    @classmethod
    def find_stockfish_binary(cls, base_dir: str, custom_path: Optional[str] = None) -> Optional[str]:
        """Finds Stockfish chess engine binary on Windows and Linux/macOS."""
        if custom_path and os.path.isfile(custom_path):
            if cls.is_windows() or os.access(custom_path, os.X_OK):
                return custom_path

        exe_names = ["stockfish.exe", "stockfish-windows-x86-64-avx2.exe", "stockfish_windows.exe"] if cls.is_windows() else ["stockfish"]

        # 1. System PATH
        for name in exe_names:
            sys_found = cls.safe_which(name)
            if sys_found:
                return sys_found

        # 2. Local project engines directory
        for name in exe_names:
            p = os.path.join(base_dir, "models", "engines", name)
            if os.path.isfile(p):
                if cls.is_windows() or os.access(p, os.X_OK):
                    return p

        # 3. Standard OS directories
        if cls.is_windows():
            prog_files = os.environ.get("PROGRAMFILES", "C:\\Program Files")
            win_candidates = [
                os.path.join(prog_files, "Stockfish", "stockfish.exe"),
                os.path.join(os.environ.get("LOCALAPPDATA", ""), "Stockfish", "stockfish.exe"),
            ]
            for p in win_candidates:
                if os.path.isfile(p):
                    return p
        else:
            unix_candidates = [
                "/usr/games/stockfish",
                "/usr/bin/stockfish",
                "/usr/local/bin/stockfish",
                os.path.expanduser("~/.local/bin/stockfish")
            ]
            for p in unix_candidates:
                if os.path.isfile(p) and os.access(p, os.X_OK):
                    return p

        return None

    @classmethod
    def find_ollama_binary(cls, models_dir: str) -> str:
        """Finds Ollama binary path across Windows, Linux, and macOS."""
        bin_name = "ollama.exe" if cls.is_windows() else "ollama"
        sys_bin = cls.safe_which(bin_name) or cls.safe_which("ollama")
        if sys_bin:
            return sys_bin

        local_bin = os.path.join(models_dir, "bin", bin_name)
        if os.path.isfile(local_bin):
            return local_bin

        if cls.is_windows():
            local_appdata = os.environ.get("LOCALAPPDATA", "")
            if local_appdata:
                win_ollama = os.path.join(local_appdata, "Programs", "Ollama", "ollama.exe")
                if os.path.isfile(win_ollama):
                    return win_ollama

        return local_bin
