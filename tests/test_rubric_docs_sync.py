"""Guard against drift between docs/questionnaire_and_scoring.md and rubric.py."""
from pathlib import Path

from src.preprocessing import rubric

DOCS = (Path(__file__).resolve().parents[1]
        / "docs" / "questionnaire_and_scoring.md").read_text()


def test_every_question_id_documented():
    for qid in rubric.ALL_QUESTIONS:
        assert qid in DOCS, f"Question {qid} missing from docs"


def test_every_mc_option_documented():
    for bank in (rubric.COGNITIVE_QUESTIONS, rubric.HABITS_QUESTIONS):
        for qid, q in bank.items():
            for option in q["options"]:
                assert option in DOCS, f"{qid} option {option!r} missing from docs"
    for option in rubric.REFLECTION_QUESTIONS["D3"]["options"]:
        assert option in DOCS
    for option in rubric.PERFORMANCE_QUESTIONS["E2"]["options"]:
        assert option in DOCS


def test_thresholds_documented():
    assert str(rubric.LOW_THRESHOLD) in DOCS
    assert str(rubric.HIGH_THRESHOLD) in DOCS
