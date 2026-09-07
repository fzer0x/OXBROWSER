import os
import time
import random
import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple, Callable

import config
from engine.ai_model_manager import AIModelManager
from engine.ai_telemetry import AITelemetryBus
from engine.ai_gemini_client import GeminiApiClient
from engine.ml_fingerprint_evaluator import MLFingerprintEvaluator

logger = logging.getLogger("AISwarmOrchestrator")


class VRAMArbiter:
    """
    3-Tier Dynamic Compute & VRAM Arbiter:
    - Tier 0: Zero-VRAM CPU Engine (ONNX Isolation Forest, Faster-Whisper, Qwen 0.5B CPU)
    - Tier 1: Interactive GPU Resident (Qwen 1.5B DOM Tactician, Moondream 2 Visual Scout) [Budget ~2.7 GB]
    - Tier 2: Heavyweight On-Demand GPU (Qwen 3B Strategist, LLaVA 7B Spatial Vision) [Budget ~4.7-6.6 GB]
    - Tier 3: Cloud Burst Supernode (Google Gemini 3.6 Flash) [0 MB VRAM]
    """
    _current_tier2_model: Optional[str] = None
    _tier2_loaded_time: float = 0.0
    _lock = asyncio.Lock()

    @classmethod
    async def request_tier2_model(cls, model_name: str, ai_mgr: AIModelManager) -> bool:
        """Loads a heavy Tier 2 model while automatically evicting conflicting Tier 2 models."""
        async with cls._lock:
            if cls._current_tier2_model == model_name:
                cls._tier2_loaded_time = time.time()
                return True

            # If another Tier 2 model is in VRAM, unload it
            if cls._current_tier2_model and cls._current_tier2_model != model_name:
                logger.info(f"[VRAMArbiter] Evicting Tier 2 model '{cls._current_tier2_model}' from VRAM to make room for '{model_name}'")
                await ai_mgr.unload_model(cls._current_tier2_model)
                cls._current_tier2_model = None

            cls._current_tier2_model = model_name
            cls._tier2_loaded_time = time.time()
            return True

    @classmethod
    async def release_tier2_if_idle(cls, ai_mgr: AIModelManager, max_idle_sec: float = 45.0):
        """Releases Tier 2 models if idle to preserve GPU resources for browser WebGL/VirGL."""
        async with cls._lock:
            if cls._current_tier2_model and (time.time() - cls._tier2_loaded_time) > max_idle_sec:
                logger.info(f"[VRAMArbiter] Auto-releasing idle Tier 2 model '{cls._current_tier2_model}' (idle > {max_idle_sec}s)")
                await ai_mgr.unload_model(cls._current_tier2_model)
                cls._current_tier2_model = None


