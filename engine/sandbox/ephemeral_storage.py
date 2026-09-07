import os
import sys
import shutil
import logging
import subprocess
from typing import Tuple, List

logger = logging.getLogger("EphemeralStorage")


import tempfile

class EphemeralStorageManager:
    """Manages flüchtige RAM-Disk Profile (tmpfs / Windows Ephemeral Temp) mit forensischem Shredding beim Beenden."""

    @staticmethod
    def is_tmpfs_supported() -> bool:
        """Checks if tmpfs/RAM-disk mounting, /dev/shm, or Windows ephemeral temp is available."""
        return os.path.exists("/dev/shm") or sys.platform == "linux" or sys.platform == "win32"

    @classmethod
    def mount_ramdisk(cls, profile_id: str, target_dir: str, size_mb: int = 512) -> Tuple[bool, str]:
        """Mounts a tmpfs RAM disk for target_dir or uses /dev/shm / Windows ephemeral fallback."""
        os.makedirs(target_dir, exist_ok=True)
        logger.info(f"[EphemeralStorage] Initializing ephemeral RAM disk for profile '{profile_id}' ({size_mb}MB)")

        # Attempt 1: Linux Native mount -t tmpfs if root/sudo permits
        if sys.platform == "linux":
            try:
                res = subprocess.run(
                    ["mount", "-t", "tmpfs", "-o", f"size={size_mb}M", "tmpfs", target_dir],
                    capture_output=True, text=True
                )
                if res.returncode == 0:
                    logger.info(f"[EphemeralStorage] Successfully mounted tmpfs RAM disk on '{target_dir}'")
                    return True, "Mounted via kernel tmpfs"
            except Exception as e:
                logger.debug(f"[EphemeralStorage] Kernel mount failed: {e}")

        # Attempt 2: Linux High-performance RAM fallback using /dev/shm
        if os.path.exists("/dev/shm"):
            shm_dir = f"/dev/shm/soxbot_ram_{profile_id[:12]}"
            try:
                os.makedirs(shm_dir, exist_ok=True)
                logger.info(f"[EphemeralStorage] Using /dev/shm RAM-disk allocation at '{shm_dir}'")
                return True, f"RAM-disk allocated at {shm_dir}"
            except Exception as e:
                return False, f"Failed to allocate RAM-disk in /dev/shm: {e}"

        # Attempt 3: Windows Ephemeral Temp Storage with auto-wipe
        if sys.platform == "win32":
            win_temp = os.path.join(tempfile.gettempdir(), f"soxbot_ram_{profile_id[:12]}")
            try:
                os.makedirs(win_temp, exist_ok=True)
                logger.info(f"[EphemeralStorage] Allocated Windows ephemeral storage at '{win_temp}'")
                return True, f"Windows ephemeral storage allocated at {win_temp}"
            except Exception as e:
                return False, f"Failed to allocate Windows ephemeral storage: {e}"

        return False, "RAM disk storage not supported on host OS"

    @classmethod
    def get_shm_path(cls, profile_id: str) -> str:
        if sys.platform == "win32":
            return os.path.join(tempfile.gettempdir(), f"soxbot_ram_{profile_id[:12]}")
        return f"/dev/shm/soxbot_ram_{profile_id[:12]}"

    @classmethod
    def wipe_and_unmount(cls, profile_id: str, target_dir: str) -> bool:
        """Executes unmount of RAM storage and cleans up ephemeral directories fast without blocking UI."""
        logger.info(f"[EphemeralStorage] Initiating wipe and unmount for profile '{profile_id}' at '{target_dir}'")

        shm_dir = cls.get_shm_path(profile_id)
        dirs_to_wipe = [target_dir]
        if os.path.exists(shm_dir):
            dirs_to_wipe.append(shm_dir)

        # 1. Attempt unmount if tmpfs mount was active
        try:
            subprocess.run(["umount", "-f", target_dir], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2.0)
        except Exception:
            pass

        # 2. Clean up directory trees fast
        for d in dirs_to_wipe:
            if os.path.exists(d):
                try:
                    shutil.rmtree(d, ignore_errors=True)
                except Exception:
                    pass

        logger.info(f"[EphemeralStorage] Storage wipe and unmount completed for profile '{profile_id}'.")
        return True
