"""
Browser Downloader & Engine Readiness Manager for OXBROWSER.
Provides safe detection, streaming downloads with byte-level progress reporting,
checksum verification, and multi-version registration for Camoufox and Chromium engines.
"""

import os
import sys
import time
import shutil
import logging
import hashlib
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Callable, Tuple, Dict, Any

logger = logging.getLogger("BrowserDownloader")


class CancellationToken:
    """Thread-safe cancellation token for browser engine downloads."""
    def __init__(self) -> None:
        self.is_cancelled: bool = False

    def cancel(self) -> None:
        self.is_cancelled = True


class BrowserDownloader:
    """
    Manages browser engine detection, downloads, and lifecycle hooks
    without triggering unexpected blocking downloads.
    """

    @classmethod
    def is_engine_installed(cls, engine_type: str = "camoufox") -> Tuple[bool, str]:
        """
        Safely checks if the requested engine is installed and ready to execute
        WITHOUT invoking any auto-download or blocking network routines.
        """
        engine = (engine_type or "camoufox").lower().strip()

        if engine in ["camoufox", "firefox"]:
            try:
                import camoufox
                from camoufox.multiversion import get_active_path
                from camoufox.pkgman import Version, LAUNCH_FILE, OS_NAME

                active = get_active_path()
                if not active or not os.path.isdir(active):
                    return False, "Camoufox engine directory not found."

                v = Version.from_path(active)
                if not v.is_supported():
                    return False, f"Camoufox v{v.full_string} is outdated and requires an update."

                launch_bin = active / LAUNCH_FILE[OS_NAME]
                if not os.path.isfile(launch_bin):
                    return False, f"Camoufox binary missing at {launch_bin}."

                return True, f"Camoufox v{v.full_string} is ready."
            except ImportError:
                return False, "Python package 'camoufox' is not installed in the environment."
            except Exception as e:
                return False, f"Camoufox readiness check notice: {e}"

        elif engine == "playwright":
            # Check for Playwright Chromium in local app data or system fallback
            try:
                from engine.platform_helper import PlatformHelper
                import config
                detected_chrome = PlatformHelper.find_chromium_binary(getattr(config, "BASE_DIR", ""))
                if detected_chrome and os.path.isfile(detected_chrome):
                    return True, f"Chromium binary ready ({detected_chrome})."

                # Check Playwright default cache folder
                local_appdata = os.environ.get("LOCALAPPDATA", "")
                if sys.platform == "win32" and local_appdata:
                    pw_cache = os.path.join(local_appdata, "ms-playwright")
                    if os.path.isdir(pw_cache):
                        for item in os.listdir(pw_cache):
                            if item.startswith("chromium-"):
                                chrome_exe = os.path.join(pw_cache, item, "chrome-win", "chrome.exe")
                                if os.path.isfile(chrome_exe):
                                    return True, f"Playwright Chromium ready ({chrome_exe})."
                return False, "Playwright Chromium binary not found."
            except Exception as e:
                return False, f"Playwright readiness check notice: {e}"

        elif engine in ["nodriver", "selenium_driverless"]:
            try:
                from engine.platform_helper import PlatformHelper
                import config
                detected_chrome = PlatformHelper.find_chromium_binary(getattr(config, "BASE_DIR", ""))
                if detected_chrome and os.path.isfile(detected_chrome):
                    return True, f"Chromium browser ready ({detected_chrome})."
                return False, "No Chromium or Chrome browser executable found on system."
            except Exception as e:
                return False, f"Chromium readiness check notice: {e}"

        return True, f"Engine '{engine_type}' does not require dedicated download management."

    @classmethod
    def get_camoufox_download_info(cls) -> Dict[str, Any]:
        """
        Retrieves release metadata (target version, URL, expected SHA256)
        from CamoufoxFetcher without starting the download.
        """
        from camoufox.pkgman import CamoufoxFetcher
        fetcher = CamoufoxFetcher()
        url = fetcher.url
        verstr = fetcher.verstr
        expected_sha = (
            fetcher._selected_version.sha256
            if getattr(fetcher, "_selected_version", None)
            else getattr(fetcher, "installed_sha256", None)
        )
        return {
            "fetcher": fetcher,
            "version": verstr,
            "url": url,
            "expected_sha": expected_sha
        }

    @classmethod
    def download_camoufox(
        cls,
        progress_callback: Optional[Callable[[int, int, float, str, str], None]] = None,
        cancel_token: Optional[CancellationToken] = None
    ) -> Tuple[bool, str]:
        """
        Downloads, verifies, and installs Camoufox stealth browser with progress reporting.

        progress_callback signature:
            callback(downloaded_bytes: int, total_bytes: int, speed_bps: float, eta_str: str, phase_text: str)
        """
        import requests
        import orjson
        import zipfile
        from camoufox.pkgman import (
            CamoufoxFetcher, GITHUB_TOKEN, OS_NAME
        )
        from camoufox.multiversion import (
            BROWSERS_DIR, COMPAT_FLAG, get_repo_name, version_folder_name, set_active
        )

        def emit_progress(downloaded: int, total: int, speed: float, eta: str, phase: str):
            if progress_callback:
                try:
                    progress_callback(downloaded, total, speed, eta, phase)
                except Exception as cb_err:
                    logger.debug(f"[BrowserDownloader] Progress callback notice: {cb_err}")

        emit_progress(0, 0, 0.0, "--", "Connecting to Camoufox release servers...")

        # 1. Resolve release metadata
        try:
            fetcher = CamoufoxFetcher()
            target_url = fetcher.url
            verstr = fetcher.verstr
            repo_name = get_repo_name(fetcher.github_repo)
            sha8 = (
                fetcher._selected_version.sha8
                if getattr(fetcher, "_selected_version", None) and fetcher._selected_version.sha256
                else getattr(fetcher, "installed_sha8", "")
            )
            version_folder = version_folder_name(fetcher.version, fetcher.build, sha8)
            install_path = BROWSERS_DIR / repo_name / version_folder
            expected_sha = (
                fetcher._selected_version.sha256
                if getattr(fetcher, "_selected_version", None)
                else getattr(fetcher, "installed_sha256", None)
            )
        except Exception as meta_err:
            logger.error(f"[BrowserDownloader] Failed to resolve Camoufox metadata: {meta_err}")
            return False, f"Failed to retrieve Camoufox release details: {meta_err}"

        # 2. Check if already installed in this exact folder
        if install_path.exists() and (install_path / "version.json").exists():
            set_active(f"browsers/{repo_name}/{version_folder}")
            COMPAT_FLAG.touch()
            emit_progress(100, 100, 0.0, "0s", f"Camoufox v{verstr} is already up to date.")
            return True, f"Camoufox v{verstr} is already installed and ready."

        # 3. Stream download to temp file
        headers = {}
        if "api.github" in target_url and GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

        temp_zip = None
        try:
            emit_progress(0, 0, 0.0, "--", f"Connecting to download Camoufox v{verstr}...")
            response = requests.get(target_url, stream=True, headers=headers, timeout=30)
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))
            fd, temp_zip = tempfile.mkstemp(suffix=".zip", prefix="camoufox_dl_")
            os.close(fd)

            downloaded = 0
            block_size = 256 * 1024  # 256 KB chunks for high throughput
            start_time = time.time()
            last_calc_time = start_time
            last_calc_bytes = 0
            current_speed = 0.0

            hasher = hashlib.sha256()

            with open(temp_zip, "wb") as f_out:
                for chunk in response.iter_content(chunk_size=block_size):
                    if cancel_token and cancel_token.is_cancelled:
                        logger.info("[BrowserDownloader] Download cancelled by user.")
                        return False, "Download cancelled by user."

                    if not chunk:
                        continue

                    f_out.write(chunk)
                    hasher.update(chunk)
                    downloaded += len(chunk)

                    now = time.time()
                    elapsed = now - last_calc_time
                    if elapsed >= 0.3:
                        bytes_diff = downloaded - last_calc_bytes
                        instant_speed = bytes_diff / elapsed if elapsed > 0 else 0.0
                        current_speed = instant_speed if current_speed == 0.0 else (current_speed * 0.7 + instant_speed * 0.3)
                        last_calc_time = now
                        last_calc_bytes = downloaded

                        if current_speed > 0 and total_size > downloaded:
                            remaining_sec = int((total_size - downloaded) / current_speed)
                            if remaining_sec < 60:
                                eta_str = f"{remaining_sec}s"
                            else:
                                eta_str = f"{remaining_sec // 60}m {remaining_sec % 60}s"
                        else:
                            eta_str = "--"

                        percent = int((downloaded / total_size * 100)) if total_size > 0 else 0
                        dl_mb = downloaded / (1024 * 1024)
                        tot_mb = total_size / (1024 * 1024) if total_size > 0 else 0
                        phase = f"Downloading Camoufox: {dl_mb:.1f} / {tot_mb:.1f} MB ({percent}%)"
                        emit_progress(downloaded, total_size, current_speed, eta_str, phase)

            if cancel_token and cancel_token.is_cancelled:
                return False, "Download cancelled by user."

            # 4. Checksum Verification
            emit_progress(downloaded, total_size, 0.0, "0s", "Verifying SHA-256 integrity checksum...")
            calculated_sha = hasher.hexdigest()
            if expected_sha and calculated_sha.lower() != expected_sha.lower():
                logger.error(f"[BrowserDownloader] Checksum mismatch! Got {calculated_sha}, expected {expected_sha}")
                return False, f"Checksum verification failed (corrupted download). Please try again."

            # 5. Extract Archive
            emit_progress(downloaded, total_size, 0.0, "0s", f"Extracting Camoufox binaries to {repo_name}...")
            install_path.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(temp_zip, "r") as zf:
                zf.extractall(str(install_path))

            # 6. Save Metadata & Activate
            emit_progress(downloaded, total_size, 0.0, "0s", "Finalizing installation and registering engine...")
            if getattr(fetcher, "_selected_version", None):
                metadata = fetcher._selected_version.to_metadata()
            else:
                metadata = {
                    "version": fetcher.version,
                    "build": fetcher.build,
                    "prerelease": fetcher.is_prerelease,
                    "sha256": getattr(fetcher, "installed_sha256", None),
                    "created_at": getattr(fetcher, "installed_created_at", None),
                }

            with open(install_path / "version.json", "wb") as vf:
                vf.write(orjson.dumps(metadata))

            if OS_NAME != "win":
                try:
                    subprocess.run(["chmod", "-R", "755", str(install_path)], check=False)
                except Exception:
                    pass

            set_active(f"browsers/{repo_name}/{version_folder}")
            COMPAT_FLAG.touch()

            emit_progress(total_size, total_size, 0.0, "0s", f"Camoufox v{verstr} ready!")
            logger.info(f"[BrowserDownloader] Camoufox v{verstr} installed successfully at {install_path}")
            return True, f"Camoufox v{verstr} installed successfully."

        except Exception as dl_err:
            logger.error(f"[BrowserDownloader] Camoufox download error: {dl_err}", exc_info=True)
            if install_path.exists() and not (install_path / "version.json").exists():
                shutil.rmtree(install_path, ignore_errors=True)
            return False, f"Download failed: {dl_err}"
        finally:
            if temp_zip and os.path.exists(temp_zip):
                try:
                    os.remove(temp_zip)
                except Exception:
                    pass

    @classmethod
    def download_playwright_chromium(
        cls,
        progress_callback: Optional[Callable[[int, int, float, str, str], None]] = None,
        cancel_token: Optional[CancellationToken] = None
    ) -> Tuple[bool, str]:
        """
        Downloads and installs Playwright Chromium binary using subprocess with progress tracking.
        """
        def emit_progress(percent: int, phase: str):
            if progress_callback:
                try:
                    progress_callback(percent, 100, 0.0, "--", phase)
                except Exception:
                    pass

        emit_progress(5, "Initiating Playwright Chromium installer...")
        cmd = [sys.executable, "-m", "playwright", "install", "chromium"]
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            current_pct = 10
            while True:
                if cancel_token and cancel_token.is_cancelled:
                    proc.kill()
                    return False, "Playwright Chromium download cancelled by user."

                line = proc.stdout.readline() if proc.stdout else ""
                if not line and proc.poll() is not None:
                    break

                if line:
                    clean_line = line.strip()
                    logger.debug(f"[BrowserDownloader Playwright] {clean_line}")
                    if "%" in clean_line:
                        import re
                        m = re.search(r"(\d{1,3})%", clean_line)
                        if m:
                            current_pct = max(current_pct, int(m.group(1)))
                    emit_progress(current_pct, f"Playwright Chromium: {clean_line[:60]}")

            returncode = proc.wait()
            if returncode == 0:
                emit_progress(100, "Playwright Chromium installation complete!")
                return True, "Playwright Chromium installed successfully."
            return False, f"Playwright installer exited with code {returncode}."
        except Exception as e:
            return False, f"Playwright Chromium installation failed: {e}"
