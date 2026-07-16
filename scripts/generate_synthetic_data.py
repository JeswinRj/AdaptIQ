"""Generate the SYNTHETIC training dataset for the content-level model.

Rows simulate students answering the in-app maths questionnaire
(src/preprocessing/rubric.py). Labels are derived by running the REAL
feature pipeline over the generated answers plus noise, so the Decision
Tree trains on exactly the features it sees at prediction time.

Usage:  python scripts/generate_synthetic_data.py [--rows 220] [--seed 42]
"""
import argparse
import random
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.preprocessing import rubric
from src.preprocessing.features import build_feature_dict

FIRST_NAMES = [
    "Aarav", "Diya", "Vihaan", "Ananya", "Arjun", "Ishita", "Kabir", "Meera",
    "Rohan", "Sanya", "Aditya", "Priya", "Karthik", "Nisha", "Farhan", "Lakshmi",
    "Dev", "Zara", "Nikhil", "Anjali", "Rahul", "Pooja", "Sameer", "Tara",
    "Vikram", "Riya", "Imran", "Kavya", "Siddharth", "Neha",
]
LAST_NAMES = [
    "Sharma", "Nair", "Patel", "Iyer", "Khan", "Reddy", "Das", "Menon",
    "Gupta", "Fernandes", "Rao", "Joshi", "Pillai", "Bose", "Kulkarni",
]

A1_ANSWERS = {
    "high": [
        "A function is a rule that maps every input to exactly one output. "
        "For example f(x) = 2x takes any x value and gives back double, so "
        "each element of the domain relates to a unique element of the range.",
        "It is like a machine: you feed in an input x and it returns exactly "
        "one output value. The set of allowed inputs is the domain and the "
        "outputs form the range, and no input can give two answers.",
    ],
    "mid": [
        "A function takes an input and gives an output, like y depends on x.",
        "It is a rule connecting x values to y values, one output for each input.",
    ],
    "low": [
        "Something with f(x) in it.",
        "It is an equation we solve in algebra.",
        "I don't really remember what it means.",
    ],
}
A2_ANSWERS = {
    "high": [
        "Division is the inverse of multiplication, so 6/0 would need a number "
        "that gives 6 when multiplied by zero, but anything times zero is zero, "
        "therefore no such number exists and the result is undefined.",
        "Because as the divisor gets smaller the answer grows toward infinity, "
        "and at exactly zero there is no number that works, so it is undefined.",
    ],
    "mid": [
        "Because the answer would be infinity and that is not a real number.",
        "There is no number which multiplied by zero gives you back the original.",
    ],
    "low": [
        "The calculator shows an error.",
        "Because the teacher said it is not allowed.",
    ],
}
A3_ANSWERS = {
    "high": [
        "The slope is the rate of change: how much y rises for each unit you "
        "move in x, so it measures steepness and whether the line is "
        "increasing or decreasing.",
        "It tells you the steepness of the line, rise over run, which is the "
        "gradient, and its sign shows the direction of the line.",
    ],
    "mid": [
        "It shows how steep the line is going up or down.",
        "Slope is rise over run between two points.",
    ],
    "low": [
        "It is the m in y = mx + c.",
        "Something about the line's angle, I forget.",
    ],
}
D1_ANSWERS = {
    "high": [
        "I know I understand it when I can explain it to a friend without notes "
        "and solve practice questions on my own, and when I check my mistakes "
        "they make sense to me.",
        "When I can teach it to someone else and test myself with new problems "
        "without help, I feel sure.",
    ],
    "mid": [
        "When I can solve textbook problems without looking at the examples.",
        "If I can explain the idea in my own words I feel I understood it.",
    ],
    "low": [
        "When the exam goes okay I guess.",
        "I am not sure, I just read it again before the test.",
    ],
}
D2_ANSWERS = {
    "visual": [
        "Trigonometry confused me until I watched a video with the unit circle "
        "animation — seeing the graph move made it click.",
        "I finally got derivatives when I drew the tangent line on a graph and "
        "watched the slope change in a diagram.",
    ],
    "auditory": [
        "My friend explained probability to me out loud on the bus and the way "
        "she said it just made sense.",
        "The teacher told a story about splitting a bill and suddenly ratios "
        "made sense when I heard it explained.",
    ],
    "kinesthetic": [
        "I only understood permutations after I physically tried arranging "
        "cards on my desk and worked through it with my hands.",
        "Integration clicked when I worked through ten problems myself instead "
        "of watching someone else.",
    ],
    "reading_writing": [
        "I read the textbook chapter twice and wrote my own summary notes, and "
        "writing it out made limits finally make sense.",
        "Making a written step-by-step summary of the quadratic formula proof "
        "is what made it click for me.",
    ],
}

