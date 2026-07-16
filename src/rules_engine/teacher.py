"""Teacher-portal engine: teaching guides, lesson plans, class insights.

Everything here is deterministic and computed from real student records, so
the portal is fully functional offline. When an AI provider is configured
the app layers richer AI-generated content on top (never instead).
"""
from src.rules_engine.engine import BREAK_RULES, METHOD_RULES, PERSONAS

STATUS_ORDER = ["needs support", "disengaging", "on track", "excelling"]


def student_status(record: dict, dims: dict, streak: int, progress_pct: int) -> str:
    """Flag for the roster: excelling / on track / needs support / disengaging."""
    if progress_pct >= 50 and dims["Confidence"] >= 60:
        return "excelling"
    if streak == 0 and progress_pct > 0:
        return "disengaging"
    if min(dims.values()) < 40 or (progress_pct < 15 and dims["Confidence"] < 50):
        return "needs support"
    return "on track"


def teaching_guide(profile: dict, content_level: str) -> list:
    """Adaptive teaching guide: (topic, recommendation, why) per learner.

    Written for teachers without an educational-psychology background;
    hedged, evidence-linked, and derived from the learner profile.
    """
    method = profile.get("learning_method", "example_driven")
    m = METHOD_RULES[method]
    brk = BREAK_RULES[profile["break_frequency"]]
    persona = PERSONAS[method]

    intro_by_method = {
        "conceptual": "Open with the underlying idea or derivation before any "
                      "procedure — this student disengages from unexplained rules.",
        "example_driven": "Open every new concept with one fully worked example "
                          "on the board before stating the general rule.",
        "practice_driven": "Give a first problem to attempt within the first five "
                           "minutes — this student learns through the attempt.",
        "memorizer": "Provide a clean structure up front (formula box, steps "
                     "list), then immediately attach one example to each rule.",
        "visual_learner": "Introduce concepts through a graph, diagram or "
                          "picture first; formal notation second.",
    }
    independence_by_method = {
        "conceptual": "after they can restate the idea in their own words",
        "example_driven": "after two guided examples, not before",
        "practice_driven": "early — but review their errors together afterwards",
        "memorizer": "once the structure is memorised, push transfer problems",
        "visual_learner": "once they have sketched the situation themselves",
    }
    homework = {"high": "Short and frequent: 20–30 minutes daily beats one long sheet.",
                "medium": "A standard 40-minute set, split into two parts.",
                "low": "One substantial problem set is fine; this student sustains focus."}

    difficulty = {
        "basic": "Start below frustration level: routine problems until fluency, "
                 "then one stretch question per set.",
        "intermediate": "Mix ~70% standard with 30% multi-step questions.",
        "advanced": "Lead with application/HOTS problems; routine drill only for speed.",
    }
    feedback = ("Feedback should be immediate and low-stakes — this student "
                "reported exam anxiety, so praise process before correcting answers."
                if profile.get("confidence", 2) <= 1 else
                "Direct, specific feedback works well; this student reports "
                "reasonable confidence.")

    return [
        ("Introducing concepts", intro_by_method[method],
         f"learning-approach answers match {persona['name']} ({persona['benefit']})"),
        ("Worked examples vs. independence",
         f"Move to independent problem solving {independence_by_method[method]}.",
         "based on how they said they handle new problems"),
        ("Pacing & breaks",
         f"Plan in {brk['work_minutes']}-minute blocks with "
         f"{brk['break_minutes']}-minute resets.",
         f"their responses suggest {profile['break_frequency']} break needs"),
        ("Homework volume", homework[profile["break_frequency"]],
         "matched to reported attention endurance"),
        ("Question difficulty", difficulty[content_level],
         f"current starting level is {content_level}"),
        ("Feedback style", feedback, "from the confidence self-report"),
        ("Revision", "Schedule recall after 2 days, then after a week; ask them "
         "to explain one idea back to you each cycle.",
         "spaced retrieval benefits every profile"),
        ("Motivation", m["watch_out"],
         f"the known failure mode of a {m['label'].lower()}"),
    ]


