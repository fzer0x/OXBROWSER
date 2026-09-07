import os
import re
import json
import base64
import random
import asyncio
import logging
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass

import config
from engine.ai_model_manager import AIModelManager
from engine.ai_inference_optimizer import JSONSchemaGrammars

logger = logging.getLogger("VLAEngine")


class VLAActionType(str, Enum):
    CLICK = "click"
    TYPE = "type"
    SCROLL = "scroll"
    HOVER = "hover"
    PRESS_KEY = "press_key"
    SOLVE_CAPTCHA = "solve_captcha"
    WAIT = "wait"
    NAVIGATE = "navigate"
    FINISHED = "finished"


@dataclass
class VLAActionResult:
    action: VLAActionType
    thought: str
    point: Optional[Tuple[int, int]] = None
    box: Optional[Tuple[int, int, int, int]] = None
    text: Optional[str] = None
    confidence: float = 0.95
    raw_response: str = ""


class VisionLanguageActionEngine:
    """
    Vision-Language-Action (VLA) End-to-End Execution Engine for SoxBot.
    Directly perceives browser viewports as visual tensors and predicts precise pixel-level
    actions (x, y) without brittle DOM CSS selector dependency.
    
    Supports:
    - UI-TARS & ShowUI coordinate syntax ([0, 1000] space)
    - Qwen2-VL & Moondream 2 Vision Action prompting
    - Google Gemini 3.6/3.7 Vision API
    - Biomechanical humanoid mouse and keyboard actuation
    """
    _instance: Optional['VisionLanguageActionEngine'] = None

    def __init__(self, ai_manager: Optional[AIModelManager] = None):
        self.ai_manager = ai_manager or AIModelManager.get_instance()

    @classmethod
    def get_instance(cls) -> 'VisionLanguageActionEngine':
        if cls._instance is None:
            cls._instance = VisionLanguageActionEngine()
        return cls._instance

    @staticmethod
    def build_vla_prompt(instruction: str, viewport_width: int, viewport_height: int) -> str:
        """Constructs a strict visual reasoning prompt for VLA vision models."""
        return (
            f"You are a browser automation agent. Look at the screenshot of size {viewport_width}x{viewport_height}.\n"
            f"User Goal: \"{instruction}\"\n\n"
            "Analyze the visual UI elements and output your next action as strict JSON adhering to this schema:\n"
            "```json\n"
            "{\n"
            '  "thought": "<concise visual reasoning on what element to interact with>",\n'
            '  "action": "click" | "type" | "scroll" | "hover" | "press_key" | "solve_captcha" | "wait" | "navigate" | "finished",\n'
            '  "point": [x, y],  // Target coordinate in 0-1000 normalized space or exact pixels\n'
            '  "box": [ymin, xmin, ymax, xmax],  // Optional bounding box\n'
            '  "text": "<content if typing or URL if navigating>",\n'
            '  "confidence": 0.95\n'
            "}\n"
            "```\n"
            "If the goal is already fulfilled, set action to 'finished'."
        )

    @classmethod
    def denormalize_coordinates(
        cls,
        raw_x: float,
        raw_y: float,
        viewport_width: int,
        viewport_height: int
    ) -> Tuple[int, int]:
        """Converts normalized (0..1 or 0..1000) model coordinates into exact pixel offsets."""
        # 1. Check if coordinates are in [0, 1] normalized float range
        if 0.0 <= raw_x <= 1.0 and 0.0 <= raw_y <= 1.0:
            pixel_x = int(raw_x * viewport_width)
            pixel_y = int(raw_y * viewport_height)
        # 2. Check if coordinates are in [0, 1000] standard UI-TARS / ShowUI space
        elif raw_x <= 1000 and raw_y <= 1000:
            pixel_x = int((raw_x / 1000.0) * viewport_width)
            pixel_y = int((raw_y / 1000.0) * viewport_height)
        # 3. Otherwise assume direct pixel coordinates
        else:
            pixel_x = int(raw_x)
            pixel_y = int(raw_y)

        # Clamp to viewport bounds
        clamped_x = max(0, min(pixel_x, viewport_width - 1))
        clamped_y = max(0, min(pixel_y, viewport_height - 1))
        return clamped_x, clamped_y

    @classmethod
    def parse_model_action_response(
        cls,
        response_text: str,
        viewport_width: int = 1280,
        viewport_height: int = 720
    ) -> VLAActionResult:
        """Parses model output into a strongly typed VLAActionResult."""
        raw = response_text.strip()

        # 1. Attempt JSON block extraction
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        candidate_json = json_match.group(1) if json_match else None

        if not candidate_json:
            json_brace = re.search(r"(\{.*\})", raw, re.DOTALL)
            if json_brace:
                candidate_json = json_brace.group(1)

        if candidate_json:
            try:
                data = json.loads(candidate_json)
                action_str = str(data.get("action", "click")).lower().strip()
                thought = str(data.get("thought", "Executing visual action"))
                text_val = data.get("text")
                conf = float(data.get("confidence", 0.9))

                point_coords = None
                raw_point = data.get("point")
                if isinstance(raw_point, (list, tuple)) and len(raw_point) >= 2:
                    rx, ry = float(raw_point[0]), float(raw_point[1])
                    point_coords = cls.denormalize_coordinates(rx, ry, viewport_width, viewport_height)

                raw_box = data.get("box")
                box_coords = None
                if isinstance(raw_box, (list, tuple)) and len(raw_box) == 4:
                    ymin, xmin, ymax, xmax = [float(v) for v in raw_box]
                    px_min, py_min = cls.denormalize_coordinates(xmin, ymin, viewport_width, viewport_height)
                    px_max, py_max = cls.denormalize_coordinates(xmax, ymax, viewport_width, viewport_height)
                    box_coords = (py_min, px_min, py_max, px_max)
                    if not point_coords:
                        point_coords = ((px_min + px_max) // 2, (py_min + py_max) // 2)

                try:
                    act_type = VLAActionType(action_str)
                except ValueError:
                    act_type = VLAActionType.CLICK

                return VLAActionResult(
                    action=act_type,
                    thought=thought,
                    point=point_coords,
                    box=box_coords,
                    text=text_val,
                    confidence=conf,
                    raw_response=raw
                )
            except Exception as ex:
                logger.debug(f"[VLAEngine] JSON parse fallback: {ex}")

        # 2. UI-TARS regex syntax fallback: click(point=[x,y])
        tars_click = re.search(r"click\s*\(\s*point\s*=\s*\[\s*(\d+)\s*,\s*(\d+)\s*\]\s*\)", raw)
        if tars_click:
            rx, ry = float(tars_click.group(1)), float(tars_click.group(2))
            pt = cls.denormalize_coordinates(rx, ry, viewport_width, viewport_height)
            return VLAActionResult(
                action=VLAActionType.CLICK,
                thought="UI-TARS Click syntax detected",
                point=pt,
                raw_response=raw
            )

        tars_type = re.search(r"type\s*\(\s*(?:content\s*=\s*)?[\"'](.*?)[\"']\s*\)", raw)
        if tars_type:
            return VLAActionResult(
                action=VLAActionType.TYPE,
                thought="UI-TARS Type syntax detected",
                text=tars_type.group(1),
                raw_response=raw
            )

        # Fallback default
        return VLAActionResult(
            action=VLAActionType.WAIT,
            thought=f"Could not parse action from: {raw[:120]}...",
            raw_response=raw
        )

    async def perceive_and_act(
        self,
        page: Any,
        instruction: str,
        vision_model: str = "moondream:v2",
        type_text: Optional[str] = None
    ) -> Tuple[bool, str, VLAActionResult]:
        """
        Executes an end-to-end perception and action cycle:
        1. Captures viewport screenshot.
        2. Queries vision model with VLA prompt.
        3. Actuates mouse / keyboard biomechanically.
        """
        from engine.warmup.human_motion import BiomechanicalMotor

        # 1. Get viewport size
        vp_width, vp_height = 1280, 720
        try:
            if hasattr(page, "viewport_size") and page.viewport_size:
                vp_width = page.viewport_size.get("width", 1280)
                vp_height = page.viewport_size.get("height", 720)
        except Exception:
            pass

        # 2. Capture screenshot as base64
        try:
            screenshot_bytes = await page.screenshot(type="jpeg", quality=80)
            b64_img = base64.b64encode(screenshot_bytes).decode("utf-8")
        except Exception as e:
            return False, f"Screenshot capture failed: {e}", VLAActionResult(action=VLAActionType.WAIT, thought=str(e))

        # 3. Build Prompt & Query Vision Model (Local Model -> Gemini Vision Fallback)
        prompt = self.build_vla_prompt(instruction, vp_width, vp_height)
        response_text = ""
        
        from engine.ai_gemini_client import GeminiApiClient
        gemini_client = GeminiApiClient.get_instance()

        try:
            if gemini_client.is_configured() and (vision_model.startswith("gemini") or "flash" in vision_model):
                target_g_model = gemini_client.normalize_model_name(vision_model)
                response_text = await gemini_client.generate_vision(
                    prompt=prompt,
                    image_data=b64_img,
                    model=target_g_model,
                    temperature=0.1
                )
            else:
                response_text = await self.ai_manager.generate_vision_response(
                    prompt=prompt,
                    screenshot_b64=b64_img,
                    model_name=vision_model
                )
        except Exception as query_err:
            logger.warning(f"[VLAEngine] Primary vision query failed ({query_err}), attempting Gemini Fallback...")
            if gemini_client.is_configured():
                try:
                    fallback_g_model = gemini_client.normalize_model_name(getattr(config, "GEMINI_DEFAULT_MODEL", "gemini-flash-lite-latest"))
                    response_text = await gemini_client.generate_vision(
                        prompt=prompt,
                        image_data=b64_img,
                        model=fallback_g_model,
                        temperature=0.1
                    )
                except Exception as g_err:
                    response_text = str(g_err)

        # 4. Parse ActionResult
        action_res = self.parse_model_action_response(response_text, vp_width, vp_height)
        logger.info(f"[VLAEngine] Predicted Action: {action_res.action} at point={action_res.point} | Thought: {action_res.thought}")

        # 5. Pre-Action Multi-Agent Safety Council Gatekeeper
        from engine.ai_action_council import AIActionCouncil
        council = AIActionCouncil.get_instance()
        verdict = await council.evaluate_action_safety(
            page=page,
            action_type=action_res.action.value,
            target_point=action_res.point,
            target_text=action_res.text,
            context_intent=action_res.thought
        )

        if not verdict.is_approved:
            return False, f"Action blocked by Safety Council ({verdict.reasoning})", action_res

        if verdict.adjusted_point and action_res.point:
            action_res.point = verdict.adjusted_point

        # 6. Dispatch Biomechanical Action
        success = True
        msg = f"Executed {action_res.action}"

        try:
            if action_res.action in [VLAActionType.CLICK, VLAActionType.HOVER] and action_res.point:
                target_x, target_y = action_res.point
                # Humanoid mouse move
                start_x, start_y = random.uniform(200, 600), random.uniform(200, 500)
                await BiomechanicalMotor.move_mouse_humanoid(
                    page=page,
                    start_x=start_x,
                    start_y=start_y,
                    end_x=target_x,
                    end_y=target_y,
                    target_width=40.0,
                    speed_mult=1.0
                )
                if action_res.action == VLAActionType.CLICK:
                    await asyncio.sleep(random.uniform(0.06, 0.14))
                    if hasattr(page, "mouse"):
                        await page.mouse.click(target_x, target_y)

            elif action_res.action == VLAActionType.TYPE and action_res.text:
                if hasattr(page, "keyboard"):
                    for char in action_res.text:
                        await page.keyboard.type(char)
                        await asyncio.sleep(random.uniform(0.04, 0.12))

            elif action_res.action == VLAActionType.SCROLL:
                if hasattr(page, "mouse"):
                    scroll_delta = random.choice([250, 450, 600])
                    await page.mouse.wheel(0, scroll_delta)
                    await asyncio.sleep(0.4)

            elif action_res.action == VLAActionType.FINISHED:
                msg = f"Goal reached: {action_res.thought}"

            elif action_res.action == VLAActionType.WAIT:
                await asyncio.sleep(random.uniform(0.8, 1.8))

        except Exception as act_err:
            success = False
            msg = f"Action actuation error: {act_err}"
            logger.error(f"[VLAEngine] {msg}")

        return success, msg, action_res
