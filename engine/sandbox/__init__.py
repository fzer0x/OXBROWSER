"""
SoxBot Sandbox & MicroVM Hardware Virtualization Engine.
Provides containerized (Podman/Docker OCI) and MicroVM (QEMU/KVM) browser process isolation
with Mesa GPU hardware emulation, font isolation, and virtual display framebuffers.
"""

from engine.sandbox.sandbox_base import BaseSandbox
from engine.sandbox.container_sandbox import ContainerSandbox
from engine.sandbox.microvm_sandbox import MicroVMSandbox
from engine.sandbox.gpu_profiles import GPUProfileManager
from engine.sandbox.sandbox_manager import SandboxManager
from engine.sandbox.sandbox_installer import SandboxInstaller

__all__ = [
    "BaseSandbox",
    "ContainerSandbox",
    "MicroVMSandbox",
    "GPUProfileManager",
    "SandboxManager",
    "SandboxInstaller"
]
