import config
from scripts.generate_synthetic_data import generate
from src.curriculum import cbse_math
from src.ml.predictor import predict_content_level
from src.notes.summarizer import summarize
from src.preprocessing.features import build_feature_dict
from src.rules_engine.engine import (build_teaching_plan, learner_summary,
                                     persona_for)


def test_generator_shape_and_labels():
    df = generate(rows=30, seed=7)
    assert len(df) == 30
    assert set(df["content_level"]) <= {"basic", "intermediate", "advanced"}
    for col in ("student_id", "A1", "B1", "C1", "D1", "E1", "E2"):
        assert col in df.columns


def test_saved_model_predicts_valid_class(sample_row):
    feats = build_feature_dict(sample_row)
    level = predict_content_level(feats, config.MODEL_PATH)
    assert level in {"basic", "intermediate", "advanced"}


def test_plan_reflects_learner_method(sample_row):
    feats = build_feature_dict(sample_row)
    plan = build_teaching_plan(feats, "intermediate",
                               task={"subject": "Mathematics",
                                     "topic": "Limits and Derivatives",
                                     "difficulty": ""},
                               live_resources=False)
    assert plan["learner_method"]["label"] == "Visual learner"
    assert plan["break_schedule"]["work_minutes"] == 15   # high break need
    assert any("Limits and Derivatives" in s["text"] for s in plan["steps"])
    for step in plan["steps"]:
        assert step["simple_text"] != step["text"]
    # persona + hedged summary (never a fixed VAK label)
    assert persona_for(feats)["name"] == "The Explorer"
    summary = learner_summary(feats)
    assert summary.startswith("Based on your responses")
    assert "visual learner" not in summary.lower()


def test_curriculum_structure():
    for cid in ("cbse-11-math", "cbse-12-math"):
        course = cbse_math.get_course(cid)
        assert len(course["chapters"]) >= 13
        for ch in course["chapters"]:
            assert ch["domain"] in cbse_math.DOMAINS
            assert ch["topics"] and ch["wiki"]
        links = cbse_math.chapter_links(cid, course["chapters"][0], "visual")
        assert any("ncert" in url for _, url in links)
        assert any("youtube" in url for _, url in links)


def test_domain_progress():
    prog = cbse_math.domain_progress("cbse-12-math", [])
    assert all(v == 0 for v in prog.values())
    # complete every calculus chapter of class 12
    course = cbse_math.get_course("cbse-12-math")
    calc = [i for i, ch in enumerate(course["chapters"])
            if ch["domain"] == "Calculus"]
    prog = cbse_math.domain_progress("cbse-12-math", calc)
    assert prog["Calculus"] == 100
    assert prog["Algebra"] == 0


def test_notes_summarizer():
    text = ("A derivative measures the rate of change of a function. "
            "The derivative of a constant is zero. "
            "My friend brought samosas to class today. "
            "The chain rule lets you differentiate composite functions. "
            "Derivatives of polynomials follow the power rule. "
            "The weather was hot. "
            "Maxima and minima are found where the derivative is zero.")
    summary = summarize(text, max_sentences=3)
    sentences = [s for s in summary.split(". ") if s]
    assert len(sentences) <= 4
    assert "derivative" in summary.lower()
    assert summarize("", 3) == ""
