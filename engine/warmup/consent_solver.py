import asyncio
import random
import logging
from typing import Any, Callable, List, Optional
from engine.warmup.human_motion import BiomechanicalMotor

logger = logging.getLogger("ConsentSolver")

COMMON_COOKIE_SELECTORS: List[str] = [
    # Google / YouTube specific IDs & Attributes
    "#L2AGLb",
    "#introAgreeButton",
    "button[aria-label*='Alle akzeptieren']",
    "button[aria-label*='Accept all']",
    "button[aria-label*='Accept the use of cookies']",
    "form[action*='consent'] button",
    "button[data-cookiebanner='accept_button']",
    "button[name='agree']",
    "button.agree",
    # OneTrust & CookiePro
    "#onetrust-accept-btn-handler",
    "#accept-recommended-btn-handler",
    "#onetrust-pc-btn-handler",
    ".ot-sdk-button-opt-in",
    "button[id*='onetrust-accept']",
    ".save-preference-btn-handler",
    # Cookiebot
    "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
    "#CybotCookiebotDialogBodyButtonAccept",
    "#CybotCookiebotDialogBodyLevelButtonAccept",
    "#CybotCookiebotDialogBodyLevelButtonAcceptAll",
    # Usercentrics (v1, v2, v3 + Shadow DOM)
    "button[data-testid='uc-accept-all-button']",
    "button#uc-btn-accept-banner",
    "div[data-testid='uc-overlay'] button[data-testid='uc-accept-all-button']",
    "#usercentrics-root",
    "uc-banner",
    # Didomi
    "#didomi-notice-agree-button",
    "#didomi-consent-popup",
    ".didomi-components-button-agree",
    "button[id*='didomi']",
    # SourcePoint / CMP 2.0
    "button.sp_choice_type_11",
    ".sp_choice_type_11",
    "button[title*='Accept' i]",
    "button[title*='Akzeptieren' i]",
    "button[aria-label*='Accept' i]",
    "button[aria-label*='Akzeptieren' i]",
    # Quantcast Choice
    ".qc-cmp2-summary-buttons button[mode='primary']",
    "button.qc-cmp2-summary-button",
    "button[mode='primary']",
    # TrustArc / TRUSTe
    ".truste-button1",
    "#truste-consent-button",
    "#truste-consent-required",
    ".truste-custom-btn",
    "button.trustarc-agree-btn",
    # Klaro
    ".klaro .cm-btn-accept",
    ".klaro .cm-btn-success",
    "button.cm-btn.cm-btn-success",
    # Borlabs Cookie (German WordPress)
    "a._brlbs-btn-accept-all",
    "button._brlbs-btn-accept-all",
    "a._brlbs-btn-accept",
    "[data-borlabs-cookie-accept-all]",
    "._brlbs-accept-all",
    # CookieYes
    "button.cky-btn-accept",
    "[data-cky-tag='accept-button']",
    ".cky-consent-bar .cky-btn-accept",
    ".cky-btn-accept-all",
    "button.cky-btn-accept-all",
    # ConsentManager.net
    "#cmpwelcomebtnyes a",
    "#cmpbntyes",
    "#cmpbntyes a",
    ".cmpboxbtn.cmpboxbtnyes",
    "a#cmpbntyes",
    "button#cmpbntyes",
    # Iubenda
    ".iubenda-cs-accept-btn",
    "button.iubenda-cs-btn-primary",
    ".iubenda-cs-btn",
    # Complianz
    ".cmplz-accept",
    "button.cmplz-btn.cmplz-accept",
    # Axeptio
    "button#axeptio_btn_acceptAll",
    "[id*='axeptio'] button",
    ".axeptio_mount button:first-of-type",
    # Fides
    "#fides-accept-all-button",
    ".fides-accept-all-button",
    "button[data-fides-action='accept-all']",
    # Termly
    "button[data-tid='banner-accept']",
    ".termly-banner-accept-button",
    # Civic UK & Osano
    "#ccc-recommended-settings",
    "#ccc-notify-accept",
    ".osano-cm-accept-all",
    ".osano-cm-button--type_accept",
    # Sirdata, Uniconsent, Shopify
    "#sd-cmp button.sd-cmp-2V7f5",
    ".sd-cmp-btn-agree",
    "#unic-agree",
    ".unic-btn-agree",
    "#shopify-pc__banner__btn-accept",
    # General attribute selectors
    "#accept-cookies",
    "#accept-all-cookies",
    ".accept-cookies-button",
    ".js-cookie-consent-accept",
    "button[id*='accept']",
    "button[class*='accept']",
    "button[aria-label*='Accept']",
    "button[aria-label*='akzeptieren']",
    "a[class*='accept']",
    "button[id*='consent']",
    "button[class*='consent']",
]

