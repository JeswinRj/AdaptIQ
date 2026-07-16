"""Rule-based recommendation engine (report §6.4), task-aware.

Produces the personalized teaching plan for the student's CHOSEN learning
task (any subject / topic / difficulty): lesson pacing, break schedule,
engagement strategy, assessment method, live-fetched resources, and a step
sequence. Deterministic given the same inputs.

Each step carries two renderings generated from the SAME structured data:
  text        - standard wording (teacher view / Quest Mode)
  simple_text - plain-language wording (reading age ~8: short sentences,
                one action per sentence, literal words, explicit times)
so Focus Mode's adapted content still comes from this single engine.

Threshold values are design decisions documented in README "Assumptions Made".
"""
from src.resources.finder import find_resources

PACING_RULES = {
    "slow":     {"label": "Slow", "session_minutes": 20,
                 "detail": "Introduce one concept at a time and revisit it before moving on."},
    "moderate": {"label": "Moderate", "session_minutes": 30,
                 "detail": "Standard pacing with a quick recap at the start of each session."},
    "fast":     {"label": "Rapid", "session_minutes": 40,
                 "detail": "Move briskly through fundamentals and spend saved time on extension problems."},
}

BREAK_RULES = {
    "high":   {"work_minutes": 15, "break_minutes": 5,
               "detail": "Short focus blocks: 15 minutes of work, then a 5-minute break."},
    "medium": {"work_minutes": 25, "break_minutes": 5,
               "detail": "Pomodoro-style blocks: 25 minutes of work, then a 5-minute break."},
    "low":    {"work_minutes": 40, "break_minutes": 10,
               "detail": "Long focus blocks: 40 minutes of work, then a 10-minute break."},
}

ENGAGEMENT_RULES = {
    "visual": {
        "strategy": "Diagrams, infographics and animations",
        "learn": "Watch a video or study labelled diagrams about {topic}",
        "learn_simple": "Watch a video about {topic}. Look at the pictures carefully.",
        "activity": "Draw and label a diagram or concept map of {topic}",
        "activity_simple": "Draw a picture of what you learned about {topic}.",
    },
    "auditory": {
        "strategy": "Discussion, verbal explanation and audio content",
        "learn": "Listen to an explanation of {topic} and discuss it aloud",
        "learn_simple": "Listen to someone explain {topic}. You can ask questions.",
        "activity": "Explain {topic} aloud in your own words to someone",
        "activity_simple": "Tell someone one thing you learned about {topic}.",
    },
    "kinesthetic": {
        "strategy": "Hands-on activities and experiments",
        "learn": "Explore {topic} through a hands-on activity or simulation",
        "learn_simple": "Try an activity about {topic}. Use your hands. Use real things.",
        "activity": "Build, act out or simulate one process from {topic}",
        "activity_simple": "Make or show something about {topic}.",
    },
    "reading_writing": {
        "strategy": "Structured reading and note-making",
        "learn": "Read about {topic} and take structured notes",
        "learn_simple": "Read about {topic}. Write down 3 things you learned.",
        "activity": "Write a 5-line summary of {topic} in your own words",
        "activity_simple": "Write 3 short sentences about {topic}.",
    },
}

ASSESSMENT_RULES = {
    "analytical":   "Structured written quiz with step-marked problems",
    "pattern":      "Puzzle-style problem set with increasing difficulty",
    "procedural":   "Worked-example completion tasks, then an untimed quiz",
    "visual":       "Diagram-labelling and concept-map assessment",
    "collaborative": "Oral questioning / explain-back assessment with a partner",
}

GAP_ADVICE = {
    "conceptual": "Begin each session by re-teaching the underlying concept before any problem practice.",
    "accuracy":   "Add a 3-minute answer-checking routine at the end of every practice set.",
    "speed":      "Include one timed mini-drill per session to build exam pacing.",
    "application": "End each session with one multi-step application (HOTS) question.",
}

# How each learner method should study — the platform's core personalization
# axis ("what kind of learner is this person").
METHOD_RULES = {
    "memorizer": {
        "label": "Structured memorizer",
        "strategy": "You retain rules and formulas well. Use spaced-repetition "
                    "formula cards, but pair every formula with ONE worked "
                    "example so exam variations don't throw you.",
        "session_tactic": "Start each session by recalling formulas from memory, "
                          "then immediately apply each one to a fresh problem.",
        "watch_out": "Memorizing without a why breaks down on twisted questions "
                     "— always ask 'when does this formula NOT apply?'",
    },
    "example_driven": {
        "label": "Example-driven learner",
        "strategy": "You learn fastest from worked examples. Study each solved "
                    "example, cover the solution, and re-derive it yourself "
                    "before trying variations.",
        "session_tactic": "Use the example-problem pair method: one worked "
                          "example, then two unsolved twins of it.",
        "watch_out": "Don't just read examples — reading feels like learning "
                     "but only re-solving proves it.",
    },
    "conceptual": {
        "label": "Concept-first learner",
        "strategy": "You need the why before the how. Read derivations, connect "
                    "new chapters to old ones, and only then practise.",
        "session_tactic": "Begin each chapter with the derivation/idea video, "
                          "write the core idea in one sentence, then practise.",
        "watch_out": "Don't skip drill practice — exams also reward speed and "
                     "fluency, not just understanding.",
    },
    "visual_learner": {
        "label": "Visual learner",
        "strategy": "Graphs, colours and diagrams are your fastest route. "
                    "Convert every abstract statement into a picture — plot it, "
                    "sketch it, colour-code your notes.",
        "session_tactic": "Open GeoGebra/Desmos alongside the textbook and graph "
                          "everything you read.",
        "watch_out": "Some topics (algebraic manipulation) resist pictures — "
                     "for those, fall back on worked examples.",
    },
    "practice_driven": {
        "label": "Practice-driven learner",
        "strategy": "You learn by doing volume. Jump into problems early, learn "
                    "from mistakes, and keep an error log you re-attempt weekly.",
        "session_tactic": "The 1-5-1 rule: 1 worked example, 5 problems, 1 review "
                          "of every mistake made.",
        "watch_out": "Slow down on new chapters — 10 minutes of concept first "
                     "saves 30 minutes of confused practice.",
    },
}

