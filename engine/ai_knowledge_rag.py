import os
import json
import re
import math
import logging
from typing import Dict, Any, List, Optional, Tuple, TypedDict

logger = logging.getLogger("AIKnowledgeRAG")


class KnowledgeItem(TypedDict):
    id: str
    title: str
    keywords: List[str]
    content: str


# Curated high-precision domain knowledge snippets for anti-detect, WebGL, WebRTC, TLS, and Playwright
KNOWLEDGE_CORPUS: List[KnowledgeItem] = [
    {
        "id": "tls_ja3_ja4",
        "title": "TLS Fingerprinting (JA3, JA3S, JA4/JA4+)",
        "keywords": ["ja3", "ja4", "tls", "ciphers", "alpn", "sni", "client hello", "fingerprint"],
        "content": (
            "JA4 fingerprinting measures the TLS Client Hello: protocol version (e.g. t13), number of ciphers (2d), "
            "number of extensions (15), ALPN (h2), and signature algorithms hash. "
            "Camoufox uses native C++ TLS stack customization to mimic exact OS/browser ClientHello structures without browser leaks."
        )
    },
    {
        "id": "webgl_os_harmony",
        "title": "WebGL Vendor/Renderer & OS Tensor Alignment",
        "keywords": ["webgl", "renderer", "vendor", "direct3d", "angle", "mesa", "apple", "anomalies", "tensor"],
        "content": (
            "OS Tensor Harmony Rule: Windows requires 'ANGLE (NVIDIA ... Direct3D11)' or 'Intel(R) UHD Graphics Direct3D11'. "
            "Linux must never present Direct3D, D3D11, or Apple GPUs (use 'Mesa ... / OpenGL'). "
            "macOS must exclusively present 'Apple M1/M2/M3' or 'Apple GPU / Intel Iris'."
        )
    },
    {
        "id": "webrtc_ice_protection",
        "title": "WebRTC Native C++ ICE Spoofing & NetNS Egress",
        "keywords": ["webrtc", "ice", "candidate", "leak", "netns", "killswitch", "udp", "stun", "mdns"],
        "content": (
            "WebRTC leakage occurs when STUN/TURN queries bypass proxies over UDP. "
            "SoxBot implements C++ Native ICE candidate protocol spoofing: binding local candidates to the active proxy exit IP, "
            "obfuscating private host IPs with mDNS GUIDs, and enforcing Linux NetNS kernel network namespace egress killswitches."
        )
    },
    {
        "id": "turnstile_cloudflare_evasion",
        "title": "Cloudflare Turnstile & Interactive Challenge Solver",
        "keywords": ["cloudflare", "turnstile", "cf-ray", "captcha", "challenge", "iframe", "managed challenge"],
        "content": (
            "Cloudflare Turnstile checks WebGL draw call timing, minimum-jerk humanoid mouse curve trajectories, "
            "and DOM event fidelity (`isTrusted: true`, `MouseEvent.screenX/screenY` offsets). "
            "Solving requires finding the Turnstile iframe (#cf-turnstile or iframe[src*='challenges.cloudflare']), "
            "moving the mouse with 5th-order polynomial acceleration, and clicking with authentic dwell time (60-120ms)."
        )
    },
    {
        "id": "shadow_dom_playwright",
        "title": "Shadow DOM Traversal & Selector Resiliency in Playwright",
        "keywords": ["shadow dom", "playwright", "shadowroot", "selector", "piercing", "open", "closed"],
        "content": (
            "Playwright natively pierces open Shadow DOMs with standard CSS selectors (e.g. `page.locator('button.consent-btn')`). "
            "For nested closed shadow roots or custom Web Components, evaluate recursive root searches via "
            "`document.querySelectorAll('*')` checking `element.shadowRoot`."
        )
    },
    {
        "id": "biomechanical_mouse_motion",
        "title": "Biomechanical Humanoid Mouse Motion (Minimum-Jerk Law)",
        "keywords": ["mouse", "bezier", "biomechanical", "humanoid", "jerk", "overshoot", "dwell", "fitts"],
        "content": (
            "Human arm movement adheres to Flash & Hogan's Minimum-Jerk optimization: x(t) = x0 + (x1-x0)*(10*(t/T)^3 - 15*(t/T)^4 + 6*(t/T)^5). "
            "It incorporates subtle micro-tremors (10-12 Hz physiological tremor), micro-overshoots (Fitts' Law adjustment), "
            "and velocity profiles bell-curved around the target coordinate."
        )
    }
]


