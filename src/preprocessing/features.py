"""Feature engineering: questionnaire answers -> learner profile.

Implements docs/questionnaire_and_scoring.md exactly (constants imported
from rubric.py so code and spec cannot drift).

Profile keys:
    learning_method            memorizer | example_driven | conceptual |
                               visual_learner | practice_driven
    learning_pace              slow | moderate | fast
    break_frequency            low | medium | high
    engagement_preference      visual | auditory | kinesthetic | reading_writing
    problem_solving_style      analytical | pattern | procedural | visual | collaborative
    cognitive_complexity       0-1 (NLP over open answers)
    foundational_knowledge_score  0-100
    previous_marks             0-100
plus auxiliary: modality_scores, confidence, metacognition,
performance_gap, reflection_sentiment.
"""
from collections import Counter

from . import rubric
from . import nlp_features as nlp

# Stable encoders for the ML model — do not reorder.
ENGAGEMENT_ENCODING = {m: i for i, m in enumerate(rubric.MODALITIES)}
STYLE_ENCODING = {s: i for i, s in enumerate(rubric.PROBLEM_SOLVING_STYLES)}
METHOD_ENCODING = {m: i for i, m in enumerate(rubric.LEARNING_METHODS)}
PACE_ENCODING = {"slow": 0, "moderate": 1, "fast": 2}
BREAK_ENCODING = {"low": 0, "medium": 1, "high": 2}

ML_FEATURE_COLUMNS = [
    "learning_method", "learning_pace", "break_frequency",
    "engagement_preference", "problem_solving_style", "cognitive_complexity",
    "foundational_knowledge_score", "previous_marks",
]


def _score_knowledge(row):
    scores = []
    for qid, q in rubric.KNOWLEDGE_QUESTIONS.items():
        answer = str(row.get(qid, "") or "")
        pts = nlp.keyword_coverage(answer, q["keyword_groups"])  # 0-8
        pts += nlp.complexity_bonus(answer)                      # 0-2
        scores.append(min(pts, 10))
    return round(sum(scores) / len(scores) * 10, 1)


def _tally_votes(row):
    modality = Counter({m: 0 for m in rubric.MODALITIES})
    style_votes, method_votes = [], []
    for bank in (rubric.COGNITIVE_QUESTIONS, rubric.HABITS_QUESTIONS):
        for qid, q in bank.items():
            opt = q["options"].get(str(row.get(qid, "") or ""))
            if not opt:
                continue
            for m, pts in opt.get("modality", {}).items():
                modality[m] += pts
            if "style" in opt:
                style_votes.append((qid, opt["style"]))
            if "method" in opt:
                method_votes.append((qid, opt["method"]))
    d2 = str(row.get("D2", "") or "").lower()
    for m, kws in rubric.REFLECTION_QUESTIONS["D2"]["modality_keywords"].items():
        modality[m] += sum(1 for kw in kws if kw in d2)

    dominant = max(rubric.MODALITIES,
                   key=lambda m: (modality[m], -rubric.MODALITIES.index(m)))

    def _majority(votes, primary_qid, default, universe):
        if not votes:
            return default
        counts = Counter(v for _, v in votes)
        top = counts.most_common(1)[0][1]
        tied = {v for v, c in counts.items() if c == top}
        primary = next((v for qid, v in votes if qid == primary_qid), None)
        if primary in tied:
            return primary
        return min(tied, key=universe.index)

    style = _majority(style_votes, "B2", "analytical",
                      rubric.PROBLEM_SOLVING_STYLES)
    method = _majority(method_votes, "B1", "example_driven",
                       rubric.LEARNING_METHODS)
    # a strongly visual profile nudges the method label toward visual_learner
    if method != "visual_learner" and modality["visual"] >= 6:
        method = "visual_learner"
    return dict(modality), dominant, style, method


def _pace_and_breaks(row):
    pace_pts, break_pts, n = 0, 0, 0
    for qid, q in rubric.HABITS_QUESTIONS.items():
        opt = q["options"].get(str(row.get(qid, "") or ""))
        if not opt:
            continue
        pace_pts += opt.get("pace", 1)
        break_pts += opt.get("break", 1)
        n += 1
    if n == 0:
        return "moderate", "medium"
    return (rubric.PACE_LABELS[rubric.bucket(pace_pts / n)],
            rubric.BREAK_LABELS[rubric.bucket(break_pts / n)])


def build_feature_dict(row, previous_marks_default=60.0):
    """Transform one raw response row (dict-like) into the learner profile."""
    modality_scores, dominant, style, method = _tally_votes(row)
    pace, brk = _pace_and_breaks(row)

    open_answers = " ".join(
        str(row.get(q, "") or "") for q in ("A1", "A2", "A3", "D1", "D2"))
    cognitive_complexity = nlp.sentence_complexity(open_answers)

    d1 = str(row.get("D1", "") or "")
    metacognition = nlp.keyword_coverage(
        d1, rubric.REFLECTION_QUESTIONS["D1"]["keyword_groups"],
        points_per_group=1)

    d3_opt = rubric.REFLECTION_QUESTIONS["D3"]["options"].get(
        str(row.get("D3", "") or ""), {})
    e2_opt = rubric.PERFORMANCE_QUESTIONS["E2"]["options"].get(
        str(row.get("E2", "") or ""), {})

    try:
        previous_marks = float(row.get("E1", None))
        if not 0 <= previous_marks <= 100:
            raise ValueError
    except (TypeError, ValueError):
        previous_marks = previous_marks_default

    return {
        "learning_method": method,
        "learning_pace": pace,
        "break_frequency": brk,
        "engagement_preference": dominant,
        "problem_solving_style": style,
        "cognitive_complexity": cognitive_complexity,
        "foundational_knowledge_score": _score_knowledge(row),
        "previous_marks": round(previous_marks, 1),
        "modality_scores": modality_scores,
        "confidence": d3_opt.get("confidence", 1),
        "metacognition": metacognition,
        "performance_gap": e2_opt.get("gap", "conceptual"),
        "reflection_sentiment": nlp.sentiment(d1),
    }


def encode_for_ml(features: dict):
    """Numeric vector in ML_FEATURE_COLUMNS order for the Decision Tree."""
    return [
        METHOD_ENCODING[features["learning_method"]],
        PACE_ENCODING[features["learning_pace"]],
        BREAK_ENCODING[features["break_frequency"]],
        ENGAGEMENT_ENCODING[features["engagement_preference"]],
        STYLE_ENCODING[features["problem_solving_style"]],
        features["cognitive_complexity"],
        features["foundational_knowledge_score"],
        features["previous_marks"],
    ]
