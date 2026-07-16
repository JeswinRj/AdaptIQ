"""Socratic mentor + adaptive quiz engine tests (all hermetic, no AI)."""
import json

from src.ai_integration import mentor, quizzes
from src.dashboard import users
from tests.test_app import _onboard, client, offline_resources  # noqa: F401


# ---- mentor: teaching contract + adaptations --------------------------------

def test_adaptations_follow_profile():
    low_conf = mentor.adaptations({"confidence": 0}, "regular")
    assert any("confidence" in a for a in low_conf)
    short_span = mentor.adaptations({"break_frequency": "high"}, "regular")
    assert any("attention" in a for a in short_span)
    deep = mentor.adaptations({"cognitive_complexity": 0.9}, "regular")
    assert any("deeper" in a for a in deep)
    simple = mentor.adaptations({}, "specialized")
    assert any("literal" in a for a in simple)


def test_solution_gated_behind_attempts():
    user = {"profile": {}, "mode": "regular"}
    ch = {"name": "Integrals", "topics": ["parts"]}
    # asks immediately -> mentor must decline
    p = mentor.build_mentor_prompt(user, ch, "12", [], "just tell me the answer")
    assert "gently decline" in p and "NOW give the complete" not in p
    # two real attempts later, an explicit ask unlocks the solution
    msgs = [{"role": "student", "text": "is it x^2?"},
            {"role": "mentor", "text": "close — why x^2?"},
            {"role": "student", "text": "because the derivative is 2x"},
            {"role": "mentor", "text": "good. and the constant?"}]
    p = mentor.build_mentor_prompt(user, ch, "12", msgs,
                                   "ok now show the full solution")
    assert "NOW give the complete" in p
    # a normal question never unlocks it
    p = mentor.build_mentor_prompt(user, ch, "12", msgs, "what next?")
    assert "NOW give the complete" not in p and "NEVER state the final" in p


def test_practice_parsing_and_xp():
    raw = ('```json\n{"problem": "Integrate x cos x", "answer": '
           '"x sin x + cos x + C", "hints": ["try parts", "ILATE"], '
           '"solution": "u = x ..."}\n```')
    p = mentor.parse_practice(raw)
    assert p["problem"].startswith("Integrate")
    assert len(p["hints"]) == 4                      # padded to a full ladder
    assert mentor.parse_practice("no json here") is None
    assert mentor.practice_xp(0) > mentor.practice_xp(2) > mentor.practice_xp(4)


def test_answer_checking_is_lenient_but_not_sloppy():
    assert mentor.check_answer("x sin x + cos x + C", "x sinx + cosx + c")
    assert mentor.check_answer("5/36", "5/36")
    assert mentor.check_answer("42", "42.0")
    assert not mentor.check_answer("42", "41")
    assert not mentor.check_answer("x + C", "")


# ---- quizzes: adaptive difficulty, parsing, grading, spaced repetition ------

def test_difficulty_adapts_to_recent_scores():
    u = {"content_level": "intermediate"}
    hi = [{"score": 5, "total": 6}, {"score": 6, "total": 6},
          {"score": 5, "total": 6}]
    lo = [{"score": 1, "total": 6}, {"score": 2, "total": 6},
          {"score": 1, "total": 6}]
    assert quizzes.difficulty_for(u, hi)[0] == "harder"
    assert quizzes.difficulty_for(u, lo)[0] == "gentler"
    assert quizzes.difficulty_for(u, [])[0] == "standard"


def test_quiz_parsing_mixed_types():
    raw = json.dumps({"questions": [
        {"type": "mcq", "q": "Which?", "options": ["a", "b", "c"],
         "answer": "b", "concept": "roots", "explanation": "because"},
        {"type": "tf", "q": "True?", "answer": "True", "concept": "sign"},
        {"type": "numeric", "q": "2+2?", "answer": "4", "concept": "sum"},
        {"type": "mcq", "q": "broken, no options", "answer": "x"},
        {"type": "weird", "q": "kind?", "answer": "y", "concept": "misc"},
    ]})
    qs = quizzes.parse_quiz(raw)
    assert len(qs) == 4                       # broken mcq dropped
    assert qs[0]["type"] == "mcq" and len(qs[0]["options"]) == 3
    assert qs[3]["type"] == "short"           # unknown type coerced


def test_grading_explains_and_collects_wrong_concepts():
    qs = quizzes.parse_quiz(json.dumps({"questions": [
        {"type": "numeric", "q": "2+2?", "answer": "4", "concept": "addition",
         "explanation": "2+2=4."},
        {"type": "tf", "q": "Is AB=BA always?", "answer": "False",
         "concept": "matrix commutativity", "explanation": "Not commutative."},
        {"type": "fill", "q": "sin^2 + cos^2 = __", "answer": "1",
         "concept": "identity"},
    ]}))
    graded = quizzes.grade_quiz(qs, {"q0": "4.0", "q1": "True", "q2": "1"})
    assert graded["score"] == 2 and graded["total"] == 3
    assert graded["wrong_concepts"] == ["matrix commutativity"]
    assert all(r["concept"] for r in graded["results"])
    assert graded["results"][1]["feedback"].startswith("Not commutative")
    assert len(graded["stems"]) == 3


def test_revision_topics_spaced_repetition():
    course = {"chapters": [{"name": f"Ch{i}"} for i in range(10)]}
    u = {"completed_chapters": [0, 1, 2, 7, 8]}
    topics = quizzes.revision_topics(u, course, current_index=9)
    assert topics[0] == "Ch9"                 # current topic first
    assert "Ch0" in topics                    # oldest completed resurfaces
    assert "Ch8" in topics                    # freshest consolidates


# ---- end-to-end: teacher quiz set -> student takes it -> concept tracking ---

