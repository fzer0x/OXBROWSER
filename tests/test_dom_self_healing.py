import pytest
from unittest.mock import AsyncMock, MagicMock
from engine.dom_self_healer import SelfHealingDOMEngine, HealedSelectorResult


def test_self_healing_dom_singleton():
    engine = SelfHealingDOMEngine.get_instance()
    assert engine is not None


def test_text_similarity():
    engine = SelfHealingDOMEngine.get_instance()
    sim_exact = engine._text_similarity("Accept All Cookies", "Accept All Cookies")
    sim_partial = engine._text_similarity("Accept All Cookies", "Accept All")
    sim_none = engine._text_similarity("Accept All Cookies", "Reject None")

    assert sim_exact == 1.0
    assert sim_partial >= 0.60
    assert sim_none < 0.20


def test_calculate_candidate_score_mutated_classes():
    engine = SelfHealingDOMEngine.get_instance()

    # Original broken selector was button#submit-order.btn-primary
    # Target element now has mutated hash classes and tag button
    cand = {
        "tag": "button",
        "id": "order-submit-btn_v2",
        "className": "btn-primary _3xK9a_mutated",
        "text": "Submit Order Now",
        "ariaLabel": "Submit Order",
        "role": "button",
        "selector": "button[aria-label='Submit Order']"
    }

    score, reasons = engine.calculate_candidate_score(
        cand,
        broken_selector="button#submit-order.btn-primary",
        expected_text="Submit Order"
    )

    assert score >= 0.70
    assert any("Tag matched" in r for r in reasons)
    assert any("Text similarity" in r for r in reasons)


@pytest.mark.asyncio
async def test_heal_selector_on_page():
    engine = SelfHealingDOMEngine.get_instance()

    mock_candidates = [
        {
            "tag": "div",
            "id": "header",
            "className": "nav",
            "text": "Home",
            "ariaLabel": "",
            "role": "",
            "selector": "#header"
        },
        {
            "tag": "button",
            "id": "cta-login-new",
            "className": "login-button-v2",
            "text": "Sign In to Account",
            "ariaLabel": "Sign In",
            "role": "button",
            "selector": "button#cta-login-new"
        }
    ]

    mock_page = MagicMock()
    mock_page.evaluate = AsyncMock(return_value=mock_candidates)

    result = await engine.heal_selector(
        page=mock_page,
        broken_selector="button#login-btn",
        expected_text="Sign In",
        min_confidence=0.40
    )

    assert result.is_healed is True
    assert result.healed_selector == "button#cta-login-new"
    assert result.confidence >= 0.50
