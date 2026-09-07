import time
import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple, Callable
from dataclasses import dataclass, field

import config
from engine.ai_model_manager import AIModelManager
from engine.ai_gemini_client import GeminiApiClient
from engine.ml_fingerprint_evaluator import MLFingerprintEvaluator

logger = logging.getLogger("AIAdversarialCouncil")


@dataclass
class DebateRound:
    round_index: int
    blue_proposal: str
    red_counter_critique: str
    identified_vulnerabilities: List[str]
    arbitrator_ruling: str
    score: float


class AIAdversarialCouncil:
    """
    Adversarial Multi-Agent Debate Engine (Red-Team vs Blue-Team Swarm):
    - Blue Team (Evasion Architect): Designs stealth profiles, WebGL overrides, and Playwright actions.
    - Red Team (Bot Defense Simulator): Simulates Cloudflare Turnstile, Datadome, Kasada, and Akamai heuristics.
    - Arbitrator (Consensus Supreme): Reconciles conflicting positions into a mathematically bulletproof configuration.
    """

    _instance: Optional['AIAdversarialCouncil'] = None

    def __init__(self):
        self.ai_mgr = AIModelManager.get_instance()
        self.gemini_client = GeminiApiClient.get_instance()

    @classmethod
    def get_instance(cls) -> 'AIAdversarialCouncil':
        if cls._instance is None:
            cls._instance = AIAdversarialCouncil()
        return cls._instance

    async def execute_adversarial_audit(
        self,
        target_subject: str,
        profile_context: Optional[Dict[str, Any]] = None,
        max_rounds: int = 1,
        notify_cb: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        """
        Runs an adversarial debate loop between Blue Team and Red Team.
        """
        def notify(msg: str):
            if notify_cb:
                notify_cb(f"⚔️ [Adversarial Swarm] {msg}")

        has_gemini = self.gemini_client.is_available()
        gemini_default = getattr(config, "GEMINI_DEFAULT_MODEL", "gemini-flash-lite-latest")
        blue_model = "qwen2.5:1.5b"
        red_model = "deepseek-r1:1.5b" if not has_gemini else gemini_default
        arbitrator_model = gemini_default if has_gemini else "qwen2.5:3b"

        t0 = time.time()
        notify("Initiating Red-Team vs. Blue-Team Adversarial Debate...")

        # Engine-aware context directive
        engine_type = "camoufox"
        if profile_context and isinstance(profile_context, dict):
            engine_type = str(profile_context.get("engine", "camoufox")).lower()

        engine_directive = (
            "AUDIT & ENGINE RULE: The target profile runs Camoufox (Gecko C++ native anti-detect engine). "
            "Evaluate ONLY Camoufox C++ capabilities (C++ fontconfig sandboxing, deterministic audio/canvas/spacing seeds, "
            "protocol-level ICE candidate WebRTC, and Hardened V2 disk cache/history persistence). "
            "DO NOT raise Chromium/Blink CDP detection issues (like 'chrome.runtime' or Blink navigator.webdriver leaks)."
            if engine_type == "camoufox" else
            "AUDIT & ENGINE RULE: The target profile runs Chromium. Evaluate Chromium/Blink CDP detection vectors."
        )

        # Step 1: Blue Team Proposal
        notify(f"🛡️ Blue Team ({blue_model}): Formulating stealth & evasion strategy...")
        blue_prompt = (
            f"Subject: {target_subject}\n"
            f"Context: {profile_context or {}}\n"
            f"{engine_directive}\n\n"
            f"You are the Blue Team Stealth Architect. Propose an evasion strategy and stealth configuration "
            f"focusing on Canvas/WebGL noise, WebRTC ICE spoofing, TLS JA3/JA4 harmony, and human motion."
        )
        blue_response = await self.ai_mgr.generate_response(
            prompt=blue_prompt,
            model_name=blue_model,
            operation="Blue Team Proposal"
        )

        # Step 2: Red Team Defense Analysis
        notify(f"🎯 Red Team ({red_model}): Attacking proposed strategy with Bot-Defense heuristics...")
        red_prompt = (
            f"Blue Team Proposal:\n{blue_response}\n\n"
            f"{engine_directive}\n\n"
            f"You are the Red Team Bot-Defense Sentinel (simulating Cloudflare Turnstile, Datadome, Kasada, Akamai). "
            f"Critique this proposal rigorously against genuine bot-detection vectors for {engine_type.upper()}. "
            f"Do not hallucinate cross-engine contradictions. List concrete attack vectors."
        )
        red_response = ""
        if red_model.startswith("gemini") and has_gemini:
            red_response = await self.gemini_client.generate_text(
                prompt=red_prompt,
                model=red_model,
                temperature=0.3,
                max_tokens=8192
            )
        if not red_response:
            fallback_red = "deepseek-r1:1.5b" if "deepseek" in red_model.lower() else "qwen2.5:1.5b"
            red_response = await self.ai_mgr.generate_response(
                prompt=red_prompt,
                model_name=fallback_red,
                operation="Red Team Critique"
            )

        # Step 3: Arbitrator Synthesis
        notify(f"⚖️ Arbitrator ({arbitrator_model}): Synthesizing bulletproof consensus...")
        arb_prompt = (
            f"Subject: {target_subject}\n"
            f"{engine_directive}\n\n"
            f"--- BLUE TEAM EVASION PROPOSAL ---\n{blue_response}\n\n"
            f"--- RED TEAM BOT DEFENSE CRITIQUE ---\n{red_response}\n\n"
            f"Task: As the Supreme Arbitrator, evaluate both sides according to the {engine_type.upper()} architecture. "
            f"Eliminate all flaws raised by the Red Team, adopt valid stealth countermeasures from the Blue Team, "
            f"and formulate a definitive, hardened recommendation with structured Action Blocks where appropriate."
        )

        final_synthesis = ""
        gemini_avail = self.gemini_client.is_available()
        if arbitrator_model.startswith("gemini") and gemini_avail:
            final_synthesis = await self.gemini_client.generate_text(
                prompt=arb_prompt,
                model=arbitrator_model,
                temperature=0.2,
                max_tokens=8192
            )
        if not final_synthesis:
            final_synthesis = await self.ai_mgr.generate_response(
                prompt=arb_prompt,
                model_name="qwen2.5:3b",
                operation="Arbitrator Ruling"
            )

        dur_ms = (time.time() - t0) * 1000.0
        notify(f"Adversarial Debate concluded in {dur_ms:.0f}ms.")

        return {
            "duration_ms": dur_ms,
            "blue_proposal": blue_response,
            "red_critique": red_response,
            "final_ruling": final_synthesis,
            "models_used": {
                "blue": blue_model,
                "red": red_model,
                "arbitrator": arbitrator_model
            }
        }
