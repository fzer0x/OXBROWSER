import sys
import os
import shutil
import asyncio
import logging
import subprocess
from typing import Tuple, Dict, List, Optional

logger = logging.getLogger("SandboxInstaller")


class SandboxInstaller:
    """Manages automatic installation of Linux sandbox dependencies (Xvfb, Podman/Docker, QEMU/KVM, Cloud-Hypervisor, Firecracker, Virtiofsd)."""

    @staticmethod
    def detect_package_manager() -> Optional[str]:
        """Detects host system package manager (apt-get, dnf, pacman, zypper)."""
        for pm in ["apt-get", "dnf", "pacman", "zypper"]:
            if shutil.which(pm):
                return pm
        return None

    @staticmethod
    async def install_missing_dependencies() -> Tuple[bool, str]:
        """Installs missing Xvfb, Podman, QEMU-KVM, Virtiofsd, Cloud-Hypervisor, and Firecracker packages."""
        pm = SandboxInstaller.detect_package_manager()

        packages = []
        if not shutil.which("Xvfb"):
            if pm == "apt-get":
                packages.append("xvfb")
            elif pm == "pacman":
                packages.append("xorg-server-xvfb")
            elif pm == "dnf":
                packages.append("xorg-x11-server-Xvfb")
            else:
                packages.append("xorg-x11-server-extra")

        if not shutil.which("podman"):
            packages.append("podman")
            if pm == "pacman":
                if not shutil.which("crun"):
                    packages.append("crun")
                if not shutil.which("slirp4netns"):
                    packages.append("slirp4netns")

        if not shutil.which("qemu-system-x86_64"):
            if pm == "apt-get":
                packages.extend(["qemu-kvm", "qemu-system-x86"])
            elif pm == "pacman":
                packages.append("qemu-desktop")
            elif pm == "dnf":
                packages.append("qemu-kvm")
            else:
                packages.append("qemu-x86")

        from engine.sandbox.virtiofs_manager import VirtiofsDaemonManager
        if not VirtiofsDaemonManager.is_virtiofsd_available():
            if pm in ["apt-get", "pacman", "dnf"]:
                packages.append("virtiofsd")

        if pm and packages:
            logger.info(f"[SandboxInstaller] Installing missing system packages: {packages} via {pm}")
            if pm == "apt-get":
                pkg_str = " ".join(packages)
                install_cmd = f"sudo apt-get update && sudo apt-get install -y {pkg_str}"
            elif pm == "dnf":
                pkg_str = " ".join(packages)
                install_cmd = f"sudo dnf install -y {pkg_str}"
            elif pm == "pacman":
                pkg_str = " ".join(packages)
                install_cmd = f"sudo pacman -S --noconfirm {pkg_str}"
            else:
                pkg_str = " ".join(packages)
                install_cmd = f"sudo zypper install -y {pkg_str}"

            term_emulator = None
            for term in ["x-terminal-emulator", "gnome-terminal", "konsole", "xfce4-terminal", "xterm"]:
                if shutil.which(term):
                    term_emulator = term
                    break

            try:
                if term_emulator == "gnome-terminal":
                    cmd = ["gnome-terminal", "--wait", "--", "bash", "-c", f"{install_cmd}; echo 'Press enter to finish...'; read"]
                elif term_emulator == "konsole":
                    cmd = ["konsole", "-e", "bash", "-c", f"{install_cmd}; read"]
                elif term_emulator == "xterm":
                    cmd = ["xterm", "-e", f"{install_cmd}; read"]
                elif term_emulator:
                    cmd = [term_emulator, "-e", "bash", "-c", f"{install_cmd}; read"]
                elif shutil.which("pkexec"):
                    cmd = ["pkexec", "bash", "-c", install_cmd]
                else:
                    cmd = ["bash", "-c", install_cmd]

                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await proc.communicate()
            except Exception as e:
                logger.warning(f"[SandboxInstaller] System package installation notice: {e}")

        # Install static binary dependencies if missing
        ch_ok, ch_msg = await SandboxInstaller.install_cloud_hypervisor()
        fc_ok, fc_msg = await SandboxInstaller.install_firecracker()
        gv_ok, gv_msg = await SandboxInstaller.install_gvisor()
        kvm_ok, kvm_msg = SandboxInstaller.ensure_kvm_permissions()

        msg_summary = f"Cloud-Hypervisor: {ch_msg} | Firecracker: {fc_msg} | gVisor: {gv_msg} | KVM: {kvm_msg}"
        logger.info(f"[SandboxInstaller] MicroVM & Sandbox setup summary: {msg_summary}")
        return True, msg_summary

    @staticmethod
    async def install_cloud_hypervisor() -> Tuple[bool, str]:
        """Downloads and installs official Cloud-Hypervisor static binary."""
        if shutil.which("cloud-hypervisor"):
            return True, "Cloud-Hypervisor is already installed."

        logger.info("[SandboxInstaller] Installing static Cloud-Hypervisor binary...")
        url = "https://github.com/cloud-hypervisor/cloud-hypervisor/releases/latest/download/cloud-hypervisor"

        try:
            # 1. Try system-wide install to /usr/local/bin
            sys_cmd = f"curl -sSL '{url}' -o /tmp/cloud-hypervisor && chmod +x /tmp/cloud-hypervisor && sudo mv /tmp/cloud-hypervisor /usr/local/bin/cloud-hypervisor"
            proc = await asyncio.create_subprocess_shell(
                sys_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()

            if shutil.which("cloud-hypervisor"):
                logger.info("[SandboxInstaller] Cloud-Hypervisor successfully installed system-wide in /usr/local/bin/cloud-hypervisor")
                return True, "Cloud-Hypervisor installed system-wide to /usr/local/bin/cloud-hypervisor"

            # 2. Local fallback to ~/.local/bin
            user_bin = os.path.expanduser("~/.local/bin")
            os.makedirs(user_bin, exist_ok=True)
            user_ch = os.path.join(user_bin, "cloud-hypervisor")

            user_cmd = f"curl -sSL '{url}' -o '{user_ch}' && chmod +x '{user_ch}'"
            proc_user = await asyncio.create_subprocess_shell(
                user_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc_user.communicate()

            if os.path.exists(user_ch):
                if user_bin not in os.environ.get("PATH", ""):
                    os.environ["PATH"] = user_bin + os.pathsep + os.environ.get("PATH", "")
                logger.info(f"[SandboxInstaller] Cloud-Hypervisor installed to {user_ch}")
                return True, f"Cloud-Hypervisor installed locally to {user_ch}"

            return False, "Failed to download Cloud-Hypervisor binary."
        except Exception as e:
            logger.error(f"[SandboxInstaller] Cloud-Hypervisor installation error: {e}")
            return False, str(e)

    @staticmethod
    async def install_firecracker() -> Tuple[bool, str]:
        """Downloads and installs official Firecracker MicroVM static binary."""
        if shutil.which("firecracker"):
            return True, "Firecracker is already installed."

        logger.info("[SandboxInstaller] Installing static Firecracker binary...")
        url = "https://github.com/firecracker-microvm/firecracker/releases/download/v1.7.0/firecracker-v1.7.0-x86_64.tgz"

        try:
            sys_cmd = (
                f"curl -sSL '{url}' -o /tmp/firecracker.tgz && "
                "tar -xzf /tmp/firecracker.tgz -C /tmp && "
                "chmod +x /tmp/release-v1.7.0-x86_64/firecracker-v1.7.0-x86_64 && "
                "sudo mv /tmp/release-v1.7.0-x86_64/firecracker-v1.7.0-x86_64 /usr/local/bin/firecracker"
            )
            proc = await asyncio.create_subprocess_shell(
                sys_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()

            if shutil.which("firecracker"):
                logger.info("[SandboxInstaller] Firecracker successfully installed system-wide in /usr/local/bin/firecracker")
                return True, "Firecracker installed system-wide to /usr/local/bin/firecracker"

            # Local user fallback
            user_bin = os.path.expanduser("~/.local/bin")
            os.makedirs(user_bin, exist_ok=True)
            user_fc = os.path.join(user_bin, "firecracker")

            user_cmd = (
                f"curl -sSL '{url}' -o /tmp/firecracker.tgz && "
                "tar -xzf /tmp/firecracker.tgz -C /tmp && "
                f"cp /tmp/release-v1.7.0-x86_64/firecracker-v1.7.0-x86_64 '{user_fc}' && "
                f"chmod +x '{user_fc}'"
            )
            proc_user = await asyncio.create_subprocess_shell(
                user_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc_user.communicate()

            if os.path.exists(user_fc):
                if user_bin not in os.environ.get("PATH", ""):
                    os.environ["PATH"] = user_bin + os.pathsep + os.environ.get("PATH", "")
                logger.info(f"[SandboxInstaller] Firecracker installed to {user_fc}")
                return True, f"Firecracker installed locally to {user_fc}"

            return False, "Failed to download Firecracker binary."
        except Exception as e:
            logger.error(f"[SandboxInstaller] Firecracker installation error: {e}")
            return False, str(e)

    @staticmethod
    def ensure_kvm_permissions() -> Tuple[bool, str]:
        """Checks /dev/kvm availability and user group permissions."""
        if not os.path.exists("/dev/kvm"):
            return False, "/dev/kvm device node does not exist. Ensure KVM virtualization is enabled in CPU BIOS/UEFI."

        if os.access("/dev/kvm", os.R_OK | os.W_OK):
            return True, "KVM hardware virtualization access confirmed (/dev/kvm R/W ok)."

        # Try adding current user to kvm group if permission denied
        try:
            user = os.environ.get("USER", os.environ.get("LOGNAME", ""))
            if user:
                subprocess.run(["sudo", "usermod", "-aG", "kvm", user], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(["sudo", "chmod", "666", "/dev/kvm"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if os.access("/dev/kvm", os.R_OK | os.W_OK):
                    return True, "KVM hardware virtualization access granted."
        except Exception:
            pass

        return False, "Permission denied for /dev/kvm. Run: sudo usermod -aG kvm $USER && sudo chmod 666 /dev/kvm"

    @staticmethod
    async def install_gvisor() -> Tuple[bool, str]:
        """Downloads and installs official static gVisor (runsc) binary."""
        if shutil.which("runsc"):
            return True, "gVisor (runsc) is already installed."

        logger.info("[SandboxInstaller] Installing static gVisor (runsc) binary...")
        url = "https://storage.googleapis.com/gvisor/releases/release/latest/x86_64/runsc"

        try:
            sys_cmd = f"curl -sSL '{url}' -o /tmp/runsc && chmod +x /tmp/runsc && sudo mv /tmp/runsc /usr/local/bin/runsc"
            proc = await asyncio.create_subprocess_shell(
                sys_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()

            if shutil.which("runsc"):
                logger.info("[SandboxInstaller] gVisor (runsc) successfully installed system-wide in /usr/local/bin/runsc")
                return True, "gVisor (runsc) installed system-wide to /usr/local/bin/runsc"

            user_bin = os.path.expanduser("~/.local/bin")
            os.makedirs(user_bin, exist_ok=True)
            user_runsc = os.path.join(user_bin, "runsc")

            user_cmd = f"curl -sSL '{url}' -o '{user_runsc}' && chmod +x '{user_runsc}'"
            proc_user = await asyncio.create_subprocess_shell(
                user_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc_user.communicate()

            if os.path.exists(user_runsc):
                if user_bin not in os.environ.get("PATH", ""):
                    os.environ["PATH"] = user_bin + os.pathsep + os.environ.get("PATH", "")
                logger.info(f"[SandboxInstaller] gVisor (runsc) installed to {user_runsc}")
                return True, f"gVisor (runsc) installed locally to {user_runsc}"

            return False, "Failed to download gVisor binary."
        except Exception as e:
            logger.error(f"[SandboxInstaller] gVisor installation error: {e}")
            return False, str(e)

    @staticmethod
    async def ensure_camoufox_installed() -> Tuple[bool, str]:
        """Ensures the camoufox Python library and browser binary are fetched and ready."""
        try:
            import camoufox
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "camoufox", "fetch",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0:
                return True, "Camoufox C++ engine is ready and updated."
            return True, f"Camoufox installed (fetch notice: {stderr.decode()[:100]})"
        except ImportError:
            logger.info("[SandboxInstaller] Installing camoufox python package...")
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "pip", "install", "camoufox",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                return False, f"Failed to install camoufox via pip: {stderr.decode()}"

            proc_fetch = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "camoufox", "fetch",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc_fetch.communicate()
            return True, "Camoufox package installed and browser fetched successfully."
        except Exception as e:
            logger.error(f"[SandboxInstaller] Camoufox check error: {e}")
            return False, str(e)

    @staticmethod
    def ensure_containers_registries_conf():
        """Ensures ~/.config/containers/registries.conf exists to resolve Podman short-names."""
        if sys.platform != "linux":
            return
        conf_dir = os.path.expanduser("~/.config/containers")
        conf_path = os.path.join(conf_dir, "registries.conf")
        if not os.path.exists(conf_path):
            try:
                os.makedirs(conf_dir, exist_ok=True)
                with open(conf_path, "w", encoding="utf-8") as f:
                    f.write(
                        'unqualified-search-registries = ["docker.io", "quay.io"]\n\n'
                        '[[registry]]\n'
                        'prefix = "localhost"\n'
                        'location = "localhost"\n'
                        'insecure = true\n'
                    )
                logger.info(f"[SandboxInstaller] Created Podman registry configuration at {conf_path}")
            except Exception as e:
                logger.warning(f"[SandboxInstaller] Could not create registries.conf: {e}")

    @staticmethod
    def is_runsc_available() -> bool:
        """Checks if gVisor (runsc) OCI runtime is installed and accessible."""
        if shutil.which("runsc"):
            return True
        user_runsc = os.path.expanduser("~/.local/bin/runsc")
        sys_runsc = "/usr/local/bin/runsc"
        return (os.path.exists(user_runsc) and os.access(user_runsc, os.X_OK)) or (os.path.exists(sys_runsc) and os.access(sys_runsc, os.X_OK))
