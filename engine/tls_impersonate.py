import ssl
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("TLSSpoofer")

BORINGSSL_AVAILABLE = False
try:
    from curl_cffi.requests import AsyncSession, Session, BrowserType
    BORINGSSL_AVAILABLE = True
except ImportError:
    BORINGSSL_AVAILABLE = False

# Mapping from SoxBot TLS presets to native BoringSSL curl_cffi browser targets
BORINGSSL_PRESET_MAP: Dict[str, str] = {
    "chrome_132_win11": "chrome131",
    "chrome_131_win11": "chrome131",
    "chrome_120_win11": "chrome120",
    "edge_131_win11": "edge101",
    "chrome_131_mac": "chrome131",
    "safari_18_mac": "safari180",
    "safari_17_mac": "safari170",
    "chrome_131_linux": "chrome131",
    "firefox_152_win11": "firefox133",
    "firefox_152_linux": "firefox133",
    "firefox_131_win11": "firefox133",
    "firefox_130_win11": "firefox133",
    "firefox_130_linux": "firefox133",
    "chrome_android_pixel8": "chrome131_android",
    "safari_ios_iphone": "safari172_ios",
}


# Predefined TLS JA3 / JA4 Fingerprint Presets mapped to OS & Browser Configurations
TLS_PRESETS: Dict[str, Dict[str, Any]] = {
    "chrome_131_win11": {
        "name": "Chrome 131 / Edge 131 (Windows 11 / NVIDIA/Intel/AMD)",
        "ja3_hash": "cdb88489816e3c0e3e41416922d4f266",
        "ja4": "t13d1516h2_8daaf6152771_e56270fb3207",
        "ciphers": [
            "TLS_AES_128_GCM_SHA256",
            "TLS_AES_256_GCM_SHA384",
            "TLS_CHACHA20_POLY1305_SHA256",
            "ECDHE-ECDSA-AES128-GCM-SHA256",
            "ECDHE-RSA-AES128-GCM-SHA256",
            "ECDHE-ECDSA-AES256-GCM-SHA384",
            "ECDHE-RSA-AES256-GCM-SHA384",
            "ECDHE-ECDSA-CHACHA20-POLY1305",
            "ECDHE-RSA-CHACHA20-POLY1305",
            "ECDHE-RSA-AES128-SHA",
            "ECDHE-RSA-AES256-SHA",
            "AES128-GCM-SHA256",
            "AES256-GCM-SHA384"
        ],
        "alpn_protocols": ["h2", "http/1.1"],
        "min_version": ssl.TLSVersion.TLSv1_2,
        "max_version": ssl.TLSVersion.TLSv1_3,
    },
    "chrome_120_win11": {
        "name": "Chrome 120 (Windows 11)",
        "ja3_hash": "b32309a26951912be7dba376398abc3b",
        "ja4": "t13d1516h2_8daaf6152771_e56270fb3207",
        "ciphers": [
            "TLS_AES_128_GCM_SHA256",
            "TLS_AES_256_GCM_SHA384",
            "TLS_CHACHA20_POLY1305_SHA256",
            "ECDHE-ECDSA-AES128-GCM-SHA256",
            "ECDHE-RSA-AES128-GCM-SHA256",
            "ECDHE-ECDSA-AES256-GCM-SHA384",
            "ECDHE-RSA-AES256-GCM-SHA384",
            "ECDHE-ECDSA-CHACHA20-POLY1305",
            "ECDHE-RSA-CHACHA20-POLY1305",
            "ECDHE-RSA-AES128-SHA",
            "ECDHE-RSA-AES256-SHA"
        ],
        "alpn_protocols": ["h2", "http/1.1"],
        "min_version": ssl.TLSVersion.TLSv1_2,
        "max_version": ssl.TLSVersion.TLSv1_3,
    },
    "firefox_130_win11": {
        "name": "Firefox 130 / Camoufox (Windows 11)",
        "ja3_hash": "83c27f6e6556e4eb30740bc43f05c3fb",
        "ja4": "t13d1715h2_5a057e42f9b8_1638202d098e",
        "ciphers": [
            "TLS_AES_128_GCM_SHA256",
            "TLS_CHACHA20_POLY1305_SHA256",
            "TLS_AES_256_GCM_SHA384",
            "ECDHE-ECDSA-AES128-GCM-SHA256",
            "ECDHE-RSA-AES128-GCM-SHA256",
            "ECDHE-ECDSA-CHACHA20-POLY1305",
            "ECDHE-RSA-CHACHA20-POLY1305",
            "ECDHE-ECDSA-AES256-GCM-SHA384",
            "ECDHE-RSA-AES256-GCM-SHA384",
            "ECDHE-ECDSA-AES128-SHA256",
            "ECDHE-RSA-AES128-SHA256"
        ],
        "alpn_protocols": ["h2", "http/1.1"],
        "min_version": ssl.TLSVersion.TLSv1_2,
        "max_version": ssl.TLSVersion.TLSv1_3,
    },
    "edge_131_win11": {
        "name": "Microsoft Edge 131 (Windows 11)",
        "ja3_hash": "213898f090b8f6356616422b404d49a4",
        "ja4": "t13d1516h2_8daaf6152771_a83b27b140aa",
        "ciphers": [
            "TLS_AES_128_GCM_SHA256",
            "TLS_AES_256_GCM_SHA384",
            "TLS_CHACHA20_POLY1305_SHA256",
            "ECDHE-ECDSA-AES128-GCM-SHA256",
            "ECDHE-RSA-AES128-GCM-SHA256",
            "ECDHE-ECDSA-AES256-GCM-SHA384",
            "ECDHE-RSA-AES256-GCM-SHA384",
            "ECDHE-ECDSA-CHACHA20-POLY1305",
            "ECDHE-RSA-CHACHA20-POLY1305"
        ],
        "alpn_protocols": ["h2", "http/1.1"],
        "min_version": ssl.TLSVersion.TLSv1_2,
        "max_version": ssl.TLSVersion.TLSv1_3,
    },
    "chrome_131_mac": {
        "name": "Chrome 131 (macOS / Apple Silicon M1-M3)",
        "ja3_hash": "67b93a02ef340e3047a06d9154ef931b",
        "ja4": "t13d1516h2_8daaf6152771_0b4f8d9c1234",
        "ciphers": [
            "TLS_AES_128_GCM_SHA256",
            "TLS_AES_256_GCM_SHA384",
            "TLS_CHACHA20_POLY1305_SHA256",
            "ECDHE-ECDSA-AES128-GCM-SHA256",
            "ECDHE-RSA-AES128-GCM-SHA256",
            "ECDHE-ECDSA-AES256-GCM-SHA384",
            "ECDHE-RSA-AES256-GCM-SHA384",
            "ECDHE-ECDSA-CHACHA20-POLY1305",
            "ECDHE-RSA-CHACHA20-POLY1305"
        ],
        "alpn_protocols": ["h2", "http/1.1"],
        "min_version": ssl.TLSVersion.TLSv1_2,
        "max_version": ssl.TLSVersion.TLSv1_3,
    },
    "safari_17_mac": {
        "name": "Safari 17 / 18 (macOS Sonoma / Apple M1-M3)",
        "ja3_hash": "771,49196-49195-49200-49199-52393-52392",
        "ja4": "t13d1913h2_8daaf6152771_0b4f8d9c1234",
        "ciphers": [
            "TLS_AES_128_GCM_SHA256",
            "TLS_AES_256_GCM_SHA384",
            "TLS_CHACHA20_POLY1305_SHA256",
            "ECDHE-ECDSA-AES128-GCM-SHA256",
            "ECDHE-RSA-AES128-GCM-SHA256",
            "ECDHE-ECDSA-AES256-GCM-SHA384",
            "ECDHE-RSA-AES256-GCM-SHA384",
            "ECDHE-ECDSA-CHACHA20-POLY1305",
            "ECDHE-RSA-CHACHA20-POLY1305"
        ],
        "alpn_protocols": ["h2", "http/1.1"],
        "min_version": ssl.TLSVersion.TLSv1_2,
        "max_version": ssl.TLSVersion.TLSv1_3,
    },
    "chrome_131_linux": {
        "name": "Chrome 131 (Linux x86_64 / Mesa / AMD / NVIDIA)",
        "ja3_hash": "b2f6c91a329d668c679a9ef9c2fb491a",
        "ja4": "t13d1516h2_8daaf6152771_864195a940bb",
        "ciphers": [
            "TLS_AES_128_GCM_SHA256",
            "TLS_AES_256_GCM_SHA384",
            "TLS_CHACHA20_POLY1305_SHA256",
            "ECDHE-ECDSA-AES128-GCM-SHA256",
            "ECDHE-RSA-AES128-GCM-SHA256",
            "ECDHE-ECDSA-AES256-GCM-SHA384",
            "ECDHE-RSA-AES256-GCM-SHA384",
            "ECDHE-ECDSA-CHACHA20-POLY1305",
            "ECDHE-RSA-CHACHA20-POLY1305"
        ],
        "alpn_protocols": ["h2", "http/1.1"],
        "min_version": ssl.TLSVersion.TLSv1_2,
        "max_version": ssl.TLSVersion.TLSv1_3,
    },
    "firefox_130_linux": {
        "name": "Firefox 130 (Linux x86_64 / Mesa VirGL)",
        "ja3_hash": "80fb879203a985ff5303c7bb69b05aa3",
        "ja4": "t13d1715h2_5a057e42f9b8_9182390a120c",
        "ciphers": [
            "TLS_AES_128_GCM_SHA256",
            "TLS_CHACHA20_POLY1305_SHA256",
            "TLS_AES_256_GCM_SHA384",
            "ECDHE-ECDSA-AES128-GCM-SHA256",
            "ECDHE-RSA-AES128-GCM-SHA256",
            "ECDHE-ECDSA-CHACHA20-POLY1305",
            "ECDHE-RSA-CHACHA20-POLY1305",
            "ECDHE-ECDSA-AES256-GCM-SHA384",
            "ECDHE-RSA-AES256-GCM-SHA384"
        ],
        "alpn_protocols": ["h2", "http/1.1"],
        "min_version": ssl.TLSVersion.TLSv1_2,
        "max_version": ssl.TLSVersion.TLSv1_3,
    },
    "firefox_152_linux": {
        "name": "Firefox 152 (Linux x86_64 / Camoufox Native / ML-KEM768)",
        "ja3_hash": "aaa7ebc89cd8dc8b84a702f149c570d0",
        "ja4": "t13d1616h2_86a278354501_ca3c9f312770",
        "ciphers": [
            "TLS_AES_128_GCM_SHA256",
            "TLS_CHACHA20_POLY1305_SHA256",
            "TLS_AES_256_GCM_SHA384",
            "ECDHE-ECDSA-AES128-GCM-SHA256",
            "ECDHE-RSA-AES128-GCM-SHA256",
            "ECDHE-ECDSA-CHACHA20-POLY1305",
            "ECDHE-RSA-CHACHA20-POLY1305",
            "ECDHE-ECDSA-AES256-GCM-SHA384",
            "ECDHE-RSA-AES256-GCM-SHA384",
            "ECDHE-ECDSA-AES256-SHA",
            "ECDHE-RSA-AES128-SHA",
            "ECDHE-RSA-AES256-SHA",
            "AES128-GCM-SHA256",
            "AES256-GCM-SHA384",
            "AES128-SHA",
            "AES256-SHA"
        ],
        "alpn_protocols": ["h2", "http/1.1"],
        "min_version": ssl.TLSVersion.TLSv1_2,
        "max_version": ssl.TLSVersion.TLSv1_3,
    },
    "firefox_152_win11": {
        "name": "Firefox 152 (Windows 11 / Camoufox Native / ML-KEM768)",
        "ja3_hash": "aaa7ebc89cd8dc8b84a702f149c570d0",
        "ja4": "t13d1616h2_86a278354501_ca3c9f312770",
        "ciphers": [
            "TLS_AES_128_GCM_SHA256",
            "TLS_CHACHA20_POLY1305_SHA256",
            "TLS_AES_256_GCM_SHA384",
            "ECDHE-ECDSA-AES128-GCM-SHA256",
            "ECDHE-RSA-AES128-GCM-SHA256",
            "ECDHE-ECDSA-CHACHA20-POLY1305",
            "ECDHE-RSA-CHACHA20-POLY1305",
            "ECDHE-ECDSA-AES256-GCM-SHA384",
            "ECDHE-RSA-AES256-GCM-SHA384",
            "ECDHE-ECDSA-AES256-SHA",
            "ECDHE-RSA-AES128-SHA",
            "ECDHE-RSA-AES256-SHA",
            "AES128-GCM-SHA256",
            "AES256-GCM-SHA384",
            "AES128-SHA",
            "AES256-SHA"
        ],
        "alpn_protocols": ["h2", "http/1.1"],
        "min_version": ssl.TLSVersion.TLSv1_2,
        "max_version": ssl.TLSVersion.TLSv1_3,
    },


    "chrome_android_pixel8": {
        "name": "Chrome Mobile 131 (Android 14 / Pixel 8 / ARM Mali-G715)",
        "ja3_hash": "35165d70b6a22f3e8ab2dfa32b2e887f",
        "ja4": "t13d1516h2_8daaf6152771_076b32810a9f",
        "ciphers": [
            "TLS_AES_128_GCM_SHA256",
            "TLS_AES_256_GCM_SHA384",
            "TLS_CHACHA20_POLY1305_SHA256",
            "ECDHE-ECDSA-AES128-GCM-SHA256",
            "ECDHE-RSA-AES128-GCM-SHA256",
            "ECDHE-ECDSA-CHACHA20-POLY1305",
            "ECDHE-RSA-CHACHA20-POLY1305"
        ],
        "alpn_protocols": ["h2", "http/1.1"],
        "min_version": ssl.TLSVersion.TLSv1_2,
        "max_version": ssl.TLSVersion.TLSv1_3,
    },
    "safari_ios_iphone": {
        "name": "Mobile Safari 17.4 (iOS 17 / iPhone 15 Pro)",
        "ja3_hash": "95a1290bb35e381023a1a457199c2010",
        "ja4": "t13d1913h2_8daaf6152771_118939c092ab",
        "ciphers": [
            "TLS_AES_128_GCM_SHA256",
            "TLS_AES_256_GCM_SHA384",
            "TLS_CHACHA20_POLY1305_SHA256",
            "ECDHE-ECDSA-AES128-GCM-SHA256",
            "ECDHE-RSA-AES128-GCM-SHA256",
            "ECDHE-ECDSA-CHACHA20-POLY1305",
            "ECDHE-RSA-CHACHA20-POLY1305"
        ],
        "alpn_protocols": ["h2", "http/1.1"],
        "min_version": ssl.TLSVersion.TLSv1_2,
        "max_version": ssl.TLSVersion.TLSv1_3,
    },
    "chrome_132_win11": {
        "name": "Chrome 132 / Edge 132 (Windows 11 / RTX 4090)",
        "ja3_hash": "e7d705a3286e19ea42f587b3d4f40954",
        "ja4": "t13d1516h2_8daaf6152771_f92471b0231a",
        "ciphers": [
            "TLS_AES_128_GCM_SHA256",
            "TLS_AES_256_GCM_SHA384",
            "TLS_CHACHA20_POLY1305_SHA256",
            "ECDHE-ECDSA-AES128-GCM-SHA256",
            "ECDHE-RSA-AES128-GCM-SHA256",
            "ECDHE-ECDSA-AES256-GCM-SHA384",
            "ECDHE-RSA-AES256-GCM-SHA384",
            "ECDHE-ECDSA-CHACHA20-POLY1305",
            "ECDHE-RSA-CHACHA20-POLY1305",
            "ECDHE-RSA-AES128-SHA",
            "ECDHE-RSA-AES256-SHA"
        ],
        "alpn_protocols": ["h2", "http/1.1"],
        "min_version": ssl.TLSVersion.TLSv1_2,
        "max_version": ssl.TLSVersion.TLSv1_3,
    },
    "firefox_131_win11": {
        "name": "Firefox 131 / Camoufox (Windows 11)",
        "ja3_hash": "4b68e9834190c1f51081512803b9059e",
        "ja4": "t13d1715h2_5a057e42f9b8_c519280a911e",
        "ciphers": [
            "TLS_AES_128_GCM_SHA256",
            "TLS_CHACHA20_POLY1305_SHA256",
            "TLS_AES_256_GCM_SHA384",
            "ECDHE-ECDSA-AES128-GCM-SHA256",
            "ECDHE-RSA-AES128-GCM-SHA256",
            "ECDHE-ECDSA-CHACHA20-POLY1305",
            "ECDHE-RSA-CHACHA20-POLY1305",
            "ECDHE-ECDSA-AES256-GCM-SHA384",
            "ECDHE-RSA-AES256-GCM-SHA384"
        ],
        "alpn_protocols": ["h2", "http/1.1"],
        "min_version": ssl.TLSVersion.TLSv1_2,
        "max_version": ssl.TLSVersion.TLSv1_3,
    },
    "safari_18_mac": {
        "name": "Safari 18.1 (macOS Sequoia / Apple M3 Max)",
        "ja3_hash": "64817e9231f478a59918204b687f8910",
        "ja4": "t13d1913h2_8daaf6152771_0b4f8d9c1818",
        "ciphers": [
            "TLS_AES_128_GCM_SHA256",
            "TLS_AES_256_GCM_SHA384",
            "TLS_CHACHA20_POLY1305_SHA256",
            "ECDHE-ECDSA-AES128-GCM-SHA256",
            "ECDHE-RSA-AES128-GCM-SHA256",
            "ECDHE-ECDSA-AES256-GCM-SHA384",
            "ECDHE-RSA-AES256-GCM-SHA384",
            "ECDHE-ECDSA-CHACHA20-POLY1305",
            "ECDHE-RSA-CHACHA20-POLY1305"
        ],
        "alpn_protocols": ["h2", "http/1.1"],
        "min_version": ssl.TLSVersion.TLSv1_2,
        "max_version": ssl.TLSVersion.TLSv1_3,
    }
}


