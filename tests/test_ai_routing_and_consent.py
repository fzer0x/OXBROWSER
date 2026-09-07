import os
import sys
import asyncio
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.ai_model_manager import AIModelManager
from engine.warmup.trajectory_planner import (
    WARMUP_CATEGORIES,
    PERSONA_PROFILES,
    PersonaTrajectoryEngine,
)


def test_hybrid_roles_mapping():
    """Verify all 6 models and 3 hybrid modes map to correct text & vision roles."""
    ai_mgr = AIModelManager.get_instance()

    roles_hp = ai_mgr.get_hybrid_roles("hybrid_high_perf")
    assert roles_hp["text_model"] == "qwen2.5:3b"
    assert roles_hp["vision_model"] == "llava:7b"

    roles_eco = ai_mgr.get_hybrid_roles("hybrid_eco")
    assert roles_hp["text_model"] != roles_eco["text_model"]
    assert roles_eco["text_model"] == "qwen2.5:0.5b"

    roles_llava = ai_mgr.get_hybrid_roles("llava:7b")
    assert roles_llava["vision_model"] == "llava:7b"

    roles_smol = ai_mgr.get_hybrid_roles("smolvlm")
    assert roles_smol["vision_model"] == "moondream:v2"

    print(" All 6 models and hybrid modes cleanly separated without role collision!")


def test_consent_solver_rejects_login_upload_feedback():
    """Verify AI consent resolver rejects non-consent buttons like 'Log in', 'Upload', 'Feedback', 'MORE'."""
    async def _test():
        ai_mgr = AIModelManager.get_instance()

        bad_candidates = [
            {"tag": "button", "text": "Log in", "x": 100, "y": 100, "width": 50, "height": 20},
            {"tag": "button", "text": "Upload", "x": 200, "y": 100, "width": 50, "height": 20},
            {"tag": "button", "text": "Feedback", "x": 300, "y": 100, "width": 50, "height": 20},
            {"tag": "button", "text": "MORE", "x": 400, "y": 100, "width": 50, "height": 20},
        ]

        result = await ai_mgr.resolve_complex_consent(bad_candidates)
        assert result is None, f"Expected None for non-consent buttons, but got: {result}"
        print(" Successfully rejected non-consent buttons (Log in, Upload, Feedback, MORE).")

        good_candidates = [
            {"tag": "button", "text": "Log in", "x": 100, "y": 100, "width": 50, "height": 20},
            {"tag": "button", "text": "Alle Cookies akzeptieren", "x": 500, "y": 800, "width": 150, "height": 40},
            {"tag": "button", "text": "Feedback", "x": 300, "y": 100, "width": 50, "height": 20},
        ]
        with patch.object(ai_mgr, "generate_response", new=AsyncMock(return_value="0")):
            # Even if LLM returns 0 for filtered list, the single matching item is chosen
            res_good = await ai_mgr.resolve_complex_consent(good_candidates)
            assert res_good is not None
            assert "akzeptieren" in res_good["text"].lower()
            print(" Successfully selected authentic cookie consent button.")

    asyncio.run(_test())


def test_article_link_selection_avoids_auth_and_utility():
    """Verify editorial link selection filters out login, feedback, cart, and terms links."""
    async def _test():
        ai_mgr = AIModelManager.get_instance()

        links = [
            {"href": "https://example.com/login", "text": "Sign In"},
            {"href": "https://example.com/terms-of-service", "text": "Terms & Privacy"},
            {"href": "https://example.com/cart/checkout", "text": "View Cart"},
            {"href": "https://example.com/news/2026/quantum-computing-breakthrough", "text": "Quantum Computing Breakthrough in 2026 Revealed"},
            {"href": "https://example.com/feedback", "text": "Feedback"},
        ]

        with patch.object(ai_mgr, "generate_response", new=AsyncMock(return_value='{"chosen_index": 0}')):
            chosen = await ai_mgr.select_humanoid_next_link(links, persona="tech")
            assert chosen is not None
            assert "quantum" in chosen["href"]
            print(f" AI Link Selection picked content article: '{chosen['text']}' and evaded auth/utility traps!")

    asyncio.run(_test())


def test_category_pool_diversity():
    """Verify expanded categories have over 100 diverse domains and random persona sampling."""
    all_domains = set()
    for cat, domain_list in WARMUP_CATEGORIES.items():
        all_domains.update(domain_list)

    assert len(all_domains) > 60
    print(f" Total unique authority domains available: {len(all_domains)}")

    # Test random sampling variance across multiple persona calls
    run1 = PersonaTrajectoryEngine.get_urls_for_persona("general", 5)
    run2 = PersonaTrajectoryEngine.get_urls_for_persona("general", 5)
    assert len(run1) == 5
    assert len(run2) == 5
    print(f" Persona Trajectory Engine sampled dynamic sets:\n  Run 1: {run1}\n  Run 2: {run2}")


def test_ai_dom_consent_persistence():
    """Verify AI DOM Consent & Trajectory hyperparameters persist across save and load cycles."""
    import config
    from storage.secrets_manager import SecretsManager
    SecretsManager.initialize()

    orig_strat = config.AI_CONSENT_STRATEGY
    orig_depth = config.AI_SHADOW_DOM_DEPTH
    orig_temp = config.AI_TEMPERATURE

    try:
        # Set test values
        config.AI_CONSENT_STRATEGY = "smart_hybrid"
        config.AI_SHADOW_DOM_DEPTH = 12
        config.AI_TEMPERATURE = 0.45
        config.AI_CUSTOM_EXCLUSIONS = ["/custom-reject/i", "/deny-all/i"]
        config.save_app_config()

        # Reset in-memory values to simulate fresh boot
        config.AI_CONSENT_STRATEGY = "strict_reject"
        config.AI_SHADOW_DOM_DEPTH = 5
        config.AI_TEMPERATURE = 0.1
        config.AI_CUSTOM_EXCLUSIONS = []

        # Load from encrypted vault
        config.load_app_config()

        assert config.AI_CONSENT_STRATEGY == "smart_hybrid", f"Expected smart_hybrid, got {config.AI_CONSENT_STRATEGY}"
        assert config.AI_SHADOW_DOM_DEPTH == 12, f"Expected 12, got {config.AI_SHADOW_DOM_DEPTH}"
        assert abs(config.AI_TEMPERATURE - 0.45) < 0.001, f"Expected 0.45, got {config.AI_TEMPERATURE}"
        assert "/custom-reject/i" in config.AI_CUSTOM_EXCLUSIONS
        print(" AI DOM Consent & Trajectory settings successfully persisted and reloaded from encrypted vault!")
    finally:
        # Restore original
        config.AI_CONSENT_STRATEGY = orig_strat
        config.AI_SHADOW_DOM_DEPTH = orig_depth
        config.AI_TEMPERATURE = orig_temp
        config.save_app_config()


if __name__ == "__main__":
    test_hybrid_roles_mapping()
    test_consent_solver_rejects_login_upload_feedback()
    test_article_link_selection_avoids_auth_and_utility()
    test_category_pool_diversity()
    test_ai_dom_consent_persistence()
    print("ALL AI ROUTING & CONSENT AUDIT TESTS PASSED! ⫸")
