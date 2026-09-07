import os
import shutil
import asyncio
import logging
import subprocess
from typing import Optional, Tuple

logger = logging.getLogger("VirtiofsManager")

class VirtiofsDaemonManager:
    """Manages host virtiofsd (Virtio-FS Daemon) instances for zero-copy MicroVM directory sharing."""

    def __init__(self, profile_id: str, shared_dir: str):
        self.profile_id = profile_id
        self.shared_dir = shared_dir
        self.socket_path = f"/tmp/vfs_{self.profile_id[:12]}.sock"
        self.process: Optional[subprocess.Popen] = None

    @classmethod
    def _get_virtiofsd_binary(cls) -> Optional[str]:
        found = shutil.which("virtiofsd")
        if found:
            return found
        candidate_paths = [
            "/usr/lib/virtiofsd",
            "/usr/libexec/virtiofsd",
            "/usr/lib/qemu/virtiofsd",
            "/usr/local/bin/virtiofsd",
            "/opt/docker-desktop/bin/virtiofsd",
        ]
        for p in candidate_paths:
            if os.path.exists(p) and os.access(p, os.X_OK):
                return p
        return None

    @classmethod
    def is_virtiofsd_available(cls) -> bool:
        """Checks if virtiofsd binary is installed on the host."""
        return cls._get_virtiofsd_binary() is not None

    async def start(self) -> Tuple[bool, str]:
        """Launches virtiofsd bound to the shared directory and socket."""
        binary = self._get_virtiofsd_binary()
        if not binary:
            return False, "virtiofsd binary not found on host."

        os.makedirs(self.shared_dir, exist_ok=True)

        # Cleanup existing socket if leftover from previous run
        if os.path.exists(self.socket_path):
            try:
                os.remove(self.socket_path)
            except Exception:
                pass

        cmd = [
            binary,
            f"--socket-path={self.socket_path}",
            f"--shared-dir={self.shared_dir}",
            "--sandbox=chroot",
            "--cache=auto"
        ]

        logger.info(f"[VirtiofsManager] Starting virtiofsd for profile '{self.profile_id}': {' '.join(cmd)}")
        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            # Wait briefly to confirm daemon started
            await asyncio.sleep(0.3)
            if self.process.poll() is not None:
                _, err = self.process.communicate()
                return False, f"virtiofsd failed to start: {err}"

            return True, self.socket_path
        except Exception as e:
            logger.error(f"[VirtiofsManager] Exception starting virtiofsd: {e}")
            return False, str(e)

    async def stop(self) -> bool:
        """Stops the virtiofsd process and removes the socket."""
        if self.process:
            logger.info(f"[VirtiofsManager] Terminating virtiofsd for profile '{self.profile_id}'")
            try:
                self.process.terminate()
                await asyncio.sleep(0.2)
                if self.process.poll() is None:
                    self.process.kill()
            except Exception as e:
                logger.warning(f"[VirtiofsManager] Error stopping virtiofsd: {e}")
            self.process = None

        if os.path.exists(self.socket_path):
            try:
                os.remove(self.socket_path)
            except Exception:
                pass
        return True
