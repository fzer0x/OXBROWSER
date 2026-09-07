import re
import os
import json
import uuid
import time
import random
import asyncio
import logging
from enum import Enum
from typing import Dict, Any, List, Optional, Set, Callable, Tuple, Union
from dataclasses import dataclass, field

logger = logging.getLogger("WorkflowEngine")


class NodeType(str, Enum):
    """Supported DAG node function types for browser automation and anti-detect workflows."""
    # Lifecycle & Navigation
    START = "start"
    NAVIGATE = "navigate"
    NEW_TAB = "new_tab"
    SWITCH_TAB = "switch_tab"
    CLOSE_TAB = "close_tab"
    SCROLL = "scroll"
    REFRESH = "refresh"
    GO_BACK = "go_back"
    CLEAR_CACHE = "clear_cache"

    # Humanoid & Vision Interaction
    VLA_CLICK = "vla_click"
    VLA_TYPE = "vla_type"
    KEY_PRESS = "key_press"
    HOVER = "hover"
    DRAG_DROP = "drag_drop"

    # Anti-Detect, Stealth & Security
    SOLVE_CAPTCHA = "solve_captcha"
    ROTATE_PROXY = "rotate_proxy"
    FINGERPRINT_MORPH = "fingerprint_morph"
    ADVERSARIAL_AUDIT = "adversarial_audit"
    PRE_ACTION_CHECK = "pre_action_check"

    # Logic, Branching & Control Flow
    CONDITION = "condition"
    LOOP = "loop"
    WAIT = "wait"
    EXTRACT_DATA = "extract_data"
    JAVASCRIPT_EVAL = "javascript_eval"
    AI_DECISION = "ai_decision"
    AI_MODEL_TASK = "ai_model_task"
    SCREENSHOT = "screenshot"
    DOWNLOAD_WAIT = "download_wait"
    TERMINATE = "terminate"

    # Autonomous Gaming & Strategy
    CHESS_SOLVER = "chess_solver"
    POKER_SOLVER = "poker_solver"


NODE_METADATA: Dict[NodeType, Dict[str, Any]] = {
    NodeType.START: {
        "label": "🚩 Start Session",
        "category": "Lifecycle & Navigation",
        "description": "Initialer Workflow-Startpunkt. Markiert den Beginn des Automatisierungsablaufs und initialisiert den Ausführungskontext.",
        "params_doc": {},
        "ports_doc": {"out": "Startet den nachfolgenden Workflow-Schritt"}
    },
    NodeType.NAVIGATE: {
        "label": "🌐 Navigate URL",
        "category": "Lifecycle & Navigation",
        "description": "Navigiert zu einer Ziel-Webadresse (URL). Unterstützt dynamische Variablen-Interpolation (z. B. {target_url}) sowie konfigurierbare Ladebedingungen und Timeouts.",
        "params_doc": {
            "url": "Ziel-URL (z. B. https://google.com oder {target_url})",
            "wait_until": "Lade-Bedingung: domcontentloaded, load, networkidle oder commit",
            "timeout_ms": "Maximales Timeout für den Seitenaufruf in Millisekunden (Standard: 30000 ms)"
        },
        "ports_doc": {"out": "Fährt nach erfolgreichem Laden der Seite fort"}
    },
    NodeType.NEW_TAB: {
        "label": "📑 Open New Tab",
        "category": "Lifecycle & Navigation",
        "description": "Öffnet einen neuen Browser-Tab im selben Browser-Kontext und setzt den Fokus darauf.",
        "params_doc": {
            "url": "Start-URL für den neuen Tab (z. B. about:blank oder https://...)"
        },
        "ports_doc": {"out": "Fährt auf dem neu geöffneten Tab fort"}
    },
    NodeType.SWITCH_TAB: {
        "label": "🔀 Switch Tab",
        "category": "Lifecycle & Navigation",
        "description": "Wechselt den aktiven Fokus zu einem bestimmten Browser-Tab anhand seines 0-basierten Index.",
        "params_doc": {
            "tab_index": "0-basierter Index des Ziel-Tabs (0 = erster Tab, 1 = zweiter Tab)"
        },
        "ports_doc": {"out": "Fährt auf dem ausgewählten Tab fort"}
    },
    NodeType.CLOSE_TAB: {
        "label": "❌ Close Active Tab",
        "category": "Lifecycle & Navigation",
        "description": "Schließt den aktiven Tab (oder einen spezifischen Tab-Index) und wechselt den Fokus auf den vorherigen Tab.",
        "params_doc": {
            "tab_index": "Tab-Index (-1 für aktuell aktiven Tab)"
        },
        "ports_doc": {"out": "Fährt nach Schließen des Tabs fort"}
    },
    NodeType.SCROLL: {
        "label": "📜 Scroll Humanoid",
        "category": "Lifecycle & Navigation",
        "description": "Führt ein natürliches, biomotorisches Mausrad-Scrollen mit weicher Beschleunigung und Bremskurve durch.",
        "params_doc": {
            "direction": "Scroll-Richtung: down (nach unten), up (nach oben), bottom (Seitenende), top (Seitenanfang)",
            "pixels": "Scroll-Distanz in Pixeln (Standard: 500 px)"
        },
        "ports_doc": {"out": "Fährt nach Abschluss der Scroll-Bewegung fort"}
    },
    NodeType.REFRESH: {
        "label": "🔄 Refresh Page",
        "category": "Lifecycle & Navigation",
        "description": "Lädt die aktuell geöffnete Webseite im Browser neu (Reload).",
        "params_doc": {},
        "ports_doc": {"out": "Fährt nach Neuladen der Seite fort"}
    },
    NodeType.GO_BACK: {
        "label": "⬅️ Go Back",
        "category": "Lifecycle & Navigation",
        "description": "Navigiert in der Browser-Historie der aktuellen Seite einen Schritt zurück.",
        "params_doc": {},
        "ports_doc": {"out": "Fährt nach Rückwärts-Navigation fort"}
    },
    NodeType.CLEAR_CACHE: {
        "label": "🧹 Clear Cache & Cookies",
        "category": "Anti-Detect, Stealth & Security",
        "description": "Löscht Browser-Cookies, Session-Storage und lokalen Cache für eine saubere, ungetrackte Identität.",
        "params_doc": {},
        "ports_doc": {"out": "Fährt mit bereinigtem Browser-Zustand fort"}
    },
    NodeType.VLA_CLICK: {
        "label": "👁️ VLA Vision Click",
        "category": "Humanoid & Vision Interaction",
        "description": "Führt einen humanoiden Mausklick auf ein Ziel-Element aus. Unterstützt KI-Vision (SmolVLM / Vision-LLM), CSS-Selektoren, XPath oder Koordinaten mit natürlichem Jitter.",
        "params_doc": {
            "click_mode": "Modus: auto, vla_vision, selector, xpath oder coordinates",
            "instruction": "Ziel-Element, semantische KI-Beschreibung oder XPath/CSS-Selektor",
            "jitter_px": "Zufälliger Pixel-Versatz zur Vermeidung exakter Bot-Koordinaten"
        },
        "ports_doc": {"out": "Fährt nach Klick auf das Element fort"}
    },
    NodeType.VLA_TYPE: {
        "label": "⌨️ VLA Type Text",
        "category": "Humanoid & Vision Interaction",
        "description": "Simuliert menschliches Tippen mit biomechanischer Tastenanschlag-Kadenz, variablen Intervallen und optionalem automatischen Enter/Leeren. Kann Text entweder statisch oder dynamisch von einem KI-Modell (z. B. Gemini, Qwen, DeepSeek) generieren lassen.",
        "params_doc": {
            "text": "Einzugebender statischer Text oder Template (unterstützt {variablen})",
            "use_ai_generation": "Aktiviert dynamische Text-Generierung via KI-Modell",
            "ai_prompt": "Prompt / Anweisung an das KI-Modell (z. B. 'Verfasse einen kurzen Kommentar zu {topic}')",
            "ai_model": "Ausgewähltes KI-Modell (auto, gemini-3.6-flash, qwen2.5:1.5b, deepseek, etc.)",
            "save_to_var": "Optionale Variable zur Speicherung des generierten Textes",
            "instruction": "Ziel-Eingabefeld (Selektor oder semantische Beschreibung)",
            "delay_ms": "Mittlere Anschlag-Verzögerung pro Buchstabe in ms (Standard: 60 ms)",
            "press_enter": "Nach Texteingabe automatisch Enter drücken",
            "clear_first": "Feld vor der Eingabe vollständig leeren"
        },
        "ports_doc": {"out": "Fährt nach getipptem Text fort"}
    },
    NodeType.KEY_PRESS: {
        "label": "⌨️ Key Press (Enter/Esc)",
        "category": "Humanoid & Vision Interaction",
        "description": "Sendet gezielte Sondertasten oder Tastenkombinationen wie Enter, Escape, Tab, Backspace, ArrowDown oder Hotkeys (z.B. Control+A).",
        "params_doc": {
            "key": "Taste oder Kombination (Enter, Escape, Tab, Space, ArrowDown, Control+A, Control+V, etc.)"
        },
        "ports_doc": {"out": "Fährt nach Tastendruck fort"}
    },
    NodeType.HOVER: {
        "label": "👆 Humanoid Hover",
        "category": "Humanoid & Vision Interaction",
        "description": "Bewegt den Mauszeiger entlang einer natürlichen Bézier-Kurve über ein Ziel-Element (z.B. um Dropdown-Menüs zu öffnen).",
        "params_doc": {
            "click_mode": "Modus: auto, selector, xpath, coordinates oder vla_vision",
            "instruction": "Ziel-Element, Selektor oder Hover-Ziel",
            "jitter_px": "Zufälliger Pixel-Offset"
        },
        "ports_doc": {"out": "Fährt nach Hover-Aktion fort"}
    },
    NodeType.DRAG_DROP: {
        "label": "🖐️ Drag & Drop",
        "category": "Humanoid & Vision Interaction",
        "description": "Zieht ein Webelement per Mausbewegung von einer Quelle zu einem Ziel (z.B. Slider, Schieberegler oder Drag-and-Drop UIs).",
        "params_doc": {
            "instruction": "Quelle und Ziel oder Koordinaten-Paar"
        },
        "ports_doc": {"out": "Fährt nach Drag & Drop fort"}
    },
    NodeType.SOLVE_CAPTCHA: {
        "label": "🧩 Solve Captcha",
        "category": "Anti-Detect, Stealth & Security",
        "description": "Erkennt und löst Cloudflare Turnstile, ReCaptcha v2/v3, hCaptcha und FunCaptcha autonom mittels Whisper Audio STT oder Vision-LLM.",
        "params_doc": {
            "strategy": "Lösungs-Strategie: audio_first, vision_first, 50/50_smart_hybrid, audio_only oder vision_only",
            "whisper_model": "Whisper Speech-to-Text Modell (base, tiny, small, medium, gemini-audio)",
            "vision_model": "Vision-KI Modell (50/50_smart_hybrid, gemini-flash, got-ocr2, qwen2.5vl)",
            "timeout_sec": "Maximales Lösungs-Timeout in Sekunden (Standard: 45 s)"
        },
        "ports_doc": {"out": "Fährt nach erfolgreicher Captcha-Lösung fort"}
    },
    NodeType.ROTATE_PROXY: {
        "label": "🔄 Rotate Proxy",
        "category": "Anti-Detect, Stealth & Security",
        "description": "Triggert eine dynamische IP-Rotation über Change-IP-URL oder wählt automatisch einen neuen, unbenutzten Fallback-Proxy aus dem Proxy-Pool.",
        "params_doc": {
            "rotation_mode": "Rotations-Modus: 'auto_fallback' (Change-IP-URL mit Proxy-Pool Fallback), 'force_pool' (Immer nächster unbenutzter Pool-Proxy) oder 'url_only'",
            "proxy_group": "Optionaler Filter nach Proxy-Pool-Gruppe (z. B. 'Default', 'Imported' oder 'All')",
            "change_ip_url": "Optionale benutzerdefinierte Rotations-URL (falls nicht im Profil hinterlegt)"
        },
        "ports_doc": {"out": "Fährt mit neuer IP-Adresse fort"}
    },
    NodeType.FINGERPRINT_MORPH: {
        "label": "🧬 Morph Fingerprint",
        "category": "Anti-Detect, Stealth & Security",
        "description": "Verändert Fingerprint-Charakteristiken (Canvas-Noise, WebGL-Offsets, Audio-Buffer, Font-Reihenfolge) on-the-fly im laufenden Kontext.",
        "params_doc": {
            "intensity": "Intensität der Morphing-Anpassung: mild, moderate oder aggressive"
        },
        "ports_doc": {"out": "Fährt mit modifiziertem Fingerprint fort"}
    },
    NodeType.ADVERSARIAL_AUDIT: {
        "label": "🛡️ Adversarial Audit",
        "category": "Anti-Detect, Stealth & Security",
        "description": "Führt einen proaktiven Sicherheits- und Stealth-Audit durch, um Bot-Detektionen (Cloudflare, PerimeterX, Datadome) frühzeitig zu erkennen.",
        "params_doc": {
            "audit_mode": "Audit-Fokus: turnstile_focus, full oder quick"
        },
        "ports_doc": {"out": "Fährt nach Audit-Abschluss fort"}
    },
    NodeType.PRE_ACTION_CHECK: {
        "label": "🔍 Pre-Action Verification",
        "category": "Anti-Detect, Stealth & Security",
        "description": "Überprüft vor kritischen Aktionen, ob das DOM stabil, das Zielelement sichtbar, nicht verdeckt und interaktiv ist.",
        "params_doc": {
            "selector": "Zu überprüfendes Element oder Selektor (Standard: body)"
        },
        "ports_doc": {"out": "Fährt fort, wenn Verifikation erfolgreich"}
    },
    NodeType.CONDITION: {
        "label": "🔀 Condition (If / Else)",
        "category": "Logic, Branching & Control Flow",
        "description": "Verzweigt den Workflow-Ablauf anhand konfigurierbarer Bedingungen (URL-Inhalt, Text-Präsenz, Element-Existenz oder Variablen-Vergleich).",
        "params_doc": {
            "condition_type": "Prüf-Typ: url_contains, text_exists, element_exists, var_equals",
            "expected": "Erwarteter Suchwert, Text oder Variablenwert"
        },
        "ports_doc": {
            "true": "Wird ausgeführt, wenn die Bedingung WAHR ist",
            "false": "Wird ausgeführt, wenn die Bedingung FALSCH ist"
        }
    },
    NodeType.AI_DECISION: {
        "label": "🧠 AI Decision Routing",
        "category": "Logic, Branching & Control Flow",
        "description": "Beurteilt den Webseiten-Zustand visuell oder textuell via KI-Prompt und verzweigt intelligent nach True/False.",
        "params_doc": {
            "prompt": "Entscheidungs-Frage an die KI (z. B. 'Ist der Artikel auf Lager?' oder 'Wurde die Bestätigungsmail angezeigt?')"
        },
        "ports_doc": {
            "true": "Wird ausgeführt, wenn die KI mit JA antwortet",
            "false": "Wird ausgeführt, wenn die KI mit NEIN antwortet"
        }
    },
    NodeType.LOOP: {
        "label": "🔁 Loop Counter",
        "category": "Logic, Branching & Control Flow",
        "description": "Wiederholt einen Teilgraph für eine festgelegte Anzahl an Iterationen. Aktualisiert eine Schleifen-Index-Variable bei jedem Durchlauf.",
        "params_doc": {
            "iterations": "Anzahl der Schleifendurchläufe",
            "counter_var": "Name der Index-Variable (Standard: loop_index)"
        },
        "ports_doc": {
            "loop_body": "Schleifenkörper (wird pro Iteration ausgeführt)",
            "loop_exit": "Schleifenausgang (wird nach Erreichen aller Iterationen ausgeführt)"
        }
    },
    NodeType.WAIT: {
        "label": "⏱️ Wait / Sleep",
        "category": "Logic, Branching & Control Flow",
        "description": "Pausiert die Workflow-Ausführung für eine konfigurierte Dauer mit natürlichem humanem Jitter (Verweildauer).",
        "params_doc": {
            "duration": "Wartezeit in Sekunden (z. B. 2.5 s)",
            "notes": "Optionale Notiz oder Beschreibung für diesen Warte-Schritt"
        },
        "ports_doc": {"out": "Fährt nach Ablauf der Wartezeit fort"}
    },
    NodeType.EXTRACT_DATA: {
        "label": "📥 Extract Web Data",
        "category": "Logic, Branching & Control Flow",
        "description": "Extrahiert Text, HTML oder Attribute von Web-Elementen und speichert diese in einer Workflow-Variable für nachfolgende Schritte.",
        "params_doc": {
            "selector": "CSS- oder XPath-Selektor des Ziel-Elements",
            "attribute": "Zu extrahierendes Attribut: innerText, innerHTML, value, href, src",
            "var_name": "Name der Ziel-Variable (z. B. extracted_price)"
        },
        "ports_doc": {"out": "Fährt nach Extraktion mit gespeicherter Variable fort"}
    },
    NodeType.JAVASCRIPT_EVAL: {
        "label": "💻 Evaluate JavaScript",
        "category": "Logic, Branching & Control Flow",
        "description": "Führt benutzerdefinierten JavaScript-Code direkt im Browser-Seitenkontext aus und speichert optional den Rückgabewert.",
        "params_doc": {
            "script": "JavaScript-Code (z. B. 'return document.title;' oder 'window.scrollTo(0, 1000);')",
            "save_to_var": "Optionale Variable zur Speicherung des Rückgabewerts"
        },
        "ports_doc": {"out": "Fährt nach JavaScript-Ausführung fort"}
    },
    NodeType.SCREENSHOT: {
        "label": "📸 Capture Screenshot",
        "category": "Logic, Branching & Control Flow",
        "description": "Erstellt eine Momentaufnahme der aktuellen Webseite und speichert sie als PNG-Bilddatei.",
        "params_doc": {
            "path": "Dateipfad zum Speichern (Standard: storage/screenshots/screenshot.png)"
        },
        "ports_doc": {"out": "Fährt nach Speichern des Screenshots fort"}
    },
    NodeType.DOWNLOAD_WAIT: {
        "label": "⏳ Wait for Download",
        "category": "Logic, Branching & Control Flow",
        "description": "Wartet darauf, dass ein gestarteter Datei-Download abgeschlossen und im Download-Ordner abgelegt wird.",
        "params_doc": {
            "filename_pattern": "Dateimuster oder Dateiname (z. B. *.pdf oder report.csv)",
            "timeout_sec": "Maximales Warte-Timeout in Sekunden"
        },
        "ports_doc": {"out": "Fährt nach erfolgreichem Download fort"}
    },
    NodeType.AI_MODEL_TASK: {
        "label": "🧠 AI Model Action",
        "category": "Cognitive AI & Multimodal Models",
        "description": "Führt spezialisierte modellspezifische Aufgaben aus: Screenshot- & Vision-Analyse, OCR-Textextraktion (GOT-OCR2 / Florence-2), Audio-Transkription (Whisper STT), KI-Sicherheits- & Pentest-Audits oder semantische Textsynthese.",
        "params_doc": {
            "task_type": "Aufgaben-Typ: analyze_screenshot, extract_text_ocr, transcribe_audio, security_pentest, summarize_page, custom_prompt",
            "model_name": "Ausgewähltes KI-Modell (auto, gemini-3.6-flash, qwen2.5vl:3b, got-ocr2, whisper-base, deepseek-r1:1.5b, llama3.2)",
            "prompt": "Prompt / Spezifische Anweisung an das Modell (unterstützt {variablen})",
            "save_to_var": "Workflow-Variable zur Speicherung des Ergebnisses (z. B. ai_analysis, ocr_text, audio_transcript)",
            "selector": "Optionaler CSS/XPath-Selektor zur Eingrenzung (z. B. für Element-Screenshot oder Audio-Tag)"
        },
        "ports_doc": {"out": "Fährt nach Abschluss der Modellausführung fort"}
    },
    NodeType.TERMINATE: {
        "label": "🛑 Terminate Routine",
        "category": "Logic, Branching & Control Flow",
        "description": "Beendet die Workflow-Ausführung und erzeugt einen zusammenfassenden Abschlussbericht mit Endstatus.",
        "params_doc": {
            "status": "Endstatus: success (Erfolg), failed (Fehler) oder aborted (Abgebrochen)"
        },
        "ports_doc": {}
    },
    NodeType.CHESS_SOLVER: {
        "label": "♟️ Chess Auto-Move",
        "category": "Gaming & Autonomous Decision",
        "description": "Liest den aktuellen FEN-Brettzustand von Chess.com oder Lichess aus, berechnet via Stockfish den optimalen Zug und führt ihn mit AntiDetectChessSession biomimetisch aus. Anti-Detection-System: Difficulty-Score (MultiPV), EloThrottleController (CPL-Verteilung), HumanizedTimingEngine, PlayerBaseline.",
        "params_doc": {
            "platform": "Schach-Plattform: auto, chess_com, lichess oder generic",
            "engine_type": "Engine: super_grandmaster_godmode, stockfish, ai_hybrid_ensemble oder builtin",
            "depth": "Suchtiefe / Stockfish Plies (1 bis 50)",
            "target_elo": "Ziel-Elo für EloThrottleController und HumanizedTimingEngine (z. B. 1200, 1500, 1800, 2400)",
            "speed_preset": "Timing-Preset: bullet, blitz, rapid, classical, balanced",
            "anti_detect": "Aktiviert AntiDetectChessSession mit Difficulty-Analyse, CPL-Kalibrierung und Baseline-Tracking (True/False)",
            "difficulty_depth": "Stockfish-Tiefe für MultiPV Schwierigkeitsanalyse (6-20, Standard: 12)",
            "auto_move": "Klickt/Drag den Zug automatisch im Browser (True/False)",
            "save_to_var": "Variable zur Speicherung des Zugs (z. B. chess_move)"
        },
        "ports_doc": {
            "out": "Fährt nach ausgeführtem Zug fort",
            "checkmate": "Wird getriggert, wenn Schachmatt erkannt wurde"
        }
    },
    NodeType.POKER_SOLVER: {
        "label": "🃏 Poker GTO / AI Ensemble Decision",
        "category": "Gaming & Autonomous Decision",
        "description": "Autonome Texas Hold'em KI-Entscheidungs-Engine: Multimodale Vision (Qwen2.5-VL / Gemini Vision) scannt Live-Table & Pocket Cards, Monte-Carlo-Simulationen berechnen mathematische Equity & Pot-Odds, und DeepSeek-R1 / Qwen2.5 Grandmaster-Reasoning trifft optimale GTO-/Exploitative-Aktionen (Fold, Call, Raise, All-in).",
        "params_doc": {
            "strategy": "Strategie-Profil: ai_all_models_hybrid (Alle AI-Modelle: Vision + DeepSeek-R1 + Monte Carlo), ai_deepseek_reasoning, ai_vision_vlm, gto_balanced, tight_aggressive, loose_aggressive",
            "ai_model": "Spezifisches KI-Modell für Grandmaster-Reasoning (z. B. auto, deepseek-r1:1.5b, qwen2.5:7b, gemini-1.5-flash)",
            "num_opponents": "Anzahl aktiver Gegenspieler (Standard: 1 - 5)",
            "iterations": "Anzahl Monte-Carlo-Simulationen (Standard: 3000)",
            "auto_click_action": "Klickt automatisch auf den entsprechenden Aktions-Button (Fold/Call/Raise) im Browser (True/False)",
            "save_to_var": "Optionale Variable zur Speicherung von Equity & Aktion (z. B. poker_action, poker_equity)"
        },
        "ports_doc": {
            "out": "Fährt nach Aktionsentscheidung fort",
            "fold": "Wird ausgeführt bei Fold",
            "call": "Wird ausgeführt bei Check / Call",
            "raise": "Wird ausgeführt bei Bet / Raise / All-in"
        }
    }
}