CHECK_CONSENT_CONTAINER_SCRIPT = r"""
(() => {
    // Check if an actual consent dialog/modal/banner container exists and is visible on DOM or Shadow DOM
    const bannerSelectors = [
        '#onetrust-banner-sdk', '#onetrust-consent-sdk', '#CybotCookiebotDialog',
        '#usercentrics-root', 'uc-banner', '.didomi-popup-container', '#didomi-notice',
        '.qc-cmp2-container', '[class*="cookie-banner"]', '[class*="cookie-modal"]',
        '[class*="consent-modal"]', '[class*="consent-banner"]', '[id*="cookie-banner"]',
        '[id*="consent-banner"]', '#L2AGLb', 'form[action*="consent"]',
        '#cmpbox', '#cmpwrapper', '.cookie-notice', '#cookie-law-info-bar',
        '.cky-consent-container', '.iubenda-cs-container', '.cm-container',
        '._brlbs-banner', '#borlabs-cookie-box', '#truste-consent-track'
    ];
    for (const sel of bannerSelectors) {
        const el = document.querySelector(sel);
        if (el) {
            const style = window.getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            if (style.display !== 'none' && style.visibility !== 'hidden' && rect.height > 15) {
                return true;
            }
        }
    }
    const dialogs = Array.from(document.querySelectorAll('dialog, [role="dialog"], [aria-modal="true"]'));
    for (const d of dialogs) {
        const txt = (d.innerText || '').toLowerCase();
        if (txt.includes('cookie') || txt.includes('consent') || txt.includes('datenschutz') || txt.includes('privacy') || txt.includes('gdpr')) {
            const style = window.getComputedStyle(d);
            const rect = d.getBoundingClientRect();
            if (style.display !== 'none' && style.visibility !== 'hidden' && rect.height > 15) {
                return true;
            }
        }
    }
    // Also check open shadow roots on root elements
    const uc = document.querySelector('#usercentrics-root, uc-banner');
    if (uc && uc.shadowRoot) {
        const srBtn = uc.shadowRoot.querySelector('button[data-testid="uc-accept-all-button"], button#uc-btn-accept-banner');
        if (srBtn) return true;
    }
    return false;
})()
"""

