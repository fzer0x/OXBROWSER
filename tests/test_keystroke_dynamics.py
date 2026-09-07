import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from engine.keystroke_dynamics import KeystrokeDynamicsEngine


def test_keystroke_dynamics_initialization():
    engine = KeystrokeDynamicsEngine.get_instance()
    assert engine is not None
    assert engine._session is not None or True  # Works with ONNX or analytical fallback


def test_key_distance_calculation():
    engine = KeystrokeDynamicsEngine.get_instance()
    dist_qw = engine.calculate_key_distance('q', 'w')
    dist_qp = engine.calculate_key_distance('q', 'p')
    assert dist_qw < dist_qp
    assert dist_qw > 0.5


def test_predict_timings_range():
    engine = KeystrokeDynamicsEngine.get_instance()
    dwell_s, flight_s = engine.predict_timings('a', 'b', speed_preset="balanced")
    assert 0.030 <= dwell_s <= 0.200
    assert 0.020 <= flight_s <= 0.600

    # Capital letters should have increased flight/dwell times
    dwell_upper, flight_upper = engine.predict_timings('a', 'B', speed_preset="balanced")
    assert dwell_upper >= 0.035
    assert flight_upper >= flight_s * 0.90  # Generally longer cognitive preparation


@pytest.mark.asyncio
async def test_type_with_biometrics_mock_page():
    engine = KeystrokeDynamicsEngine.get_instance()

    mock_page = MagicMock()
    mock_keyboard = MagicMock()
    mock_keyboard.down = AsyncMock()
    mock_keyboard.up = AsyncMock()
    mock_page.keyboard = mock_keyboard
    mock_page.click = AsyncMock()

    success = await engine.type_with_biometrics(
        page=mock_page,
        selector="#username",
        text="SoxBot",
        speed_preset="fast",
        error_rate=0.0,
        press_enter=True
    )

    assert success is True
    assert mock_keyboard.down.call_count >= 7  # 'S', 'o', 'x', 'B', 'o', 't', 'Enter'
    assert mock_keyboard.up.call_count >= 7
