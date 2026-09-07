import pytest
import wave
import io
from engine.neural_tts import LocalNeuralTTSEngine
from engine.ai_voice_copilot import AIVoiceCopilot


def test_neural_tts_initialization():
    tts = LocalNeuralTTSEngine.get_instance()
    assert tts.is_available() is True


def test_synthesize_to_wav_bytes():
    tts = LocalNeuralTTSEngine.get_instance()
    text = "SoxBot Local AI Engine operational."
    wav_bytes = tts.synthesize_to_bytes(text, voice="neutral_copilot", speed=1.2)

    assert len(wav_bytes) > 1000
    assert wav_bytes.startswith(b"RIFF")
    assert b"WAVE" in wav_bytes[:16]

    # Verify standard WAV headers using Python wave module
    buffer = io.BytesIO(wav_bytes)
    with wave.open(buffer, "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 24000
        n_frames = wf.getnframes()
        assert n_frames > 0


def test_voice_copilot_speak_feedback():
    copilot = AIVoiceCopilot.get_instance()
    audio_data = copilot.speak_intent_feedback("start_warmup", details="Profil 1")

    assert isinstance(audio_data, (bytes, bytearray))
    assert len(audio_data) > 500
    assert audio_data.startswith(b"RIFF")
