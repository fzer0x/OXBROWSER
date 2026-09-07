import os
import sys
import asyncio
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.ai_model_manager import AIModelManager


def test_vision_grounding_normalized_coords():
    async def _test():
        ai_mgr = AIModelManager.get_instance()

        mock_json_response = '{"center_x_norm": 0.5, "center_y_norm": 0.8}'
        with patch.object(ai_mgr, "generate_vision_response", new=AsyncMock(return_value=mock_json_response)):
            coords = await ai_mgr.ground_ui_element(
                screenshot_b64="fake_b64",
                query="accept cookies",
                viewport_width=1920,
                viewport_height=1080,
                vision_model="llava:7b"
            )
            assert coords is not None
            cx, cy = coords
            assert abs(cx - 960.0) < 1.0
            assert abs(cy - 864.0) < 1.0
            print(f" Normalized coords parsed successfully: ({cx:.1f}, {cy:.1f})")

    asyncio.run(_test())


def test_vision_grounding_box_coords():
    async def _test():
        ai_mgr = AIModelManager.get_instance()

        # 0-1000 scale bounding box format [ymin, xmin, ymax, xmax]
        mock_box_response = '{"box_2d": [700, 400, 900, 600]}'
        with patch.object(ai_mgr, "generate_vision_response", new=AsyncMock(return_value=mock_box_response)):
            coords = await ai_mgr.ground_ui_element(
                screenshot_b64="fake_b64",
                query="accept cookies",
                viewport_width=1000,
                viewport_height=1000,
                vision_model="llava:7b"
            )
            assert coords is not None
            cx, cy = coords
            assert abs(cx - 500.0) < 1.0
            assert abs(cy - 800.0) < 1.0
            print(f" Bounding box coordinates parsed and scaled successfully: ({cx:.1f}, {cy:.1f})")

    asyncio.run(_test())


if __name__ == "__main__":
    test_vision_grounding_normalized_coords()
    test_vision_grounding_box_coords()
    print("ALL PHASE 4 VISION GROUNDING TESTS PASSED! ⫸")
