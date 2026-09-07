import os
import json
import uuid
import time
import shutil
import zipfile
import copy
import logging
from typing import List, Dict, Optional, Tuple
import config
from storage.crypto_vault import ZeroKnowledgeCryptoVault
from engine.sandbox.ephemeral_storage import EphemeralStorageManager

logger = logging.getLogger("ProfileManager")


def _safe_extractall(zipf: zipfile.ZipFile, target_dir: str) -> None:
    """[F-02] Zip-Slip-safe extraction: validates all member paths stay within target_dir."""
    target_dir = os.path.realpath(target_dir)
    for member in zipf.namelist():
        member_path = os.path.realpath(os.path.join(target_dir, member))
        if not member_path.startswith(target_dir + os.sep) and member_path != target_dir:
            raise ValueError(f"[Security] Zip Slip blocked: '{member}' would escape target directory.")
    zipf.extractall(target_dir)


class ProfileManager:
    """Manages browser profiles stored as JSON/encrypted files with individual user data & RAM-disk directories."""

    def __init__(self, profiles_dir: str = config.PROFILES_DIR):
        self.profiles_dir = profiles_dir
        os.makedirs(self.profiles_dir, exist_ok=True)

    def get_profile_path(self, profile_id: str) -> str:
        return os.path.join(self.profiles_dir, profile_id)

    def get_profile_json_path(self, profile_id: str) -> str:
        return os.path.join(self.get_profile_path(profile_id), "profile.json")

    def get_profile_enc_path(self, profile_id: str) -> str:
        return os.path.join(self.get_profile_path(profile_id), "profile.enc")

    def get_user_data_dir(self, profile_id: str) -> str:
        return os.path.join(self.get_profile_path(profile_id), "user_data")

    def create_default_profile_data(self, name: str = "New Profile", os_type: str = "linux") -> Dict:
        profile_id = str(uuid.uuid4())
        valid_presets = config.get_webgl_presets_for_os(os_type)
        preset_webgl = valid_presets[0] if valid_presets else config.WEBGL_PRESETS[0]

        return {
            "id": profile_id,
            "name": name,
            "group": "Default",
            "tags": ["General"],
            "notes": "",
            "created_at": time.time(),
            "last_launch": 0,
            "status": "Stopped",
            "engine": "camoufox",
            "ephemeral_ram": False,
            "encrypted": False,

            # Operating System & Device Fingerprint
            "start_url": "",
            "os": os_type,
            "os_version": "10.0.0",
            "device_vendor": "Google" if os_type != "mac" else "Apple",
            "device_model": "PC" if os_type != "mac" else "Macintosh",
            "user_agent": config.get_default_user_agent(os_type, "camoufox"),
            "screen_resolution": "1920x1080",
            "window_mode": "tile_grid",
            "window_width": 1368    ,
            "window_height": 768,
            "window_pos_x": 0,
            "window_pos_y": 0,
            "color_depth": 24,
            "max_touch_points": 0,
            "hardware_concurrency": 8,
            "device_memory": 16,
            "language": "en-US,en;q=0.9",
            "timezone": "auto",
            "do_not_track": "null",

            # Custom Geolocation Details
            "location": {
                "country": "",
                "region": "",
                "city": "",
                "postal_code": "",
                "lat": 0.0,
                "lon": 0.0
            },

            # Proxy Configuration
            "proxy": {
                "enabled": False,
                "type": "http",
                "host": "",
                "port": 3128,
                "username": "",
                "password": "",
                "auto_timezone": True,
                "auto_geolocation": True,
                "network_killswitch": True
            },

            "network_killswitch": True,
            "tls_ja3_preset": "auto",

            # Proxy Cache / Geolocation Info
            "proxy_info": {
                "ip": "",
                "country": "",
                "country_code": "",
                "city": "",
                "timezone": "",
                "lat": 0.0,
                "lon": 0.0,
                "isp": ""
            },

            # Stealth & Anti-Detect Overrides (Hardened V2 Defaults)
            "stealth": {
                "canvas_noise": True,
                "canvas_mode": "aggressiveness_low",
                "webgl_spoofing": True,
                "webgl_mode": "spoof",
                "webgl_vendor": preset_webgl["vendor"],
                "webgl_renderer": preset_webgl["renderer"],
                "webgpu_supported": False,
                "audio_noise": True,
                "audio_mode": "natural_jitter",
                "webrtc_mode": "altered",
                "client_rects_noise": True,
                "font_fingerprint_noise": True,
                "pdf_viewers": ["internal-pdf-viewer", "Chrome PDF Viewer", "Chromium PDF Viewer"],
                "custom_fonts": ["Helvetica", "Arial", "Times New Roman", "Courier New", "Verdana"],
                "custom_patches": []
            },

            # Hardware & Sandbox Isolation (Container / MicroVM)
            "sandbox": {
                "mode": "off",  # 'container', 'microvm', 'off'
                "microvm_engine": "cloud-hypervisor",  # 'cloud-hypervisor', 'firecracker', 'qemu'
                "use_virtiofs": True,
                "oci_runtime": "auto",
                "emulated_os": "linux",
                "gpu_preset": "nvidia_rtx3060",
                "graphics_driver": "llvmpipe",
                "font_pack": "win10_standard",
                "isolate_network": True
            },

            # Accounts & Social Logins (Google, Instagram, GitHub, TikTok, etc.)
            "accounts": [],

            # Extensions and Remote Debugging
            "extensions": [],
            "debug_port": 0,

            # Browser Behavior, History, Autofill & Natural Persistence (Hardened V2 Defaults)
            "behavior": {
                "save_history": True,
                "search_suggestions": True,
                "restore_session": False,
                "form_autofill": True,
                "password_manager": False,
                "credit_card_autofill": False,
                "address_autofill": False,
                "disk_cache": True,
                "offline_storage": True,
                "clear_on_shutdown": False,
                "block_telemetry": False,
                "autoplay_media": "allow",
                "drm_widevine": False
            }
        }

    def harmonize_profile_tensor(self, profile_data: Dict) -> Tuple[Dict, List[str]]:
        """
        Validates and auto-harmonizes OS, WebGL GPU, Hardware, and WebRTC parameters
        to eliminate mathematical fingerprint contradictions (e.g. Linux with Direct3D11).
        """
        fixes: List[str] = []
        os_type = (profile_data.get("os") or "windows").lower()
        stealth = profile_data.setdefault("stealth", {})
        
        cur_vendor = stealth.get("webgl_vendor", "")
        cur_renderer = stealth.get("webgl_renderer", "")
        
        valid_presets = config.get_webgl_presets_for_os(os_type)
        default_preset = valid_presets[0]
        # Check if current WebGL renderer contradicts OS
        r_lower = cur_renderer.lower()
        v_lower = cur_vendor.lower()
        is_conflict = False
        
        if os_type == "linux" and ("direct3d" in r_lower or "d3d" in r_lower or "apple" in v_lower or "google inc" in v_lower):
            is_conflict = True
        elif os_type == "windows" and ("mesa" in v_lower or "apple" in v_lower or "llvmpipe" in r_lower):
            is_conflict = True
        elif os_type == "mac" and ("direct3d" in r_lower or "d3d" in r_lower or "mesa" in v_lower):
            is_conflict = True
        elif os_type in ["android", "ios"] and ("direct3d" in r_lower or "rtx" in r_lower):
            is_conflict = True

        if is_conflict or not cur_renderer:
            # Match specific GPU model if possible, otherwise default to first valid preset
            matched_preset = default_preset
            if "4090" in r_lower:
                matched_preset = next((p for p in valid_presets if "4090" in p["renderer"]), default_preset)
            elif "4080" in r_lower:
                matched_preset = next((p for p in valid_presets if "4080" in p["renderer"]), default_preset)
            elif "4070" in r_lower:
                matched_preset = next((p for p in valid_presets if "4070" in p["renderer"]), default_preset)
            elif "3060" in r_lower:
                matched_preset = next((p for p in valid_presets if "3060" in p["renderer"]), default_preset)
            elif "7900" in r_lower or "radeon" in r_lower:
                matched_preset = next((p for p in valid_presets if "7900" in p["renderer"] or "Radeon" in p["renderer"]), default_preset)
            elif "m3" in r_lower:
                matched_preset = next((p for p in valid_presets if "M3" in p["renderer"]), default_preset)
            elif "m2" in r_lower:
                matched_preset = next((p for p in valid_presets if "M2" in p["renderer"]), default_preset)

            stealth["webgl_vendor"] = matched_preset["vendor"]
            stealth["webgl_renderer"] = matched_preset["renderer"]
            profile_data["webgl_vendor"] = matched_preset["vendor"]
            profile_data["webgl_renderer"] = matched_preset["renderer"]
            fixes.append(f"Harmonized WebGL GPU to match {os_type.capitalize()}: '{matched_preset['renderer']}'")

        # Hardware Concurrency / RAM harmony check
        cores = profile_data.get("hardware_concurrency", 8)
        ram = profile_data.get("device_memory", 8)
        if cores >= 12 and ram < 16:
            profile_data["device_memory"] = 16
            fixes.append(f"Adjusted RAM to 16 GB to harmonize with {cores}-core CPU topology")

        # Engine & User-Agent harmony check
        engine_type = str(profile_data.get("engine", "camoufox")).lower()
        custom_ua = profile_data.get("custom_user_agent", False)
        cur_ua = profile_data.get("user_agent", "")
        if engine_type == "camoufox" and not custom_ua and ("Chrome/" in cur_ua or not cur_ua):
            new_ua = config.get_default_user_agent(os_type, "camoufox")
            profile_data["user_agent"] = new_ua
            fixes.append(f"Harmonized User-Agent to match native Camoufox Firefox engine: '{new_ua}'")
        elif engine_type in ["playwright", "nodriver", "selenium_driverless"] and not custom_ua and ("Firefox/" in cur_ua or not cur_ua):
            new_ua = config.get_default_user_agent(os_type, engine_type)
            profile_data["user_agent"] = new_ua
            fixes.append(f"Harmonized User-Agent to match native Chromium engine: '{new_ua}'")

        # WebRTC Protection Policy harmony check
        orig_webrtc = stealth.get("webrtc_mode") or stealth.get("webrtc") or profile_data.get("webrtc_mode") or profile_data.get("webrtc")
        self._normalize_stealth_config(profile_data)
        webrtc_mode = stealth.get("webrtc_mode", "altered")
        if orig_webrtc not in ["altered", "disabled", "real"]:
            fixes.append(f"Harmonized WebRTC Protection policy to '{webrtc_mode}' (Protocol-Level IP Spoofing)")

        return profile_data, fixes

    def create_profile(self, profile_data: Dict, master_password: Optional[str] = None) -> Dict:
        if "id" not in profile_data or not profile_data["id"]:
            profile_data["id"] = str(uuid.uuid4())

        profile_dir = self.get_profile_path(profile_data["id"])
        user_data_dir = self.get_user_data_dir(profile_data["id"])
        os.makedirs(profile_dir, exist_ok=True)
        os.makedirs(user_data_dir, exist_ok=True)

        self.save_profile(profile_data, master_password=master_password)
        return profile_data

    @staticmethod
    def _atomic_write_file(file_path: str, content: str, encoding: str = "utf-8") -> bool:
        """Atomically writes string content to target file via temporary file replacement."""
        dir_name = os.path.dirname(file_path)
        os.makedirs(dir_name, exist_ok=True)
        import tempfile
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, prefix=".tmp_profile_", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding=encoding) as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, file_path)
            return True
        except Exception as e:
            logger.error(f"Atomic write failure for '{file_path}': {e}")
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
            return False

    def get_profile(self, profile_id: str, master_password: Optional[str] = None) -> Optional[Dict]:
        return self.load_profile(profile_id, master_password=master_password)

    def load_profile(self, profile_id: str, master_password: Optional[str] = None) -> Optional[Dict]:
        profile_dir = self.get_profile_path(profile_id)
        json_path = self.get_profile_json_path(profile_id)
        enc_path = self.get_profile_enc_path(profile_id)

        # 1. Load Encrypted Profile if present
        if os.path.exists(enc_path):
            try:
                with open(enc_path, "r", encoding="ascii") as f:
                    enc_b64 = f.read()

                # If master password not supplied, check session vault
                if not master_password and ZeroKnowledgeCryptoVault.is_vault_unlocked():
                    pwd = ZeroKnowledgeCryptoVault.get_session_password()
                    if pwd:
                        master_password = pwd

                if not master_password:
                    logger.warning(f"Profile '{profile_id}' is zero-knowledge encrypted. Master password required.")
                    return None

                data = ZeroKnowledgeCryptoVault.decrypt_dict(enc_b64, master_password)
                self._normalize_sandbox_config(data)
                return data
            except Exception as e:
                logger.error(f"Failed to decrypt profile {profile_id}: {e}")
                return None

        # 2. Load Standard Plain JSON Profile
        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._normalize_sandbox_config(data)
                    return data
            except Exception as e:
                logger.error(f"Error loading profile {profile_id}: {e}")
                return None

        return None

    def _normalize_stealth_config(self, data: Dict):
        """Normalizes and migrates WebRTC and stealth parameters to eliminate legacy parameter conflicts."""
        stealth = data.setdefault("stealth", {})
        raw_mode = None
        for candidate in [
            stealth.get("webrtc_mode"),
            stealth.get("webrtc"),
            data.get("webrtc_mode"),
            data.get("webrtc")
        ]:
            if candidate is not None:
                raw_mode = candidate
                break

        if raw_mode is None:
            raw_mode = "altered"

        if isinstance(raw_mode, bool):
            norm_mode = "altered" if raw_mode else "disabled"
        else:
            m_str = str(raw_mode).lower().strip()
            if m_str in ["altered", "spoof", "spoofed", "protocol_spoofing", "proxy"]:
                norm_mode = "altered"
            elif m_str in ["disabled", "block", "blocked", "off", "disable", "none"]:
                norm_mode = "disabled"
            elif m_str in ["real", "raw", "leak", "enabled", "on", "default"]:
                norm_mode = "real"
            else:
                norm_mode = "altered"

        stealth["webrtc_mode"] = norm_mode
        # Remove legacy redundant top-level and inner keys to prevent configuration desync
        data.pop("webrtc_mode", None)
        data.pop("webrtc", None)
        stealth.pop("webrtc", None)

    def _normalize_sandbox_config(self, data: Dict):
        self._normalize_stealth_config(data)
        if "sandbox" not in data:
            data["sandbox"] = {
                "mode": "container",
                "microvm_engine": "cloud-hypervisor",
                "use_virtiofs": True,
                "emulated_os": data.get("os", "linux"),
                "gpu_preset": "nvidia_rtx3060",
                "graphics_driver": "llvmpipe",
                "font_pack": "win10_standard",
                "isolate_network": True
            }
        if "ephemeral_ram" not in data:
            data["ephemeral_ram"] = False
        if "encrypted" not in data:
            data["encrypted"] = False

    def save_profile(self, profile_data: Dict, master_password: Optional[str] = None) -> bool:
        profile_id = profile_data.get("id")
        if not profile_id:
            return False
        self._normalize_stealth_config(profile_data)
        profile_dir = self.get_profile_path(profile_id)
        user_data_dir = self.get_user_data_dir(profile_id)
        os.makedirs(profile_dir, exist_ok=True)
        os.makedirs(user_data_dir, exist_ok=True)

        json_path = self.get_profile_json_path(profile_id)
        enc_path = self.get_profile_enc_path(profile_id)

        # Zero-Knowledge Encryption path
        if profile_data.get("encrypted") or master_password:
            profile_data["encrypted"] = True
            # Fallback to session vault password if active
            if not master_password and ZeroKnowledgeCryptoVault.is_vault_unlocked():
                master_password = ZeroKnowledgeCryptoVault.get_session_password()

            if master_password:
                try:
                    enc_b64 = ZeroKnowledgeCryptoVault.encrypt_dict(profile_data, master_password)
                    if self._atomic_write_file(enc_path, enc_b64, encoding="ascii"):
                        if os.path.exists(json_path):
                            try:
                                os.remove(json_path)
                            except Exception:
                                pass
                        return True
                    return False
                except Exception as e:
                    logger.error(f"Error saving encrypted profile {profile_id}: {e}")
                    return False

        # Standard plain JSON save via atomic write
        try:
            json_str = json.dumps(profile_data, indent=4, ensure_ascii=False)
            if self._atomic_write_file(json_path, json_str, encoding="utf-8"):
                if os.path.exists(enc_path):
                    try:
                        os.remove(enc_path)
                    except Exception:
                        pass
                return True
            return False
        except Exception as e:
            logger.error(f"Error saving profile {profile_id}: {e}")
            return False

    def list_profiles(self, master_password: Optional[str] = None) -> List[Dict]:
        profiles = []
        if not os.path.exists(self.profiles_dir):
            return profiles

        for folder_name in os.listdir(self.profiles_dir):
            folder_path = os.path.join(self.profiles_dir, folder_name)
            if os.path.isdir(folder_path):
                profile = self.load_profile(folder_name, master_password=master_password)
                if profile:
                    profiles.append(profile)
                else:
                    # Return minimal metadata marker if profile is encrypted and locked
                    enc_file = self.get_profile_enc_path(folder_name)
                    if os.path.exists(enc_file):
                        profiles.append({
                            "id": folder_name,
                            "name": f"Locked Encrypted Profile ({folder_name[:8]})",
                            "status": "Locked",
                            "encrypted": True,
                            "ephemeral_ram": False
                        })

        profiles.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        return profiles

    def delete_profile(self, profile_id: str) -> bool:
        profile_dir = self.get_profile_path(profile_id)
        user_data_dir = self.get_user_data_dir(profile_id)

        # Execute forensic RAM wipe if ephemeral RAM disk was used
        EphemeralStorageManager.wipe_and_unmount(profile_id, user_data_dir)

        if os.path.exists(profile_dir):
            try:
                shutil.rmtree(profile_dir)
                return True
            except Exception as e:
                logger.error(f"Error deleting profile directory {profile_id}: {e}")
                return False
        return False

    def prepare_profile_launch(self, profile_data: Dict) -> Tuple[str, bool]:
        """Prepares profile launch by setting up ephemeral RAM disk if enabled."""
        profile_id = profile_data["id"]
        user_data_dir = self.get_user_data_dir(profile_id)

        if profile_data.get("ephemeral_ram", False):
            ok, msg = EphemeralStorageManager.mount_ramdisk(profile_id, user_data_dir)
            logger.info(f"Ephemeral RAM Disk preparation for profile '{profile_id}': {msg}")
            return user_data_dir, ok

        return user_data_dir, True

    def finish_profile_launch(self, profile_data: Dict):
        """Cleanly wipes ephemeral RAM disk after profile stop if enabled."""
        profile_id = profile_data["id"]
        user_data_dir = self.get_user_data_dir(profile_id)

        if profile_data.get("ephemeral_ram", False):
            EphemeralStorageManager.wipe_and_unmount(profile_id, user_data_dir)

    def clone_profile(self, profile_id: str, master_password: Optional[str] = None) -> Optional[Dict]:
        """Duplicates an existing profile with a new UUID and copies browser data."""
        source_profile = self.load_profile(profile_id, master_password=master_password)
        if not source_profile:
            return None

        new_profile = copy.deepcopy(source_profile)
        new_id = str(uuid.uuid4())
        new_profile["id"] = new_id
        new_profile["name"] = f"{source_profile.get('name', 'Profile')} (Copy)"
        new_profile["created_at"] = time.time()
        new_profile["last_launch"] = 0
        new_profile["status"] = "Stopped"

        new_dir = self.get_profile_path(new_id)
        new_user_data = self.get_user_data_dir(new_id)
        os.makedirs(new_dir, exist_ok=True)

        src_user_data = self.get_user_data_dir(profile_id)
        if os.path.exists(src_user_data):
            try:
                shutil.copytree(src_user_data, new_user_data, dirs_exist_ok=True)
                # Purge cloned Widevine CDM certificates/keys to ensure cryptographic unlinkability
                self.clear_profile_drm_cache(new_id)
            except Exception as e:
                logger.warning(f"Note copying user data for profile clone: {e}")
        else:
            os.makedirs(new_user_data, exist_ok=True)

        self.save_profile(new_profile, master_password=master_password)
        return new_profile

    def clear_profile_drm_cache(self, profile_id: str) -> bool:
        """
        Purges cached Widevine CDM binaries, certificate stores, and EME license databases
        from the profile's user data directory to ensure cryptographic unlinkability and fresh DRM identity.
        """
        user_data = self.get_user_data_dir(profile_id)
        if not os.path.exists(user_data):
            return True

        targets = [
            os.path.join(user_data, "gmp-widevinecdm"),
            os.path.join(user_data, "gmp-gmpopenh264"),
            os.path.join(user_data, "storage", "default", "https+++open.spotify.com"),
            os.path.join(user_data, "storage", "permanent", "chrome", "idb"),
        ]

        success = True
        for t in targets:
            if os.path.exists(t):
                try:
                    if os.path.isdir(t):
                        shutil.rmtree(t, ignore_errors=True)
                    else:
                        os.remove(t)
                    logger.debug(f"[ProfileManager] Cleared DRM / CDM cache artifact: {t}")
                except Exception as e:
                    logger.warning(f"[ProfileManager] Could not delete DRM cache '{t}': {e}")
                    success = False
        return success

    def export_profile_bundle(self, profile_id: str, zip_filepath: str, master_password: Optional[str] = None) -> bool:
        """Exports profile directory into a portable .soxprofile / .zip archive."""
        profile_dir = self.get_profile_path(profile_id)
        if not os.path.exists(profile_dir):
            return False

        try:
            os.makedirs(os.path.dirname(os.path.abspath(zip_filepath)), exist_ok=True)
            with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(profile_dir):
                    for file in files:
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, profile_dir)
                        zipf.write(full_path, rel_path)
            logger.info(f"Successfully exported profile '{profile_id}' to archive '{zip_filepath}'.")
            return True
        except Exception as e:
            logger.error(f"Failed to export profile bundle for {profile_id}: {e}")
            return False

    def import_profile_bundle(self, zip_filepath: str, master_password: Optional[str] = None) -> Optional[Dict]:
        """Imports a profile from a .soxprofile / .zip archive with a fresh UUID."""
        if not os.path.exists(zip_filepath):
            return None

        new_id = str(uuid.uuid4())
        target_dir = self.get_profile_path(new_id)
        os.makedirs(target_dir, exist_ok=True)

        try:
            with zipfile.ZipFile(zip_filepath, 'r') as zipf:
                _safe_extractall(zipf, target_dir)  # [F-02] Zip-Slip-safe extraction

            profile_data = self.load_profile(new_id, master_password=master_password)
            if profile_data:
                profile_data["id"] = new_id
                self.save_profile(profile_data, master_password=master_password)
                logger.info(f"Successfully imported profile '{new_id}' from archive '{zip_filepath}'.")
                return profile_data
            else:
                json_files = [f for f in os.listdir(target_dir) if os.path.isdir(os.path.join(target_dir, f))]
                for subfolder in json_files:
                    sub_path = os.path.join(target_dir, subfolder)
                    sub_json = os.path.join(sub_path, "profile.json")
                    if os.path.exists(sub_json):
                        with open(sub_json, "r", encoding="utf-8") as f:
                            pdata = json.load(f)
                        pdata["id"] = new_id
                        shutil.copytree(sub_path, target_dir, dirs_exist_ok=True)
                        shutil.rmtree(sub_path)
                        self.save_profile(pdata, master_password=master_password)
                        return pdata

        except Exception as e:
            logger.error(f"Failed to import profile archive '{zip_filepath}': {e}")
            if os.path.exists(target_dir):
                shutil.rmtree(target_dir, ignore_errors=True)

        return None
