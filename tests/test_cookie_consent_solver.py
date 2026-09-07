import os
import sys
import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock playwright if needed
if "playwright" not in sys.modules:
    sys.modules["playwright"] = MagicMock()
    sys.modules["playwright.async_api"] = MagicMock()

from engine.warmup.consent_solver import (
    SemanticBannerResolver,
    COMMON_COOKIE_SELECTORS,
    CHECK_CONSENT_CONTAINER_SCRIPT,
    AUTOWATCHER_SCRIPT,
)
from engine.warmup.orchestrator import CookieWarmupRobot, WarmupConfig


def test_common_selectors_comprehensive_coverage():
    """Verify COMMON_COOKIE_SELECTORS contains all industry standard CMPs."""
    selectors_str = " ".join(COMMON_COOKIE_SELECTORS)

    # Major CMPs
    assert "onetrust" in selectors_str
    assert "CybotCookiebotDialog" in selectors_str
    assert "uc-accept-all-button" in selectors_str or "uc-btn-accept" in selectors_str
    assert "didomi" in selectors_str
    assert "sp_choice_type_11" in selectors_str
    assert "qc-cmp2" in selectors_str
    assert "truste" in selectors_str
    assert "klaro" in selectors_str
    assert "_brlbs-btn-accept-all" in selectors_str
    assert "cky-btn-accept" in selectors_str
    assert "cmpwelcomebtnyes" in selectors_str or "cmpbntyes" in selectors_str
    assert "iubenda" in selectors_str
    assert "axeptio" in selectors_str
    assert "fides" in selectors_str
    assert "L2AGLb" in selectors_str

    print(" Verified comprehensive selector coverage for 15+ CMPs!")


def test_autowatcher_script_structure():
    """Verify AUTOWATCHER_SCRIPT contains active MutationObserver, Shadow DOM traversal, and heartbeat interval."""
    assert "MutationObserver" in AUTOWATCHER_SCRIPT
    assert "shadowRoot" in AUTOWATCHER_SCRIPT
    assert "setInterval" in AUTOWATCHER_SCRIPT
    assert "positiveAcceptRegex" in AUTOWATCHER_SCRIPT
    assert "exclusionRegex" in AUTOWATCHER_SCRIPT
    assert "__soxbot_consent_autowatcher_active" in AUTOWATCHER_SCRIPT
    print(" Autowatcher script structure verified!")


def test_direct_cmp_resolution():
    """Verify resolve_consent_banners succeeds when a direct CMP button is matched."""
    async def _test():
        mock_page = MagicMock()
        mock_page.frames = [mock_page]

        # Simulate evaluate returning direct match for OneTrust
        mock_evaluate = AsyncMock()
        mock_evaluate.return_value = {
            "found": True,
            "x": 300,
            "y": 600,
            "width": 120,
            "height": 40,
            "text": "Alle akzeptieren"
        }

        with patch("engine.warmup.human_motion.BiomechanicalMotor.move_mouse_humanoid", new=AsyncMock()):
            solved = await SemanticBannerResolver.resolve_consent_banners(mock_page, mock_evaluate)
            assert solved is True
            assert mock_evaluate.called
            print(" Direct CMP resolution successfully clicked!")

    asyncio.run(_test())


def test_multi_frame_iframe_resolution():
    """Verify resolve_consent_banners scans all child frames if direct CMP is inside an iframe."""
    async def _test():
        mock_page = MagicMock()
        mock_frame_main = MagicMock()
        mock_frame_iframe = MagicMock()
        mock_page.frames = [mock_frame_main, mock_frame_iframe]

        # Main frame returns None, child iframe returns found
        async def mock_eval(page: Any, script: str, *args: Any) -> Any:
            if page is mock_frame_iframe:
                return {
                    "found": True,
                    "x": 200,
                    "y": 400,
                    "width": 100,
                    "height": 35,
                    "text": "ACCEPT ALL"
                }
            return None

        with patch("engine.warmup.human_motion.BiomechanicalMotor.move_mouse_humanoid", new=AsyncMock()):
            solved = await SemanticBannerResolver.resolve_consent_banners(mock_page, mock_eval)
            assert solved is True
            print(" Iframe CMP consent resolution successfully traversed child frames!")

    asyncio.run(_test())


def test_attach_consent_autowatcher():
    """Verify attach_consent_autowatcher invokes evaluate and add_init_script."""
    async def _test():
        mock_page = MagicMock()
        mock_page.add_init_script = AsyncMock()
        mock_evaluate = AsyncMock()

        success = await SemanticBannerResolver.attach_consent_autowatcher(mock_page, mock_evaluate)
        assert success is True
        assert mock_page.add_init_script.called
        assert mock_evaluate.called
        print(" Autowatcher successfully attached via both add_init_script and evaluate!")

    asyncio.run(_test())


def test_dismiss_cookie_banners_adaptive_polling():
    """Verify CookieWarmupRobot.dismiss_cookie_banners executes retries, container check, and micro-scroll."""
    async def _test():
        launcher = MagicMock()
        robot = CookieWarmupRobot(launcher)

        mock_page = MagicMock()
        mock_page.frames = [mock_page]

        eval_calls = []

        async def mock_eval(page: Any, script: str, *args: Any) -> Any:
            eval_calls.append(script[:30])
            # Return True on 2nd attempt
            if len(eval_calls) >= 3:
                return {
                    "found": True,
                    "x": 250,
                    "y": 450,
                    "width": 80,
                    "height": 30,
                    "text": "Accept All Cookies"
                }
            return None

        robot._evaluate = mock_eval

        with patch("engine.warmup.human_motion.BiomechanicalMotor.move_mouse_humanoid", new=AsyncMock()):
            with patch("engine.warmup.consent_solver.SemanticBannerResolver.attach_consent_autowatcher", new=AsyncMock(return_value=True)):
                solved = await robot.dismiss_cookie_banners(mock_page, retries=3, delay=0.05)
                assert solved is True
                print(" Robot dismiss_cookie_banners adaptive polling & resolution verified!")

    asyncio.run(_test())


if __name__ == "__main__":
    test_common_selectors_comprehensive_coverage()
    test_autowatcher_script_structure()
    test_direct_cmp_resolution()
    test_multi_frame_iframe_resolution()
    test_attach_consent_autowatcher()
    test_dismiss_cookie_banners_adaptive_polling()
    print("ALL COOKIE CONSENT SOLVER TESTS PASSED! ⫸")
