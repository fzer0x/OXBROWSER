import hashlib
import json
import random
import logging
from typing import Dict, List, Optional, Any, Union
from engine.cdp_patcher import CDPRestrictionMitigator

logger = logging.getLogger("FingerprintGenerator")

class FingerprintGenerator:
    """Generates modular, high-stealth fingerprint scripts for Chromium CDP Page.addScriptToEvaluateOnNewDocument."""

    @staticmethod
    def generate_stealth_script(profile: Dict[str, Any], target_timezone: str = "UTC") -> str:
        stealth_cfg = profile.get("stealth", {})
        profile_id = profile.get("id", "default_profile")
        
        # Screen parameters
        res_str = profile.get("screen_resolution", "1920x1080")
        try:
            width, height = map(int, res_str.split("x"))
        except ValueError:
            width, height = 1920, 1080
            
        avail_width = width
        avail_height = height - 40  # subtract taskbar height
        
        hardware_concurrency = profile.get("hardware_concurrency", 8)
        device_memory = profile.get("device_memory", 8)
        color_depth = profile.get("color_depth", 24)
        max_touch_points = profile.get("max_touch_points", 0)
        dnt_val = profile.get("do_not_track", "null")
        
        raw_webgl_vendor = str(stealth_cfg.get("webgl_vendor", "Google Inc. (NVIDIA)")).strip()
        raw_webgl_renderer = str(stealth_cfg.get("webgl_renderer", "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)")).strip()
        
        # Senior Level OS Alignment for WebGL Vendor & Renderer Strings
        target_os_clean = profile.get("os", "windows").lower()
        if target_os_clean == "mac":
            webgl_vendor = raw_webgl_vendor if "APPLE" in raw_webgl_vendor.upper() else "Google Inc. (Apple)"
            webgl_renderer = raw_webgl_renderer if "METAL" in raw_webgl_renderer.upper() else "ANGLE (Apple, ANGLE Metal Renderer: Apple M1, Unspecified Version)"
        elif target_os_clean == "windows":
            if "AMD" in raw_webgl_vendor.upper() or "RADEON" in raw_webgl_renderer.upper():
                webgl_vendor = raw_webgl_vendor if "AMD" in raw_webgl_vendor.upper() else "Google Inc. (AMD)"
                webgl_renderer = raw_webgl_renderer if "DIRECT3D11" in raw_webgl_renderer.upper() else f"ANGLE (AMD, {raw_webgl_renderer} Direct3D11 vs_5_0 ps_5_0, D3D11)"
            elif "INTEL" in raw_webgl_vendor.upper() or "IRIS" in raw_webgl_renderer.upper():
                webgl_vendor = raw_webgl_vendor if "INTEL" in raw_webgl_vendor.upper() else "Google Inc. (Intel)"
                webgl_renderer = raw_webgl_renderer if "DIRECT3D11" in raw_webgl_renderer.upper() else f"ANGLE (Intel, {raw_webgl_renderer} Direct3D11 vs_5_0 ps_5_0, D3D11)"
            else:
                webgl_vendor = raw_webgl_vendor if "NVIDIA" in raw_webgl_vendor.upper() else "Google Inc. (NVIDIA)"
                webgl_renderer = raw_webgl_renderer if "DIRECT3D11" in raw_webgl_renderer.upper() else f"ANGLE (NVIDIA, {raw_webgl_renderer} Direct3D11 vs_5_0 ps_5_0, D3D11)"
        elif target_os_clean == "linux":
            if "NVIDIA" in raw_webgl_vendor.upper() or "GEFORCE" in raw_webgl_renderer.upper() or "RTX" in raw_webgl_renderer.upper() or "GTX" in raw_webgl_renderer.upper():
                webgl_vendor = "NVIDIA Corporation"
                clean_rend = raw_webgl_renderer.replace("ANGLE (NVIDIA, ", "").replace("Direct3D11 vs_5_0 ps_5_0, D3D11)", "").replace("Direct3D11", "").strip(", ")
                if not clean_rend or "NVIDIA" not in clean_rend:
                    clean_rend = "NVIDIA GeForce RTX 3060/PCIe/SSE2"
                elif not clean_rend.endswith("/PCIe/SSE2") and ("RTX" in clean_rend or "GTX" in clean_rend or "GEFORCE" in clean_rend.upper()):
                    if not clean_rend.endswith("/PCIe/SSE2"):
                        clean_rend = f"{clean_rend}/PCIe/SSE2"
                webgl_renderer = clean_rend
            elif "MESA" in raw_webgl_vendor.upper() or "MESA DRI" in raw_webgl_renderer.upper():
                webgl_vendor = raw_webgl_vendor if raw_webgl_vendor else "Mesa/X.org"
                webgl_renderer = raw_webgl_renderer if raw_webgl_renderer else "Mesa DRI AMD Radeon Graphics (RENOIR, DRM 3.35.0, 5.15.0-76-generic, LLVM 15.0.7)"
            elif "AMD" in raw_webgl_vendor.upper() or "RADEON" in raw_webgl_renderer.upper():
                webgl_vendor = "AMD" if "MESA" not in raw_webgl_vendor.upper() else "Mesa/X.org"
                webgl_renderer = raw_webgl_renderer if ("RADV" in raw_webgl_renderer or "Mesa DRI" in raw_webgl_renderer) else "Mesa DRI AMD Radeon Graphics (RENOIR, DRM 3.35.0, 5.15.0-76-generic, LLVM 15.0.7)"
            elif "INTEL" in raw_webgl_vendor.upper() or "IRIS" in raw_webgl_renderer.upper():
                webgl_vendor = "Mesa/X.org"
                webgl_renderer = raw_webgl_renderer if "Mesa" in raw_webgl_renderer else "Mesa Intel(R) Iris(R) Xe Graphics (TGL GT2)"
            elif "LLVMPIPE" in raw_webgl_renderer.upper():
                webgl_vendor = "Mesa"
                webgl_renderer = "llvmpipe (LLVM 18.1.8, 256 bits)"
            else:
                webgl_vendor = raw_webgl_vendor
                webgl_renderer = raw_webgl_renderer
        else:
            webgl_vendor = raw_webgl_vendor
            webgl_renderer = raw_webgl_renderer

        webgpu_supported = stealth_cfg.get("webgpu_supported", False)
        canvas_noise = stealth_cfg.get("canvas_noise", True)
        audio_noise = stealth_cfg.get("audio_noise", True)
        webrtc_mode = stealth_cfg.get("webrtc_mode", "altered")
        client_rects_noise = stealth_cfg.get("client_rects_noise", True)
        font_noise = stealth_cfg.get("font_fingerprint_noise", True)
        custom_patches = stealth_cfg.get("custom_patches", [])
        
        # WebGL Spoofing Mode (spoof vs real/native/off)
        webgl_mode = str(stealth_cfg.get("webgl_mode", "spoof")).lower()
        if "webgl_spoofing" in stealth_cfg:
            enable_webgl_spoof = bool(stealth_cfg["webgl_spoofing"])
        else:
            enable_webgl_spoof = webgl_mode not in ["off", "real", "disabled", "unspoofed"]

        # Deterministic noise seed derived from customizable noise_seed or profile ID
        seed_str = str(stealth_cfg.get("noise_seed") or profile_id).strip()
        seed_hash = hashlib.md5(seed_str.encode('utf-8')).hexdigest()
        seed_int = int(seed_hash[:8], 16)
        rng = random.Random(seed_int)
        noise_seed = rng.uniform(0.0001, 0.0099)

        # Language & Locale parsing
        lang_raw = profile.get("language", "en-US,en")
        lang_parts = [p.split(";")[0].strip() for p in lang_raw.split(",") if p.strip()]
        primary_locale = lang_parts[0] if lang_parts else "en-US"
        langs_list = lang_parts if lang_parts else ["en-US", "en"]
        langs_list_json = json.dumps(langs_list)

        target_os = profile.get("os", "windows").lower()
        is_mobile = target_os in ["android", "ios"] or profile.get("is_mobile", False)
        
        if target_os == "mac":
            nav_platform = "MacIntel"
            nav_app_version = "5.0 (Macintosh; Intel Mac OS X 10_15_7)"
            ua_os = "macOS"
            os_ver = "14.4.1"
        elif target_os == "linux":
            nav_platform = "Linux x86_64"
            nav_app_version = "5.0 (X11; Linux x86_64)"
            ua_os = "Linux"
            os_ver = "6.5.0"
        elif target_os == "android":
            nav_platform = "Linux armv8l"
            nav_app_version = "5.0 (Linux; Android 14; Mobile)"
            ua_os = "Android"
            os_ver = "14.0.0"
        elif target_os == "ios":
            nav_platform = "iPhone"
            nav_app_version = "5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X)"
            ua_os = "iOS"
            os_ver = "17.4"
        else:
            nav_platform = "Win32"
            nav_app_version = "5.0 (Windows NT 10.0; Win64; x64)"
            ua_os = "Windows"
            os_ver = "15.0.0"

        # Synthetic Media Devices IDs
        audio_in_id = hashlib.md5(f"{profile_id}_mic".encode()).hexdigest()
        audio_out_id = hashlib.md5(f"{profile_id}_speaker".encode()).hexdigest()
        video_in_id = hashlib.md5(f"{profile_id}_cam".encode()).hexdigest()

        # Target Spoofed WebRTC IP from Proxy if available
        target_webrtc_ip = ""
        proxy_cfg = profile.get("proxy", {})
        proxy_info = profile.get("proxy_info", {})
        if proxy_cfg and isinstance(proxy_cfg, dict) and proxy_cfg.get("enabled"):
            target_webrtc_ip = str((proxy_info or {}).get("ip") or proxy_cfg.get("host") or "").strip()
            if target_webrtc_ip in ["127.0.0.1", "localhost", "0.0.0.0"]:
                target_webrtc_ip = ""

        beh = profile.get("behavior", {})
        drm_enabled = beh.get("drm_widevine", True)
        is_camoufox = str(profile.get("engine", "camoufox")).lower() in ["camoufox", "firefox"]

        try:
            parts = [
                FingerprintGenerator._generate_native_infrastructure(),
                CDPRestrictionMitigator.generate_cdp_leak_protection_script(),
                FingerprintGenerator._generate_navigator_defaults(
                    nav_platform, nav_app_version, primary_locale, langs_list_json,
                    hardware_concurrency, device_memory, max_touch_points, dnt_val,
                    ua_os, os_ver, is_mobile
                ),
                FingerprintGenerator._generate_intl_timezone_patch(primary_locale, target_timezone),
                FingerprintGenerator._generate_screen_patch(width, height, avail_width, avail_height, color_depth),
                FingerprintGenerator._generate_webgl_patch(webgl_vendor, webgl_renderer, target_os_clean) if enable_webgl_spoof else "// WebGL Spoofing Disabled (100% Real Native GPU Passthrough)",
                FingerprintGenerator._generate_canvas_noise_patch(canvas_noise, noise_seed),
                FingerprintGenerator._generate_font_rects_noise_patch(font_noise, client_rects_noise, noise_seed),
                FingerprintGenerator._generate_audio_noise_patch(audio_noise, noise_seed, is_camoufox=is_camoufox),
                FingerprintGenerator._generate_synthetic_media_devices(audio_in_id, audio_out_id, video_in_id),
                FingerprintGenerator._generate_speech_synthesis_patch(target_os_clean, primary_locale),
                FingerprintGenerator._generate_permissions_patch(),
                FingerprintGenerator._generate_network_battery_patch(),
                FingerprintGenerator._generate_sensor_patch(is_mobile),
                FingerprintGenerator._generate_webgpu_patch(webgpu_supported, webgl_vendor, webgl_renderer, target_os_clean),
                FingerprintGenerator._generate_drm_eme_patch(drm_enabled, target_os_clean),
                FingerprintGenerator._generate_worker_patch(
                    nav_platform, nav_app_version, primary_locale, langs_list_json,
                    hardware_concurrency, device_memory, webgl_vendor, webgl_renderer, target_os_clean,
                    enable_webgl_spoof=enable_webgl_spoof
                ),
                FingerprintGenerator._generate_webrtc_patch(webrtc_mode, target_webrtc_ip)
            ]

            # Append custom patches if provided
            if custom_patches and isinstance(custom_patches, list):
                for patch in custom_patches:
                    if isinstance(patch, str) and patch.strip():
                        parts.append(f"// Custom User Patch\ntry {{ {patch} }} catch(e) {{ console.debug('Custom patch error:', e); }}")

            return "(function() {\n'use strict';\n" + "\n".join(parts) + "\n})();"
        except Exception as e:
            logger.error(f"Failed to generate stealth script for profile {profile_id}: {e}")
            return "// Stealth script generation fallback\n(function() {})();"

    @staticmethod
    def _generate_native_infrastructure() -> str:
        return """
        // 0. Memory-Safe Native Function toString Masking Infrastructure
        const nativeToStringMap = new WeakMap();
        const origFunctionToString = Function.prototype.toString;

        if (typeof FinalizationRegistry !== 'undefined') {
            try {
                new FinalizationRegistry((heldItem) => {
                    // Optional gc cleanup hook
                });
            } catch(e) {}
        }

        const makeNative = function(fn, name, length) {
            if (typeof fn !== 'function') return fn;
            const fnName = name || fn.name || '';
            try {
                nativeToStringMap.set(fn, `function ${fnName}() { [native code] }`);
            } catch(e) {}
            if (typeof length === 'number') {
                try {
                    Object.defineProperty(fn, 'length', { value: length, configurable: true });
                } catch(e) {}
            }
            try {
                Object.defineProperty(fn, 'name', { value: fnName, configurable: true });
            } catch(e) {}
            return fn;
        };

        Function.prototype.toString = makeNative(function toString() {
            if (typeof this !== 'function') {
                throw new TypeError('Function.prototype.toString requires that "this" be a Function.');
            }
            if (nativeToStringMap.has(this)) {
                return nativeToStringMap.get(this);
            }
            return origFunctionToString.apply(this, arguments);
        }, 'toString', 0);
        """

    @staticmethod
    def _generate_navigator_defaults(
        nav_platform: str, nav_app_version: str, primary_locale: str, langs_list_json: str,
        hardware_concurrency: int, device_memory: int, max_touch_points: int, dnt_val: str,
        ua_os: str, os_ver: str, is_mobile: bool
    ) -> str:
        return f"""
        // 1. Navigator Prototype Properties & Client Hints
        try {{
            const navProto = Object.getPrototypeOf(navigator) || Navigator.prototype;
            Object.defineProperty(navProto, 'webdriver', {{ get: makeNative(() => false, 'get webdriver'), configurable: true, enumerable: true }});
            Object.defineProperty(navProto, 'oscpu', {{ get: makeNative(() => undefined, 'get oscpu'), configurable: true, enumerable: true }});
            Object.defineProperty(navProto, 'platform', {{ get: makeNative(() => "{nav_platform}", 'get platform'), configurable: true, enumerable: true }});
            Object.defineProperty(navProto, 'appVersion', {{ get: makeNative(() => "{nav_app_version}", 'get appVersion'), configurable: true, enumerable: true }});
            Object.defineProperty(navProto, 'language', {{ get: makeNative(() => "{primary_locale}", 'get language'), configurable: true, enumerable: true }});
            Object.defineProperty(navProto, 'languages', {{ get: makeNative(() => Object.freeze({langs_list_json}), 'get languages'), configurable: true, enumerable: true }});
            Object.defineProperty(navProto, 'hardwareConcurrency', {{ get: makeNative(() => {hardware_concurrency}, 'get hardwareConcurrency'), configurable: true, enumerable: true }});
            Object.defineProperty(navProto, 'deviceMemory', {{ get: makeNative(() => {device_memory}, 'get deviceMemory'), configurable: true, enumerable: true }});
            Object.defineProperty(navProto, 'maxTouchPoints', {{ get: makeNative(() => {max_touch_points}, 'get maxTouchPoints'), configurable: true, enumerable: true }});
            
            const dntValue = {f'"{dnt_val}"' if dnt_val != "null" else "null"};
            Object.defineProperty(navProto, 'doNotTrack', {{ get: makeNative(() => dntValue, 'get doNotTrack'), configurable: true, enumerable: true }});
        }} catch(e) {{ console.debug('Navigator patch error:', e); }}

        if (navigator.userAgentData) {{
            try {{
                const origGetHighEntropyValues = navigator.userAgentData.getHighEntropyValues;
                Object.defineProperty(navigator.userAgentData, 'platform', {{ get: makeNative(() => "{ua_os}", 'get platform'), configurable: true, enumerable: true }});
                
                navigator.userAgentData.getHighEntropyValues = makeNative(function getHighEntropyValues(hints) {{
                    return origGetHighEntropyValues.apply(this, arguments).then(res => {{
                        res.platform = "{ua_os}";
                        res.platformVersion = "{os_ver}";
                        res.architecture = "{'arm' if is_mobile or ua_os == 'macOS' else 'x86'}";
                        res.bitness = "64";
                        res.mobile = {str(is_mobile).lower()};
                        res.model = "{'Pixel 8' if ua_os == 'Android' else ('iPhone' if ua_os == 'iOS' else '')}";
                        res.wow64 = false;
                        return res;
                    }});
                }}, 'getHighEntropyValues');
            }} catch(e) {{ console.debug('UserAgentData patch error:', e); }}
        }}
        """

    @staticmethod
    def _generate_intl_timezone_patch(primary_locale: str, target_timezone: str) -> str:
        return f"""
        // 2. Intl API Locale & Timezone Alignment
        try {{
            const targetLocale = "{primary_locale}";
            const targetTz = "{target_timezone}";

            const intlClasses = [
                'DateTimeFormat', 'NumberFormat', 'Collator', 'PluralRules',
                'RelativeTimeFormat', 'DisplayNames', 'Segmenter', 'ListFormat'
            ];

            intlClasses.forEach(name => {{
                if (Intl[name]) {{
                    const Orig = Intl[name];
                    const Patched = makeNative(function(locales, options) {{
                        const loc = locales || targetLocale;
                        let opts = options;
                        if (name === 'DateTimeFormat') {{
                            opts = Object.assign({{}}, options, {{ timeZone: targetTz }});
                        }}
                        return new Orig(loc, opts);
                    }}, name);
                    Patched.prototype = Orig.prototype;

                    const origResolved = Orig.prototype.resolvedOptions;
                    if (origResolved) {{
                        Orig.prototype.resolvedOptions = makeNative(function resolvedOptions() {{
                            const res = origResolved.apply(this, arguments);
                            res.locale = targetLocale;
                            if (name === 'DateTimeFormat') {{
                                res.timeZone = targetTz;
                            }}
                            return res;
                        }}, 'resolvedOptions');
                    }}
                    Intl[name] = Patched;
                }}
            }});

            const origGetTimezoneOffset = Date.prototype.getTimezoneOffset;
            Date.prototype.getTimezoneOffset = makeNative(function getTimezoneOffset() {{
                try {{
                    const str = this.toLocaleString('en-US', {{ timeZone: targetTz, timeZoneName: 'shortOffset' }});
                    const m = str.match(/GMT([+-])(\\d+)(?::(\\d+))?/);
                    if (!m) return origGetTimezoneOffset.apply(this, arguments);
                    const sign = m[1] === '+' ? -1 : 1;
                    const hours = parseInt(m[2], 10);
                    const mins = parseInt(m[3] || '0', 10);
                    return sign * (hours * 60 + mins);
                }} catch (e) {{
                    return origGetTimezoneOffset.apply(this, arguments);
                }}
            }}, 'getTimezoneOffset');
        }} catch(e) {{ console.debug('Intl patch error:', e); }}
        """

    @staticmethod
    def _generate_screen_patch(width: int, height: int, avail_width: int, avail_height: int, color_depth: int) -> str:
        return f"""
        // 3. Screen Resolution & Color Depth
        try {{
            const scrProto = (typeof Screen !== 'undefined' && Screen.prototype) ? Screen.prototype : (window.screen ? Object.getPrototypeOf(window.screen) : null);
            if (scrProto) {{
                Object.defineProperty(scrProto, 'width', {{ get: makeNative(() => {width}, 'get width'), configurable: true, enumerable: true }});
                Object.defineProperty(scrProto, 'height', {{ get: makeNative(() => {height}, 'get height'), configurable: true, enumerable: true }});
                Object.defineProperty(scrProto, 'availWidth', {{ get: makeNative(() => {avail_width}, 'get availWidth'), configurable: true, enumerable: true }});
                Object.defineProperty(scrProto, 'availHeight', {{ get: makeNative(() => {avail_height}, 'get availHeight'), configurable: true, enumerable: true }});
                Object.defineProperty(scrProto, 'colorDepth', {{ value: {color_depth}, writable: false, configurable: true, enumerable: true }});
                Object.defineProperty(scrProto, 'pixelDepth', {{ value: {color_depth}, writable: false, configurable: true, enumerable: true }});
            }}
        }} catch(e) {{ console.debug('Screen patch error:', e); }}
        """

    @staticmethod
    def _generate_webgl_patch(webgl_vendor: str, webgl_renderer: str, target_os: str = "windows") -> str:
        os_clean = (target_os or "windows").lower()
        is_linux = os_clean == "linux"
        is_mac = os_clean == "mac"
        is_nvidia = "NVIDIA" in webgl_vendor.upper() or "NVIDIA" in webgl_renderer.upper() or "RTX" in webgl_renderer.upper() or "GTX" in webgl_renderer.upper() or "GEFORCE" in webgl_renderer.upper()
        is_mesa = "MESA" in webgl_vendor.upper() or "MESA" in webgl_renderer.upper() or "RADV" in webgl_renderer.upper()

        if is_linux and is_nvidia:
            shading_lang = "WebGL GLSL ES 1.0 (NVIDIA 550.54.14)"
            gl_version = "WebGL 1.0 (OpenGL ES 3.0 NVIDIA 550.54.14)"
            max_tex_size = 32768
            max_uniform_vectors = 4096
            max_varying_vectors = 31
            viewport_w, viewport_h = 32768, 32768
            point_size_max = 2047
            line_width_max = 1
            extensions_json = json.dumps([
                "ANGLE_instanced_arrays", "EXT_blend_minmax", "EXT_color_buffer_half_float", "EXT_float_blend",
                "EXT_frag_depth", "EXT_shader_texture_lod", "EXT_sRGB", "EXT_texture_compression_bptc",
                "EXT_texture_compression_rgtc", "EXT_texture_filter_anisotropic", "OES_element_index_uint",
                "OES_fbo_render_mipmap", "OES_standard_derivatives", "OES_texture_float", "OES_texture_float_linear",
                "OES_texture_half_float", "OES_texture_half_float_linear", "OES_vertex_array_object",
                "WEBGL_color_buffer_float", "WEBGL_compressed_texture_etc", "WEBGL_compressed_texture_s3tc",
                "WEBGL_compressed_texture_s3tc_srgb", "WEBGL_debug_renderer_info", "WEBGL_debug_shaders",
                "WEBGL_depth_texture", "WEBGL_draw_buffers", "WEBGL_lose_context"
            ])
        elif is_linux and (is_mesa or "AMD" in webgl_vendor.upper() or "INTEL" in webgl_vendor.upper()):
            shading_lang = "WebGL GLSL ES 1.0 (OpenGL ES GLSL ES 1.0 Mesa 24.0.0)"
            gl_version = "WebGL 1.0 (OpenGL ES 3.0 Mesa 24.0.0)"
            max_tex_size = 16384
            max_uniform_vectors = 1024
            max_varying_vectors = 32
            viewport_w, viewport_h = 16384, 16384
            point_size_max = 2047
            line_width_max = 2047
            extensions_json = json.dumps([
                "ANGLE_instanced_arrays", "EXT_blend_minmax", "EXT_color_buffer_half_float", "EXT_float_blend",
                "EXT_frag_depth", "EXT_shader_texture_lod", "EXT_sRGB", "EXT_texture_compression_bptc",
                "EXT_texture_compression_rgtc", "EXT_texture_filter_anisotropic", "OES_element_index_uint",
                "OES_fbo_render_mipmap", "OES_standard_derivatives", "OES_texture_float", "OES_texture_float_linear",
                "OES_texture_half_float", "OES_texture_half_float_linear", "OES_vertex_array_object",
                "WEBGL_color_buffer_float", "WEBGL_compressed_texture_etc", "WEBGL_compressed_texture_s3tc",
                "WEBGL_compressed_texture_s3tc_srgb", "WEBGL_debug_renderer_info", "WEBGL_debug_shaders",
                "WEBGL_depth_texture", "WEBGL_draw_buffers", "WEBGL_lose_context"
            ])
        elif is_mac:
            shading_lang = "WebGL GLSL ES 1.0 (Metal)"
            gl_version = "WebGL 1.0 (OpenGL ES 3.0 Metal)"
            max_tex_size = 16384
            max_uniform_vectors = 1024
            max_varying_vectors = 31
            viewport_w, viewport_h = 16384, 16384
            point_size_max = 1024
            line_width_max = 1
            extensions_json = json.dumps([
                "ANGLE_instanced_arrays", "EXT_blend_minmax", "EXT_color_buffer_half_float", "EXT_float_blend",
                "EXT_frag_depth", "EXT_shader_texture_lod", "EXT_sRGB", "EXT_texture_filter_anisotropic",
                "OES_element_index_uint", "OES_fbo_render_mipmap", "OES_standard_derivatives",
                "OES_texture_float", "OES_texture_float_linear", "OES_texture_half_float",
                "OES_texture_half_float_linear", "OES_vertex_array_object", "WEBGL_color_buffer_float",
                "WEBGL_compressed_texture_s3tc", "WEBGL_compressed_texture_s3tc_srgb",
                "WEBGL_debug_renderer_info", "WEBGL_depth_texture", "WEBGL_draw_buffers", "WEBGL_lose_context"
            ])
        else:
            shading_lang = "WebGL GLSL ES 1.0 (OpenGL ES 3.0 Chromium)"
            gl_version = "WebGL 1.0 (OpenGL ES 3.0 Chromium)"
            max_tex_size = 16384
            max_uniform_vectors = 1024
            max_varying_vectors = 30
            viewport_w, viewport_h = 32767, 32767
            point_size_max = 1024
            line_width_max = 1
            extensions_json = json.dumps([
                "ANGLE_instanced_arrays", "EXT_blend_minmax", "EXT_color_buffer_half_float", "EXT_float_blend",
                "EXT_frag_depth", "EXT_shader_texture_lod", "EXT_sRGB", "EXT_texture_compression_bptc",
                "EXT_texture_compression_rgtc", "EXT_texture_filter_anisotropic", "OES_element_index_uint",
                "OES_fbo_render_mipmap", "OES_standard_derivatives", "OES_texture_float", "OES_texture_float_linear",
                "OES_texture_half_float", "OES_texture_half_float_linear", "OES_vertex_array_object",
                "WEBGL_color_buffer_float", "WEBGL_compressed_texture_s3tc", "WEBGL_compressed_texture_s3tc_srgb",
                "WEBGL_debug_renderer_info", "WEBGL_debug_shaders", "WEBGL_depth_texture", "WEBGL_draw_buffers",
                "WEBGL_lose_context"
            ])

        return f"""
        // 4. WebGL Senior Deep Hardware & Precision Engine
        try {{
            const debugExtObj = Object.freeze({{
                UNMASKED_VENDOR_WEBGL: 37445,
                UNMASKED_RENDERER_WEBGL: 37446
            }});

            const targetExtensions = Object.freeze({extensions_json});

            const patchWebGL = function(glProto) {{
                if (!glProto) return;

                const origGetSupportedExtensions = glProto.getSupportedExtensions;
                if (origGetSupportedExtensions) {{
                    glProto.getSupportedExtensions = makeNative(function getSupportedExtensions() {{
                        const ext = origGetSupportedExtensions.apply(this, arguments);
                        const baseList = Array.isArray(ext) ? [...ext] : [];
                        for (const targetExt of targetExtensions) {{
                            if (!baseList.includes(targetExt)) {{
                                baseList.push(targetExt);
                            }}
                        }}
                        return baseList;
                    }}, 'getSupportedExtensions');
                }}

                const origGetExtension = glProto.getExtension;
                if (origGetExtension) {{
                    glProto.getExtension = makeNative(function getExtension(name) {{
                        const extName = String(name || '').toLowerCase();
                        const ext = origGetExtension.apply(this, arguments);
                        if (extName === 'webgl_debug_renderer_info') {{
                            return debugExtObj;
                        }}
                        if (extName === 'ext_texture_filter_anisotropic') {{
                            const dummy = ext || {{}};
                            return Object.freeze({{
                                MAX_TEXTURE_MAX_ANISOTROPY_EXT: 34047,
                                __proto__: dummy
                            }});
                        }}
                        return ext;
                    }}, 'getExtension');
                }}

                const origGetParam = glProto.getParameter;
                glProto.getParameter = makeNative(function getParameter(parameter) {{
                    let p = parameter;
                    try {{
                        p = Number(parameter);
                    }} catch(e) {{}}

                    if (p === 37445 || p === 0x9245) return '{webgl_vendor}';
                    if (p === 37446 || p === 0x9246) return '{webgl_renderer}';
                    if (p === 0x1F00) return 'WebKit';
                    if (p === 0x1F01) return 'WebKit WebGL';
                    if (p === 0x1F02) return '{gl_version}';
                    if (p === 0x8B8C) return '{shading_lang}';
                    if (p === 34047) return 16;
                    if (p === 3379) return {max_tex_size};
                    if (p === 34069) return {max_tex_size};
                    if (p === 34024) return {max_tex_size};
                    if (p === 34921) return 16;
                    if (p === 36347) return {max_uniform_vectors};
                    if (p === 36348) return {max_uniform_vectors};
                    if (p === 36349) return {max_varying_vectors};
                    if (p === 35661) return 192;
                    if (p === 34930) return 32;
                    if (p === 3386) return new Int32Array([{viewport_w}, {viewport_h}]);
                    if (p === 33902) return new Float32Array([1, {point_size_max}]);
                    if (p === 33901) return new Float32Array([1, {line_width_max}]);
                    return origGetParam.apply(this, arguments);
                }}, 'getParameter');

                const origGetShaderPrecision = glProto.getShaderPrecisionFormat;
                if (origGetShaderPrecision) {{
                    glProto.getShaderPrecisionFormat = makeNative(function getShaderPrecisionFormat(shaderType, precisionType) {{
                        const res = origGetShaderPrecision.apply(this, arguments);
                        if (res) {{
                            try {{
                                Object.defineProperty(res, 'rangeMin', {{ value: 127, configurable: true, enumerable: true }});
                                Object.defineProperty(res, 'rangeMax', {{ value: 127, configurable: true, enumerable: true }});
                                Object.defineProperty(res, 'precision', {{ value: 23, configurable: true, enumerable: true }});
                            }} catch(e) {{}}
                        }}
                        return res;
                    }}, 'getShaderPrecisionFormat');
                }}

                // 3D WebGL Canvas Shader Jitter & readPixels Micro-Noise (GPU Level Anti-Detect)
                const origReadPixels = glProto.readPixels;
                if (origReadPixels) {{
                    glProto.readPixels = makeNative(function readPixels(x, y, w, h, format, type, pixels) {{
                        const res = origReadPixels.apply(this, arguments);
                        if (pixels && pixels instanceof Uint8Array && pixels.length > 0) {{
                            const noiseFactor = 0.0008;
                            for (let i = 0; i < Math.min(pixels.length, 10000); i += 16) {{
                                if (pixels[i] > 0 && (i % 4 !== 3)) {{
                                    const jitter = Math.round(Math.sin(i * 1.37 + 0.5) * noiseFactor * 255);
                                    pixels[i] = Math.min(255, Math.max(0, pixels[i] + jitter));
                                }}
                            }}
                        }}
                        return res;
                    }}, 'readPixels');
                }}
            }};

            if (typeof WebGLRenderingContext !== 'undefined') patchWebGL(WebGLRenderingContext.prototype);
            if (typeof WebGL2RenderingContext !== 'undefined') patchWebGL(WebGL2RenderingContext.prototype);
        }} catch(e) {{ console.debug('WebGL patch error:', e); }}
        """

    @staticmethod
    def _generate_canvas_noise_patch(canvas_noise: bool, noise_seed: float) -> str:
        if not canvas_noise:
            return ""
        return f"""
        // 5. Advanced Content-Keyed Deterministic Canvas Anti-Fingerprinting (CreepJS & DataDome Inconsistency Resistant)
        try {{
            const profileSeed = Math.abs(Math.round({noise_seed} * 100000)) || 1337;

            // Fast 32-bit FNV-1a hash for content-keyed determinism
            function fnv1a(data, len) {{
                let h = 0x811c9dc5;
                const step = Math.max(1, Math.floor(len / 128));
                for (let i = 0; i < len; i += step) {{
                    h ^= data[i];
                    h = Math.imul(h, 0x01000193);
                }}
                return (h ^ profileSeed) >>> 0;
            }}

            // Deterministic Mulberry32 PRNG seeded from canvas content hash
            function mulberry32(a) {{
                return function() {{
                    let t = a += 0x6D2B79F5;
                    t = Math.imul(t ^ t >>> 15, t | 1);
                    t ^= t + Math.imul(t ^ t >>> 7, t | 61);
                    return ((t ^ t >>> 14) >>> 0) / 4294967296;
                }};
            }}

            function applyDeterministicNoise(imageData, w, h) {{
                if (!imageData || !imageData.data || imageData.data.length === 0) return imageData;
                const data = imageData.data;
                const len = data.length;
                const contentHash = fnv1a(data, len) ^ ((w * 31 + h) >>> 0);
                const rng = mulberry32(contentHash);

                const step = Math.max(8, Math.floor(len / 1000));
                for (let i = 0; i < len; i += step) {{
                    if (data[i + 3] > 10) {{ // Apply subtle +/- 1 noise to non-transparent pixels
                        const channel = Math.floor(rng() * 3); // R, G, or B
                        const delta = (rng() < 0.5) ? -1 : 1;
                        data[i + channel] = Math.min(255, Math.max(0, data[i + channel] + delta));
                    }}
                }}
                return imageData;
            }}

            const patchCanvasContext = function(ctxProto) {{
                if (!ctxProto) return;
                const origGetImageData = ctxProto.getImageData;
                if (origGetImageData) {{
                    ctxProto.getImageData = makeNative(function getImageData(x, y, w, h) {{
                        const img = origGetImageData.apply(this, arguments);
                        return applyDeterministicNoise(img, w || 1, h || 1);
                    }}, 'getImageData');
                }}
            }};

            if (typeof CanvasRenderingContext2D !== 'undefined') patchCanvasContext(CanvasRenderingContext2D.prototype);
            if (typeof OffscreenCanvasRenderingContext2D !== 'undefined') patchCanvasContext(OffscreenCanvasRenderingContext2D.prototype);

            if (typeof HTMLCanvasElement !== 'undefined') {{
                const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
                if (origToDataURL) {{
                    HTMLCanvasElement.prototype.toDataURL = makeNative(function toDataURL(type, encoderOptions) {{
                        try {{
                            const ctx = this.getContext('2d');
                            if (ctx && this.width > 0 && this.height > 0) {{
                                const img = ctx.getImageData(0, 0, this.width, this.height);
                                const tmpCanvas = document.createElement('canvas');
                                tmpCanvas.width = this.width;
                                tmpCanvas.height = this.height;
                                const tmpCtx = tmpCanvas.getContext('2d');
                                if (tmpCtx) {{
                                    tmpCtx.putImageData(img, 0, 0);
                                    return origToDataURL.call(tmpCanvas, type, encoderOptions);
                                }}
                            }}
                        }} catch(e) {{}}
                        return origToDataURL.apply(this, arguments);
                    }}, 'toDataURL');
                }}

                const origToBlob = HTMLCanvasElement.prototype.toBlob;
                if (origToBlob) {{
                    HTMLCanvasElement.prototype.toBlob = makeNative(function toBlob(callback, type, quality) {{
                        try {{
                            const ctx = this.getContext('2d');
                            if (ctx && this.width > 0 && this.height > 0) {{
                                const img = ctx.getImageData(0, 0, this.width, this.height);
                                const tmpCanvas = document.createElement('canvas');
                                tmpCanvas.width = this.width;
                                tmpCanvas.height = this.height;
                                const tmpCtx = tmpCanvas.getContext('2d');
                                if (tmpCtx) {{
                                    tmpCtx.putImageData(img, 0, 0);
                                    return origToBlob.call(tmpCanvas, callback, type, quality);
                                }}
                            }}
                        }} catch(e) {{}}
                        return origToBlob.apply(this, arguments);
                    }}, 'toBlob');
                }}
            }}
        }} catch(e) {{ console.debug('Canvas noise patch error:', e); }}
        """

    @staticmethod
    def _generate_font_rects_noise_patch(font_noise: bool, client_rects_noise: bool, noise_seed: float) -> str:
        script = ""
        if font_noise:
            script += f"""
            try {{
                if (typeof TextMetrics !== 'undefined' && TextMetrics.prototype) {{
                    const origWidthDesc = Object.getOwnPropertyDescriptor(TextMetrics.prototype, 'width');
                    if (origWidthDesc && origWidthDesc.get) {{
                        const origGetWidth = origWidthDesc.get;
                        Object.defineProperty(TextMetrics.prototype, 'width', {{
                            get: makeNative(function width() {{
                                const w = origGetWidth.apply(this, arguments);
                                return (typeof w === 'number') ? w + ({noise_seed} * 0.00001) : w;
                            }}, 'get width', 0),
                            configurable: true,
                            enumerable: true
                        }});
                    }}
                }}
            }} catch(e) {{ console.debug('Font noise patch error:', e); }}
            """

        if client_rects_noise:
            script += f"""
            try {{
                if (typeof DOMRectReadOnly !== 'undefined' && DOMRectReadOnly.prototype) {{
                    const origWidthDesc = Object.getOwnPropertyDescriptor(DOMRectReadOnly.prototype, 'width');
                    if (origWidthDesc && origWidthDesc.get) {{
                        const origGetWidth = origWidthDesc.get;
                        Object.defineProperty(DOMRectReadOnly.prototype, 'width', {{
                            get: makeNative(function width() {{
                                const w = origGetWidth.apply(this, arguments);
                                return (typeof w === 'number' && w > 0) ? w + ({noise_seed} * 0.00001) : w;
                            }}, 'get width', 0),
                            configurable: true,
                            enumerable: true
                        }});
                    }}
                }}
            }} catch(e) {{ console.debug('DOMRect noise patch error:', e); }}
            """
        return script

    @staticmethod
    def _generate_audio_noise_patch(audio_noise: bool, noise_seed: float, is_camoufox: bool = False) -> str:
        if not audio_noise:
            return ""
        
        # Camoufox has C++/Rust internal DSP noise — skip JS level AudioBuffer hooking to avoid CreepJS float-noise red digit flags
        if is_camoufox:
            return "// Camoufox Engine: Utilizing Native C++/Rust DSP Audio Jitter (No JS Prototype Tampering)"

        return f"""
        // 6. AudioContext Fingerprint Noise Injection (Bounded WeakSet & Idempotent per Buffer)
        try {{
            if (typeof AudioBuffer !== 'undefined') {{
                const processedBuffers = new WeakSet();
                const originalGetChannelData = AudioBuffer.prototype.getChannelData;
                AudioBuffer.prototype.getChannelData = makeNative(function getChannelData(channel) {{
                    const results = originalGetChannelData.apply(this, arguments);
                    if (results && results.length > 0 && !processedBuffers.has(this)) {{
                        processedBuffers.add(this);
                        let hasSignal = false;
                        const checkLen = Math.min(results.length, 1000);
                        for (let i = 0; i < checkLen; i++) {{
                            if (results[i] !== 0) {{
                                hasSignal = true;
                                break;
                            }}
                        }}
                        if (hasSignal) {{
                            const seedFactor = {noise_seed} * 0.00000001;
                            const maxScan = Math.min(results.length, 10000);
                            for (let i = 0; i < maxScan; i++) {{
                                if (results[i] !== 0) {{
                                    results[i] = results[i] + (Math.sin(i) * seedFactor);
                                }}
                            }}
                        }}
                    }}
                    return results;
                }}, 'getChannelData', 1);
            }}

            if (typeof AnalyserNode !== 'undefined') {{
                const origGetFloatFreq = AnalyserNode.prototype.getFloatFrequencyData;
                AnalyserNode.prototype.getFloatFrequencyData = makeNative(function getFloatFrequencyData(array) {{
                    origGetFloatFreq.apply(this, arguments);
                    if (array && array.length > 0) {{
                        const seedFactor = {noise_seed} * 0.00001;
                        for (let i = 0; i < Math.min(array.length, 4096); i++) {{
                            array[i] = array[i] + (Math.sin(i) * seedFactor);
                        }}
                    }}
                }}, 'getFloatFrequencyData', 1);
            }}
        }} catch(e) {{ console.debug('Audio patch error:', e); }}
        """

    @staticmethod
    def _generate_speech_synthesis_patch(target_os: str = "windows", primary_locale: str = "en-US") -> str:
        """Emulates realistic SpeechSynthesis voices to prevent CreepJS speech blocked flags."""
        os_clean = (target_os or "windows").lower()
        if "mac" in os_clean:
            voices_json = json.dumps([
                {"name": "Samantha", "lang": "en-US", "voiceURI": "Samantha", "default": True, "localService": True},
                {"name": "Alex", "lang": "en-US", "voiceURI": "Alex", "default": False, "localService": True},
                {"name": "Fred", "lang": "en-US", "voiceURI": "Fred", "default": False, "localService": True},
                {"name": "Victoria", "lang": "en-US", "voiceURI": "Victoria", "default": False, "localService": True}
            ])
        elif "linux" in os_clean:
            voices_json = json.dumps([
                {"name": "English (America)+default", "lang": "en-US", "voiceURI": "default", "default": True, "localService": True},
                {"name": "English (Great Britain)", "lang": "en-GB", "voiceURI": "english-gb", "default": False, "localService": True}
            ])
        else:
            voices_json = json.dumps([
                {"name": "Microsoft David - English (United States)", "lang": "en-US", "voiceURI": "Microsoft David - English (United States)", "default": True, "localService": True},
                {"name": "Microsoft Zira - English (United States)", "lang": "en-US", "voiceURI": "Microsoft Zira - English (United States)", "default": False, "localService": True},
                {"name": "Microsoft Mark - English (United States)", "lang": "en-US", "voiceURI": "Microsoft Mark - English (United States)", "default": False, "localService": True}
            ])

        return f"""
        // 7. SpeechSynthesis Voices Realism Patch
        try {{
            if (typeof window.speechSynthesis !== 'undefined') {{
                const rawVoicesData = {voices_json};
                const voicesList = rawVoicesData.map(v => Object.freeze({{
                    name: v.name,
                    lang: v.lang,
                    voiceURI: v.voiceURI,
                    default: v.default,
                    localService: v.localService
                }}));

                window.speechSynthesis.getVoices = makeNative(function getVoices() {{
                    return voicesList;
                }}, 'getVoices', 0);

                if (typeof window.speechSynthesis.onvoiceschanged !== 'undefined') {{
                    setTimeout(() => {{
                        try {{
                            if (typeof window.speechSynthesis.onvoiceschanged === 'function') {{
                                window.speechSynthesis.onvoiceschanged(new Event('voiceschanged'));
                            }}
                            window.speechSynthesis.dispatchEvent(new Event('voiceschanged'));
                        }} catch(e) {{}}
                    }}, 20);
                }}
            }}
        }} catch(e) {{ console.debug('SpeechSynthesis patch error:', e); }}
        """

    @staticmethod
    def _generate_synthetic_media_devices(audio_in_id: str, audio_out_id: str, video_in_id: str) -> str:
        return f"""
        // 7. Synthetic Media Devices
        if (navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {{
            try {{
                const fakeDevices = [
                    {{ deviceId: "{audio_in_id}", kind: "audioinput", label: "Default Audio Input (Realtek High Definition)", groupId: "group_audio_in" }},
                    {{ deviceId: "{audio_out_id}", kind: "audiooutput", label: "Default Audio Output (Realtek High Definition)", groupId: "group_audio_out" }},
                    {{ deviceId: "{video_in_id}", kind: "videoinput", label: "Integrated HD Webcam", groupId: "group_video_in" }}
                ];
                navigator.mediaDevices.enumerateDevices = makeNative(async function enumerateDevices() {{
                    return fakeDevices;
                }}, 'enumerateDevices');
            }} catch(e) {{ console.debug('MediaDevices patch error:', e); }}
        }}
        """

    @staticmethod
    def _generate_permissions_patch() -> str:
        return """
        // 8. Permissions API Realism Patch
        try {
            if (navigator.permissions && navigator.permissions.query) {
                const origQuery = navigator.permissions.query;
                navigator.permissions.query = makeNative(function query(parameters) {
                    const name = parameters ? parameters.name : '';
                    if (name === 'notifications') {
                        return Promise.resolve({ state: 'default', onchange: null });
                    }
                    if (name === 'geolocation') {
                        return Promise.resolve({ state: 'prompt', onchange: null });
                    }
                    if (name === 'camera' || name === 'microphone') {
                        return Promise.resolve({ state: 'prompt', onchange: null });
                    }
                    return origQuery.apply(this, arguments);
                }, 'query');
            }
        } catch(e) { console.debug('Permissions patch error:', e); }
        """

    @staticmethod
    def _generate_network_battery_patch() -> str:
        return """
        // 9. Network Information & Battery API Realism Patch
        try {
            if (!navigator.connection) {
                Object.defineProperty(navigator, 'connection', {
                    get: makeNative(() => Object.freeze({
                        effectiveType: '4g',
                        rtt: 50,
                        downlink: 10,
                        saveData: false,
                        onchange: null
                    }), 'get connection'),
                    configurable: true,
                    enumerable: true
                });
            }
            if (typeof navigator.getBattery !== 'function') {
                navigator.getBattery = makeNative(function getBattery() {
                    return Promise.resolve({
                        charging: true,
                        chargingTime: 0,
                        dischargingTime: Infinity,
                        level: 1.0,
                        onchargingchange: null,
                        onlevelchange: null
                    });
                }, 'getBattery');
            }
        } catch(e) { console.debug('Network & Battery patch error:', e); }
        """

    @staticmethod
    def _generate_sensor_patch(is_mobile: bool = False) -> str:
        """Emulates modern Hardware Sensor APIs (Accelerometer, Gyroscope, DeviceOrientation, DeviceMotion)."""
        return f"""
        // 10. Hardware Sensor APIs & Motion Emulation
        (function() {{
            try {{
                const isMob = {str(is_mobile).lower()};
                
                // Sensor base class mock
                class SensorMock extends EventTarget {{
                    constructor() {{
                        super();
                        this.activated = true;
                        this.hasReading = true;
                        this.timestamp = performance.now();
                        this.onreading = null;
                        this.onerror = null;
                    }}
                    start() {{ this.activated = true; }}
                    stop() {{ this.activated = false; }}
                }}

                if (typeof window.Accelerometer === 'undefined') {{
                    window.Accelerometer = makeNative(class Accelerometer extends SensorMock {{
                        get x() {{ return (Math.random() - 0.5) * 0.04; }}
                        get y() {{ return (Math.random() - 0.5) * 0.04; }}
                        get z() {{ return 9.80665 + (Math.random() - 0.5) * 0.02; }}
                    }}, 'Accelerometer');
                }}

                if (typeof window.LinearAccelerationSensor === 'undefined') {{
                    window.LinearAccelerationSensor = makeNative(class LinearAccelerationSensor extends SensorMock {{
                        get x() {{ return (Math.random() - 0.5) * 0.01; }}
                        get y() {{ return (Math.random() - 0.5) * 0.01; }}
                        get z() {{ return (Math.random() - 0.5) * 0.01; }}
                    }}, 'LinearAccelerationSensor');
                }}

                if (typeof window.Gyroscope === 'undefined') {{
                    window.Gyroscope = makeNative(class Gyroscope extends SensorMock {{
                        get x() {{ return (Math.random() - 0.5) * 0.002; }}
                        get y() {{ return (Math.random() - 0.5) * 0.002; }}
                        get z() {{ return (Math.random() - 0.5) * 0.002; }}
                    }}, 'Gyroscope');
                }}

                if (typeof window.AbsoluteOrientationSensor === 'undefined') {{
                    window.AbsoluteOrientationSensor = makeNative(class AbsoluteOrientationSensor extends SensorMock {{
                        get quaternion() {{ return [0, 0, 0, 1]; }}
                    }}, 'AbsoluteOrientationSensor');
                }}

                // Window DeviceOrientation Event Mock for desktop/mobile consistency
                if (isMob) {{
                    window.addEventListener('deviceorientation', function(e) {{
                        if (e.alpha === null) {{
                            Object.defineProperty(e, 'alpha', {{ value: 0.0 }});
                            Object.defineProperty(e, 'beta', {{ value: 0.0 }});
                            Object.defineProperty(e, 'gamma', {{ value: 0.0 }});
                        }}
                    }}, {{ passive: true }});
                }}
            }} catch(e) {{
                console.debug('Sensor patch error:', e);
            }}
        }})();
        """

    @staticmethod
    def _generate_webgpu_patch(
        webgpu_supported: bool,
        webgl_vendor: str,
        webgl_renderer: str,
        target_os: str = "windows"
    ) -> str:
        """Emulates W3C WebGPU GPUAdapter, GPUDevice, shader precision (F16/F32), and Limits."""
        if not webgpu_supported:
            return """
            try {
                if (navigator.gpu) {
                    Object.defineProperty(navigator, 'gpu', { get: makeNative(() => undefined, 'get gpu'), configurable: true, enumerable: true });
                }
            } catch(e) {}
            """

        os_clean = (target_os or "windows").lower()
        supports_f16 = ("apple" in webgl_vendor.lower() or "apple" in webgl_renderer.lower() or 
                        "rtx" in webgl_renderer.lower() or "4090" in webgl_renderer.lower() or 
                        "4080" in webgl_renderer.lower() or "4070" in webgl_renderer.lower() or 
                        "7900" in webgl_renderer.lower())

        arch_name = "arm64" if "apple" in os_clean else ("ada-lovelace" if "40" in webgl_renderer else ("ampere" if "30" in webgl_renderer else "rdna3"))
        vendor_clean = "apple" if "apple" in os_clean else ("nvidia" if "nvidia" in webgl_vendor.lower() or "geforce" in webgl_renderer.lower() else "amd")

        return f"""
        // 11. Senior WebGPU Hardware & Shader F16/F32 Emulation
        (function() {{
            try {{
                const featureArray = [
                    "depth-clip-control",
                    "depth32float-stencil8",
                    "texture-compression-bc",
                    "indirect-first-instance",
                    "rg11b10ufloat-renderable",
                    "bgra8unorm-storage",
                    "float32-filterable"
                ];
                if ({str(supports_f16).lower()}) {{
                    featureArray.push("shader-f16");
                }}

                const mockFeatures = new Set(featureArray);

                const mockLimits = Object.freeze({{
                    maxTextureDimension1D: 16384,
                    maxTextureDimension2D: 16384,
                    maxTextureDimension3D: 2048,
                    maxTextureArrayLayers: 2048,
                    maxBindGroups: 4,
                    maxBindGroupsPlusVertexBuffers: 24,
                    maxBindingsPerBindGroup: 1000,
                    maxDynamicUniformBuffersPerPipelineLayout: 8,
                    maxDynamicStorageBuffersPerPipelineLayout: 4,
                    maxSampledTexturesPerShaderStage: 16,
                    maxSamplersPerShaderStage: 16,
                    maxStorageBuffersPerShaderStage: 8,
                    maxStorageTexturesPerShaderStage: 4,
                    maxUniformBuffersPerShaderStage: 12,
                    maxUniformBufferBindingSize: 65536,
                    maxStorageBufferBindingSize: 134217728,
                    minUniformBufferOffsetAlignment: 256,
                    minStorageBufferOffsetAlignment: 256,
                    maxVertexBuffers: 8,
                    maxBufferSize: 268435456,
                    maxVertexAttributes: 16,
                    maxVertexBufferArrayStride: 2048,
                    maxInterStageShaderVariables: 16,
                    maxColorAttachments: 8,
                    maxColorAttachmentBytesPerSample: 32,
                    maxComputeWorkgroupStorageSize: 32768,
                    maxComputeInvocationsPerWorkgroup: 1024,
                    maxComputeWorkgroupSizeX: 1024,
                    maxComputeWorkgroupSizeY: 1024,
                    maxComputeWorkgroupSizeZ: 64,
                    maxComputeWorkgroupsPerDimension: 65535
                }});

                const mockAdapterInfo = Object.freeze({{
                    vendor: "{vendor_clean}",
                    architecture: "{arch_name}",
                    device: "{webgl_renderer}",
                    description: "Hardware WebGPU Adapter ({webgl_renderer})"
                }});

                const mockDevice = Object.freeze({{
                    features: mockFeatures,
                    limits: mockLimits,
                    queue: Object.freeze({{
                        submit: makeNative(() => {{}}, 'submit'),
                        onSubmittedWorkDone: makeNative(() => Promise.resolve(), 'onSubmittedWorkDone')
                    }}),
                    lost: new Promise(() => {{}}),
                    createShaderModule: makeNative((desc) => Object.freeze({{}}), 'createShaderModule'),
                    createRenderPipeline: makeNative((desc) => Object.freeze({{}}), 'createRenderPipeline'),
                    createComputePipeline: makeNative((desc) => Object.freeze({{}}), 'createComputePipeline'),
                    createBuffer: makeNative((desc) => Object.freeze({{
                        size: desc ? desc.size : 0,
                        usage: desc ? desc.usage : 0,
                        mapAsync: makeNative(() => Promise.resolve(), 'mapAsync'),
                        getMappedRange: makeNative(() => new ArrayBuffer(desc ? desc.size : 0), 'getMappedRange'),
                        unmap: makeNative(() => {{}}, 'unmap'),
                        destroy: makeNative(() => {{}}, 'destroy')
                    }}), 'createBuffer'),
                    createTexture: makeNative(() => Object.freeze({{}}), 'createTexture'),
                    createSampler: makeNative(() => Object.freeze({{}}), 'createSampler'),
                    createBindGroup: makeNative(() => Object.freeze({{}}), 'createBindGroup'),
                    createBindGroupLayout: makeNative(() => Object.freeze({{}}), 'createBindGroupLayout'),
                    createPipelineLayout: makeNative(() => Object.freeze({{}}), 'createPipelineLayout'),
                    createCommandEncoder: makeNative(() => Object.freeze({{
                        beginRenderPass: makeNative(() => Object.freeze({{
                            end: makeNative(() => {{}}, 'end'),
                            setPipeline: makeNative(() => {{}}, 'setPipeline'),
                            draw: makeNative(() => {{}}, 'draw')
                        }}), 'beginRenderPass'),
                        finish: makeNative(() => Object.freeze({{}}), 'finish')
                    }}), 'createCommandEncoder'),
                    destroy: makeNative(() => {{}}, 'destroy'),
                    addEventListener: makeNative(() => {{}}, 'addEventListener'),
                    removeEventListener: makeNative(() => {{}}, 'removeEventListener')
                }});

                const mockAdapter = Object.freeze({{
                    name: "{webgl_renderer}",
                    vendor: "{webgl_vendor}",
                    architecture: "{arch_name}",
                    device: "gpu-0",
                    description: "Hardware WebGPU Adapter",
                    features: mockFeatures,
                    limits: mockLimits,
                    isFallbackAdapter: false,
                    requestAdapterInfo: makeNative(async () => mockAdapterInfo, 'requestAdapterInfo'),
                    info: mockAdapterInfo,
                    requestDevice: makeNative(async () => mockDevice, 'requestDevice')
                }});

                const mockGPU = Object.freeze({{
                    requestAdapter: makeNative(async function requestAdapter(options) {{
                        return mockAdapter;
                    }}, 'requestAdapter'),
                    getPreferredCanvasFormat: makeNative(function getPreferredCanvasFormat() {{
                        return "bgra8unorm";
                    }}, 'getPreferredCanvasFormat'),
                    getPreferredFormat: makeNative(function getPreferredFormat() {{
                        return "bgra8unorm";
                    }}, 'getPreferredFormat'),
                    wgslLanguageFeatures: Object.freeze(new Set({str(supports_f16).lower()} ? ["readonly_and_readwrite_storage_textures", "packed_4x8_integer_dot_product", "unrestricted_pointer_parameters", "pointer_composite_access"] : []))
                }});

                Object.defineProperty(navigator, 'gpu', {{
                    get: makeNative(() => mockGPU, 'get gpu'),
                    configurable: true,
                    enumerable: true
                }});
            }} catch(e) {{
                console.debug('WebGPU patch error:', e);
            }}
        }})();
        """

    @staticmethod
    def _generate_drm_eme_patch(drm_enabled: bool = True, target_os: str = "windows") -> str:
        """
        Generates W3C Standard EME & CDM (Encrypted Media Extensions) compatibility layer
        supporting ClearKey (org.w3.clearkey), Widevine L3/L1 (com.widevine.alpha),
        PlayReady SW/HW (com.microsoft.playready), and WebKit-EME FairPlay (com.apple.fps).
        When drm_enabled is False, installs a W3C-compliant rejection layer to safely satisfy
        anti-bot probers (such as TikTok / ByteDance WebMSSDK) without DRM fingerprinting.
        """
        t_os = (target_os or "windows").lower()
        if not drm_enabled:
            return f"""
        // 13. W3C Standard EME Privacy-First Rejection Layer (TikTok & Universal Video Safe)
        (function() {{
            try {{
                const navProto = Object.getPrototypeOf(navigator) || Navigator.prototype;
                const origRequestAccess = navigator.requestMediaKeySystemAccess;

                const privacyRequestMediaKeySystemAccess = makeNative(async function requestMediaKeySystemAccess(keySystem, supportedConfigurations) {{
                    if (!keySystem || typeof keySystem !== 'string') {{
                        throw new TypeError("Failed to execute 'requestMediaKeySystemAccess' on 'Navigator': 1 argument required, but only 0 present.");
                    }}
                    if (!supportedConfigurations || !Array.isArray(supportedConfigurations) || supportedConfigurations.length === 0) {{
                        throw new TypeError("Failed to execute 'requestMediaKeySystemAccess' on 'Navigator': The provided value is not of type '(sequence<MediaKeySystemConfiguration> or MediaKeySystemConfiguration)'.");
                    }}
                    // Standard W3C Firefox rejection when DRM / Widevine is intentionally disabled
                    throw new DOMException("Key system not supported", "NotSupportedError");
                }}, 'requestMediaKeySystemAccess', 2);

                Object.defineProperty(navProto, 'requestMediaKeySystemAccess', {{
                    value: privacyRequestMediaKeySystemAccess,
                    writable: true,
                    configurable: true,
                    enumerable: true
                }});
                Object.defineProperty(navigator, 'requestMediaKeySystemAccess', {{
                    value: privacyRequestMediaKeySystemAccess,
                    writable: true,
                    configurable: true,
                    enumerable: true
                }});
            }} catch(e) {{}}
        }})();
        """

        return f"""
        // 13. W3C Standard EME, DRM & Virtual CDM System (ClearKey, Widevine L1/L3, PlayReady, FairPlay)
        (function() {{
            try {{
                const targetOS = "{t_os}";
                const origRequestAccess = navigator.requestMediaKeySystemAccess;

                // Mock MediaKeySession implementation
                class MockMediaKeySession extends EventTarget {{
                    constructor() {{
                        super();
                        this.sessionId = 'session_' + Math.random().toString(36).substring(2, 10);
                        this.expiration = NaN;
                        this.closed = new Promise((res) => {{ this._resolveClosed = res; }});
                        this.keyStatuses = new Map();
                        this.onkeystatuseschange = null;
                        this.onmessage = null;
                    }}
                    async generateRequest(initDataType, initData) {{
                        setTimeout(() => {{
                            try {{
                                const msgEvent = new CustomEvent('message', {{
                                    detail: {{ messageType: 'license-request', message: new Uint8Array([1, 2, 3, 4]).buffer }}
                                }});
                                Object.defineProperty(msgEvent, 'messageType', {{ value: 'license-request', enumerable: true }});
                                Object.defineProperty(msgEvent, 'message', {{ value: new Uint8Array([1, 2, 3, 4]).buffer, enumerable: true }});
                                this.dispatchEvent(msgEvent);
                                if (typeof this.onmessage === 'function') {{
                                    this.onmessage(msgEvent);
                                }}
                            }} catch(e) {{}}
                        }}, 10);
                        return undefined;
                    }}
                    async load(sessionId) {{ return true; }}
                    async update(response) {{
                        setTimeout(() => {{
                            try {{
                                const statusEvent = new Event('keystatuseschange');
                                this.dispatchEvent(statusEvent);
                                if (typeof this.onkeystatuseschange === 'function') {{
                                    this.onkeystatuseschange(statusEvent);
                                }}
                            }} catch(e) {{}}
                        }}, 10);
                        return undefined;
                    }}
                    async close() {{
                        if (this._resolveClosed) this._resolveClosed();
                        return undefined;
                    }}
                    async remove() {{ return undefined; }}
                }}
                makeNative(MockMediaKeySession.prototype.generateRequest, 'generateRequest', 2);
                makeNative(MockMediaKeySession.prototype.load, 'load', 1);
                makeNative(MockMediaKeySession.prototype.update, 'update', 1);
                makeNative(MockMediaKeySession.prototype.close, 'close', 0);
                makeNative(MockMediaKeySession.prototype.remove, 'remove', 0);

                // Mock MediaKeys implementation
                class MockMediaKeys {{
                    constructor(keySystem) {{
                        this._keySystem = keySystem;
                    }}
                    createSession(sessionType = 'temporary') {{
                        return new MockMediaKeySession();
                    }}
                    async setServerCertificate(serverCertificate) {{
                        return true;
                    }}
                    async getStatusForPolicy(policy) {{
                        return 'usable';
                    }}
                }}
                makeNative(MockMediaKeys.prototype.createSession, 'createSession', 0);
                makeNative(MockMediaKeys.prototype.setServerCertificate, 'setServerCertificate', 1);
                makeNative(MockMediaKeys.prototype.getStatusForPolicy, 'getStatusForPolicy', 1);

                // Mock MediaKeySystemAccess implementation
                class MockMediaKeySystemAccess {{
                    constructor(keySystem, configuration) {{
                        this.keySystem = keySystem;
                        this._configuration = configuration;
                    }}
                    getConfiguration() {{
                        return JSON.parse(JSON.stringify(this._configuration));
                    }}
                    async createMediaKeys() {{
                        return new MockMediaKeys(this.keySystem);
                    }}
                }}
                makeNative(MockMediaKeySystemAccess.prototype.getConfiguration, 'getConfiguration', 0);
                makeNative(MockMediaKeySystemAccess.prototype.createMediaKeys, 'createMediaKeys', 0);

                if (typeof window.MediaKeySystemAccess === 'undefined') {{
                    window.MediaKeySystemAccess = makeNative(MockMediaKeySystemAccess, 'MediaKeySystemAccess');
                }}
                if (typeof window.MediaKeys === 'undefined') {{
                    window.MediaKeys = makeNative(MockMediaKeys, 'MediaKeys');
                }}
                if (typeof window.MediaKeySession === 'undefined') {{
                    window.MediaKeySession = makeNative(MockMediaKeySession, 'MediaKeySession');
                }}

                // Support HTMLMediaElement setMediaKeys
                if (window.HTMLMediaElement && !HTMLMediaElement.prototype.setMediaKeys) {{
                    HTMLMediaElement.prototype.setMediaKeys = makeNative(async function setMediaKeys(mediaKeys) {{
                        this._mediaKeys = mediaKeys;
                        return undefined;
                    }}, 'setMediaKeys', 1);
                    Object.defineProperty(HTMLMediaElement.prototype, 'mediaKeys', {{
                        get: makeNative(function() {{ return this._mediaKeys || null; }}, 'get mediaKeys'),
                        configurable: true,
                        enumerable: true
                    }});
                }}

                // WebKit-EME Legacy Support (WebKitMediaKeys / webkitGenerateKeyRequest)
                if (window.HTMLMediaElement) {{
                    if (!HTMLMediaElement.prototype.webkitGenerateKeyRequest) {{
                        HTMLMediaElement.prototype.webkitGenerateKeyRequest = makeNative(function webkitGenerateKeyRequest(keySystem, initData) {{
                            setTimeout(() => {{
                                try {{
                                    const evt = new CustomEvent('webkitneedkey', {{ detail: {{ keySystem: keySystem, initData: initData }} }});
                                    this.dispatchEvent(evt);
                                }} catch(e) {{}}
                            }}, 10);
                        }}, 'webkitGenerateKeyRequest', 2);
                    }}
                    if (!HTMLMediaElement.prototype.webkitAddKey) {{
                        HTMLMediaElement.prototype.webkitAddKey = makeNative(function webkitAddKey(keySystem, key, initData, sessionId) {{
                            return;
                        }}, 'webkitAddKey', 4);
                    }}
                    if (!HTMLMediaElement.prototype.webkitCancelKeyRequest) {{
                        HTMLMediaElement.prototype.webkitCancelKeyRequest = makeNative(function webkitCancelKeyRequest(keySystem, sessionId) {{
                            return;
                        }}, 'webkitCancelKeyRequest', 2);
                    }}
                    if (typeof window.WebKitMediaKeys === 'undefined') {{
                        window.WebKitMediaKeys = makeNative(class WebKitMediaKeys {{
                            constructor(keySystem) {{
                                this.keySystem = keySystem;
                            }}
                            static isTypeSupported(keySystem, type) {{
                                return true;
                            }}
                            createSession(type, initData) {{
                                return new MockMediaKeySession();
                            }}
                        }}, 'WebKitMediaKeys');
                        window.WebKitMediaKeys.isTypeSupported = makeNative((keySystem, type) => true, 'isTypeSupported', 2);
                    }}
                }}

                // Core Standard EME Hook
                const patchedRequestMediaKeySystemAccess = makeNative(async function requestMediaKeySystemAccess(keySystem, supportedConfigurations) {{
                    if (!keySystem || typeof keySystem !== 'string') {{
                        throw new TypeError("Failed to execute 'requestMediaKeySystemAccess' on 'Navigator': 1 argument required, but only 0 present.");
                    }}
                    if (!supportedConfigurations || !Array.isArray(supportedConfigurations) || supportedConfigurations.length === 0) {{
                        throw new TypeError("Failed to execute 'requestMediaKeySystemAccess' on 'Navigator': The provided value is not of type '(sequence<MediaKeySystemConfiguration> or MediaKeySystemConfiguration)'.");
                    }}

                    const ks = keySystem.toLowerCase().trim();

                    // Recognized Key Systems
                    const isClearKey = ks === 'org.w3.clearkey';
                    const isWidevine = ks === 'com.widevine.alpha';
                    const isPlayReady = ks.startsWith('com.microsoft.playready');
                    const isFairPlay = ks.startsWith('com.apple.fps');

                    // If native browser CDM is available (Spotify real playback), delegate to real C++ CDM
                    if (typeof origRequestAccess === 'function' && (isWidevine || isClearKey)) {{
                        try {{
                            const realAccess = await origRequestAccess.call(navigator, keySystem, supportedConfigurations);
                            if (realAccess) {{
                                return realAccess;
                            }}
                        }} catch (realErr) {{
                            // Only fallback to mock if native CDM is not yet loaded for this configuration
                        }}
                    }}

                    if (!isClearKey && !isWidevine && !isPlayReady && !isFairPlay) {{
                        if (typeof origRequestAccess === 'function') {{
                            return origRequestAccess.call(navigator, keySystem, supportedConfigurations);
                        }}
                        throw new DOMException(`Unsupported keySystem: ${{keySystem}}`, 'NotSupportedError');
                    }}

                    // Match Configuration
                    for (const candidate of supportedConfigurations) {{
                        const matched = {{
                            initDataTypes: candidate.initDataTypes ? [...candidate.initDataTypes] : ['cenc'],
                            distinctiveIdentifier: candidate.distinctiveIdentifier || 'not-allowed',
                            persistentState: candidate.persistentState || 'not-allowed',
                            sessionTypes: candidate.sessionTypes ? [...candidate.sessionTypes] : ['temporary']
                        }};

                        if (candidate.videoCapabilities && Array.isArray(candidate.videoCapabilities) && candidate.videoCapabilities.length > 0) {{
                            matched.videoCapabilities = candidate.videoCapabilities.map(v => ({{
                                contentType: v.contentType || 'video/mp4; codecs="avc1.42E01E"',
                                robustness: v.robustness || (isWidevine ? 'SW_SECURE_CRYPTO' : (isPlayReady ? '3000' : '')),
                                encryptionScheme: v.encryptionScheme || (isFairPlay ? 'sinf' : 'cenc')
                            }}));
                        }}

                        if (candidate.audioCapabilities && Array.isArray(candidate.audioCapabilities) && candidate.audioCapabilities.length > 0) {{
                            matched.audioCapabilities = candidate.audioCapabilities.map(a => ({{
                                contentType: a.contentType || 'audio/mp4; codecs="mp4a.40.2"',
                                robustness: a.robustness || (isWidevine ? 'SW_SECURE_CRYPTO' : ''),
                                encryptionScheme: a.encryptionScheme || (isFairPlay ? 'sinf' : 'cenc')
                            }}));
                        }}

                        return new MockMediaKeySystemAccess(keySystem, matched);
                    }}

                    throw new DOMException("None of the requested configurations were supported.", "NotSupportedError");
                }}, 'requestMediaKeySystemAccess', 2);

                const navProto = Object.getPrototypeOf(navigator) || Navigator.prototype;
                Object.defineProperty(navProto, 'requestMediaKeySystemAccess', {{
                    value: patchedRequestMediaKeySystemAccess,
                    writable: true,
                    configurable: true,
                    enumerable: true
                }});
                Object.defineProperty(navigator, 'requestMediaKeySystemAccess', {{
                    value: patchedRequestMediaKeySystemAccess,
                    writable: true,
                    configurable: true,
                    enumerable: true
                }});

            }} catch(drmErr) {{
                console.debug('DRM EME patch error:', drmErr);
            }}
        }})();
        """

    @staticmethod
    def _generate_worker_patch(
        nav_platform: str, nav_app_version: str, primary_locale: str, langs_list_json: str,
        hardware_concurrency: int, device_memory: int, webgl_vendor: str, webgl_renderer: str,
        target_os: str = "windows", enable_webgl_spoof: bool = True
    ) -> str:
        os_clean = (target_os or "windows").lower()
        max_tex = 32768 if (os_clean == "linux" and "NVIDIA" in webgl_vendor.upper()) else 16384
        webgl_worker_code = f"""
                    if (typeof WebGLRenderingContext !== 'undefined') {{
                        WebGLRenderingContext.prototype.getParameter = function(p) {{
                            if (p === 37445 || p === 0x9245) return "{webgl_vendor}";
                            if (p === 37446 || p === 0x9246) return "{webgl_renderer}";
                            return {max_tex};
                        }};
                    }}
                    if (typeof WebGL2RenderingContext !== 'undefined') {{
                        WebGL2RenderingContext.prototype.getParameter = function(p) {{
                            if (p === 37445 || p === 0x9245) return "{webgl_vendor}";
                            if (p === 37446 || p === 0x9246) return "{webgl_renderer}";
                            return {max_tex};
                        }};
                    }}
        """ if enable_webgl_spoof else ""

        return f"""
        // 11. Worker & SharedWorker Interception Scope
        (function() {{
            const workerPatchScript = `
                try {{
                    Object.defineProperty(self.navigator, 'platform', {{ get: () => "{nav_platform}", configurable: true }});
                    Object.defineProperty(self.navigator, 'appVersion', {{ get: () => "{nav_app_version}", configurable: true }});
                    Object.defineProperty(self.navigator, 'language', {{ get: () => "{primary_locale}", configurable: true }});
                    Object.defineProperty(self.navigator, 'languages', {{ get: () => Object.freeze({langs_list_json}), configurable: true }});
                    Object.defineProperty(self.navigator, 'hardwareConcurrency', {{ get: () => {hardware_concurrency}, configurable: true }});
                    Object.defineProperty(self.navigator, 'deviceMemory', {{ get: () => {device_memory}, configurable: true }});
                    {webgl_worker_code}
                }} catch(e) {{}}
            `;

            if (window.Worker) {{
                const OrigWorker = window.Worker;
                window.Worker = makeNative(function Worker(scriptURL, options) {{
                    try {{
                        const urlStr = (scriptURL && typeof scriptURL === 'object' && scriptURL.href) ? scriptURL.href : String(scriptURL || '');
                        if (urlStr) {{
                            const blob = new Blob([workerPatchScript + '\\ntry {{ importScripts("' + urlStr + '"); }} catch(e){{}}'], {{ type: 'application/javascript' }});
                            return new OrigWorker(URL.createObjectURL(blob), options);
                        }}
                    }} catch(e) {{}}
                    return new OrigWorker(scriptURL, options);
                }}, 'Worker');
                window.Worker.prototype = OrigWorker.prototype;
            }}
        }})();
        """

    @staticmethod
    def _generate_webrtc_patch(webrtc_mode: str, spoofed_ip: str = "") -> str:
        return f"""
        // 12. WebRTC & IFrame Comprehensive Isolation
        (function() {{
            const mode = "{webrtc_mode}";
            const spoofedIP = "{spoofed_ip}";

            const sanitizeSDP = function(sdp) {{
                if (!sdp || typeof sdp !== 'string') return sdp;
                let clean = sdp
                    .replace(/a=candidate:[^\\r\\n]*typ host[^\\r\\n]*\\r\\n/gi, '')
                    .replace(/a=candidate:[^\\r\\n]*(10\\.\\d+|172\\.(1[6-9]|2[0-9]|3[01])\\.|192\\.168\\.|127\\.0\\.0\\.1)[^\\r\\n]*\\r\\n/gi, '');
                if (spoofedIP) {{
                    clean = clean.replace(/\\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.){{3}}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\b/g, function(match) {{
                        if (match === '0.0.0.0' || match === '127.0.0.1' || match.startsWith('10.') || match.startsWith('192.168.') || match.startsWith('172.')) {{
                            return match;
                        }}
                        return spoofedIP;
                    }});
                }}
                return clean;
            }};

            const isLeakedCandidate = function(candStr) {{
                if (!candStr || typeof candStr !== 'string') return false;
                if (candStr.includes('typ host') || /10\\.\\d+|172\\.(1[6-9]|2\\d|3[01])\\.|192\\.168\\.|127\\.0\\.0\\.1/.test(candStr)) {{
                    return true;
                }}
                return false;
            }};

            const patchWindowWebRTC = function(win) {{
                if (!win) return;
                if (mode === "disabled") {{
                    try {{
                        delete win.RTCPeerConnection;
                        delete win.webkitRTCPeerConnection;
                        delete win.RTCSessionDescription;
                        delete win.RTCIceCandidate;
                        delete win.RTCDataChannel;
                        Object.defineProperty(win, 'RTCPeerConnection', {{
                            get: makeNative(() => undefined, 'get RTCPeerConnection'),
                            set: makeNative(() => {{}}, 'set RTCPeerConnection'),
                            configurable: true
                        }});
                        Object.defineProperty(win, 'webkitRTCPeerConnection', {{
                            get: makeNative(() => undefined, 'get webkitRTCPeerConnection'),
                            set: makeNative(() => {{}}, 'set webkitRTCPeerConnection'),
                            configurable: true
                        }});
                    }} catch (e) {{}}

                    if (win.navigator && win.navigator.mediaDevices) {{
                        try {{
                            win.navigator.mediaDevices.getUserMedia = makeNative(function getUserMedia() {{
                                return Promise.reject(new DOMException("Permission denied", "NotAllowedError"));
                            }}, 'getUserMedia');
                        }} catch (e) {{}}
                    }}
                }} else if (mode === "altered") {{
                    if (win.RTCPeerConnection) {{
                        const OrigPC = win.RTCPeerConnection;
                        const PatchedPC = makeNative(function RTCPeerConnection(config, constraints) {{
                            const cleanConfig = Object.assign({{}}, config);
                            if (cleanConfig.iceServers) {{
                                cleanConfig.iceServers = [];
                            }}
                            cleanConfig.iceTransportPolicy = 'relay';

                            const pc = new OrigPC(cleanConfig, constraints);

                            // Intercept createOffer & createAnswer
                            const origCreateOffer = pc.createOffer;
                            if (origCreateOffer) {{
                                pc.createOffer = makeNative(function createOffer() {{
                                    return origCreateOffer.apply(this, arguments).then(offer => {{
                                        if (offer && offer.sdp) {{
                                            offer.sdp = sanitizeSDP(offer.sdp);
                                        }}
                                        return offer;
                                    }});
                                }}, 'createOffer');
                            }}

                            const origCreateAnswer = pc.createAnswer;
                            if (origCreateAnswer) {{
                                pc.createAnswer = makeNative(function createAnswer() {{
                                    return origCreateAnswer.apply(this, arguments).then(answer => {{
                                        if (answer && answer.sdp) {{
                                            answer.sdp = sanitizeSDP(answer.sdp);
                                        }}
                                        return answer;
                                    }});
                                }}, 'createAnswer');
                            }}

                            // Intercept setLocalDescription
                            const origSetLocalDesc = pc.setLocalDescription;
                            if (origSetLocalDesc) {{
                                pc.setLocalDescription = makeNative(function setLocalDescription(desc) {{
                                    if (desc && desc.sdp) {{
                                        desc.sdp = sanitizeSDP(desc.sdp);
                                    }}
                                    return origSetLocalDesc.apply(this, arguments);
                                }}, 'setLocalDescription');
                            }}

                            // Intercept localDescription getter
                            try {{
                                const origLocalDescDesc = Object.getOwnPropertyDescriptor(OrigPC.prototype, 'localDescription');
                                if (origLocalDescDesc && origLocalDescDesc.get) {{
                                    const origGetLocal = origLocalDescDesc.get;
                                    Object.defineProperty(pc, 'localDescription', {{
                                        get: makeNative(function localDescription() {{
                                            const desc = origGetLocal.apply(this, arguments);
                                            if (desc && desc.sdp) {{
                                                desc.sdp = sanitizeSDP(desc.sdp);
                                            }}
                                            return desc;
                                        }}, 'get localDescription'),
                                        configurable: true
                                    }});
                                }}
                            }} catch(e) {{}}

                            // Intercept onicecandidate listener
                            let customIceCandidateHandler = null;
                            Object.defineProperty(pc, 'onicecandidate', {{
                                get: makeNative(() => customIceCandidateHandler, 'get onicecandidate'),
                                set: makeNative((fn) => {{
                                    if (typeof fn !== 'function') {{
                                        customIceCandidateHandler = null;
                                        return;
                                    }}
                                    customIceCandidateHandler = fn;
                                    OrigPC.prototype.addEventListener.call(pc, 'icecandidate', function(evt) {{
                                        if (!evt.candidate) {{
                                            fn.call(pc, evt);
                                            return;
                                        }}
                                        const cStr = evt.candidate.candidate || '';
                                        if (isLeakedCandidate(cStr)) {{
                                            return; // Drop host/private candidate
                                        }}
                                        fn.call(pc, evt);
                                    }});
                                }}, 'set onicecandidate'),
                                configurable: true,
                                enumerable: true
                            }});

                            // Intercept addEventListener for 'icecandidate'
                            const origAddEventListener = pc.addEventListener;
                            pc.addEventListener = makeNative(function addEventListener(type, listener, options) {{
                                if (type === 'icecandidate' && typeof listener === 'function') {{
                                    const wrappedListener = function(evt) {{
                                        if (!evt.candidate) {{
                                            return listener.call(this, evt);
                                        }}
                                        const cStr = evt.candidate.candidate || '';
                                        if (isLeakedCandidate(cStr)) {{
                                            return;
                                        }}
                                        return listener.call(this, evt);
                                    }};
                                    return origAddEventListener.call(this, type, wrappedListener, options);
                                }}
                                return origAddEventListener.apply(this, arguments);
                            }}, 'addEventListener');

                            // Intercept getStats() to prevent IP leaks via stats reports
                            const origGetStats = pc.getStats;
                            if (origGetStats) {{
                                pc.getStats = makeNative(async function getStats(selector) {{
                                    const stats = await origGetStats.apply(this, arguments);
                                    if (!stats || typeof stats.forEach !== 'function') return stats;
                                    const sanitized = new Map();
                                    stats.forEach((report, key) => {{
                                        if (report && (report.type === 'local-candidate' || report.type === 'remote-candidate')) {{
                                            const repObj = Object.assign({{}}, report);
                                            if (repObj.ip && isLeakedCandidate(repObj.ip)) {{
                                                repObj.ip = spoofedIP || '127.0.0.1';
                                                repObj.address = spoofedIP || '127.0.0.1';
                                            }}
                                            if (repObj.candidateType === 'host') {{
                                                repObj.candidateType = 'relay';
                                            }}
                                            sanitized.set(key, Object.freeze(repObj));
                                        }} else {{
                                            sanitized.set(key, report);
                                        }}
                                    }});
                                    return sanitized;
                                }}, 'getStats');
                            }}

                            return pc;
                        }}, 'RTCPeerConnection');

                        PatchedPC.prototype = OrigPC.prototype;
                        try {{
                            win.RTCPeerConnection = PatchedPC;
                            win.webkitRTCPeerConnection = PatchedPC;
                        }} catch (e) {{}}

                        if (win.RTCIceCandidate) {{
                            const OrigCandidate = win.RTCIceCandidate;
                            const PatchedCandidate = makeNative(function RTCIceCandidate(candidateInitDict) {{
                                if (candidateInitDict && candidateInitDict.candidate) {{
                                    candidateInitDict.candidate = sanitizeSDP(candidateInitDict.candidate);
                                }}
                                return new OrigCandidate(candidateInitDict);
                            }}, 'RTCIceCandidate');
                            PatchedCandidate.prototype = OrigCandidate.prototype;
                            try {{ win.RTCIceCandidate = PatchedCandidate; }} catch(e) {{}}
                        }}
                    }}
                }}
            }};

            patchWindowWebRTC(window);

            try {{
                const origContentWindow = Object.getOwnPropertyDescriptor(HTMLIFrameElement.prototype, 'contentWindow');
                if (origContentWindow && origContentWindow.get) {{
                    Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {{
                        get: makeNative(function contentWindow() {{
                            const win = origContentWindow.get.apply(this, arguments);
                            if (win) patchWindowWebRTC(win);
                            return win;
                        }}, 'get contentWindow')
                    }});
                }}
            }} catch(e) {{}}
        }})();
        """

    # ---------------------------------------------------------
    # Camoufox C++ Native Anti-Detect Helper Infrastructure
    # ---------------------------------------------------------

    @staticmethod
    def derive_camoufox_seeds(profile: Dict[str, Any], profile_id: str) -> Dict[str, int]:
        """
        Derive deterministic 32-bit seeds (1 .. 4_294_967_295) for Camoufox C++
        anti-fingerprinting features (audio, fonts spacing, canvas).
        Ensures consistent fingerprints across repeat launches of the same profile
        while providing unique fingerprints between different profiles.
        """
        stealth_cfg = profile.get("stealth", {}) if isinstance(profile, dict) else {}
        seed_str = str(stealth_cfg.get("noise_seed") or profile_id).strip()
        if not seed_str:
            seed_str = "soxbot_default_seed"

        def _to_uint32(salt: str) -> int:
            h = hashlib.sha256(f"{salt}_{seed_str}".encode("utf-8")).hexdigest()
            val = int(h[:8], 16)
            return (val % 4_294_967_294) + 1  # Guaranteed 1 .. 2^32 - 1

        audio_noise_enabled = stealth_cfg.get("audio_noise", True)
        font_noise_enabled = stealth_cfg.get("font_fingerprint_noise", True)
        canvas_noise_enabled = stealth_cfg.get("canvas_noise", True)

        seeds: Dict[str, int] = {}
        if audio_noise_enabled:
            seeds["audio:seed"] = _to_uint32("audio")
        if font_noise_enabled:
            seeds["fonts:spacing_seed"] = _to_uint32("fonts_spacing")
        if canvas_noise_enabled:
            seeds["canvas:seed"] = _to_uint32("canvas")

        return seeds

    @staticmethod
    def get_deterministic_camoufox_fonts(target_os: str, seed_str: str, locale: str = "en-US") -> List[str]:
        """
        Generate a deterministic, realistic font subset for the target OS and locale.
        Always includes essential & marker fonts plus a deterministic sample of OS fonts,
        enriched with regional language fonts matching the profile's locale.
        """
        t_os = (target_os or "windows").lower()
        if t_os in ["mac", "macos", "darwin", "ios"]:
            target_norm = "macos"
        elif t_os in ["lin", "linux", "android"]:
            target_norm = "linux"
        else:
            target_norm = "windows"

        # Deterministic random generator for this profile
        seed_hash = hashlib.sha256(f"fonts_{target_norm}_{seed_str}".encode("utf-8")).hexdigest()
        seed_int = int(seed_hash[:8], 16)
        rng = random.Random(seed_int)

        # Load base OS fonts from Camoufox bundle if available
        full_list: List[str] = []
        try:
            from camoufox.fingerprints import _load_os_fonts
            os_fonts_data = _load_os_fonts()
            c_key = {"macos": "mac", "windows": "win", "linux": "lin"}.get(target_norm, "win")
            full_list = list(os_fonts_data.get(c_key, []))
        except Exception:
            pass

        if not full_list:
            if target_norm == "windows":
                full_list = [
                    "Arial", "Arial Black", "Bahnschrift", "Calibri", "Calibri Light", "Cambria",
                    "Cambria Math", "Candara", "Comic Sans MS", "Consolas", "Constantia", "Corbel",
                    "Courier New", "Ebrima", "Franklin Gothic Medium", "Gabriola", "Gadugi", "Georgia",
                    "Impact", "Ink Free", "Javanese Text", "Leelawadee UI", "Lucida Console",
                    "Lucida Sans Unicode", "Malgun Gothic", "Marlett", "Microsoft Himalaya",
                    "Microsoft JhengHei", "Microsoft New Tai Lue", "Microsoft PhagsPa",
                    "Microsoft Sans Serif", "Microsoft Tai Le", "Microsoft YaHei", "Microsoft Yi Baiti",
                    "MingLiU-ExtB", "Mongolian Baiti", "Myanmar Text", "NSimSun", "Nirmala UI",
                    "Palatino Linotype", "Segoe MDL2 Assets", "Segoe Print", "Segoe Script",
                    "Segoe UI", "Segoe UI Emoji", "Segoe UI Historic", "Segoe UI Symbol",
                    "SimSun", "Sitka Text", "Sylfaen", "Symbol", "Tahoma", "Times New Roman",
                    "Trebuchet MS", "Twemoji Mozilla", "Verdana", "Webdings", "Wingdings", "Yu Gothic"
                ]
            elif target_norm == "macos":
                full_list = [
                    "American Typewriter", "Andale Mono", "Apple Braille", "Apple Chancery",
                    "Apple Color Emoji", "Apple SD Gothic Neo", "Apple Symbols", "Arial",
                    "Arial Black", "Arial Narrow", "Arial Rounded MT Bold", "Avenir",
                    "Avenir Next", "Baskerville", "Big Caslon", "Bodoni 72", "Bradley Hand",
                    "Brush Script MT", "Chalkboard", "Chalkboard SE", "Chalkduster", "Charter",
                    "Cochin", "Comic Sans MS", "Copperplate", "Courier", "Courier New",
                    "DIN Alternate", "DIN Condensed", "Didot", "Futura", "Geneva", "Georgia",
                    "Gill Sans", "Helvetica", "Helvetica Neue", "Herculanum", "Hiragino Sans",
                    "Hoefler Text", "Impact", "Lucida Grande", "Luminari", "Marker Felt", "Menlo",
                    "Monaco", "Noteworthy", "Optima", "Palatino", "Papyrus", "Phosphate",
                    "PingFang HK", "PingFang SC", "PingFang TC", "Rockwell", "SF Pro", "Savoye LET",
                    "SignPainter", "Skia", "Snell Roundhand", "Songti SC", "Sukhumvit Set",
                    "Symbol", "Tahoma", "Times", "Times New Roman", "Trattatello", "Trebuchet MS",
                    "Verdana", "Zapfino"
                ]
            else:
                full_list = [
                    "Arimo", "Cousine", "Noto Naskh Arabic", "Noto Sans Devanagari",
                    "Noto Sans Hebrew", "Noto Sans JP", "Noto Sans KR", "Noto Sans SC",
                    "Noto Sans TC", "Noto Serif", "STIX Two Math", "Tinos", "Twemoji Mozilla"
                ]

        essential_map = {
            "windows": [
                "Arial", "Times New Roman", "Courier New", "Verdana", "Georgia",
                "Trebuchet MS", "Tahoma", "Segoe UI", "Calibri", "Cambria Math",
                "Nirmala UI", "Consolas"
            ],
            "macos": [
                "Arial", "Helvetica", "Times New Roman", "Courier New", "Verdana",
                "Georgia", "Trebuchet MS", "Tahoma", "Helvetica Neue", "Lucida Grande",
                "Menlo", "Monaco", "Geneva", "PingFang HK", "PingFang SC", "PingFang TC"
            ],
            "linux": [
                "Arimo", "Cousine", "Tinos", "Twemoji Mozilla",
                "Noto Sans Devanagari", "Noto Sans JP", "Noto Sans KR",
                "Noto Sans SC", "Noto Sans TC"
            ]
        }
        marker_map = {
            "windows": ["Segoe UI", "Calibri", "Cambria Math", "Nirmala UI", "Consolas"],
            "macos": ["Helvetica Neue", "Lucida Grande", "PingFang SC", "PingFang TC", "SF Pro"],
            "linux": ["Arimo", "Cousine", "Tinos", "Twemoji Mozilla"]
        }

        essential = set(essential_map.get(target_norm, essential_map["windows"]))
        markers = marker_map.get(target_norm, marker_map["windows"])

        result = [f for f in full_list if f in essential]
        non_essential = [f for f in full_list if f not in essential]

        # Deterministic sample percentage (between 45% and 75%)
        pct = 45 + rng.randint(0, 30)
        count = round((pct / 100.0) * len(non_essential))
        if count < len(non_essential):
            selected = rng.sample(non_essential, count)
        else:
            selected = non_essential
        result.extend(selected)

        # Ensure marker fonts
        for m in markers:
            if m not in result:
                result.append(m)

        # Regional Locale Font Enrichment
        loc = (locale or "en-US").lower()
        regional_fonts: List[str] = []
        if "ja" in loc:
            regional_fonts = ["MS Gothic", "MS PGothic", "MS UI Gothic", "Yu Gothic", "Yu Gothic UI", "Meiryo", "Meiryo UI", "Hiragino Sans", "Hiragino Kaku Gothic ProN"]
        elif "zh" in loc:
            regional_fonts = ["Microsoft YaHei", "Microsoft YaHei UI", "SimSun", "NSimSun", "SimHei", "KaiTi", "FangSong", "PingFang SC", "PingFang TC"]
        elif "ko" in loc:
            regional_fonts = ["Malgun Gothic", "Malgun Gothic Semilight", "Gulim", "Dotum", "Batang", "Apple SD Gothic Neo"]
        elif "ru" in loc or "uk" in loc:
            regional_fonts = ["Arial", "Times New Roman", "Calibri", "Segoe UI", "Georgia"]
        elif "ar" in loc:
            regional_fonts = ["Segoe UI", "Tahoma", "Traditional Arabic", "Arabic Typesetting", "Geeza Pro", "Damascus"]
        elif "he" in loc:
            regional_fonts = ["David", "FrankRuehl", "Gisha", "Levenim MT", "Narkisim", "Rod"]
        elif "th" in loc:
            regional_fonts = ["Leelawadee UI", "Tahoma", "Thonburi", "Ayuthaya"]

        for rf in regional_fonts:
            if rf not in result:
                result.append(rf)

        return list(dict.fromkeys(result))

    @staticmethod
    def get_deterministic_camoufox_voices(target_os: str, seed_str: str, locale: str = "en-US") -> List[Any]:
        """
        Generate deterministic Web Speech Synthesis TTS voice subset matching target OS and locale.
        """
        t_os = (target_os or "windows").lower()
        if t_os in ["mac", "macos", "darwin", "ios"]:
            target_norm = "macos"
        elif t_os in ["lin", "linux", "android"]:
            target_norm = "linux"
        else:
            target_norm = "windows"

        try:
            from camoufox.fingerprints import _load_os_voices, _ESSENTIAL_VOICES_WINDOWS, _ESSENTIAL_VOICES_MACOS, _VOICE_URI_PREFIX
            os_voices_data = _load_os_voices()
            c_key = {"macos": "mac", "windows": "win", "linux": "lin"}.get(target_norm, "win")
            raw_voices = os_voices_data.get(c_key, [])
            if not raw_voices:
                return []

            seed_hash = hashlib.sha256(f"voices_{target_norm}_{seed_str}".encode("utf-8")).hexdigest()
            seed_int = int(seed_hash[:8], 16)
            rng = random.Random(seed_int)

            if target_norm == "windows":
                essential_names = set(_ESSENTIAL_VOICES_WINDOWS)
            elif target_norm == "macos":
                essential_names = set(_ESSENTIAL_VOICES_MACOS)
            else:
                essential_names = set()

            essential_voices = [v for v in raw_voices if v[0] in essential_names]
            non_essential_voices = [v for v in raw_voices if v[0] not in essential_names]

            loc_prefix = (locale or "en-US").split("-")[0].lower()
            locale_matched = [v for v in non_essential_voices if v[1].lower().startswith(loc_prefix)]
            other_voices = [v for v in non_essential_voices if not v[1].lower().startswith(loc_prefix)]

            pct = 40 + rng.randint(0, 35)
            other_count = round((pct / 100.0) * len(other_voices))
            selected_other = rng.sample(other_voices, min(other_count, len(other_voices)))

            chosen = essential_voices + locale_matched + selected_other
            prefix = _VOICE_URI_PREFIX.get(c_key, 'urn:moz-tts:sapi:')
            
            result = []
            for name, lang, vtype in chosen:
                slug = name.lower().replace(' ', '.').replace('(', '').replace(')', '').replace('-', '.')
                uri = f"{prefix}{slug}"
                is_local = (vtype == 'local')
                result.append({
                    'voiceUri': uri,
                    'voiceURI': uri,
                    'name': name,
                    'lang': lang,
                    'isLocalService': is_local,
                    'localService': is_local,
                    'isDefault': False,
                    'default': False,
                })
            if result:
                result[0]['isDefault'] = True
                result[0]['default'] = True
            return result
        except Exception:
            return []

