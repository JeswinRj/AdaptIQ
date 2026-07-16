"""Socratic mentor: guides students toward answers instead of giving them.

Design:
- Every reply is built from a teaching contract (never reveal the final
  answer early; one idea + one guiding question per turn) plus adaptations
  computed from the learner profile — low confidence gets encouragement and
  smaller steps, strong conceptual learners get deeper questions, short
  attention spans get concise chunks.
- The full solution is only produced when the student explicitly asks for
  it AND has made at least MIN_ATTEMPTS guided attempts.
- Practice problems come with a 4-level hint ladder (nudge -> concept ->
  method -> partial working) and the final solution; solving with fewer
  hints earns more XP.

Provider-agnostic by construction: all AI calls go through the existing
ai_client abstraction (any of its providers can be swapped in .env without
touching this module).
"""
import json
import re

MIN_ATTEMPTS_FOR_SOLUTION = 2

MATH_STYLE = (" Write every formula and mathematical expression in LaTeX: "
              "inline as \\( ... \\), standalone equations as \\[ ... \\].")

SOLUTION_MARKERS = ("full solution", "final answer", "just tell me",
                    "give me the answer", "show the solution", "solve it for me",
                    "reveal", "i give up")

# XP policy: fewer hints -> bigger reward
PRACTICE_XP = {0: 30, 1: 25, 2: 20, 3: 15, 4: 10}
REVEAL_XP = 5


def wants_solution(message: str) -> bool:
    m = message.lower()
    return any(k in m for k in SOLUTION_MARKERS)


def adaptations(profile: dict, mode: str) -> list:
    """Teaching-style lines derived from the learner profile (hedged
    estimates, so phrased as tendencies, not diagnoses)."""
    out = []
    p = profile or {}
    if mode == "specialized":
        out.append("Use very simple, literal language: short sentences, one "
                   "idea each, no metaphors or idioms. Be calm and concrete.")
    if p.get("confidence", 3) <= 1:
        out.append("This student appears to have low confidence: encourage "
                   "warmly, celebrate every partial success, and keep each "
                   "step very small.")
    if p.get("cognitive_complexity", 0) >= 0.7:
        out.append("This student shows strong conceptual reasoning: ask "
                   "deeper 'why' questions, invite a second solution method, "
                   "and raise the challenge gradually.")
    if p.get("break_frequency") == "high":
        out.append("This student has a short attention span: keep every "
                   "reply under 80 words and end with one clear checkpoint "
                   "question.")
    method = p.get("learning_method", "")
    if method == "example_driven":
        out.append("Anchor guidance in tiny concrete examples before "
                   "abstract statements.")
    elif method == "memorizer":
        out.append("Connect each step to a formula the student can recall.")
    elif method == "visual_learner":
        out.append("Suggest quick sketches or diagrams the student can draw.")
    elif method == "practice_driven":
        out.append("Turn each step into something the student does, not "
                   "something they watch.")
    return out


