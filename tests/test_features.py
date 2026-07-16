from src.preprocessing import nlp_features as nlp
from src.preprocessing.features import (ML_FEATURE_COLUMNS, build_feature_dict,
                                        encode_for_ml)


def test_worked_example_matches_docs(sample_row):
    feats = build_feature_dict(sample_row)
    assert feats["learning_method"] == "visual_learner"
    assert feats["engagement_preference"] == "visual"
    assert feats["problem_solving_style"] == "visual"
    assert feats["learning_pace"] == "moderate"   # pace mean 0.75
    assert feats["break_frequency"] == "high"     # break mean 1.75
    assert feats["previous_marks"] == 72.0
    assert feats["performance_gap"] == "speed"
    assert feats["confidence"] == 2
    assert feats["metacognition"] >= 2
    assert feats["foundational_knowledge_score"] >= 60  # strong open answers
    assert 0 <= feats["cognitive_complexity"] <= 1


def test_memorizer_detection(sample_row):
    sample_row["B1"] = "Memorize it so I can use it in the exam"
    sample_row["B3"] = "Re-read my formula list until I know it by heart"
    sample_row["B4"] = "Read a written explanation with the rules"
    sample_row["D2"] = "I wrote my own summary notes from the textbook and it clicked."
    feats = build_feature_dict(sample_row)
    assert feats["learning_method"] == "memorizer"


def test_missing_marks_imputed(sample_row):
    sample_row["E1"] = ""
    feats = build_feature_dict(sample_row, previous_marks_default=61.5)
    assert feats["previous_marks"] == 61.5


def test_unanswered_row_still_produces_features():
    feats = build_feature_dict({})
    assert feats["learning_pace"] == "moderate"
    assert feats["break_frequency"] == "medium"
    assert feats["learning_method"] == "example_driven"
    assert feats["foundational_knowledge_score"] == 0.0


def test_encode_for_ml_is_numeric(sample_row):
    vec = encode_for_ml(build_feature_dict(sample_row))
    assert len(vec) == len(ML_FEATURE_COLUMNS)
    assert all(isinstance(v, (int, float)) for v in vec)


def test_nlp_primitives():
    kw = nlp.keyword_coverage("Slope is rise over run", [["rise"], ["run"]])
    assert kw == 4
    assert nlp.sentence_complexity("") == 0.0
    rich = ("The slope measures the rate of change because it compares rise "
            "and run, and therefore it tells you the direction of the line.")
    assert nlp.sentence_complexity(rich) > nlp.sentence_complexity("It is m.")
    assert nlp.sentiment("I love solving these, maths is great") > 0
    dens = nlp.tfidf_density(["slope is rise over run", "a function maps inputs", ""])
    assert len(dens) == 3 and all(d >= 0 for d in dens)