def lesson_plan(course: dict, chapter: dict, minutes: int, class_records: list) -> dict:
    """Rule-based lesson plan adapted to the class's dominant learner methods."""
    methods = [r["profile"].get("learning_method", "example_driven")
               for r in class_records if r.get("profile")]
    dominant = max(set(methods), key=methods.count) if methods else "example_driven"
    high_break = sum(1 for r in class_records if r.get("profile")
                     and r["profile"]["break_frequency"] == "high")
    needs_reset = class_records and high_break >= len(class_records) / 2

    def slot(pct):
        return max(5, round(minutes * pct / 5) * 5 // 1)

    open_move = {
        "conceptual": "Pose the why-question behind the chapter and collect hypotheses",
        "example_driven": "Work one complete example on the board, narrating each decision",
        "practice_driven": "Cold-open problem: two minutes of silent attempt, then discuss",
        "memorizer": "Put the chapter's structure (definitions/formula box) on the board",
        "visual_learner": "Open with a graph/diagram and ask what students notice",
    }[dominant]

    return {
        "chapter": chapter["name"],
        "duration": minutes,
        "objectives": [f"Students can explain and apply: {t}" for t in chapter["topics"][:3]],
        "sequence": [
            {"phase": "Recall warm-up", "minutes": slot(0.10),
             "detail": "Three quick retrieval questions from the previous chapter."},
            {"phase": "Concept introduction", "minutes": slot(0.25),
             "detail": open_move + f" — anchor on {chapter['topics'][0]}."},
            {"phase": "Guided practice", "minutes": slot(0.30),
             "detail": "Example-problem pairs: teacher does one, pairs do its twin."
                       + (" Insert a 3-minute reset midway — half the class profiles "
                          "show high break needs." if needs_reset else "")},
            {"phase": "Independent practice", "minutes": slot(0.20),
             "detail": "Tiered problem set (routine → multi-step); circulate to the "
                       "students flagged 'needs support'."},
            {"phase": "Formative check & close", "minutes": slot(0.15),
             "detail": "Two-question exit ticket on today's objective; one-line "
                       "self-rating of confidence."},
        ],
        "homework": f"Chapter exercise selection on {chapter['topics'][0]} "
                    "(20–30 min), plus one challenge question for early finishers.",
        "class_note": f"Dominant learning approach in this class: "
                      f"{METHOD_RULES[dominant]['label'].lower()} "
                      f"({methods.count(dominant) if methods else 0} of {len(methods)} students).",
    }


def quiz_set_analytics(quiz_set: dict, assignee_count: int) -> dict:
    """Aggregate a teacher quiz set's submissions into participation, a
    per-question difficulty breakdown, the most-missed concepts, and plain
    insight sentences. Pure computation — no AI, honest provenance."""
    questions = quiz_set.get("questions", [])
    subs = quiz_set.get("submissions", [])
    n = len(subs)
    assigned = max(assignee_count, n)          # never show >100% completion
    totals = [s["total"] for s in subs if s["total"]]
    scores = [s["score"] for s in subs]
    avg_pct = round(sum(scores) / sum(totals) * 100) if totals else 0

    # per-question: how many answered it correctly
    per_q = []
    from collections import Counter
    missed = Counter()
    for i, q in enumerate(questions):
        answered = [s for s in subs if i < len(s.get("results", []))]
        correct = sum(1 for s in answered if s["results"][i]["correct"])
        pct = round(correct / len(answered) * 100) if answered else 0
        per_q.append({
            "n": i + 1, "q": q.get("q", ""), "concept": q.get("concept", ""),
            "correct": correct, "answered": len(answered), "pct": pct})
        for s in answered:
            if not s["results"][i]["correct"]:
                missed[q.get("concept", "—")] += 1

    hardest = sorted([p for p in per_q if p["answered"]],
                     key=lambda p: p["pct"])[:3]

    insights = []
    pending = assigned - n
    if n == 0:
        insights.append("No submissions yet — results appear here as students "
                        "complete the quiz.")
    else:
        insights.append(
            f"{n} of {assigned} student{'s' if assigned != 1 else ''} "
            f"completed it · class average {avg_pct}%.")
        if pending > 0:
            insights.append(f"{pending} still to submit — a reminder or a near "
                            "due date usually helps.")
        if hardest and hardest[0]["pct"] <= 50:
            h = hardest[0]
            insights.append(
                f"Question {h['n']} ({h['concept']}) was the hardest — only "
                f"{h['pct']}% correct. Worth reteaching before moving on.")
        top_missed = missed.most_common(2)
        if top_missed:
            names = ", ".join(c for c, _ in top_missed)
            label = "concepts" if len(top_missed) > 1 else "concept"
            insights.append(f"Most-missed {label}: {names}.")
        if avg_pct >= 80 and n >= max(2, assigned // 2):
            insights.append("Strong results across the class — this cohort is "
                            "ready for extension material on this topic.")

    return {
        "submitted": n, "assigned": assigned, "pending": pending,
        "avg_pct": avg_pct, "per_q": per_q, "hardest": hardest,
        "missed": missed.most_common(6),
        "submissions": sorted(subs, key=lambda s: s["score"] / s["total"]
                              if s["total"] else 0, reverse=True),
        "insights": insights,
    }


def class_insights(rows: list) -> list:
    """Rule-derived insight sentences from real class data (AI-style surface,
    honest provenance — computed, not generated)."""
    insights = []
    if not rows:
        return ["No students have completed the assessment yet."]
    n = len(rows)
    low_focus = [r for r in rows if r["dims"]["Attention endurance"] < 50]
    if len(low_focus) >= max(2, n // 3):
        insights.append(
            f"{len(low_focus)} of {n} students show low attention endurance — "
            "consider chunking lessons into shorter segments with built-in resets.")
    anxious = [r for r in rows if r["dims"]["Confidence"] < 40]
    if anxious:
        names = ", ".join(r["user"]["name"] for r in anxious[:3])
        insights.append(
            f"Low reported confidence for {names} — favour untimed, low-stakes "
            "checks before graded assessments.")
    example_led = [r for r in rows
                   if r["user"]["profile"]["learning_method"] == "example_driven"]
    if len(example_led) >= n / 2:
        insights.append(
            "Most of this class works example-first — lead new topics with a "
            "fully worked example before stating general rules.")
    stalled = [r for r in rows if r["streak"] == 0 and r["progress"] > 0]
    if stalled:
        names = ", ".join(r["user"]["name"] for r in stalled[:3])
        insights.append(
            f"{names} started the course but have no recent activity — a small "
            "assigned task with a near due date usually restarts momentum.")
    ready = [r for r in rows if r["status"] == "excelling"]
    if ready:
        names = ", ".join(r["user"]["name"] for r in ready[:3])
        insights.append(
            f"{names} are progressing quickly — ready for extension/HOTS material.")
    return insights or ["Class data looks steady — no interventions suggested right now."]
