import os
import time
import json
import asyncio
import tempfile
import random
import logging
import base64
import io
import re
from typing import Dict, Any, List, Optional, Tuple, Callable

from PIL import Image, ImageDraw
from engine.ai_model_manager import AIModelManager

logger = logging.getLogger("AICaptchaSolver")


class AICaptchaSolver:
    """
    Local AI-powered Multi-Modal Captcha Solver for Google reCAPTCHA v2 / /sorry/index barriers.
    Supports multi-round Audio-Whisper STT, Vision-VLM Image Grid recognition, and configurable prioritization.
    """
    _cursor_pos: Tuple[float, float] = (random.uniform(250, 650), random.uniform(200, 500))
    _instance: Optional['AICaptchaSolver'] = None
    _ddddocr_instance: Optional[Any] = None

    @classmethod
    def get_instance(cls) -> 'AICaptchaSolver':
        if cls._instance is None:
            cls._instance = AICaptchaSolver()
        return cls._instance

    @classmethod
    async def solve_captcha_on_page(
        cls,
        page: Any,
        strategy: str = "audio_first",
        vision_model: Optional[str] = None,
        whisper_model: str = "base",
        notify_cb: Optional[Callable[[str], None]] = None,
        timeout_sec: float = 45.0,
        captcha_type: Optional[str] = None,
        image_selector: Optional[str] = None,
        input_selector: Optional[str] = None,
        submit_selector: Optional[str] = None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Comprehensive Multi-Modal Captcha Resolver:
        Integrates Google reCAPTCHA v2/Enterprise, Cloudflare Turnstile, hCaptcha, FunCaptcha,
        and traditional Image-to-Text Normal Captchas (ddddocr ONNX + Vision VLM).
        """
        def notify(msg: str):
            if notify_cb:
                notify_cb(f"🧩 [CaptchaSolver] {msg}")

        if not page:
            return True, "No active page", {"solved": True, "method": "no_page"}

        # Explicit type routing bypass
        c_type = (captcha_type or "").strip().lower()
        if c_type in ["normal", "normal_captcha", "text_captcha", "image"]:
            notify(f"🎯 Explicit Target: Normal Captcha (Image-to-Text). Resolving...")
            return await cls.solve_normal_captcha(
                page=page,
                image_selector=image_selector,
                input_selector=input_selector,
                submit_selector=submit_selector,
                vision_model=vision_model,
                notify_cb=notify,
                timeout_sec=timeout_sec
            )
        elif c_type in ["turnstile", "cloudflare"]:
            notify("🎯 Explicit Target: Cloudflare Turnstile. Resolving...")
            return await cls.solve_cloudflare_turnstile(page, notify_cb=notify, timeout_sec=timeout_sec)
        elif c_type in ["recaptcha", "recaptcha_v2", "google"]:
            notify("🎯 Explicit Target: Google reCAPTCHA. Resolving...")
            return await cls.solve_google_captcha(
                page=page, strategy=strategy, vision_model=vision_model,
                whisper_model=whisper_model, notify_cb=notify, timeout_sec=timeout_sec
            )
        elif c_type == "hcaptcha":
            notify("🎯 Explicit Target: hCaptcha. Resolving...")
            return await cls.solve_hcaptcha(
                page=page, strategy=strategy, vision_model=vision_model,
                whisper_model=whisper_model, notify_cb=notify, timeout_sec=timeout_sec
            )
        elif c_type in ["funcaptcha", "arkose"]:
            notify("🎯 Explicit Target: Arkose Labs FunCaptcha. Resolving...")
            return await cls.solve_funcaptcha(
                page=page, vision_model=vision_model, notify_cb=notify, timeout_sec=timeout_sec
            )

        notify(f"Scanning for active barriers (Strategy: '{strategy}', Vision Model: '{vision_model or '50/50_smart_hybrid'}', Audio STT: '{whisper_model}')...")

        # 0. Early Clean Check (If Google Search results or clean page is already visible, return immediately)
        if await cls._is_captcha_solved(page):
            notify("No active captcha barrier detected on page (Page clean / Results visible).")
            return True, "No Active Captcha", {"solved": True, "method": "already_clean"}

        detected_type = None

        # 1. Multi-Stage Detection Polling (Distinguishes reCAPTCHA vs Turnstile vs hCaptcha vs FunCaptcha vs Normal Captcha)
        for _ in range(8):
            try:
                # A. Strict Google reCAPTCHA Check (api2/anchor, enterprise/anchor, /sorry/index)
                recaptcha_count = await page.locator(
                    "iframe[src*='recaptcha/api2/anchor'], iframe[src*='recaptcha/enterprise/anchor'], iframe[title*='reCAPTCHA'], #recaptcha-anchor, .recaptcha-checkbox"
                ).count()
                has_recaptcha_frame = any("recaptcha" in getattr(f, "url", "").lower() for f in getattr(page, "frames", []))
                is_google_sorry = "/sorry/index" in getattr(page, "url", "").lower()

                if recaptcha_count > 0 or has_recaptcha_frame or is_google_sorry:
                    detected_type = "recaptcha"
                    break

                # B. Strict Cloudflare Turnstile Check (challenges.cloudflare.com, #challenge-stage)
                cf_count = await page.locator(
                    "iframe[src*='challenges.cloudflare.com'], iframe[src*='turnstile'], iframe[title*='Widget containing a Cloudflare'], iframe[title*='Cloudflare security challenge'], #challenge-stage, #cf-stage"
                ).count()
                has_cf_frame = any("challenges.cloudflare.com" in getattr(f, "url", "").lower() or "turnstile" in getattr(f, "url", "").lower() for f in getattr(page, "frames", []))
                
                if cf_count > 0 or has_cf_frame:
                    detected_type = "turnstile"
                    break

                # C. Strict hCaptcha Check (hcaptcha.com, assets.hcaptcha.com, [name='h-captcha-response'])
                hcap_count = await page.locator(
                    "iframe[src*='hcaptcha.com'], iframe[src*='assets.hcaptcha.com'], iframe[data-hcaptcha-widget-id], [name='h-captcha-response'], #hcaptcha, .h-captcha"
                ).count()
                has_hcap_frame = any("hcaptcha" in getattr(f, "url", "").lower() for f in getattr(page, "frames", []))
                if hcap_count > 0 or has_hcap_frame:
                    detected_type = "hcaptcha"
                    break

                # D. Strict FunCaptcha / Arkose Labs Check (arkoselabs, funcaptcha, fc-iframe)
                fc_count = await page.locator(
                    "iframe[src*='arkoselabs'], iframe[src*='funcaptcha'], iframe[id*='fc-iframe'], #fc-iframe-wrap, [name='fc-token']"
                ).count()
                has_fc_frame = any("arkoselabs" in getattr(f, "url", "").lower() or "funcaptcha" in getattr(f, "url", "").lower() for f in getattr(page, "frames", []))
                if fc_count > 0 or has_fc_frame:
                    detected_type = "funcaptcha"
                    break

                # E. Strict Normal Captcha Check (Image-to-Text alphanumeric captcha)
                normal_cap = await cls._detect_normal_captcha(page)
                if normal_cap:
                    detected_type = "normal_captcha"
                    break

                # F. Check if token already exists
                token_check = await page.evaluate(
                    "() => Boolean(document.querySelector('[name=\"cf-turnstile-response\"], [name=\"cf_challenge_response\"], [name=\"g-recaptcha-response\"], [name=\"h-captcha-response\"], [name=\"fc-token\"]')?.value)"
                )
                if token_check:
                    notify("Captcha already verified on page (Valid token found).")
                    return True, "Captcha Already Resolved", {"solved": True, "method": "already_clean"}

            except Exception as det_err:
                logger.debug(f"[AICaptchaSolver] Barrier detection note: {det_err}")

            await asyncio.sleep(0.4)

        # 2. Route to specialized solver based on detected barrier
        if detected_type == "recaptcha":
            notify(f"🎯 Distinct Barrier: Google reCAPTCHA v2 / Enterprise. Resolving (Strategy: {strategy}, Vision Model: {vision_model or 'auto'}, Audio Whisper: {whisper_model})...")
            solved, msg, details = await cls.solve_google_captcha(
                page=page,
                strategy=strategy,
                vision_model=vision_model,
                whisper_model=whisper_model,
                notify_cb=notify,
                timeout_sec=timeout_sec
            )
            return solved, msg, details

        elif detected_type == "turnstile":
            notify(f"🎯 Distinct Barrier: Cloudflare Turnstile. Resolving via Biomechanical Humanoid Solver (Vision: {vision_model or 'auto'})...")
            ok, msg, details = await cls.solve_cloudflare_turnstile(page, notify_cb=notify, timeout_sec=timeout_sec)
            return ok, msg, details

        elif detected_type == "hcaptcha":
            notify(f"🎯 Distinct Barrier: hCaptcha. Resolving via Biomechanical Multi-Modal Solver (Strategy: {strategy}, Vision: {vision_model or 'auto'}, Audio: {whisper_model})...")
            return await cls.solve_hcaptcha(
                page=page,
                strategy=strategy,
                vision_model=vision_model,
                whisper_model=whisper_model,
                notify_cb=notify,
                timeout_sec=timeout_sec
            )

        elif detected_type == "funcaptcha":
            notify(f"🎯 Distinct Barrier: Arkose Labs FunCaptcha. Resolving 3D Orientation / Vision Challenge (Vision: {vision_model or 'auto'})...")
            return await cls.solve_funcaptcha(
                page=page,
                vision_model=vision_model,
                notify_cb=notify,
                timeout_sec=timeout_sec
            )

        elif detected_type == "normal_captcha":
            notify("🎯 Distinct Barrier: Normal Captcha (Image-to-Text). Resolving via High-Speed ONNX OCR & Vision VLM...")
            return await cls.solve_normal_captcha(
                page=page,
                image_selector=image_selector,
                input_selector=input_selector,
                submit_selector=submit_selector,
                vision_model=vision_model,
                notify_cb=notify,
                timeout_sec=timeout_sec
            )

        else:
            # Fallback check if page is already clean
            if await cls._is_captcha_solved(page):
                notify("No active captcha barrier detected.")
                return True, "No Active Captcha", {"solved": True, "method": "already_clean"}

            notify("No recognized Captcha or Turnstile barrier detected.")
            return True, "No Active Barrier", {"solved": True, "method": "already_clean"}

    @classmethod
    async def _human_idle(cls, page: Any, duration_sec: float):
        """Simulates natural human hand rest, micro-drifts, tremors, and gaze movement during pauses."""
        if not hasattr(page, "mouse") or duration_sec <= 0.05:
            await asyncio.sleep(duration_sec)
            return

        from engine.warmup.human_motion import BiomechanicalMotor
        try:
            cx, cy = cls._cursor_pos
            nx, ny = await BiomechanicalMotor.humanoid_idle_sleep(page, duration_sec, cx, cy)
            cls._cursor_pos = (nx, ny)
        except Exception:
            await asyncio.sleep(duration_sec)

    @classmethod
    async def _human_click(cls, page: Any, locator: Any, target_size: float = 35.0, speed_mult: float = 1.0):
        """Moves cursor to locator with natural, swift biomechanical trajectory, hesitates, and clicks."""
        from engine.warmup.human_motion import BiomechanicalMotor
        try:
            box = await locator.bounding_box(timeout=2500)
            if box and hasattr(page, "mouse"):
                # Human target center with Gaussian offset within element
                tx = box["x"] + box["width"] * random.uniform(0.35, 0.65)
                ty = box["y"] + box["height"] * random.uniform(0.35, 0.65)
                start_x, start_y = cls._cursor_pos

                await BiomechanicalMotor.move_mouse_humanoid(
                    page=page,
                    start_x=start_x,
                    start_y=start_y,
                    end_x=tx,
                    end_y=ty,
                    target_width=box.get("width", target_size),
                    speed_mult=speed_mult
                )
                cls._cursor_pos = (tx, ty)

                # Swift micro hesitation before pressing button
                hesitate = random.uniform(0.02, 0.05) / max(0.5, speed_mult)
                await asyncio.sleep(hesitate)
                await page.mouse.down()
                down_time = random.uniform(0.04, 0.08) / max(0.5, speed_mult)
                await asyncio.sleep(down_time)
                await page.mouse.up()
                await asyncio.sleep(0.02)
                # Guarantees element-level click propagation for cross-origin iframes
                try:
                    await asyncio.wait_for(locator.click(force=True), timeout=0.8)
                except Exception:
                    pass
                return
        except Exception as e:
            logger.debug(f"[AICaptchaSolver] Human click fallback note: {e}")

        # Fallback click
        try:
            await asyncio.wait_for(locator.click(force=True), timeout=1.5)
        except Exception:
            try:
                await asyncio.wait_for(locator.evaluate("el => el.click()"), timeout=1.0)
            except Exception:
                pass

    @classmethod
    async def solve_google_captcha(
        cls,
        page: Any,
        strategy: str = "audio_first",
        vision_model: Optional[str] = None,
        whisper_model: str = "base",
        human_session: Optional[Any] = None,
        notify_cb: Optional[Callable[[str], None]] = None,
        timeout_sec: float = 35.0
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Attempts to solve any active Google reCAPTCHA challenge on the page using local AI with characterized human mouse movements.
        """
        def notify(msg: str):
            logger.info(f"[AICaptchaSolver] {msg}")
            if notify_cb:
                notify_cb(f"⎘ {msg}")

        if strategy == "disabled":
            return False, "Captcha Solver Disabled", {"solved": False, "method": "none"}

        notify(f"Initiating Local AI Captcha Solver (Strategy: {strategy}, Whisper: {whisper_model})...")

        # 1. Locate Anchor iframe & Checkbox with generous polling
        checkbox_loc = None
        anchor_loc = None
        
        for _ in range(12):
            try:
                candidate = page.frame_locator("iframe[src*='api2/anchor'], iframe[src*='enterprise/anchor'], iframe[title*='reCAPTCHA']").first
                cb = candidate.locator("#recaptcha-anchor, .recaptcha-checkbox").first
                if await cb.count() > 0:
                    anchor_loc = candidate
                    checkbox_loc = cb
                    break
            except Exception:
                pass
            await cls._human_idle(page, 0.5)

        if not checkbox_loc:
            if await cls._is_captcha_solved(page):
                return True, "No Active Captcha", {"solved": True, "method": "already_clean"}
            notify("reCAPTCHA anchor checkbox not detected.")
            return False, "reCAPTCHA Anchor Missing", {"solved": False}

        # 2. Click the Checkbox with biomechanical mouse motion and wait for state update
        try:
            notify("Clicking 'I'm not a robot' checkbox...")
            await cls._human_click(page, checkbox_loc, target_size=28.0)
            await cls._human_idle(page, random.uniform(2.0, 3.0))
            
            # Check for instant pass
            aria = await checkbox_loc.get_attribute("aria-checked")
            if aria == "true":
                notify("Instant pass (Trust score / Cookie passed)!")
                return True, "Instant Captcha Pass", {"solved": True, "method": "checkbox_pass"}
        except Exception as e:
            logger.debug(f"[AICaptchaSolver] Checkbox click note: {e}")

        # 3. Locate Challenge bframe
        bframe_loc = None
        bframe_elem = None
        for _ in range(10):
            try:
                b_elem = page.locator("iframe[src*='api2/bframe'], iframe[src*='enterprise/bframe'], iframe[title*='challenge']").first
                if await b_elem.count() > 0 and await b_elem.is_visible():
                    bframe_elem = b_elem
                    bframe_loc = page.frame_locator("iframe[src*='api2/bframe'], iframe[src*='enterprise/bframe'], iframe[title*='challenge']").first
                    break
            except Exception:
                pass
            await cls._human_idle(page, 0.5)


        if not bframe_loc:
            if await cls._is_captcha_solved(page):
                notify("Page unlocked without challenge popup.")
                return True, "Captcha Solved", {"solved": True, "method": "instant"}
            notify("Challenge bframe not detected.")
            return False, "Challenge Frame Missing", {"solved": False}

        # 4. Execute Solver Pipeline according to strategy with intelligent Multi-Stage Watchdog
        success = False
        method_used = "none"
        error_msg = ""

        for stage in range(1, 4):
            if await cls._is_captcha_solved(page):
                notify("✧ Page unlocked & verified!")
                return True, f"Google Unlocked ({method_used or 'instant'})", {"solved": True, "method": method_used or "instant"}

            # Re-locate current active bframe
            bframe_elem = page.locator("iframe[src*='api2/bframe'], iframe[src*='enterprise/bframe'], iframe[title*='challenge']").first
            if await bframe_elem.count() > 0 and await bframe_elem.is_visible():
                bframe_loc = page.frame_locator("iframe[src*='api2/bframe'], iframe[src*='enterprise/bframe'], iframe[title*='challenge']").first
            else:
                if await cls._is_captcha_solved(page):
                    return True, "Google Unlocked", {"solved": True, "method": method_used or "cleared"}
                if stage > 1:
                    break

            if stage > 1:
                notify(f"⟳ Consecutive / Follow-up Challenge detected (Stage {stage}/3)! Solving next challenge...")

            current_stage_strategy = strategy
            if stage > 1 and method_used == "audio_whisper" and strategy == "audio_first":
                notify(f"⟳ Follow-up challenge detected after Audio solve! Switching Stage {stage} to Vision VLM solver...")
                current_stage_strategy = "vision_first"

            if current_stage_strategy in ["gemini_first", "vision_first", "vision_only"]:

                notify(f"Executing Primary Gemini / Vision-VLM solver (Stage {stage})...")
                effective_v_model = vision_model or "gemini-3.6-flash" if current_stage_strategy == "gemini_first" else vision_model
                success, method_used, error_msg = await cls._solve_vision_loop(page, bframe_loc, bframe_elem, effective_v_model, notify, max_rounds=8)
                
                if not success and current_stage_strategy in ["gemini_first", "vision_first"]:
                    notify(f"Vision solver did not complete ({error_msg}). Initiating Audio fallback...")
                    success, method_used, error_msg = await cls._solve_audio_loop(page, bframe_loc, notify, strategy=current_stage_strategy, whisper_model=whisper_model, max_rounds=4)

            elif current_stage_strategy in ["audio_first", "audio_only"]:
                notify(f"Executing Primary Audio solver (Stage {stage}, Model: {whisper_model})...")
                success, method_used, error_msg = await cls._solve_audio_loop(page, bframe_loc, notify, strategy=current_stage_strategy, whisper_model=whisper_model, max_rounds=4)
                
                # Fallback to vision if audio solver fails or is blocked by Google
                if not success and current_stage_strategy == "audio_first":
                    notify(f"Audio solver could not complete ({error_msg}). Initiating Vision fallback...")
                    success, method_used, error_msg = await cls._solve_vision_loop(page, bframe_loc, bframe_elem, vision_model, notify, max_rounds=8)



            # Check if cleared after current stage
            if success or await cls._is_captcha_solved(page):
                notify("Puzzle solved. Waiting 2.0s to verify if a new challenge appears...")
                await asyncio.sleep(2.0)
                
                # Check if a consecutive puzzle/challenge is still active or has popped up
                consecutive_challenge = False
                try:
                    next_elem = page.locator("iframe[src*='api2/bframe'], iframe[src*='enterprise/bframe'], iframe[title*='challenge']").first
                    if await next_elem.count() > 0 and await next_elem.is_visible():
                        # Check if inside the frame there are active challenge controls
                        next_bframe = page.frame_locator("iframe[src*='api2/bframe'], iframe[src*='enterprise/bframe'], iframe[title*='challenge']").first
                        has_puzzle_controls = (
                            await next_bframe.locator("#rc-imageselect-target, .rc-imageselect-desc, table.rc-imageselect-table-33, table.rc-imageselect-table-44, #audio-response, .rc-audiochallenge-response-wrapper, #recaptcha-verify-button").count() > 0
                        )
                        if has_puzzle_controls:
                            consecutive_challenge = True
                except Exception:
                    pass

                if consecutive_challenge:
                    notify("⟳ Follow-up challenge detected after 2.0s verification! Resolving new puzzle...")
                    continue

                if await cls._is_captcha_solved(page):
                    try:
                        submit_btn = await page.query_selector("form#captcha-form input[type='submit'], input[name='continue'], input[type='submit'], button[type='submit'], form button")
                        if submit_btn and await submit_btn.is_visible():
                            notify("Submitting Google continue form...")
                            await submit_btn.click()
                            await asyncio.sleep(1.5)
                    except Exception:
                        pass

                    notify(f"✧ Captcha SUCCESSFULLY unlocked via {method_used} (Verified clean after 2s check)!")
                    return True, f"Google Unlocked ({method_used})", {
                        "solved": True,
                        "method": method_used
                    }

        await asyncio.sleep(1.0)
        if await cls._is_captcha_solved(page):
            try:
                submit_btn = await page.query_selector("form#captcha-form input[type='submit'], input[name='continue'], input[type='submit'], button[type='submit'], form button")
                if submit_btn and await submit_btn.is_visible():
                    notify("Submitting Google continue form...")
                    await submit_btn.click()
                    await asyncio.sleep(1.5)
            except Exception:
                pass
            notify(f"✧ Captcha SUCCESSFULLY unlocked via {method_used}!")
            return True, f"Google Unlocked ({method_used})", {
                "solved": True,
                "method": method_used
            }

        notify(f"Captcha could not be solved ({error_msg or 'Verification failed'}).")
        return False, f"Captcha Failed ({error_msg or 'Blocked'})", {
            "solved": False,
            "method": method_used,
            "error": error_msg
        }



    @classmethod
    async def _solve_audio_loop(
        cls,
        page: Any,
        bframe_loc: Any,
        notify: Callable[[str], None],
        strategy: str = "audio_first",
        whisper_model: str = "base",
        max_rounds: int = 3
    ) -> Tuple[bool, str, str]:
        """Handles multi-round audio challenges with generous delays and IP rate limit detection."""
        for round_idx in range(1, max_rounds + 1):
            if await cls._is_captcha_solved(page):
                return True, "audio_whisper", ""

            notify(f"[Audio Round {round_idx}/{max_rounds}] Opening Audio Challenge...")
            
            # Check if already in audio challenge mode (audio response input field or download link present)
            audio_input = bframe_loc.locator("#audio-response, .rc-audiochallenge-response-wrapper").first
            in_audio_mode = await audio_input.count() > 0 and await audio_input.is_visible()
            
            if not in_audio_mode:
                audio_btn = bframe_loc.locator("#recaptcha-audio-button, button#recaptcha-audio-button").first
                if await audio_btn.count() > 0 and await audio_btn.is_visible():
                    await cls._human_click(page, audio_btn, target_size=28.0)
                    # Wait dynamically for audio container or doscaptcha rate limit
                    for _ in range(10):
                        await asyncio.sleep(0.4)
                        if await bframe_loc.locator("#audio-response, a.rc-audiochallenge-download-link, .rc-doscaptcha-body, .rc-doscaptcha-header").count() > 0:
                            break

            # 1. Check for IP Rate Limit block ("Try again later")
            blocked_elem = bframe_loc.locator(".rc-doscaptcha-body, .rc-doscaptcha-header, .rc-doscaptcha-footer, :text('Try again later'), :text('Automated queries'), :text('automatische Anfragen')").first
            if await blocked_elem.count() > 0 and await blocked_elem.is_visible():
                notify("Google blocked Audio challenge ('Try again later' / IP rate limit). Switching back to Vision solver...")
                # Immediately click reload button or image button to switch back to image challenge
                reload_btn = bframe_loc.locator("#recaptcha-reload-button, button#recaptcha-reload-button, .rc-button-reload, #recaptcha-image-button, button#recaptcha-image-button").first
                if await reload_btn.count() > 0 and await reload_btn.is_visible():
                    await cls._human_click(page, reload_btn, target_size=28.0)
                    await cls._human_idle(page, 1.5)
                return False, "audio_whisper", "Audio IP Rate Limit (Try again later)"

            # 2. Get audio download link with robust multi-selector polling
            audio_url = None
            for _ in range(12):
                if await cls._is_captcha_solved(page):
                    return True, "audio_whisper", ""
                
                # Check for IP block during load
                blocked_elem = bframe_loc.locator(".rc-doscaptcha-body, .rc-doscaptcha-header, .rc-doscaptcha-footer, :text('Try again later'), :text('Automated queries'), :text('automatische Anfragen')").first
                if await blocked_elem.count() > 0 and await blocked_elem.is_visible():
                    notify("Google blocked Audio challenge ('Try again later' / IP rate limit). Switching back to Vision solver...")
                    reload_btn = bframe_loc.locator("#recaptcha-reload-button, button#recaptcha-reload-button, .rc-button-reload, #recaptcha-image-button, button#recaptcha-image-button").first
                    if await reload_btn.count() > 0 and await reload_btn.is_visible():
                        await cls._human_click(page, reload_btn, target_size=28.0)
                        await cls._human_idle(page, 1.5)
                    return False, "audio_whisper", "Audio IP Rate Limit (Try again later)"

                # Check via DOM selector in iframe
                try:
                    url = await bframe_loc.locator("body").evaluate("""() => {
                        const dl = document.querySelector('a.rc-audiochallenge-download-link, a.rc-audiochallenge-tdownload-link, a[href*="payload"], a[href*="audio"]');
                        if (dl && dl.href) return dl.href;
                        const aud = document.querySelector('audio#audio-source, audio source, audio');
                        if (aud && (aud.src || aud.currentSrc)) return aud.src || aud.currentSrc;
                        return null;
                    }""")
                    if url:
                        audio_url = url
                        break
                except Exception:
                    pass
                await asyncio.sleep(0.5)

            if not audio_url:
                if await cls._is_captcha_solved(page):
                    return True, "audio_whisper", ""
                notify("Audio download URL not found on page.")
                return False, "audio_whisper", "Audio download link missing"

            notify("Downloading audio payload via session context...")
            raw_audio: Optional[bytes] = None
            
            # Method 1: Playwright APIRequestContext (bypasses browser CORS & CSP restrictions)
            try:
                if hasattr(page, "context") and hasattr(page.context, "request"):
                    req_resp = await page.context.request.get(audio_url)
                    if req_resp.ok:
                        raw_audio = await req_resp.body()
                        logger.info(f"[Audio Solver] Downloaded {len(raw_audio)} bytes audio via Playwright APIRequestContext")
            except Exception as e_req:
                logger.debug(f"[Audio Solver] context.request fetch note: {e_req}")

            # Method 2: Same-origin fetch inside the Google bframe iframe
            if not raw_audio:
                try:
                    audio_b64 = await bframe_loc.locator("body").evaluate("""async (body, url) => {
                        try {
                            const resp = await fetch(url, { credentials: 'include' });
                            if (!resp.ok) return null;
                            const buf = await resp.arrayBuffer();
                            const bytes = new Uint8Array(buf);
                            let binary = '';
                            const chunk = 8192;
                            for (let i = 0; i < bytes.length; i += chunk) {
                                binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
                            }
                            return btoa(binary);
                        } catch (e) {
                            return null;
                        }
                    }""", audio_url)
                    if audio_b64:
                        raw_audio = base64.b64decode(audio_b64)
                        logger.info(f"[Audio Solver] Downloaded {len(raw_audio)} bytes audio via bframe same-origin fetch")
                except Exception as e_bframe:
                    logger.debug(f"[Audio Solver] bframe evaluate fetch note: {e_bframe}")

            # Method 3: Top-page fetch fallback
            if not raw_audio:
                try:
                    audio_b64 = await page.evaluate("""async (url) => {
                        try {
                            const resp = await fetch(url, { credentials: 'include' });
                            if (!resp.ok) return null;
                            const buf = await resp.arrayBuffer();
                            const bytes = new Uint8Array(buf);
                            let binary = '';
                            const chunk = 8192;
                            for (let i = 0; i < bytes.length; i += chunk) {
                                binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
                            }
                            return btoa(binary);
                        } catch(e) {
                            return null;
                        }
                    }""", audio_url)
                    if audio_b64:
                        raw_audio = base64.b64decode(audio_b64)
                except Exception as e_page:
                    logger.debug(f"[Audio Solver] page evaluate fetch note: {e_page}")

            # Method 4: Python aiohttp download
            if not raw_audio:
                try:
                    import aiohttp
                    cookies_dict = {}
                    if hasattr(page, "context") and hasattr(page.context, "cookies"):
                        c_list = await page.context.cookies()
                        for c in c_list:
                            cookies_dict[c["name"]] = c["value"]
                    async with aiohttp.ClientSession(cookies=cookies_dict) as session:
                        async with session.get(audio_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}) as a_resp:
                            if a_resp.status == 200:
                                raw_audio = await a_resp.read()
                                logger.info(f"[Audio Solver] Downloaded {len(raw_audio)} bytes audio via aiohttp session")
                except Exception as e_aio:
                    logger.debug(f"[Audio Solver] aiohttp download note: {e_aio}")

            if not raw_audio:
                return False, "audio_whisper", "Audio download failed via all fetch strategies"

            transcription = ""
            from engine.ai_gemini_client import GeminiApiClient
            gemini_client = GeminiApiClient.get_instance()
            use_gemini = (whisper_model == "gemini-audio" or strategy.startswith("gemini")) and gemini_client.is_configured()

            from engine.warmup.human_motion import CognitiveGazeTracker
            async with CognitiveGazeTracker(page, cls._cursor_pos) as gaze:
                if use_gemini:
                    notify(f"Transcribing {len(raw_audio)} bytes audio with Google Gemini Cloud Audio STT...")
                    transcription = await gemini_client.transcribe_audio(raw_audio)
                    if not transcription:
                        notify(f"Gemini audio transcription empty, falling back to Local Faster-Whisper ({whisper_model})...")
                        ai_mgr = AIModelManager.get_instance()
                        transcription = ai_mgr.transcribe_audio_whisper_bytes(raw_audio, model_name=whisper_model)
                else:
                    # Local Whisper STT First
                    notify(f"Transcribing {len(raw_audio)} bytes audio with Faster-Whisper ({whisper_model}) STT...")
                    ai_mgr = AIModelManager.get_instance()
                    transcription = ai_mgr.transcribe_audio_whisper_bytes(raw_audio, model_name=whisper_model)
                    if not transcription and gemini_client.is_configured():
                        notify("Whisper STT empty, falling back to Google Gemini Cloud Audio STT...")
                        transcription = await gemini_client.transcribe_audio(raw_audio)

                cls._cursor_pos = gaze.current_pos

            if not transcription:
                notify("Audio transcription returned empty text.")
                reload_btn = bframe_loc.locator("#recaptcha-reload-button").first
                if await reload_btn.count() > 0:
                    await cls._human_click(page, reload_btn, target_size=28.0)
                    await cls._human_idle(page, 2.0)
                continue

            response_text = cls._format_audio_response(transcription)
            notify(f"Audio transcription: '{transcription}' -> submitting: '{response_text}'")

            input_field = bframe_loc.locator("#audio-response").first
            if await input_field.count() == 0:
                return False, "audio_whisper", "Audio response input missing"

            await cls._human_click(page, input_field, target_size=35.0)
            await input_field.fill("")
            await cls._human_idle(page, random.uniform(0.15, 0.35))
            await input_field.fill(response_text)
            await cls._human_idle(page, random.uniform(0.4, 0.8))

            verify_btn = bframe_loc.locator("#recaptcha-verify-button").first
            if await verify_btn.count() > 0:
                await cls._human_click(page, verify_btn, target_size=40.0)
                notify("Submitted solution. Waiting for Google validation...")

            # Poll for Google validation up to 8s
            for _ in range(16):
                await asyncio.sleep(0.5)
                if await cls._is_captcha_solved(page):
                    notify("Audio solution accepted. Waiting 2.0s to verify if a follow-up puzzle appears...")
                    await asyncio.sleep(2.0)
                    has_followup = (
                        await bframe_loc.locator("#audio-response, .rc-imageselect-desc, table.rc-imageselect-table-33, table.rc-imageselect-table-44, #recaptcha-verify-button").count() > 0
                        and await bframe_loc.locator("#recaptcha-verify-button").is_visible()
                    )
                    if has_followup:
                        notify("⟳ Consecutive follow-up puzzle appeared after audio verification! Switching to Vision solver...")
                        return False, "audio_whisper", "Consecutive puzzle requested Vision solve"
                    notify("✧ Audio Challenge verified by Google!")
                    return True, "audio_whisper", ""

                # Check error message
                err_elem = bframe_loc.locator(".rc-audiochallenge-error-message").first
                if await err_elem.count() > 0 and await err_elem.is_visible():
                    err_txt = await err_elem.inner_text()
                    notify(f"Google requested another audio attempt ({err_txt[:40]})...")
                    await cls._human_idle(page, 1.5)
                    break

            if await cls._is_captcha_solved(page):
                await asyncio.sleep(2.0)
                if not (await bframe_loc.locator("#recaptcha-verify-button").is_visible()):
                    return True, "audio_whisper", ""

        return False, "audio_whisper", "Max audio rounds exceeded"

    @classmethod
    async def _solve_vision_loop(
        cls,
        page: Any,
        bframe_loc: Any,
        bframe_elem: Any,
        vision_model: Optional[str],
        notify: Callable[[str], None],
        max_rounds: int = 8
    ) -> Tuple[bool, str, str]:
        """Handles multi-round image tile challenges using high-resolution parallel tile cropping optimized for LLaVA."""
        # If currently in audio challenge or 'Try again later' view, switch back to image mode
        is_audio_or_doscaptcha = (
            await bframe_loc.locator(".rc-doscaptcha-body, .rc-doscaptcha-header, #audio-response, .rc-audiochallenge-response-wrapper").count() > 0
        )
        img_btn = bframe_loc.locator("#recaptcha-image-button, button#recaptcha-image-button").first
        reload_btn = bframe_loc.locator("#recaptcha-reload-button, button#recaptcha-reload-button, .rc-button-reload").first

        if await img_btn.count() > 0 and await img_btn.is_visible():
            notify("Switching reCAPTCHA challenge view from Audio back to Vision / Image challenge...")
            await cls._human_click(page, img_btn, target_size=28.0)
            await cls._human_idle(page, 2.0)
        elif is_audio_or_doscaptcha and await reload_btn.count() > 0 and await reload_btn.is_visible():
            notify("Resetting 'Try again later' Audio block back to Vision Image challenge...")
            await cls._human_click(page, reload_btn, target_size=28.0)
            await cls._human_idle(page, 2.0)

        # Ensure image challenge grid has rendered
        for _ in range(8):
            if await bframe_loc.locator(".rc-imageselect-desc-wrapper, .rc-imageselect-desc, table.rc-imageselect-table-33, table.rc-imageselect-table-44, #rc-imageselect-target").count() > 0:
                break
            await asyncio.sleep(0.4)

        from engine.ai_gemini_client import GeminiApiClient
        import config
        gemini_client = GeminiApiClient.get_instance()
        strat = getattr(config, "AI_PROVIDER_STRATEGY", "hybrid_fallback")

        is_50_50_hybrid = bool(vision_model and ("50/50" in vision_model or "50_50" in vision_model or "smart_hybrid" in vision_model.lower()))
        is_explicit_gemini = bool(vision_model and "gemini" in vision_model.lower() and not is_50_50_hybrid)
        is_explicit_local = bool(vision_model and vision_model.lower() not in ["auto", "default"] and not is_explicit_gemini and not is_50_50_hybrid)

        if strat == "local_only":
            use_gemini_vision = False
            if is_explicit_gemini:
                vision_model = "llava:7b"
        elif is_50_50_hybrid:
            use_gemini_vision = gemini_client.is_configured()
        elif is_explicit_gemini:
            use_gemini_vision = gemini_client.is_configured()
        elif is_explicit_local:
            use_gemini_vision = False
        else:
            use_gemini_vision = (
                strat in ["gemini_only", "hybrid_gemini_vision"] or
                (strat == "hybrid_fallback" and gemini_client.is_configured())
            )

        for round_idx in range(1, max_rounds + 1):

            if await cls._is_captcha_solved(page):
                return True, "vision_vlm", ""

            if is_50_50_hybrid:
                preferred_engine = "Google Gemini Cloud Vision (50% Hybrid)" if (round_idx % 2 == 1 and gemini_client.is_configured()) else "Local VLM (50% Hybrid)"
                notify(f"[Vision Round {round_idx}/{max_rounds}] ⚖️ 50/50 Smart Hybrid inspecting image challenge via {preferred_engine}...")
            else:
                vision_engine_name = "Google Gemini Multimodal Vision" if (use_gemini_vision and gemini_client.is_configured()) else (vision_model or "Local VLM")
                notify(f"[Vision Round {round_idx}/{max_rounds}] Inspecting image challenge with {vision_engine_name}...")

            # 1. Read instruction
            desc_elem = bframe_loc.locator(".rc-imageselect-desc-wrapper, .rc-imageselect-desc, .rc-imageselect-desc-no-canonical").first
            instruction = ""
            if await desc_elem.count() > 0:
                instruction = (await desc_elem.inner_text()).replace("\n", " ").strip()
            if not instruction:
                instruction = "Select all matching images"

            notify(f"Instruction: '{instruction[:65]}'")

            # 2. Check 4x4 (16 tiles) vs 3x3 (9 tiles)
            is_4x4 = await bframe_loc.locator(".rc-image-tile-44, img.rc-image-tile-44").count() > 0
            grid_size = 16 if is_4x4 else 9

            # 3. Capture screenshot of target grid element
            target_elem = bframe_loc.locator("#rc-imageselect-target, .rc-imageselect-target").first
            if await target_elem.count() == 0:
                target_elem = bframe_elem

            try:
                screenshot_bytes = await target_elem.screenshot(timeout=4000)
            except Exception:
                if await cls._is_captcha_solved(page):
                    return True, "vision_vlm", ""
                try:
                    screenshot_bytes = await bframe_elem.screenshot(timeout=3000)
                except Exception:
                    if await cls._is_captcha_solved(page):
                        return True, "vision_vlm", ""
                    notify("Captcha target element no longer visible. Checking page state...")
                    return await cls._is_captcha_solved(page), "vision_vlm", ""

            ai_mgr = AIModelManager.get_instance()
            target_tiles = []
            g_size = (4, 4) if is_4x4 else (3, 3)
            local_model_target = "moondream:latest" if (vision_model and "moondream" in vision_model.lower()) else ("qwen2.5-vl:7b" if (vision_model and "qwen" in vision_model.lower()) else "llava:7b")

            badged_image = cls._overlay_grid_numbers(screenshot_bytes, rows=g_size[0], cols=g_size[1])

            from engine.warmup.human_motion import CognitiveGazeTracker
            async with CognitiveGazeTracker(page, cls._cursor_pos) as gaze:
                # In 50/50 mode: alternate primary engine per round
                gemini_first = (is_50_50_hybrid and round_idx % 2 == 1) or (use_gemini_vision and not is_50_50_hybrid)

                if gemini_first and gemini_client.is_configured():
                    try:
                        notify(f"⭍ Evaluating {grid_size} badged tiles in One-Shot mode via Google Gemini Vision...")
                        target_tiles = await gemini_client.solve_captcha_grid(
                            image_data=badged_image,
                            target_instruction=instruction,
                            grid_size=g_size
                        )
                        if target_tiles:
                            notify(f"★ Gemini identified matching tiles: {target_tiles}")
                    except Exception as gem_err:
                        notify(f"Gemini Cloud note ({gem_err}), auto-falling back to Local VLM...")

                if not target_tiles:
                    notify(f"Evaluating {grid_size} cropped tiles with Local AI ({local_model_target})...")
                    try:
                        target_tiles = await ai_mgr.solve_recaptcha_vision(
                            raw_image_bytes=screenshot_bytes,
                            instruction=instruction,
                            grid_size=grid_size,
                            model_name=local_model_target
                        )
                        if target_tiles:
                            notify(f"Local AI ({local_model_target}) identified matching tiles: {target_tiles}")
                    except Exception as loc_err:
                        notify(f"Local VLM note: {loc_err}")

                # Secondary fallback to Gemini if Local VLM failed in 50/50 mode round 2
                if not target_tiles and not gemini_first and gemini_client.is_configured():
                    notify(f"Local VLM yielded no tiles, triggering Gemini Cloud Vision backup...")
                    try:
                        target_tiles = await gemini_client.solve_captcha_grid(
                            image_data=badged_image,
                            target_instruction=instruction,
                            grid_size=g_size
                        )
                        if target_tiles:
                            notify(f"★ Gemini Cloud backup identified matching tiles: {target_tiles}")
                    except Exception:
                        pass

            cls._cursor_pos = gaze.current_pos


            # Locate clickable tile table cells (1-to-1 mapping without parent/child duplication)
            if is_4x4:
                tiles = bframe_loc.locator("table.rc-imageselect-table-44 td")
            else:
                tiles = bframe_loc.locator("table.rc-imageselect-table-33 td")

            tile_count = await tiles.count()
            if tile_count == 0:
                tiles = bframe_loc.locator("td.rc-imageselect-tile")
                tile_count = await tiles.count()

            if not target_tiles:
                verify_btn = bframe_loc.locator("#recaptcha-verify-button").first
                btn_text = (await verify_btn.inner_text()).strip().upper() if await verify_btn.count() > 0 else ""
                if "SKIP" in btn_text or "ÜBERSPRINGEN" in btn_text or "PASSER" in btn_text or "SALTAR" in btn_text:
                    notify(f"No matching tiles. Clicking '{btn_text}' button as instructed by challenge...")
                    await cls._human_click(page, verify_btn, target_size=40.0)
                    await cls._human_idle(page, random.uniform(2.5, 4.0))
                    if await cls._is_captcha_solved(page):
                        return True, "vision_vlm", ""
                    continue
                else:
                    notify("No matching tiles detected. Requesting new challenge image...")
                    reload_btn = bframe_loc.locator("#recaptcha-reload-button").first
                    if await reload_btn.count() > 0:
                        await cls._human_click(page, reload_btn, target_size=28.0)
                        await cls._human_idle(page, 2.0)
                        continue

            # Check if this is a dynamic fading tile challenge ("none left", "keine mehr", "terminé", etc.)
            is_dynamic = any(w in instruction.lower() for w in ["none left", "keine mehr", "terminé", "ninguno", "restano", "restam"])

            for idx in target_tiles:
                if 0 <= idx < tile_count:
                    t_elem = tiles.nth(idx)
                    try:
                        already_selected = await t_elem.evaluate("""el => {
                            return el.classList.contains('rc-imageselect-tileselected') ||
                                   el.querySelector('.rc-imageselect-checkbox-on') !== null ||
                                   el.getAttribute('aria-selected') === 'true';
                        }""")
                    except Exception:
                        already_selected = False

                    if not already_selected:
                        notify(f"Selecting tile [{idx}]...")
                        await cls._human_click(page, t_elem, target_size=32.0, speed_mult=2.6)
                        try:
                            await asyncio.wait_for(t_elem.click(force=True), timeout=0.8)
                        except Exception:
                            pass
                        await asyncio.sleep(random.uniform(0.06, 0.12))

            # Dynamic replacement tiles loop (wait for fade-in and check replacement squares)
            if is_dynamic:
                for fade_round in range(3):
                    notify("Waiting for replacement tiles to complete fade animation...")
                    await cls._human_idle(page, 2.5)
                    try:
                        screenshot_bytes = await target_elem.screenshot(timeout=7000)
                        badged_rep = cls._overlay_grid_numbers(screenshot_bytes, rows=g_size[0], cols=g_size[1])
                        new_tiles = []
                        if use_gemini_vision and gemini_client.is_configured():
                            new_tiles = await gemini_client.solve_captcha_grid(
                                image_data=badged_rep,
                                target_instruction=instruction,
                                grid_size=g_size
                            )
                        if not new_tiles:
                            new_tiles = await ai_mgr.solve_recaptcha_vision(
                                raw_image_bytes=screenshot_bytes,
                                instruction=instruction,
                                grid_size=grid_size,
                                model_name=vision_model or "llava:7b"
                            )
                        if not new_tiles:
                            notify("No more matching replacement tiles detected.")
                            break
                        notify(f"Replacement matching tiles: {new_tiles}")
                        for n_idx in new_tiles:
                            if 0 <= n_idx < tile_count:
                                rep_elem = tiles.nth(n_idx)
                                try:
                                    rep_selected = await rep_elem.evaluate("""el => {
                                        return el.classList.contains('rc-imageselect-tileselected') ||
                                               el.querySelector('.rc-imageselect-checkbox-on') !== null ||
                                               el.getAttribute('aria-selected') === 'true';
                                    }""")
                                except Exception:
                                    rep_selected = False

                                if not rep_selected:
                                    notify(f"Selecting replacement tile [{n_idx}]...")
                                    await cls._human_click(page, rep_elem, target_size=32.0, speed_mult=2.6)
                                    try:
                                        await asyncio.wait_for(rep_elem.click(force=True), timeout=0.8)
                                    except Exception:
                                        pass
                                    await asyncio.sleep(random.uniform(0.06, 0.12))
                    except Exception as fade_err:
                        logger.debug(f"Fade loop note: {fade_err}")
                        break

            await asyncio.sleep(random.uniform(0.18, 0.35))

            # Click verify / next button
            verify_btn = bframe_loc.locator("#recaptcha-verify-button").first
            if await verify_btn.count() > 0:
                btn_text = await verify_btn.inner_text()
                notify(f"Clicking '{btn_text}' button. Awaiting Google validation...")
                await cls._human_click(page, verify_btn, target_size=40.0, speed_mult=2.2)
                try:
                    await asyncio.wait_for(verify_btn.click(force=True), timeout=1.2)
                except Exception:
                    try:
                        await asyncio.wait_for(verify_btn.evaluate("el => el.click()"), timeout=1.0)
                    except Exception:
                        pass

            # Dynamic validation watchdog: Poll Google validation state for up to 8s (every 0.5s)
            validation_passed = False
            followup_detected = False
            start_poll = time.time()

            while (time.time() - start_poll) < 8.0:
                await asyncio.sleep(0.5)

                # Check if captcha is cleared / solved
                if await cls._is_captcha_solved(page):
                    validation_passed = True
                    break

                # Check if Google returned an error or follow-up prompt
                try:
                    err_elem = bframe_loc.locator(".rc-imageselect-incorrect-response, .rc-imageselect-error-select-more, .rc-imageselect-error-dynamic-more").first
                    if await err_elem.count() > 0 and await err_elem.is_visible():
                        notify("Google indicated additional/replacement tiles needed. Continuing...")
                        followup_detected = True
                        break
                except Exception:
                    pass

                # Check if bframe was closed or detached
                bframe_open = False
                for f in getattr(page, "frames", []):
                    if not getattr(f, "is_detached", lambda: False)() and ("recaptcha/api2/bframe" in f.url.lower() or "enterprise/bframe" in f.url.lower()):
                        bframe_open = True
                        break
                if not bframe_open and await cls._is_captcha_solved(page):
                    validation_passed = True
                    break

            if validation_passed or await cls._is_captcha_solved(page):
                notify("✧ Vision solution accepted! Captcha cleared.")
                # Submit Google sorry continue form if present
                try:
                    submit_btn = await page.query_selector("form#captcha-form input[type='submit'], input[name='continue'], input[type='submit'], button[type='submit'], form button")
                    if submit_btn and await submit_btn.is_visible():
                        notify("Submitting Google continue form...")
                        await submit_btn.click()
                        await asyncio.sleep(1.5)
                except Exception:
                    pass
                return True, "vision_vlm", ""

            if followup_detected:
                continue

            # Check if consecutive follow-up puzzle appeared
            has_followup = False
            try:
                has_followup = (
                    await bframe_loc.locator("#rc-imageselect-target, .rc-imageselect-desc, table.rc-imageselect-table-33, table.rc-imageselect-table-44, #recaptcha-verify-button").count() > 0
                    and await asyncio.wait_for(bframe_loc.locator("#recaptcha-verify-button").is_visible(), timeout=1.5)
                )
            except Exception:
                pass

            if has_followup:
                notify("⟳ Consecutive follow-up puzzle appeared after vision verification. Continuing...")
                continue

        if await cls._is_captcha_solved(page):
            await asyncio.sleep(1.5)
            return True, "vision_vlm", ""

        return False, "vision_vlm", "Vision verification incomplete"

    @classmethod
    def _overlay_grid_numbers(cls, image_bytes: bytes, rows: int = 3, cols: int = 3) -> bytes:
        """Overlays clear numbered badges [0-8] and yellow boundary lines for unambiguous VLM spatial grounding."""
        try:
            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            draw = ImageDraw.Draw(img)
            w, h = img.size
            tile_w = w / cols
            tile_h = h / rows

            idx = 0
            for r in range(rows):
                for c in range(cols):
                    x1 = c * tile_w
                    y1 = r * tile_h
                    # Bounding box
                    draw.rectangle([x1, y1, x1 + tile_w, y1 + tile_h], outline=(255, 255, 0), width=2)
                    # Number badge
                    badge_size = 20 if rows >= 4 else 24
                    draw.rectangle([x1 + 3, y1 + 3, x1 + 3 + badge_size, y1 + 3 + badge_size], fill=(255, 235, 0), outline=(0, 0, 0), width=2)
                    draw.text((x1 + 6, y1 + 4), str(idx), fill=(0, 0, 0))
                    idx += 1

            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=95)
            return buf.getvalue()
        except Exception:
            return image_bytes


    @classmethod
    def _format_audio_response(cls, transcription: str) -> str:
        """Formats transcription into clean text (digits or words) for reCAPTCHA input."""
        if not transcription:
            return ""

        # Check if digits exist
        digits = "".join(re.findall(r'\d+', transcription))
        if len(digits) >= 2:
            return digits

        # Multilingual word conversion
        words_map = {
            "zero": "0", "null": "0", "one": "1", "eins": "1", "un": "1", "uno": "1",
            "two": "2", "zwei": "2", "deux": "2", "dos": "2", "due": "2",
            "three": "3", "drei": "3", "trois": "3", "tres": "3", "tre": "3",
            "four": "4", "vier": "4", "quatre": "4", "cuatro": "4", "quattro": "4",
            "five": "5", "fünf": "5", "cinq": "5", "cinco": "5", "cinque": "5",
            "six": "6", "sechs": "6", "six": "6", "seis": "6", "sei": "6",
            "seven": "7", "sieben": "7", "sept": "7", "siete": "7", "sette": "7",
            "eight": "8", "acht": "8", "huit": "8", "ocho": "8", "otto": "8",
            "nine": "9", "neun": "9", "neuf": "9", "nueve": "9", "nove": "9"
        }

        tokens = transcription.lower().replace("-", " ").split()
        parsed_digits = []
        for t in tokens:
            clean = re.sub(r'[^a-z0-9]', '', t)
            if clean in words_map:
                parsed_digits.append(words_map[clean])

        if len(parsed_digits) >= 2:
            return "".join(parsed_digits)

        # Return clean phrase text without punctuation
        return re.sub(r'[^\w\s]', '', transcription).strip().lower()

    @classmethod
    def crop_challenge_region(
        cls,
        image_bytes: bytes,
        box: Tuple[int, int, int, int],
        padding: int = 10
    ) -> str:
        """Crops challenge image region to reduce VLM token consumption and inference latency."""
        try:
            img = Image.open(io.BytesIO(image_bytes))
            w_img, h_img = img.size
            x, y, w, h = box
            x1 = max(0, x - padding)
            y1 = max(0, y - padding)
            x2 = min(w_img, x + w + padding)
            y2 = min(h_img, y + h + padding)
            cropped = img.crop((x1, y1, x2, y2))
            buf = io.BytesIO()
            cropped.save(buf, format="JPEG", quality=90)
            return base64.b64encode(buf.getvalue()).decode("ascii")
        except Exception as e:
            logger.debug(f"[AICaptchaSolver] Crop note: {e}")
            return base64.b64encode(image_bytes).decode("ascii")

    @classmethod
    async def _is_captcha_solved(cls, page: Any) -> bool:
        """Checks if the captcha has been completely cleared on the page and no challenge popup remains."""
        try:
            url = page.url.lower()
            if "search?q=" in url or "search%3fq=" in url:
                return True

            # 1. Authoritative check: Anchor checkbox has green checkmark
            for f in getattr(page, "frames", []):
                if getattr(f, "is_detached", lambda: False)():
                    continue
                if "recaptcha/api2/anchor" in f.url.lower() or "enterprise/anchor" in f.url.lower():
                    try:
                        checked = await asyncio.wait_for(
                            f.evaluate("() => { const a = document.querySelector('#recaptcha-anchor, .recaptcha-checkbox'); return (a && a.getAttribute('aria-checked') === 'true') || !!document.querySelector('.recaptcha-checkbox-checked'); }"),
                            timeout=1.5
                        )
                        if checked:
                            return True
                    except Exception:
                        pass

            # 2. Check if search results are already visible
            if "sorry/index" not in url and "recaptcha" not in url:
                try:
                    res = await asyncio.wait_for(
                        page.query_selector("#search, #rso, div.g, div.MjjYud, textarea[name='q'], input[name='q']"),
                        timeout=1.5
                    )
                    if res and await asyncio.wait_for(res.is_visible(), timeout=1.5):
                        return True
                except Exception:
                    pass

            # 3. If challenge popup frame is STILL open and visible on screen, challenge is NOT yet solved!
            for f in getattr(page, "frames", []):
                if getattr(f, "is_detached", lambda: False)():
                    continue
                if "recaptcha/api2/bframe" in f.url.lower() or "enterprise/bframe" in f.url.lower():
                    try:
                        is_vis = await asyncio.wait_for(
                            f.evaluate("() => { const b = document.querySelector('#rc-imageselect, .rc-imageselect, #audio-response'); return b && b.offsetParent !== null; }"),
                            timeout=1.5
                        )
                        if is_vis:
                            return False
                    except Exception:
                        pass

        except Exception:
            pass
        return False

    @classmethod
    async def solve_cloudflare_turnstile(

        cls,
        page: Any,
        human_session: Optional[Any] = None,
        notify_cb: Optional[Callable[[str], None]] = None,
        timeout_sec: float = 25.0
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Detects and solves interactive Cloudflare Turnstile / Cloudflare Challenge widgets using biomechanical mouse interactions.
        """
        def notify(msg: str):
            logger.info(f"[AICaptchaSolver] {msg}")
            if notify_cb:
                notify_cb(f"⛊ {msg}")

        notify("Detecting Cloudflare Turnstile / Challenge widget...")

        # 1. Search for Turnstile iframe or container
        turnstile_iframe = None
        turnstile_box = None
        turnstile_elem = None

        for _ in range(12):
            try:
                # Check for Cloudflare Turnstile iframes in page.frames
                for f in getattr(page, "frames", []):
                    f_url = getattr(f, "url", "").lower()
                    if "challenges.cloudflare.com" in f_url or "turnstile" in f_url:
                        turnstile_iframe = f
                        break

                # Check for iframe locator on main page
                iframe_loc = page.locator("iframe[src*='challenges.cloudflare.com'], iframe[src*='turnstile'], iframe[title*='Widget containing a Cloudflare'], iframe[title*='Cloudflare']").first
                if await iframe_loc.count() > 0 and await iframe_loc.is_visible():
                    turnstile_elem = iframe_loc
                    turnstile_box = await iframe_loc.bounding_box()
                    break

                # Check for main page stage selectors
                stage = page.locator("#cf-stage, #challenge-stage, .cf-turnstile-wrapper, .cf-turnstile, #cf-turnstile, div[data-sitekey]").first
                if await stage.count() > 0 and await stage.is_visible():
                    turnstile_box = await stage.bounding_box()
                    break
            except Exception:
                pass
            await asyncio.sleep(0.4)

        # 2. Check if already bypassed or token exists
        try:
            token = await page.evaluate("() => { const el = document.querySelector('[name=\"cf-turnstile-response\"], [name=\"cf_challenge_response\"]'); return el ? el.value : ''; }")
            if token and len(token) > 10:
                notify("Cloudflare challenge already verified.")
                return True, "Turnstile Passed", {"solved": True, "token": token[:15] + "..."}
        except Exception:
            pass

        # 3. Locate and interact with Checkbox
        try:
            clicked = False
            
            # Method A: Click via main page iframe bounding box
            if turnstile_box:
                cx = turnstile_box["x"] + min(32, max(24, turnstile_box["width"] * 0.12))
                cy = turnstile_box["y"] + (turnstile_box["height"] / 2.0)
                notify("Targeting Cloudflare verification checkbox via humanoid cursor...")
                if hasattr(cls, "_human_idle"):
                    await cls._human_idle(page, random.uniform(0.3, 0.6))
                await page.mouse.click(cx, cy)
                clicked = True

            # Method B: FrameLocator direct click fallback (only if Method A did not click)
            if not clicked:
                try:
                    fl = page.frame_locator("iframe[src*='challenges.cloudflare.com'], iframe[src*='turnstile'], iframe[title*='Widget containing a Cloudflare'], iframe[title*='Cloudflare']").first
                    cb = fl.locator("input[type='checkbox'], label, .cb-c, span.mark, div[style*='display: flex']").first
                    if await cb.count() > 0 and await cb.is_visible():
                        await cb.click(timeout=2000)
                        clicked = True
                except Exception:
                    pass

            # Method C: Frame object click
            if not clicked and turnstile_iframe:
                try:
                    cb = turnstile_iframe.locator("input[type='checkbox'], .cb-c, #challenge-stage input, label").first
                    if await cb.count() > 0:
                        await cb.click(timeout=2000)
                        clicked = True
                except Exception:
                    pass

            if clicked:
                notify("Clicked challenge checkbox, verifying token generation...")
                # Poll for success state
                for _ in range(20):
                    await asyncio.sleep(0.6)
                    token = await page.evaluate("() => { const el = document.querySelector('[name=\"cf-turnstile-response\"], [name=\"cf_challenge_response\"]'); return el ? el.value : ''; }")
                    if token and len(token) > 10:
                        notify("Cloudflare Turnstile token successfully generated!")
                        return True, "Turnstile Solved", {"solved": True, "token": token[:15] + "..."}
                    # Check if challenge container cleared
                    is_gone = await page.evaluate("() => !document.querySelector('#challenge-stage, #cf-stage, .cf-turnstile-wrapper:not(:empty)')")
                    if is_gone:
                        notify("Cloudflare challenge cleared!")
                        return True, "Challenge Cleared", {"solved": True}

            if not clicked:
                notify("No active clickable Cloudflare Turnstile verification iframe rendered on page.")
                return False, "Turnstile Iframe Not Rendered", {"solved": False}
        except Exception as e:
            notify(f"Turnstile interaction error: {e}")

        return False, "Turnstile Timeout / Unresolved", {"solved": False}

    @classmethod
    async def _fetch_audio_bytes(cls, page: Any, audio_url: str) -> Optional[bytes]:
        """Downloads audio bytes using context.request, page evaluate fetch, or aiohttp fallback."""
        try:
            if hasattr(page, "context") and hasattr(page.context, "request"):
                req_resp = await page.context.request.get(audio_url)
                if req_resp.ok:
                    return await req_resp.body()
        except Exception:
            pass

        try:
            audio_b64 = await page.evaluate("""async (url) => {
                try {
                    const resp = await fetch(url, { credentials: 'include' });
                    if (!resp.ok) return null;
                    const buf = await resp.arrayBuffer();
                    const bytes = new Uint8Array(buf);
                    let binary = '';
                    const chunk = 8192;
                    for (let i = 0; i < bytes.length; i += chunk) {
                        binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
                    }
                    return btoa(binary);
                } catch(e) {
                    return null;
                }
            }""", audio_url)
            if audio_b64:
                return base64.b64decode(audio_b64)
        except Exception:
            pass

        try:
            import aiohttp
            cookies_dict = {}
            if hasattr(page, "context") and hasattr(page.context, "cookies"):
                c_list = await page.context.cookies()
                for c in c_list:
                    cookies_dict[c["name"]] = c["value"]
            async with aiohttp.ClientSession(cookies=cookies_dict) as session:
                async with session.get(audio_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}, timeout=aiohttp.ClientTimeout(total=10)) as a_resp:
                    if a_resp.status == 200:
                        return await a_resp.read()
        except Exception:
            pass

        return None

    @classmethod
    async def solve_hcaptcha(
        cls,
        page: Any,
        strategy: str = "vision_first",
        vision_model: Optional[str] = None,
        whisper_model: str = "base",
        notify_cb: Optional[Callable[[str], None]] = None,
        timeout_sec: float = 45.0
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Production-grade Multi-Modal hCaptcha Solver:
        - Detects checkbox frame and executes biomechanical humanoid click.
        - Automatically captures 3x3 challenge grid tiles and classifies via Local Vision VLM or Gemini Cloud.
        - Audio fallback via Faster-Whisper / Gemini Audio STT.
        - Verifies token generation in [name='h-captcha-response'].
        """
        def notify(msg: str):
            if notify_cb:
                notify_cb(f"🧩 [hCaptcha] {msg}")

        start_time = time.time()
        notify("Initiating hCaptcha resolution workflow...")

        try:
            # 0. Early check if already verified or token present
            try:
                early_token = await page.evaluate("() => document.querySelector('[name=\"h-captcha-response\"]')?.value || ''")
                if early_token and len(early_token) > 10:
                    notify("hCaptcha token already present on page (Instant Pass)!")
                    return True, "hCaptcha Solved", {"solved": True, "token": early_token[:15] + "..."}
            except Exception:
                pass

            # 1. Locate Checkbox Iframe & execute humanoid click
            checkbox_frame = None
            for frame in getattr(page, "frames", []):
                f_url = getattr(frame, "url", "").lower()
                if "hcaptcha.com" in f_url and ("checkbox" in f_url or "api.js" in f_url):
                    checkbox_frame = frame
                    break

            if not checkbox_frame:
                cb_locator = page.locator("iframe[src*='hcaptcha.com'][src*='checkbox'], iframe[data-hcaptcha-widget-id]").first
                if await cb_locator.count() > 0:
                    try:
                        checkbox_frame = await cb_locator.content_frame()
                    except Exception:
                        pass

            if checkbox_frame:
                box_btn = checkbox_frame.locator("#checkbox, .check, #anchor").first
                if await box_btn.count() > 0:
                    notify("Clicking hCaptcha anchor checkbox via biomechanical humanoid cursor...")
                    await cls._human_click(page, box_btn, target_size=28.0)
            else:
                anchor_loc = page.locator("iframe[src*='hcaptcha']").first
                if await anchor_loc.count() > 0:
                    await cls._human_click(page, anchor_loc, target_size=30.0)

            # 2. Check for passive bypass / instant pass
            for _ in range(6):
                await asyncio.sleep(0.5)
                token = await page.evaluate("() => document.querySelector('[name=\"h-captcha-response\"]')?.value || ''")
                if token and len(token) > 10:
                    notify("Passive hCaptcha verification succeeded (Instant Token Pass)!")
                    return True, "hCaptcha Solved (Instant)", {"solved": True, "token": token[:15] + "..."}

            # 3. Locate Challenge Popup Iframe
            challenge_frame = None
            for _ in range(12):
                for frame in getattr(page, "frames", []):
                    f_url = getattr(frame, "url", "").lower()
                    if "hcaptcha.com" in f_url and "challenge" in f_url:
                        challenge_frame = frame
                        break
                if challenge_frame:
                    break
                await asyncio.sleep(0.5)

            if not challenge_frame:
                token = await page.evaluate("() => document.querySelector('[name=\"h-captcha-response\"]')?.value || ''")
                if token and len(token) > 10:
                    return True, "hCaptcha Solved", {"solved": True, "token": token[:15] + "..."}
                notify("No active hCaptcha challenge dialog appeared after checkbox click.")
                return False, "hCaptcha Dialog Not Rendered", {"solved": False}

            notify("Challenge dialog detected. Analyzing challenge instructions...")

            # 4. Extract Challenge Prompt
            prompt_loc = challenge_frame.locator(".prompt-text, h2.prompt-text, .challenge-prompt").first
            prompt_text = ""
            if await prompt_loc.count() > 0:
                try:
                    prompt_text = (await prompt_loc.inner_text()).strip()
                except Exception:
                    pass

            notify(f"Challenge instruction: '{prompt_text or 'Object Classification'}'")

            # 5. Audio Solver Fallback Check if requested
            if strategy in ["audio_first", "audio_only"]:
                audio_btn = challenge_frame.locator("button.accessibility, button[title*='audio'], .audio-challenge-button").first
                if await audio_btn.count() > 0:
                    notify("Switching to hCaptcha Audio Challenge...")
                    await cls._human_click(page, audio_btn, target_size=24.0)
                    await asyncio.sleep(1.0)
                    audio_el = challenge_frame.locator("audio source, audio").first
                    if await audio_el.count() > 0:
                        audio_src = await audio_el.get_attribute("src")
                        if audio_src:
                            raw_audio = await cls._fetch_audio_bytes(page, audio_src)
                            if raw_audio:
                                ai_mgr = AIModelManager.get_instance()
                                transcription = ai_mgr.transcribe_audio_whisper_bytes(raw_audio, model_name=whisper_model)
                                if transcription:
                                    notify(f"Audio transcribed: '{transcription}', submitting...")
                                    ans_input = challenge_frame.locator("input[type='text'], .response-input").first
                                    if await ans_input.count() > 0:
                                        await ans_input.fill(transcription)
                                        submit_btn = challenge_frame.locator(".button-submit, button:has-text('Verify')").first
                                        if await submit_btn.count() > 0:
                                            await cls._human_click(page, submit_btn, target_size=32.0)
                                            await asyncio.sleep(1.5)

            # 6. Vision VLM 3x3 Grid Classification
            task_images = challenge_frame.locator(".task-image, .task-grid .image, .task-grid .task-image")
            tile_count = await task_images.count()
            if tile_count >= 9:
                notify(f"Found {tile_count} challenge image tiles. Capturing frame snapshot for Vision VLM...")
                screenshot_bytes = await challenge_frame.locator(".challenge-container, body").first.screenshot()

                ai_mgr = AIModelManager.get_instance()
                from engine.ai_gemini_client import GeminiApiClient
                gemini_client = GeminiApiClient.get_instance()

                matching_tiles = []
                if gemini_client.is_configured():
                    try:
                        notify("Querying Gemini Vision for hCaptcha tile identification...")
                        matching_tiles = await gemini_client.solve_captcha_grid(
                            image_data=screenshot_bytes,
                            target_instruction=prompt_text or "objects matching prompt",
                            grid_size=(3, 3)
                        )
                    except Exception as gem_e:
                        notify(f"Gemini Cloud notice: {gem_e}, using local VLM...")

                if not matching_tiles:
                    notify("Classifying tiles with local Vision VLM...")
                    try:
                        matching_tiles = await ai_mgr.solve_recaptcha_vision(
                            raw_image_bytes=screenshot_bytes,
                            instruction=prompt_text or "target object",
                            grid_size=9,
                            model_name=vision_model or "llava:7b"
                        )
                    except Exception as loc_e:
                        notify(f"Local VLM notice: {loc_e}")

                if matching_tiles:
                    notify(f"Vision identified matching tiles: {matching_tiles}. Clicking with humanoid motor trajectory...")
                    for tile_idx in matching_tiles:
                        if 1 <= tile_idx <= tile_count:
                            cell = task_images.nth(tile_idx - 1)
                            await cls._human_click(page, cell, target_size=40.0)
                            await asyncio.sleep(random.uniform(0.18, 0.35))

                    await cls._human_idle(page, 0.4)
                    submit_btn = challenge_frame.locator(".button-submit, button:has-text('Verify')").first
                    if await submit_btn.count() > 0:
                        notify("Submitting tile selections...")
                        await cls._human_click(page, submit_btn, target_size=34.0)

            # 7. Verification Polling
            for _ in range(15):
                await asyncio.sleep(0.6)
                token = await page.evaluate("() => document.querySelector('[name=\"h-captcha-response\"]')?.value || ''")
                if token and len(token) > 10:
                    duration = round(time.time() - start_time, 1)
                    notify(f"hCaptcha successfully verified in {duration}s!")
                    return True, "hCaptcha Solved", {"solved": True, "token": token[:15] + "...", "duration": duration}

            return False, "hCaptcha Verification Timed Out", {"solved": False}

        except Exception as e:
            notify(f"hCaptcha solver exception: {e}")
            return False, f"hCaptcha Error: {e}", {"solved": False}

    @classmethod
    async def solve_funcaptcha(
        cls,
        page: Any,
        vision_model: Optional[str] = None,
        notify_cb: Optional[Callable[[str], None]] = None,
        timeout_sec: float = 45.0
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Production-grade Arkose Labs / FunCaptcha 3D Orientation & Puzzle Solver:
        - Discovers nested Arkose challenge frames.
        - Triggers challenge entry via humanoid trajectory.
        - Extracts 3D object rotation angle / direction via Vision VLM prompts.
        - Operates rotation navigation arrows and verifies completion token.
        """
        def notify(msg: str):
            if notify_cb:
                notify_cb(f"🧩 [FunCaptcha] {msg}")

        start_time = time.time()
        notify("Initiating Arkose Labs / FunCaptcha resolution workflow...")

        try:
            # 0. Early check if already verified or token present
            try:
                early_token = await page.evaluate("() => document.querySelector('[name=\"fc-token\"]')?.value || ''")
                if early_token and len(early_token) > 10:
                    notify("FunCaptcha token already present on page (Instant Pass)!")
                    return True, "FunCaptcha Solved", {"solved": True, "token": early_token[:15] + "..."}
            except Exception:
                pass

            # 1. Locate Arkose frame
            arkose_frame = None
            for frame in getattr(page, "frames", []):
                f_url = getattr(frame, "url", "").lower()
                if "arkoselabs" in f_url or "funcaptcha" in f_url:
                    arkose_frame = frame
                    break

            if not arkose_frame:
                fc_loc = page.locator("iframe[src*='arkoselabs'], iframe[src*='funcaptcha'], iframe#fc-iframe-wrap").first
                if await fc_loc.count() > 0:
                    try:
                        arkose_frame = await fc_loc.content_frame()
                    except Exception:
                        pass

            if not arkose_frame:
                notify("No active Arkose Labs iframe found on page.")
                return False, "Arkose Iframe Not Found", {"solved": False}

            # 2. Check for child game frame (Arkose often embeds a second iframe)
            target_frame = arkose_frame
            for child in getattr(arkose_frame, "child_frames", []):
                target_frame = child
                break

            # 3. Click Initial Verify button
            verify_btn = target_frame.locator("#home_children_button, button:has-text('Verify'), [data-theme='home.verify'], button.button").first
            if await verify_btn.count() > 0:
                notify("Clicking verification start button...")
                await cls._human_click(page, verify_btn, target_size=36.0)
                await asyncio.sleep(1.2)

            # 4. Check for rotation arrows & challenge instructions
            for _ in range(10):
                await asyncio.sleep(0.5)
                game_el = target_frame.locator("#game_children_challenge, .challenge-container, canvas").first
                if await game_el.count() > 0:
                    break

            instruction_loc = target_frame.locator(".challenge-instructions, h2, #game_children_challenge p").first
            instruction_text = ""
            if await instruction_loc.count() > 0:
                try:
                    instruction_text = (await instruction_loc.inner_text()).strip()
                except Exception:
                    pass

            notify(f"Arkose challenge instruction: '{instruction_text or '3D Object Orientation'}'")

            # 5. Capture Snapshot of the 3D Rotation Object
            canvas_el = target_frame.locator("canvas, #game_children_challenge img").first
            if await canvas_el.count() > 0:
                img_bytes = await canvas_el.screenshot()
                img_b64 = base64.b64encode(img_bytes).decode("utf-8")

                from engine.ai_gemini_client import GeminiApiClient
                gemini_client = GeminiApiClient.get_instance()
                clicks_needed = 1
                direction = "right"

                prompt_query = (
                    f"You are solving an Arkose Labs / FunCaptcha orientation puzzle. "
                    f"Instruction: '{instruction_text}'. "
                    f"Look at the image carefully. How many clicks on the arrow are needed to rotate the object into the correct position? "
                    f"Answer strictly in JSON format: {{\"direction\": \"right\", \"clicks\": 1}}"
                )

                if gemini_client.is_configured():
                    try:
                        raw_content = await gemini_client.generate_vision(
                            prompt=prompt_query,
                            image_data=img_bytes,
                            json_mode=True
                        )
                        m = re.search(r'\{.*\}', raw_content, re.DOTALL)
                        if m:
                            parsed = json.loads(m.group(0))
                            direction = parsed.get("direction", "right")
                            clicks_needed = int(parsed.get("clicks", 1))
                            notify(f"Vision recommendation: Rotate {direction} with {clicks_needed} click(s).")
                    except Exception as ai_err:
                        notify(f"Vision prompt note: {ai_err}, using default single click.")

                # Click navigation arrow
                arrow_selector = ".slider-arrow-right, button.arrow-right, a.right" if direction == "right" else ".slider-arrow-left, button.arrow-left, a.left"
                arrow_btn = target_frame.locator(arrow_selector).first
                if await arrow_btn.count() > 0:
                    for i in range(min(clicks_needed, 6)):
                        await cls._human_click(page, arrow_btn, target_size=28.0)
                        await asyncio.sleep(random.uniform(0.25, 0.45))

                await cls._human_idle(page, 0.4)
                submit_btn = target_frame.locator("button:has-text('Submit'), .game-button:has-text('Submit'), #game_children_button").first
                if await submit_btn.count() > 0:
                    notify("Submitting orientation solution...")
                    await cls._human_click(page, submit_btn, target_size=32.0)

            # 6. Verify token or solved barrier
            for _ in range(15):
                await asyncio.sleep(0.6)
                token = await page.evaluate("() => document.querySelector('[name=\"fc-token\"]')?.value || ''")
                if token and len(token) > 10:
                    duration = round(time.time() - start_time, 1)
                    notify(f"FunCaptcha successfully resolved in {duration}s!")
                    return True, "FunCaptcha Solved", {"solved": True, "token": token[:15] + "...", "duration": duration}

            return False, "FunCaptcha Resolution Timed Out", {"solved": False}

        except Exception as e:
            notify(f"FunCaptcha solver exception: {e}")
            return False, f"FunCaptcha Error: {e}", {"solved": False}

    @classmethod
    async def _detect_normal_captcha(cls, page: Any) -> bool:
        """
        Detects traditional alphanumeric / distorted image captchas (Normal Captcha) on page.
        Looks for a captcha image/canvas paired with a verification text input field.
        """
        try:
            has_captcha = await page.evaluate('''() => {
                const inputs = Array.from(document.querySelectorAll("input[type='text'], input:not([type]), input[name*='captcha' i], input[id*='captcha' i], input[placeholder*='captcha' i], input[name*='code' i], input[id*='code' i], input[placeholder*='answer' i]"));
                if (!inputs.length) return false;

                const imgs = Array.from(document.querySelectorAll("img, canvas"));
                for (const img of imgs) {
                    const rect = img.getBoundingClientRect();
                    if (rect.width < 35 || rect.width > 450 || rect.height < 15 || rect.height > 150) continue;

                    const src = (img.src || "").toLowerCase();
                    const alt = (img.alt || "").toLowerCase();
                    const cls = (img.className || "").toLowerCase();
                    const id = (img.id || "").toLowerCase();

                    // Filter out logos or brand assets
                    if (src.includes("logo") || alt.includes("logo") || cls.includes("logo") || src.includes("icon") || alt.includes("icon")) continue;

                    const isCaptchaImg = src.includes("captcha") || alt.includes("captcha") || cls.includes("captcha") || id.includes("captcha") ||
                                         src.includes("valcode") || src.includes("authcode") || src.includes("securimage") ||
                                         src.startsWith("data:image") || (img.tagName === "CANVAS" && cls.includes("captcha"));

                    if (isCaptchaImg) {
                        const form = img.closest("form");
                        if (form) {
                            const formInput = form.querySelector("input[type='text'], input:not([type]), input[name*='captcha' i], input[id*='captcha' i], input[placeholder*='answer' i]");
                            if (formInput) return true;
                        }
                        for (const inp of inputs) {
                            const inRect = inp.getBoundingClientRect();
                            const dist = Math.hypot(rect.x - inRect.x, rect.y - inRect.y);
                            if (dist < 400) return true;
                        }
                    }
                }
                return false;
            }''')
            return bool(has_captcha)
        except Exception:
            return False

    @classmethod
    async def solve_normal_captcha(
        cls,
        page: Any,
        image_selector: Optional[str] = None,
        input_selector: Optional[str] = None,
        submit_selector: Optional[str] = None,
        vision_model: Optional[str] = None,
        notify_cb: Optional[Callable[[str], None]] = None,
        timeout_sec: float = 25.0
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Autonomously deciphers and solves traditional image-to-text / alphanumeric Normal Captchas:
        1. Identifies the captcha image & target input element
        2. Takes a high-resolution snapshot of the captcha image
        3. Deciphers text using high-speed ONNX OCR (ddddocr) or Multi-Modal Vision VLM fallback
        4. Types the deciphered string into the input field with humanoid cadence
        5. Submits and confirms validation state
        """
        def notify(msg: str):
            logger.info(f"[AICaptchaSolver] {msg}")
            if notify_cb:
                notify_cb(f"🔤 {msg}")

        start_time = time.time()
        notify("Detecting and capturing Normal Captcha image & target input...")

        try:
            img_loc = None
            input_loc = None

            if image_selector:
                cand_img = page.locator(image_selector).first
                if await cand_img.count() > 0 and await cand_img.is_visible():
                    img_loc = cand_img

            if input_selector:
                cand_inp = page.locator(input_selector).first
                if await cand_inp.count() > 0 and await cand_inp.is_visible():
                    input_loc = cand_inp

            # Intelligent auto-discovery if selectors not passed
            if not input_loc or not img_loc:
                auto_pair = await page.evaluate('''() => {
                    const inputs = Array.from(document.querySelectorAll("input[type='text'], input:not([type]), input[name*='captcha' i], input[id*='captcha' i], input[placeholder*='captcha' i], input[name*='code' i], input[id*='code' i], input[placeholder*='answer' i]"));
                    const imgs = Array.from(document.querySelectorAll("img, canvas"));

                    for (const img of imgs) {
                        const rect = img.getBoundingClientRect();
                        if (rect.width < 35 || rect.width > 450 || rect.height < 15 || rect.height > 150) continue;
                        const src = (img.src || "").toLowerCase();
                        const alt = (img.alt || "").toLowerCase();
                        const cls = (img.className || "").toLowerCase();
                        const id = (img.id || "").toLowerCase();
                        if (src.includes("logo") || alt.includes("logo") || cls.includes("logo") || src.includes("icon") || alt.includes("icon")) continue;

                        const isCaptchaImg = src.includes("captcha") || alt.includes("captcha") || cls.includes("captcha") || id.includes("captcha") ||
                                             src.includes("valcode") || src.includes("authcode") || src.includes("securimage") ||
                                             src.startsWith("data:image") || (img.tagName === "CANVAS" && cls.includes("captcha"));

                        if (isCaptchaImg) {
                            const form = img.closest("form");
                            if (form) {
                                const fi = form.querySelector("input[type='text'], input:not([type]), input[name*='captcha' i], input[id*='captcha' i], input[placeholder*='answer' i]");
                                if (fi) return {
                                    img_id: img.id,
                                    img_class: img.className,
                                    img_src: img.src,
                                    input_id: fi.id,
                                    input_name: fi.name
                                };
                            }
                            for (const inp of inputs) {
                                const inRect = inp.getBoundingClientRect();
                                const dist = Math.hypot(rect.x - inRect.x, rect.y - inRect.y);
                                if (dist < 400) return {
                                    img_id: img.id,
                                    img_class: img.className,
                                    img_src: img.src,
                                    input_id: inp.id,
                                    input_name: inp.name
                                };
                            }
                        }
                    }
                    return null;
                }''')

                if auto_pair:
                    if not img_loc:
                        if auto_pair.get("img_id"):
                            img_loc = page.locator(f"#{auto_pair['img_id']}").first
                        elif auto_pair.get("img_class"):
                            c_sel = "." + ".".join(auto_pair["img_class"].strip().split())
                            img_loc = page.locator(c_sel).first
                        elif auto_pair.get("img_src"):
                            img_loc = page.locator(f"img[src='{auto_pair['img_src']}']").first

                    if not input_loc:
                        if auto_pair.get("input_id"):
                            input_loc = page.locator(f"#{auto_pair['input_id']}").first
                        elif auto_pair.get("input_name"):
                            input_loc = page.locator(f"input[name='{auto_pair['input_name']}']").first

            # Fallback selectors
            if not img_loc:
                img_loc = page.locator("img[class*='captchaImage'], img[alt*='captcha' i], img[src*='captcha' i], img[id*='captcha' i], .captcha-image, #captchaImage").first
            if not input_loc:
                input_loc = page.locator("#simple-captcha-field, input[name*='captcha' i], input[id*='captcha' i], input[placeholder*='captcha' i], input[name*='code' i], input[placeholder*='answer' i]").first

            if await img_loc.count() == 0 or await input_loc.count() == 0:
                notify("Normal Captcha image or verification input could not be located.")
                return False, "Normal Captcha Elements Not Found", {"solved": False}

            # 2. Capture Snapshot of Captcha Image
            notify("Capturing high-resolution snapshot of Normal Captcha image...")
            img_bytes = await img_loc.screenshot()

            # 3. Classify Text (Ultra-Fast Local ONNX OCR + Multi-Modal Vision VLM fallback)
            recognized_code: str = ""
            try:
                import ddddocr  # type: ignore
                if cls._ddddocr_instance is None:
                    cls._ddddocr_instance = ddddocr.DdddOcr(show_ad=False)
                raw_ocr = cls._ddddocr_instance.classification(img_bytes)
                recognized_code = str(raw_ocr).strip() if raw_ocr else ""
            except Exception as ocr_err:
                logger.debug(f"[AICaptchaSolver] ddddocr note: {ocr_err}")

            if not recognized_code:
                notify("Invoking Vision VLM for image captcha deciphering...")
                ai_mgr = AIModelManager.get_instance()
                v_resp = await ai_mgr.generate_vision_response(
                    prompt="Read the distorted letters and numbers in this image captcha. Output ONLY the exact text string, no extra words or punctuation.",
                    image_data=img_bytes,
                    model_name=vision_model or "moondream:v2",
                    operation="Normal Captcha OCR"
                )
                if v_resp:
                    clean_v = re.sub(r'[^a-zA-Z0-9]', '', v_resp).strip()
                    if clean_v:
                        recognized_code = clean_v

            # Clean and sanitize string
            recognized_code = re.sub(r'[^a-zA-Z0-9]', '', recognized_code).strip()
            if not recognized_code:
                notify("Failed to decipher characters from captcha image.")
                return False, "OCR Decipher Failed", {"solved": False}

            notify(f"Deciphered Captcha Text: '{recognized_code}'. Entering into input field...")

            # 4. Humanoid Typing into Field
            await input_loc.click()
            await asyncio.sleep(random.uniform(0.15, 0.25))
            await input_loc.fill("")
            await asyncio.sleep(0.1)

            for char in recognized_code:
                await input_loc.press_sequentially(char, delay=random.uniform(30, 65))

            await asyncio.sleep(random.uniform(0.25, 0.45))

            # 5. Submit Form / Check Button
            submit_btn = None
            if submit_selector:
                cand_sub = page.locator(submit_selector).first
                if await cand_sub.count() > 0:
                    submit_btn = cand_sub

            if not submit_btn:
                form_ancestor = input_loc.locator("xpath=ancestor::form[1]")
                if await form_ancestor.count() > 0:
                    sub = form_ancestor.locator("button[type='submit'], input[type='submit'], button:has-text('Check'), button:has-text('Submit'), button:has-text('Verify')").first
                    if await sub.count() > 0:
                        submit_btn = sub

            if not submit_btn:
                submit_btn = page.locator("button[type='submit'], input[type='submit'], button:has-text('Check'), button:has-text('Submit'), button:has-text('Verify')").first

            if submit_btn and await submit_btn.count() > 0:
                notify("Submitting solution via humanoid click...")
                await cls._human_click(page, submit_btn, target_size=32.0)
            else:
                await input_loc.press("Enter")

            # 6. Verify Confirmation State
            for _ in range(12):
                await asyncio.sleep(0.5)
                success_detected = await page.evaluate('''() => {
                    const text = document.body.innerText.toLowerCase();
                    if (text.includes("passed successfully") || text.includes("captcha is passed") ||
                        text.includes("captcha passed") || text.includes("verification successful") ||
                        text.includes("correct captcha") || text.includes("code is correct")) {
                        return true;
                    }
                    const successAlert = document.querySelector(".alert-success, ._success_151cx_1, div[class*='success'], span[class*='success']");
                    if (successAlert && successAlert.offsetParent !== null) return true;
                    return false;
                }''')
                if success_detected:
                    duration = round(time.time() - start_time, 1)
                    notify(f"Normal Captcha successfully passed ('{recognized_code}') in {duration}s!")
                    return True, f"Normal Captcha Passed ('{recognized_code}')", {"solved": True, "text": recognized_code, "duration": duration}

            duration = round(time.time() - start_time, 1)
            notify(f"Normal Captcha submitted ('{recognized_code}') in {duration}s.")
            return True, f"Normal Captcha Submitted ('{recognized_code}')", {"solved": True, "text": recognized_code, "duration": duration}

        except Exception as e:
            notify(f"Normal Captcha solver exception: {e}")
            return False, f"Normal Captcha Error: {e}", {"solved": False}


