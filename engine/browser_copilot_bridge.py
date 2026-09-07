import os
import sys
import time
import io
import re
import inspect
import json
import base64
import asyncio
import logging
import traceback
from typing import Optional, Dict, Any, List, Tuple, Callable

from storage.profile_manager import ProfileManager
from engine.browser import BrowserLauncher

logger = logging.getLogger("BrowserCopilotBridge")


class BrowserCopilotBridge:
    """
    Live Interaction Bridge between AI Swarm Copilot and running Camoufox/Playwright instances:
    - Lists active profiles and their live page tabs.
    - Captures real-time Viewport screenshots as Base64 for multimodal LLM vision.
    - Flattens live Shadow-DOM & normal DOM into token-efficient interactive element maps.
    - Safely executes arbitrary Playwright scripts in an isolated sandbox with stdout/stderr capture.
    """

    _instance: Optional['BrowserCopilotBridge'] = None

    def __init__(self, launcher: Optional[BrowserLauncher] = None, profile_manager: Optional[ProfileManager] = None):
        self.profile_manager = profile_manager or ProfileManager()
        self.launcher = launcher or BrowserLauncher.get_instance(self.profile_manager)

    @classmethod
    def get_instance(cls, launcher: Optional[BrowserLauncher] = None) -> 'BrowserCopilotBridge':
        if cls._instance is None:
            cls._instance = BrowserCopilotBridge(launcher=launcher)
        elif launcher is not None:
            cls._instance.launcher = launcher
        return cls._instance

    # -------------------------------------------------------------------------
    # Active Tab & Profile Discovery
    # -------------------------------------------------------------------------
    def _resolve_target_profile(self, profile_id: Optional[str] = None) -> Tuple[Optional[str], Optional[Any]]:
        """Resolves target profile ID and active page, falling back to any live browser instance."""
        active_map = getattr(self.launcher, "running_processes", {}) or getattr(self.launcher, "active_contexts", {})
        if not active_map:
            active_map = BrowserLauncher._shared_active_contexts

        target_pid = profile_id
        if target_pid in ["default", "none", "None", ""] or not target_pid:
            target_pid = None

        if target_pid:
            page = self.get_active_page_for_profile(target_pid)
            if page is not None:
                return target_pid, page

        if target_pid:
            for pid in active_map.keys():
                prof = self.profile_manager.load_profile(pid) or {}
                if prof.get("name", "").lower() == target_pid.lower() or target_pid.lower() in pid.lower():
                    page = self.get_active_page_for_profile(pid)
                    if page is not None:
                        return pid, page

        if active_map:
            first_pid = next(iter(active_map.keys()))
            page = self.get_active_page_for_profile(first_pid)
            if page is not None:
                return first_pid, page

        # Fallback check
        page = self.get_active_page_for_profile(target_pid)
        if page is not None:
            return target_pid or "active", page

        return None, None

    def get_running_profiles(self) -> List[Dict[str, Any]]:
        """Returns metadata for all currently running browser profiles."""
        running = []
        try:
            active_map = getattr(self.launcher, "running_processes", {}) or getattr(self.launcher, "active_contexts", {})
            if not active_map:
                active_map = BrowserLauncher._shared_active_contexts

            for pid in active_map.keys():
                prof = self.profile_manager.load_profile(pid) or {}
                running.append({
                    "id": pid,
                    "name": prof.get("name", pid),
                    "os": prof.get("os", "windows"),
                    "engine": prof.get("engine", "camoufox"),
                    "proxy": prof.get("proxy", {}),
                    "is_active": True
                })
        except Exception as e:
            logger.debug(f"[BrowserCopilotBridge] Discovery note: {e}")
        return running

    def get_active_page_for_profile(self, profile_id: Optional[str] = None) -> Optional[Any]:
        """Retrieves the active Playwright Page object for a running profile."""
        try:
            if hasattr(self.launcher, "get_active_page"):
                page = self.launcher.get_active_page(profile_id)
                if page is not None:
                    return page

            active_map = getattr(self.launcher, "running_processes", {}) or getattr(self.launcher, "active_contexts", {})
            if not active_map:
                active_map = BrowserLauncher._shared_active_contexts

            target_pid = profile_id
            if not target_pid or target_pid == "default":
                target_pid = next(iter(active_map.keys())) if active_map else None

            if not target_pid:
                return None

            ctx = active_map.get(target_pid)
            if ctx is not None:
                if hasattr(ctx, "pages") and ctx.pages:
                    return ctx.pages[-1]
                if hasattr(ctx, "contexts") and ctx.contexts:
                    sub = ctx.contexts[0]
                    if hasattr(sub, "pages") and sub.pages:
                        return sub.pages[-1]
                if hasattr(ctx, "main_tab") and ctx.main_tab:
                    return ctx.main_tab
                if hasattr(ctx, "tabs") and ctx.tabs:
                    return ctx.tabs[-1]
                if hasattr(ctx, "page"):
                    return ctx.page
                if hasattr(ctx, "evaluate"):
                    return ctx
        except Exception as e:
            logger.debug(f"[BrowserCopilotBridge] Page access note: {e}")
        return None

    # -------------------------------------------------------------------------
    # Real-Time Viewport Screenshot Capture
    # -------------------------------------------------------------------------
    async def capture_viewport_base64(self, profile_id: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        """
        Captures the current viewport of the specified profile (or first active profile)
        and returns (base64_jpeg_string, profile_name).
        """
        target_pid, page = self._resolve_target_profile(profile_id)

        if not target_pid:
            return None, "No active browser profile currently running."

        prof = self.profile_manager.load_profile(target_pid) or {}
        p_name = prof.get("name", target_pid)

        if not page or not hasattr(page, "screenshot"):
            return None, f"Browser profile '{p_name}' has no active Playwright page attached."

        try:
            screenshot_bytes = await page.screenshot(type="jpeg", quality=85, full_page=False)
            b64_str = base64.b64encode(screenshot_bytes).decode("utf-8")
            return b64_str, p_name
        except Exception as e:
            logger.error(f"[BrowserCopilotBridge] Screenshot failed: {e}")
            return None, f"Screenshot error: {e}"

    # -------------------------------------------------------------------------
    # Live DOM Inspection & Shadow-DOM Tree Flattener
    # -------------------------------------------------------------------------
    async def inspect_live_dom(self, profile_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Extracts high-value interactive DOM & Shadow-DOM elements (buttons, inputs, links, iframes)
        with geometry and accessibility tags for LLM reasoning.
        """
        target_pid, page = self._resolve_target_profile(profile_id)

        if not target_pid:
            return {"error": "No running browser session found."}

        if not page or not hasattr(page, "evaluate"):
            return {"error": "Active page handle unavailable."}

        inspect_js = """
        (() => {
            const items = [];
            function isVisible(el) {
                if (!el) return false;
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.display !== 'none' && 
                       style.visibility !== 'hidden' && 
                       style.opacity !== '0' &&
                       rect.width > 4 && rect.height > 4;
            }

            function scan(root) {
                const candidates = root.querySelectorAll('button, a, input, select, textarea, [role="button"], [onclick], iframe');
                for (const el of candidates) {
                    if (!isVisible(el)) continue;
                    const rect = el.getBoundingClientRect();
                    const tag = el.tagName.toLowerCase();
                    const text = (el.innerText || el.textContent || el.value || el.placeholder || el.getAttribute('aria-label') || '').trim().slice(0, 80);
                    
                    let selector = tag;
                    if (el.id) selector += '#' + el.id;
                    else if (el.className && typeof el.className === 'string') {
                        const cls = el.className.split(' ').filter(c => c.length > 2)[0];
                        if (cls) selector += '.' + cls;
                    }

                    items.push({
                        tag: tag,
                        text: text,
                        selector: selector,
                        id: el.id || '',
                        role: el.getAttribute('role') || '',
                        rect: {
                            x: Math.round(rect.left),
                            y: Math.round(rect.top),
                            width: Math.round(rect.width),
                            height: Math.round(rect.height)
                        }
                    });
                    if (items.length >= 40) break;
                }

                // Traverse Shadow Roots
                const all = root.querySelectorAll('*');
                for (const node of all) {
                    if (node.shadowRoot && items.length < 40) {
                        scan(node.shadowRoot);
                    }
                }
            }

            scan(document);
            return {
                url: window.location.href,
                title: document.title,
                viewport: { width: window.innerWidth, height: window.innerHeight },
                interactive_elements: items
            };
        })()
        """
        try:
            res = await page.evaluate(inspect_js)
            return res
        except Exception as e:
            return {"error": f"DOM evaluation failed: {e}"}

    # -------------------------------------------------------------------------
    # Live Interactive Script Runner Sandbox (Dual Python & JavaScript Engine)
    # -------------------------------------------------------------------------
    async def execute_in_sandbox(
        self,
        script_code: str,
        profile_id: Optional[str] = None,
        timeout_sec: float = 30.0
    ) -> Dict[str, Any]:
        """
        Executes arbitrary JavaScript or Playwright/Python code against the active browser page
        in a sandboxed async scope. Captures return value and console output.
        Automatically detects JavaScript vs Python scripts.
        """
        target_pid, page = self._resolve_target_profile(profile_id)

        raw_trimmed = script_code.strip()
        first_line = raw_trimmed.splitlines()[0].lower() if raw_trimmed else ""
        is_explicit_js = (
            first_line.startswith("```js")
            or first_line.startswith("```javascript")
            or first_line.startswith("```html")
        )

        # Clean markdown wrappers if present
        clean_code = raw_trimmed
        if clean_code.startswith("```"):
            lines = clean_code.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            clean_code = "\n".join(lines).strip()

        # Heuristic detection for JavaScript
        js_patterns = [
            r"\bconst\s+", r"\blet\s+", r"\bvar\s+", r"\bfunction\s*\(", r"\bfunction\s+\w+",
            r"\bdocument\.", r"\bwindow\.", r"\bconsole\.", r"\bHTMLCanvasElement\b",
            r"\bObject\.defineProperty\b", r"\bWebGLRenderingContext\b", r"\bnavigator\.",
            r"\baddEventListener\s*\(", r"=>"
        ]
        is_js = is_explicit_js or any(re.search(p, clean_code) for p in js_patterns)

        wrapped_code = f"async def _copilot_user_script(page):\n"
        for line in clean_code.splitlines():
            wrapped_code += f"    {line}\n"

        if not is_js:
            try:
                compile(wrapped_code, "<string>", "exec")
            except SyntaxError:
                is_js = True

        t0 = time.time()
        stdout_capture = io.StringIO()

        # 1. Direct In-Tab JavaScript Evaluation
        if is_js:
            if not page:
                return {
                    "success": False,
                    "output": "",
                    "result": None,
                    "duration_ms": 0.0,
                    "error": (
                        f"No active browser tab found for profile '{target_pid or 'default'}'. "
                        "Please launch the browser profile first to execute JavaScript in the active tab."
                    )
                }

            try:
                js_to_run = clean_code
                if "return " not in js_to_run and not js_to_run.strip().startswith("(() =>"):
                    js_to_run = f"(() => {{\n{clean_code}\n}})()"

                if hasattr(page, "evaluate"):
                    eval_coro = page.evaluate(js_to_run)
                    if inspect.isawaitable(eval_coro):
                        res = await asyncio.wait_for(eval_coro, timeout=timeout_sec)
                    else:
                        res = eval_coro
                elif hasattr(page, "execute_script"):
                    res = await asyncio.wait_for(
                        asyncio.to_thread(page.execute_script, clean_code),
                        timeout=timeout_sec
                    )
                else:
                    return {
                        "success": False,
                        "output": "",
                        "result": None,
                        "duration_ms": 0.0,
                        "error": f"Active browser page object ({type(page).__name__}) does not support script evaluation."
                    }

                dur_ms = (time.time() - t0) * 1000.0
                return {
                    "success": True,
                    "output": f"[JavaScript Evaluated in Tab: {target_pid}]",
                    "result": str(res) if res is not None else "JavaScript evaluated successfully (undefined/void)",
                    "duration_ms": round(dur_ms, 1),
                    "error": None
                }
            except asyncio.TimeoutError:
                return {
                    "success": False,
                    "output": "",
                    "result": None,
                    "duration_ms": timeout_sec * 1000.0,
                    "error": f"JavaScript execution timed out after {timeout_sec}s"
                }
            except Exception as e:
                dur_ms = (time.time() - t0) * 1000.0
                return {
                    "success": False,
                    "output": "",
                    "result": None,
                    "duration_ms": round(dur_ms, 1),
                    "error": f"JavaScript Evaluation Error: {e}"
                }

        # 2. Python / Playwright Sandbox Execution
        scope_globals: Dict[str, Any] = {
            "asyncio": asyncio,
            "page": page,
            "profile_id": target_pid,
            "print": lambda *args, **kwargs: print(*args, file=stdout_capture, **kwargs),
            "logger": logging.getLogger("CopilotSandbox")
        }

        wrapped_code = f"async def _copilot_user_script(page):\n"
        for line in clean_code.splitlines():
            wrapped_code += f"    {line}\n"

        try:
            exec(wrapped_code, scope_globals)
            user_func = scope_globals.get("_copilot_user_script")
            if callable(user_func):
                ret_val = user_func(page)
                if inspect.isawaitable(ret_val):
                    res = await asyncio.wait_for(ret_val, timeout=timeout_sec)
                else:
                    res = ret_val
            else:
                res = "Execution entry point missing"

            dur_ms = (time.time() - t0) * 1000.0

            return {
                "success": True,
                "output": stdout_capture.getvalue().strip(),
                "result": str(res) if res is not None else "Completed successfully",
                "duration_ms": round(dur_ms, 1),
                "error": None
            }
        except asyncio.TimeoutError:
            return {
                "success": False,
                "output": stdout_capture.getvalue().strip(),
                "result": None,
                "duration_ms": timeout_sec * 1000.0,
                "error": f"Script execution timed out after {timeout_sec}s"
            }
        except Exception as e:
            dur_ms = (time.time() - t0) * 1000.0
            err_trace = traceback.format_exc()
            return {
                "success": False,
                "output": stdout_capture.getvalue().strip(),
                "result": None,
                "duration_ms": round(dur_ms, 1),
                "error": f"{type(e).__name__}: {e}\n{err_trace}"
            }