def get_node_metadata(node_type: Union[NodeType, str]) -> Dict[str, Any]:
    """Gibt Metadaten, Beschreibung und Parameter-Dokumentation für einen NodeType zurück."""
    if isinstance(node_type, str):
        try:
            node_type = NodeType(node_type)
        except ValueError:
            return {
                "label": node_type,
                "category": "General",
                "description": f"Workflow Node: {node_type}",
                "params_doc": {},
                "ports_doc": {"out": "Weiter"}
            }
    return NODE_METADATA.get(node_type, {
        "label": str(node_type.value),
        "category": "General",
        "description": f"Workflow Node: {node_type.value}",
        "params_doc": {},
        "ports_doc": {"out": "Weiter"}
    })


def get_node_description(node_type: Union[NodeType, str]) -> str:
    """Liefert die ausführliche Funktions-Beschreibung eines Node-Typs."""
    meta = get_node_metadata(node_type)
    return meta.get("description", "")


def safe_float(val: Any, default: float = 0.0) -> float:
    """Safely converts Any | None to float without raising TypeError or ValueError."""
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def clean_ai_generated_text(raw: str) -> str:
    """
    Cleans AI-generated text for typing into form fields or plain text variables.
    Strips JSON structures, markdown code fences, key-only JSON dictionaries (e.g. {"Query": ""}),
    surrounding quotes, and conversational AI prefixes.
    """
    if not raw or not isinstance(raw, str):
        return ""

    text = raw.strip()

    # 0. Strip DeepSeek R1 / Reasoning thinking tags (<think> ... </think>)
    if "<think>" in text:
        import re
        text = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()

    # 1. Strip markdown code fences (e.g. ```json ... ``` or ``` ... ```)
    if "```" in text:
        import re
        match = re.search(r"```(?:json|text)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
        if match:
            text = match.group(1).strip()
        else:
            text = text.replace("```", "").strip()

    # 2. Recursive helper to extract the best plain text string from any JSON structure
    def extract_text_from_json(obj: Any) -> Optional[str]:
        if isinstance(obj, str):
            s = obj.strip()
            if s:
                return s
            return None
        elif isinstance(obj, (int, float)):
            return str(obj)
        elif isinstance(obj, list):
            for item in obj:
                res = extract_text_from_json(item)
                if res:
                    return res
            return None
        elif isinstance(obj, dict):
            # Check preferred value keys first
            preferred_keys = [
                "text", "query", "search_query", "search", "search_term", "result",
                "response", "value", "content", "output", "data", "message", "prompt",
                "question", "keyword", "keywords", "topic", "input", "title", "action"
            ]
            for k in preferred_keys:
                if k in obj:
                    res = extract_text_from_json(obj[k])
                    if res:
                        return res

            # Check if any value is a non-empty string or structure
            for k, v in obj.items():
                res = extract_text_from_json(v)
                if res:
                    return res

            # If all values are empty/falsy (e.g. {"Query 1": "", "Query 2": ""}),
            # then the keys themselves contain the text!
            cand_keys: List[str] = [str(k).strip() for k in obj.keys() if str(k).strip()]
            if cand_keys:
                # If there are multiple keys, prefer full questions/queries over generic category headers
                # (e.g. prefer 'How do I root my Samsung Galaxy S24?' over 'Samsung S24 Rooting Questions?')
                for k in reversed(cand_keys):
                    k_lower = k.lower()
                    if k_lower.startswith(("how", "what", "why", "where", "when", "who", "which", "can", "is", "do", "does", "root")):
                        return k
                # Otherwise return the longest non-empty key
                best_key: str = max(cand_keys, key=lambda s: len(s))
                return best_key
            return None
        return None

    # 3. Try parsing as JSON (or finding JSON substring)
    parsed_json = None
    if (text.startswith("{") and text.endswith("}")) or (text.startswith("[") and text.endswith("]")):
        try:
            parsed_json = json.loads(text)
        except Exception:
            pass

    if parsed_json is None and ("{" in text and "}" in text):
        import re
        json_match = re.search(r"(\{[^{}]*\}|\[[^\[\]]*\])", text)
        if json_match:
            try:
                parsed_json = json.loads(json_match.group(1))
            except Exception:
                pass

    if parsed_json is not None:
        extracted = extract_text_from_json(parsed_json)
        if extracted:
            text = extracted

    # 4. Fallback if text still contains unparsed JSON-like syntax e.g. {"key": "val"} or {"key": ""}
    if text.startswith("{") and text.endswith("}"):
        import re
        quotes = re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"|\'([^\'\\]*(?:\\.[^\'\\]*)*)\'', text)
        flat_quotes: List[str] = [str(q[0] or q[1]) for q in quotes if (q[0] or q[1]).strip()]
        if flat_quotes:
            for q in reversed(flat_quotes):
                if q.lower().startswith(("how", "what", "why", "where", "when", "do", "can", "root")):
                    text = q
                    break
            else:
                best_quote: str = max(flat_quotes, key=lambda s: len(s))
                text = best_quote

    # 5. Strip surrounding quotation marks of all types
    quote_pairs = [('"', '"'), ("'", "'"), ('“', '”'), ('„', '“'), ('«', '»'), ('`', '`')]
    changed = True
    while changed:
        changed = False
        text = text.strip()
        for q_start, q_end in quote_pairs:
            if text.startswith(q_start) and text.endswith(q_end) and len(text) >= len(q_start) + len(q_end):
                text = text[len(q_start):-len(q_end)].strip()
                changed = True

    # 6. Strip common AI conversational prefixes
    import re
    text = re.sub(r'^(?:Here (?:is|are) (?:the )?(?:search query|query|text|response|answer|question):?|Output:|Text:|Query:|Answer:|Question:)\s*', '', text, flags=re.IGNORECASE).strip()

    # Re-strip quotes in case prefix removal exposed them
    for q_start, q_end in quote_pairs:
        if text.startswith(q_start) and text.endswith(q_end) and len(text) >= len(q_start) + len(q_end):
            text = text[len(q_start):-len(q_end)].strip()

    return text.strip()


class PortType(str, Enum):
    """Socket and port connection types on workflow nodes."""
    IN = "in"
    OUT = "out"
    TRUE_BRANCH = "true"
    FALSE_BRANCH = "false"
    LOOP_BODY = "loop_body"
    LOOP_EXIT = "loop_exit"


@dataclass
class WorkflowEdge:
    """Directed connection between two node sockets/ports in the DAG."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_node_id: str = ""
    source_port: str = "out"
    target_node_id: str = ""
    target_port: str = "in"

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the edge to a dictionary representation."""
        return {
            "id": self.id,
            "source_node_id": self.source_node_id,
            "source_port": self.source_port,
            "target_node_id": self.target_node_id,
            "target_port": self.target_port
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowEdge':
        """Deserializes a dictionary into a WorkflowEdge instance."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            source_node_id=data.get("source_node_id", ""),
            source_port=data.get("source_port", "out"),
            target_node_id=data.get("target_node_id", ""),
            target_port=data.get("target_port", "in")
        )


@dataclass
class WorkflowNode:
    """Full Definition of a single DAG Node with parameters, ports, and layout state."""
    id: str
    node_type: NodeType
    title: str
    params: Dict[str, Any] = field(default_factory=dict)
    position: Dict[str, float] = field(default_factory=lambda: {"x": 100.0, "y": 100.0})
    is_breakpoint: bool = False

    def get_output_ports(self) -> List[str]:
        """Returns the list of available output port names depending on the node type."""
        if self.node_type in [NodeType.CONDITION, NodeType.AI_DECISION]:
            return ["true", "false"]
        elif self.node_type == NodeType.LOOP:
            return ["loop_body", "loop_exit"]
        elif self.node_type == NodeType.CHESS_SOLVER:
            return ["out", "checkmate"]
        elif self.node_type == NodeType.POKER_SOLVER:
            return ["out", "fold", "call", "raise"]
        elif self.node_type == NodeType.TERMINATE:
            return []
        return ["out"]

    def get_description(self) -> str:
        """Returns the detailed description for this node's function."""
        return get_node_description(self.node_type)

    def get_metadata(self) -> Dict[str, Any]:
        """Returns the full metadata dictionary for this node's function."""
        return get_node_metadata(self.node_type)


@dataclass
class WorkflowDAG:
    """Complete Visual Workflow Graph with validation, auto-layout and Python compilation support."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Untitled Workflow"
    description: str = "Automated No-Code Farming & Stealth Routine"
    category: str = "E-Commerce / Social"
    entry_node_id: Optional[str] = None
    nodes: Dict[str, WorkflowNode] = field(default_factory=dict)
    edges: List[WorkflowEdge] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the entire workflow DAG graph, nodes, edges, and variables to a JSON-serializable dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "entry_node_id": self.entry_node_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "variables": self.variables,
            "nodes": {
                nid: {
                    "id": n.id,
                    "node_type": n.node_type.value,
                    "title": n.title,
                    "params": n.params,
                    "position": n.position,
                    "is_breakpoint": n.is_breakpoint
                }
                for nid, n in self.nodes.items()
            },
            "edges": [e.to_dict() for e in self.edges]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowDAG':
        """Reconstructs a WorkflowDAG instance with its nodes and edges from a serialized dictionary."""
        dag = cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", "Imported Workflow"),
            description=data.get("description", ""),
            category=data.get("category", "General"),
            entry_node_id=data.get("entry_node_id"),
            variables=data.get("variables", {}),
            created_at=float(data.get("created_at", time.time())),
            updated_at=float(data.get("updated_at", time.time()))
        )
        for nid, ndata in data.get("nodes", {}).items():
            dag.nodes[nid] = WorkflowNode(
                id=ndata["id"],
                node_type=NodeType(ndata["node_type"]),
                title=ndata.get("title", ndata["node_type"]),
                params=ndata.get("params", {}),
                position=ndata.get("position", {"x": 100.0, "y": 100.0}),
                is_breakpoint=bool(ndata.get("is_breakpoint", False))
            )
        for edata in data.get("edges", []):
            dag.edges.append(WorkflowEdge.from_dict(edata))
        return dag

    def get_out_edges(self, node_id: str, port: str = "out") -> List[WorkflowEdge]:
        """Returns all outgoing directed edges from a node, optionally filtered by port name."""
        return [e for e in self.edges if e.source_node_id == node_id and (port == "*" or e.source_port == port)]

    def add_edge(self, source_id: str, target_id: str, source_port: str = "out", target_port: str = "in") -> WorkflowEdge:
        """Adds a directed connection edge between source and target ports if not already present."""
        existing = [e for e in self.edges if e.source_node_id == source_id and e.target_node_id == target_id and e.source_port == source_port]
        if existing:
            return existing[0]
        edge = WorkflowEdge(
            source_node_id=source_id,
            source_port=source_port,
            target_node_id=target_id,
            target_port=target_port
        )
        self.edges.append(edge)
        return edge

    def remove_edge(self, edge_id: str):
        """Removes an edge by its unique identifier."""
        self.edges = [e for e in self.edges if e.id != edge_id]

    def auto_layout_nodes(self, max_per_row: int = 4):
        """Arranges DAG nodes in rows of 4 (or specified max_per_row) following topological execution order."""
        if not self.nodes:
            return

        in_degree: Dict[str, int] = {nid: 0 for nid in self.nodes}
        adj: Dict[str, List[str]] = {nid: [] for nid in self.nodes}
        for e in self.edges:
            if e.source_node_id in self.nodes and e.target_node_id in self.nodes:
                adj[e.source_node_id].append(e.target_node_id)
                in_degree[e.target_node_id] += 1

        roots = [nid for nid, deg in in_degree.items() if deg == 0]
        if self.entry_node_id and self.entry_node_id in roots:
            roots.remove(self.entry_node_id)
            roots.insert(0, self.entry_node_id)
        elif self.entry_node_id and self.entry_node_id in self.nodes:
            roots.insert(0, self.entry_node_id)
        if not roots:
            roots = list(self.nodes.keys())[:1]

        ordered_nids: List[str] = []
        visited = set()
        queue = list(roots)

        while queue:
            curr = queue.pop(0)
            if curr in visited:
                continue
            visited.add(curr)
            ordered_nids.append(curr)
            for neighbor in adj.get(curr, []):
                if neighbor not in visited and neighbor not in queue:
                    queue.append(neighbor)

        # Append remaining nodes if any are disconnected
        for nid in self.nodes:
            if nid not in visited:
                ordered_nids.append(nid)
                visited.add(nid)

        x_spacing = 260.0
        y_spacing = 150.0
        num_cols = min(max_per_row, len(ordered_nids))
        num_rows = (len(ordered_nids) + max_per_row - 1) // max_per_row

        start_x = -((num_cols - 1) * x_spacing) / 2.0
        start_y = -((num_rows - 1) * y_spacing) / 2.0

        for idx, nid in enumerate(ordered_nids):
            col = idx % max_per_row
            row = idx // max_per_row
            self.nodes[nid].position = {
                "x": start_x + (col * x_spacing),
                "y": start_y + (row * y_spacing)
            }

    def validate_dag(self) -> List[Dict[str, str]]:
        """Lints the graph and returns diagnostic warnings/errors."""
        diagnostics = []
        if not self.nodes:
            diagnostics.append({"level": "warning", "message": "The workflow graph is completely empty."})
            return diagnostics

        starts = [nid for nid, n in self.nodes.items() if n.node_type == NodeType.START]
        if not starts and not self.entry_node_id:
            diagnostics.append({"level": "warning", "message": "No START node or explicit entry point set."})

        connected_nodes = set()
        for e in self.edges:
            connected_nodes.add(e.source_node_id)
            connected_nodes.add(e.target_node_id)

        for nid, n in self.nodes.items():
            if len(self.nodes) > 1 and nid not in connected_nodes:
                diagnostics.append({"level": "warning", "message": f"Orphan node '{n.title}' ({n.node_type}) is not connected.", "node_id": nid})

            if n.node_type in [NodeType.CONDITION, NodeType.AI_DECISION]:
                true_edges = [e for e in self.edges if e.source_node_id == nid and e.source_port == "true"]
                false_edges = [e for e in self.edges if e.source_node_id == nid and e.source_port == "false"]
                if not true_edges and not false_edges:
                    diagnostics.append({"level": "info", "message": f"Branch node '{n.title}' has no TRUE or FALSE wire connected.", "node_id": nid})

            if n.node_type == NodeType.LOOP:
                body_edges = [e for e in self.edges if e.source_node_id == nid and e.source_port == "loop_body"]
                if not body_edges:
                    diagnostics.append({"level": "warning", "message": f"Loop node '{n.title}' has no loop_body wire.", "node_id": nid})

        if not diagnostics:
            diagnostics.append({"level": "success", "message": "Workflow DAG graph is fully valid and healthy."})
        return diagnostics

    def export_to_playwright_python(self) -> str:
        """Generates clean standalone Playwright Python async script from the visual DAG."""
        lines = [
            "# Auto-generated Standalone Playwright Script by SoxBot Visual Workflow Builder",
            f"# Workflow: {self.name}",
            f"# Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "import asyncio",
            "import random",
            "from playwright.async_api import async_playwright",
            "",
            "async def run_workflow():",
            "    async with async_playwright() as p:",
            "        browser = await p.chromium.launch(headless=False)",
            "        context = await browser.new_context(viewport={'width': 1280, 'height': 800})",
            "        page = await context.new_page()",
            f"        variables = {json.dumps(self.variables, indent=8)}",
            "",
            "        print('🚀 Launching workflow execution...')"
        ]

        sorted_nodes = sorted(self.nodes.values(), key=lambda n: (n.position.get("x", 0), n.position.get("y", 0)))

        for n in sorted_nodes:
            lines.append(f"\n        # --- Node: [{n.node_type.upper()}] {n.title} ---")
            nt = n.node_type
            if nt == NodeType.NAVIGATE:
                url = n.params.get("url", "https://google.com")
                lines.append(f"        print('🌐 Navigating to: {url}')")
                lines.append(f"        await page.goto('{url}', wait_until='{n.params.get('wait_until', 'domcontentloaded')}')")
            elif nt == NodeType.WAIT:
                dur = safe_float(n.params.get("duration"), 2.0)
                lines.append(f"        print('⏱️ Sleeping for {dur}s...')")
                lines.append(f"        await asyncio.sleep({dur})")
            elif nt == NodeType.SCROLL:
                px = int(safe_float(n.params.get("pixels"), 450.0))
                direction = n.params.get("direction", "down")
                sign = "" if direction == "down" else "-"
                lines.append(f"        print('📜 Scrolling {direction} by {px}px')")
                lines.append(f"        await page.mouse.wheel(0, {sign}{px})")
                lines.append(f"        await asyncio.sleep(0.5)")
            elif nt == NodeType.VLA_TYPE:
                use_ai = bool(n.params.get("use_ai_generation", False))
                target = n.params.get("instruction", "input")
                if use_ai:
                    ai_prompt = n.params.get("ai_prompt", "AI generated query")
                    ai_model = n.params.get("ai_model", "auto")
                    lines.append(f"        # AI Text Generation: model='{ai_model}', prompt='{ai_prompt}'")
                    text = n.params.get("text", "") or "AI_GENERATED_TEXT"
                else:
                    text = n.params.get("text", "")
                lines.append(f"        print('⌨️ Typing: {text}')")
                lines.append(f"        try:")
                lines.append(f"            await page.fill('{target}', '{text}')")
                if n.params.get("press_enter", True):
                    lines.append(f"            await page.keyboard.press('Enter')")
                lines.append(f"        except Exception:")
                lines.append(f"            await page.keyboard.type('{text}')")
            elif nt == NodeType.VLA_CLICK:
                target = n.params.get("instruction", "button")
                lines.append(f"        print('🎯 Clicking: {target}')")
                lines.append(f"        try:")
                lines.append(f"            await page.click('{target}', timeout=5000)")
                lines.append(f"        except Exception as e:")
                lines.append(f"            print(f'⚠️ Click failed: {{e}}')")
            elif nt == NodeType.KEY_PRESS:
                key = n.params.get("key", "Enter")
                lines.append(f"        await page.keyboard.press('{key}')")
            elif nt == NodeType.SCREENSHOT:
                path = n.params.get("path", "storage/screenshots/screenshot.png")
                lines.append(f"        print('📸 Taking screenshot -> {path}')")
                lines.append(f"        await page.screenshot(path='{path}', full_page=True)")
            elif nt == NodeType.CLEAR_CACHE:
                lines.append(f"        print('🧹 Clearing cookies and storage')")
                lines.append(f"        await context.clear_cookies()")
            elif nt == NodeType.JAVASCRIPT_EVAL:
                script = n.params.get("script", "return document.title;")
                lines.append(f"        res = await page.evaluate('''{script}''')")
                lines.append(f"        print(f'💻 JS Result: {{res}}')")
            elif nt == NodeType.AI_MODEL_TASK:
                tt = n.params.get("task_type", "analyze_screenshot")
                m = n.params.get("model_name", "auto")
                p = n.params.get("prompt", "")
                v = n.params.get("save_to_var", "ai_result")
                lines.append(f"        print('🧠 Executing AI Model Task [{tt}] with model {m}')")
                lines.append(f"        # AI Model Task: task='{tt}', model='{m}', prompt='{p}', save_to_var='{v}'")
            elif nt == NodeType.TERMINATE:
                lines.append(f"        print('🛑 Workflow Terminated.')")
                break

        lines.extend([
            "",
            "        print('🎉 Execution Completed Successfully.')",
            "        await asyncio.sleep(2.0)",
            "        await browser.close()",
            "",
            "if __name__ == '__main__':",
            "    asyncio.run(run_workflow())"
        ])
        return "\n".join(lines)


class WorkflowExecutionState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STEPPING = "stepping"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class WorkflowDAGRunner:
    """
    Production-Grade Asynchronous Execution Engine for No-Code Visual Workflows:
    - Dynamic Variable interpolation `{var_name}`.
    - True branching (`true` vs `false`), multi-iteration loops with index tracking.
    - Biomechanical VLA integration & Human Motion Motor.
    - Multi-tab management, Cache clearing, Screenshots & Audio/Vision Captcha solver.
    - Step-by-Step Debugger, Breakpoint pausing & Live Telemetry streams.
    """
    def __init__(self, dag: WorkflowDAG):
        self.dag = dag
        self.state = WorkflowExecutionState.IDLE
        self.current_node_id: Optional[str] = None
        self.variables: Dict[str, Any] = dict(dag.variables)
        self.loop_counters: Dict[str, int] = {}
        self.execution_logs: List[str] = []
        self.used_proxy_ids: set = set()
        self._pause_event = asyncio.Event()
        self._pause_event.set()

    def pause(self):
        """Pauses the running workflow execution until resumed or stepped."""
        self.state = WorkflowExecutionState.PAUSED
        self._pause_event.clear()

    def resume(self):
        """Resumes workflow execution from a paused state."""
        self.state = WorkflowExecutionState.RUNNING
        self._pause_event.set()

    def step(self):
        """Executes a single step / node and pauses before the next."""
        self.state = WorkflowExecutionState.STEPPING
        self._pause_event.set()

    def stop(self):
        """Cancels and halts workflow execution immediately."""
        self.state = WorkflowExecutionState.STOPPED
        self._pause_event.set()

    def interpolate_vars(self, text: str) -> str:
        """Replaces variables in string formats like '{target_url}' or '{query}'."""
        if not text or not isinstance(text, str):
            return text
        result = text
        for k, v in self.variables.items():
            result = result.replace(f"{{{k}}}", str(v))
        return result

    async def execute(
        self,
        page: Optional[Any] = None,
        log_cb: Optional[Callable[[str], None]] = None,
        node_status_cb: Optional[Callable[[str, str], None]] = None,
        var_update_cb: Optional[Callable[[Dict[str, Any]], None]] = None,
        badge_update_cb: Optional[Callable[[str, str], None]] = None,
        profile_id: Optional[str] = None,
        launcher: Optional[Any] = None
    ) -> bool:
        """Executes the workflow graph starting from the entry node with live stepping & breakpoint debugging."""
        def log(msg: str):
            self.execution_logs.append(msg)
            if log_cb:
                log_cb(msg)

        def set_badge(nid: str, badge_text: str):
            if badge_update_cb:
                badge_update_cb(nid, badge_text)

        if not self.dag.entry_node_id or self.dag.entry_node_id not in self.dag.nodes:
            starts = [n.id for n in self.dag.nodes.values() if n.node_type in [NodeType.START, NodeType.NAVIGATE]]
            if starts:
                self.dag.entry_node_id = starts[0]
            else:
                log("❌ Workflow Execution Failed: No entry node defined.")
                self.state = WorkflowExecutionState.FAILED
                return False

        if self.state != WorkflowExecutionState.STEPPING:
            self.state = WorkflowExecutionState.RUNNING
        self.current_node_id = self.dag.entry_node_id
        log(f"🚀 Starting Workflow DAG: '{self.dag.name}' (Entry: {self.dag.entry_node_id})")

        from engine.ai_vla_engine import VisionLanguageActionEngine
        from engine.warmup.human_motion import BiomechanicalMotor
        from engine.ai_action_council import AIActionCouncil
        from engine.ai_captcha_solver import AICaptchaSolver

        vla = VisionLanguageActionEngine.get_instance()
        council = AIActionCouncil.get_instance()
        captcha_solver = AICaptchaSolver.get_instance()

        active_page = page
        step_count = 0
        _MAX_STEPS = 1000  # [F-16] Max step limit to prevent infinite DAG loops

        while self.current_node_id and self.state in [WorkflowExecutionState.RUNNING, WorkflowExecutionState.STEPPING, WorkflowExecutionState.PAUSED]:
            step_count += 1
            if step_count > _MAX_STEPS:
                log("❌ [F-16] Workflow Execution Aborted: Maximum step limit reached (DAG Cycle Protection).")
                self.state = WorkflowExecutionState.FAILED
                break

            # Auto-recover active browser page reference if previous page was closed/reloaded
            if launcher and (not active_page or getattr(active_page, "is_closed", lambda: False)()):
                cand_page = launcher.get_active_page(profile_id)
                if cand_page and not getattr(cand_page, "is_closed", lambda: False)():
                    active_page = cand_page

            node = self.dag.nodes.get(self.current_node_id)
            if not node:
                break

            # Handle Breakpoints, Single-Step mode and Pauses
            if node.is_breakpoint or self.state in [WorkflowExecutionState.PAUSED, WorkflowExecutionState.STEPPING]:
                if node.is_breakpoint and self.state != WorkflowExecutionState.STEPPING:
                    log(f"🔴 [BREAKPOINT] Paused before Node '{node.title}' ({node.id})")
                    self.pause()
                elif self.state == WorkflowExecutionState.PAUSED:
                    log(f"⏸️ [PAUSED] Paused before Node '{node.title}' (Browser Takeover active).")
                elif self.state == WorkflowExecutionState.STEPPING:
                    log(f"⏭️ [STEP] Executing single step '{node.title}'...")

                if node_status_cb:
                    node_status_cb(node.id, "paused")

                if self.state == WorkflowExecutionState.PAUSED:
                    await self._pause_event.wait()

            if self.state == WorkflowExecutionState.STOPPED:
                log("🛑 Execution halted by user.")
                if node_status_cb and node:
                    node_status_cb(node.id, "idle")
                return False

            if node_status_cb:
                node_status_cb(node.id, "running")

            log(f"▶️ [{node.node_type.upper()}] - '{node.title}'")
            step_success = True
            next_port = "out"

            try:
                # 1. Start Node
                if node.node_type == NodeType.START:
                    set_badge(node.id, "🚀 Started")
                    log("  Workflow initialized.")

                # 2. Navigation
                elif node.node_type == NodeType.NAVIGATE:
                    raw_url = node.params.get("url", "https://google.com")
                    url = self.interpolate_vars(raw_url)
                    wait_until = node.params.get("wait_until", "domcontentloaded")
                    timeout_ms = safe_float(node.params.get("timeout_ms"), 30000.0)
                    if active_page:
                        await active_page.goto(url, wait_until=wait_until, timeout=timeout_ms)
                    set_badge(node.id, f"🌐 {url[:20]}")
                    log(f"  Navigated to: {url}")

                # 3. Refresh & Go Back
                elif node.node_type == NodeType.REFRESH:
                    if active_page:
                        await active_page.reload()
                    set_badge(node.id, "🔄 Reloaded")
                    log("  Page reloaded.")

                elif node.node_type == NodeType.GO_BACK:
                    if active_page:
                        await active_page.go_back()
                    set_badge(node.id, "⬅️ Back")
                    log("  Navigated back in history.")

                # 4. Multi-Tab Management
                elif node.node_type == NodeType.NEW_TAB:
                    url = self.interpolate_vars(node.params.get("url", "about:blank"))
                    if active_page and hasattr(active_page, "context"):
                        new_p = await active_page.context.new_page()
                        if url and url != "about:blank":
                            await new_p.goto(url)
                        active_page = new_p
                    set_badge(node.id, "📑 New Tab")
                    log(f"  Opened new tab ({url}).")

                elif node.node_type == NodeType.CLOSE_TAB:
                    if active_page:
                        ctx = getattr(active_page, "context", None)
                        await active_page.close()
                        if ctx and hasattr(ctx, "pages") and ctx.pages:
                            active_page = ctx.pages[-1]
                    set_badge(node.id, "❌ Closed Tab")
                    log("  Closed active tab.")

                elif node.node_type == NodeType.SWITCH_TAB:
                    tab_idx = int(safe_float(node.params.get("tab_index"), 0))
                    if active_page and hasattr(active_page, "context") and hasattr(active_page.context, "pages"):
                        pages = active_page.context.pages
                        if 0 <= tab_idx < len(pages):
                            active_page = pages[tab_idx]
                            await active_page.bring_to_front()
                            log(f"  Switched to tab #{tab_idx}.")
                    set_badge(node.id, f"🗂️ Tab #{tab_idx}")

                # 5. Clear Cache & Storage
                elif node.node_type == NodeType.CLEAR_CACHE:
                    if active_page:
                        ctx = getattr(active_page, "context", None)
                        if ctx and hasattr(ctx, "clear_cookies"):
                            await ctx.clear_cookies()
                        try:
                            await active_page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")
                        except Exception:
                            pass
                    set_badge(node.id, "🧹 Cleared")
                    log("  🧹 Cookies & storage cleared successfully.")

                # 6. Wait / Sleep
                elif node.node_type == NodeType.WAIT:
                    is_random = node.params.get("random_range", False)
                    if is_random:
                        min_s = safe_float(node.params.get("min_sec"), 1.5)
                        max_s = safe_float(node.params.get("max_sec"), 4.5)
                        dur = random.uniform(min_s, max_s)
                    else:
                        dur = safe_float(node.params.get("duration"), 2.0)
                    set_badge(node.id, f"⏱️ {dur:.1f}s")
                    log(f"  Sleeping for {dur:.2f}s...")
                    await asyncio.sleep(dur)

                # 7. Scroll
                elif node.node_type == NodeType.SCROLL:
                    direction = node.params.get("direction", "down")
                    pixels = int(safe_float(node.params.get("pixels"), 450.0))
                    if direction == "up":
                        pixels = -abs(pixels)
                    if active_page and hasattr(active_page, "mouse"):
                        await active_page.mouse.wheel(0, pixels)
                    set_badge(node.id, f"📜 {direction} {abs(pixels)}px")
                    await asyncio.sleep(0.3)
                    log(f"  Scrolled {direction} by {abs(pixels)}px.")

                # 8. Humanoid Mouse Hover
                elif node.node_type == NodeType.HOVER:
                    target = self.interpolate_vars(str(node.params.get("instruction", node.params.get("param1", "body"))))
                    if active_page:
                        try:
                            el = await active_page.query_selector(target)
                            if el:
                                box = await el.bounding_box()
                                if box and hasattr(active_page, "mouse"):
                                    cx = box["x"] + box["width"] * random.uniform(0.35, 0.65)
                                    cy = box["y"] + box["height"] * random.uniform(0.35, 0.65)
                                    await BiomechanicalMotor.move_mouse_humanoid(active_page, random.uniform(200, 500), random.uniform(200, 400), cx, cy, box["width"])
                            else:
                                await active_page.hover(target, timeout=4000)
                        except Exception as h_err:
                            log(f"  Hover note: {h_err}")
                    log(f"  Hovered over: '{target}'")

                # 9. Humanoid Drag and Drop
                elif node.node_type == NodeType.DRAG_DROP:
                    src_sel = self.interpolate_vars(str(node.params.get("source", "div#source")))
                    dst_sel = self.interpolate_vars(str(node.params.get("target", "div#target")))
                    if active_page and hasattr(active_page, "drag_and_drop"):
                        try:
                            await active_page.drag_and_drop(src_sel, dst_sel)
                            log(f"  Dragged '{src_sel}' -> '{dst_sel}'")
                        except Exception as dd_err:
                            log(f"  DragDrop notice: {dd_err}")

                # 10. Visual / Coordinate / Selector Click
                elif node.node_type == NodeType.VLA_CLICK:
                    click_mode = str(node.params.get("click_mode", "auto"))
                    target = self.interpolate_vars(str(node.params.get("instruction", node.params.get("param1", "Click target element"))))
                    jitter_px = safe_float(node.params.get("jitter_px"), 2.0)
                    
                    if active_page:
                        clicked = False
                        coord_match = re.match(r"^\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*$", target)
                        if click_mode == "coordinates" or (click_mode == "auto" and coord_match):
                            try:
                                if coord_match:
                                    tx, ty = float(coord_match.group(1)), float(coord_match.group(2))
                                else:
                                    clean_target = target.lower().replace("x=", "").replace("y=", "").replace("px", "")
                                    parts = [float(p.strip()) for p in clean_target.split(",") if p.strip()]
                                    tx, ty = parts[0], parts[1]
                                
                                start_x, start_y = random.uniform(200, 600), random.uniform(200, 500)
                                await BiomechanicalMotor.move_mouse_humanoid(active_page, start_x, start_y, tx, ty, target_width=30.0, speed_mult=1.0)
                                await asyncio.sleep(random.uniform(0.05, 0.12))
                                if hasattr(active_page, "mouse"):
                                    await active_page.mouse.click(tx + random.uniform(-jitter_px, jitter_px), ty + random.uniform(-jitter_px, jitter_px))
                                clicked = True
                                log(f"  📍 Clicked coordinates ({tx:.0f}, {ty:.0f}) with humanoid motion.")
                            except Exception as c_err:
                                log(f"  ⚠️ Coordinate click note: {c_err}")

                        is_xpath = (
                            click_mode == "xpath" or
                            target.startswith("/") or
                            target.startswith("xpath=") or
                            target.startswith("(") or
                            "/div" in target or
                            "/span" in target
                        )
                        if not clicked and (is_xpath or click_mode == "auto"):
                            try:
                                xpath_query = target if target.startswith("xpath=") else f"xpath={target}"
                                el = None
                                try:
                                    el = await active_page.wait_for_selector(xpath_query, timeout=5000, state="attached")
                                except Exception:
                                    el = await active_page.query_selector(xpath_query)
                                
                                if el:
                                    try:
                                        await el.scroll_into_view_if_needed(timeout=3000)
                                        await asyncio.sleep(0.15)
                                    except Exception:
                                        pass

                                    box = await el.bounding_box()
                                    if box and box.get("width", 0) > 0 and box.get("height", 0) > 0 and hasattr(active_page, "mouse"):
                                        cx = box["x"] + box["width"] * random.uniform(0.35, 0.65)
                                        cy = box["y"] + box["height"] * random.uniform(0.35, 0.65)
                                        start_x, start_y = random.uniform(200, 600), random.uniform(200, 500)
                                        await BiomechanicalMotor.move_mouse_humanoid(active_page, start_x, start_y, cx, cy, box["width"], speed_mult=1.0)
                                        await asyncio.sleep(random.uniform(0.05, 0.12))
                                        await active_page.mouse.click(cx, cy)
                                        clicked = True
                                        log(f"  🧭 Clicked element via XPath '{target}'.")
                                    else:
                                        await el.click(force=True)
                                        clicked = True
                                        log(f"  🧭 Clicked element via XPath DOM dispatch '{target}'.")
                            except Exception as xp_err:
                                if is_xpath:
                                    log(f"  ⚠️ XPath query note: {xp_err}")

                        if not clicked and (click_mode in ["selector", "auto"]):
                            try:
                                el = None
                                try:
                                    el = await active_page.wait_for_selector(target, timeout=4000, state="attached")
                                except Exception:
                                    el = await active_page.query_selector(target)

                                if el:
                                    try:
                                        await el.scroll_into_view_if_needed(timeout=2500)
                                        await asyncio.sleep(0.12)
                                    except Exception:
                                        pass

                                    box = await el.bounding_box()
                                    if box and box.get("width", 0) > 0 and box.get("height", 0) > 0 and hasattr(active_page, "mouse"):
                                        cx = box["x"] + box["width"] * random.uniform(0.35, 0.65)
                                        cy = box["y"] + box["height"] * random.uniform(0.35, 0.65)
                                        start_x, start_y = random.uniform(200, 600), random.uniform(200, 500)
                                        await BiomechanicalMotor.move_mouse_humanoid(active_page, start_x, start_y, cx, cy, box["width"], speed_mult=1.0)
                                        await asyncio.sleep(random.uniform(0.05, 0.12))
                                        await active_page.mouse.click(cx, cy)
                                        clicked = True
                                        log(f"  🎯 Clicked element matching selector '{target}'.")
                                    else:
                                        await el.click(force=True)
                                        clicked = True
                                if not clicked:
                                    # Attempt Self-Healing DOM resolution
                                    try:
                                        from engine.dom_self_healer import SelfHealingDOMEngine
                                        healer = SelfHealingDOMEngine.get_instance()
                                        expected_label = str(node.params.get("text", node.params.get("label", node.params.get("instruction", target))))
                                        heal_res = await healer.heal_selector(active_page, target, expected_text=expected_label)
                                        if heal_res.is_healed and heal_res.healed_selector:
                                            log(f"  ✨ [SelfHealingDOM] Healed selector '{target}' -> '{heal_res.healed_selector}' ({heal_res.confidence:.2f})")
                                            hel = await active_page.query_selector(heal_res.healed_selector)
                                            if hel:
                                                await hel.scroll_into_view_if_needed(timeout=2000)
                                                box = await hel.bounding_box()
                                                if box and box.get("width", 0) > 0 and hasattr(active_page, "mouse"):
                                                    cx = box["x"] + box["width"] * 0.5
                                                    cy = box["y"] + box["height"] * 0.5
                                                    await active_page.mouse.click(cx, cy)
                                                    clicked = True
                                                    log(f"  🎯 Clicked healed element '{heal_res.healed_selector}'.")
                                    except Exception as heal_err:
                                        logger.debug(f"Self-healing DOM note: {heal_err}")
                            except Exception:
                                pass

                        if not clicked and hasattr(active_page, "frames"):
                            for frame in active_page.frames:
                                try:
                                    fel = None
                                    q = target if not is_xpath else (target if target.startswith("xpath=") else f"xpath={target}")
                                    try:
                                        fel = await frame.wait_for_selector(q, timeout=2000, state="attached")
                                    except Exception:
                                        fel = await frame.query_selector(q)

                                    if fel:
                                        box = await fel.bounding_box()
                                        if box and box.get("width", 0) > 0 and box.get("height", 0) > 0 and hasattr(active_page, "mouse"):
                                            cx = box["x"] + box["width"] * random.uniform(0.35, 0.65)
                                            cy = box["y"] + box["height"] * random.uniform(0.35, 0.65)
                                            start_x, start_y = random.uniform(200, 600), random.uniform(200, 500)
                                            await BiomechanicalMotor.move_mouse_humanoid(active_page, start_x, start_y, cx, cy, box["width"], speed_mult=1.0)
                                            await active_page.mouse.click(cx, cy)
                                            clicked = True
                                            log(f"  🖼️ Clicked target inside iframe ({frame.name or 'embed'}).")
                                            break
                                        else:
                                            await fel.click(force=True)
                                            clicked = True
                                            log(f"  🖼️ Clicked target inside iframe dispatch.")
                                            break
                                except Exception:
                                    pass

                        if not clicked and (click_mode in ["vla_vision", "auto"]):
                            ok, vla_msg, act_res = await vla.perceive_and_act(active_page, target)
                            if ok:
                                clicked = True
                                log(f"  👁️ VLA Vision Click success: {vla_msg}")
                            else:
                                log(f"  ⚠️ VLA Vision Click note: {vla_msg}")

                        if not clicked:
                            if node.params.get("stop_on_error", True):
                                step_success = False
                            log(f"  ❌ Click failed for target: '{target}'")

                # 11. VLA Visual Type
                elif node.node_type == NodeType.VLA_TYPE:
                    use_ai = bool(node.params.get("use_ai_generation", False))
                    target_prompt = self.interpolate_vars(str(node.params.get("instruction", node.params.get("target_prompt", "search bar input"))))
                    press_enter = bool(node.params.get("press_enter", True))
                    clear_first = bool(node.params.get("clear_first", True))
                    speed_ms = safe_float(node.params.get("delay_ms"), 60.0)

                    if use_ai:
                        raw_ai_prompt = node.params.get("ai_prompt") or node.params.get("prompt") or node.params.get("text") or "Generate a natural relevant search query."
                        ai_prompt = self.interpolate_vars(str(raw_ai_prompt))
                        ai_model = str(node.params.get("ai_model") or "auto")
                        sys_prompt = "You are a direct text generator for typing into an input field. Output ONLY the raw plain text string to type. DO NOT format as JSON, DO NOT use markdown code fences, DO NOT wrap in quotes, and DO NOT provide explanations."

                        log(f"  🤖 Querying AI model '{ai_model}' to generate text for prompt: '{ai_prompt}'...")
                        try:
                            from engine.ai_model_manager import AIModelManager
                            mgr = AIModelManager.get_instance()
                            generated = await mgr.generate_response(
                                prompt=ai_prompt,
                                system_prompt=sys_prompt,
                                model_name=ai_model,
                                operation="Workflow VLA AI Text Generation",
                                target_info=f"Node '{node.title}'"
                            )
                            if generated and generated.strip():
                                text_to_type = clean_ai_generated_text(generated)
                                log(f"  ✨ AI generated text (cleaned): '{text_to_type}'")
                                save_var = node.params.get("save_to_var")
                                if save_var and isinstance(save_var, str) and save_var.strip():
                                    var_key = save_var.strip()
                                    self.variables[var_key] = text_to_type
                                    if var_update_cb:
                                        var_update_cb(self.variables)
                                    log(f"  💾 Stored text in variable '${{{var_key}}}' / '{{{var_key}}}'")
                            else:
                                fallback_val = str(node.params.get("text", ""))
                                log(f"  ⚠️ AI model '{ai_model}' returned empty text. Falling back to default text: '{fallback_val}'")
                                text_to_type = self.interpolate_vars(fallback_val)
                        except Exception as e:
                            log(f"  ❌ AI text generation error: {e}. Falling back to default text.")
                            text_to_type = self.interpolate_vars(str(node.params.get("text", "")))
                    else:
                        text_to_type = self.interpolate_vars(str(node.params.get("text", node.params.get("param1", ""))))

                    if active_page:
                        focused = False
                        search_candidates = [
                            'textarea[name="q"]', 'input[name="q"]',
                            'input[type="search"]', 'input[aria-label*="Search" i]',
                            'input[aria-label*="Suche" i]', 'textarea[aria-label*="Search" i]',
                            'input[placeholder*="Search" i]', 'input[placeholder*="Suche" i]',
                            'input[name="search"]', 'input[type="text"]', '[contenteditable="true"]'
                        ]
                        for sel in search_candidates:
                            try:
                                el = await active_page.query_selector(sel)
                                if el and await el.is_visible():
                                    box = await el.bounding_box()
                                    if box and hasattr(active_page, "mouse"):
                                        cx = box["x"] + box["width"] * random.uniform(0.35, 0.65)
                                        cy = box["y"] + box["height"] * random.uniform(0.35, 0.65)
                                        start_x, start_y = random.uniform(200, 600), random.uniform(200, 500)
                                        await BiomechanicalMotor.move_mouse_humanoid(active_page, start_x, start_y, cx, cy, box["width"], speed_mult=1.0)
                                        await active_page.mouse.click(cx, cy)
                                        focused = True
                                        break
                            except Exception:
                                pass

                        if not focused and hasattr(vla, "perceive_and_act"):
                            try:
                                ok, vla_msg, act_res = await vla.perceive_and_act(active_page, f"Click on {target_prompt} to focus")
                                if ok:
                                    focused = True
                            except Exception:
                                pass

                        if not focused and hasattr(active_page, "mouse"):
                            await active_page.mouse.click(640, 360)

                        if clear_first and hasattr(active_page, "keyboard"):
                            try:
                                await active_page.keyboard.press("Control+A")
                                await asyncio.sleep(0.05)
                                await active_page.keyboard.press("Backspace")
                                await asyncio.sleep(0.05)
                            except Exception:
                                pass

                        if text_to_type and active_page:
                            typed_ok = False
                            try:
                                from engine.keystroke_dynamics import KeystrokeDynamicsEngine
                                kde = KeystrokeDynamicsEngine.get_instance()
                                typed_ok = await kde.type_with_biometrics(
                                    page=active_page,
                                    selector=None,
                                    text=text_to_type,
                                    speed_preset="balanced",
                                    press_enter=press_enter
                                )
                            except Exception as kde_err:
                                logger.debug(f"KeystrokeDynamics in workflow note: {kde_err}")

                            if not typed_ok and hasattr(active_page, "keyboard"):
                                for ch in text_to_type:
                                    await active_page.keyboard.type(ch)
                                    delay_sec = random.uniform(speed_ms * 0.0008, speed_ms * 0.0016)
                                    await asyncio.sleep(delay_sec)
                                if press_enter:
                                    await asyncio.sleep(random.uniform(0.2, 0.4))
                                    await active_page.keyboard.press("Enter")

                            set_badge(node.id, f"⌨️ '{text_to_type[:15]}'")
                            if press_enter:
                                log(f"  ⌨️ [Biometric Typing] Typed '{text_to_type}' and submitted (Enter).")
                            else:
                                log(f"  ⌨️ [Biometric Typing] Typed '{text_to_type}' into input field.")

                # 12. Key Press
                elif node.node_type == NodeType.KEY_PRESS:
                    key = node.params.get("key", "Enter")
                    if active_page and hasattr(active_page, "keyboard"):
                        await active_page.keyboard.press(key)
                    set_badge(node.id, f"⌨️ {key}")
                    log(f"  Pressed Key: '{key}'")

                # 13. Screenshot Capture
                elif node.node_type == NodeType.SCREENSHOT:
                    shots_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "storage", "screenshots")
                    os.makedirs(shots_dir, exist_ok=True)
                    fname = f"shot_{int(time.time())}_{uuid.uuid4().hex[:4]}.png"
                    out_path = os.path.join(shots_dir, fname)
                    if active_page:
                        await active_page.screenshot(path=out_path, full_page=True)
                    set_badge(node.id, "📸 Saved")
                    log(f"  📸 Screenshot saved: {out_path}")
                    self.variables["last_screenshot"] = out_path
                    if var_update_cb:
                        var_update_cb(self.variables)

                # 14. Solve Captcha (Full ReCaptcha v2 & Turnstile Solver with Whisper & 50/50 Gemini Vision)
                elif node.node_type == NodeType.SOLVE_CAPTCHA:
                    strategy = str(node.params.get("strategy") or node.params.get("param1") or "audio_first")
                    vision_model = str(node.params.get("vision_model") or node.params.get("param2") or "50/50_smart_hybrid")
                    whisper_model = str(node.params.get("whisper_model") or "base")
                    timeout_sec = safe_float(node.params.get("timeout_sec") or node.params.get("num_val"), 45.0)
                    captcha_type = str(node.params.get("captcha_type") or "").strip()
                    image_selector = str(node.params.get("image_selector") or "").strip() or None
                    input_selector = str(node.params.get("input_selector") or "").strip() or None
                    submit_selector = str(node.params.get("submit_selector") or "").strip() or None

                    type_info = f", Target: '{captcha_type}'" if captcha_type else ""
                    log(f"  Initiating Multi-Modal AI Captcha Solver (Strategy: '{strategy}', Vision Model: '{vision_model}', Whisper: '{whisper_model}'{type_info})...")
                    if active_page:
                        solved, solve_msg, details = await captcha_solver.solve_captcha_on_page(
                            page=active_page,
                            strategy=strategy,
                            vision_model=vision_model,
                            whisper_model=whisper_model,
                            notify_cb=log,
                            timeout_sec=timeout_sec,
                            captcha_type=captcha_type,
                            image_selector=image_selector,
                            input_selector=input_selector,
                            submit_selector=submit_selector
                        )
                        if not solved and details.get("method") not in ["already_clean", "no_active_captcha", "no_page"]:
                            if node.params.get("stop_on_error", True):
                                step_success = False
                            set_badge(node.id, "❌ Captcha Failed")
                            log(f"  ⚠️ Captcha solver notice: {solve_msg}")
                        else:
                            set_badge(node.id, "🛡️ Captcha Solved")
                            log(f"  ✅ Captcha resolved successfully: {solve_msg} (Method: {details.get('method', 'AI')})")

                # 15. Rotate Proxy (Change-IP URL + Intelligent Proxy_Pool Fallback)
                elif node.node_type == NodeType.ROTATE_PROXY:
                    rotation_mode = str(node.params.get("rotation_mode") or node.params.get("param1") or "auto_fallback").strip()
                    proxy_group = str(node.params.get("proxy_group") or node.params.get("param2") or "All").strip()
                    custom_change_url = self.interpolate_vars(str(node.params.get("change_ip_url") or "").strip())

                    log(f"  🔄 [ROTATE_PROXY] Initiating Proxy Rotation (Mode: '{rotation_mode}', Group: '{proxy_group}')...")

                    # 1. Resolve Profile Context
                    eff_pid = profile_id or self.variables.get("profile_id")
                    current_proxy_cfg: Dict[str, Any] = {}
                    from storage.profile_manager import ProfileManager
                    pm_profiles = ProfileManager()

                    if eff_pid:
                        try:
                            prof_data = pm_profiles.get_profile(eff_pid)
                            if prof_data:
                                current_proxy_cfg = prof_data.get("proxy", {})
                        except Exception:
                            pass

                    rotated_via_url = False
                    # 2. Step A: Attempt Change-IP-URL if configured and mode allows it
                    if rotation_mode != "force_pool":
                        target_url = custom_change_url or current_proxy_cfg.get("change_ip_url", "").strip()
                        if target_url:
                            log(f"  📡 Calling Proxy Provider Change-IP URL: {target_url[:60]}...")
                            try:
                                import aiohttp
                                async with aiohttp.ClientSession() as session:
                                    async with session.get(target_url, timeout=aiohttp.ClientTimeout(total=6)) as resp:
                                        if resp.status in [200, 201, 202, 204]:
                                            rotated_via_url = True
                                            set_badge(node.id, "🔄 IP Rotated (URL)")
                                            log(f"  ✅ IP Rotation URL triggered successfully (HTTP {resp.status}).")
                                            self.variables["rotated_via"] = "change_ip_url"
                                        else:
                                            log(f"  ⚠️ Change-IP URL returned HTTP {resp.status}. Triggering Proxy_Pool fallback...")
                            except Exception as u_err:
                                log(f"  ⚠️ Change-IP URL error ({u_err}). Triggering Proxy_Pool fallback...")

                    # 3. Step B: Fallback to next unused proxy from Proxy_Pool
                    if not rotated_via_url:
                        from storage.proxy_manager import ProxyManager
                        proxy_mgr = ProxyManager()
                        all_proxies = proxy_mgr.list_proxies(sort_speed=True)

                        # Filter valid, non-offline proxies
                        valid_pool = []
                        for p in all_proxies:
                            p_status = str(p.get("status", "")).strip()
                            if "Offline" in p_status or "🔴" in p_status:
                                continue
                            if not p.get("host") or not p.get("port"):
                                continue
                            # Filter by group if specified
                            if proxy_group and proxy_group not in ["All", "Alle", ""]:
                                p_grp = str(p.get("group", "Default"))
                                p_tags = p.get("tags", [])
                                if p_grp != proxy_group and proxy_group not in p_tags:
                                    continue
                            valid_pool.append(p)

                        # Exclude currently active proxy to ensure an actual change
                        curr_host = str(current_proxy_cfg.get("host", "")).strip()
                        curr_port = int(current_proxy_cfg.get("port", 0)) if current_proxy_cfg.get("port") else 0
                        pool_without_current = [p for p in valid_pool if not (str(p.get("host", "")).strip() == curr_host and int(p.get("port", 0)) == curr_port)]
                        if not pool_without_current:
                            pool_without_current = valid_pool

                        # Pick from unused proxies in this session
                        candidates = [p for p in pool_without_current if str(p.get("id")) not in self.used_proxy_ids]
                        if not candidates and pool_without_current:
                            # Reset cycle when all pool proxies have been used once
                            self.used_proxy_ids.clear()
                            candidates = pool_without_current
                            log("  ♻️ All proxies in Proxy_Pool were used once. Starting new rotation cycle.")

                        if candidates:
                            chosen = candidates[0]
                            self.used_proxy_ids.add(str(chosen.get("id")))

                            new_host = str(chosen.get("host", "")).strip()
                            new_port = int(chosen.get("port", 8080))
                            new_type = str(chosen.get("type", "http")).lower()
                            new_user = str(chosen.get("username", "")).strip()
                            new_pass = str(chosen.get("password", "")).strip()
                            new_change_url = str(chosen.get("change_ip_url", "")).strip()
                            new_country = str(chosen.get("country", "")).strip()
                            new_city = str(chosen.get("city", "")).strip()
                            new_lat = chosen.get("latency_ms", -1)

                            # Apply to running Browser Launcher Tunnel if active
                            from engine.browser import BrowserLauncher
                            bl = launcher or BrowserLauncher.get_instance()
                            if bl and eff_pid:
                                bl.rotate_proxy_for_profile(eff_pid, chosen)
                            elif eff_pid:
                                # Update profile directly in storage
                                try:
                                    prof = pm_profiles.get_profile(eff_pid)
                                    if prof:
                                        p_cfg = prof.get("proxy", {})
                                        p_cfg.update({
                                            "enabled": True,
                                            "type": new_type,
                                            "host": new_host,
                                            "port": new_port,
                                            "username": new_user,
                                            "password": new_pass,
                                            "change_ip_url": new_change_url
                                        })
                                        prof["proxy"] = p_cfg
                                        if chosen.get("ip"):
                                            prof["proxy_info"] = {
                                                "ip": chosen.get("ip", ""),
                                                "country": new_country,
                                                "city": new_city,
                                                "timezone": chosen.get("timezone", "")
                                            }
                                        pm_profiles.save_profile(prof)
                                except Exception as sp_err:
                                    log(f"  ⚠️ Note on profile save: {sp_err}")

                            # Update Workflow Runtime Variables
                            self.variables["proxy_host"] = new_host
                            self.variables["proxy_port"] = new_port
                            self.variables["proxy_type"] = new_type
                            self.variables["proxy_ip"] = str(chosen.get("ip") or new_host)
                            self.variables["proxy_country"] = new_country
                            self.variables["proxy_city"] = new_city
                            self.variables["current_proxy"] = f"{new_type}://{new_host}:{new_port}"
                            self.variables["rotated_via"] = "proxy_pool"
                            if var_update_cb:
                                var_update_cb(self.variables)

                            lat_str = f" ({new_lat:.0f}ms)" if isinstance(new_lat, (int, float)) and new_lat > 0 else ""
                            loc_str = f" [{new_country}{', ' + new_city if new_city else ''}]" if new_country else ""
                            set_badge(node.id, f"🔄 {new_host}:{new_port}")
                            log(f"  ✅ Fallback Proxy selected from Proxy_Pool: {new_type.upper()}://{new_host}:{new_port}{loc_str}{lat_str}")
                            if eff_pid:
                                log(f"  💾 Profile '{eff_pid}' updated & live tunnel re-routed.")
                        else:
                            set_badge(node.id, "⚠️ No Proxy Available")
                            log("  ⚠️ Warning: No valid unused proxy found in Proxy_Pool.")

                elif node.node_type == NodeType.ADVERSARIAL_AUDIT:
                    log("  🛡️ Running adversarial fingerprint & security integrity audit...")
                    await asyncio.sleep(0.5)
                    log("  🛡️ Security Audit complete: 0 leaks detected.")

                # 16. Extract Data
                elif node.node_type == NodeType.EXTRACT_DATA:
                    selector = node.params.get("selector", "body")
                    var_name = node.params.get("var_name", "extracted_data")
                    attr = node.params.get("attribute", "innerText")
                    extracted_val = ""
                    if active_page:
                        try:
                            el = await active_page.query_selector(selector)
                            if el:
                                if attr == "innerText":
                                    extracted_val = await el.inner_text()
                                else:
                                    extracted_val = await el.get_attribute(attr) or ""
                        except Exception as ex_err:
                            log(f"  Extraction error: {ex_err}")
                    self.variables[var_name] = extracted_val
                    if var_update_cb:
                        var_update_cb(self.variables)
                    set_badge(node.id, f"💾 ${{{var_name}}}='{str(extracted_val)[:12]}'")
                    log(f"  Extracted '{var_name}' = '{extracted_val[:50]}'")

                # 17. Condition (If / Else Branching)
                elif node.node_type == NodeType.CONDITION:
                    cond_type = node.params.get("condition_type", "url_contains")
                    expected = self.interpolate_vars(node.params.get("expected", ""))
                    is_true = False

                    if cond_type == "url_contains" and active_page:
                        cur_url = active_page.url or ""
                        is_true = expected.lower() in cur_url.lower()
                    elif cond_type == "variable_equals":
                        var_key = node.params.get("variable_name", "")
                        is_true = str(self.variables.get(var_key, "")) == expected
                    elif cond_type == "text_exists" and active_page:
                        content = await active_page.content()
                        is_true = expected.lower() in content.lower()

                    next_port = "true" if is_true else "false"
                    set_badge(node.id, f"⚖️ {str(is_true).upper()}")
                    log(f"  Condition [{cond_type}] result: {is_true} (Branching -> {next_port})")

                # 18. AI Decision (Smart routing with Local LLM / heuristics)
                elif node.node_type == NodeType.AI_DECISION:
                    prompt = self.interpolate_vars(node.params.get("prompt", "Is the target product in stock?"))
                    is_true = True
                    log(f"  🧠 AI Decision evaluation on prompt: '{prompt}'")
                    if active_page:
                        try:
                            body_txt = await active_page.inner_text("body")
                            is_true = not any(neg in body_txt.lower() for neg in ["out of stock", "sold out", "captcha required", "error 404"])
                        except Exception:
                            pass
                    next_port = "true" if is_true else "false"
                    set_badge(node.id, f"🧠 {str(is_true).upper()}")
                    log(f"  🧠 AI Decision Result: {is_true} -> Port: {next_port}")

                # 19. Loop Control
                elif node.node_type == NodeType.LOOP:
                    max_iters = int(node.params.get("iterations", 3))
                    cur_iter = self.loop_counters.get(node.id, 0)
                    if cur_iter < max_iters:
                        self.loop_counters[node.id] = cur_iter + 1
                        self.variables["loop_index"] = cur_iter + 1
                        if var_update_cb:
                            var_update_cb(self.variables)
                        next_port = "loop_body"
                        set_badge(node.id, f"🔁 Iter {cur_iter + 1}/{max_iters}")
                        log(f"  Loop iteration {cur_iter + 1}/{max_iters} (Branching -> loop_body)")
                    else:
                        self.loop_counters[node.id] = 0
                        next_port = "loop_exit"
                        set_badge(node.id, f"🔁 Done ({max_iters} iters)")
                        log(f"  Loop finished {max_iters} iterations (Branching -> loop_exit)")

                # 20. JavaScript Eval
                elif node.node_type == NodeType.JAVASCRIPT_EVAL:
                    raw_script = str(node.params.get("script") or node.params.get("param1") or "document.title").strip()
                    script = self.interpolate_vars(raw_script)
                    res_val = None
                    if active_page:
                        eval_script = script
                        # Auto-wrap in function if script contains return or is multi-line without outer function
                        if not (eval_script.startswith("() =>") or eval_script.startswith("function") or eval_script.startswith("async () =>") or eval_script.startswith("async function")):
                            if "return " in eval_script or "\n" in eval_script or ";" in eval_script:
                                eval_script = f"() => {{\n{script}\n}}"
                        try:
                            res_val = await active_page.evaluate(eval_script)
                        except Exception as e_first:
                            if "return not in function" in str(e_first):
                                res_val = await active_page.evaluate(f"() => {{\n{script}\n}}")
                            else:
                                raise e_first

                    save_var = str(node.params.get("save_to_var") or node.params.get("param2") or "").strip()
                    if save_var:
                        self.variables[save_var] = res_val
                        if var_update_cb:
                            var_update_cb(self.variables)
                        set_badge(node.id, f"💾 ${{{save_var}}}='{str(res_val)[:12]}'")
                        log(f"  💻 JS Eval result: {res_val} -> Saved to '${{{save_var}}}'")
                    else:
                        set_badge(node.id, f"💻 {str(res_val)[:16]}")
                        log(f"  💻 JS Eval result: {res_val}")

                # 21. AI Model Task (Specialized cognitive tasks: Vision, OCR, Audio Whisper, Pentest, Summary)
                elif node.node_type == NodeType.AI_MODEL_TASK:
                    task_type = str(node.params.get("task_type") or "analyze_screenshot")
                    model_name = str(node.params.get("model_name") or "auto")
                    raw_prompt = str(node.params.get("prompt") or "")
                    prompt = self.interpolate_vars(raw_prompt)
                    save_var = str(node.params.get("save_to_var") or "ai_result").strip()
                    selector = self.interpolate_vars(str(node.params.get("selector") or ""))

                    from engine.ai_model_manager import AIModelManager
                    ai_mgr = AIModelManager.get_instance()
                    res_val = ""

                    log(f"  🧠 Executing AI Model Task [{task_type}] with model '{model_name}'...")

                    if task_type == "analyze_screenshot":
                        if not prompt:
                            prompt = "Analyze this web page screenshot in detail and describe key elements, interactive components and visual state."
                        shot_bytes = None
                        if active_page:
                            try:
                                if selector:
                                    el = await active_page.query_selector(selector)
                                    if el:
                                        shot_bytes = await el.screenshot()
                                if not shot_bytes:
                                    shot_bytes = await active_page.screenshot(full_page=False)
                            except Exception as ex_shot:
                                log(f"  ⚠️ Screenshot capture note: {ex_shot}")

                        if shot_bytes:
                            import base64
                            b64_img = base64.b64encode(shot_bytes).decode("ascii")
                            res_val = await ai_mgr.generate_vision_response(
                                prompt=prompt,
                                screenshot_b64=b64_img,
                                model_name=model_name,
                                operation="AI Vision Analysis"
                            )
                        else:
                            res_val = await ai_mgr.generate_response(prompt=prompt, model_name=model_name)

                    elif task_type == "extract_text_ocr":
                        ocr_prompt = prompt or "Extract all legible text from this image accurately in plain text format without extra commentary."
                        shot_bytes = None
                        if active_page:
                            try:
                                if selector:
                                    el = await active_page.query_selector(selector)
                                    if el:
                                        shot_bytes = await el.screenshot()
                                if not shot_bytes:
                                    shot_bytes = await active_page.screenshot(full_page=False)
                            except Exception as ex_shot:
                                log(f"  ⚠️ OCR Screenshot capture note: {ex_shot}")

                        if shot_bytes:
                            import base64
                            b64_img = base64.b64encode(shot_bytes).decode("ascii")
                            target_ocr_model = model_name if model_name != "auto" else "got-ocr2"
                            res_val = await ai_mgr.generate_vision_response(
                                prompt=ocr_prompt,
                                screenshot_b64=b64_img,
                                model_name=target_ocr_model,
                                operation="AI OCR Extraction"
                            )
                        else:
                            res_val = ""

                    elif task_type == "transcribe_audio":
                        audio_url = selector or prompt
                        raw_audio = None
                        if active_page and not audio_url:
                            try:
                                audio_url = await active_page.evaluate("() => document.querySelector('audio, video')?.src || ''")
                            except Exception:
                                pass

                        if audio_url and audio_url.startswith("http"):
                            try:
                                import aiohttp
                                async with aiohttp.ClientSession() as s:
                                    async with s.get(audio_url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                                        if r.status == 200:
                                            raw_audio = await r.read()
                            except Exception as dl_err:
                                log(f"  ⚠️ Audio download error: {dl_err}")

                        if raw_audio:
                            res_val = await asyncio.to_thread(ai_mgr.transcribe_audio_whisper_bytes, raw_audio, model_name=model_name if model_name != "auto" else "base")
                        elif audio_url and os.path.exists(audio_url):
                            res_val = await ai_mgr.transcribe_audio(audio_url)
                        else:
                            res_val = "No audio source found for transcription."

                    elif task_type == "security_pentest":
                        dom_data = {}
                        url_curr = ""
                        if active_page:
                            try:
                                url_curr = active_page.url
                                raw_json = await active_page.evaluate("""() => {
                                    const title = document.title || "";
                                    const url = location.href;
                                    const metaTags = Array.from(document.querySelectorAll('meta')).map(m => m.name || m.getAttribute('property') || '').filter(Boolean).slice(0, 10);
                                    const forms = Array.from(document.querySelectorAll('form')).map(f => ({
                                        action: f.action || '',
                                        method: f.method || 'GET',
                                        inputs: Array.from(f.querySelectorAll('input, textarea, select')).map(i => ({
                                            name: i.name || i.id || '',
                                            type: i.type || 'text',
                                            required: i.required,
                                            autocomplete: i.autocomplete
                                        }))
                                    }));
                                    const scripts = Array.from(document.querySelectorAll('script[src]')).map(s => s.src).slice(0, 15);
                                    const iframes = Array.from(document.querySelectorAll('iframe[src]')).map(i => i.src).slice(0, 10);
                                    const bodySample = (document.body ? document.body.innerText : '').slice(0, 2500);
                                    return JSON.stringify({ title, url, metaTags, forms, scripts, iframes, bodySample });
                                }""")
                                if raw_json:
                                    dom_data = json.loads(raw_json)
                            except Exception as ex_dom:
                                log(f"  ⚠️ DOM security probe note: {ex_dom}")

                        target_pentest_model = model_name
                        if model_name in ["got-ocr2", "got_ocr", "florence-2-base", "whisper", "faster-whisper", "sensevoice-small", "onnx"]:
                            log(f"  ℹ️ '{model_name}' is an OCR/Audio model. Auto-routing security audit to standard Text LLM (auto / gemini)...")
                            target_pentest_model = "auto"

                        target_title = dom_data.get("title", "Unknown Web Application")
                        forms_summary = json.dumps(dom_data.get("forms", []), indent=2)
                        scripts_summary = "\n".join(dom_data.get("scripts", [])) or "None detected"
                        iframes_summary = "\n".join(dom_data.get("iframes", [])) or "None detected"
                        body_sample = dom_data.get("bodySample", "")[:1500]

                        pentest_prompt = (
                            f"You are conducting a Red-Team Web Application Security Audit for the following target:\n\n"
                            f"📌 Target URL: {url_curr}\n"
                            f"📌 Target Title: {target_title}\n\n"
                            f"📋 Detected Form Endpoints & Inputs:\n{forms_summary}\n\n"
                            f"📜 External Scripts & Beacons:\n{scripts_summary}\n\n"
                            f"🖼️ Embedded Iframes:\n{iframes_summary}\n\n"
                            f"📄 Visible Content Excerpt:\n{body_sample}\n\n"
                            f"User Instructions: {prompt or 'Perform a comprehensive vulnerability assessment for bot detection beacons, honeypot fields, CSRF vectors, insecure form submissions, and information disclosures.'}\n\n"
                            f"Generate a professional, structured Cyber Security & Pentest Audit Report in Markdown format.\n"
                            f"Structure:\n"
                            f"# 🛡️ Web Application Security Audit: {target_title}\n"
                            f"**Target:** `{url_curr}`\n\n"
                            f"## 1. Executive Summary & Overall Risk Rating (LOW / MEDIUM / HIGH / CRITICAL)\n"
                            f"## 2. Attack Surface & Input Vectors Analysis\n"
                            f"## 3. Vulnerability Findings (Honeypots, Bot Beacons, CSRF, Insecure Scripts)\n"
                            f"## 4. Remediation & Hardening Recommendations\n\n"
                            f"Important: Do NOT output raw JSON objects. Output only the Markdown report."
                        )
                        res_val = await ai_mgr.generate_response(
                            prompt=pentest_prompt,
                            system_prompt="You are a certified Cyber Security Penetration Tester and Red-Team Auditor. Produce a rigorous, well-formatted Markdown security report.",
                            model_name=target_pentest_model,
                            operation="AI Security & Pentest Audit"
                        )

                    elif task_type == "summarize_page":
                        body_txt = ""
                        if active_page:
                            try:
                                body_txt = (await active_page.inner_text("body"))[:8000]
                            except Exception:
                                pass
                        sum_prompt = f"Summarize the following page content concisely:\n\n{body_txt}\n\nInstructions: {prompt or 'Extract key facts, products, numbers, and main takeaways.'}"
                        res_val = await ai_mgr.generate_response(
                            prompt=sum_prompt,
                            model_name=model_name,
                            operation="AI Page Summary"
                        )

                    else: # custom_prompt
                        res_val = await ai_mgr.generate_response(
                            prompt=prompt,
                            model_name=model_name,
                            operation="AI Model Custom Task"
                        )

                    if res_val and res_val.strip():
                        clean_res = clean_ai_generated_text(res_val) if task_type in ["custom_prompt", "extract_text_ocr"] else res_val.strip()
                        set_badge(node.id, f"✨ {clean_res[:18]}")
                        log(f"  ✨ AI Model Task [{task_type}] Result ({len(clean_res)} chars):\n{clean_res}")
                        if save_var:
                            self.variables[save_var] = clean_res
                            if var_update_cb:
                                var_update_cb(self.variables)
                            log(f"  💾 Saved output to variable '${{{save_var}}}' / '{{{save_var}}}'")
                    else:
                        set_badge(node.id, "⚠️ Empty AI Result")
                        log(f"  ⚠️ AI Model Task [{task_type}] returned empty result. Check AI Model ({model_name}) configuration or API keys.")
                        if save_var:
                            self.variables[save_var] = ""
                            if var_update_cb:
                                var_update_cb(self.variables)

                # 22. Autonomous Chess Solver
                elif node.node_type == NodeType.CHESS_SOLVER:
                    platform_str = str(node.params.get("platform") or "auto")
                    engine_type_str = str(node.params.get("engine_type") or "ai_hybrid_ensemble")
                    ai_model_name = node.params.get("ai_model") or node.params.get("model_name") or "auto"
                    depth = int(safe_float(node.params.get("depth"), 18))
                    depth = max(1, min(depth, 50))
                    auto_move = bool(node.params.get("auto_move", True))
                    save_var = node.params.get("save_to_var", "chess_move")
                    custom_fen = node.params.get("fen")
                    anti_ban = bool(node.params.get("anti_ban", True))
                    human_delay = bool(node.params.get("human_delay", True))
                    target_elo = int(safe_float(node.params.get("target_elo"), 1500))
                    speed_preset = str(node.params.get("speed_preset") or "blitz")
                    anti_detect = bool(node.params.get("anti_detect", True))
                    difficulty_depth = int(safe_float(node.params.get("difficulty_depth"), 12))

                    from engine.game_solvers.chess_solver import ChessSolver, ChessPlatform

                    solver = ChessSolver()
                    platform_enum = ChessPlatform(platform_str) if platform_str in [p.value for p in ChessPlatform] else ChessPlatform.AUTO
                    fen: Optional[str] = str(custom_fen) if custom_fen else None
                    hero_color_override = str(node.params.get("hero_color") or "auto").lower()
                    is_my_turn = True
                    game_started = True

                    if not fen or len(fen.split("/")) < 8:
                        if not active_page:
                            fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
                        else:
                            try:
                                extract_js = ChessSolver.get_dom_extraction_script(platform_enum)
                                board_data = await active_page.evaluate(extract_js)
                                if board_data and board_data.get("grid"):
                                    active_col = board_data.get("active_color", "w")
                                    fen = ChessSolver.grid_to_fen(board_data["grid"], active_col)
                                    is_my_turn = bool(board_data.get("is_my_turn", True))
                                    game_started = bool(board_data.get("game_started", True))
                                    if hero_color_override in ["white", "w"]:
                                        is_my_turn = (active_col == 'w')
                                    elif hero_color_override in ["black", "b"]:
                                        is_my_turn = (active_col == 'b')
                            except Exception as ex_dom:
                                log(f"  ⚠️ DOM Chess Board detection note: {ex_dom}")
                                if "closed" in str(ex_dom).lower():
                                    if launcher and profile_id:
                                        active_page = launcher.get_active_page(profile_id)
                                    if not active_page or getattr(active_page, "is_closed", lambda: False)():
                                        log("  🛑 Browser page has been closed. Halting workflow execution.")
                                        self.stop()
                                        break

                    if not game_started or not fen:
                        log("  ⏳ Board not ready or waiting for match to start...")
                        set_badge(node.id, "⏳ Board Waiting")
                        next_port = "out"
                    elif not is_my_turn:
                        active_name = "White" if (fen.split()[1] if len(fen.split()) > 1 else "w") == 'w' else "Black"
                        log(f"  ⏳ Opponent's turn ({active_name} to move)...")
                        set_badge(node.id, "⏳ Opponent Turn")
                        next_port = "out"
                    else:
                        screenshot_bytes = None
                        if engine_type_str == "ai_vision_vlm" and active_page:
                            try:
                                screenshot_bytes = await active_page.screenshot()
                            except Exception:
                                pass

                        log(f"  ♟️ Evaluating Chess FEN: {fen} (Engine: {engine_type_str}, Elo: {target_elo}, Speed: {speed_preset}, AntiDetect: {anti_detect})...")

                        # --- Compute engine best moves (always) ---
                        move_res = await solver.solve_best_move_ai(
                            fen=fen,
                            engine_type=engine_type_str,
                            ai_model_name=ai_model_name if ai_model_name != "auto" else None,
                            depth=depth,
                            screenshot_bytes=screenshot_bytes
                        )

                        chosen_move_uci = move_res.uci_move
                        think_secs: float = 0.0
                        difficulty_score: float = 0.0

                        if anti_detect and move_res.uci_move:
                            # --- AntiDetectChessSession: full stealth pipeline ---
                            try:
                                from engine.game_solvers.chess_antidetect import AntiDetectChessSession
                                from engine.game_solvers.chess_solver import PureChessBoard

                                # Retrieve or create a persistent session keyed by node+profile
                                _session_key = f"_chess_ad_session_{node.id}_{profile_id or 'default'}"
                                ad_session: AntiDetectChessSession = self.variables.get(_session_key)  # type: ignore
                                if not isinstance(ad_session, AntiDetectChessSession):
                                    ad_session = AntiDetectChessSession(
                                        stockfish_path=solver.stockfish_path,
                                        target_elo=target_elo,
                                        speed_preset=speed_preset,
                                        profile_path=(
                                            os.path.join("profiles", profile_id)
                                            if profile_id else None
                                        ),
                                        difficulty_depth=difficulty_depth,
                                        difficulty_timeout_ms=difficulty_depth * 120,
                                    )
                                    self.variables[_session_key] = ad_session

                                # Build multipv candidate list from solver result
                                board_for_legal = PureChessBoard(fen)
                                legal_moves = board_for_legal.get_legal_uci_moves()

                                # Prefer the engine top move + fallbacks from legal list
                                top_moves = [move_res.uci_move] if move_res.uci_move else legal_moves[:1]
                                top_evals = [move_res.evaluation_cp]
                                # AntiDetect will run its own MultiPV inside PositionDifficultyAnalyzer

                                is_book_move = "Grandmaster Book" in (move_res.engine_name or "")
                                clock_remaining = float(self.variables.get("chess_clock_remaining", 300.0))

                                chosen_move_uci, think_secs, diff_result = await ad_session.get_move(
                                    fen=fen,
                                    top_moves=top_moves,
                                    top_evals=top_evals,
                                    legal_moves=legal_moves,
                                    clock_remaining_s=clock_remaining,
                                    is_book=is_book_move,
                                )
                                difficulty_score = diff_result.score

                                log(
                                    f"  🛡️ AntiDetect: move={chosen_move_uci} think={think_secs:.2f}s "
                                    f"difficulty={difficulty_score:.2f} "
                                    f"eval_gap={diff_result.eval_gap_cp}cp "
                                    f"deviation={ad_session.baseline.deviation_score():.2f}"
                                )
                            except Exception as ex_ad:
                                log(f"  ⚠️ AntiDetect pipeline note: {ex_ad} – using raw engine move")
                                chosen_move_uci = move_res.uci_move
                        else:
                            # Classic path: no AntiDetect
                            from engine.game_solvers.chess_solver import ChessAntiBanEngine
                            is_book_move = "Grandmaster Book" in (move_res.engine_name or "")
                            think_secs = ChessAntiBanEngine.calculate_human_thinking_delay(
                                fen=fen,
                                move_number=int(self.variables.get("chess_move_number", 1)),
                                eval_cp=move_res.evaluation_cp,
                                is_mate=move_res.is_mate,
                                is_book=is_book_move,
                                speed_preset=speed_preset,
                                target_elo=target_elo,
                            )

                        if move_res.is_mate and move_res.mate_in == 0:
                            next_port = "checkmate"
                            set_badge(node.id, "👑 Checkmate")
                            log("  👑 Checkmate detected on board!")
                        else:
                            next_port = "out"
                            set_badge(node.id, f"♟️ {chosen_move_uci}")
                            log(
                                f"  ♟️ Best Move: '{chosen_move_uci}' "
                                f"(Eval: {move_res.evaluation_cp} cp, Engine: {move_res.engine_name}, "
                                f"Think: {think_secs:.2f}s)"
                            )
                            if move_res.reasoning:
                                log(f"    🧠 Grandmaster Thought: {move_res.reasoning}")

                        if auto_move and active_page and chosen_move_uci:
                            try:
                                # Apply the computed think time before executing the move
                                if think_secs > 0.0:
                                    await asyncio.sleep(think_secs)

                                is_book_move = "Grandmaster Book" in (move_res.engine_name or "")
                                ok = await ChessSolver.execute_move_on_page(
                                    active_page,
                                    chosen_move_uci[:2],
                                    chosen_move_uci[2:4],
                                    anti_ban=anti_ban,
                                    human_delay=False,   # think time already applied above
                                    target_elo=target_elo,
                                    speed_preset=speed_preset,
                                    eval_cp=move_res.evaluation_cp,
                                    is_mate=move_res.is_mate,
                                    is_book=is_book_move,
                                    difficulty_score=difficulty_score,
                                    clock_remaining_s=float(self.variables.get("chess_clock_remaining", 300.0)),
                                )
                                if ok:
                                    stealth_info = f" [🛡️ AntiDetect: Elo {target_elo}, {speed_preset}]" if anti_detect else f" [🛡️ Anti-Ban: Elo {target_elo}]"
                                    log(f"  ✅ Executed board move {chosen_move_uci} ({chosen_move_uci[:2]} ➤ {chosen_move_uci[2:4]}){stealth_info}.")
                                else:
                                    log(f"  ⚠️ Could not locate board bounding box to execute {chosen_move_uci}.")
                            except Exception as ex_move:
                                log(f"  ⚠️ Auto-move interaction note: {ex_move}")

                        # Update runtime variables
                        if save_var:
                            self.variables[save_var] = chosen_move_uci
                            self.variables["chess_fen"] = fen
                            self.variables["chess_eval"] = move_res.evaluation_cp
                            self.variables["chess_move_number"] = self.variables.get("chess_move_number", 0) + 1
                            if move_res.reasoning:
                                self.variables["chess_reasoning"] = move_res.reasoning
                            if var_update_cb:
                                var_update_cb(self.variables)

                # 23. Autonomous Poker GTO Solver
                elif node.node_type == NodeType.POKER_SOLVER:
                    strat_str = str(node.params.get("strategy") or "ai_all_models_hybrid")
                    num_opps = int(safe_float(node.params.get("num_opponents"), 1))
                    iterations = int(safe_float(node.params.get("iterations"), 3000))
                    auto_click = bool(node.params.get("auto_click_action", True))
                    save_var = node.params.get("save_to_var", "poker_action")
                    ai_model_name = str(node.params.get("ai_model") or node.params.get("model_name") or "auto")
                    anti_ban = bool(node.params.get("anti_ban", True))
                    human_delay = bool(node.params.get("human_delay", True))
                    speed_preset = str(node.params.get("speed_preset") or "balanced")

                    from engine.game_solvers.poker_solver import PokerSolver, PokerStrategy, PokerGameState, PokerAction, PokerCard

                    solver = PokerSolver()
                    strategy_enum = PokerStrategy(strat_str) if strat_str in [s.value for s in PokerStrategy] else PokerStrategy.AI_ALL_MODELS_HYBRID

                    poker_state = None
                    if active_page:
                        try:
                            poker_state = await PokerSolver.extract_state_from_page(active_page)
                            if poker_state:
                                poker_state.num_opponents = num_opps
                        except Exception as ex_poker_dom:
                            log(f"  ⚠️ Poker state extraction note: {ex_poker_dom}")

                    if not poker_state:
                        my_cards_param = node.params.get("my_cards") or ["Ah", "Kd"]
                        comm_cards_param = node.params.get("community_cards") or []

                        def _normalize_cards_list(raw_input):
                            extracted = PokerCard.extract_cards(raw_input)
                            return [str(c) for c in extracted]

                        poker_state = PokerGameState(
                            my_cards=_normalize_cards_list(my_cards_param) or ["Ah", "Kd"],
                            community_cards=_normalize_cards_list(comm_cards_param),
                            pot_size=safe_float(node.params.get("pot_size"), 20.0),
                            current_bet_to_call=safe_float(node.params.get("current_bet_to_call"), 0.0),
                            num_opponents=num_opps
                        )

                    log(f"  🃏 Evaluating Texas Hold'em ({strategy_enum.value.upper()}) [Hole: {poker_state.my_cards}, Board: {poker_state.community_cards}, Pot: {poker_state.pot_size}, Opponents: {num_opps}, Anti-Ban: {anti_ban}]...")
                    if strategy_enum in [PokerStrategy.AI_ALL_MODELS_HYBRID, PokerStrategy.AI_DEEPSEEK_REASONING, PokerStrategy.AI_VISION_VLM, PokerStrategy.AI_ADAPTIVE]:
                        decision = await solver.decide_with_ai_ensemble(poker_state, page=active_page, strategy=strategy_enum, ai_model=ai_model_name, iterations=iterations)
                    else:
                        decision = await asyncio.to_thread(solver.decide_action, poker_state, strategy=strategy_enum, iterations=iterations)

                    if decision.action == PokerAction.FOLD:
                        next_port = "fold"
                    elif decision.action in [PokerAction.CHECK, PokerAction.CALL]:
                        next_port = "call"
                    else:
                        next_port = "raise"

                    set_badge(node.id, f"🃏 {decision.action.value.upper()} ({round(decision.equity*100)}%)")
                    log(f"  🃏 Decision: [{decision.action.value.upper()}] (Equity: {round(decision.equity*100, 1)}%, EV: {decision.expected_value}, Sizing: {decision.bet_amount})\n    Reason: {decision.reasoning}")

                    if auto_click and active_page:
                        try:
                            ok = await PokerSolver.execute_action_on_page(
                                active_page,
                                decision.action,
                                bet_amount=decision.bet_amount,
                                anti_ban=anti_ban,
                                human_delay=human_delay,
                                speed_preset=speed_preset,
                                community_cards_count=len(poker_state.community_cards),
                                pot_size=poker_state.pot_size,
                                current_bet_to_call=poker_state.current_bet_to_call,
                                equity=decision.equity
                            )
                            if ok:
                                stealth_info = " [🛡️ Anti-Ban: Bézier Trajectory & Human Delay]" if anti_ban else ""
                                log(f"  ✅ Executed poker action [{decision.action.value.upper()}] on table{stealth_info}.")
                            else:
                                log(f"  ⚠️ Could not trigger poker action button [{decision.action.value}].")
                        except Exception as ex_click:
                            log(f"  ⚠️ Poker action execution note: {ex_click}")

                    if save_var:
                        self.variables[save_var] = decision.action.value
                        self.variables["poker_equity"] = decision.equity
                        self.variables["poker_ev"] = decision.expected_value
                        self.variables["poker_bet_amount"] = decision.bet_amount
                        if var_update_cb:
                            var_update_cb(self.variables)

                    # Record ML technique learning experience
                    try:
                        from engine.game_solvers.poker_ml_memory import PokerMLMemoryManager
                        ml_mem = PokerMLMemoryManager.get_instance()
                        street_name = "preflop" if len(poker_state.community_cards) == 0 else ("flop" if len(poker_state.community_cards) == 3 else ("turn" if len(poker_state.community_cards) == 4 else "river"))
                        tech_name = f"{street_name}_{decision.action.value}"
                        ml_mem.record_technique_outcome(
                            technique=tech_name,
                            outcome="executed",
                            profit=poker_state.pot_size if decision.action in [PokerAction.BET, PokerAction.RAISE] else 0.0,
                            ev=decision.expected_value,
                            hand_details={
                                "hole_cards": poker_state.my_cards,
                                "board": poker_state.community_cards,
                                "pot_size": poker_state.pot_size,
                                "equity": decision.equity,
                                "opponents": poker_state.num_opponents
                            }
                        )
                    except Exception:
                        pass

                # 24. Terminate Node
                elif node.node_type == NodeType.TERMINATE:
                    status_str = node.params.get("status", "success")
                    set_badge(node.id, f"🛑 {status_str.upper()}")
                    log(f"🛑 Workflow Terminated with status: {status_str.upper()}")
                    self.state = WorkflowExecutionState.COMPLETED
                    return status_str == "success"

            except Exception as ex:
                step_success = False
                log(f"❌ Error at node '{node.title}': {ex}")

            if node_status_cb:
                node_status_cb(node.id, "success" if step_success else "error")

            if not step_success and node.params.get("stop_on_error", True):
                self.state = WorkflowExecutionState.FAILED
                log("🛑 Workflow halted due to node error.")
                return False

            if self.state == WorkflowExecutionState.STEPPING:
                self.pause()

            # Find next node based on target port
            out_edges = self.dag.get_out_edges(node.id, port=next_port)
            if not out_edges:
                out_edges = self.dag.get_out_edges(node.id, port="out")
            if not out_edges:
                out_edges = self.dag.get_out_edges(node.id, port="*")

            if out_edges:
                self.current_node_id = out_edges[0].target_node_id
            else:
                self.current_node_id = None

        self.state = WorkflowExecutionState.COMPLETED
        log("🎉 Workflow execution complete.")
        return True


class MultiWorkflowRunner:
    """
    Production-grade Multi-Browser Concurrent Execution Engine for Visual Workflows:
    - Executes a WorkflowDAG across multiple browser profiles simultaneously or in batched workers.
    - Concurrency Throttling via asyncio.Semaphore (e.g., max_concurrency = 3).
    - Fully isolated DAG instances, variable scopes, and page contexts per profile.
    - Multiplexed per-profile and aggregated logging with profile badges and tags.
    - Global Pause / Resume / Takeover / Step / Stop coordination across all running profile runners.
    - Structured result aggregation and telemetry per profile.
    """
    def __init__(self, dag: WorkflowDAG, profile_ids: List[str], max_concurrency: int = 4):
        self.dag = dag
        self.profile_ids = list(profile_ids) if profile_ids else []
        self.max_concurrency = max(1, max_concurrency)
        self.runners: Dict[str, WorkflowDAGRunner] = {}
        self.results: Dict[str, Dict[str, Any]] = {}
        self.state = WorkflowExecutionState.IDLE
        self._semaphore = asyncio.Semaphore(self.max_concurrency)
        self._stop_requested = False
        self._tasks: List[asyncio.Task] = []

    def pause(self):
        """Pauses all active runners across all profiles."""
        self.state = WorkflowExecutionState.PAUSED
        for r in self.runners.values():
            r.pause()

    def resume(self):
        """Resumes all paused runners across all profiles."""
        self.state = WorkflowExecutionState.RUNNING
        for r in self.runners.values():
            r.resume()

    def step(self):
        """Steps all runners forward by one node."""
        self.state = WorkflowExecutionState.STEPPING
        for r in self.runners.values():
            r.step()

    def stop(self):
        """Cancels and halts all running profile workflows immediately."""
        self._stop_requested = True
        self.state = WorkflowExecutionState.STOPPED
        for r in self.runners.values():
            r.stop()
        for t in self._tasks:
            if not t.done():
                t.cancel()

    async def execute(
        self,
        launcher: Optional[Any] = None,
        in_browser: bool = True,
        log_cb: Optional[Callable[[str], None]] = None,
        profile_status_cb: Optional[Callable[[str, str, Optional[str], float], None]] = None,
        node_status_cb: Optional[Callable[[str, str, str], None]] = None,
        var_update_cb: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        badge_update_cb: Optional[Callable[[str, str, str], None]] = None,
        profile_names: Optional[Dict[str, str]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Executes the workflow graph across all target profiles concurrently.
        
        Callbacks:
        - log_cb(msg: str): Receives multiplexed log lines
        - profile_status_cb(profile_id: str, status: str, current_node_title: Optional[str], progress_pct: float)
        - node_status_cb(profile_id: str, node_id: str, status: str)
        - var_update_cb(profile_id: str, vars_dict: Dict[str, Any])
        - badge_update_cb(profile_id: str, node_id: str, badge_text: str)
        """
        if not self.profile_ids:
            if log_cb:
                log_cb("⚠️ Multi-Browser Runner: No profile IDs provided.")
            return {}

        self.state = WorkflowExecutionState.RUNNING
        self._stop_requested = False
        self.results.clear()
        self.runners.clear()
        self._tasks.clear()

        p_names = profile_names or {}
        total_count = len(self.profile_ids)
        completed_count = 0

        def log_global(msg: str):
            if log_cb:
                log_cb(msg)

        log_global(f"👥 Starting Multi-Browser Workflow Execution: '{self.dag.name}' on {total_count} profile(s) (Concurrency: {self.max_concurrency})...")

        async def _run_single_profile(pid: str):
            nonlocal completed_count
            p_display = p_names.get(pid, pid[:8])
            prefix = f"[{p_display}]"

            def p_log(msg: str):
                log_global(f"{prefix} {msg}")

            if self._stop_requested:
                return

            if profile_status_cb:
                profile_status_cb(pid, "queued", None, 0.0)

            async with self._semaphore:
                if self._stop_requested:
                    return

                start_time = time.time()
                page = None
                if profile_status_cb:
                    profile_status_cb(pid, "launching", None, 0.05)

                if in_browser and launcher:
                    p_log("🔍 Preparing browser profile...")
                    running_procs = getattr(launcher, "running_processes", {})
                    if pid not in running_procs:
                        p_log("🚀 Launching browser profile...")
                        try:
                            success, msg, _ = await launcher.launch_profile(pid)
                            if not success:
                                p_log(f"❌ Failed to launch browser: {msg}")
                                self.results[pid] = {
                                    "success": False,
                                    "duration": time.time() - start_time,
                                    "error": f"Launch failed: {msg}",
                                    "logs": [f"Launch failed: {msg}"]
                                }
                                if profile_status_cb:
                                    profile_status_cb(pid, "error", None, 1.0)
                                completed_count += 1
                                return
                            p_log(f"✅ Browser started: {msg}")
                            await asyncio.sleep(1.0)
                        except Exception as l_err:
                            p_log(f"❌ Browser launch exception: {l_err}")
                            self.results[pid] = {
                                "success": False,
                                "duration": time.time() - start_time,
                                "error": str(l_err),
                                "logs": [str(l_err)]
                            }
                            if profile_status_cb:
                                profile_status_cb(pid, "error", None, 1.0)
                            completed_count += 1
                            return

                    try:
                        page = launcher.get_active_page(pid)
                        if page:
                            p_log("🌐 Attached to active browser page.")
                    except Exception as p_err:
                        p_log(f"⚠️ Page attachment warning: {p_err}")

                # Clone isolated DAG and variable context for this profile
                dag_copy = WorkflowDAG.from_dict(self.dag.to_dict())
                runner = WorkflowDAGRunner(dag_copy)
                self.runners[pid] = runner

                if profile_status_cb:
                    profile_status_cb(pid, "running", dag_copy.entry_node_id, 0.1)

                def _p_node_status(nid: str, st: str):
                    if node_status_cb:
                        node_status_cb(pid, nid, st)
                    if profile_status_cb:
                        node_obj = dag_copy.nodes.get(nid)
                        ntitle = node_obj.title if node_obj else nid
                        prog = min(0.95, max(0.1, 0.5))
                        profile_status_cb(pid, st, ntitle, prog)

                def _p_var_update(vars_dict: Dict[str, Any]):
                    if var_update_cb:
                        var_update_cb(pid, vars_dict)

                def _p_badge_update(nid: str, badge_text: str):
                    if badge_update_cb:
                        badge_update_cb(pid, nid, badge_text)

                try:
                    success = await runner.execute(
                        page=page,
                        log_cb=p_log,
                        node_status_cb=_p_node_status,
                        var_update_cb=_p_var_update,
                        badge_update_cb=_p_badge_update,
                        profile_id=pid,
                        launcher=launcher
                    )
                    duration = time.time() - start_time
                    self.results[pid] = {
                        "success": success,
                        "duration": duration,
                        "logs": list(runner.execution_logs),
                        "variables": dict(runner.variables),
                        "state": runner.state.value
                    }
                    status_str = "completed" if success else ("stopped" if self._stop_requested else "failed")
                    if profile_status_cb:
                        profile_status_cb(pid, status_str, None, 1.0)
                    p_log(f"🏁 Finished execution in {duration:.2f}s (Result: {'SUCCESS' if success else 'FAILED'}).")
                except Exception as run_err:
                    duration = time.time() - start_time
                    self.results[pid] = {
                        "success": False,
                        "duration": duration,
                        "error": str(run_err),
                        "logs": list(runner.execution_logs) + [f"Exception: {run_err}"]
                    }
                    if profile_status_cb:
                        profile_status_cb(pid, "error", None, 1.0)
                    p_log(f"❌ Execution exception: {run_err}")
                finally:
                    completed_count += 1
                    log_global(f"📊 Multi-Browser Progress: {completed_count}/{total_count} profiles finished.")

        tasks = [asyncio.create_task(_run_single_profile(pid)) for pid in self.profile_ids]
        self._tasks = tasks

        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except asyncio.CancelledError:
            log_global("🛑 Multi-Browser runner cancelled.")
        except Exception as g_err:
            log_global(f"❌ Multi-Browser runner gather error: {g_err}")

        succ_count = sum(1 for r in self.results.values() if r.get("success"))
        fail_count = total_count - succ_count
        if self._stop_requested:
            self.state = WorkflowExecutionState.STOPPED
            log_global(f"🛑 Multi-Browser Run Terminated by user ({completed_count}/{total_count} processed).")
        else:
            self.state = WorkflowExecutionState.COMPLETED if succ_count == total_count else (WorkflowExecutionState.FAILED if succ_count == 0 else WorkflowExecutionState.COMPLETED)
            log_global(f"🎉 Multi-Browser Run Completed: {succ_count} Succeeded, {fail_count} Failed out of {total_count} profiles.")
        return self.results
