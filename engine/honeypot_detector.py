import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

logger = logging.getLogger("HoneypotDetector")


@dataclass
class HoneypotScanResult:
    """Structured report produced by the Honeypot Detector."""
    is_clean: bool = True
    total_scanned: int = 0
    traps_count: int = 0
    blacklisted_hrefs: Set[str] = field(default_factory=set)
    blacklisted_selectors: List[str] = field(default_factory=list)
    blacklisted_rects: List[Dict[str, float]] = field(default_factory=list)
    trap_details: List[Dict[str, Any]] = field(default_factory=list)
    model_used: str = "Deterministic+LocalAI"
    duration_ms: float = 0.0

    def is_safe_url(self, url: str) -> bool:
        """Returns True if the target URL is not flagged as a honeypot trap."""
        if not url:
            return False
        clean_target = url.strip().lower()
        for trapped in self.blacklisted_hrefs:
            t = trapped.strip().lower()
            if t == clean_target:
                return False
            # Check host + path match without query variance
            try:
                p_trapped = urlparse(t)
                p_target = urlparse(clean_target)
                if p_trapped.netloc and p_target.netloc == p_trapped.netloc and p_trapped.path and p_target.path == p_trapped.path:
                    if p_trapped.path != "/":
                        return False
            except Exception:
                pass
        return True

    def is_safe_element(self, element_rect: Optional[Dict[str, float]] = None, href: Optional[str] = None, selector: Optional[str] = None) -> bool:
        """Checks if a specific element or coordinate intersects a known click-trap or honeypot zone."""
        if href and not self.is_safe_url(href):
            return False
        if selector and selector in self.blacklisted_selectors:
            return False
        if element_rect and self.blacklisted_rects:
            ex = element_rect.get("x", 0)
            ey = element_rect.get("y", 0)
            for r in self.blacklisted_rects:
                rx, ry, rw, rh = r.get("x", 0), r.get("y", 0), r.get("width", 0), r.get("height", 0)
                if rx <= ex <= rx + rw and ry <= ey <= ry + rh:
                    return False
        return True

    def filter_safe_links(self, link_candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filters a list of candidate links, stripping out all honeypots and click traps."""
        safe = []
        for item in link_candidates:
            h = item.get("href", "")
            if not h or not self.is_safe_url(h):
                continue
            sel = item.get("selector", "")
            if sel and sel in self.blacklisted_selectors:
                continue
            rect = item.get("rect")
            if rect and not self.is_safe_element(element_rect=rect):
                continue
            safe.append(item)
        return safe


HONEYPOT_SCAN_SCRIPT = r"""
(() => {
    const results = {
        total_scanned: 0,
        deterministic_traps: [],
        suspicious_candidates: [],
        page_title: document.title || '',
        page_url: window.location.href || ''
    };

    const TRAP_KEYWORD_REGEX = /(honeypot|honey-pot|bot-trap|spider-trap|crawler-trap|decoy|fake-link|antispam|anti-bot|nobot|trap-link|do-not-click|chk_jschl|wlwmanifest|\/trap\/|\/honey\/)/i;
    const SUSPICIOUS_HREF_REGEX = /(\/trap|\/honey|hidden|fake|spider|crawler|test-bot|bot-check|verify-human-auto)/i;

    const interactiveElements = Array.from(document.querySelectorAll(
        'a[href], button, input[type="submit"], input[type="button"], [role="button"], [onclick], div[class*="trap"], div[id*="trap"], div[class*="honey"], div[id*="honey"], span[class*="trap"], span[class*="honey"], iframe[style*="opacity: 0"], div[style*="opacity: 0"]'
    ));

    results.total_scanned = interactiveElements.length;
    const vpWidth = window.innerWidth || 1920;
    const vpHeight = window.innerHeight || 1080;

    for (let i = 0; i < interactiveElements.length; i++) {
        const el = interactiveElements[i];
        let isTrap = false;
        let reason = '';
        let trapType = 'css_hidden';

        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        const href = el.href || el.getAttribute('href') || '';
        const text = (el.innerText || el.textContent || '').trim();
        const className = el.className || '';
        const idName = el.id || '';
        const ariaHidden = el.getAttribute('aria-hidden');
        const tabIndex = el.getAttribute('tabindex');

        // 1. Semantic Trap Class / ID / Name Check
        if (TRAP_KEYWORD_REGEX.test(className) || TRAP_KEYWORD_REGEX.test(idName) || TRAP_KEYWORD_REGEX.test(href)) {
            isTrap = true;
            reason = 'Trap signature detected in class/id/href keyword';
            trapType = 'semantic_keyword';
        }

        // 2. Invisible Dimensions & Display
        else if (style.display === 'none') {
            isTrap = true;
            reason = 'Element styled with display: none';
            trapType = 'display_none';
        }
        else if (style.visibility === 'hidden' || style.visibility === 'collapse') {
            isTrap = true;
            reason = 'Element styled with visibility: hidden';
            trapType = 'visibility_hidden';
        }
        else if (parseFloat(style.opacity || '1') <= 0.01 && (rect.width > 0 && rect.height > 0)) {
            // Check if it is a transparent clickjacking overlay
            if (rect.width >= vpWidth * 0.7 && rect.height >= vpHeight * 0.7) {
                isTrap = true;
                reason = 'Full-viewport transparent clickjacking overlay detected';
                trapType = 'clickjacking_overlay';
            } else if (href || el.tagName.toLowerCase() === 'button') {
                isTrap = true;
                reason = 'Clickable link/button with 0% opacity (invisible to user)';
                trapType = 'transparent_link';
            }
        }
        else if (rect.width <= 1 && rect.height <= 1 && (rect.width > 0 || rect.height > 0)) {
            isTrap = true;
            reason = 'Microscopic 1x1 or 0-pixel click trap';
            trapType = 'zero_dimension';
        }
        else if (style.maxHeight === '0px' || style.maxWidth === '0px' || (style.overflow === 'hidden' && (rect.height === 0 || rect.width === 0))) {
            if (href) {
                isTrap = true;
                reason = 'Anchor collapsed to 0px via CSS overflow/max-height';
                trapType = 'collapsed_box';
            }
        }

        // 3. Extreme Off-Screen Coordinate Positioning
        else if (rect.x < -100 || rect.y < -100 || rect.x > vpWidth + 2000 || rect.y > vpHeight + 50000) {
            if (href || el.tagName.toLowerCase() === 'button') {
                isTrap = true;
                reason = 'Element positioned far outside viewport coordinates (' + Math.round(rect.x) + ',' + Math.round(rect.y) + ')';
                trapType = 'offscreen_position';
            }
        }
        else if (style.position === 'absolute' && (style.left === '-9999px' || style.top === '-9999px' || style.left === '-999em')) {
            isTrap = true;
            reason = 'Element positioned offscreen via absolute negative offsets';
            trapType = 'offscreen_css';
        }

        // 4. CSS Clip / Clip-path Hiding
        else if (style.clip === 'rect(0px, 0px, 0px, 0px)' || style.clip === 'rect(0, 0, 0, 0)' || style.clip === 'rect(1px, 1px, 1px, 1px)') {
            isTrap = true;
            reason = 'Element hidden via CSS clip rectangle';
            trapType = 'css_clipped';
        }
        else if (style.clipPath && (style.clipPath.includes('inset(50%)') || style.clipPath.includes('circle(0') || style.clipPath.includes('polygon(0 0, 0 0'))) {
            isTrap = true;
            reason = 'Element hidden via CSS clip-path';
            trapType = 'css_clippath';
        }

        // 5. Negative Z-Index Behind Background
        else if (parseInt(style.zIndex || '0', 10) <= -100) {
            if (href || el.tagName.toLowerCase() === 'button') {
                isTrap = true;
                reason = 'Clickable element submerged beneath page layers with negative z-index';
                trapType = 'negative_zindex';
            }
        }

        // 6. Accessibility Cloaking on Interactive Links
        else if ((ariaHidden === 'true' || tabIndex === '-1') && href && text.length > 5 && style.display !== 'none' && rect.height < 5) {
            isTrap = true;
            reason = 'Aria-hidden cloak on flattened anchor link';
            trapType = 'aria_cloak';
        }

        // Compile Findings
        const elementData = {
            tag: el.tagName.toLowerCase(),
            href: href,
            text: text.slice(0, 80),
            id: idName,
            className: typeof className === 'string' ? className.slice(0, 80) : '',
            rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
            reason: reason,
            trap_type: trapType
        };

        if (isTrap) {
            results.deterministic_traps.push(elementData);
        } else if (SUSPICIOUS_HREF_REGEX.test(href) || (text.length === 0 && rect.width > 20 && rect.height > 20 && !el.querySelector('img, svg'))) {
            // Potential ambiguous trap candidate -> send to AI for cognitive verification
            results.suspicious_candidates.push(elementData);
        }
    }

    return results;
})()
"""


class HoneypotDetector:
    """High-Speed Deterministic & AI-Assisted Honeypot Click-Trap Detection Engine."""

    @classmethod
    async def scan_page(
        cls,
        page: Any,
        model_name: Optional[str] = None,
        evaluate_fn: Optional[Callable] = None,
        notify_cb: Optional[Callable[[str], None]] = None,
        timeout_sec: float = 3.0
    ) -> HoneypotScanResult:
        """Executes a full DOM honeypot scan on the given page.
        
        1. Fast In-Page DOM Javascript analysis (<2ms CPU)
        2. Local Micro-LLM / Gemini Evaluation of ambiguous trap candidates (<150ms)
        3. Returns structured HoneypotScanResult with blacklists and safe selectors.
        """
        start_t = time.time()
        result = HoneypotScanResult()

        if not page:
            return result

        try:
            # 1. Execute JS In-DOM Scanner
            raw_scan: Optional[Dict[str, Any]] = None
            if evaluate_fn:
                raw_scan = await evaluate_fn(page, HONEYPOT_SCAN_SCRIPT)
            elif hasattr(page, "evaluate"):
                raw_scan = await page.evaluate(HONEYPOT_SCAN_SCRIPT)
            elif hasattr(page, "evaluate_async"):
                raw_scan = await page.evaluate_async(HONEYPOT_SCAN_SCRIPT)

            if not raw_scan or not isinstance(raw_scan, dict):
                result.duration_ms = round((time.time() - start_t) * 1000, 2)
                return result

            total_scanned = raw_scan.get("total_scanned", 0)
            det_traps = raw_scan.get("deterministic_traps", [])
            suspicious = raw_scan.get("suspicious_candidates", [])
            page_title = raw_scan.get("page_title", "")
            page_url = raw_scan.get("page_url", getattr(page, "url", ""))

            result.total_scanned = total_scanned

            # Ingest deterministic traps immediately
            for trap in det_traps:
                result.traps_count += 1
                h = trap.get("href")
                if h and isinstance(h, str) and h.startswith("http"):
                    result.blacklisted_hrefs.add(h)
                
                # Register selector / ID if available
                t_id = trap.get("id")
                if t_id:
                    result.blacklisted_selectors.append(f"#{t_id}")
                t_class = trap.get("className")
                if t_class and " " not in t_class:
                    result.blacklisted_selectors.append(f".{t_class}")
                
                rect = trap.get("rect")
                if rect and isinstance(rect, dict):
                    result.blacklisted_rects.append(rect)

                result.trap_details.append(trap)

            # 2. AI Model Verification for Ambiguous / Suspicious candidates
            if suspicious:
                ai_evaluated_traps = await cls._evaluate_candidates_with_ai(
                    candidates=suspicious[:10],
                    page_url=page_url,
                    page_title=page_title,
                    model_name=model_name
                )
                for ai_trap in ai_evaluated_traps:
                    result.traps_count += 1
                    h = ai_trap.get("href")
                    if h and isinstance(h, str) and h.startswith("http"):
                        result.blacklisted_hrefs.add(h)
                    
                    t_id = ai_trap.get("id")
                    if t_id:
                        result.blacklisted_selectors.append(f"#{t_id}")
                    rect = ai_trap.get("rect")
                    if rect:
                        result.blacklisted_rects.append(rect)
                    result.trap_details.append(ai_trap)

            result.is_clean = (result.traps_count == 0)
            result.duration_ms = round((time.time() - start_t) * 1000, 2)
            result.model_used = model_name or "Deterministic+Qwen"

            # 3. Notification & Telemetry Logging
            if not result.is_clean:
                trap_reasons = ", ".join(t.get("reason", "Trap") for t in result.trap_details[:3])
                msg = f"⛉ [AI Honeypot Shield] {result.traps_count} Honeypots / Click-Traps detected & neutralized ({trap_reasons}) [{result.duration_ms}ms]"
                logger.warning(msg)
                if notify_cb:
                    notify_cb(msg)
            else:
                msg = f"⛉ [AI Honeypot Shield] DOM verified clean ({total_scanned} elements scanned, 0 traps) [{result.duration_ms}ms]"
                logger.debug(msg)
                if notify_cb:
                    notify_cb(msg)

            return result

        except Exception as e:
            logger.debug(f"Honeypot scan exception: {e}")
            result.duration_ms = round((time.time() - start_t) * 1000, 2)
            return result

    @classmethod
    async def _evaluate_candidates_with_ai(
        cls,
        candidates: List[Dict[str, Any]],
        page_url: str,
        page_title: str,
        model_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Sends ambiguous candidate elements to AIModelManager for cognitive classification."""
        if not candidates:
            return []

        try:
            from engine.ai_model_manager import AIModelManager
            ai_mgr = AIModelManager.get_instance()
            if not ai_mgr:
                return []

            return await ai_mgr.evaluate_honeypot_elements(
                elements_data=candidates,
                page_url=page_url,
                page_title=page_title,
                model_name=model_name
            )
        except Exception as ai_e:
            logger.debug(f"AI honeypot evaluation note: {ai_e}")
            return []

    # Compatibility Aliases
    scan_page_for_honeypots = scan_page

    _instance: Optional['HoneypotDetector'] = None

    @classmethod
    def get_instance(cls) -> 'HoneypotDetector':
        if cls._instance is None:
            cls._instance = HoneypotDetector()
        return cls._instance