# Universal In-Page Autowatcher & Shadow-DOM Interceptor Script
AUTOWATCHER_SCRIPT = r"""
(() => {
    if (window.__soxbot_consent_autowatcher_active) return true;
    window.__soxbot_consent_autowatcher_active = true;

    const directSelectors = [
        '#L2AGLb',
        '#onetrust-accept-btn-handler',
        '#accept-recommended-btn-handler',
        '#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll',
        '#CybotCookiebotDialogBodyButtonAccept',
        '#CybotCookiebotDialogBodyLevelButtonAccept',
        '#CybotCookiebotDialogBodyLevelButtonAcceptAll',
        'button#uc-btn-accept-banner',
        'button[data-testid="uc-accept-all-button"]',
        '#didomi-notice-agree-button',
        'button.sp_choice_type_11',
        '.sp_choice_type_11',
        '.qc-cmp2-summary-buttons button[mode="primary"]',
        'button.qc-cmp2-summary-button',
        '#truste-consent-button',
        '.truste-button1',
        'a._brlbs-btn-accept-all',
        'button._brlbs-btn-accept-all',
        'a._brlbs-btn-accept',
        '[data-borlabs-cookie-accept-all]',
        'button.cky-btn-accept',
        '[data-cky-tag="accept-button"]',
        'button.cky-btn-accept-all',
        '#cmpwelcomebtnyes a',
        '#cmpbntyes',
        '#cmpbntyes a',
        '.cmpboxbtn.cmpboxbtnyes',
        'a#cmpbntyes',
        '.iubenda-cs-accept-btn',
        'button.iubenda-cs-btn-primary',
        '.cmplz-accept',
        'button.cmplz-btn.cmplz-accept',
        'button#axeptio_btn_acceptAll',
        '#fides-accept-all-button',
        '#ccc-recommended-settings',
        '.osano-cm-accept-all',
        '#shopify-pc__banner__btn-accept',
        'button[data-cookiebanner="accept_button"]',
        'button[name="agree"]',
        '#accept-all-cookies',
        '#accept-cookies',
        '.accept-cookies-button',
        '.js-cookie-consent-accept'
    ];

    const positiveAcceptRegex = /(alle\s*akzeptieren|alle\s*cookies\s*akzeptieren|alles\s*akzeptieren|cookies\s*akzeptieren|zustimmen|einverstanden|alle\s*erlauben|cookies\s*erlauben|alle\s*zulassen|cookies\s*zulassen|alle\s*annehmen|cookies\s*annehmen|ich\s*stimme\s*zu|akzeptieren\s*(&|und)\s*(fortfahren|weiter|schlie|speichern)|alles\s*erlauben|verstanden|alles\s*klar|accept\s*all|accept\s*all\s*cookies|allow\s*all|allow\s*all\s*cookies|agree\s*(&|and)\s*(proceed|continue|close)|accept\s*(&|and)\s*(continue|proceed|close)|i\s*agree|i\s*accept|agree\s*to\s*all|accept\s*recommended|enable\s*all|consent\s*to\s*all|tout\s*accepter|accepter\s*tous|accepter\s*tout|j'accepte|autoriser\s*tout|tout\s*autoriser|aceptar\s*todo|aceptar\s*todas|permitir\s*todas|de\s*acuerdo|estoy\s*de\s*acuerdo|accetta\s*tutti|accetta\s*tutti\s*i\s*cookie|accetto|acconsento|consenti\s*tutti|alles\s*accepteren|alle\s*cookies\s*accepteren|alles\s*toestaan|zaakceptuj\s*wszystkie|wszystkie\s*zgody|godk\xe4nn\s*alla|godkend\s*alle|aksepter\s*alle)/i;

    const exclusionRegex = /(do\s*not|don't|reject|ablehnen|decline|refuse|without|nur\s*notwendige|necessary\s*only|nur\s*essenzielle|opt-out|disagree|nicht\s*zustimmen|nein|manage|einstellungen|pr\xe4ferenzen|customise|customize|options|save\s*choices|speichern|log\s*in|signin|sign\s*in|sign\s*up|signup|upload|feedback|more|about|cart|basket|warenkorb|search|suche|account|konto)/i;

    function isClickable(el) {
        if (!el) return false;
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return style.display !== 'none' &&
               style.visibility !== 'hidden' &&
               style.opacity !== '0' &&
               rect.width > 8 && rect.height > 8;
    }

    function isInsideConsentScope(el) {
        let parent = el;
        while (parent && parent !== document.body && parent !== document.documentElement) {
            const cls = (typeof parent.getAttribute === 'function' ? (parent.getAttribute('class') || '') : '').toLowerCase();
            const id = (parent.id || '').toLowerCase();
            const role = (parent.getAttribute ? (parent.getAttribute('role') || '') : '').toLowerCase();
            const tag = (parent.tagName || '').toUpperCase();

            if (id.includes('cookie') || id.includes('consent') || id.includes('gdpr') ||
                id.includes('privacy') || id.includes('datenschutz') || id.includes('cmp') ||
                id.includes('usercentrics') || id.includes('onetrust') || id.includes('didomi') ||
                id.includes('cookiebot') || id.includes('borlabs') || id.includes('cky-') ||
                cls.includes('cookie') || cls.includes('consent') || cls.includes('gdpr') ||
                cls.includes('privacy') || cls.includes('datenschutz') || cls.includes('cmp') ||
                cls.includes('usercentrics') || cls.includes('onetrust') || cls.includes('didomi') ||
                cls.includes('cookiebot') || cls.includes('borlabs') || cls.includes('cky-') ||
                role === 'dialog' || tag === 'DIALOG' || parent.getAttribute?.('aria-modal') === 'true') {
                return true;
            }
            parent = parent.parentElement;
        }
        return false;
    }

    function triggerClick(el) {
        try { el.scrollIntoView({ block: 'center', inline: 'center' }); } catch(e){}
        try { el.focus(); } catch(e){}
        try { el.click(); } catch(e){}
        try {
            const mousedown = new MouseEvent('mousedown', { bubbles: true, cancelable: true, view: window });
            const mouseup = new MouseEvent('mouseup', { bubbles: true, cancelable: true, view: window });
            const click = new MouseEvent('click', { bubbles: true, cancelable: true, view: window });
            el.dispatchEvent(mousedown);
            el.dispatchEvent(mouseup);
            el.dispatchEvent(click);
        } catch(e){}
    }

    function searchAndClickInRoot(root) {
        if (!root) return false;

        // 1. Check known direct CMP selectors first
        for (const sel of directSelectors) {
            try {
                const btn = root.querySelector(sel);
                if (btn && isClickable(btn)) {
                    triggerClick(btn);
                    return true;
                }
            } catch(e){}
        }

        // 2. Semantic matching across buttons, links, and role=button
        const candidates = Array.from(root.querySelectorAll('button, a, div[role="button"], span[role="button"], input[type="button"], input[type="submit"]'));
        for (const el of candidates) {
            const rawTxt = (el.innerText || el.textContent || el.value || el.getAttribute?.('aria-label') || el.title || '').replace(/\\s+/g, ' ').trim();
            if (rawTxt.length >= 2 && rawTxt.length < 80 && isClickable(el)) {
                if (exclusionRegex.test(rawTxt)) continue;

                const hasExplicitCookieAttr = (el.id && el.id.toLowerCase().includes('cookie')) ||
                                             (el.className && typeof el.className === 'string' && el.className.toLowerCase().includes('cookie')) ||
                                             el.id === 'L2AGLb' ||
                                             /cookies/i.test(rawTxt);

                if (!hasExplicitCookieAttr && !isInsideConsentScope(el)) {
                    continue;
                }

                if (positiveAcceptRegex.test(rawTxt)) {
                    triggerClick(el);
                    return true;
                }
            }
        }

        // 3. Piercing open Shadow DOMs recursively
        try {
            const allElements = root.querySelectorAll('*');
            for (const node of allElements) {
                if (node.shadowRoot) {
                    const resolved = searchAndClickInRoot(node.shadowRoot);
                    if (resolved) return true;
                }
            }
        } catch(e){}

        return false;
    }

    function attemptResolution() {
        if (searchAndClickInRoot(document)) {
            window.__soxbot_consent_resolved = true;
            return true;
        }
        return false;
    }

    // Run initial pass immediately
    attemptResolution();

    // Setup active MutationObserver
    let resolvedCount = 0;
    const observer = new MutationObserver((mutations) => {
        for (const m of mutations) {
            if ((m.addedNodes && m.addedNodes.length > 0) || m.type === 'attributes') {
                if (attemptResolution()) {
                    resolvedCount++;
                    // Keep observing in case of a 2nd confirmation dialog, but debounce
                    if (resolvedCount >= 3) {
                        try { observer.disconnect(); } catch(e){}
                        break;
                    }
                }
            }
        }
    });

    try {
        observer.observe(document.documentElement || document.body, {
            childList: true,
            subtree: true,
            attributes: true,
            attributeFilter: ['class', 'style', 'hidden', 'aria-hidden']
        });
    } catch(e){}

    // Periodic heartbeat check every 750ms for delayed CMPs up to 60s
    let intervalTicks = 0;
    const intervalTimer = setInterval(() => {
        intervalTicks++;
        if (attemptResolution()) {
            resolvedCount++;
            if (resolvedCount >= 3 || intervalTicks > 80) {
                clearInterval(intervalTimer);
                try { observer.disconnect(); } catch(e){}
            }
        }
        if (intervalTicks > 80) {
            clearInterval(intervalTimer);
            try { observer.disconnect(); } catch(e){}
        }
    }, 750);

    return true;
})()
"""


