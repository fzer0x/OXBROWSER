import os
import shutil
import tempfile
import pytest
from engine.profile_episodic_memory import ProfileEpisodicMemory


def test_profile_episodic_memory_lifecycle():
    temp_dir = tempfile.mkdtemp()
    try:
        mem = ProfileEpisodicMemory(profile_id="test_profile_001", db_dir=temp_dir)

        # Record episodes
        ok1 = mem.record_episode(
            domain="reddit.com",
            topic="Renewable Energy & Solar",
            content="Advocated for residential rooftop solar panels and micro-inverters.",
            sentiment=0.8
        )
        ok2 = mem.record_episode(
            domain="bloomberg.com",
            topic="Semiconductor Industry",
            content="Analyzed EUV lithography advancements in European foundries.",
            sentiment=0.4
        )

        assert ok1 is True
        assert ok2 is True

        # Recall related episode
        recalled = mem.recall_episodes("What are your thoughts on solar power installation?", limit=1)
        assert len(recalled) == 1
        assert recalled[0].domain == "reddit.com"
        assert "solar" in recalled[0].topic.lower()
        assert recalled[0].similarity > 0.20

        # Memory prompt context
        prompt_ctx = mem.format_memory_context_prompt("solar panels")
        assert "EPISODIC PERSONA MEMORY" in prompt_ctx
        assert "reddit.com" in prompt_ctx

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
