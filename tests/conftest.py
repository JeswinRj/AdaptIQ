import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from src.preprocessing import rubric  # noqa: E402


@pytest.fixture(autouse=True)
def hermetic_ai():
    """Tests never call live AI providers, regardless of the developer's .env
    (offline-fallback behaviour is part of the contract under test)."""
    old_provider, old_key = config.AI_PROVIDER, config.AI_API_KEY
    config.AI_PROVIDER, config.AI_API_KEY = "", ""
    yield
    config.AI_PROVIDER, config.AI_API_KEY = old_provider, old_key


@pytest.fixture
def sample_row():
    """The worked example from docs/questionnaire_and_scoring.md
    (a visual example: visual_learner method, visual modality)."""
    return {
        "A1": "A function is a rule that maps every input x to exactly one "
              "output value, like a machine with a domain and range.",
        "A2": "Because division is the inverse of multiplication and no number "
              "times zero gives the original, so it is undefined.",
        "A3": "The slope tells you the steepness, the rate of change, rise over run.",
        "B1": "Draw a picture or graph of what it means",
        "B2": "Draw a diagram or graph of the situation",
        "B3": "Make colourful summary sheets, graphs and mind-maps",
        "B4": "Watch an animation of the graph shifting",
        "C1": "Split the topic over two shorter sessions",
        "C2": "10–20 minutes",
        "C3": "Sometimes",
        "C4": "Somewhere I can move around or stand",
        "D1": "When I can explain it to a friend and test myself with practice questions.",
        "D2": "I finally understood trigonometry after watching a video with a "
              "graph animation of the unit circle.",
        "D3": "Mostly prepared, a few doubts",
        "E1": 72.0,
        "E2": "I ran out of time",
    }


def full_answers():
    """A complete, valid answer set for the in-app questionnaire form."""
    answers = {}
    for bank in (rubric.COGNITIVE_QUESTIONS, rubric.HABITS_QUESTIONS):
        for qid, q in bank.items():
            answers[qid] = next(iter(q["options"]))
    answers["D3"] = next(iter(rubric.REFLECTION_QUESTIONS["D3"]["options"]))
    answers["E2"] = next(iter(rubric.PERFORMANCE_QUESTIONS["E2"]["options"]))
    answers.update({
        "A1": "A function maps each input to exactly one output.",
        "A2": "There is no number that multiplied by zero gives it back, so it is undefined.",
        "A3": "It tells you the steepness of the line, rise over run.",
        "D1": "When I can explain it and solve problems without help.",
        "D2": "It clicked when I worked through practice problems myself.",
        "E1": "68",
    })
    return answers
