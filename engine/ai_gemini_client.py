import os
import json
import base64
import time
import socket
import logging
import asyncio
import io
from typing import Dict, Any, List, Optional, Tuple, Union
import aiohttp
from PIL import Image

import config

logger = logging.getLogger("GeminiClient")
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

class GeminiApiClient:
    """
    Direct asynchronous REST API client for Google Gemini (Gemini 2.0 Flash, 1.5 Flash, 1.5 Pro).
    Provides high-speed text generation, multimodal vision reasoning, and one-shot Captcha grid classification.
    """
    _instance: Optional['GeminiApiClient'] = None

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = (api_key or getattr(config, "GEMINI_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "")).strip()

    @classmethod
    def get_instance(cls) -> 'GeminiApiClient':
        if cls._instance is None:
            cls._instance = GeminiApiClient()
        return cls._instance

    def set_api_key(self, key: str):
        self._api_key = key.strip()
        config.GEMINI_API_KEY = self._api_key

    def get_api_key(self) -> str:
        return self._api_key

    _quota_exhausted_until: float = 0.0

    def has_valid_key(self) -> bool:
        """Returns True if a valid API key string is present, regardless of active strategy."""
        return bool(self._api_key and len(self._api_key) > 10)

    def is_configured(self) -> bool:
        """Returns True ONLY if a valid key is present AND strategy is NOT 'local_only'."""
        strat = getattr(config, "AI_PROVIDER_STRATEGY", "hybrid_fallback")
        if strat == "local_only":
            return False
        return self.has_valid_key()

    def is_rate_limited(self) -> bool:
        """Returns True if Gemini API recently responded with 429 quota exhaustion and is in cooldown."""
        return time.time() < self._quota_exhausted_until

    def trigger_quota_cooldown(self, seconds: float = 60.0):
        """Activates a circuit breaker cooldown when Google returns 429 RESOURCE_EXHAUSTED."""
        self._quota_exhausted_until = time.time() + seconds
        logger.info(f"[GeminiClient] Quota circuit breaker active for {seconds:.0f}s. Routing tasks to local models.")

    def is_available(self) -> bool:
        """Returns True if configured AND not currently rate-limited by quota exhaustion."""
        return self.is_configured() and not self.is_rate_limited()

    @classmethod
    def normalize_model_name(cls, model: Optional[str]) -> str:
        """Normalizes model names and maps legacy/deprecated version aliases to active Google endpoints."""
        if not model:
            return getattr(config, "GEMINI_DEFAULT_MODEL", "gemini-flash-lite-latest")
        m = model.strip()
        if m.startswith("models/"):
            m = m.replace("models/", "")
        # Map deprecated or quota-constrained aliases directly to active default
        if m in ["gemini-3.6-flash", "gemini-2.5-flash"]:
            return getattr(config, "GEMINI_DEFAULT_MODEL", "gemini-flash-lite-latest")
        if m in ["gemini-2.0-flash", "gemini-2.0", "gemini-flash-2.0", "gemini-1.5-flash"]:
            return "gemini-flash-lite-latest"
        if m in ["gemini-1.5-pro", "gemini-2.0-pro", "gemini-2.5-pro"]:
            return "gemini-3.1-pro-preview"
        return m

    async def test_connection(self, api_key: Optional[str] = None, model: str = "gemini-flash-lite-latest") -> Tuple[bool, str]:
        """Validates API key by executing a minimal test prompt with auto-fallback to active Google models."""
        key = (api_key or self._api_key).strip()
        if not key:
            return False, "API Key is empty. Provide a valid Google Gemini API Key."

        primary = self.normalize_model_name(model or getattr(config, "GEMINI_DEFAULT_MODEL", "gemini-flash-lite-latest"))
        candidate_models = [primary]
        for fallback in ["gemini-flash-lite-latest", "gemini-3-flash-preview", "gemini-3.8-flash", "gemini-3.7-flash"]:
            if fallback not in candidate_models:
                candidate_models.append(fallback)

        last_err = ""
        for cur_model in candidate_models:
            url = f"{GEMINI_API_BASE}/{cur_model}:generateContent"  # [F-01] Key via header, not URL
            payload = {
                "contents": [{
                    "parts": [{"text": "Reply with 'OK'."}]
                }],
                "generationConfig": {
                    "maxOutputTokens": 100,
                    "temperature": 0.0
                }
            }

            try:
                conn = aiohttp.TCPConnector(family=socket.AF_INET)
                _auth_headers = {"x-goog-api-key": key}
                async with aiohttp.ClientSession(connector=conn, headers=_auth_headers, trust_env=True) as session:
                    async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=30.0, connect=10.0, sock_read=25.0)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            candidates = data.get("candidates", [])
                            if candidates:
                                config.GEMINI_DEFAULT_MODEL = cur_model
                                return True, f"Connection successful! Model '{cur_model}' responded."
                            return False, "API responded 200 but returned no candidates."
                        else:
                            err_text = await resp.text()
                            try:
                                err_json = json.loads(err_text)
                                msg = err_json.get("error", {}).get("message", f"HTTP {resp.status}")
                            except Exception:
                                msg = f"HTTP {resp.status}: {err_text[:120]}"
                            last_err = f"Model '{cur_model}': {msg}"
                            # If model is deprecated or not found or 429/503, try next candidate
                            if "no longer available" in msg.lower() or "not found" in msg.lower() or resp.status in [404, 429, 503]:
                                continue
                            return False, f"API Error: {msg}"
            except Exception as e:
                err_str = str(e).strip()
                if not err_str:
                    if isinstance(e, (asyncio.TimeoutError, aiohttp.ServerTimeoutError)):
                        err_str = "Request timed out (>30s)"
                    else:
                        err_str = "Connection reset or socket closed"
                last_err = f"{type(e).__name__}: {err_str}"
                logger.warning(f"[GeminiClient] Test connection exception on {cur_model}: {last_err}")
                continue

        return False, f"Network Error connecting to Gemini API: {last_err}"

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str = "",
        model: Optional[str] = None,
        json_mode: bool = False,
        temperature: float = 0.1,
        max_tokens: int = 8192
    ) -> str:
        """Generates text completion using specified Gemini model with automatic 503/404/429 fallback and telemetry tracking."""
        if not self.is_configured():
            logger.warning("[GeminiClient] Cannot generate text: Gemini API Key not configured.")
            return ""

        if self.is_rate_limited():
            return ""

        from engine.ai_telemetry import AITelemetryBus
        telemetry = AITelemetryBus.get_instance()
        t0 = time.time()

        primary = self.normalize_model_name(model or getattr(config, "GEMINI_DEFAULT_MODEL", "gemini-flash-lite-latest"))
        telemetry.record_start(primary, "★ Gemini Cloud Text Reasoning", prompt[:60], "Cloud API")

        candidates = [primary]
        for fb in ["gemini-flash-lite-latest", "gemini-3-flash-preview", "gemini-3.8-flash", "gemini-3.7-flash"]:
            if fb not in candidates:
                candidates.append(fb)

        contents: List[Dict[str, Any]] = [{"role": "user", "parts": [{"text": prompt}]}]
        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens
            }
        }
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        if json_mode:
            payload["generationConfig"]["responseMimeType"] = "application/json"

        saw_429 = False
        for cur_model in candidates:
            url = f"{GEMINI_API_BASE}/{cur_model}:generateContent"  # [F-01] Key via header, not URL
            try:
                conn = aiohttp.TCPConnector(family=socket.AF_INET)
                _auth_headers = {"x-goog-api-key": self._api_key}
                async with aiohttp.ClientSession(connector=conn, headers=_auth_headers, trust_env=True) as session:
                    async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=60.0, connect=10.0, sock_read=45.0)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            res_txt = self._extract_text_from_response(data)
                            dur_ms = round((time.time() - t0) * 1000, 2)
                            telemetry.record_finish(cur_model, "★ Gemini Cloud Text Reasoning", dur_ms, "SUCCESS", res_txt[:80] if res_txt else "OK")
                            return res_txt
                        else:
                            err_text = await resp.text()
                            logger.warning(f"[GeminiClient] Text generation error on {cur_model} ({resp.status}): {err_text[:120]}")
                            if resp.status == 429:
                                saw_429 = True
                                continue
                            if resp.status in [503, 404]:
                                continue
                            dur_ms = round((time.time() - t0) * 1000, 2)
                            telemetry.record_finish(cur_model, "★ Gemini Cloud Text Reasoning", dur_ms, "ERROR", f"HTTP {resp.status}")
                            return ""
            except Exception as e:
                logger.warning(f"[GeminiClient] Text generation exception on {cur_model}: {e}")

        if saw_429:
            self.trigger_quota_cooldown(60.0)

        dur_ms = round((time.time() - t0) * 1000, 2)
        telemetry.record_finish(primary, "★ Gemini Cloud Text Reasoning", dur_ms, "ERROR", "All candidates exhausted")
        return ""

    async def generate_vision(
        self,
        prompt: str,
        image_data: Union[bytes, str, Image.Image],
        system_prompt: str = "",
        model: Optional[str] = None,
        json_mode: bool = False,
        mime_type: str = "image/jpeg",
        temperature: float = 0.1
    ) -> str:
        """Executes multimodal image reasoning on image data with automatic 503/404/429 fallback and telemetry tracking."""
        if not self.is_configured():
            logger.warning("[GeminiClient] Cannot generate vision: Gemini API Key not configured.")
            return ""

        if self.is_rate_limited():
            return ""

        from engine.ai_telemetry import AITelemetryBus
        telemetry = AITelemetryBus.get_instance()
        t0 = time.time()

        b64_data = self._encode_image_to_base64(image_data)
        if not b64_data:
            logger.warning("[GeminiClient] Invalid image data provided for vision generation.")
            dur_ms = round((time.time() - t0) * 1000, 2)
            telemetry.record_finish("gemini-flash-lite-latest", "⚆ Gemini Cloud Vision Reasoning", dur_ms, "ERROR", "Invalid Image")
            return ""

        primary = self.normalize_model_name(model or getattr(config, "GEMINI_DEFAULT_MODEL", "gemini-flash-lite-latest"))
        telemetry.record_start(primary, "⚆ Gemini Cloud Vision Reasoning", prompt[:60], "Image Analysis")

        candidates = [primary]
        for fb in ["gemini-flash-lite-latest", "gemini-3-flash-preview", "gemini-3.8-flash", "gemini-3.7-flash"]:
            if fb not in candidates:
                candidates.append(fb)

        parts: List[Dict[str, Any]] = [
            {"text": prompt},
            {
                "inline_data": {
                    "mime_type": mime_type,
                    "data": b64_data
                }
            }
        ]
        payload: Dict[str, Any] = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": 8192
            }
        }
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        if json_mode:
            payload["generationConfig"]["responseMimeType"] = "application/json"

        saw_429 = False
        for cur_model in candidates:
            url = f"{GEMINI_API_BASE}/{cur_model}:generateContent"  # [F-01] Key via header, not URL
            try:
                conn = aiohttp.TCPConnector(family=socket.AF_INET)
                _auth_headers = {"x-goog-api-key": self._api_key}
                async with aiohttp.ClientSession(connector=conn, headers=_auth_headers, trust_env=True) as session:
                    async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=60.0, connect=10.0, sock_read=45.0)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            res_txt = self._extract_text_from_response(data)
                            dur_ms = round((time.time() - t0) * 1000, 2)
                            telemetry.record_finish(cur_model, "⚆ Gemini Cloud Vision Reasoning", dur_ms, "SUCCESS", res_txt[:80] if res_txt else "OK")
                            return res_txt
                        else:
                            err_text = await resp.text()
                            if resp.status == 429:
                                saw_429 = True
                                logger.warning(f"[GeminiClient] Rate limit/quota (429) on {cur_model}: {err_text[:100]}. Trying next fallback model.")
                                continue
                            logger.warning(f"[GeminiClient] Vision error on {cur_model} ({resp.status}): {err_text[:120]}")
                            if resp.status in [503, 404]:
                                continue
                            dur_ms = round((time.time() - t0) * 1000, 2)
                            telemetry.record_finish(cur_model, "⚆ Gemini Cloud Vision Reasoning", dur_ms, "ERROR", f"HTTP {resp.status}")
                            return ""
            except Exception as e:
                logger.warning(f"[GeminiClient] Vision generation exception on {cur_model}: {e}")

        if saw_429:
            self.trigger_quota_cooldown(60.0)

        dur_ms = round((time.time() - t0) * 1000, 2)
        telemetry.record_finish(primary, "⚆ Gemini Cloud Vision Reasoning", dur_ms, "ERROR", "All candidates exhausted")
        return ""

    async def transcribe_audio(
        self,
        audio_data: Union[bytes, str],
        model: Optional[str] = None
    ) -> str:
        """Transcribes acoustic challenge audio using Gemini Multimodal Audio API with live telemetry tracking."""
        if not self.is_configured():
            return ""

        from engine.ai_telemetry import AITelemetryBus
        telemetry = AITelemetryBus.get_instance()
        t0 = time.time()
        telemetry.record_start("gemini-3.6-flash", "☊ reCAPTCHA Audio STT Challenge", "Transcribing audio payload (MP3)", "Google reCAPTCHA Audio")

        if isinstance(audio_data, str) and os.path.exists(audio_data):
            with open(audio_data, "rb") as f:
                raw_bytes = f.read()
        elif isinstance(audio_data, bytes):
            raw_bytes = audio_data
        else:
            dur_ms = round((time.time() - t0) * 1000, 2)
            telemetry.record_finish("gemini-3.6-flash", "☊ reCAPTCHA Audio STT Challenge", dur_ms, "ERROR", "Invalid Audio Data")
            return ""

        b64_audio = base64.b64encode(raw_bytes).decode("ascii")
        prompt = "Listen to this audio recording carefully. Transcribe ONLY the numbers or words spoken in order. Output plain text without any introductory words or punctuation."

        primary = self.normalize_model_name(model or "gemini-flash-lite-latest")
        candidates = [primary]
        for fb in ["gemini-flash-lite-latest", "gemini-3-flash-preview", "gemini-3.1-flash-lite"]:
            if fb not in candidates:
                candidates.append(fb)

        for cur_model in candidates:
            url = f"{GEMINI_API_BASE}/{cur_model}:generateContent"  # [F-01] Key via header, not URL
            payload = {
                "contents": [{
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "audio/mp3",
                                "data": b64_audio
                            }
                        }
                    ]
                }],
                "generationConfig": {
                    "temperature": 0.0,
                    "maxOutputTokens": 100
                }
            }

            try:
                conn = aiohttp.TCPConnector(family=socket.AF_INET)
                _auth_headers = {"x-goog-api-key": self._api_key}
                async with aiohttp.ClientSession(connector=conn, headers=_auth_headers) as session:
                    async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=30.0, connect=10.0, sock_read=25.0)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            txt = self._extract_text_from_response(data)
                            if txt:
                                dur_ms = round((time.time() - t0) * 1000, 2)
                                telemetry.record_finish("gemini-3.6-flash", "☊ reCAPTCHA Audio STT Challenge", dur_ms, "SUCCESS", f"Decoded: '{txt}'")
                                logger.info(f"[GeminiClient] Transcribed audio via Gemini '{cur_model}': '{txt}'")
                                return txt
                        else:
                            if resp.status in [503, 404, 429]:
                                continue
            except Exception as e:
                logger.debug(f"[GeminiClient] Audio transcribe exception on {cur_model}: {e}")

        dur_ms = round((time.time() - t0) * 1000, 2)
        telemetry.record_finish("gemini-3.6-flash", "☊ reCAPTCHA Audio STT Challenge", dur_ms, "ERROR", "Audio transcription failed")
        return ""

    async def solve_captcha_grid(
        self,
        image_data: Union[bytes, str, Image.Image],
        target_instruction: str,
        grid_size: Tuple[int, int] = (3, 3),
        model: Optional[str] = None
    ) -> List[int]:
        """
        One-Shot Captcha Grid Solver:
        Evaluates an entire 3x3 or 4x4 image grid in a single ~400ms request with real-time telemetry updates.
        """
        from engine.ai_telemetry import AITelemetryBus
        telemetry = AITelemetryBus.get_instance()
        rows, cols = grid_size
        total_tiles = rows * cols

        op_name = f"⭍ One-Shot {rows}x{cols} reCAPTCHA Solver"
        telemetry.record_start(
            "gemini-3.6-flash",
            op_name,
            f"Target: \"{target_instruction[:40]}\"",
            f"reCAPTCHA {rows}x{cols} Grid"
        )

        prompt = (
            f"You are a superhuman image captcha classifier specialized in Google reCAPTCHA v2 / Enterprise visual grids.\n"
            f"The image is divided into a {rows}x{cols} grid with {total_tiles} numbered tiles (from 0 to {total_tiles - 1}) labeled clearly with yellow badges in the top-left corner of each tile.\n\n"
            f"Instruction / Goal: \"{target_instruction}\"\n\n"
            f"Task Rules:\n"
            f"1. Check EVERY numbered tile from 0 to {total_tiles - 1}.\n"
            f"2. If a tile contains ANY PART of the requested object (even a corner, pole, wheel, windshield, stripe, light, or reflection), YOU MUST INCLUDE THAT TILE NUMBER.\n"
            f"3. Specific object guidelines:\n"
            f"   - 'traffic lights' / 'feux de signalisation' / 'Ampeln': Include all tiles containing the lights, the metal housing, or the pole attached to it.\n"
            f"   - 'crosswalk' / 'passages piétons' / 'Zebrastreifen': Include all tiles with white pedestrian road stripes, zebra markings, or sidewalk curb connections.\n"
            f"   - 'bus' / 'autobus' / 'Busse': Include all tiles showing any part of a bus (front, roof, wheels, windows, side panels, yellow school buses, city buses).\n"
            f"   - 'cars' / 'voitures' / 'Autos': Include all sedans, SUVs, trucks, vans, headlights, or tail sections.\n"
            f"   - 'motorcycles' / 'motos' / 'Motorräder' / 'bicycles' / 'vélos': Include all tiles with frames, handlebars, tires, or riders.\n"
            f"   - 'stairs' / 'escaliers' / 'Treppen': Include all outdoor or indoor steps and handrails.\n"
            f"   - 'bridges' / 'ponts' / 'Brücken' / 'fire hydrant' / 'bornes d'incendie' / 'chimneys': Include all tiles with any visible part of the object.\n"
            f"4. Output format: Return ONLY valid JSON: {{\"matching_tiles\": [indices]}}, e.g. {{\"matching_tiles\": [0, 3, 5]}} or {{\"matching_tiles\": []}} if none match."
        )

        system_prompt = "You are an expert AI vision classifier for Google reCAPTCHA grids. Output only valid JSON with key 'matching_tiles'."


        t0 = time.time()
        resp = await self.generate_vision(
            prompt=prompt,
            image_data=image_data,
            system_prompt=system_prompt,
            model=model or getattr(config, "GEMINI_DEFAULT_MODEL", "gemini-flash-lite-latest"),
            json_mode=True,
            temperature=0.0
        )
        duration_ms = round((time.time() - t0) * 1000, 2)

        if not resp:
            telemetry.record_finish("gemini-3.6-flash", op_name, duration_ms, "ERROR", "Vision returned empty response")
            return []

        try:
            data = json.loads(resp)
            tiles = data.get("matching_tiles", [])
            valid_tiles = [int(x) for x in tiles if isinstance(x, (int, float, str)) and str(x).isdigit() and 0 <= int(x) < total_tiles]
            telemetry.record_finish(
                "gemini-3.6-flash",
                op_name,
                duration_ms,
                "SUCCESS",
                f"Solved tiles: {valid_tiles} for '{target_instruction[:25]}'"
            )
            logger.info(f"[GeminiClient] Solved {rows}x{cols} Captcha Grid in {duration_ms}ms -> Matches: {valid_tiles} for '{target_instruction}'")
            return valid_tiles
        except Exception:
            import re
            nums = [int(n) for n in re.findall(r'\b\d\b', resp)]
            valid_tiles = [n for n in nums if 0 <= n < total_tiles]
            telemetry.record_finish(
                "gemini-3.6-flash",
                op_name,
                duration_ms,
                "SUCCESS" if valid_tiles else "STANDBY",
                f"Regex parsed tiles: {valid_tiles}"
            )
            logger.info(f"[GeminiClient] Regex parsed Captcha Grid matches in {duration_ms}ms -> {valid_tiles}")
            return valid_tiles


    @staticmethod
    def _encode_image_to_base64(image_data: Union[bytes, str, Image.Image]) -> str:
        """Converts bytes, file path, PIL Image, or data URL into clean base64 string."""
        if isinstance(image_data, str):
            if image_data.startswith("data:"):
                return image_data.split(",")[-1].strip()
            if os.path.exists(image_data):
                with open(image_data, "rb") as f:
                    return base64.b64encode(f.read()).decode("ascii")
            return image_data.strip()
        elif isinstance(image_data, bytes):
            return base64.b64encode(image_data).decode("ascii")
        elif isinstance(image_data, Image.Image):
            buf = io.BytesIO()
            image_data.save(buf, format="JPEG", quality=90)
            return base64.b64encode(buf.getvalue()).decode("ascii")
        return ""

    @staticmethod
    def _extract_text_from_response(data: Dict[str, Any]) -> str:
        """Extracts text content safely from Gemini JSON response object."""
        try:
            candidates = data.get("candidates", [])
            if candidates:
                content = candidates[0].get("content", {})
                parts = content.get("parts", [])
                text_parts = [p.get("text", "") for p in parts if "text" in p]
                return "".join(text_parts).strip()
        except Exception as e:
            logger.debug(f"[GeminiClient] Parse note: {e}")
        return ""
