from pathlib import Path
import sys

SERVICE_ROOT = Path(__file__).resolve().parents[2]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

import realtime_voice_service as realtime_voice


def test_clamp_realtime_speed_respects_bounds():
    assert realtime_voice.clamp_realtime_speed(0.1) == 0.25
    assert realtime_voice.clamp_realtime_speed(2.5) == 1.5
    assert realtime_voice.clamp_realtime_speed(1.1) == 1.1


def test_build_cefr_level_instruction_uses_default_on_invalid_level():
    instruction = realtime_voice.build_cefr_level_instruction("invalid")
    assert "CEFR-niveau" in instruction
    assert realtime_voice.OPENAI_REALTIME_CEFR_LEVEL_DEFAULT in instruction


def test_build_dutch_system_message_contains_prompt_and_level(monkeypatch):
    monkeypatch.setattr(realtime_voice, "get_effective_system_prompt", lambda: "Test system prompt")

    message = realtime_voice.build_dutch_system_message("A2")
    content = message["item"]["content"][0]["text"]

    assert "Test system prompt" in content
    assert "CEFR-niveau A2" in content