class TLSImpersonate:
    """
    Constructs custom SSL contexts matching specific Browser/OS TLS Handshake (JA3/JA4) profiles.
    Allows proxy tunnel connections to bypass TLS fingerprint detection mechanisms.
    """

    @classmethod
    def create_impersonated_ssl_context(cls, preset_key: str = "auto", target_os: str = "windows") -> ssl.SSLContext:
        """
        Builds a customized SSLContext configured with cipher suite ordering, ALPN protocols,
        and version constraints matching the requested preset or OS default.

        Certificate verification is ENABLED by default. Use create_proxy_tunnel_ssl_context()
        if you need an unverified context for proxy tunnel TCP connections.
        """
        if preset_key == "auto" or preset_key not in TLS_PRESETS:
            os_clean = target_os.lower()
            if os_clean == "mac":
                preset_key = "chrome_131_mac"
            elif os_clean == "linux":
                preset_key = "chrome_131_linux"
            elif os_clean == "android":
                preset_key = "chrome_android_pixel8"
            elif os_clean == "ios":
                preset_key = "safari_ios_iphone"
            else:
                preset_key = "chrome_131_win11"

        preset = TLS_PRESETS.get(preset_key, TLS_PRESETS["chrome_131_win11"])
        logger.info(f"[TLSImpersonate] Applying TLS Impersonation Preset: '{preset['name']}' (JA4={preset['ja4']})")

        ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        # Certificate verification ENABLED — do not disable without explicit justification.
        # For proxy tunnel connections (where TCP-level verification is not applicable),
        # use create_proxy_tunnel_ssl_context() instead.
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED

        # Configure TLS versions
        ctx.minimum_version = preset.get("min_version", ssl.TLSVersion.TLSv1_2)
        ctx.maximum_version = preset.get("max_version", ssl.TLSVersion.TLSv1_3)

        # Configure Cipher Suites
        ciphers_str = ":".join(preset["ciphers"])
        try:
            ctx.set_ciphers(ciphers_str)
        except Exception as e:
            logger.warning(f"[TLSImpersonate] Could not set custom ciphers ({e}). Falling back to default high-security suite.")

        # Configure ALPN protocols (h2, http/1.1)
        alpn = preset.get("alpn_protocols", ["h2", "http/1.1"])
        try:
            ctx.set_alpn_protocols(alpn)
        except Exception as e:
            logger.debug(f"[TLSImpersonate] ALPN setting note: {e}")

        return ctx

    @classmethod
    def create_proxy_tunnel_ssl_context(cls, preset_key: str = "auto", target_os: str = "windows") -> ssl.SSLContext:
        """
        Builds an SSL context for proxy tunnel upstream connections.

        SECURITY NOTE: Certificate verification is intentionally DISABLED here.
        Rationale: The proxy tunnel connects at the TCP layer to the upstream proxy server.
        The actual TLS session to the target website is established end-to-end by the
        browser through the CONNECT tunnel — the browser handles cert verification.
        This context is ONLY used for the TCP connection to the proxy itself.
        """
        if preset_key == "auto" or preset_key not in TLS_PRESETS:
            os_clean = target_os.lower()
            if os_clean == "mac":
                preset_key = "chrome_131_mac"
            elif os_clean == "linux":
                preset_key = "chrome_131_linux"
            elif os_clean == "android":
                preset_key = "chrome_android_pixel8"
            elif os_clean == "ios":
                preset_key = "safari_ios_iphone"
            else:
                preset_key = "chrome_131_win11"

        preset = TLS_PRESETS.get(preset_key, TLS_PRESETS["chrome_131_win11"])
        logger.info(f"[TLSImpersonate] Applying Proxy Tunnel TLS Preset: '{preset['name']}' (JA4={preset['ja4']})")

        ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        # Disabled for proxy tunnel TCP connections only — see docstring above.
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        ctx.minimum_version = preset.get("min_version", ssl.TLSVersion.TLSv1_2)
        ctx.maximum_version = preset.get("max_version", ssl.TLSVersion.TLSv1_3)

        ciphers_str = ":".join(preset["ciphers"])
        try:
            ctx.set_ciphers(ciphers_str)
        except Exception as e:
            logger.warning(f"[TLSImpersonate] Proxy tunnel: could not set custom ciphers ({e}).")

        alpn = preset.get("alpn_protocols", ["h2", "http/1.1"])
        try:
            ctx.set_alpn_protocols(alpn)
        except Exception as e:
            logger.debug(f"[TLSImpersonate] Proxy tunnel ALPN note: {e}")

        return ctx

    @classmethod
    def is_boringssl_available(cls) -> bool:
        """Returns True if native BoringSSL engine (curl_cffi) is available."""
        return BORINGSSL_AVAILABLE

    @classmethod
    def get_boringssl_target(cls, preset_key: str = "auto", target_os: str = "windows") -> str:
        """Resolves preset key to native BoringSSL browser impersonation target string."""
        if preset_key == "auto" or preset_key not in BORINGSSL_PRESET_MAP:
            os_clean = target_os.lower()
            if os_clean == "mac":
                return "chrome131"
            elif os_clean == "linux":
                return "chrome131"
            elif os_clean == "android":
                return "chrome131_android"
            elif os_clean == "ios":
                return "safari172_ios"
            else:
                return "chrome131"
        return BORINGSSL_PRESET_MAP.get(preset_key, "chrome131")

    @classmethod
    def get_preset_for_profile(cls, profile: Dict[str, Any]) -> str:
        """Derives the most accurate TLS & JA4 preset based on profile engine, OS, and User-Agent."""
        if not profile:
            return "chrome_131_win11"

        engine = str(profile.get("engine", "camoufox")).lower()
        target_os = str(profile.get("os", "windows")).lower()
        ua = str(profile.get("user_agent", "")).lower()

        if engine in ["camoufox", "firefox"] or "firefox" in ua:
            if "152" in ua:
                return "firefox_152_linux" if "linux" in target_os else "firefox_152_win11"
            if "linux" in target_os:
                return "firefox_130_linux"
            return "firefox_130_win11"


        if target_os == "mac":
            if "safari" in ua and "chrome" not in ua:
                return "safari_18_mac"
            return "chrome_131_mac"
        elif target_os == "linux":
            return "chrome_131_linux"
        elif target_os == "android":
            return "chrome_android_pixel8"
        elif target_os == "ios":
            return "safari_ios_iphone"

        if "edg/" in ua:
            return "edge_131_win11"

        return "chrome_131_win11"

    @classmethod
    def create_boringssl_session(
        cls,
        preset_key: str = "auto",
        target_os: str = "windows",
        proxy_url: Optional[str] = None,
        timeout: float = 10.0
    ) -> Any:
        """
        Creates an AsyncSession powered by native BoringSSL (curl_cffi) with full TLS extension ordering,
        GREASE bytes, ECH negotiation, and HTTP/2 SETTINGS frames matching target browsers (Chrome/Firefox/Safari).
        Bypasses Cloudflare / Akamai JA3 & JA4 TLS Fingerprint detection.
        """
        if not BORINGSSL_AVAILABLE:
            logger.warning("[TLSImpersonate] curl_cffi not available. Falling back to standard transport.")
            return None

        target = cls.get_boringssl_target(preset_key, target_os)
        logger.info(f"[TLSImpersonate] Initialized native BoringSSL session with target '{target}' (Bypassing Cloudflare/Akamai JA4)")

        kwargs: Dict[str, Any] = {
            "impersonate": target,
            "timeout": timeout,
            "verify": True
        }
        if proxy_url:
            kwargs["verify"] = False
            kwargs["proxies"] = {"http": proxy_url, "https": proxy_url}

        return AsyncSession(**kwargs)

    @classmethod
    def create_sync_boringssl_session(
        cls,
        preset_key: str = "auto",
        target_os: str = "windows",
        proxy_url: Optional[str] = None,
        timeout: float = 10.0
    ) -> Any:
        """Creates a synchronous Session powered by native BoringSSL (curl_cffi)."""
        if not BORINGSSL_AVAILABLE:
            return None

        target = cls.get_boringssl_target(preset_key, target_os)
        kwargs: Dict[str, Any] = {
            "impersonate": target,
            "timeout": timeout,
            "verify": True
        }
        if proxy_url:
            kwargs["verify"] = False
            kwargs["proxies"] = {"http": proxy_url, "https": proxy_url}

        return Session(**kwargs)


# Alias for backward and forward compatibility
TLSImpersonator = TLSImpersonate

