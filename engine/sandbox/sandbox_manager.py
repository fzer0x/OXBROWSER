import os
import shutil
import logging
from typing import Dict, Any, Optional, Tuple
import config
from engine.sandbox.sandbox_base import BaseSandbox
from engine.sandbox.container_sandbox import ContainerSandbox, check_cmd_available
from engine.sandbox.microvm_sandbox import MicroVMSandbox
from engine.sandbox.virtiofs_manager import VirtiofsDaemonManager
from engine.sandbox.ephemeral_storage import EphemeralStorageManager

logger = logging.getLogger("SandboxManager")

class SandboxManager:
    """Factory and lifecycle orchestrator for SoxBot profile sandboxes."""

    @staticmethod
    def create_sandbox(profile_id: str, profile_data: Dict[str, Any], user_data_dir: str, debug_port: int) -> BaseSandbox:
        """Instantiates the appropriate sandbox instance based on profile configuration."""
        sandbox_cfg = profile_data.get("sandbox", {})
        mode = str(sandbox_cfg.get("mode", "container")).lower().strip()

        if mode == "microvm":
            logger.info(f"[SandboxManager] Creating MicroVM Sandbox for profile '{profile_id}'")
            return MicroVMSandbox(profile_id, profile_data, user_data_dir, debug_port)
        elif mode == "container" or mode == "on":
            logger.info(f"[SandboxManager] Creating Container/Process Sandbox for profile '{profile_id}'")
            return ContainerSandbox(profile_id, profile_data, user_data_dir, debug_port)
        else:
            logger.info(f"[SandboxManager] Sandbox mode 'off' selected for profile '{profile_id}'. Using standard process sandbox.")
            return ContainerSandbox(profile_id, profile_data, user_data_dir, debug_port)

    @staticmethod
    def check_system_capabilities() -> Dict[str, Any]:
        """Inspects host OS capabilities for Docker, Podman, Cloud-Hypervisor, Firecracker, Virtiofs, KVM, and Ephemeral RAM Storage."""
        has_docker = check_cmd_available("docker")
        has_podman = check_cmd_available("podman")
        has_ch = check_cmd_available("cloud-hypervisor")
        has_fc = check_cmd_available("firecracker")
        has_virtiofsd = VirtiofsDaemonManager.is_virtiofsd_available()
        has_kvm = os.path.exists("/dev/kvm") and os.access("/dev/kvm", os.R_OK | os.W_OK)
        has_xvfb = check_cmd_available("Xvfb")
        has_qemu = check_cmd_available("qemu-system-x86_64")
        has_tmpfs = EphemeralStorageManager.is_tmpfs_supported()

        rec_mode = "container"
        if (has_ch or has_fc) and has_kvm:
            rec_mode = "microvm"
        elif has_podman or has_docker or has_xvfb:
            rec_mode = "container"

        return {
            "docker": has_docker,
            "podman": has_podman,
            "cloud_hypervisor": has_ch,
            "firecracker": has_fc,
            "virtiofsd": has_virtiofsd,
            "kvm": has_kvm,
            "xvfb": has_xvfb,
            "qemu": has_qemu,
            "tmpfs_ram": has_tmpfs,
            "recommended_mode": rec_mode
        }
