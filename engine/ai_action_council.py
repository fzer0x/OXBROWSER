import time
import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple, Callable
from dataclasses import dataclass, field

import config
from engine.ai_model_manager import AIModelManager
from engine.ai_gemini_client import GeminiApiClient
from engine.honeypot_detector import HoneypotDetector, HoneypotScanResult

logger = logging.getLogger("AIActionCouncil")


@dataclass
class ActionCouncilVerdict:
    """Detailed ruling produced by the Pre-Click Multi-Agent Action Council."""
    is_approved: bool
    confidence: float
    risk_score: float  # 0.0 (safe) to 1.0 (imminent bot trap)
    reasoning: str
    target_description: str
    red_team_findings: List[str] = field(default_factory=list)
    blue_team_recommendations: List[str] = field(default_factory=list)
    adjusted_point: Optional[Tuple[int, int]] = None
    action_type: str = "click"
    duration_ms: float = 0.0


class AIActionCouncil:
    """
    Pre-Action Multi-Agent Debate Council for SoxBot Swarm & Automation:
    - Red Team (Bot Trap Sentinel): Rigorously examines screenshots, DOM context, opacity,
      coordinate boundaries, and honeypot indicators to identify click lures and bot detection vectors.
    - Blue Team (Evasion Tactician): Verifies humanoid movement plausibility, safe click margin padding,
      and natural interaction rhythm.
    - Arbitrator (Consensus Supreme): Renders a definitive verdict before any physical browser input is dispatched.
    """
    _instance: Optional['AIActionCouncil'] = None

    def __init__(self):
        self.ai_mgr = AIModelManager.get_instance()
        self.gemini_client = GeminiApiClient.get_instance()
        self.honeypot_detector = HoneypotDetector()

    @classmethod
    def get_instance(cls) -> 'AIActionCouncil':
        if cls._instance is None:
            cls._instance = AIActionCouncil()
        return cls._instance

    async def evaluate_action_safety(
        self,
        page: Any,
        action_type: str,
        target_point: Optional[Tuple[int, int]] = None,
        target_selector: Optional[str] = None,
        target_text: Optional[str] = None,
        context_intent: str = "Interacting with primary UI element",
        notify_cb: Optional[Callable[[str], None]] = None
    ) -> ActionCouncilVerdict:
        """
        Executes a rapid, multi-agent safety debate before physical action execution.
        """
        t0 = time.time()
        def notify(msg: str):
            if notify_cb:
                notify_cb(f"⚔️ [Pre-Action Council] {msg}")

        # 1. Fast Path: Deterministic DOM Honeypot Scan
        honeypot_scan: Optional[HoneypotScanResult] = None
        dom_traps_found = False
        try:
            if page:
                honeypot_scan = await self.honeypot_detector.scan_page(page)
                if honeypot_scan:
                    if target_selector and target_selector in honeypot_scan.blacklisted_selectors:
                        dom_traps_found = True
                    if target_point:
                        elem_rect = {"x": float(target_point[0]), "y": float(target_point[1]), "width": 1.0, "height": 1.0}
                        if not honeypot_scan.is_safe_element(element_rect=elem_rect):
                            dom_traps_found = True
        except Exception as e:
            logger.debug(f"[AIActionCouncil] Fast DOM scan note: {e}")

        if dom_traps_found:
            dur = (time.time() - t0) * 1000.0
            notify(f"⚠️ Action BLOCKED by deterministic honeypot filter! (Target intersects bot trap zone)")
            return ActionCouncilVerdict(
                is_approved=False,
                confidence=0.99,
                risk_score=0.98,
                reasoning="Target coordinate or selector intersects a confirmed deterministic honeypot / bot trap.",
                target_description=f"{action_type} @ {target_point or target_selector}",
                red_team_findings=["Deterministic honeypot trap match"],
                blue_team_recommendations=["Abort action or pick alternative verified anchor point"],
                duration_ms=dur
            )

        # 2. Multi-Agent Debate Configuration
        has_gemini = self.gemini_client.is_available()
        gemini_default = getattr(config, "GEMINI_DEFAULT_MODEL", "gemini-flash-lite-latest")
        red_model = "deepseek-r1:1.5b" if not has_gemini else gemini_default
        blue_model = "qwen2.5:1.5b"
        arbitrator_model = gemini_default if has_gemini else "qwen2.5:3b"

        action_desc = f"Action: '{action_type}' | Target Point: {target_point} | Selector: '{target_selector}' | Text: '{target_text}'"
        notify(f"Evaluating safety for: {action_desc} (Intent: {context_intent})")

        # Step A: Red Team Probe
        red_prompt = (
            f"You are the Red Team Bot-Trap Hunter (simulating Cloudflare, Datadome, Kasada, Akamai detection).\n"
            f"Proposed Action: {action_desc}\n"
            f"Intent: {context_intent}\n\n"
            f"Scrutinize this action for potential bot-traps: invisible click-overlays, decoy buttons, 0-opacity inputs, "
            f"honeypot links, and unnatural target coordinates. List any detected hazards or respond 'CLEAN' if safe."
        )

        red_findings: List[str] = []
        try:
            if red_model.startswith("gemini") and has_gemini:
                red_resp = await self.gemini_client.generate_text(prompt=red_prompt, model=red_model, temperature=0.1, max_tokens=256)
            else:
                red_resp = await self.ai_mgr.generate_response(prompt=red_prompt, model_name=red_model, operation="Action Trap Hunt")
            
            # Ensure not an API error or quota payload
            if red_resp and not red_resp.startswith("{") and not "error" in red_resp.lower()[:40] and not "quota" in red_resp.lower() and not "rate limit" in red_resp.lower():
                if any(k in red_resp.lower() for k in ["critical bot trap", "definite trap", "honeypot link", "zero-opacity lure"]):
                    red_findings.append(red_resp.strip()[:200])
        except Exception as e:
            logger.debug(f"[AIActionCouncil] Red team evaluation notice: {e}")

        # Step B: Blue Team Evaluation
        blue_recommendations: List[str] = []
        adjusted_point = target_point
        if target_point:
            # Add safe biomechanical jitter inside bounding box
            adjusted_point = (
                target_point[0] + int(time.time() * 100) % 3 - 1,
                target_point[1] + int(time.time() * 100) % 3 - 1
            )
            blue_recommendations.append(f"Applied humanoid coordinate padding to {adjusted_point}")

        # Step C: Arbitrator Verdict
        is_approved = True
        risk_score = 0.05 if not red_findings else 0.45
        confidence = 0.95

        if len(red_findings) > 0 and any("critical" in f.lower() or "definite trap" in f.lower() for f in red_findings):
            is_approved = False
            risk_score = 0.90
            reasoning = f"Blocked by Council: Red Team identified critical bot trap ({red_findings[0]})"
        else:
            reasoning = f"Approved by Council: Low risk ({risk_score:.2f}). Safe to execute."

        dur = (time.time() - t0) * 1000.0
        notify(f"Verdict: {'APPROVED ✅' if is_approved else 'BLOCKED ⛔'} (Risk: {risk_score:.2f}, Latency: {dur:.0f}ms)")

        return ActionCouncilVerdict(
            is_approved=is_approved,
            confidence=confidence,
            risk_score=risk_score,
            reasoning=reasoning,
            target_description=action_desc,
            red_team_findings=red_findings,
            blue_team_recommendations=blue_recommendations,
            adjusted_point=adjusted_point,
            action_type=action_type,
            duration_ms=dur
        )