def build_mentor_prompt(user: dict, chapter: dict, grade: str,
                        messages: list, new_message: str) -> str:
    """One prompt carrying the teaching contract, profile adaptations and
    the conversation so far. Single-completion providers stay supported."""
    attempts = sum(1 for m in messages if m["role"] == "student")
    allow_solution = (wants_solution(new_message)
                      and attempts >= MIN_ATTEMPTS_FOR_SOLUTION)
    style = "\n".join(f"- {a}" for a in
                      adaptations(user.get("profile"), user.get("mode", "")))
    transcript = "\n".join(
        f"{'Student' if m['role'] == 'student' else 'Mentor'}: {m['text']}"
        for m in messages[-10:])
    contract = (
        "You are a patient, experienced CBSE Class {g} mathematics mentor "
        "inside Adapt IQ. Chapter: {ch}. Your goal is to teach the student "
        "HOW TO THINK, never to hand over answers.\n"
        "Rules:\n"
        "- NEVER state the final answer or complete the solution unless "
        "explicitly permitted below.\n"
        "- Each reply: acknowledge what the student got right, give AT MOST "
        "one small idea, then ask ONE guiding question that moves them one "
        "step forward.\n"
        "- If the student is wrong, do not just correct them — ask a "
        "question that lets them notice the mistake.\n"
        "- Keep replies short and warm.{math}\n").format(
            g=grade, ch=chapter["name"], math=MATH_STYLE)
    if allow_solution:
        contract += ("\nThe student has made several guided attempts and "
                     "explicitly asked for the solution: NOW give the "
                     "complete worked solution, step by step, explaining "
                     "the reasoning at each step.\n")
    elif wants_solution(new_message):
        contract += ("\nThe student asked for the answer but has not "
                     "seriously attempted it yet: gently decline, explain "
                     "that trying first is how learning sticks, and offer "
                     "the first small step as a question.\n")
    return (f"{contract}\nAdapt to this learner:\n{style or '- (no notes)'}\n"
            f"\nConversation so far:\n{transcript or '(new conversation)'}\n"
            f"Student: {new_message}\n\nReply as the mentor.")


# ---- hint-ladder practice problems -----------------------------------------

def build_practice_prompt(chapter: dict, grade: str, difficulty: str) -> str:
    return (
        "Create ONE fresh practice problem for CBSE Class "
        f"{grade} Mathematics, chapter '{chapter['name']}' "
        f"(topics: {', '.join(chapter['topics'])}). Difficulty: {difficulty}. "
        "Use novel numbers/context (do not copy a textbook exercise)."
        f"{MATH_STYLE} "
        "Return STRICT JSON only, no markdown fences, exactly this shape: "
        '{"problem": "...", "answer": "final answer only, short", '
        '"hints": ["gentle nudge", "the relevant concept", '
        '"outline of the method", "first half of the working"], '
        '"solution": "complete step-by-step solution"}')


def _fix_latex_escapes(s: str) -> str:
    """LaTeX inside JSON strings ('\\(', '\\frac') is an invalid JSON escape
    and kills json.loads — double any backslash that isn't a legal escape."""
    return re.sub(r'\\(?![\\/"bfnrtu])', r"\\\\", s)


def parse_json_block(text: str):
    """Lenient JSON extraction — models wrap JSON in prose/fences and put
    LaTeX in string values."""
    text = re.sub(r"^\s*```\w*|```\s*$", "", text.strip(), flags=re.M)
    candidates = [text]
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        candidates.append(m.group(0))
    for c in candidates:
        for attempt in (c, _fix_latex_escapes(c)):
            try:
                return json.loads(attempt)
            except Exception:
                continue
    return None


def parse_practice(text: str):
    data = parse_json_block(text)
    if not isinstance(data, dict):
        return None
    if not all(k in data for k in ("problem", "answer", "hints", "solution")):
        return None
    hints = [str(h) for h in (data["hints"] or [])][:4]
    while len(hints) < 4:
        hints.append("Look back at the worked examples for this chapter.")
    return {"problem": str(data["problem"]), "answer": str(data["answer"]),
            "hints": hints, "solution": str(data["solution"]),
            "hints_used": 0, "solved": False, "revealed": False}


def normalize_answer(s: str) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"[\s,]", "", s)
    s = s.replace("\\(", "").replace("\\)", "").replace("$", "")
    return s.rstrip(".")


def check_answer(expected: str, given: str) -> bool:
    e, g = normalize_answer(expected), normalize_answer(given)
    if not g:
        return False
    if e == g or (len(g) >= 2 and g in e) or (len(e) >= 2 and e in g):
        return True
    try:                                    # numeric tolerance
        return abs(float(e) - float(g)) < 1e-6
    except ValueError:
        return False


def practice_xp(hints_used: int) -> int:
    return PRACTICE_XP.get(min(hints_used, 4), 10)
