import os
import time
import asyncio
import logging
from typing import Optional, Dict, Any, Tuple, Callable

from engine.ai_model_manager import AIModelManager

logger = logging.getLogger("AIVoiceCopilot")


class AIVoiceCopilot:
    """
    Local Voice-to-Action Copilot:
    - Transcribes voice commands using local Faster-Whisper (zero-cloud STT, 80ms latency).
    - Classifies transcription into direct action intents (create profile, warmup, audit).
    """

    _instance: Optional['AIVoiceCopilot'] = None

    def __init__(self):
        self.ai_mgr = AIModelManager.get_instance()

    @classmethod
    def get_instance(cls) -> 'AIVoiceCopilot':
        if cls._instance is None:
            cls._instance = AIVoiceCopilot()
        return cls._instance

    async def transcribe_audio_file(self, audio_path: str) -> str:
        """Transcribes an audio file (.wav, .mp3, .ogg) via Faster-Whisper."""
        return await self.ai_mgr.transcribe_audio(audio_path)

    async def process_voice_command(self, audio_path: str) -> Dict[str, Any]:
        """Transcribes audio and extracts high-level intention."""
        text = await self.transcribe_audio_file(audio_path)
        t_clean = text.strip()
        
        intent = "general_chat"
        t_lower = t_clean.lower()
        if any(k in t_lower for k in ["profil anlegen", "erstelle profil", "create profile", "batch profile"]):
            intent = "create_profile"
        elif any(k in t_lower for k in ["warmup", "start warmup", "aufwärmen", "kampagne"]):
            intent = "start_warmup"
        elif any(k in t_lower for k in ["audit", "prüfe", "check", "fingerprint", "webrtc"]):
            intent = "audit_profile"

        return {
            "transcription": t_clean,
            "intent": intent,
            "success": bool(t_clean)
        }

    def speak_feedback(self, text: str, voice: str = "neutral_copilot") -> bytes:
        """Synthesizes spoke audio feedback bytes for the user."""
        from engine.neural_tts import LocalNeuralTTSEngine
        tts = LocalNeuralTTSEngine.get_instance()
        return tts.synthesize_to_bytes(text, voice=voice)

    def speak_intent_feedback(self, intent: str, details: str = "") -> bytes:
        """Synthesizes human-like spoken feedback for recognized voice intents."""
        responses = {
            "create_profile": f"Erstelle neues Profil {details}.".strip(),
            "start_warmup": f"Starte Warmup-Kampagne {details}.".strip(),
            "audit_profile": "Starte Sicherheits- und Fingerprint-Audit.",
            "general_chat": "Befehl verarbeitet."
        }
        text = responses.get(intent, "Aktion ausgeführt.")
        return self.speak_feedback(text)
