import os
import time
import json
import asyncio
import base64
import hashlib
import hmac
import struct
import uuid
import logging
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger("AccountManager")


class AccountManager:
    """
    Manages social/web platform accounts, credentials, RFC 6238 TOTP 2FA generation,
    and automated stealth autofill / login routines for browser profiles.
    """

    PLATFORMS: Dict[str, Dict[str, Any]] = {
        "google": {
            "name": "Google",
            "icon": "🌐",
            "login_url": "https://accounts.google.com/signin",
            "domains": ["google.com", "accounts.google.com", "youtube.com", "gmail.com"],
            "user_selectors": ["#identifierId", "input[type='email']", "input[name='identifier']"],
            "user_next_selectors": ["#identifierNext", "button[jsname='LgbsSe']", "button[type='button']", "button[type='submit']"],
            "pass_selectors": ["input[type='password']", "input[name='Passwd']", "input[name='password']"],
            "pass_next_selectors": ["#passwordNext", "button[jsname='LgbsSe']", "button[type='submit']", "button[type='button']"],
            "next_btn_selectors": ["#passwordNext", "#identifierNext", "button[type='submit']", "button[type='button']"],
            "totp_selectors": ["input[type='tel']", "input[name='totpPin']", "#totpPin", "input[autocomplete='one-time-code']", "input[name='code']"],
            "totp_next_selectors": ["#totpNext", "button[type='submit']", "button[type='button']"],
            "description": "Google, Gmail, YouTube, Google Cloud"
        },
        "instagram": {
            "name": "Instagram",
            "icon": "📸",
            "login_url": "https://www.instagram.com/accounts/login/",
            "domains": ["instagram.com", "www.instagram.com"],
            "user_selectors": ["input[name='username']", "input[aria-label*='Phone number, username, or email']"],
            "pass_selectors": ["input[name='password']", "input[aria-label*='Password']"],
            "next_btn_selectors": ["button[type='submit']"],
            "description": "Instagram Web & Direct"
        },
        "github": {
            "name": "GitHub",
            "icon": "🐙",
            "login_url": "https://github.com/login",
            "domains": ["github.com"],
            "user_selectors": ["#login_field", "input[name='login']"],
            "pass_selectors": ["#password", "input[name='password']"],
            "next_btn_selectors": ["input[type='submit']", "button[type='submit']"],
            "description": "GitHub Developer Platform"
        },
        "tiktok": {
            "name": "TikTok",
            "icon": "🎵",
            "login_url": "https://www.tiktok.com/login",
            "domains": ["tiktok.com", "www.tiktok.com"],
            "user_selectors": ["input[name='username']", "input[placeholder*='Email or username']", "input[type='text']"],
            "pass_selectors": ["input[type='password']", "input[placeholder*='Password']"],
            "next_btn_selectors": ["button[type='submit']", "button[data-e2e='login-button']"],
            "description": "TikTok Social Network"
        },
        "spotify": {
            "name": "Spotify",
            "icon": "🎧",
            "login_url": "https://accounts.spotify.com/login",
            "domains": ["spotify.com", "open.spotify.com", "accounts.spotify.com"],
            "user_selectors": ["#login-username", "input[data-testid='login-username']", "input[type='text']"],
            "pass_selectors": ["#login-password", "input[data-testid='login-password']", "input[type='password']"],
            "next_btn_selectors": ["#login-button", "button[data-testid='login-button']", "button[type='submit']"],
            "description": "Spotify Music & Podcasts"
        },
        "twitter": {
            "name": "Twitter / X",
            "icon": "🐦",
            "login_url": "https://x.com/i/flow/login",
            "domains": ["x.com", "twitter.com"],
            "user_selectors": ["input[autocomplete='username']", "input[name='text']"],
            "user_next_selectors": ["button[role='button']", "div[role='button']"],
            "pass_selectors": ["input[name='password']", "input[autocomplete='current-password']"],
            "pass_next_selectors": ["button[data-testid='LoginForm_Login_Button']", "button[role='button']", "div[role='button']"],
            "next_btn_selectors": ["button[role='button']", "div[role='button']"],
            "totp_selectors": ["input[data-testid='ocfEnterTextTextInput']", "input[name='text']"],
            "totp_next_selectors": ["button[data-testid='ocfEnterTextNextButton']", "button[role='button']"],
            "description": "X (formerly Twitter)"
        },
        "discord": {
            "name": "Discord",
            "icon": "💬",
            "login_url": "https://discord.com/login",
            "domains": ["discord.com"],
            "user_selectors": ["input[name='email']", "input[type='email']"],
            "pass_selectors": ["input[name='password']", "input[type='password']"],
            "next_btn_selectors": ["button[type='submit']"],
            "description": "Discord Community & Chat"
        },
        "reddit": {
            "name": "Reddit",
            "icon": "🔴",
            "login_url": "https://www.reddit.com/login",
            "domains": ["reddit.com", "www.reddit.com"],
            "user_selectors": ["#login-username", "input[name='username']", "input[id*='user']"],
            "pass_selectors": ["#login-password", "input[name='password']", "input[id*='pass']"],
            "next_btn_selectors": ["button[type='submit']", "button.login"],
            "description": "Reddit Social Forum"
        },
        "spotify": {
            "name": "Spotify",
            "icon": "🟢",
            "login_url": "https://accounts.spotify.com/login",
            "domains": ["spotify.com", "accounts.spotify.com", "open.spotify.com"],
            "user_selectors": ["#login-username", "input[name='username']", "input[type='text']"],
            "pass_selectors": ["#login-password", "input[name='password']", "input[type='password']"],
            "next_btn_selectors": ["#login-button", "button[data-testid='login-button']"],
            "description": "Spotify Music Streaming"
        },
        "facebook": {
            "name": "Facebook",
            "icon": "👥",
            "login_url": "https://www.facebook.com/login",
            "domains": ["facebook.com", "www.facebook.com"],
            "user_selectors": ["#email", "input[name='email']"],
            "pass_selectors": ["#pass", "input[name='pass']"],
            "next_btn_selectors": ["#loginbutton", "button[name='login']"],
            "description": "Facebook Social Network"
        },
        "custom": {
            "name": "Custom Platform",
            "icon": "🔑",
            "login_url": "https://example.com/login",
            "domains": [],
            "user_selectors": ["input[type='email']", "input[type='text']", "input[name='username']", "input[name='login']"],
            "pass_selectors": ["input[type='password']", "input[name='password']"],
            "next_btn_selectors": ["button[type='submit']", "input[type='submit']"],
            "description": "Custom / Other Web Platform"
        }
    }

    # -------------------------------------------------------------------------
    # RFC 6238 TOTP 2FA Code Generator (Native Python - No External Dependencies)
    # -------------------------------------------------------------------------

    @staticmethod
    def generate_totp_code(secret: str, digits: int = 6, time_step: int = 30) -> Tuple[str, int]:
        """
        Computes the current 6-digit TOTP token and seconds remaining in current step.
        Supports standard Base32 encoded secrets (with or without spaces/dashes).
        Returns:
            (totp_code: str, remaining_seconds: int)
        """
        clean_secret = secret.upper().replace(" ", "").replace("-", "").strip()
        if not clean_secret:
            return "", 0

        try:
            # Handle padding for base32 decode
            missing_padding = len(clean_secret) % 8
            if missing_padding != 0:
                clean_secret += "=" * (8 - missing_padding)

            key = base64.b32decode(clean_secret, casefold=True)
            current_time = int(time.time())
            time_counter = current_time // time_step
            remaining_seconds = time_step - (current_time % time_step)

            # Pack 8-byte big-endian integer counter
            msg = struct.pack(">Q", time_counter)
            h = hmac.new(key, msg, hashlib.sha1).digest()

            # Dynamic truncation
            offset = h[-1] & 0x0F
            binary = struct.unpack(">I", h[offset:offset + 4])[0] & 0x7FFFFFFF
            code_num = binary % (10 ** digits)
            totp_code = str(code_num).zfill(digits)

            return totp_code, remaining_seconds
        except Exception as e:
            logger.debug(f"Failed to calculate TOTP code for secret: {e}")
            return "", 0

    # -------------------------------------------------------------------------
    # Account Helpers & Normalization
    # -------------------------------------------------------------------------

    @classmethod
    def get_platform_info(cls, platform_key: str) -> Dict[str, Any]:
        key = (platform_key or "custom").lower().strip()
        return cls.PLATFORMS.get(key, cls.PLATFORMS["custom"])

    @classmethod
    def create_account_record(
        cls,
        platform: str = "google",
        username: Optional[str] = "",
        password: Optional[str] = "",
        name: Optional[str] = "",
        totp_secret: Optional[str] = "",
        login_url: Optional[str] = "",
        cookies: Optional[str] = "",
        auto_login_on_launch: bool = False,
        notes: Optional[str] = ""
    ) -> Dict[str, Any]:
        """Creates a sanitized account dictionary structure."""
        plat_info = cls.get_platform_info(platform)
        acc_id = str(uuid.uuid4())
        acc_name = (name or "").strip() or f"{plat_info['name']} Account"
        acc_url = (login_url or "").strip() or plat_info.get("login_url", "")

        return {
            "id": acc_id,
            "platform": (platform or "custom").lower().strip(),
            "name": acc_name,
            "login_url": acc_url,
            "username": (username or "").strip(),
            "password": (password or "").strip(),
            "totp_secret": (totp_secret or "").replace(" ", "").strip(),
            "cookies": (cookies or "").strip(),
            "auto_login_on_launch": auto_login_on_launch,
            "notes": (notes or "").strip(),
            "created_at": time.time(),
            "last_login": 0
        }

    # -------------------------------------------------------------------------
    # Batch Import / Export Parser
    # -------------------------------------------------------------------------

    @classmethod
    def parse_batch_credentials(cls, text: str) -> List[Dict[str, Any]]:
        """
        Parses pasted account credentials from common formats:
        - JSON array: [{"platform": "...", "username": "...", ...}]
        - Delimited text lines:
          - platform:username:password:totp_secret
          - platform:username:password
          - username:password:totp_secret
          - username:password
          - username|password|totp
        """
        text = text.strip()
        if not text:
            return []

        # Try JSON first
        if text.startswith("[") or text.startswith("{"):
            try:
                data = json.loads(text)
                if isinstance(data, list):
                    res: List[Dict[str, Any]] = []
                    for item in data:
                        if isinstance(item, dict):
                            raw_user = item.get("username") or item.get("user") or item.get("email") or ""
                            raw_pass = item.get("password") or item.get("pass") or ""
                            raw_totp = item.get("totp_secret") or item.get("totp") or item.get("2fa") or ""
                            res.append(cls.create_account_record(
                                platform=str(item.get("platform") or "custom"),
                                username=str(raw_user),
                                password=str(raw_pass),
                                name=str(item.get("name") or ""),
                                totp_secret=str(raw_totp),
                                login_url=str(item.get("login_url") or ""),
                                cookies=str(item.get("cookies") or ""),
                                auto_login_on_launch=bool(item.get("auto_login_on_launch", False)),
                                notes=str(item.get("notes") or "")
                            ))
                    return res
                elif isinstance(data, dict):
                    raw_user = data.get("username") or data.get("user") or data.get("email") or ""
                    raw_pass = data.get("password") or data.get("pass") or ""
                    raw_totp = data.get("totp_secret") or data.get("totp") or data.get("2fa") or ""
                    return [cls.create_account_record(
                        platform=str(data.get("platform") or "custom"),
                        username=str(raw_user),
                        password=str(raw_pass),
                        name=str(data.get("name") or ""),
                        totp_secret=str(raw_totp),
                        login_url=str(data.get("login_url") or ""),
                        cookies=str(data.get("cookies") or ""),
                        auto_login_on_launch=bool(data.get("auto_login_on_launch", False)),
                        notes=str(data.get("notes") or "")
                    )]
            except Exception:
                pass

        accounts: List[Dict[str, Any]] = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Determine delimiter (: , | ;)
            delimiter = ":"
            if "|" in line and line.count("|") >= line.count(":"):
                delimiter = "|"
            elif ";" in line and line.count(";") >= line.count(":"):
                delimiter = ";"
            elif "," in line and line.count(",") >= line.count(":"):
                delimiter = ","

            parts = [p.strip() for p in line.split(delimiter)]
            if len(parts) < 2:
                continue

            # Format 1: platform:user:pass:totp
            # Format 2: platform:user:pass
            # Format 3: user:pass:totp
            # Format 4: user:pass
            first_part_lower = parts[0].lower()
            if first_part_lower in cls.PLATFORMS:
                platform = first_part_lower
                username = parts[1] if len(parts) > 1 else ""
                password = parts[2] if len(parts) > 2 else ""
                totp = parts[3] if len(parts) > 3 else ""
            else:
                # Infer platform from username / email domain if possible
                platform = "custom"
                if "@gmail" in first_part_lower or "@google" in first_part_lower:
                    platform = "google"
                username = parts[0]
                password = parts[1]
                totp = parts[2] if len(parts) > 2 else ""

            if username and password:
                accounts.append(cls.create_account_record(
                    platform=platform,
                    username=username,
                    password=password,
                    totp_secret=totp
                ))

        return accounts

    @classmethod
    def export_accounts_text(cls, accounts: List[Dict[str, Any]], format_type: str = "delimited") -> str:
        """Exports accounts to delimited format or JSON string."""
        if format_type == "json":
            return json.dumps(accounts, indent=2)

        lines = []
        for acc in accounts:
            plat = acc.get("platform", "custom")
            user = acc.get("username", "")
            pwd = acc.get("password", "")
            totp = acc.get("totp_secret", "")
            if totp:
                lines.append(f"{plat}:{user}:{pwd}:{totp}")
            else:
                lines.append(f"{plat}:{user}:{pwd}")
        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # Stealth Autofill Script Generation
    # -------------------------------------------------------------------------

    @classmethod
    def generate_autofill_script(cls, account: Dict[str, Any]) -> str:
        """
        Generates client-side JavaScript that securely, stealthily and reactively autofills
        login forms with simulated user input events and React-safe property setters.
        """
        user = json.dumps(account.get("username", ""))
        pwd = json.dumps(account.get("password", ""))
        totp_secret = account.get("totp_secret", "")
        totp_code, _ = cls.generate_totp_code(totp_secret) if totp_secret else ("", 0)
        totp_json = json.dumps(totp_code)
        auto_submit = "true" if account.get("auto_login_on_launch") else "false"
        plat = account.get("platform", "custom")
        plat_info = cls.get_platform_info(plat)

        user_selectors = json.dumps(plat_info.get("user_selectors", ["input[name='username']", "input[type='email']", "input[type='text']"]))
        user_next_selectors = json.dumps(plat_info.get("user_next_selectors", ["#identifierNext", "button[type='button']", "button[type='submit']"]))
        pass_selectors = json.dumps(plat_info.get("pass_selectors", ["input[name='password']", "input[type='password']"]))
        pass_next_selectors = json.dumps(plat_info.get("pass_next_selectors", ["#passwordNext", "button[type='submit']", "button[type='button']"]))
        btn_selectors = json.dumps(plat_info.get("next_btn_selectors", ["button[type='submit']", "button._acan", "input[type='submit']"]))
        totp_selectors = json.dumps(plat_info.get("totp_selectors", ["input[type='tel']", "input[name='totpPin']", "#totpPin", "input[autocomplete='one-time-code']", "input[name='code']"]))
        totp_next_selectors = json.dumps(plat_info.get("totp_next_selectors", ["#totpNext", "button[type='submit']"]))

        return f"""
        (function() {{
            const usernameVal = {user};
            const passwordVal = {pwd};
            const totpCodeVal = {totp_json};
            const autoSubmit = {auto_submit};
            const userSelectors = {user_selectors};
            const userNextSelectors = {user_next_selectors};
            const passSelectors = {pass_selectors};
            const passNextSelectors = {pass_next_selectors};
            const btnSelectors = {btn_selectors};
            const totpSelectors = {totp_selectors};
            const totpNextSelectors = {totp_next_selectors};

            function isVisible(el) {{
                return !!(el && (el.offsetWidth > 0 || el.offsetHeight > 0 || el.getClientRects().length > 0));
            }}

            function setNativeValue(el, val) {{
                if (!el || el.value === val) return false;
                el.focus();
                const lastVal = el.value;
                const desc = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
                if (desc && desc.set) {{
                    desc.set.call(el, val);
                }} else {{
                    el.value = val;
                }}
                if (el._valueTracker) {{
                    el._valueTracker.setValue(lastVal);
                }}
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                el.dispatchEvent(new KeyboardEvent('keydown', {{ bubbles: true, key: 'a' }}));
                el.dispatchEvent(new KeyboardEvent('keyup', {{ bubbles: true, key: 'a' }}));
                return true;
            }}

            let userNextTriggered = false;
            let passNextTriggered = false;
            let totpNextTriggered = false;

            function tryFill() {{
                let filledUser = false;
                let filledPass = false;
                let filledTotp = false;

                if (usernameVal) {{
                    for (const sel of userSelectors) {{
                        const el = document.querySelector(sel);
                        if (el && isVisible(el)) {{
                            setNativeValue(el, usernameVal);
                            filledUser = true;
                            break;
                        }}
                    }}
                }}

                if (passwordVal) {{
                    for (const sel of passSelectors) {{
                        const el = document.querySelector(sel);
                        if (el && isVisible(el)) {{
                            setNativeValue(el, passwordVal);
                            filledPass = true;
                            break;
                        }}
                    }}
                }}

                if (totpCodeVal) {{
                    for (const sel of totpSelectors) {{
                        const totpInput = document.querySelector(sel);
                        if (totpInput && isVisible(totpInput) && !totpInput.value) {{
                            setNativeValue(totpInput, totpCodeVal);
                            filledTotp = true;
                            break;
                        }}
                    }}
                }}

                if (autoSubmit) {{
                    // Step 1: User filled, password not yet rendered (Multi-Step like Google)
                    if (filledUser && !filledPass && !userNextTriggered && passwordVal) {{
                        userNextTriggered = true;
                        setTimeout(() => {{
                            const nextCandidates = userNextSelectors.concat(btnSelectors);
                            for (const bSel of nextCandidates) {{
                                const btn = document.querySelector(bSel);
                                if (btn && isVisible(btn) && typeof btn.click === 'function') {{
                                    btn.click();
                                    break;
                                }}
                            }}
                        }}, 400);
                    }}
                    // Step 2: Password filled
                    else if (filledPass && !passNextTriggered) {{
                        passNextTriggered = true;
                        setTimeout(() => {{
                            const nextCandidates = passNextSelectors.concat(btnSelectors);
                            for (const bSel of nextCandidates) {{
                                const btn = document.querySelector(bSel);
                                if (btn && isVisible(btn) && typeof btn.click === 'function') {{
                                    btn.click();
                                    break;
                                }}
                            }}
                        }}, 450);
                    }}
                    // Step 3: TOTP filled
                    else if (filledTotp && !totpNextTriggered) {{
                        totpNextTriggered = true;
                        setTimeout(() => {{
                            const nextCandidates = totpNextSelectors.concat(btnSelectors);
                            for (const bSel of nextCandidates) {{
                                const btn = document.querySelector(bSel);
                                if (btn && isVisible(btn) && typeof btn.click === 'function') {{
                                    btn.click();
                                    break;
                                }}
                            }}
                        }}, 450);
                    }}
                }}

                return filledPass && (!totpCodeVal || filledTotp);
            }}

            let attempts = 0;
            const poller = setInterval(() => {{
                attempts++;
                if (tryFill() || attempts > 60) {{
                    if (attempts > 60) clearInterval(poller);
                }}
            }}, 250);

            try {{
                const observer = new MutationObserver(() => {{
                    tryFill();
                }});
                if (document.documentElement) {{
                    observer.observe(document.documentElement, {{ childList: true, subtree: true }});
                }}
            }} catch (e) {{}}
        }})();
        """

    @classmethod
    def generate_in_browser_hud_script(cls, accounts: List[Dict[str, Any]]) -> str:
        """
        Generates client-side JavaScript that injects a floating, glassmorphic
        SoxBot Login Assistant overlay HUD on web pages, providing 1-click auto-fill,
        live 2FA code generation and display, and automated login assistance.
        """
        if not accounts:
            return ""

        enriched_accounts = []
        for acc in accounts:
            a_copy = dict(acc)
            totp = a_copy.get("totp_secret", "")
            if totp:
                code, rem = cls.generate_totp_code(totp)
                a_copy["live_totp_code"] = code
                a_copy["totp_rem"] = rem
            enriched_accounts.append(a_copy)

        accounts_json = json.dumps(enriched_accounts)

        template = """
        (function() {
            if (window.__soxbot_hud_active) return;
            window.__soxbot_hud_active = true;

            const allAccounts = __ACCOUNTS_JSON__;
            if (!allAccounts || !allAccounts.length) return;

            const currentHost = (window.location.hostname || "").toLowerCase();
            const currentPath = (window.location.pathname || "").toLowerCase();

            let targetAccount = allAccounts.find(a => {
                const p = (a.platform || "").toLowerCase();
                if (p === "google" && (currentHost.includes("google.") || currentHost.includes("youtube."))) return true;
                if (p === "instagram" && currentHost.includes("instagram.")) return true;
                if (p === "github" && currentHost.includes("github.")) return true;
                if (p === "tiktok" && currentHost.includes("tiktok.")) return true;
                if (p === "twitter" && (currentHost.includes("twitter.") || currentHost.includes("x.com"))) return true;
                if (p === "discord" && currentHost.includes("discord.")) return true;
                if (p === "reddit" && currentHost.includes("reddit.")) return true;
                if (p === "spotify" && currentHost.includes("spotify.")) return true;
                if (p === "facebook" && currentHost.includes("facebook.")) return true;
                if (a.login_url && currentHost) {
                    try {
                        const parsedHost = new URL(a.login_url).hostname.toLowerCase();
                        if (currentHost === parsedHost || currentHost.endsWith("." + parsedHost) || parsedHost.endsWith("." + currentHost)) return true;
                    } catch (e) {}
                }
                return false;
            });

            // STRICT: Never inject or autofill credentials on unrelated websites
            if (!targetAccount) return;

            function setNativeValue(el, val) {
                if (!el || el.value === val) return;
                el.focus();
                const lastVal = el.value;
                const desc = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
                if (desc && desc.set) {
                    desc.set.call(el, val);
                } else {
                    el.value = val;
                }
                if (el._valueTracker) {
                    el._valueTracker.setValue(lastVal);
                }
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
                el.dispatchEvent(new KeyboardEvent('keydown', { bubbles: true, key: 'a' }));
                el.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true, key: 'a' }));
            }

            function executeFormFill(clickSubmit) {
                const u = targetAccount.username || "";
                const p = targetAccount.password || "";

                const uInputs = document.querySelectorAll("input[type='email'], input[name='username'], input[name='login'], input[name='identifier'], #identifierId, #login_field, input[aria-label*='Phone number'], input[aria-label*='username'], input[type='text']");
                for (const inp of uInputs) {
                    if (inp && inp.offsetParent !== null) {
                        setNativeValue(inp, u);
                        break;
                    }
                }

                const pInputs = document.querySelectorAll("input[type='password'], input[name='password'], input[name='Passwd'], #password, input[aria-label*='Password']");
                for (const inp of pInputs) {
                    if (inp && inp.offsetParent !== null) {
                        setNativeValue(inp, p);
                        break;
                    }
                }

                if (clickSubmit) {
                    setTimeout(function() {
                        const sub = document.querySelector("button[type='submit'], input[type='submit'], #identifierNext, #passwordNext, button[data-e2e='login-button'], button._acan, button.login");
                        if (sub && typeof sub.click === 'function') {
                            sub.click();
                        }
                    }, 400);
                }
            }

            function createHUD() {
                if (document.getElementById("soxbot-login-assistant-hud")) return;

                const hud = document.createElement("div");
                hud.id = "soxbot-login-assistant-hud";
                hud.style.cssText = "position: fixed !important; top: 16px !important; right: 16px !important; z-index: 2147483647 !important; " +
                    "background: rgba(15, 23, 42, 0.96) !important; backdrop-filter: blur(16px) !important; -webkit-backdrop-filter: blur(16px) !important; " +
                    "border: 1px solid rgba(59, 130, 246, 0.5) !important; border-radius: 12px !important; padding: 10px 16px !important; " +
                    "font-family: system-ui, -apple-system, sans-serif !important; box-shadow: 0 12px 32px rgba(0, 0, 0, 0.7), 0 0 16px rgba(59, 130, 246, 0.2) !important; " +
                    "color: #f8fafc !important; display: flex !important; align-items: center !important; gap: 12px !important; font-size: 12px !important; pointer-events: auto !important;";

                const infoBox = document.createElement("div");
                infoBox.style.cssText = "display: flex; flex-direction: column; gap: 2px;";
                const platformIcon = targetAccount.platform === "google" ? "🌐" : (targetAccount.platform === "instagram" ? "📸" : (targetAccount.platform === "github" ? "🐙" : (targetAccount.platform === "tiktok" ? "🎵" : "🔑")));
                infoBox.innerHTML = '<span style="font-weight: 700; color: #38bdf8; font-size: 12px;">' + platformIcon + ' OXBROWSER Login Assistant</span>' +
                    '<span style="color: #94a3b8; font-size: 11px;">' + (targetAccount.username || targetAccount.name) + '</span>';
                hud.appendChild(infoBox);

                const btnFill = document.createElement("button");
                btnFill.id = "soxbot-btn-autofill";
                btnFill.innerText = "⚡ Auto-Fill & Login";
                btnFill.style.cssText = "background: linear-gradient(135deg, #2563eb, #1d4ed8) !important; color: white !important; " +
                    "border: none !important; padding: 6px 12px !important; border-radius: 6px !important; font-weight: 700 !important; cursor: pointer !important; font-size: 11px !important;";
                btnFill.onclick = function() {
                    executeFormFill(true);
                };
                hud.appendChild(btnFill);

                if (targetAccount.totp_secret) {
                    const btn2fa = document.createElement("button");
                    const liveCode = targetAccount.live_totp_code || "Copy 2FA";
                    btn2fa.innerText = "🔑 2FA: " + liveCode;
                    btn2fa.style.cssText = "background: #0f172a !important; border: 1px solid #10b981 !important; color: #34d399 !important; " +
                        "padding: 6px 10px !important; border-radius: 6px !important; font-weight: 700 !important; cursor: pointer !important; font-size: 11px !important;";
                    btn2fa.onclick = function() {
                        if (targetAccount.live_totp_code) {
                            navigator.clipboard.writeText(targetAccount.live_totp_code).then(() => {
                                btn2fa.innerText = "✓ Copied!";
                                setTimeout(() => { btn2fa.innerText = "🔑 2FA: " + targetAccount.live_totp_code; }, 2000);
                            }).catch(() => {});
                        }
                    };
                    hud.appendChild(btn2fa);
                }

                const btnClose = document.createElement("button");
                btnClose.innerHTML = "✕";
                btnClose.title = "Dismiss Assistant";
                btnClose.style.cssText = "background: transparent !important; border: none !important; color: #64748b !important; font-size: 14px !important; cursor: pointer !important; padding: 0 4px !important;";
                btnClose.onclick = function() {
                    hud.remove();
                };
                hud.appendChild(btnClose);

                document.body.appendChild(hud);

                if (targetAccount.auto_login_on_launch) {
                    btnFill.innerText = "⏳ Auto-logging in (1s)...";
                    btnFill.style.background = "#ca8a04";
                    setTimeout(function() {
                        executeFormFill(true);
                        btnFill.innerText = "✓ Login Injected";
                        btnFill.style.background = "#16a34a";
                    }, 1200);
                }
            }

            // Proactively create HUD once when DOM ready
            let hudCreated = false;
            let hudAttempts = 0;
            const hudPoller = setInterval(() => {
                hudAttempts++;
                if (document.body && !hudCreated) {
                    createHUD();
                    hudCreated = true;
                    clearInterval(hudPoller);
                }
                if (hudAttempts > 20) clearInterval(hudPoller);
            }, 300);

            if (document.readyState === "loading") {
                document.addEventListener("DOMContentLoaded", createHUD);
            } else {
                createHUD();
            }
        })();
        """
        return template.replace("__ACCOUNTS_JSON__", accounts_json)

    # -------------------------------------------------------------------------
    # Automated Browser Login Execution
    # -------------------------------------------------------------------------

    @classmethod
    async def is_account_authenticated(cls, context_or_page: Any, account: Dict[str, Any]) -> bool:
        """
        Checks if the browser context currently holds valid session/auth cookies for the account platform.
        """
        if not context_or_page or not account:
            return False

        plat = account.get("platform", "custom")
        plat_info = cls.get_platform_info(plat)
        target_domains = [d.lower() for d in plat_info.get("domains", [])]

        cookies: List[Dict[str, Any]] = []
        try:
            if hasattr(context_or_page, "cookies") and callable(getattr(context_or_page, "cookies")):
                res = await context_or_page.cookies()
                if isinstance(res, list):
                    cookies = res
            elif hasattr(context_or_page, "context") and hasattr(context_or_page.context, "cookies"):
                res = await context_or_page.context.cookies()
                if isinstance(res, list):
                    cookies = res
        except Exception:
            return False

        if not cookies or not isinstance(cookies, list):
            return False

        auth_cookie_names = {
            "google": ["SID", "SSID", "HSID", "SAPISID", "__Secure-1PSID", "APISID", "LOGIN_INFO"],
            "instagram": ["sessionid", "ds_user_id"],
            "github": ["user_session", "logged_in"],
            "tiktok": ["sessionid", "sessionid_ss", "sid_tt"],
            "twitter": ["auth_token", "twid", "ct0"],
            "discord": ["token"],
            "spotify": ["sp_t", "sp_dc"],
            "reddit": ["reddit_session", "token_v2"],
            "facebook": ["c_user", "xs"]
        }
        known_auth_names = auth_cookie_names.get(plat, [])

        for c in cookies:
            c_domain = str(c.get("domain", "")).lower()
            c_name = str(c.get("name", ""))
            
            if any(td in c_domain for td in target_domains):
                if known_auth_names:
                    if c_name in known_auth_names and c.get("value"):
                        return True
                else:
                    if c.get("value") and len(str(c.get("value", ""))) > 8:
                        return True

        return False

    @classmethod
    async def perform_account_login(cls, page: Any, account: Dict[str, Any]) -> bool:
        """
        Executes human-like automated login on given browser page context.
        """
        if not page or not account:
            return False

        plat = account.get("platform", "custom")
        plat_info = cls.get_platform_info(plat)
        login_url = account.get("login_url") or plat_info.get("login_url", "")
        username = account.get("username", "")
        password = account.get("password", "")

        try:
            # Check if user already has an active authenticated session
            if await cls.is_account_authenticated(page, account):
                logger.info(f"[AccountManager] Account '{account.get('name', username)}' ({plat_info['name']}) is already authenticated via cookies. Skipping login redirect.")
                return True

            cur_url = ""
            if hasattr(page, "url"):
                cur_url = page.url or ""
            elif hasattr(page, "evaluate"):
                try:
                    cur_url = await page.evaluate("window.location.href")
                except Exception:
                    pass

            target_domains = plat_info.get("domains", [])
            domain_match = any(d in cur_url.lower() for d in target_domains)

            # If the current page is on an unrelated website (e.g. duckduckgo.com), only navigate if start_url was explicitly login
            if not domain_match:
                if not any(d in cur_url.lower() for d in ["about:blank", "about:home", "about:newtab"]):
                    logger.debug(f"[AccountManager] Current page ({cur_url}) does not belong to {plat_info['name']}. Skipping auto-login navigation.")
                    return False

            if not domain_match and login_url:
                logger.info(f"[AccountManager] Navigating to {plat_info['name']} login URL: {login_url}")
                if hasattr(page, "goto"):
                    await page.goto(login_url, timeout=45000, wait_until="domcontentloaded")
                elif hasattr(page, "get"):
                    await page.get(login_url)

            # Wait for page readiness
            if hasattr(page, "wait_for_timeout"):
                await page.wait_for_timeout(1800)
            else:
                await asyncio.sleep(1.8)

            user_selectors = plat_info.get("user_selectors", ["input[name='username']", "input[type='email']", "input[type='text']"])
            user_next_selectors = plat_info.get("user_next_selectors", ["#identifierNext", "button[type='button']", "button[type='submit']"])
            pass_selectors = plat_info.get("pass_selectors", ["input[name='password']", "input[type='password']"])
            pass_next_selectors = plat_info.get("pass_next_selectors", ["#passwordNext", "button[type='submit']", "button[type='button']"])
            btn_selectors = plat_info.get("next_btn_selectors", ["button[type='submit']", "button._acan", "input[type='submit']"])
            totp_selectors = plat_info.get("totp_selectors", ["input[type='tel']", "input[name='totpPin']", "#totpPin", "input[autocomplete='one-time-code']", "input[name='code']"])
            totp_next_selectors = plat_info.get("totp_next_selectors", ["#totpNext", "button[type='submit']"])

            filled_user = False
            filled_pass = False
            filled_totp = False

            # 1. Robust Native fill via Playwright / Automation API
            if hasattr(page, "wait_for_selector") and hasattr(page, "fill"):
                # Phase 1: Fill Username
                if username:
                    for u_sel in user_selectors:
                        try:
                            u_el = await page.wait_for_selector(u_sel, state="visible", timeout=3500)
                            if u_el:
                                await u_el.click()
                                await asyncio.sleep(0.1)
                                await u_el.fill(username)
                                filled_user = True
                                break
                        except Exception:
                            continue

                # Multi-step detection: if user filled, check if password field is already visible or if we need to click Next
                if filled_user and account.get("auto_login_on_launch") and password:
                    pass_already_visible = False
                    for p_sel in pass_selectors:
                        try:
                            p_chk = await page.query_selector(p_sel)
                            if p_chk and (not hasattr(p_chk, "is_visible") or await p_chk.is_visible()):
                                pass_already_visible = True
                                break
                        except Exception:
                            pass

                    if not pass_already_visible:
                        # Click Next to reveal password step (Google, Twitter, Microsoft, etc.)
                        await asyncio.sleep(0.3)
                        for b_sel in (user_next_selectors + btn_selectors):
                            try:
                                b_el = await page.query_selector(b_sel)
                                if b_el and (not hasattr(b_el, "is_visible") or await b_el.is_visible()):
                                    await b_el.click()
                                    break
                            except Exception:
                                continue
                        await asyncio.sleep(1.0)

                # Phase 2: Fill Password (wait for it to become visible on multi-step forms)
                if password:
                    for p_sel in pass_selectors:
                        try:
                            p_el = await page.wait_for_selector(p_sel, state="visible", timeout=6000)
                            if p_el:
                                await p_el.click()
                                await asyncio.sleep(0.15)
                                await p_el.fill(password)
                                filled_pass = True
                                break
                        except Exception:
                            continue

                    if filled_pass and account.get("auto_login_on_launch"):
                        await asyncio.sleep(0.4)
                        for b_sel in (pass_next_selectors + btn_selectors):
                            try:
                                b_el = await page.query_selector(b_sel)
                                if b_el and (not hasattr(b_el, "is_visible") or await b_el.is_visible()):
                                    await b_el.click()
                                    break
                            except Exception:
                                continue
                        await asyncio.sleep(1.0)

                # Phase 3: Fill RFC 6238 TOTP 2FA if configured
                totp_secret = account.get("totp_secret", "")
                if totp_secret:
                    totp_code, _ = cls.generate_totp_code(totp_secret)
                    if totp_code:
                        for t_sel in totp_selectors:
                            try:
                                t_el = await page.wait_for_selector(t_sel, state="visible", timeout=4000)
                                if t_el:
                                    await t_el.click()
                                    await asyncio.sleep(0.1)
                                    await t_el.fill(totp_code)
                                    filled_totp = True
                                    if account.get("auto_login_on_launch"):
                                        await asyncio.sleep(0.3)
                                        for b_sel in (totp_next_selectors + btn_selectors):
                                            try:
                                                b_el = await page.query_selector(b_sel)
                                                if b_el and (not hasattr(b_el, "is_visible") or await b_el.is_visible()):
                                                    await b_el.click()
                                                    break
                                            except Exception:
                                                continue
                                    break
                            except Exception:
                                continue

            # 2. Reactive JavaScript fallback injection
            script = cls.generate_autofill_script(account)
            if hasattr(page, "evaluate"):
                try:
                    await page.evaluate(script)
                except Exception as eval_err:
                    if "closed" in str(eval_err).lower():
                        return True
                    raise eval_err

            logger.info(f"[AccountManager] Successfully assisted login for '{account.get('name', username)}' ({plat_info['name']}).")
            return True
        except Exception as e:
            if "closed" in str(e).lower():
                return True
            logger.warning(f"[AccountManager] Automated login assistance notice for '{account.get('name')}': {e}")
            return False