ARCHETYPES = [
    # (method, modality, style, pace, break, knowledge tier weights)
    ("memorizer", "reading_writing", "procedural", "moderate", "medium",
     {"high": .2, "mid": .5, "low": .3}),
    ("example_driven", "visual", "pattern", "moderate", "medium",
     {"high": .3, "mid": .5, "low": .2}),
    ("conceptual", "reading_writing", "analytical", "slow", "low",
     {"high": .5, "mid": .35, "low": .15}),
    ("visual_learner", "visual", "visual", "moderate", "high",
     {"high": .35, "mid": .4, "low": .25}),
    ("practice_driven", "kinesthetic", "pattern", "fast", "high",
     {"high": .3, "mid": .4, "low": .3}),
    ("example_driven", "auditory", "collaborative", "moderate", "medium",
     {"high": .25, "mid": .45, "low": .3}),
]


def _pick_option(rng, question, prefer):
    options = list(question["options"].items())
    weighted = []
    for label, meta in options:
        w = 1.0
        if meta.get("style") == prefer.get("style"):
            w += 3.0
        if meta.get("method") == prefer.get("method"):
            w += 3.0
        for m, pts in meta.get("modality", {}).items():
            if m == prefer.get("modality"):
                w += 2.0 * pts
        if "pace" in meta and meta["pace"] == prefer.get("pace"):
            w += 2.0
        if "break" in meta and meta["break"] == prefer.get("break"):
            w += 2.0
        weighted.append(w)
    return rng.choices([l for l, _ in options], weights=weighted, k=1)[0]


def generate(rows: int, seed: int) -> pd.DataFrame:
    rng = random.Random(seed)
    pace_num = {"slow": 0, "moderate": 1, "fast": 2}
    brk_num = {"low": 0, "medium": 1, "high": 2}
    records = []
    for i in range(rows):
        method, modality, style, pace_t, break_t, kw = rng.choice(ARCHETYPES)
        tier = rng.choices(list(kw), weights=list(kw.values()), k=1)[0]
        prefer = {"method": method, "modality": modality, "style": style,
                  "pace": pace_num[pace_t], "break": brk_num[break_t]}

        row = {
            "student_id": f"S{i + 1:03d}",
            "name": f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
            "subject": "Mathematics",
            "A1": rng.choice(A1_ANSWERS[tier]),
            "A2": rng.choice(A2_ANSWERS[tier]),
            "A3": rng.choice(A3_ANSWERS[tier]),
            "D1": rng.choice(D1_ANSWERS[tier]),
            "D2": rng.choice(D2_ANSWERS[modality]),
        }
        for qid, q in {**rubric.COGNITIVE_QUESTIONS,
                       **rubric.HABITS_QUESTIONS}.items():
            row[qid] = _pick_option(rng, q, prefer)
        row["D3"] = _pick_option(rng, rubric.REFLECTION_QUESTIONS["D3"], prefer)
        row["E2"] = _pick_option(rng, rubric.PERFORMANCE_QUESTIONS["E2"], prefer)

        base_marks = {"high": 78, "mid": 60, "low": 42}[tier]
        marks = max(15, min(98, rng.gauss(base_marks, 9)))
        row["E1"] = "" if rng.random() < 0.07 else round(marks, 1)

        feats = build_feature_dict(row, previous_marks_default=60.0)
        composite = (0.55 * feats["foundational_knowledge_score"]
                     + 0.35 * feats["previous_marks"]
                     + 10.0 * feats["cognitive_complexity"]
                     + rng.gauss(0, 4))
        if composite >= 68:
            row["content_level"] = "advanced"
        elif composite >= 46:
            row["content_level"] = "intermediate"
        else:
            row["content_level"] = "basic"
        records.append(row)
    return pd.DataFrame.from_records(records)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=220)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    out = Path(__file__).resolve().parents[1] / "data" / "synthetic_responses.csv"
    out.parent.mkdir(exist_ok=True)
    df = generate(args.rows, args.seed)
    df.to_csv(out, index=False)
    print(f"Wrote {len(df)} synthetic responses to {out}")
    print(df["content_level"].value_counts().to_string())


if __name__ == "__main__":
    main()