class AIKnowledgeRAG:
    """
    Local Vector Knowledge Store & Retrieval-Augmented Generation (RAG) Engine:
    Performs fast, dense semantic Cosine-Similarity retrieval against persistent SQLite
    anti-detect knowledge snippets with dynamic learning capabilities.
    """

    _instance: Optional['AIKnowledgeRAG'] = None

    def __init__(self):
        from storage.vector_store import SQLiteVectorStore
        self.vector_store = SQLiteVectorStore()
        self._seed_initial_corpus()

    @classmethod
    def get_instance(cls) -> 'AIKnowledgeRAG':
        if cls._instance is None:
            cls._instance = AIKnowledgeRAG()
        return cls._instance

    def _seed_initial_corpus(self):
        """Seeds initial curated knowledge items into the persistent vector database."""
        for item in KNOWLEDGE_CORPUS:
            self.vector_store.insert_document(
                doc_id=item["id"],
                title=item["title"],
                content=item["content"],
                category="anti_detect",
                metadata={"keywords": item.get("keywords", [])}
            )

    def add_knowledge_snippet(self, doc_id: str, title: str, content: str, category: str = "custom", keywords: Optional[List[str]] = None) -> bool:
        """Dynamically adds or updates a knowledge snippet in the vector database."""
        return self.vector_store.insert_document(
            doc_id=doc_id,
            title=title,
            content=content,
            category=category,
            metadata={"keywords": keywords or []}
        )

    def query(self, prompt: Any, top_k: int = 2) -> List[Dict[str, Any]]:
        """Finds the most semantically relevant knowledge snippets for the prompt."""
        if not prompt:
            return []

        if isinstance(prompt, str):
            prompt_str = prompt
        elif isinstance(prompt, list):
            prompt_str = " ".join(str(x) for x in prompt if x is not None)
        elif isinstance(prompt, dict):
            prompt_str = " ".join(str(v) for v in prompt.values() if v is not None)
        else:
            prompt_str = str(prompt)

        p_clean = prompt_str.strip()
        if not p_clean:
            return []

        # Dense Vector Semantic Retrieval
        vector_matches = self.vector_store.query_semantic(p_clean, top_k=top_k, min_similarity=0.25)
        if vector_matches:
            return vector_matches

        # Fallback to in-memory static corpus
        p_lower = p_clean.lower()
        words = set(re.findall(r'\w+', p_lower))
        scored: List[Tuple[float, Dict[str, Any]]] = []

        for item in KNOWLEDGE_CORPUS:
            score = 0.0
            keywords = item.get("keywords", [])
            for kw in keywords:
                kw_str = kw.lower()
                if kw_str in p_lower:
                    score += 3.0
                elif any(w in kw_str for w in words):
                    score += 1.0

            if score > 0.5:
                scored.append((score, dict(item)))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:top_k]]

    def format_rag_context(self, prompt: Any) -> str:
        """Formats retrieved knowledge into structured markdown context for the LLM."""
        matches = self.query(prompt, top_k=2)
        if not matches:
            return ""

        snippets = []
        for m in matches:
            snippets.append(f"### [Knowledge: {m['title']}]\n{m['content']}")

        return (
            "\n\n[LOCAL VERIFIED KNOWLEDGE BASE & ANTI-DETECT SPECS]\n"
            + "\n\n".join(snippets)
            + "\n[END KNOWLEDGE BASE]\n"
        )