class SemanticBannerResolver:
    """Dynamic multi-lingual NLP & Deep Shadow DOM Cookie Consent Resolver.
    Inspects DOM, Shadow DOM roots, and iframe contexts for multi-lingual consent patterns (DE, EN, FR, ES, IT, NL, PL, SV).
    Reliably clicks full-acceptance buttons while filtering out negative / anti-consent options.
    """

    @classmethod
    async def resolve_consent_banners(
        cls,
        page: Any,
        evaluate_fn: Callable,
        model_name: Optional[str] = None,
        vision_model: Optional[str] = None
    ) -> bool:
        """Scans DOM, all open Shadow DOMs, and all frame contexts to accept all cookies."""
        try:
            # 1. Direct fast-path: Check known direct CMP buttons across DOM and Shadow DOMs
            direct_cmp_script = r"""
            (() => {
                const directSelectors = [
                    '#L2AGLb',
                    '#onetrust-accept-btn-handler',
                    '#accept-recommended-btn-handler',
                    '#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll',
                    '#CybotCookiebotDialogBodyButtonAccept',
                    '#CybotCookiebotDialogBodyLevelButtonAccept',
                    '#CybotCookiebotDialogBodyLevelButtonAcceptAll',
                    'button#uc-btn-accept-banner',
                    'button[data-testid="uc-accept-all-button"]',
                    '#didomi-notice-agree-button',
                    'button.sp_choice_type_11',
                    '.sp_choice_type_11',
                    '.qc-cmp2-summary-buttons button[mode="primary"]',
                    'button.qc-cmp2-summary-button',
                    '#truste-consent-button',
                    '.truste-button1',
                    'a._brlbs-btn-accept-all',
                    'button._brlbs-btn-accept-all',
                    'a._brlbs-btn-accept',
                    '[data-borlabs-cookie-accept-all]',
                    'button.cky-btn-accept',
                    '[data-cky-tag="accept-button"]',
                    'button.cky-btn-accept-all',
                    '#cmpwelcomebtnyes a',
                    '#cmpbntyes',
                    '#cmpbntyes a',
                    '.cmpboxbtn.cmpboxbtnyes',
                    'a#cmpbntyes',
                    '.iubenda-cs-accept-btn',
                    'button.iubenda-cs-btn-primary',
                    '.cmplz-accept',
                    'button.cmplz-btn.cmplz-accept',
                    'button#axeptio_btn_acceptAll',
                    '#fides-accept-all-button',
                    '#ccc-recommended-settings',
                    '.osano-cm-accept-all',
                    '#shopify-pc__banner__btn-accept',
                    'button[data-cookiebanner="accept_button"]',
                    'button[name="agree"]',
                    '#accept-all-cookies',
                    '#accept-cookies',
                    '.accept-cookies-button',
                    '.js-cookie-consent-accept',
                    'button[aria-label*="Alle akzeptieren"]',
                    'button[aria-label*="Accept all"]',
                    'button[aria-label*="Accept the use of cookies"]',
                    'form[action*="consent"] button'
                ];

                function searchRoot(root) {
                    if (!root) return null;
                    for (const sel of directSelectors) {
                        try {
                            const btn = root.querySelector(sel);
                            if (btn) {
                                const style = window.getComputedStyle(btn);
                                const rect = btn.getBoundingClientRect();
                                if (style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 5 && rect.height > 5) {
                                    try { btn.scrollIntoView({ block: 'center', inline: 'center' }); } catch(e){}
                                    try { btn.click(); } catch(e){}
                                    try {
                                        const evt = new MouseEvent('click', { bubbles: true, cancelable: true, view: window });
                                        btn.dispatchEvent(evt);
                                    } catch(e){}
                                    return {
                                        found: true,
                                        x: rect.left,
                                        y: rect.top,
                                        width: rect.width,
                                        height: rect.height,
                                        text: (btn.innerText || btn.textContent || sel).trim()
                                    };
                                }
                            }
                        } catch(e){}
                    }

                    // Traverse Shadow DOMs
                    const nodes = root.querySelectorAll('*');
                    for (const node of nodes) {
                        if (node.shadowRoot) {
                            const res = searchRoot(node.shadowRoot);
                            if (res) return res;
                        }
                    }
                    return null;
                }

                return searchRoot(document);
            })()
            """

            # Check frames
            frames_to_check = []
            if hasattr(page, "frames") and isinstance(page.frames, list) and page.frames:
                frames_to_check = list(page.frames)
            else:
                frames_to_check = [page]

            for frame in frames_to_check:
                try:
                    direct_res = await evaluate_fn(frame, direct_cmp_script)
                    if direct_res and isinstance(direct_res, dict) and direct_res.get("found"):
                        cx = direct_res.get("x", 0) + direct_res.get("width", 0) / 2.0
                        cy = direct_res.get("y", 0) + direct_res.get("height", 0) / 2.0
                        if cx > 0 and cy > 0 and hasattr(page, "mouse") and hasattr(page.mouse, "click"):
                            try:
                                await BiomechanicalMotor.move_mouse_humanoid(page, 200, 200, cx, cy, target_width=direct_res.get("width", 40.0))
                                await page.mouse.click(cx, cy)
                            except Exception:
                                pass
                        btn_txt = direct_res.get('text', '')[:40]
                        logger.info(f"Accepted cookie banner ('{btn_txt}') via Direct CMP Matcher.")
                        await asyncio.sleep(random.uniform(0.6, 1.2))
                        return True
                except Exception:
                    continue

            # 2. In-Page Scanner: Multi-lingual semantic matching with shadow DOM traversal
            scanner_script = r"""
            (() => {
                const positivePatterns = [
                    // German variants
                    /\\balle\\s*akzeptieren\\b/i,
                    /\\balle\\s*cookies\\s*akzeptieren\\b/i,
                    /\\balles\\s*akzeptieren\\b/i,
                    /\\bcookies\\s*akzeptieren\\b/i,
                    /\\bzustimmen\\b/i,
                    /\\beinverstanden\\b/i,
                    /\\balle\\s*erlauben\\b/i,
                    /\\bcookies\\s*erlauben\\b/i,
                    /\\balle\\s*zulassen\\b/i,
                    /\\bcookies\\s*zulassen\\b/i,
                    /\\balle\\s*annehmen\\b/i,
                    /\\bcookies\\s*annehmen\\b/i,
                    /\\bich\\s*stimme\\s*zu\\b/i,
                    /\\bakzeptieren\\s*(&|und)\\s*(fortfahren|weiter|schlie|speichern)\\b/i,
                    /\\balles\\s*erlauben\\b/i,
                    /\\bverstanden\\b/i,
                    /\\balles\\s*klar\\b/i,
                    // English variants
                    /\\baccept\\s*all\\b/i,
                    /\\baccept\\s*all\\s*cookies\\b/i,
                    /\\ballow\\s*all\\b/i,
                    /\\ballow\\s*all\\s*cookies\\b/i,
                    /\\bagree\\s*(&|and)\\s*(proceed|continue|close)\\b/i,
                    /\\baccept\\s*(&|and)\\s*(continue|proceed|close)\\b/i,
                    /\\bi\\s*agree\\b/i,
                    /\\bi\\s*accept\\b/i,
                    /\\bagree\\s*to\\s*all\\b/i,
                    /\\baccept\\s*recommended\\b/i,
                    /\\benable\\s*all\\b/i,
                    /\\bconsent\\s*to\\s*all\\b/i,
                    /\\bgot\\s*it\\b/i,
                    // French variants
                    /\\btout\\s*accepter\\b/i,
                    /\\baccepter\\s*tous\\b/i,
                    /\\baccepter\\s*tout\\b/i,
                    /\\bj'accepte\\b/i,
                    /\\bautoriser\\s*tout\\b/i,
                    // Spanish variants
                    /\\baceptar\\s*todo\\b/i,
                    /\\baceptar\\s*todas\\b/i,
                    /\\bpermitir\\s*todas\\b/i,
                    /\\bde\\s*acuerdo\\b/i,
                    /\\bestoy\\s*de\\s*acuerdo\\b/i,
                    // Italian variants
                    /\\baccetta\\s*tutti\\b/i,
                    /\\baccetta\\s*tutti\\s*i\\s*cookie\\b/i,
                    /\\baccetto\\b/i,
                    /\\bacconsento\\b/i,
                    /\\bconsenti\\s*tutti\\b/i,
                    // Dutch & Polish & Nordic
                    /\\balles\\s*accepteren\\b/i,
                    /\\balle\\s*cookies\\s*accepteren\\b/i,
                    /\\balles\\s*toestaan\\b/i,
                    /\\bzaakceptuj\\s*wszystkie\\b/i,
                    /\\bwszystkie\\s*zgody\\b/i,
                    /\\bgodk\xe4nn\\s*alla\\b/i,
                    /\\bgodkend\\s*alle\\b/i,
                    /\\baksepter\\s*alle\\b/i
                ];

                const exclusionPatterns = [
                    /do\\s*not/i, /don't/i, /reject/i, /ablehnen/i, /decline/i, /refuse/i,
                    /without/i, /nur\\s*notwendige/i, /necessary\\s*only/i, /nur\\s*essenzielle/i,
                    /opt-out/i, /disagree/i, /nicht\\s*zustimmen/i, /nein/i,
                    /manage/i, /einstellungen/i, /pr\xe4ferenzen/i, /customise/i, /customize/i, /options/i,
                    /save\\s*choices/i, /speichern/i,
                    /log\\s*in/i, /signin/i, /sign\\s*in/i, /sign\\s*up/i, /signup/i,
                    /upload/i, /feedback/i, /more/i, /about/i, /cart/i, /basket/i, /warenkorb/i,
                    /search/i, /suche/i, /account/i, /konto/i, /statement/i, /break/i
                ];

                function isVisible(el) {
                    if (!el) return false;
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    return style.display !== 'none' && 
                           style.visibility !== 'hidden' && 
                           style.opacity !== '0' &&
                           rect.width > 10 && rect.height > 10;
                }

                function isInsideConsentContainer(el) {
                    let parent = el;
                    while (parent && parent !== document.body && parent !== document.documentElement) {
                        const cls = (typeof parent.getAttribute === 'function' ? (parent.getAttribute('class') || '') : '').toLowerCase();
                        const id = (parent.id || '').toLowerCase();
                        const role = (parent.getAttribute ? (parent.getAttribute('role') || '') : '').toLowerCase();
                        const tag = (parent.tagName || '').toUpperCase();

                        if (id.includes('cookie') || id.includes('consent') || id.includes('gdpr') ||
                            id.includes('privacy') || id.includes('datenschutz') || id.includes('sp_message') ||
                            id.includes('cmp') || id.includes('usercentrics') || id.includes('onetrust') ||
                            id.includes('didomi') || id.includes('cookiebot') || id.includes('borlabs') || id.includes('cky-') ||
                            cls.includes('cookie') || cls.includes('consent') || cls.includes('gdpr') ||
                            cls.includes('privacy') || cls.includes('datenschutz') || cls.includes('sp_message') ||
                            cls.includes('cmp') || cls.includes('usercentrics') || cls.includes('onetrust') ||
                            cls.includes('didomi') || cls.includes('cookiebot') || cls.includes('borlabs') || cls.includes('cky-') ||
                            role === 'dialog' || tag === 'DIALOG' || parent.getAttribute?.('aria-modal') === 'true') {
                            return true;
                        }
                        parent = parent.parentElement;
                    }
                    return false;
                }

                function searchRoots(root) {
                    if (!root) return null;
                    const elements = Array.from(root.querySelectorAll(
                        '#L2AGLb, button, a[role="button"], a.btn, a.button, div[role="button"], span[role="button"], input[type="button"], input[type="submit"]'
                    ));

                    for (const el of elements) {
                        const txt = (el.innerText || el.textContent || el.value || el.getAttribute?.('aria-label') || el.title || '').replace(/\\s+/g, ' ').trim();
                        if (txt.length >= 2 && txt.length < 80 && isVisible(el)) {
                            // Check exclusion
                            if (exclusionPatterns.some(ex => ex.test(txt))) continue;

                            // Must either match explicit cookie keyword or be in consent container
                            const hasExplicitCookieAttr = (el.id && el.id.toLowerCase().includes('cookie')) ||
                                                         (el.className && typeof el.className === 'string' && el.className.toLowerCase().includes('cookie')) ||
                                                         el.id === 'L2AGLb' ||
                                                         /cookies?/i.test(txt);

                            if (!hasExplicitCookieAttr && !isInsideConsentContainer(el)) {
                                continue;
                            }

                            for (const pat of positivePatterns) {
                                if (pat.test(txt)) {
                                    try { el.scrollIntoView({ block: 'center', inline: 'center' }); } catch(e){}
                                    try { el.click(); } catch(e){}
                                    try {
                                        const evt = new MouseEvent('click', { bubbles: true, cancelable: true, view: window });
                                        el.dispatchEvent(evt);
                                    } catch(e){}

                                    const rect = el.getBoundingClientRect();
                                    return {
                                        found: true,
                                        x: rect.left,
                                        y: rect.top,
                                        width: rect.width,
                                        height: rect.height,
                                        text: txt
                                    };
                                }
                            }
                        }
                    }

                    // Search open Shadow DOMs
                    const allNodes = Array.from(root.querySelectorAll('*'));
                    for (const node of allNodes) {
                        if (node.shadowRoot) {
                            const res = searchRoots(node.shadowRoot);
                            if (res) return res;
                        }
                    }
                    return null;
                }

                return searchRoots(document);
            })()
            """

            for frame in frames_to_check:
                try:
                    res = await evaluate_fn(frame, scanner_script)
                    if res and isinstance(res, dict) and res.get("found"):
                        cx = res.get("x", 0) + res.get("width", 0) / 2.0
                        cy = res.get("y", 0) + res.get("height", 0) / 2.0

                        if cx > 0 and cy > 0 and hasattr(page, "mouse") and hasattr(page.mouse, "click"):
                            try:
                                await BiomechanicalMotor.move_mouse_humanoid(page, 200, 200, cx, cy, target_width=res.get("width", 40.0))
                                await page.mouse.click(cx, cy)
                            except Exception:
                                pass
                        btn_txt = res.get('text', '')[:40]
                        logger.info(f"Accepted cookie banner ('{btn_txt}') via Verified Consent Matcher.")
                        await asyncio.sleep(random.uniform(0.6, 1.2))
                        return True
                except Exception:
                    continue

            # 3. AI Micro-LLM Tactician (if candidates exist within verified consent containers)
            try:
                from engine.ai_model_manager import AIModelManager
                ai_mgr = AIModelManager.get_instance()
                if await ai_mgr.is_engine_ready(model_name):
                    candidates_script = r"""
                    (() => {
                        const banner = document.querySelector(
                            '#onetrust-banner-sdk, #CybotCookiebotDialog, #usercentrics-root, uc-banner, ' +
                            '.didomi-popup-container, .qc-cmp2-container, [class*="cookie-banner"], ' +
                            '[class*="consent-banner"], [id*="cookie-banner"], [id*="consent-banner"], ' +
                            '.cky-consent-container, dialog[open], [role="dialog"][aria-modal="true"]'
                        );
                        let root = banner || document;
                        const uc = document.querySelector('#usercentrics-root, uc-banner');
                        if (uc && uc.shadowRoot) root = uc.shadowRoot;

                        const nodes = Array.from(root.querySelectorAll('button, a[role="button"], div[role="button"], input[type="button"], input[type="submit"]'));
                        return nodes.map(n => {
                            const rect = n.getBoundingClientRect();
                            return {
                                tag: n.tagName.toLowerCase(),
                                text: (n.innerText || n.textContent || n.value || '').trim(),
                                x: rect.left,
                                y: rect.top,
                                width: rect.width,
                                height: rect.height
                            };
                        }).filter(item => item.text.length > 2 && item.text.length < 60 && item.width > 10 && item.height > 10);
                    })()
                    """
                    candidates = await evaluate_fn(page, candidates_script)
                    if candidates and isinstance(candidates, list) and len(candidates) >= 2:
                        chosen = await ai_mgr.resolve_complex_consent(candidates, page_url=getattr(page, "url", ""), model_name=model_name)
                        if chosen and chosen.get("text"):
                            cx = chosen.get("x", 0) + chosen.get("width", 0) / 2.0
                            cy = chosen.get("y", 0) + chosen.get("height", 0) / 2.0
                            if cx > 0 and cy > 0 and hasattr(page, "mouse") and hasattr(page.mouse, "click"):
                                await BiomechanicalMotor.move_mouse_humanoid(page, 200, 200, cx, cy, target_width=chosen.get("width", 40.0))
                                await page.mouse.click(cx, cy)
                                btn_txt = chosen.get('text', '')[:40]
                                logger.info(f"Accepted cookie banner ('{btn_txt}') via AI Container Tactician.")
                                await asyncio.sleep(random.uniform(0.6, 1.2))
                                return True
            except Exception as ai_err:
                logger.debug(f"AI banner resolver note: {ai_err}")

            return False

        except Exception as e:
            logger.debug(f"Semantic banner resolver note: {e}")
            return False

    @classmethod
    async def attach_consent_autowatcher(cls, page: Any, evaluate_fn: Callable) -> bool:
        """
        Injects a persistent, zero-overhead in-page MutationObserver and interval heartbeat into the browser JS engine.
        Continuously detects and dismisses CMP dialogs / consent overlays that load asynchronously
        even after 5-30 seconds without blocking or interrupting Python execution threads.
        """
        try:
            # Also install via add_init_script if page supports it
            if hasattr(page, "add_init_script"):
                try:
                    await page.add_init_script(AUTOWATCHER_SCRIPT)
                except Exception:
                    pass

            await evaluate_fn(page, AUTOWATCHER_SCRIPT)
            return True
        except Exception as e:
            logger.debug(f"Attach consent autowatcher note: {e}")
            return False
