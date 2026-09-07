import os
import sys
import asyncio
import unittest
from unittest.mock import MagicMock

# Ensure mocks for playwright if not installed in current environment
if "playwright" not in sys.modules:
    mock_pw = MagicMock()
    mock_pw_async = MagicMock()
    mock_pw.async_api = mock_pw_async
    sys.modules["playwright"] = mock_pw
    sys.modules["playwright.async_api"] = mock_pw_async

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.cookie_warmup import (
    CookieWarmupRobot as LegacyRobot,
    WarmupConfig as LegacyConfig,
    WARMUP_CATEGORIES,
    PERSONA_PROFILES,
    BiomechanicalMotor,
    BiGramTypingEngine,
    WarmupKnowledgeStore,
    LoginAuthDetector,
)
from engine.warmup import (
    CookieWarmupRobot,
    WarmupConfig,
    SemanticBannerResolver,
)
from engine.events import AsyncEventBus


def test_import_compatibility():
    """Verify that both legacy facade and new modular imports work identically."""
    assert LegacyRobot is CookieWarmupRobot
    assert LegacyConfig is WarmupConfig
    assert "ecommerce" in WARMUP_CATEGORIES
    assert "general" in PERSONA_PROFILES


def test_biomechanical_motor_math():
    """Verify Min-Jerk trajectory calculations and Fitts duration."""
    start = (100.0, 100.0)
    end = (500.0, 400.0)
    duration = BiomechanicalMotor.calculate_fitts_duration(500.0, target_width=40.0)
    assert 0.14 <= duration <= 3.0

    path = BiomechanicalMotor.generate_min_jerk_path(start, end, duration, num_points=20)
    assert len(path) >= 20
    assert isinstance(path[0], tuple)
    assert len(path[0]) == 2


def test_bigram_typing_distance():
    """Verify QWERTY spatial distance logic."""
    d_same = BiGramTypingEngine.get_key_distance('a', 'a')
    d_adjacent = BiGramTypingEngine.get_key_distance('a', 's')
    d_far = BiGramTypingEngine.get_key_distance('q', 'p')
    assert d_same == 0.0
    assert d_adjacent > 0.0
    assert d_far > d_adjacent


def test_login_auth_detector():
    """Verify login/auth URL and keyword pattern matching."""
    assert LoginAuthDetector.url_matches_auth_pattern("https://example.com/user/login")
    assert LoginAuthDetector.url_matches_auth_pattern("https://example.com/checkout/warenkorb")
    assert not LoginAuthDetector.url_matches_auth_pattern("https://example.com/blog/latest-news")
    assert LoginAuthDetector.link_text_matches_auth_pattern("Sign In to Account")
    assert LoginAuthDetector.link_text_matches_auth_pattern("Jetzt Anmelden")


def test_knowledge_store():
    """Verify WarmupKnowledgeStore singleton behavior and stats."""
    store = WarmupKnowledgeStore.get_instance()
    initial_stats = store.get_stats()
    assert isinstance(initial_stats, dict)
    assert "total_traps_recorded" in initial_stats


def test_event_bus():
    """Verify AsyncEventBus event dispatching."""
    async def _async_test():
        bus = AsyncEventBus.get_instance()
        received_events = []

        def on_event(**kwargs):
            received_events.append(kwargs)

        bus.subscribe("test_event", on_event)
        await bus.emit("test_event", profile_id="prof_123", status="ok")
        await asyncio.sleep(0.05)
        
        assert len(received_events) == 1
        assert received_events[0]["profile_id"] == "prof_123"
        assert received_events[0]["status"] == "ok"

        bus.unsubscribe("test_event", on_event)
        await bus.emit("test_event", profile_id="prof_456")
        await asyncio.sleep(0.05)
        assert len(received_events) == 1

    asyncio.run(_async_test())


if __name__ == "__main__":
    test_import_compatibility()
    test_biomechanical_motor_math()
    test_bigram_typing_distance()
    test_login_auth_detector()
    test_knowledge_store()
    test_event_bus()
    print("ALL PHASE 1 REFACTORING TESTS PASSED! ⫸")