def test_teacher_quiz_review_assign_take(client):
    student = _onboard(client, name="Quiz Taker")
    client.post("/teacher", data={"name": "Mrs. Nair"})

    qid = users.save_quiz_set(0, "Relations check", quizzes.parse_quiz(
        json.dumps({"questions": [
            {"type": "numeric", "q": "If f(x)=2x, f(3)?", "answer": "6",
             "concept": "function evaluation", "explanation": "f(3)=2*3."},
            {"type": "tf", "q": "Every relation is a function.",
             "answer": "False", "concept": "relations vs functions",
             "explanation": "Functions need exactly one output."},
        ]})))
    # unapproved -> hidden from students, and cannot be assigned
    assert client.get(f"/quiz/{student}/assigned/{qid}").status_code == 404
    resp = client.post(f"/teacher/quizzes/{qid}/assign",
                       data={"uid": student}, follow_redirects=True)
    assert b"Approve the quiz" in resp.data
    # teacher edits one answer and approves
    qs = users.get_quiz_set(qid)
    form = {"approve": "on"}
    for i, q in enumerate(qs["questions"]):
        form.update({f"q{i}": q["q"], f"a{i}": q["answer"],
                     f"e{i}": q.get("explanation", "")})
    client.post(f"/teacher/quizzes/{qid}/save", data=form)
    client.post(f"/teacher/quizzes/{qid}/assign", data={"uid": student})
    assert any(a.get("quiz_id") == qid
               for a in users.get_user(student)["assignments"])

    # student takes it: one right, one wrong -> graded with feedback
    resp = client.get(f"/quiz/{student}/assigned/{qid}")
    assert resp.status_code == 200 and b"Relations check" in resp.data
    resp = client.post(f"/quiz/{student}/submit",
                       data={"q0": "6", "q1": "True"})
    assert b"1 / 2" in resp.data
    assert b"relations vs functions" in resp.data      # concept in feedback
    u = users.get_user(student)
    assert u["quiz_history"][-1]["wrong_concepts"] == ["relations vs functions"]
    assert all(a["done"] for a in u["assignments"]
               if a.get("quiz_id") == qid)
    # teacher sees the concept gap
    resp = client.get(f"/teacher/student/{student}")
    assert b"relations vs functions" in resp.data

    # the submission is attached to the quiz set for the results view
    qs2 = users.get_quiz_set(qid)
    assert len(qs2["submissions"]) == 1
    assert qs2["submissions"][0]["score"] == 1 and qs2["submissions"][0]["total"] == 2

    # teacher results page: participation + per-question + insights + solution
    resp = client.get(f"/teacher/quizzes/{qid}/results")
    assert resp.status_code == 200
    assert b"students submitted" in resp.data         # participation panel
    assert b"1 of 1 student completed it" in resp.data
    assert b"Quiz Taker" in resp.data                # student in submissions
    assert b"relations vs functions" in resp.data    # missed concept surfaced
    assert b"Insights" in resp.data
    users.delete_quiz_set(qid)


def test_quiz_analytics_aggregation():
    from src.rules_engine import teacher as teacher_engine
    qs = {"title": "T", "created": "2026-07-08",
          "questions": [{"q": "Q1", "concept": "a"}, {"q": "Q2", "concept": "b"}],
          "submissions": [
              {"uid": "u1", "name": "Asha", "score": 2, "total": 2, "attempts": 1,
               "date": "2026-07-08", "results": [
                   {"correct": True, "given": "x", "expected": "x", "concept": "a", "q": "Q1"},
                   {"correct": True, "given": "y", "expected": "y", "concept": "b", "q": "Q2"}]},
              {"uid": "u2", "name": "Ben", "score": 0, "total": 2, "attempts": 1,
               "date": "2026-07-08", "results": [
                   {"correct": False, "given": "z", "expected": "x", "concept": "a", "q": "Q1"},
                   {"correct": False, "given": "w", "expected": "y", "concept": "b", "q": "Q2"}]}]}
    a = teacher_engine.quiz_set_analytics(qs, assignee_count=3)
    assert a["submitted"] == 2 and a["assigned"] == 3 and a["pending"] == 1
    assert a["avg_pct"] == 50                          # (2+0)/4
    assert a["per_q"][0]["pct"] == 50                  # 1 of 2 correct on Q1
    assert a["submissions"][0]["name"] == "Asha"       # ranked by score desc
    assert any("completed it" in line for line in a["insights"])
    # empty set is safe
    empty = teacher_engine.quiz_set_analytics(
        {"questions": [], "submissions": []}, assignee_count=0)
    assert empty["avg_pct"] == 0 and empty["submitted"] == 0


def test_practice_problem_flow_offline(client):
    uid = _onboard(client, name="Practice Kid")
    # offline generation fails honestly
    resp = client.post(f"/chapter/{uid}/0/practice", data={"action": "new"})
    assert b"Could not generate a problem" in resp.data
    # inject a problem directly, then walk the hint ladder and solve
    state = users.mentor_state(uid, 0)
    state["practice"] = {"problem": "Compute 6*7", "answer": "42",
                         "hints": ["h1", "h2", "h3", "h4"],
                         "solution": "6*7=42", "hints_used": 0,
                         "solved": False, "revealed": False}
    users.save_mentor_state(uid, 0, state)
    client.post(f"/chapter/{uid}/0/practice", data={"action": "hint"})
    xp_before = users.get_user(uid)["xp"]
    resp = client.post(f"/chapter/{uid}/0/practice",
                       data={"action": "answer", "answer": "42"})
    assert b"Correct!" in resp.data
    gained = users.get_user(uid)["xp"] - xp_before
    assert gained == mentor.practice_xp(1)    # one hint used -> 25 XP
