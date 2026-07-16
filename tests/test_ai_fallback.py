from src.ai_integration.ai_client import (OFFLINE_MESSAGE, build_prompt,
                                          get_ai_tips)
from src.preprocessing.features import build_feature_dict
from src.rules_engine.engine import build_teaching_plan


def _plan(sample_row, level="intermediate"):
    feats = build_feature_dict(sample_row)
    return feats, build_teaching_plan(feats, level, live_resources=False)


def test_no_provider_gives_clear_fallback(sample_row):
    feats, plan = _plan(sample_row)
    result = get_ai_tips(feats, "intermediate", plan, provider="")
    assert result["available"] is False
    assert result["tips"] == []
    assert result["message"] == OFFLINE_MESSAGE


def test_provider_without_key_is_explicit(sample_row):
    feats, plan = _plan(sample_row)
    result = get_ai_tips(feats, "intermediate", plan, provider="gemini", api_key="")
    assert result["available"] is False
    assert "AI_API_KEY is empty" in result["message"]


def test_unknown_provider_is_explicit(sample_row):
    feats, plan = _plan(sample_row)
    result = get_ai_tips(feats, "intermediate", plan, provider="skynet",
                         api_key="x")
    assert result["available"] is False
    assert "unknown AI_PROVIDER" in result["message"]


def test_prompt_contains_task_and_plan(sample_row):
    feats, plan = _plan(sample_row, "advanced")
    task = {"subject": "Biology", "topic": "Photosynthesis", "difficulty": "basic"}
    prompt = build_prompt(feats, "advanced", plan, task)
    assert "Photosynthesis" in prompt and "Biology" in prompt
    assert feats["learning_pace"] in prompt
    assert plan["lesson_pacing"]["label"] in prompt


def test_simplified_audience_changes_prompt(sample_row):
    feats, plan = _plan(sample_row)
    standard = build_prompt(feats, "basic", plan, audience="standard")
    simplified = build_prompt(feats, "basic", plan, audience="simplified")
    assert "reading age" in simplified and "no metaphors" in simplified
    assert "reading age" not in standard
