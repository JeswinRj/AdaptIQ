"""Adaptive quiz engine: generation, grading with educational feedback,
spaced-repetition revision.

- Difficulty adapts to the student's recent quiz record (and content level).
- Questions are generated fresh each time; recent question stems are sent
  back to the model with a do-not-repeat instruction.
- Grading explains WHY, names the concept tested and the likely
  misconception — never a bare right/wrong.
- Weekly revision quizzes mix the current topic with older completed
  chapters and the concepts the student got wrong most often.

Provider-agnostic: all AI calls go through the ai_client abstraction.
"""
import re
from collections import Counter

from src.ai_integration.mentor import (MATH_STYLE, normalize_answer,
                                       parse_json_block)

QUESTION_TYPES = ("mcq", "tf", "fill", "numeric", "short")
MICRO_SIZE = 6
REVISION_SIZE = 8
QUIZ_XP_PERFECT = 40
QUIZ_XP_PASS = 15          # >= 60%


def difficulty_for(user: dict, history: list) -> tuple:
    """(label, instruction) from content level + last three quiz scores."""
    recent = history[-3:]
    avg = (sum(q["score"] / max(q["total"], 1) for q in recent) / len(recent)
           if recent else None)
    base = {"basic": "gentle", "intermediate": "standard",
            "advanced": "challenging"}.get(user.get("content_level"),
                                           "standard")
    if avg is not None and avg >= 0.8:
        return ("harder",
                "The student has been scoring highly: raise the difficulty, "
                "include one mixed-topic problem and one higher-order "
                "reasoning question.")
    if avg is not None and avg <= 0.4:
        return ("gentler",
                "The student has been struggling: reduce complexity, use "
                "scaffolded questions that build up in small steps, and "
                "reinforce prerequisite concepts.")
    return (base, f"Difficulty: {base}, with a gradual ramp across the quiz.")


def wrong_concept_counts(user: dict) -> Counter:
    c = Counter()
    for q in user.get("quiz_history", []):
        for concept in q.get("wrong_concepts", []):
            c[concept] += 1
    return c


def recent_stems(user: dict, n: int = 24) -> list:
    stems = []
    for q in user.get("quiz_history", []):
        stems.extend(q.get("stems", []))
    return stems[-n:]


def revision_topics(user: dict, course: dict, current_index=None) -> list:
    """Spaced repetition: oldest completed chapters resurface first, plus
    the current chapter and frequently-wrong concepts (added by caller)."""
    done = user.get("completed_chapters", [])
    chapters = course["chapters"]
    topics = []
    if current_index is not None and current_index < len(chapters):
        topics.append(chapters[current_index]["name"])
    for i in done[:3]:                       # earliest-completed = most decayed
        if i < len(chapters) and chapters[i]["name"] not in topics:
            topics.append(chapters[i]["name"])
    for i in reversed(done[-2:]):            # plus the freshest, to consolidate
        if i < len(chapters) and chapters[i]["name"] not in topics:
            topics.append(chapters[i]["name"])
    return topics[:5]


def build_quiz_prompt(user: dict, grade: str, topics: list, kind: str,
                      difficulty_note: str, weak_concepts: list,
                      avoid_stems: list, size: int, audience: str) -> str:
    style = (" Very simple language, one short sentence per question."
             if audience == "simplified" else "")
    weak = (f" Include at least one question on each of these previously "
            f"missed concepts: {', '.join(weak_concepts[:3])}."
            if weak_concepts else "")
    avoid = (" Do NOT reuse these earlier questions: "
             + " | ".join(avoid_stems[-12:]) if avoid_stems else "")
    return (
        f"Create a {size}-question {kind} quiz for CBSE Class {grade} "
        f"Mathematics on: {', '.join(topics)}. {difficulty_note}{weak}"
        f"{style}{avoid}{MATH_STYLE} "
        "Mix question types: mcq, tf (true/false), fill (fill in the "
        "blank), numeric, short (short conceptual/application answer). "
        "Use fresh numbers and contexts. Return STRICT JSON only, no "
        "markdown fences: "
        '{"questions": [{"type": "mcq", "q": "...", '
        '"options": ["...", "...", "...", "..."], "answer": "exact correct '
        'option text (or the answer string for other types)", '
        '"concept": "the concept tested, 2-5 words", '
        '"explanation": "why this is the answer + the common misconception"'
        "}]}")


def parse_quiz(text: str, size_cap: int = 10):
    data = parse_json_block(text)
    if not isinstance(data, dict) or not isinstance(data.get("questions"),
                                                    list):
        return None
    out = []
    for q in data["questions"][:size_cap]:
        if not isinstance(q, dict) or not q.get("q") or "answer" not in q:
            continue
        qtype = q.get("type", "short")
        if qtype not in QUESTION_TYPES:
            qtype = "short"
        item = {"type": qtype, "q": str(q["q"]), "answer": str(q["answer"]),
                "concept": str(q.get("concept", "general")),
                "explanation": str(q.get("explanation", ""))}
        if qtype == "mcq":
            opts = [str(o) for o in (q.get("options") or []) if str(o).strip()]
            if len(opts) < 2:
                continue
            item["options"] = opts[:5]
        out.append(item)
    return out or None


def grade_quiz(questions: list, answers: dict, judge=None) -> dict:
    """answers: {'q0': 'student text', ...}. judge: optional AI judge
    fn(question, expected, given) -> (bool, feedback) for short answers.
    Returns per-question feedback that teaches, plus totals."""
    results, score = [], 0
    for i, q in enumerate(questions):
        given = (answers.get(f"q{i}") or "").strip()
        if q["type"] == "short" and judge and given:
            ok, extra = judge(q["q"], q["answer"], given)
        else:
            ok = _auto_correct(q, given)
            extra = ""
        if ok:
            score += 1
        results.append({
            "q": q["q"], "type": q["type"], "given": given,
            "expected": q["answer"], "correct": ok,
            "concept": q["concept"],
            "feedback": (q.get("explanation") or "") +
                        (f"\n{extra}" if extra else "")})
    wrong_concepts = [r["concept"] for r in results if not r["correct"]]
    return {"results": results, "score": score, "total": len(questions),
            "wrong_concepts": wrong_concepts,
            "stems": [q["q"][:60] for q in questions]}


def _auto_correct(q: dict, given: str) -> bool:
    e, g = normalize_answer(q["answer"]), normalize_answer(given)
    if not g:
        return False
    if q["type"] == "tf":
        truthy = {"true", "t", "yes"}
        return (e in truthy) == (g in truthy)
    if q["type"] == "numeric":
        en, gn = _first_number(e), _first_number(g)
        if en is not None and gn is not None:
            return abs(en - gn) < 1e-6
    if e == g:
        return True
    return len(g) >= 2 and (g in e or e in g)


def _first_number(s: str):
    m = re.search(r"-?\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)?", s)
    if not m:
        return None
    tok = m.group(0)
    try:
        if "/" in tok:
            a, b = tok.split("/")
            return float(a) / float(b)
        return float(tok)
    except (ValueError, ZeroDivisionError):
        return None


def quiz_xp(score: int, total: int) -> int:
    if total and score == total:
        return QUIZ_XP_PERFECT
    if total and score / total >= 0.6:
        return QUIZ_XP_PASS
    return 5
