import os
import logging
from typing import Dict, Any, List, Optional
from functools import lru_cache
import config

logger = logging.getLogger("GPUProfiles")

# GPU-specific Mesa OpenGL & GLSL Version Registry
GPU_MESA_VERSIONS: Dict[str, Dict[str, str]] = {
    "nvidia_ada": {"gl": "4.6", "glsl": "460"},
    "nvidia_ampere": {"gl": "4.6", "glsl": "460"},
    "nvidia_turing": {"gl": "4.6", "glsl": "460"},
    "nvidia_generic": {"gl": "4.6", "glsl": "460"},
    "amd_rdna3": {"gl": "4.6", "glsl": "460"},
    "amd_rdna2": {"gl": "4.6", "glsl": "460"},
    "amd_generic": {"gl": "4.6", "glsl": "460"},
    "intel_arc": {"gl": "4.6", "glsl": "460"},
    "intel_iris": {"gl": "4.6", "glsl": "460"},
    "apple_silicon": {"gl": "4.1", "glsl": "410"},
    "unknown": {"gl": "4.5", "glsl": "450"}
}

class GPUProfileManager:
    """Manages Mesa OpenGL hardware virtualization profiles, dynamic driver overrides, and Chromium CLI flags."""

    @staticmethod
    def get_preset_by_id(preset_id: str) -> Dict[str, Any]:
        """Returns the hardware preset metadata for a given preset ID with safe fallback and warning logging."""
        presets = getattr(config, "GPU_HARDWARE_PRESETS", [])
        for p in presets:
            if p.get("id") == preset_id:
                return p
        logger.warning(f"[GPUProfileManager] GPU preset '{preset_id}' not found, falling back to default preset.")
        return presets[0] if presets else {}

    @staticmethod
    def validate_profile(profile_data: Dict[str, Any]) -> bool:
        """Validates whether a profile data dictionary contains required GPU compatibility fields."""
        if not isinstance(profile_data, dict):
            logger.error("[GPUProfileManager] Profile data is not a dictionary.")
            return False
            
        required = ["os", "screen_resolution"]
        for req in required:
            if req not in profile_data:
                logger.error(f"[GPUProfileManager] Missing required profile field for GPU initialization: '{req}'")
                return False
        
        stealth = profile_data.get("stealth", {})
        if "webgl_vendor" in stealth and not stealth["webgl_vendor"]:
            logger.warning("[GPUProfileManager] Empty webgl_vendor specified in profile stealth config.")
            
        return True

    @staticmethod
    def _detect_gpu_type(webgl_vendor: str, webgl_renderer: str) -> str:
        """Detects specific GPU family and architecture generation from WebGL vendor and renderer strings."""
        combined = f"{webgl_vendor} {webgl_renderer}".upper()
        
        # NVIDIA Generations
        if "NVIDIA" in combined or "GEFORCE" in combined or "RTX" in combined or "GTX" in combined:
            if "RTX 40" in combined or "ADA" in combined:
                return "nvidia_ada"
            elif "RTX 30" in combined or "AMPERE" in combined:
                return "nvidia_ampere"
            elif "GTX" in combined or "TURING" in combined or "RTX 20" in combined:
                return "nvidia_turing"
            return "nvidia_generic"
        
        # AMD Generations
        if "AMD" in combined or "RADEON" in combined:
            if "RX 7" in combined or "RX 7000" in combined or "RDNA3" in combined:
                return "amd_rdna3"
            elif "RX 6" in combined or "RX 6000" in combined or "RDNA2" in combined:
                return "amd_rdna2"
            return "amd_generic"
        
        # Intel Generations
        if "INTEL" in combined or "IRIS" in combined or "ARC" in combined:
            if "ARC" in combined:
                return "intel_arc"
            return "intel_iris"
            
        # Apple Silicon
        if "APPLE" in combined or "M1" in combined or "M2" in combined or "M3" in combined or "METAL" in combined:
            return "apple_silicon"
        
        return "unknown"

    @staticmethod
    def _get_gpu_specific_env(gpu_type: str) -> Dict[str, str]:
        """Returns Mesa OpenGL driver environment variables tailored to specific GPU types."""
        mesa_ver = GPU_MESA_VERSIONS.get(gpu_type, GPU_MESA_VERSIONS["unknown"])
        env = {
            "MESA_GL_VERSION_OVERRIDE": mesa_ver["gl"],
            "MESA_GLSL_VERSION_OVERRIDE": mesa_ver["glsl"],
        }
        
        if gpu_type.startswith("nvidia") or gpu_type == "apple_silicon" or gpu_type == "unknown":
            env.update({
                "LIBGL_ALWAYS_SOFTWARE": "1",
                "GALLIUM_DRIVER": "llvmpipe"
            })
        elif gpu_type.startswith("amd"):
            env.update({
                "GALLIUM_DRIVER": "virgl",
            })
        elif gpu_type.startswith("intel"):
            env.update({
                "MESA_LOADER_DRIVER_OVERRIDE": "iris",
            })
            
        return env

    @staticmethod
    def _get_virtualization_env(gpu_type: str) -> Dict[str, str]:
        """Returns virtualization-specific driver environment variables."""
        base_env = {
            "MESA_GLES_VERSION_OVERRIDE": "3.2",
            "EGL_PLATFORM": "surfaceless",
            "GALLIUM_DUMP_CPU": "0",
            "GALLIUM_LOG_FILE": "/dev/null",
        }
        
        if gpu_type in ["nvidia_ampere", "nvidia_ada", "amd_rdna2", "amd_rdna3"]:
            base_env.update({
                "GALLIUM_DRIVER": "virgl",
                "VIRGL_DEBUG": "sync",
                "VIRGL_RENDERER": "gl",
            })
            
        return base_env

    @staticmethod
    def _get_performance_env(profile_data: Dict[str, Any]) -> Dict[str, str]:
        """Sets performance-related Mesa environment variables based on profile settings."""
        perf_mode = profile_data.get("performance_mode", "balanced").lower()
        env = {}
        if perf_mode == "high":
            env.update({
                "MESA_SHADER_CACHE_MAX_SIZE": "1G",
                "MESA_SHADER_CACHE_DIR": "/tmp/mesa_cache",
                "GALLIUM_HUD": "off",
                "MESA_GL_THREAD_SAFETY": "1",
            })
        elif perf_mode == "low":
            env.update({
                "MESA_SHADER_CACHE_MAX_SIZE": "128M",
                "MESA_NO_ERROR": "1",
                "GALLIUM_HUD": "off",
            })
        return env

    @staticmethod
    def _get_display_env() -> Dict[str, str]:
        """Detects intelligent X11 or Wayland display environment."""
        env = {}
        if os.path.exists("/run/user/1000"):
            env.update({
                "XDG_RUNTIME_DIR": "/run/user/1000",
                "WAYLAND_DISPLAY": "wayland-0",
                "DISPLAY": os.environ.get("DISPLAY", ":99")
            })
        else:
            env.update({
                "DISPLAY": os.environ.get("DISPLAY", ":99")
            })
            
        env.update({
            "LIBGL_DEBUG": "quiet",
            "MESA_DEBUG": "quiet",
        })
        return env

    @staticmethod
    def _get_container_env() -> Dict[str, str]:
        """Detects OCI container environments (Docker/Podman) and applies necessary software GL overrides."""
        env = {}
        if os.path.exists("/.dockerenv") or os.path.exists("/run/.containerenv"):
            env.update({
                "MESA_LOADER_DRIVER_OVERRIDE": "llvmpipe",
                "LIBGL_ALWAYS_SOFTWARE": "1",
                "GALLIUM_DRIVER": "llvmpipe",
            })
        return env

    @staticmethod
    def _get_safe_default_env() -> Dict[str, str]:
        """Fallback environment dictionary when profile validation fails."""
        return {
            "DISPLAY": os.environ.get("DISPLAY", ":99"),
            "LIBGL_ALWAYS_SOFTWARE": "1",
            "GALLIUM_DRIVER": "llvmpipe",
            "MESA_GL_VERSION_OVERRIDE": "4.5",
            "LIBGL_DEBUG": "quiet"
        }

    @staticmethod
    def build_mesa_env(profile_data: Dict[str, Any]) -> Dict[str, str]:
        """Generates environment variables for Mesa / virgl / LLVMpipe dynamically matched to profile settings."""
        if not GPUProfileManager.validate_profile(profile_data):
            logger.warning("[GPUProfileManager] Invalid profile data provided, returning safe default Mesa environment.")
            return GPUProfileManager._get_safe_default_env()

        stealth_cfg = profile_data.get("stealth", {})
        webgl_vendor = str(stealth_cfg.get("webgl_vendor", "")).strip()
        webgl_renderer = str(stealth_cfg.get("webgl_renderer", "")).strip()
        
        gpu_type = GPUProfileManager._detect_gpu_type(webgl_vendor, webgl_renderer)
        
        # Assemble environment pipeline
        env = {}
        env.update(GPUProfileManager._get_display_env())
        env.update(GPUProfileManager._get_gpu_specific_env(gpu_type))
        
        # Virtualization overrides if explicitly requested or containerized
        sandbox_cfg = profile_data.get("sandbox", {})
        if sandbox_cfg.get("mode") in ["container", "microvm"]:
            env.update(GPUProfileManager._get_virtualization_env(gpu_type))
            
        env.update(GPUProfileManager._get_performance_env(profile_data))
        env.update(GPUProfileManager._get_container_env())
        
        # Manual graphics_driver override if set in profile
        driver_override = sandbox_cfg.get("graphics_driver")
        if driver_override and driver_override != "auto":
            env["GALLIUM_DRIVER"] = driver_override

        logger.info(f"[GPUProfileManager] GPU environment built successfully: type='{gpu_type}', GALLIUM_DRIVER='{env.get('GALLIUM_DRIVER', 'auto')}' ({len(env)} vars)")
        return env

    @staticmethod
    def get_chromium_gpu_flags(profile_data: Dict[str, Any]) -> List[str]:
        """Generates CLI flags to pass to Chromium dynamically matched to detected GPU type and display resolution."""
        stealth_cfg = profile_data.get("stealth", {})
        webgl_vendor = str(stealth_cfg.get("webgl_vendor", "Google Inc. (NVIDIA)")).strip()
        webgl_renderer = str(stealth_cfg.get("webgl_renderer", "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)")).strip()

        gpu_type = GPUProfileManager._detect_gpu_type(webgl_vendor, webgl_renderer)

        base_flags = [
            "--ignore-gpu-blocklist",
            "--enable-gpu-rasterization",
            "--enable-zero-copy",
            "--enable-features=UseOzonePlatform",
            "--ozone-platform=wayland,x11",
        ]

        target_os = str(profile_data.get("os", "windows")).lower()

        if target_os == "linux":
            gpu_flags = {
                "nvidia_ada": [
                    "--use-gl=desktop",
                    "--enable-webgl-developer-extensions",
                    "--disable-gpu-driver-bug-workarounds",
                    "--enable-features=Vulkan",
                ],
                "nvidia_ampere": [
                    "--use-gl=desktop",
                    "--enable-webgl-developer-extensions",
                    "--disable-gpu-driver-bug-workarounds",
                    "--enable-features=Vulkan",
                ],
                "nvidia_turing": [
                    "--use-gl=desktop",
                    "--enable-webgl-developer-extensions",
                ],
                "nvidia_generic": [
                    "--use-gl=desktop",
                    "--enable-webgl-developer-extensions",
                ],
                "amd_rdna3": [
                    "--use-gl=egl",
                    "--use-angle=vulkan",
                    "--enable-features=Vulkan,WebGPUSupport",
                ],
                "amd_rdna2": [
                    "--use-gl=egl",
                    "--use-angle=vulkan",
                    "--enable-features=Vulkan,WebGPUSupport",
                ],
                "amd_generic": [
                    "--use-gl=egl",
                    "--use-angle=vulkan",
                ],
                "intel_arc": [
                    "--use-gl=egl",
                    "--disable-gpu-driver-bug-workarounds",
                ],
                "intel_iris": [
                    "--use-gl=egl",
                    "--disable-gpu-driver-bug-workarounds",
                ],
                "apple_silicon": [
                    "--use-gl=desktop",
                    "--enable-features=UseSkiaRenderer",
                ],
            }
        else:
            gpu_flags = {
                "nvidia_ada": [
                    "--use-gl=angle",
                    "--use-angle=gl",
                    "--enable-webgl-developer-extensions",
                    "--disable-gpu-driver-bug-workarounds",
                    "--enable-features=Vulkan",
                ],
                "nvidia_ampere": [
                    "--use-gl=angle",
                    "--use-angle=gl",
                    "--enable-webgl-developer-extensions",
                    "--disable-gpu-driver-bug-workarounds",
                    "--enable-features=Vulkan",
                ],
                "nvidia_turing": [
                    "--use-gl=angle",
                    "--use-angle=gl",
                    "--enable-webgl-developer-extensions",
                ],
                "nvidia_generic": [
                    "--use-gl=angle",
                    "--use-angle=gl",
                    "--enable-webgl-developer-extensions",
                ],
                "amd_rdna3": [
                    "--use-gl=egl",
                    "--use-angle=vulkan",
                    "--enable-features=Vulkan,WebGPUSupport",
                ],
                "amd_rdna2": [
                    "--use-gl=egl",
                    "--use-angle=vulkan",
                    "--enable-features=Vulkan,WebGPUSupport",
                ],
                "amd_generic": [
                    "--use-gl=egl",
                    "--use-angle=vulkan",
                ],
                "intel_arc": [
                    "--use-gl=angle",
                    "--use-angle=gl",
                    "--disable-gpu-driver-bug-workarounds",
                ],
                "intel_iris": [
                    "--use-gl=angle",
                    "--use-angle=gl",
                    "--disable-gpu-driver-bug-workarounds",
                ],
                "apple_silicon": [
                    "--use-gl=desktop",
                    "--enable-features=UseSkiaRenderer",
                ],
            }

        flags = base_flags + gpu_flags.get(gpu_type, [
            "--use-gl=angle",
            "--use-angle=swiftshader",
        ])

        # Native vendor & renderer CLI parameters
        flags.extend([
            f"--gl-vendor={webgl_vendor}",
            f"--gl-renderer={webgl_renderer}",
        ])

        # Resolution scaling factor rules
        screen_res = str(profile_data.get("screen_resolution", "1920x1080"))
        if "4K" in screen_res or "3840x2160" in screen_res:
            flags.append("--force-device-scale-factor=2")

        return flags
