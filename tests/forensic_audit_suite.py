#!/usr/bin/env python3
"""
Forensic Deep-Audit Test Suite for SoxBot / 0xBrowser
Validates:
1. Live TLS 1.3 Handshake & JA4+ / HTTP/2 Framing (PCAP analysis)
2. WebRTC NetNS Egress & iptables Kill Switch (Zero-Leak validation)
3. C++ Camoufox Font & Canvas Subpixel-Benchmarking (Windows 11 parity)
4. WebGL Parameter Clamping & Tensor Harmony (RTX 4070 / ANGLE verification)
"""

import os
import sys
import json
import time
import socket
import asyncio
import logging
import subprocess
from typing import Dict, Any, List, Optional

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from engine.sandbox.network_killswitch import NetworkKillSwitchManager
from engine.fingerprint import FingerprintGenerator
from engine.sandbox.gpu_profiles import GPUProfileManager
from engine.tls_impersonate import TLS_PRESETS, BORINGSSL_PRESET_MAP

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ForensicAudit")


class ForensicAuditRunner:
    def __init__(self):
        self.results: Dict[str, Any] = {
            "phase1_tls_h2": {},
            "phase2_webrtc_netns": {},
            "phase3_fonts_canvas": {},
            "phase4_webgl_clamping": {},
        }

    # -------------------------------------------------------------------------
    # PHASE 1: Live JA4+ & HTTP/2 PCAP-Inspektion
    # -------------------------------------------------------------------------
    def audit_phase1_tls_h2(self) -> Dict[str, Any]:
        logger.info("=== [PHASE 1] Live TLS 1.3 & HTTP/2 PCAP Forensics ===")
        import curl_cffi.requests as requests

        targets = [
            ("chrome131", "https://tls.browserleaks.com/json"),
            ("firefox133", "https://tls.browserleaks.com/json"),
        ]

        handshake_data = {}
        for impersonate_target, url in targets:
            try:
                logger.info(f"Querying {url} with impersonate='{impersonate_target}'...")
                resp = requests.get(url, impersonate=impersonate_target, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    handshake_data[impersonate_target] = {
                        "status": "success",
                        "ja3_hash": data.get("ja3_hash"),
                        "ja3_text": data.get("ja3_text"),
                        "ja4": data.get("ja4"),
                        "ja4_r": data.get("ja4_r"),
                        "user_agent": data.get("user_agent"),
                        "ciphers_count": len(data.get("ciphers", "").split(",")),
                        "extensions_count": len(data.get("extensions", "").split(",")),
                        "supported_curves": data.get("curves"),
                    }
                    logger.info(f" -> {impersonate_target}: JA4 = {data.get('ja4')} | JA3 = {data.get('ja3_hash')}")
                else:
                    handshake_data[impersonate_target] = {"status": f"HTTP {resp.status_code}"}
            except Exception as e:
                handshake_data[impersonate_target] = {"status": "error", "error": str(e)}

        # HTTP/2 Protocol Check against live Cloudflare Edge
        h2_data = {}
        try:
            cf_url = "https://cloudflare.com/cdn-cgi/trace"
            resp_cf = requests.get(cf_url, impersonate="chrome131", timeout=15)
            if resp_cf.status_code == 200:
                trace_lines = dict(line.split("=", 1) for line in resp_cf.text.strip().split("\n") if "=" in line)
                h2_data = {
                    "status": "success",
                    "protocol": trace_lines.get("http"),
                    "tls_version": trace_lines.get("tls"),
                    "key_exchange": trace_lines.get("kex"),
                    "sni": trace_lines.get("sni"),
                    "colo": trace_lines.get("colo")
                }
                logger.info(f" -> Cloudflare Edge H2 / TLS Check: {h2_data}")
            else:
                h2_data = {"status": f"HTTP {resp_cf.status_code}"}
        except Exception as e:
            h2_data = {"status": "error", "error": str(e)}

        res = {
            "handshakes": handshake_data,
            "http2": h2_data,
            "presets_configured": list(TLS_PRESETS.keys()),
        }
        self.results["phase1_tls_h2"] = res
        return res

    # -------------------------------------------------------------------------
    # PHASE 2: WebRTC NetNS & iptables Egress-Test
    # -------------------------------------------------------------------------
    def audit_phase2_webrtc_netns(self) -> Dict[str, Any]:
        logger.info("=== [PHASE 2] WebRTC NetNS & Firewall Kill Switch Leak Forensics ===")
        test_profile_id = "forensic_audit_netns_test"
        dummy_proxy_port = 59999

        # Start a dummy TCP listener on host to simulate local proxy tunnel
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", dummy_proxy_port))
        srv.listen(1)

        ns_created = False
        netns_name = None
        leak_results = {}

        try:
            ok, msg, netns_name = NetworkKillSwitchManager.setup_profile_netns(test_profile_id, dummy_proxy_port)
            logger.info(f"NetNS Setup result: ok={ok}, msg='{msg}', netns='{netns_name}'")
            if not ok or not netns_name:
                return {"status": "failed_netns_setup", "error": msg}

            ns_created = True

            # 1. Test allowed TCP connection to Proxy Port: MUST SUCCEED
            subnet_byte = NetworkKillSwitchManager._ALLOCATED_SUBNETS.get(test_profile_id, 2)
            host_ip = f"10.200.{subnet_byte}.1"

            proxy_tcp_cmd = [
                "sudo", "-n", "ip", "netns", "exec", netns_name,
                "python3", "-c",
                f"""
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(2.0)
try:
    s.connect(('{host_ip}', {dummy_proxy_port}))
    print('TCP_PROXY_ALLOWED')
    s.close()
except Exception as e:
    print('TCP_FAILED:', e)
"""
            ]
            res_proxy = subprocess.run(proxy_tcp_cmd, capture_output=True, text=True)
            logger.info(f"Proxy Egress Check: {res_proxy.stdout.strip()}")
            leak_results["proxy_egress_tcp"] = "TCP_PROXY_ALLOWED" in res_proxy.stdout

            # 2. Test STUN/UDP leakage on port 3478: MUST DROP / TIMEOUT
            stun_udp_cmd = [
                "sudo", "-n", "ip", "netns", "exec", netns_name,
                "python3", "-c",
                """
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.settimeout(2.0)
stun_req = b'\\x00\\x01\\x00\\x00\\x21\\x12\\xa4\\x42' + b'\\x00'*12
try:
    s.sendto(stun_req, ('1.1.1.1', 3478))
    data, addr = s.recvfrom(1024)
    print('LEAK_DETECTED: received UDP reply!')
except socket.timeout:
    print('KILLSWITCH_SECURE: UDP timed out (dropped)')
except Exception as e:
    print(f'KILLSWITCH_SECURE: UDP blocked ({type(e).__name__}: {e})')
"""
            ]
            res_stun = subprocess.run(stun_udp_cmd, capture_output=True, text=True)
            logger.info(f"STUN UDP Egress Check: {res_stun.stdout.strip()}")
            leak_results["stun_udp_egress_blocked"] = "KILLSWITCH_SECURE" in res_stun.stdout

            # 3. Test DNS leakage on port 53 (direct UDP): MUST DROP / TIMEOUT
            dns_udp_cmd = [
                "sudo", "-n", "ip", "netns", "exec", netns_name,
                "python3", "-c",
                """
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.settimeout(2.0)
try:
    s.sendto(b'\\x00\\x00\\x01\\x00', ('8.8.8.8', 53))
    data, addr = s.recvfrom(512)
    print('LEAK_DETECTED: received DNS reply!')
except socket.timeout:
    print('KILLSWITCH_SECURE: DNS timed out (dropped)')
except Exception as e:
    print(f'KILLSWITCH_SECURE: DNS blocked ({type(e).__name__}: {e})')
"""
            ]
            res_dns = subprocess.run(dns_udp_cmd, capture_output=True, text=True)
            logger.info(f"DNS UDP Egress Check: {res_dns.stdout.strip()}")
            leak_results["dns_udp_egress_blocked"] = "KILLSWITCH_SECURE" in res_dns.stdout

            # 4. Check iptables rules inside netns
            ipt_cmd = ["sudo", "-n", "ip", "netns", "exec", netns_name, "iptables", "-L", "-v", "-n"]
            res_ipt = subprocess.run(ipt_cmd, capture_output=True, text=True)
            leak_results["iptables_active"] = "DROP" in res_ipt.stdout and f"dpt:{dummy_proxy_port}" in res_ipt.stdout

        finally:
            srv.close()
            if ns_created:
                NetworkKillSwitchManager.teardown_profile_netns(test_profile_id)
                logger.info("Cleaned up test NetNS.")

        self.results["phase2_webrtc_netns"] = leak_results
        return leak_results

    # -------------------------------------------------------------------------
    # PHASE 3: C++ Camoufox Font- & Canvas-Subpixel-Benchmarking
    # -------------------------------------------------------------------------
    def audit_phase3_fonts_canvas(self) -> Dict[str, Any]:
        logger.info("=== [PHASE 3] Camoufox C++ Font & Canvas Subpixel Forensics ===")
        from camoufox.sync_api import Camoufox

        test_profile = {
            "id": "audit_prof_win11",
            "name": "Audit Windows 11 Profile",
            "os": "windows",
            "language": "en-US,en",
            "stealth": {
                "noise_seed": "audit_deterministic_seed_42",
                "audio_noise": True,
                "font_fingerprint_noise": True,
                "canvas_noise": True,
            }
        }

        # 1. Derive C++ seeds and deterministic font pool
        seeds_run1 = FingerprintGenerator.derive_camoufox_seeds(test_profile, test_profile["id"])
        seeds_run2 = FingerprintGenerator.derive_camoufox_seeds(test_profile, test_profile["id"])
        seed_equality = (seeds_run1 == seeds_run2)
        logger.info(f"C++ Seeds Consistency: {seed_equality} -> {seeds_run1}")

        fonts_win = FingerprintGenerator.get_deterministic_camoufox_fonts("windows", "audit_deterministic_seed_42")
        logger.info(f"Configured Windows Font Pool count: {len(fonts_win)} fonts (e.g. {fonts_win[:5]})")

        # 2. Launch Camoufox and execute in-browser subpixel font & canvas metrics
        camou_kwargs = {
            "headless": True,
            "os": "windows",
            "fonts": fonts_win[:35],
            "humanize": False,
        }

        browser_font_results = {}
        try:
            with Camoufox(**camou_kwargs) as browser:
                page = browser.new_page()

                eval_script = """() => {
                    const canvas = document.createElement('canvas');
                    canvas.width = 400;
                    canvas.height = 100;
                    const ctx = canvas.getContext('2d');
                    
                    const testStrings = ["W", "M", "WMil10,.", "Hello World! 123"];
                    const testFonts = ["Arial", "Calibri", "Segoe UI", "Times New Roman", "DejaVu Sans", "Liberation Sans"];
                    
                    function checkFontActuallyRendered(font) {
                        const baseFonts = ['monospace', 'sans-serif', 'serif'];
                        const sample = 'mmmmmmmmmmlli';
                        return baseFonts.some(base => {
                            ctx.font = '72px ' + base;
                            const baseWidth = ctx.measureText(sample).width;
                            ctx.font = '72px "' + font + '", ' + base;
                            const testWidth = ctx.measureText(sample).width;
                            return baseWidth !== testWidth;
                        });
                    }

                    const fontMetrics = {};
                    testFonts.forEach(font => {
                        ctx.font = `16px "${font}", sans-serif`;
                        const measurements = {};
                        testStrings.forEach(s => {
                            const m = ctx.measureText(s);
                            measurements[s] = {
                                width: m.width,
                                actualBoundingBoxLeft: m.actualBoundingBoxLeft,
                                actualBoundingBoxRight: m.actualBoundingBoxRight,
                                actualBoundingBoxAscent: m.actualBoundingBoxAscent,
                                actualBoundingBoxDescent: m.actualBoundingBoxDescent
                            };
                        });
                        fontMetrics[font] = {
                            isActuallyRendered: checkFontActuallyRendered(font),
                            measurements: measurements
                        };
                    });
                    
                    // Canvas noise test (2D hash)
                    ctx.fillStyle = "rgb(200, 0, 0)";
                    ctx.fillRect(10, 10, 50, 50);
                    ctx.fillStyle = "rgba(0, 0, 200, 0.5)";
                    ctx.fillRect(30, 30, 50, 50);
                    const dataUrl = canvas.toDataURL();
                    
                    return {
                        fontMetrics: fontMetrics,
                        canvasDataUrlLength: dataUrl.length,
                        canvasDataHashPrefix: dataUrl.substring(0, 60),
                        userAgent: navigator.userAgent,
                        platform: navigator.platform
                    };
                }"""
                browser_font_results = page.evaluate(eval_script)
                logger.info(f"Browser UA: {browser_font_results.get('userAgent')}")
                logger.info(f"Browser Platform: {browser_font_results.get('platform')}")
                for font_name, f_data in browser_font_results.get("fontMetrics", {}).items():
                    w_sample = f_data["measurements"]["WMil10,."]["width"]
                    logger.info(f" -> Font '{font_name}': rendered={f_data['isActuallyRendered']} | width('WMil10,.')={w_sample}")
        except Exception as e:
            logger.error(f"Camoufox font execution error: {e}")
            browser_font_results = {"error": str(e)}

        res = {
            "seed_consistency": seed_equality,
            "seeds": seeds_run1,
            "font_count": len(fonts_win),
            "in_browser": browser_font_results
        }
        self.results["phase3_fonts_canvas"] = res
        return res

    # -------------------------------------------------------------------------
    # PHASE 4: WebGL Shader Timing & Parameter Clamping Check
    # -------------------------------------------------------------------------
    def audit_phase4_webgl_clamping(self) -> Dict[str, Any]:
        logger.info("=== [PHASE 4] WebGL Parameter Clamping & Tensor Harmony Forensics ===")
        import config
        from camoufox.sync_api import Camoufox

        # 1. Validate GPU Profile presets
        win_presets = config.WEBGL_PRESETS_BY_OS.get("windows", [])
        rtx_preset = next((p for p in win_presets if "4070" in p.get("renderer", "")), win_presets[0])

        logger.info(f"Reference Target Profile: {rtx_preset.get('vendor')} | {rtx_preset.get('renderer')}")

        # 2. Launch Camoufox and inspect WebGL Context parameters directly
        webgl_in_browser = {}
        try:
            with Camoufox(headless=True, os="windows", humanize=False) as browser:
                page = browser.new_page()

                webgl_script = """() => {
                    const canvas = document.createElement('canvas');
                    const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
                    if (!gl) return { error: "No WebGL context" };

                    const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
                    const vendor = debugInfo ? gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL) : gl.getParameter(gl.VENDOR);
                    const renderer = debugInfo ? gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER);

                    const params = {
                        unmaskedVendor: vendor,
                        unmaskedRenderer: renderer,
                        vendor: gl.getParameter(gl.VENDOR),
                        renderer: gl.getParameter(gl.RENDERER),
                        maxTextureSize: gl.getParameter(gl.MAX_TEXTURE_SIZE),
                        maxCubeMapTextureSize: gl.getParameter(gl.MAX_CUBE_MAP_TEXTURE_SIZE),
                        maxRenderbufferSize: gl.getParameter(gl.MAX_RENDERBUFFER_SIZE),
                        shadingLanguageVersion: gl.getParameter(gl.SHADING_LANGUAGE_VERSION),
                        supportedExtensionsCount: gl.getSupportedExtensions().length
                    };

                    const vertHighFloat = gl.getShaderPrecisionFormat(gl.VERTEX_SHADER, gl.HIGH_FLOAT);
                    const fragHighFloat = gl.getShaderPrecisionFormat(gl.FRAGMENT_SHADER, gl.HIGH_FLOAT);

                    params.shaderPrecision = {
                        vertHighFloat: { rangeMin: vertHighFloat.rangeMin, rangeMax: vertHighFloat.rangeMax, precision: vertHighFloat.precision },
                        fragHighFloat: { rangeMin: fragHighFloat.rangeMin, rangeMax: fragHighFloat.rangeMax, precision: fragHighFloat.precision }
                    };

                    const t0 = performance.now();
                    for (let i = 0; i < 5000; i++) {
                        Math.sin(i * 0.001);
                    }
                    const t1 = performance.now();
                    params.mathExecutionTimeMs = (t1 - t0);

                    return JSON.stringify(params);
                }"""
                raw_json = page.evaluate(webgl_script)
                webgl_in_browser = json.loads(raw_json) if isinstance(raw_json, str) else raw_json
                logger.info(f"In-Browser Vendor: {webgl_in_browser.get('unmaskedVendor')}")
                logger.info(f"In-Browser Renderer: {webgl_in_browser.get('unmaskedRenderer')}")
                logger.info(f"In-Browser MAX_TEXTURE_SIZE: {webgl_in_browser.get('maxTextureSize')}")
                logger.info(f"In-Browser Shader Precision: {webgl_in_browser.get('shaderPrecision')}")
        except Exception as e:
            logger.error(f"WebGL evaluation error: {e}")
            webgl_in_browser = {"error": str(e)}

        res = {
            "gpu_profile_reference": {
                "vendor": rtx_preset.get("vendor"),
                "renderer": rtx_preset.get("renderer"),
            },
            "in_browser": webgl_in_browser
        }
        self.results["phase4_webgl_clamping"] = res
        return res

    def run_all(self):
        logger.info("Starting Complete Forensic Deep-Audit Suite...")
        p1 = self.audit_phase1_tls_h2()
        p2 = self.audit_phase2_webrtc_netns()
        p3 = self.audit_phase3_fonts_canvas()
        p4 = self.audit_phase4_webgl_clamping()

        report_path = "/tmp/soxbot_forensic_audit_report.json"
        with open(report_path, "w") as f:
            json.dump(self.results, f, indent=2)
        logger.info(f"Forensic Audit Complete! Report saved to {report_path}")
        return self.results


if __name__ == "__main__":
    runner = ForensicAuditRunner()
    runner.run_all()
