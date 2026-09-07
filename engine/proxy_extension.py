import os
import json
import logging
from typing import Dict

logger = logging.getLogger("ProxyExtension")

class ProxyExtensionManager:
    """Generates dynamically configured Chrome Manifest V3 Proxy Auth Extensions."""

    @staticmethod
    def create_proxy_extension(profile_dir: str, proxy_cfg: Dict) -> str:
        """
        Creates an unpacked Chrome Extension in profile_dir that configures Chrome's native
        proxy settings and handles proxy authentication seamlessly across all domains.
        Returns the path to the created extension directory.
        """
        ext_dir = os.path.join(profile_dir, "proxy_auth_extension")
        os.makedirs(ext_dir, exist_ok=True)

        host = str(proxy_cfg.get("host", "")).strip()
        port = int(proxy_cfg.get("port", 8080))
        user = str(proxy_cfg.get("username", "")).strip()
        pwd = str(proxy_cfg.get("password", "")).strip()
        p_type = str(proxy_cfg.get("type", "http")).lower().strip()

        scheme = "socks5" if p_type in ["socks5", "socks5h"] else "http"

        manifest = {
            "version": "1.0.0",
            "manifest_version": 3,
            "name": "SoxBot Native Proxy",
            "description": "SoxBot Native Proxy Authentication & Network Manager",
            "permissions": [
                "proxy",
                "tabs",
                "unlimitedStorage",
                "storage",
                "webRequest",
                "webRequestAuthProvider"
            ],
            "host_permissions": ["<all_urls>"],
            "background": {
                "service_worker": "background.js"
            }
        }

        host_js = json.dumps(host)
        user_js = json.dumps(user)
        pwd_js = json.dumps(pwd)

        auth_js = ""
        if user or pwd:
            auth_js = f"""
chrome.webRequest.onAuthRequired.addListener(
    function(details) {{
        console.log("[SoxBot Proxy Extension] Auth required for URL:", details.url, "Realm:", details.realm, "isProxy:", details.isProxy);
        return {{
            authCredentials: {{
                username: {user_js},
                password: {pwd_js}
            }}
        }};
    }},
    {{ urls: ["<all_urls>"] }},
    ["blocking"]
);
"""

        background_js = f"""
console.log("[SoxBot Proxy Extension] Initializing Proxy Extension for {scheme}://{host}:{port}...");
chrome.proxy.settings.set({{
    value: {{
        mode: "fixed_servers",
        rules: {{
            singleProxy: {{
                scheme: "{scheme}",
                host: {host_js},
                port: {port}
            }},
            bypassList: ["<local>"]
        }}
    }},
    scope: "regular"
}}, function() {{
    if (chrome.runtime.lastError) {{
        console.error("[SoxBot Proxy Extension] Failed to apply proxy settings:", chrome.runtime.lastError.message);
    }} else {{
        console.log("[SoxBot Proxy Extension] Successfully configured Chrome proxy settings to {scheme}://{host}:{port}");
    }}
}});
{auth_js}
"""

        manifest_path = os.path.join(ext_dir, "manifest.json")
        bg_path = os.path.join(ext_dir, "background.js")

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        with open(bg_path, "w", encoding="utf-8") as f:
            f.write(background_js)

        logger.info(f"Generated Native Proxy Extension at {ext_dir} for {scheme}://{host}:{port}")
        return ext_dir

