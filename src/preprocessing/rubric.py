"""ADAPT-IQ questionnaire and scoring rubric — single source of truth.

Instrument for the CBSE Class 11/12 Mathematics learning platform.
Five sections, answered in-app during onboarding:

  A  Foundational maths understanding   (open-ended, NLP-scored)
  B  Learning approach & cognitive style (multiple choice -> learner method,
     problem-solving style, modality)
  C  Study habits, attention span & breaks
  D  Self-reflection & metacognition
  E  Academic performance snapshot

Every option's scoring contribution is explicit below and mirrored in
docs/questionnaire_and_scoring.md (a sync test keeps them aligned).

Design principles: indirect, behaviour-based wording (never "are you a slow
learner?" or any diagnostic question); every derived feature is triangulated
from at least two items; the Regular/Specialized mode choice is made
explicitly by the user, never inferred from answers.

NOT clinically validated — a heuristic profiling instrument, not a
diagnostic. Learning-style models are contested; modality is treated as a
format preference only.
"""

MODALITIES = ["visual", "auditory", "kinesthetic", "reading_writing"]

# How the student naturally acquires maths — the "what kind of learner am I"
# axis the platform's plans are built around.
LEARNING_METHODS = ["memorizer", "example_driven", "conceptual",
                    "visual_learner", "practice_driven"]

PROBLEM_SOLVING_STYLES = ["analytical", "pattern", "procedural", "visual",
                          "collaborative"]

# ---------------------------------------------------------------------------
# Section A — Foundational maths understanding (open-ended)
# Score per question: 0-8 keyword-coverage points (2 per concept group)
# + 0-2 sentence-complexity bonus. foundational_knowledge_score =
# mean(A1..A3) * 10 -> 0-100.
# ---------------------------------------------------------------------------
KNOWLEDGE_QUESTIONS = {
    "A1": {
        "text": "Explain in your own words what a 'function' means in maths. "
                "You may use an example.",
        "keyword_groups": [
            ["input", "output", "x", "value"],
            ["relation", "mapping", "maps", "rule", "machine"],
            ["unique", "exactly one", "only one", "single"],
            ["domain", "range", "set"],
        ],
    },
    "A2": {
        "text": "Why can we not divide a number by zero? Explain your thinking.",
        "keyword_groups": [
            ["undefined", "not defined", "no answer", "meaningless"],
            ["infinity", "infinite", "larger and larger"],
            ["multiplication", "multiply", "inverse", "reverse"],
            ["no number", "nothing times", "cannot find"],
        ],
    },
    "A3": {
        "text": "What does the slope of a straight line tell you? "
                "Explain simply, as if to a friend.",
        "keyword_groups": [
            ["steep", "steepness", "inclination", "angle"],
            ["rate of change", "change in y", "rise", "run"],
            ["gradient"],
            ["direction", "increasing", "decreasing", "upward", "downward"],
        ],
    },
}

# ---------------------------------------------------------------------------
# Section B — Learning approach & cognitive style (multiple choice)
# Options carry: a learning-method vote, a problem-solving-style vote,
# and/or modality points.
# ---------------------------------------------------------------------------
COGNITIVE_QUESTIONS = {
    "B1": {
        "text": "Your teacher introduces a brand-new formula. "
                "What do you naturally do first?",
        "options": {
            "Memorize it so I can use it in the exam":
                {"method": "memorizer"},
            "Look at a solved example that uses it":
                {"method": "example_driven"},
            "Try to understand where the formula comes from":
                {"method": "conceptual"},
            "Draw a picture or graph of what it means":
                {"method": "visual_learner", "modality": {"visual": 2}},
            "Immediately try a practice question with it":
                {"method": "practice_driven", "modality": {"kinesthetic": 1}},
        },
    },
    "B2": {
        "text": "When you face a maths problem you have never seen before, "
                "what is your usual first move?",
        "options": {
            "Break it into smaller parts":
                {"style": "analytical"},
            "Look for a pattern from problems I know":
                {"style": "pattern", "modality": {"visual": 1}},
            "Search for a formula that fits":
                {"style": "procedural", "modality": {"reading_writing": 1}},
            "Draw a diagram or graph of the situation":
                {"style": "visual", "modality": {"visual": 2}},
            "Ask a friend or teacher how to start":
                {"style": "collaborative", "modality": {"auditory": 1}},
        },
    },
    "B3": {
        "text": "How do you usually revise before a maths exam?",
        "options": {
            "Re-read my formula list until I know it by heart":
                {"method": "memorizer", "modality": {"reading_writing": 1}},
            "Redo the solved examples from the textbook":
                {"method": "example_driven"},
            "Go back to WHY each method works, then practise a little":
                {"method": "conceptual"},
            "Make colourful summary sheets, graphs and mind-maps":
                {"method": "visual_learner", "modality": {"visual": 2}},
            "Solve as many new problems as possible against the clock":
                {"method": "practice_driven", "modality": {"kinesthetic": 1}},
        },
    },
    "B4": {
        "text": "You need to learn how the graph of y = x² changes when it "
                "becomes y = (x-2)² + 3. Which would you pick first?",
        "options": {
            "Watch an animation of the graph shifting":
                {"modality": {"visual": 2}},
            "Have someone talk me through it step by step":
                {"modality": {"auditory": 2}},
            "Plot the points myself and see what happens":
                {"modality": {"kinesthetic": 2}},
            "Read a written explanation with the rules":
                {"modality": {"reading_writing": 2}},
        },
    },
}