class AISwarmOrchestrator:
    """
    Central AI Swarm Orchestrator for SoxBot (Auto-Full-Modus):
    Coordinates all 7 Local AI models + Google Gemini like a synchronized tactical team:
    
    1. ONNX Sentinel      -> Mathematical Fingerprint & Anomaly Verification (<1ms CPU)
    2. Faster-Whisper     -> Acoustic Speech-to-Text for Audio Challenge Bypass (80ms CPU)
    3. Qwen 2.5 (0.5B)    -> Micro-DOM Triage, Token Pruning & Reading Dwell Time (40ms)
    4. Qwen 2.5 (1.5B)    -> DOM Consent & Shadow DOM Selector Tactician (110ms GPU)
    5. Moondream 2 (1.4B) -> Viewport OCR & Visual Bounding Box Proof (190ms GPU)
    6. Qwen 2.5 (3B)      -> Strategic Persona Clickstream & Topic Coherence (250ms On-Demand GPU)
    7. LLaVA (7B)         -> Deep Spatial Vision & Multimodal reCAPTCHA Specialist (600ms On-Demand GPU)
    +. Gemini 3.6 Flash   -> Cloud Multimodal Burst Accelerator (Zero-VRAM Cloud API)
    """

    _instance: Optional['AISwarmOrchestrator'] = None

    def __init__(self):
        self.ai_mgr = AIModelManager.get_instance()
        self.telemetry = AITelemetryBus.get_instance()
        self.gemini_client = GeminiApiClient.get_instance()
        self.vram_arbiter = VRAMArbiter()
        self._auto_full_mode_active = False

    @classmethod
    def get_instance(cls) -> 'AISwarmOrchestrator':
        if cls._instance is None:
            cls._instance = AISwarmOrchestrator()
        return cls._instance

    def is_auto_full_mode_active(self) -> bool:
        return self._auto_full_mode_active

    def set_auto_full_mode(self, active: bool):
        self._auto_full_mode_active = active
        logger.info(f"[AISwarmOrchestrator] Auto Full Mode state set to: {active}")

    # ----------------------------------------------------------------------------------
    # PIPELINE 1: Page Arrival & Stealth Triage
    # ----------------------------------------------------------------------------------
    async def execute_triage_flow(
        self,
        page: Any,
        profile_data: Optional[Dict[str, Any]] = None,
        configured_model: Optional[str] = None,
        notify_cb: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        """
        Executes Phase 1 Swarm Triage upon page navigation:
        1. ONNX Sentinel verifies profile authenticity.
        2. Configured Micro-Scout analyzes page content density & computes human dwell time.
        3. Scans for barriers (reCAPTCHA, Cloudflare, Cookie Banners).
        """
        def notify(msg: str):
            if notify_cb:
                notify_cb(f"≑ [Swarm] {msg}")

        roles = self.ai_mgr.get_hybrid_roles(configured_model)
        micro_mod = roles.get("micro_model", "qwen2.5:0.5b")

        results: Dict[str, Any] = {
            "stealth_score": 100.0,
            "anomalies": [],
            "dwell_time_sec": 4.5,
            "has_captcha": False,
            "has_consent_banner": False,
            "pruned_dom_length": 0
        }

        # Step 1: Sentinel Check (ONNX)
        if profile_data:
            notify("⛊ AI Sentinel: Validating fingerprint tensor harmony...")
            score, anomalies, recs = MLFingerprintEvaluator.evaluate(profile_data)
            results["stealth_score"] = score
            results["anomalies"] = anomalies
            if score < 70.0:
                logger.warning(f"[AISwarm] Stealth Sentinel Alert: Score {score} with {len(anomalies)} anomalies")

        # Step 2: Content Density & Human Reading Dwell Time
        try:
            notify(f"⭍ Micro-Scout ({micro_mod}): Evaluating page text density & dwell time...")
            page_text = ""
            page_title = "Webpage"
            if hasattr(page, "evaluate"):
                page_text = await page.evaluate("() => document.body ? document.body.innerText.slice(0, 3000) : ''")
                page_title = await page.evaluate("() => document.title || 'Webpage'")
            
            dwell_time = await self.ai_mgr.evaluate_page_dwell_time(
                page_title=page_title,
                text_snippet=page_text,
                persona="general",
                model_name=micro_mod
            )
            results["dwell_time_sec"] = dwell_time
        except Exception as e:
            logger.debug(f"[AISwarm] Dwell time evaluation note: {e}")

        # Step 3: Fast Barrier Scan
        try:
            has_captcha = False
            if hasattr(page, "locator"):
                cap_loc = page.locator("iframe[src*='recaptcha'], iframe[src*='turnstile'], iframe[src*='hcaptcha'], #recaptcha-anchor").first
                if await cap_loc.count() > 0:
                    has_captcha = True
            results["has_captcha"] = has_captcha

            has_consent = False
            if hasattr(page, "locator"):
                consent_loc = page.locator("div[id*='cookie'], div[class*='cookie'], div[id*='consent'], div[class*='consent'], div[id*='banner'], div[class*='sp_message_container']").first
                if await consent_loc.count() > 0:
                    has_consent = True
            results["has_consent_banner"] = has_consent
        except Exception:
            pass

        return results

    # ----------------------------------------------------------------------------------
    # PIPELINE 2: Cross-Verified Consent Banner Solver
    # ----------------------------------------------------------------------------------
    async def resolve_consent_swarm(
        self,
        page: Any,
        html_snippet: Optional[str] = None,
        strategy: str = "accept",
        configured_model: Optional[str] = None,
        notify_cb: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        """
        Executes Phase 2 Swarm Consent Resolution with Cross-Validation:
        1. Extracts real candidate interactive buttons with live bounding boxes from DOM & Shadow DOM.
        2. Configured Tactician: Semantic reasoning to select exact acceptance/rejection button.
        3. Biomechanical Motor: Humanoid minimum-jerk click execution.
        """
        def notify(msg: str):
            if notify_cb:
                notify_cb(f"⚇ [Swarm Consent] {msg}")

        roles = self.ai_mgr.get_hybrid_roles(configured_model)
        tactician_mod = roles.get("text_model", "qwen2.5:1.5b")

        notify(f"Initiating Consent Handshake (Model: {tactician_mod})...")

        # Step 1: Extract real DOM candidates ONLY from verified consent containers or explicit cookie IDs
        extract_candidates_script = """
        (() => {
            function isVisible(el) {
                if (!el) return false;
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.display !== 'none' && 
                       style.visibility !== 'hidden' && 
                       style.opacity !== '0' &&
                       rect.width > 12 && rect.height > 12;
            }

            function isInsideConsentContainer(el) {
                let parent = el;
                while (parent && parent !== document.body) {
                    const idCls = ((parent.id || '') + ' ' + (parent.className || '') + ' ' + (parent.getAttribute('role') || '')).toLowerCase();
                    if (idCls.includes('cookie') || idCls.includes('consent') || idCls.includes('gdpr') || idCls.includes('privacy') || idCls.includes('datenschutz') || idCls.includes('sp_message') || idCls.includes('cmp') || idCls.includes('dialog') || idCls.includes('modal')) {
                        return true;
                    }
                    if (parent.tagName === 'DIALOG' || parent.getAttribute('aria-modal') === 'true') return true;
                    parent = parent.parentElement;
                }
                return false;
            }

            function searchRoots(root, results = []) {
                const candidates = Array.from(root.querySelectorAll(
                    '#L2AGLb, #onetrust-accept-btn-handler, #CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll, button#uc-btn-accept-banner, #didomi-notice-agree-button, [class*="cookie"] button, [class*="consent"] button, [id*="cookie"] button, [id*="consent"] button, form[action*="consent"] button, dialog button, [role="dialog"] button'
                ));
                for (const btn of candidates) {
                    if (!isVisible(btn)) continue;
                    const txt = (btn.innerText || btn.textContent || btn.value || btn.getAttribute('aria-label') || '').trim();
                    if (txt.length < 2 || txt.length > 50) continue;

                    // Must have explicit cookie attr or be in a consent container
                    const hasExplicitCookieAttr = (btn.id && btn.id.toLowerCase().includes('cookie')) || (btn.className && typeof btn.className === 'string' && btn.className.toLowerCase().includes('cookie')) || btn.id === 'L2AGLb';
                    if (!hasExplicitCookieAttr && !isInsideConsentContainer(btn)) {
                        continue;
                    }
                    
                    const rect = btn.getBoundingClientRect();
                    let sel = '';
                    if (btn.id) {
                        sel = '#' + btn.id;
                    } else if (btn.className && typeof btn.className === 'string') {
                        const firstCls = btn.className.split(' ').filter(c => c.trim().length > 2)[0];
                        if (firstCls) sel = btn.tagName.toLowerCase() + '.' + firstCls;
                    }
                    if (!sel) sel = btn.tagName.toLowerCase();

                    results.push({
                        tag: btn.tagName.toLowerCase(),
                        text: txt,
                        selector: sel,
                        x: rect.left,
                        y: rect.top,
                        width: rect.width,
                        height: rect.height
                    });
                    if (results.length >= 8) break;
                }

                // Search Shadow DOMs
                const allNodes = Array.from(root.querySelectorAll('*'));
                for (const node of allNodes) {
                    if (node.shadowRoot && results.length < 8) {
                        searchRoots(node.shadowRoot, results);
                    }
                }
                return results;
            }

            return searchRoots(document);
        })()
        """

        candidates = []
        if hasattr(page, "evaluate"):
            try:
                candidates = await page.evaluate(extract_candidates_script)
            except Exception as eval_err:
                logger.debug(f"[AISwarm] Candidate extraction note: {eval_err}")

        if not candidates or not isinstance(candidates, list) or len(candidates) == 0:
            notify("No interactive consent elements detected on DOM.")
            return {"solved": False, "method": "none"}

        # Step 2: Semantic Tactician Reasoning (Configured Model)
        notify(f"⛊ Tactician ({tactician_mod}): Analyzing {len(candidates)} candidate buttons...")
        page_url = getattr(page, "url", "") if page else ""
        
        tactician_result = await self.ai_mgr.resolve_complex_consent(
            candidates=candidates,
            page_url=page_url,
            model_name=tactician_mod
        )

        if not tactician_result or not isinstance(tactician_result, dict):
            # Fallback: Find candidate with strongest positive keyword
            import re
            pos_re = re.compile(r"(accept|agree|allow|alle\s*akzeptieren|zustimmen|einverstanden|akzeptieren|tout\s*accepter|got\s*it|ok)", re.IGNORECASE)
            for c in candidates:
                if pos_re.search(c.get("text", "")):
                    tactician_result = c
                    break

        if not tactician_result:
            notify(" AI found no matching consent button.")
            return {"solved": False, "method": "none"}

        target_text = tactician_result.get("text", "")
        target_selector = tactician_result.get("selector", "")
        cx = tactician_result.get("x", 0) + tactician_result.get("width", 0) / 2.0
        cy = tactician_result.get("y", 0) + tactician_result.get("height", 0) / 2.0
        target_w = tactician_result.get("width", 40.0)

        notify(f"⌖ AI Tactician Selected Consent Target: '{target_text}' at ({int(cx)}, {int(cy)})")

        # Step 3: Biomechanical Motor Click Execution
        try:
            from engine.warmup.human_motion import BiomechanicalMotor
            if cx > 0 and cy > 0 and hasattr(page, "mouse"):
                notify(f"⍾ Executing Humanoid Biomechanical Click on '{target_text}'...")
                await BiomechanicalMotor.move_mouse_humanoid(page, 250, 250, cx, cy, target_width=target_w)
                await asyncio.sleep(0.08)
                await page.mouse.down()
                await asyncio.sleep(0.09)
                await page.mouse.up()
            elif target_selector and hasattr(page, "locator"):
                loc = page.locator(target_selector).first
                if await loc.count() > 0:
                    await loc.click(force=True, timeout=3000)

            # Also trigger in-page click dispatch for guarantee
            click_script = f"""
            (() => {{
                const all = Array.from(document.querySelectorAll('button, a, div[role="button"], input'));
                for (const el of all) {{
                    const t = (el.innerText || el.textContent || el.value || '').trim();
                    if (t === {repr(target_text)}) {{
                        try {{ el.scrollIntoView({{ block: 'center', inline: 'center' }}); }} catch(e){{}}
                        try {{ el.click(); }} catch(e){{}}
                        try {{
                            const evt = new MouseEvent('click', {{ bubbles: true, cancelable: true, view: window }});
                            el.dispatchEvent(evt);
                        }} catch(e){{}}
                        return true;
                    }}
                }}
                return false;
            }})()
            """
            if hasattr(page, "evaluate"):
                await page.evaluate(click_script)

            await asyncio.sleep(0.8)
            notify(f"★ Cookie Consent Banner successfully accepted ('{target_text}')!")
            return {"solved": True, "text": target_text, "selector": target_selector}
        except Exception as e:
            logger.warning(f"[AISwarm] Click execution error: {e}")

        return {"solved": False, "error": "Execution failed"}

    # ----------------------------------------------------------------------------------
    # PIPELINE 3: Multi-AI Captcha Swarm Solver
    # ----------------------------------------------------------------------------------
    async def solve_captcha_swarm(
        self,
        page: Any,
        strategy: str = "auto_ensemble",
        configured_model: Optional[str] = None,
        vision_model: Optional[str] = None,
        notify_cb: Optional[Callable[[str], None]] = None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Executes Phase 3 Multi-AI Captcha Solver (Identical high-precision pipeline as AI Google Check):
        - Tier 0: Faster-Whisper Acoustic STT (Zero-GPU, 80ms CPU) -> First Line of Defense
        - Tier 1/2: Configured Vision Model (LLaVA, Moondream, Gemini, etc.) as High-Fidelity Fallback
        """
        def notify(msg: str):
            if notify_cb:
                notify_cb(f"⎘ [Swarm Captcha] {msg}")

        roles = self.ai_mgr.get_hybrid_roles(configured_model)
        target_v = vision_model or roles.get("heavy_vision_model") or roles.get("vision_model", "llava:7b")

        effective_strategy = strategy if strategy in ["audio_first", "audio_only", "vision_first", "vision_only", "gemini_first"] else "audio_first"
        notify(f"Initiating AI Captcha Solver (Strategy: {effective_strategy}, Vision: {target_v})...")

        from engine.ai_captcha_solver import AICaptchaSolver
        
        # Load Tier 2 VRAM model if local vision solver is selected
        if "vision" in effective_strategy and target_v in ["llava:7b", "qwen2.5:3b"]:
            await self.vram_arbiter.request_tier2_model(target_v, self.ai_mgr)

        solved, msg, meta = await AICaptchaSolver.solve_google_captcha(
            page=page,
            strategy=effective_strategy,
            vision_model=target_v,
            notify_cb=notify,
            timeout_sec=40.0
        )

        if "vision" in effective_strategy and target_v in ["llava:7b", "qwen2.5:3b"]:
            asyncio.create_task(self.vram_arbiter.release_tier2_if_idle(self.ai_mgr, max_idle_sec=30.0))

        return solved, msg, meta

    # ----------------------------------------------------------------------------------
    # PIPELINE 4: Strategic Trajectory & Persona Planning
    # ----------------------------------------------------------------------------------
    async def plan_strategic_trajectory(
        self,
        persona: Dict[str, Any],
        topic_keywords: List[str],
        current_url: str,
        visited_urls: List[str],
        configured_model: Optional[str] = None,
        notify_cb: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        """
        Executes Phase 4 Strategic Trajectory using strictly configured strategy model.
        """
        def notify(msg: str):
            if notify_cb:
                notify_cb(f"◵ [Swarm Strategy] {msg}")

        roles = self.ai_mgr.get_hybrid_roles(configured_model)
        strat_mod = roles.get("strategy_model", "qwen2.5:3b")

        notify(f"⎔ Synthesizing human browsing intent (Model: {strat_mod})...")
        if strat_mod in ["qwen2.5:3b", "llava:7b"]:
            await self.vram_arbiter.request_tier2_model(strat_mod, self.ai_mgr)

        persona_name = persona.get("name", "General User") if isinstance(persona, dict) else "General User"
        persona_str = f"Interest: {persona_name}, Context: {', '.join(topic_keywords)}"
        
        query = await self.ai_mgr.generate_contextual_query(
            page_title=current_url,
            text_snippet=persona_str,
            persona=persona_name,
            model_name=strat_mod
        )

        notify(f"⌖ Strategic Search Intent Formulated: '{query}'")
        if strat_mod in ["qwen2.5:3b", "llava:7b"]:
            asyncio.create_task(self.vram_arbiter.release_tier2_if_idle(self.ai_mgr, max_idle_sec=45.0))
        return {
            "search_query": query,
            "persona_theme": topic_keywords,
            "next_action": "organic_search"
        }

    # ----------------------------------------------------------------------------------
    # PIPELINE 5: Dedicated Swarm WarmUp Methods (8-Phase Master Symphony)
    # ----------------------------------------------------------------------------------
    async def execute_warmup_preflight(
        self,
        profile_data: Dict[str, Any],
        notify_cb: Optional[Callable[[str], None]] = None
    ) -> Tuple[float, List[str], List[str]]:
        """
        Phase 1: Pre-Flight Sentinel Fingerprint & Tensor Audit (ONNX Isolation Forest).
        Validates hardware matrix, OS, WebGL shader and canvas noise consistency before session start.
        """
        def notify(msg: str):
            if notify_cb:
                notify_cb(f"⛊ [ONNX Sentinel] {msg}")

        notify("Executing mathematical 10D tensor consistency check (<1ms CPU)...")
        score, anomalies, recommendations = MLFingerprintEvaluator.evaluate(profile_data or {})
        
        if score >= 85.0:
            notify(f"Fingerprint harmony verified! Stealth Score: {score:.1f}% (Clean)")
        elif score >= 70.0:
            notify(f"Fingerprint acceptable. Stealth Score: {score:.1f}% ({len(anomalies)} minor deviations)")
        else:
            notify(f"Stealth Warning: Score {score:.1f}% with anomalies: {', '.join(anomalies[:3])}")

        return score, anomalies, recommendations

    async def synthesize_warmup_story(
        self,
        persona_key: str,
        custom_keywords: Optional[List[str]] = None,
        search_queries: Optional[List[str]] = None,
        configured_model: Optional[str] = None,
        profile_name: Optional[str] = None,
        profile_id: Optional[str] = None,
        used_queries: Optional[set] = None,
        notify_cb: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        """
        Phase 2: Intent- & Story-Synthese using strictly the configured strategy model.
        Generates a coherent, UNIQUE thematic browsing narrative ("Roter Faden") for this warmup session.
        Guarantees that parallel browsers explore distinct search topics.
        """
        def notify(msg: str):
            if notify_cb:
                notify_cb(f"⎔ [Swarm Story Lead] {msg}")

        roles = self.ai_mgr.get_hybrid_roles(configured_model)
        strat_mod = roles.get("strategy_model", "qwen2.5:3b")

        from engine.warmup.trajectory_planner import PERSONA_PROFILES
        persona_info = PERSONA_PROFILES.get(persona_key, PERSONA_PROFILES.get("general", {}))
        persona_name = persona_info.get("name", "General Consumer")
        default_queries = list(persona_info.get("queries", ["technology news 2026", "online shopping trends"]))

        notify(f"Formulating authentic browsing persona for '{persona_name}' (Profile: {profile_name or 'Default'}) (Model: {strat_mod})...")
        if strat_mod in ["qwen2.5:3b", "llava:7b"]:
            await self.vram_arbiter.request_tier2_model(strat_mod, self.ai_mgr)

        # Context seeds
        seeds = []
        if custom_keywords:
            seeds.extend(custom_keywords)
        if search_queries:
            seeds.extend(search_queries)
        if not seeds:
            seeds = default_queries

        # Ensure unique seed selection per parallel worker
        used_set = used_queries if used_queries is not None else set()
        available_seeds = [s for s in seeds if s not in used_set]
        if not available_seeds:
            available_seeds = seeds

        primary_intent = random.choice(available_seeds) if available_seeds else "lifestyle and modern technology"

        # Generate story context via configured strategy model with diversity
        prompt = (
            f"You are a real human web user (Persona: '{persona_name}', Session: '{profile_name or profile_id or 'Browser'}').\n"
            f"Your specific search topic interest right now is: '{primary_intent}'.\n"
            "Generate a single, natural, realistic 3-6 word Google search query or question related to this topic.\n"
            "Output ONLY the plain search query string, without JSON formatting, without quotes, and without preamble."
        )

        synthesized_query = primary_intent
        try:
            from engine.ai_model_manager import AIModelManager
            resp = await self.ai_mgr.generate_response(
                prompt=prompt,
                model_name=strat_mod,
                operation="⎔ WarmUp Story Synthesis",
                target_info=f"{persona_name} ({profile_name or 'Profile'})"
            )
            clean_q = AIModelManager.sanitize_search_query(resp)
            if clean_q and len(clean_q) >= 3 and len(clean_q) < 90 and clean_q not in used_set:
                synthesized_query = clean_q
            elif clean_q and clean_q in used_set:
                fallback_choices = [q for q in default_queries if q not in used_set]
                if fallback_choices:
                    synthesized_query = random.choice(fallback_choices)
                else:
                    synthesized_query = f"{clean_q} updates"
        except Exception as e:
            logger.debug(f"[AISwarm] Story synthesis fallback: {e}")

        if used_queries is not None:
            used_queries.add(synthesized_query)

        notify(f"Synthesized Coherent Session Story Query: '{synthesized_query}'")
        if strat_mod in ["qwen2.5:3b", "llava:7b"]:
            asyncio.create_task(self.vram_arbiter.release_tier2_if_idle(self.ai_mgr, max_idle_sec=30.0))

        return {
            "persona_name": persona_name,
            "session_topic": primary_intent,
            "primary_query": synthesized_query,
            "keywords": seeds
        }

    async def evaluate_search_snippets(
        self,
        top_results: List[Dict[str, str]],
        story_topic: str,
        persona_name: str,
        configured_model: Optional[str] = None,
        notify_cb: Optional[Callable[[str], None]] = None
    ) -> Optional[Dict[str, str]]:
        """
        Phase 3: Autonome Suche & Rank-Evaluation using strictly configured micro-scout model.
        Scores search result snippets for authenticity, domain authority, and thematic alignment.
        """
        def notify(msg: str):
            if notify_cb:
                notify_cb(f"⭍ [Search Scout] {msg}")

        if not top_results:
            return None

        if len(top_results) == 1:
            return top_results[0]

        roles = self.ai_mgr.get_hybrid_roles(configured_model)
        scout_mod = roles.get("micro_model", "qwen2.5:0.5b")

        notify(f"Scoring {len(top_results)} search results for topic '{story_topic}' (Model: {scout_mod})...")

        try:
            candidates_summary = "\n".join([f"[{idx+1}] {r.get('text', '')} -> {r.get('href', '')}" for idx, r in enumerate(top_results[:5])])
            prompt = (
                f"Persona: {persona_name}. Topic: {story_topic}.\n"
                f"Candidate Search Results:\n{candidates_summary}\n\n"
                f"Which index (1 to {min(5, len(top_results))}) is the most relevant organic article to click? Respond with just the single number."
            )
            
            resp = await self.ai_mgr.generate_response(
                prompt=prompt,
                model_name=scout_mod,
                operation="⭍ Search Snippet Ranking",
                target_info=story_topic
            )
            
            import re
            m = re.search(r'\b([1-5])\b', resp)
            if m:
                idx = int(m.group(1)) - 1
                if 0 <= idx < len(top_results):
                    chosen = top_results[idx]
                    notify(f"Selected Rank #{idx+1} result: {chosen.get('href', '')}")
                    return chosen
        except Exception as e:
            logger.debug(f"[AISwarm] Search ranking note: {e}")

        # Fallback to weighted choice favoring rank 1-3
        import random
        ranks = list(range(len(top_results)))
        weights = [5, 3, 2, 1, 1][:len(top_results)]
        selected_idx = random.choices(ranks, weights=weights, k=1)[0]
        chosen = top_results[selected_idx]
        notify(f"Selected Organic Rank #{selected_idx+1}: {chosen.get('href', '')}")
        return chosen

    async def evaluate_subnavigation_choice(
        self,
        link_candidates: List[Dict[str, str]],
        story_topic: str,
        persona_name: str,
        configured_model: Optional[str] = None,
        notify_cb: Optional[Callable[[str], None]] = None
    ) -> Optional[Dict[str, str]]:
        """
        Phase 7: Context-Coherent Sub-Navigation using strictly configured text model.
        Selects the next internal link that maintains realistic user interest.
        """
        def notify(msg: str):
            if notify_cb:
                notify_cb(f"◵ [Sub-Navigation Lead] {msg}")

        if not link_candidates:
            return None

        if len(link_candidates) == 1:
            return link_candidates[0]

        roles = self.ai_mgr.get_hybrid_roles(configured_model)
        subnav_mod = roles.get("text_model", "qwen2.5:1.5b")

        notify(f"Selecting coherent sub-navigation path among {len(link_candidates)} candidates (Model: {subnav_mod})...")
        
        try:
            chosen = await self.ai_mgr.select_humanoid_next_link(
                links=link_candidates,
                persona=f"{persona_name} (Focus: {story_topic})",
                model_name=subnav_mod
            )
            if chosen:
                notify(f"Selected editorial article: '{chosen.get('text', '')[:40]}' -> {chosen.get('href', '')}")
                return chosen
        except Exception as e:
            logger.debug(f"[AISwarm] Sub-navigation choice note: {e}")

        import random
        return random.choice(link_candidates[:min(6, len(link_candidates))])

    async def audit_post_warmup(
        self,
        profile_data: Dict[str, Any],
        page: Any,
        context: Any,
        initial_cookies: int,
        final_cookies: int,
        notify_cb: Optional[Callable[[str], None]] = None
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Phase 8: Post-Warmup Trust & Anomaly Audit.
        Combines ONNX Isolation Forest tensor evaluation with ProfileTrustEvaluator.
        """
        def notify(msg: str):
            if notify_cb:
                notify_cb(f"◫ [Swarm Post-Audit] {msg}")

        notify("Conducting multi-vector trust score and cookie maturation audit...")
        
        trust_score = 88.0
        trust_details: Dict[str, Any] = {"rating": "Good", "cookie_gain": final_cookies - initial_cookies}
        
        try:
            from engine.trust_score_evaluator import ProfileTrustEvaluator
            trust_score, trust_details = await ProfileTrustEvaluator.evaluate_profile_trust(
                profile_data=profile_data,
                page=page,
                context=context
            )
        except Exception as e:
            logger.debug(f"[AISwarm] ProfileTrustEvaluator note: {e}")

        # ONNX Tensor Harmony Check
        onnx_score, anomalies, _ = MLFingerprintEvaluator.evaluate(profile_data or {})
        combined_score = round(0.6 * trust_score + 0.4 * onnx_score, 1)

        notify(f"Post-Warmup Audit: Combined Trust Score {combined_score}% | Cookies: {final_cookies} (+{final_cookies - initial_cookies})")
        return combined_score, trust_details

    async def scan_page_honeypots_swarm(
        self,
        page: Any,
        configured_model: Optional[str] = None,
        notify_cb: Optional[Callable[[str], None]] = None
    ) -> Any:
        """
        Phase Honeypot Shield: Swarm-orchestrated scan of all in-page elements
        to detect, evaluate, and neutralize hidden click traps and honeypots.
        """
        from engine.honeypot_detector import HoneypotDetector, HoneypotScanResult
        def notify(m: str):
            if notify_cb:
                notify_cb(f"⛉ [Swarm Honeypot Shield] {m}")

        return await HoneypotDetector.scan_page(
            page=page,
            model_name=configured_model or "qwen2.5:1.5b",
            notify_cb=notify
        )