DEFAULT_TASK = {"subject": "Physics", "topic": "Newton's Laws", "difficulty": ""}


def build_teaching_plan(features: dict, content_level: str,
                        task: dict = None, live_resources: bool = True) -> dict:
    """The single shared plan both modes present.

    task = {"subject", "topic", "difficulty"}; empty difficulty means
    "use the ML-predicted content level".
    """
    task = {**DEFAULT_TASK, **(task or {})}
    topic = task["topic"] or DEFAULT_TASK["topic"]
    subject = task["subject"] or DEFAULT_TASK["subject"]
    level = task["difficulty"] or content_level  # chosen course level wins

    pacing = dict(PACING_RULES[features["learning_pace"]])
    breaks = dict(BREAK_RULES[features["break_frequency"]])
    engagement = ENGAGEMENT_RULES[features["engagement_preference"]]
    assessment = ASSESSMENT_RULES[features["problem_solving_style"]]
    if features.get("confidence", 1) <= 1 or features.get("metacognition", 0) <= 1:
        assessment += " — start untimed and low-stakes to build confidence"

    resources = find_resources(topic, subject, level,
                               features["engagement_preference"],
                               audience="standard", live=live_resources)
    simple_resources = find_resources(topic, subject, level,
                                      features["engagement_preference"],
                                      audience="simplified", live=live_resources)

    wm, bm = breaks["work_minutes"], breaks["break_minutes"]
    steps = [
        {"kind": "review", "minutes": 5,
         "text": f"Recap the previous session's key ideas on {topic} ({level} level).",
         "simple_text": f"First: remember what you learned last time about {topic}. "
                        "Take 5 minutes."},
        {"kind": "learn", "minutes": wm,
         "text": engagement["learn"].format(topic=topic) + f" ({level} level).",
         "simple_text": engagement["learn_simple"].format(topic=topic)
                        + f" Work for {wm} minutes."},
        {"kind": "break", "minutes": bm,
         "text": f"Take a {bm}-minute break away from the screen.",
         "simple_text": f"Now take a break for {bm} minutes. "
                        "Stand up. Drink some water."},
        {"kind": "activity", "minutes": 15,
         "text": engagement["activity"].format(topic=topic) + ".",
         "simple_text": engagement["activity_simple"].format(topic=topic)
                        + " Take 15 minutes."},
        {"kind": "assess", "minutes": 10,
         "text": f"Check understanding of {topic}: {assessment}.",
         "simple_text": f"Last step: answer 3 questions about {topic}. "
                        "It is okay to make mistakes. That is how we learn."},
    ]

    method = METHOD_RULES[features.get("learning_method", "example_driven")]

    return {
        "content_level": level,
        "predicted_level": content_level,
        "task": {"subject": subject, "topic": topic, "difficulty": task["difficulty"]},
        "lesson_pacing": pacing,
        "break_schedule": breaks,
        "engagement_strategy": engagement["strategy"],
        "learner_method": method,
        "assessment_method": assessment,
        "resources": resources,
        "simple_resources": simple_resources,
        "gap_advice": GAP_ADVICE[features.get("performance_gap", "conceptual")],
        "steps": steps,
    }


# Motivational personas (summaries, not fixed identities — never presented as
# a diagnosis, and never as "visual/auditory/kinesthetic learner" labels).
PERSONAS = {
    "conceptual": {
        "name": "The Analyst",
        "tagline": "You dig for the why before the how.",
        "benefit": "concept-first explanations followed by guided practice",
    },
    "example_driven": {
        "name": "The Detective",
        "tagline": "You crack new ideas by studying solved cases.",
        "benefit": "worked examples before independent problem solving",
    },
    "practice_driven": {
        "name": "The Builder",
        "tagline": "You learn by doing — attempt, adjust, repeat.",
        "benefit": "hands-on practice with quick feedback loops",
    },
    "memorizer": {
        "name": "The Strategist",
        "tagline": "You turn knowledge into reliable systems.",
        "benefit": "structured summaries reinforced by spaced recall",
    },
    "visual_learner": {
        "name": "The Explorer",
        "tagline": "You map ideas — structure and pattern first.",
        "benefit": "diagram- and structure-led explanations before formal notation",
    },
}


def persona_for(features: dict) -> dict:
    return PERSONAS[features.get("learning_method", "example_driven")]


def learner_summary(features: dict) -> str:
    """Hedged, evidence-based headline — never a fixed label."""
    persona = persona_for(features)
    rhythm = {
        "high": "short focus blocks with frequent resets",
        "medium": "balanced focus blocks with regular breaks",
        "low": "longer, sustained focus blocks",
    }[features["break_frequency"]]
    return (f"Based on your responses, you appear to benefit from "
            f"{persona['benefit']}, working in {rhythm}.")