# ---------------------------------------------------------------------------
# Section C — Study habits, attention span & break preferences
# pace points (0=slow..2=fast) and break points (0=low..2=high need).
# ---------------------------------------------------------------------------
HABITS_QUESTIONS = {
    "C1": {
        "text": "Imagine a 40-minute maths topic to study tonight. "
                "Which best describes your natural approach?",
        "options": {
            "Study it continuously without breaks":              {"pace": 2, "break": 0},
            "Take a 5-minute break after 20 minutes":            {"pace": 1, "break": 1},
            "Split the topic over two shorter sessions":         {"pace": 0, "break": 2},
            "Study with a friend and discuss along the way":     {"pace": 1, "break": 1, "modality": {"auditory": 1}},
        },
    },
    "C2": {
        "text": "How long can you usually stay on one maths exercise before "
                "you feel like switching to something else?",
        "options": {
            "Less than 10 minutes": {"pace": 0, "break": 2},
            "10–20 minutes":        {"pace": 1, "break": 2},
            "20–40 minutes":        {"pace": 1, "break": 1},
            "More than 40 minutes": {"pace": 2, "break": 0},
        },
    },
    "C3": {
        "text": "While studying alone, how often do you notice you have "
                "drifted off or picked up your phone?",
        "options": {
            "Very often — every few minutes": {"pace": 0, "break": 2},
            "Sometimes":                      {"pace": 1, "break": 1},
            "Rarely — I stay on task":        {"pace": 2, "break": 0},
        },
    },
    "C4": {
        "text": "Your ideal place to study maths is…",
        "options": {
            "Somewhere quiet where I am alone":        {"pace": 1, "break": 1},
            "With soft music or background sound":     {"pace": 1, "break": 1, "modality": {"auditory": 1}},
            "With friends so we can talk it through":  {"pace": 1, "break": 1, "modality": {"auditory": 1}},
            "Somewhere I can move around or stand":    {"pace": 1, "break": 2, "modality": {"kinesthetic": 1}},
        },
    },
}

# ---------------------------------------------------------------------------
# Section D — Self-reflection & metacognition
# ---------------------------------------------------------------------------
REFLECTION_QUESTIONS = {
    "D1": {
        "text": "How do you know you have understood a maths topic well enough?",
        "open_ended": True,
        "keyword_groups": [
            ["explain", "teach"],
            ["without help", "on my own", "myself"],
            ["test myself", "practice questions", "solve problems", "quiz"],
            ["mistakes", "check", "compare"],
        ],
    },
    "D2": {
        "text": "Describe one time you finally understood a maths idea that "
                "had confused you. What made it click?",
        "open_ended": True,
        "modality_keywords": {
            "visual": ["video", "videos", "diagram", "diagrams", "graph",
                       "picture", "animation", "watch", "drew", "drawing"],
            "auditory": ["listen", "listening", "explained", "discussion",
                         "talk", "told me", "said"],
            "kinesthetic": ["tried", "practice", "practising", "doing",
                            "worked through", "experiment", "hands"],
            "reading_writing": ["notes", "reading", "read", "wrote",
                                "writing", "summary", "textbook"],
        },
    },
    "D3": {
        "text": "Before a maths test, you usually feel…",
        "options": {
            "Well prepared and calm":           {"confidence": 3},
            "Mostly prepared, a few doubts":    {"confidence": 2},
            "Unsure what to expect":            {"confidence": 1},
            "Anxious even when I have studied": {"confidence": 0},
        },
    },
}

# ---------------------------------------------------------------------------
# Section E — Academic performance snapshot
# ---------------------------------------------------------------------------
PERFORMANCE_QUESTIONS = {
    "E1": {
        "text": "Your approximate percentage in your last maths exam (optional).",
        "numeric": True,
    },
    "E2": {
        "text": "In your last maths exam, where did you lose the most marks?",
        "options": {
            "Concepts I never fully understood":     {"gap": "conceptual"},
            "Silly mistakes in things I knew":       {"gap": "accuracy"},
            "I ran out of time":                     {"gap": "speed"},
            "Hard application/HOTS questions":       {"gap": "application"},
        },
    },
}

# Bucketing thresholds for mean pace/break points (0-2 scale).
LOW_THRESHOLD = 0.7
HIGH_THRESHOLD = 1.4

PACE_LABELS = {0: "slow", 1: "moderate", 2: "fast"}
BREAK_LABELS = {0: "low", 1: "medium", 2: "high"}

ALL_QUESTIONS = {}
for _bank in (KNOWLEDGE_QUESTIONS, COGNITIVE_QUESTIONS, HABITS_QUESTIONS,
              REFLECTION_QUESTIONS, PERFORMANCE_QUESTIONS):
    ALL_QUESTIONS.update(_bank)

# Ordered sections for rendering the in-app questionnaire form.
SECTIONS = [
    ("A", "Understanding check", "Answer in your own words — there are no "
     "wrong answers, we just want to see how you think.", KNOWLEDGE_QUESTIONS),
    ("B", "How you learn", "Pick the option closest to what you actually do.",
     COGNITIVE_QUESTIONS),
    ("C", "Focus and breaks", "Think about a normal study day.",
     HABITS_QUESTIONS),
    ("D", "About you", "A little reflection.", REFLECTION_QUESTIONS),
    ("E", "Your marks", "This helps us pitch the difficulty right.",
     PERFORMANCE_QUESTIONS),
]


def bucket(mean_points: float) -> int:
    """Bucket a 0-2 mean into 0 (low/slow), 1 (medium/moderate), 2 (high/fast)."""
    if mean_points < LOW_THRESHOLD:
        return 0
    if mean_points > HIGH_THRESHOLD:
        return 2
    return 1
