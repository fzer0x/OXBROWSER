import os
import sys
import shutil
import asyncio
import logging
import subprocess
import socket
from typing import Dict, Tuple, Optional, Any, List
import config
from engine.sandbox.sandbox_base import BaseSandbox
from engine.sandbox.gpu_profiles import GPUProfileManager

logger = logging.getLogger("ContainerSandbox")


def check_cmd_available(cmd: str) -> bool:
    if shutil.which(cmd):
        return True
    for p in [os.path.expanduser(f"~/.local/bin/{cmd}"), f"/usr/local/bin/{cmd}"]:
        if os.path.exists(p) and os.access(p, os.X_OK):
            return True
    return False


class ContainerSandbox(BaseSandbox):
    """Manages containerized OCI isolation (Docker/Podman) or isolated process namespace with Xvfb & Mesa GL."""

    def __init__(self, profile_id: str, profile_data: Dict[str, Any], user_data_dir: str, debug_port: int):
        super().__init__(profile_id, profile_data, user_data_dir, debug_port)
        self.process: Optional[subprocess.Popen] = None
        self.xvfb_process: Optional[subprocess.Popen] = None
        self.display_num: Optional[str] = None
        self.runtime_cmd: Optional[str] = None
        self.log_buffer: List[str] = []

    async def start(self) -> Tuple[bool, str, int]:
        sandbox_cfg = self.profile_data.get("sandbox", {})
        gpu_preset = sandbox_cfg.get("gpu_preset", "nvidia_rtx3060")
        sandbox_mode = str(sandbox_cfg.get("mode", "container")).lower().strip()

        # Determine runtime: Docker, Podman, or Isolated Host Process Sandbox with Mesa & Xvfb
        if sandbox_mode == "off":
            self.runtime_cmd = None
            self.is_active = True
            logger.info(f"[ContainerSandbox] Sandbox mode 'off' for '{self.profile_id}'. Using standard uncontainerized process.")
            return True, "Standard process sandbox (uncontainerized)", self.debug_port

        engine_type = str(self.profile_data.get("engine", "playwright")).lower().strip()
        if engine_type == "camoufox":
            self.runtime_cmd = None
            self.is_active = True
            logger.info(f"[ContainerSandbox] Camoufox engine selected for '{self.profile_id}'. Using native C++ engine sandbox.")
            return True, "Camoufox native process sandbox", self.debug_port

        if check_cmd_available("podman"):
            self.runtime_cmd = "podman"
        elif check_cmd_available("docker"):
            self.runtime_cmd = "docker"
        else:
            self.runtime_cmd = None

        logger.info(f"[ContainerSandbox] Initializing sandbox for profile '{self.profile_id}' (runtime: {self.runtime_cmd or 'isolated-xvfb-process'}, gpu: {gpu_preset})")

        # Allocate virtual display number if using Xvfb
        display_id = (hash(self.profile_id) % 800) + 100
        self.display_num = f":{display_id}"

        # If container binary is present, attempt container spawn
        if self.runtime_cmd:
            success, msg = await self._start_container()
            if success:
                self.is_active = True
                return True, f"Container sandbox launched via {self.runtime_cmd}", self.debug_port
            logger.warning(f"[ContainerSandbox] Container launch failed ({msg}). Falling back to isolated process sandbox with Xvfb & Mesa.")

        # Fallback to isolated process sandbox with virtual frame buffer & Mesa driver overrides
        success, msg = await self._start_isolated_process()
        if success:
            self.is_active = True
            return True, "Isolated process sandbox launched with Mesa GL virtualization", self.debug_port
        
        return False, f"Failed to launch sandbox: {msg}", self.debug_port

    async def _start_isolated_process(self) -> Tuple[bool, str]:
        """Launches Chromium in an isolated Xvfb frame buffer with Mesa environment variables."""
        try:
            sandbox_mode = str(self.profile_data.get("sandbox", {}).get("mode", "container")).lower().strip()
            engine_type = str(self.profile_data.get("engine", "playwright")).lower().strip()
            if sandbox_mode == "off" or engine_type == "camoufox":
                return True, "Success"
            # 1. Start Xvfb virtual display if available and sandbox mode is enabled
            res_str = self.profile_data.get("screen_resolution", "1920x1080")
            sandbox_mode = str(self.profile_data.get("sandbox", {}).get("mode", "container")).lower().strip()
            engine_type = str(self.profile_data.get("engine", "playwright")).lower().strip()

            if not sys.platform.startswith("win") and check_cmd_available("Xvfb") and self.display_num and sandbox_mode != "off" and engine_type != "camoufox":
                xvfb_cmd: List[str] = ["Xvfb", self.display_num, "-screen", "0", f"{res_str}x24", "-ac"]
                self.xvfb_process = subprocess.Popen(
                    xvfb_cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                await asyncio.sleep(0.3)
                logger.info(f"[ContainerSandbox] Started Xvfb virtual display {self.display_num}")

            # 2. Build Mesa GPU environment variables (Linux only)
            env = os.environ.copy()
            if not sys.platform.startswith("win") and sandbox_mode != "off" and engine_type != "camoufox":
                mesa_env = GPUProfileManager.build_mesa_env(self.profile_data)
                env.update(mesa_env)
                if self.display_num:
                    env["DISPLAY"] = self.display_num

            # 3. Chromium Command Line Arguments
            chrome_bin = self._find_chromium_binary()
            if not chrome_bin:
                return False, "Chromium binary not found on host."

            gpu_flags = GPUProfileManager.get_chromium_gpu_flags(self.profile_data)
            cmd: List[str] = [
                chrome_bin,
                f"--user-data-dir={self.user_data_dir}",
                f"--remote-debugging-port={self.debug_port}",
                f"--window-size={res_str.replace('x', ',')}",
                "--no-first-run",
                "--no-default-browser-check",
                "--no-sandbox",
                "--test-type",
                "--disable-infobars",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ] + gpu_flags

            self.process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Allow process to start up
            await asyncio.sleep(0.5)
            if self.process.poll() is not None:
                _, err = self.process.communicate()
                return False, f"Chromium process exited immediately: {err}"

            return True, "Success"
        except Exception as e:
            logger.error(f"[ContainerSandbox] Process launch exception: {e}")
            return False, str(e)

    async def _start_container(self) -> Tuple[bool, str]:
        """Launches Chromium inside a Docker or Podman OCI container."""
        if not self.runtime_cmd:
            return False, "No container runtime command available."

        try:
            runtime = self.runtime_cmd
            container_name = f"soxbot_sandbox_{self.profile_id[:8]}"
            res_str = self.profile_data.get("screen_resolution", "1920x1080")
            sandbox_cfg = self.profile_data.get("sandbox", {})
            mesa_env = GPUProfileManager.build_mesa_env(self.profile_data)

            from engine.sandbox.sandbox_installer import SandboxInstaller
            SandboxInstaller.ensure_containers_registries_conf()

            # Build run command
            cmd: List[str] = [
                runtime, "run", "-d",
                "--name", container_name,
                "--rm",
                "-p", f"127.0.0.1:{self.debug_port}:{self.debug_port}",
                "-v", f"{self.user_data_dir}:/data/user_data:Z",
            ]

            # Enable gVisor (runsc) syscall sandbox if requested/available
            oci_runtime = sandbox_cfg.get("oci_runtime", "auto")
            if (oci_runtime == "runsc" or sandbox_cfg.get("gvisor", False)) and SandboxInstaller.is_runsc_available():
                runsc_path = shutil.which("runsc") or os.path.expanduser("~/.local/bin/runsc")
                cmd.extend(["--runtime", runsc_path, "--runtime-flag=ignore-cgroups"])
                logger.info(f"[ContainerSandbox] Activated gVisor (runsc) Kernel Syscall Sandbox at '{runsc_path}' for profile '{self.profile_id}'")

            # Pass environment variables
            for k, v in mesa_env.items():
                cmd.extend(["-e", f"{k}={v}"])

            # Pass GPU device if native pass-through requested
            if sandbox_cfg.get("gpu_preset") == "native_passthrough" and os.path.exists("/dev/dri"):
                cmd.extend(["--device", "/dev/dri"])

            image = getattr(config, "SANDBOX_CONTAINER_IMAGE", "localhost/soxbot-browser-sandbox:latest")
            cmd.append(image)

            logger.info(f"[ContainerSandbox] Executing container command: {' '.join(cmd)}")
            proc = await asyncio.create_subprocess_exec(
                cmd[0], *cmd[1:],
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode == 0:
                self.container_or_vm_id = stdout.decode().strip()
                return True, f"Container ID: {self.container_or_vm_id}"
            else:
                return False, stderr.decode().strip()
        except Exception as e:
            return False, str(e)

    def _find_chromium_binary(self) -> Optional[str]:
        """Finds system Chromium or local downloaded Chrome binary across Windows and Linux."""
        from engine.platform_helper import PlatformHelper
        return PlatformHelper.find_chromium_binary(config.BASE_DIR)

    async def stop(self) -> bool:
        """Stops the sandbox container or process and cleans up virtual framebuffers."""
        logger.info(f"[ContainerSandbox] Stopping sandbox for profile '{self.profile_id}'")
        
        # Stop OCI container if active
        if self.runtime_cmd and self.container_or_vm_id:
            try:
                cmd = [self.runtime_cmd, "stop", f"soxbot_sandbox_{self.profile_id[:8]}"]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            except Exception as e:
                logger.warning(f"Error stopping container: {e}")

        # Stop local subprocess if active
        if self.process:
            try:
                self.process.terminate()
                await asyncio.sleep(0.2)
                if self.process.poll() is None:
                    self.process.kill()
            except Exception:
                pass
            self.process = None

        # Stop Xvfb virtual display if active
        if self.xvfb_process:
            try:
                self.xvfb_process.terminate()
                if self.xvfb_process.poll() is None:
                    self.xvfb_process.kill()
            except Exception:
                pass
            self.xvfb_process = None

        self.is_active = False
        return True

    async def is_running(self) -> bool:
        if self.process:
            return self.process.poll() is None
        if self.runtime_cmd and self.container_or_vm_id:
            try:
                res = subprocess.run(
                    [self.runtime_cmd, "ps", "-q", "-f", f"id={self.container_or_vm_id}"],
                    capture_output=True, text=True
                )
                return bool(res.stdout.strip())
            except Exception:
                return False
        return self.is_active

    async def get_logs(self) -> str:
        if self.process and self.process.stdout:
            try:
                return self.process.stdout.read() or ""
            except Exception:
                pass
        return "\n".join(self.log_buffer)
