"""ADAPT-IQ — self-serve personalized learning platform (CBSE 11/12 Maths).

Flow:
  /                         landing: Regular vs Specialized (parent-guided)
  /start/<mode>             basic details + course selection
  /questionnaire/<uid>      in-app psychologist-designed questionnaire
  (POST processes answers: NLP + rubric scoring -> Decision Tree -> profile)
  /report/<uid>             learner assessment report
  /profile/<uid>            game profile: HP/XP/level/streak/skill web
  /course/<uid>             syllabus with per-chapter completion
  /chapter/<uid>/<i>        chapter: personalized plan, live resources,
                            mark-complete (+XP), AI doubt box
  /notes/<uid>              upload/paste notes -> summary

Run locally:  python -m src.dashboard.app     (http://127.0.0.1:5050)
Deploy:       gunicorn 'src.dashboard.app:create_app()'
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from flask import (Flask, abort, redirect, render_template, request,
                   session, url_for)

import config
from src.ai_integration.ai_client import get_ai_tips
from src.curriculum import cbse_math
from src.dashboard import users
from src.ml.predictor import predict_content_level
from src.notes.summarizer import summarize
from src.preprocessing import rubric
from src.preprocessing.features import build_feature_dict
from src.resources.finder import find_resources
from src.rules_engine import teacher as teacher_engine
from src.rules_engine.engine import (build_teaching_plan, learner_summary,
                                     persona_for)


def _dimensions(profile: dict) -> dict:
    """Multidimensional learner estimates (0-100). Estimates, not diagnoses —
    every user-facing rendering hedges accordingly."""
    focus = {"low": 85, "medium": 62, "high": 42}[profile["break_frequency"]]
    return {
        "Foundational understanding": round(profile["foundational_knowledge_score"]),
        "Reasoning depth": round(profile["cognitive_complexity"] * 100),
        "Attention endurance": focus,
        "Metacognition": profile["metacognition"] * 25,
        "Confidence": round(profile["confidence"] / 3 * 100),
        "Exam readiness": round(profile["previous_marks"]),
    }


def _strengths_growth(dims: dict):
    ranked = sorted(dims.items(), key=lambda kv: kv[1], reverse=True)
    strengths = [k for k, v in ranked[:2] if v >= 55]
    growth = [k for k, v in ranked[::-1][:2] if v < 60]
    return strengths or [ranked[0][0]], growth or [ranked[-1][0]]

import requests as _requests


def _ask_ai(prompt: str) -> dict:
    """One-off AI question (doubt solving, quizzes, follow-ups).

    Resilient: rate-limited Gemini retries on flash-lite automatically, then
    the optional AI_FALLBACK_PROVIDER. Honest offline fallback otherwise.
    """
    if not config.AI_PROVIDER:
        return {"available": False, "text":
                "AI is not configured yet. Set AI_PROVIDER and AI_API_KEY in "
                ".env (see README 'Free AI setup') to enable doubt solving."}
    from src.ai_integration import ai_client
    try:
        text = ai_client.resilient_complete(
            prompt, config.AI_PROVIDER, config.AI_API_KEY, config.AI_MODEL,
            config.AI_FALLBACK_PROVIDER, config.AI_FALLBACK_KEY,
            config.OLLAMA_HOST)
        return {"available": True,
                "text": ai_client.strip_markdown(text or "")}
    except Exception as exc:
        return {"available": False,
                "text": f"AI call failed ({exc}). The rest of the app keeps working."}


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = config.FLASK_SECRET_KEY

    def user_or_404(uid):
        u = users.get_user(uid)
        if u is None:
            abort(404)
        return u

    def theme(u):
        return "calm" if u["mode"] == "specialized" else "game"

    @app.template_filter("mathsnip")
    def mathsnip(text, limit=420):
        """Display cleanup: drop '## ' heading markers, and truncate without
        cutting a LaTeX expression in half (an unclosed \\( \\[ or $$ would
        render as raw markup, so trim back past it)."""
        import re as _re
        text = _re.sub(r"^#{1,6}\s*", "", text or "", flags=_re.M)
        if len(text) <= limit:
            return text
        cut = text[:limit]
        for op, cl in (("\\(", "\\)"), ("\\[", "\\]")):
            if cut.count(op) > cut.count(cl):
                cut = cut[:cut.rfind(op)]
        if cut.count("$$") % 2:
            cut = cut[:cut.rfind("$$")]
        return cut.rstrip() + " …"

    # ---------------- onboarding ----------------

    @app.route("/")
    def landing():
        current = users.get_user(session.get("uid", "")) if session.get("uid") else None
        return render_template("landing.html", current=current)

    @app.route("/start/<mode>")
    def start(mode):
        if mode not in ("regular", "specialized"):
            abort(404)
        return render_template("start.html", mode=mode,
                               courses=cbse_math.COURSES)

    @app.route("/start/<mode>", methods=["POST"])
    def start_post(mode):
        course_id = request.form.get("course_id", "cbse-11-math")
        if course_id not in cbse_math.COURSES:
            abort(400)
        uid = users.create_user(request.form.get("name", ""), mode, course_id)
        session["uid"] = uid
        return redirect(url_for("questionnaire", uid=uid))

    @app.route("/questionnaire/<uid>")
    def questionnaire(uid):
        u = user_or_404(uid)
        return render_template("questionnaire.html", u=u, theme=theme(u),
                               sections=rubric.SECTIONS)

    @app.route("/questionnaire/<uid>", methods=["POST"])
    def questionnaire_post(uid):
        u = user_or_404(uid)
        answers = {qid: request.form.get(qid, "") for qid in rubric.ALL_QUESTIONS}
        profile = build_feature_dict(answers)
        level = predict_content_level(profile, config.MODEL_PATH)
        followup = None
        if config.AI_PROVIDER:  # adaptive conversational follow-up (AI only)
            result = _ask_ai(
                "You are an educational advisor. A student just completed a "
                f"learning assessment. Their profile: learning method "
                f"{profile['learning_method']}, pace {profile['learning_pace']}, "
                f"break needs {profile['break_frequency']}, confidence "
                f"{profile['confidence']}/3. Their answer to 'how do you know "
                f"you understood a topic' was: \"{answers.get('D1','')}\". "
                "Ask ONE short, warm follow-up question that would sharpen this "
                "profile. Just the question, under 25 words.")
            if result["available"]:
                followup = result["text"]
        users.update_user(uid, answers=answers, profile=profile,
                          content_level=level, followup=followup)
        users.touch_activity(uid)
        return redirect(url_for("report", uid=uid))

    # ---------------- results ----------------

    @app.route("/report/<uid>")
    def report(uid):
        u = user_or_404(uid)
        if not u["profile"]:
            return redirect(url_for("questionnaire", uid=uid))
        plan = build_teaching_plan(
            u["profile"], u["content_level"],
            task={"subject": "Mathematics", "topic": "your course",
                  "difficulty": ""},
            live_resources=False)
        dims = _dimensions(u["profile"])
        strengths, growth = _strengths_growth(dims)
        return render_template("report.html", u=u, theme=theme(u), plan=plan,
                               persona=persona_for(u["profile"]),
                               summary=learner_summary(u["profile"]),
                               dims=dims, strengths=strengths, growth=growth,
                               course=cbse_math.get_course(u["course_id"]))

    @app.route("/profile/<uid>")
    def profile(uid):
        u = user_or_404(uid)
        if not u["profile"]:
            return redirect(url_for("questionnaire", uid=uid))
        course = cbse_math.get_course(u["course_id"])
        game = users.game_state(u)
        domains = cbse_math.domain_progress(u["course_id"],
                                            u["completed_chapters"])
        # skill web layout (SVG coordinates)
        import math as _m
        nodes = []
        for i, d in enumerate(cbse_math.DOMAINS):
            angle = 2 * _m.pi * i / len(cbse_math.DOMAINS) - _m.pi / 2
            nodes.append({"name": d, "mastery": domains[d],
                          "x": round(170 + 120 * _m.cos(angle), 1),
                          "y": round(170 + 120 * _m.sin(angle), 1)})
        next_ch = next((i for i in range(len(course["chapters"]))
                        if i not in u["completed_chapters"]), None)
        dims = _dimensions(u["profile"])
        health = {
            "Focus": dims["Attention endurance"],
            "Confidence": dims["Confidence"],
            "Consistency": min(100, game["streak"] * 20),
        }
        pending = [a for a in u.get("assignments", []) if not a.get("done")]
        return render_template("profile.html", u=u, theme=theme(u), game=game,
                               course=course, nodes=nodes, next_ch=next_ch,
                               health=health, pending=pending,
                               announcements=users.announcements(),
                               teacher=users.teacher_name(),
                               persona=persona_for(u["profile"]),
                               summary=learner_summary(u["profile"]))

    @app.route("/rewards/<uid>", methods=["GET", "POST"])
    def rewards(uid):
        u = user_or_404(uid)
        message = None
        if request.method == "POST":
            name = request.form.get("name", "")
            try:
                cost = int(request.form.get("cost", "0"))
            except ValueError:
                cost = 0
            if users.redeem_reward(uid, name, cost):
                message = f"Enjoy it — {name} redeemed for {cost} coins."
            else:
                message = "Not enough coins yet. Complete a chapter (+25) first."
            u = users.get_user(uid)
        return render_template("rewards.html", u=u, theme=theme(u),
                               rewards=users.DEFAULT_REWARDS, message=message)

    @app.route("/course/<uid>")
    def course_view(uid):
        u = user_or_404(uid)
        if not u["profile"]:
            return redirect(url_for("questionnaire", uid=uid))
        return render_template("course.html", u=u, theme=theme(u),
                               course=cbse_math.get_course(u["course_id"]))

    def _chapter_context(u, idx, with_article=True):
        course = cbse_math.get_course(u["course_id"])
        if not 0 <= idx < len(course["chapters"]):
            abort(404)
        ch = course["chapters"][idx]
        plan = build_teaching_plan(
            u["profile"], u["content_level"],
            task={"subject": "Mathematics", "topic": ch["name"],
                  "difficulty": ""},
            live_resources=False)
        article = None
        if with_article and config.LIVE_RESOURCES:
            audience = "simplified" if u["mode"] == "specialized" else "standard"
            fetched = find_resources(ch["wiki"], "Mathematics",
                                     u["content_level"],
                                     u["profile"]["engagement_preference"],
                                     audience=audience)
            article = fetched["article"]
        links = cbse_math.chapter_links(u["course_id"], ch,
                                        u["profile"]["engagement_preference"])
        grade = "11" if "11" in u["course_id"] else "12"
        return dict(u=u, theme=theme(u), ch=ch, idx=idx, course=course,
                    plan=plan, article=article, links=links, grade=grade,
                    done=idx in u["completed_chapters"],
                    mentor_session=users.mentor_state(u["id"], idx),
                    flash=None)

    @app.route("/chapter/<uid>/<int:idx>")
    def chapter(uid, idx):
        u = user_or_404(uid)
        if not u["profile"]:
            return redirect(url_for("questionnaire", uid=uid))
        users.touch_activity(uid)
        return render_template("chapter.html", **_chapter_context(u, idx))

    @app.route("/chapter/<uid>/<int:idx>/complete", methods=["POST"])
    def chapter_complete(uid, idx):
        user_or_404(uid)
        users.complete_chapter(uid, idx)
        return redirect(url_for("profile", uid=uid))

    # ---------------- Socratic mentor ----------------

    @app.route("/chapter/<uid>/<int:idx>/mentor", methods=["POST"])
    def chapter_mentor(uid, idx):
        u = user_or_404(uid)
        from src.ai_integration import mentor
        ctx = _chapter_context(u, idx, with_article=False)
        message = request.form.get("message", "").strip()
        state = ctx["mentor_session"]
        if message:
            prompt = mentor.build_mentor_prompt(
                u, ctx["ch"], ctx["grade"], state["messages"], message)
            reply = _ask_ai(prompt)
            state["messages"].append({"role": "student", "text": message})
            state["messages"].append(
                {"role": "mentor", "text": reply["text"],
                 "off": not reply["available"]})
            users.save_mentor_state(uid, idx, state)
            users.touch_activity(uid)
        ctx["mentor_session"] = state
        return render_template("chapter.html", **ctx)

    @app.route("/chapter/<uid>/<int:idx>/mentor/reset", methods=["POST"])
    def chapter_mentor_reset(uid, idx):
        u = user_or_404(uid)
        state = users.mentor_state(uid, idx)
        state["messages"] = []
        users.save_mentor_state(uid, idx, state)
        return redirect(url_for("chapter", uid=uid, idx=idx))

    # ---------------- hint-ladder practice problems ----------------

    @app.route("/chapter/<uid>/<int:idx>/practice", methods=["POST"])
    def chapter_practice(uid, idx):
        u = user_or_404(uid)
        from src.ai_integration import mentor
        ctx = _chapter_context(u, idx, with_article=False)
        action = request.form.get("action", "new")
        state = ctx["mentor_session"]
        practice = state.get("practice")

        if action == "new":
            result = _ask_ai(mentor.build_practice_prompt(
                ctx["ch"], ctx["grade"],
                u.get("content_level") or "intermediate"))
            practice = (mentor.parse_practice(result["text"])
                        if result["available"] else None)
            state["practice"] = practice
            if not practice:
                ctx["flash"] = ("Could not generate a problem right now — "
                                "AI is off or returned an unusable answer. "
                                "Try again in a moment.")
        elif practice and not (practice["solved"] or practice["revealed"]):
            if action == "hint" and practice["hints_used"] < 4:
                practice["hints_used"] += 1
            elif action == "answer":
                given = request.form.get("answer", "")
                if mentor.check_answer(practice["answer"], given):
                    practice["solved"] = True
                    xp = mentor.practice_xp(practice["hints_used"])
                    users.award_xp(uid, xp, coins=xp // 5)
                    ctx["flash"] = (f"Correct! +{xp} XP "
                                    f"({practice['hints_used']} hints used — "
                                    "fewer hints, more XP).")
                else:
                    practice["attempts"] = practice.get("attempts", 0) + 1
                    ctx["flash"] = ("Not quite — check your working, or take "
                                    "a hint. You've got this.")
            elif action == "reveal":
                practice["revealed"] = True
                users.award_xp(uid, mentor.REVEAL_XP)
                ctx["flash"] = ("Solution revealed (+5 XP). Read each step, "
                                "then try a fresh problem without hints.")
        users.save_mentor_state(uid, idx, state)
        ctx["mentor_session"] = state
        return render_template("chapter.html", **ctx)

    # ---------------- adaptive quizzes ----------------

    def _judge_short_answer(question, expected, given):
        """AI-graded short answers with educational feedback."""
        from src.ai_integration import mentor as m
        result = _ask_ai(
            "You are grading one short-answer maths question. Return STRICT "
            'JSON only: {"correct": true/false, "feedback": "one or two '
            'sentences: why, and how to improve"}.\n'
            f"Question: {question}\nExpected: {expected}\nStudent: {given}")
        data = m.parse_json_block(result["text"]) if result["available"] else None
        if isinstance(data, dict) and "correct" in data:
            return bool(data["correct"]), str(data.get("feedback", ""))
        return (m.check_answer(expected, given),
                "(auto-checked against the expected answer)")

    def _start_quiz(u, questions, kind, chapter_index, title, quiz_id=""):
        users.set_pending_quiz(u["id"], {
            "questions": questions, "kind": kind, "quiz_id": quiz_id,
            "chapter_index": chapter_index, "title": title})
        return render_template("quiz.html", u=u, theme=theme(u), title=title,
                               questions=questions, kind=kind)

    @app.route("/chapter/<uid>/<int:idx>/quiz", methods=["POST"])
    def chapter_quiz(uid, idx):
        u = user_or_404(uid)
        from src.ai_integration import quizzes
        ctx = _chapter_context(u, idx, with_article=False)
        history = users.quiz_history(u, chapter_index=idx)
        _, note = quizzes.difficulty_for(u, history)
        weak = [c for c, _ in
                quizzes.wrong_concept_counts(u).most_common(3)]
        audience = "simplified" if u["mode"] == "specialized" else "standard"
        result = _ask_ai(quizzes.build_quiz_prompt(
            u, ctx["grade"], [ctx["ch"]["name"]] + ctx["ch"]["topics"][:2],
            "micro", note, weak, quizzes.recent_stems(u),
            quizzes.MICRO_SIZE, audience))
        questions = (quizzes.parse_quiz(result["text"])
                     if result["available"] else None)
        if not questions:
            ctx["flash"] = ("Quiz generation needs AI and a usable response "
                            "— try again in a moment.")
            return render_template("chapter.html", **ctx)
        return _start_quiz(u, questions, "micro", idx,
                           f"Micro-quiz — {ctx['ch']['name']}")

    @app.route("/quiz/<uid>/revision", methods=["POST"])
    def quiz_revision(uid):
        u = user_or_404(uid)
        from src.ai_integration import quizzes
        course = cbse_math.get_course(u["course_id"])
        topics = quizzes.revision_topics(u, course)
        if not topics:
            return redirect(url_for("profile", uid=uid))
        _, note = quizzes.difficulty_for(u, users.quiz_history(u))
        weak = [c for c, _ in
                quizzes.wrong_concept_counts(u).most_common(4)]
        audience = "simplified" if u["mode"] == "specialized" else "standard"
        grade = "11" if "11" in u["course_id"] else "12"
        result = _ask_ai(quizzes.build_quiz_prompt(
            u, grade, topics, "spaced-repetition revision", note, weak,
            quizzes.recent_stems(u), quizzes.REVISION_SIZE, audience))
        questions = (quizzes.parse_quiz(result["text"])
                     if result["available"] else None)
        if not questions:
            return redirect(url_for("profile", uid=uid))
        return _start_quiz(u, questions, "revision", None, "Weekly revision")

    @app.route("/quiz/<uid>/assigned/<qid>")
    def quiz_assigned(uid, qid):
        u = user_or_404(uid)
        qs = users.get_quiz_set(qid)
        if not qs or not qs["approved"]:
            abort(404)
        return _start_quiz(u, qs["questions"], "assigned",
                           qs["chapter_index"], qs["title"], quiz_id=qid)

    @app.route("/quiz/<uid>/submit", methods=["POST"])
    def quiz_submit(uid):
        u = user_or_404(uid)
        from src.ai_integration import quizzes
        pending = users.pop_pending_quiz(uid)
        if not pending:
            return redirect(url_for("profile", uid=uid))
        judge = _judge_short_answer if config.AI_PROVIDER else None
        graded = quizzes.grade_quiz(pending["questions"], request.form,
                                    judge=judge)
        users.record_quiz(uid, {
            "kind": pending["kind"], "chapter_index": pending["chapter_index"],
            "quiz_id": pending.get("quiz_id", ""),
            "score": graded["score"], "total": graded["total"],
            "wrong_concepts": graded["wrong_concepts"],
            "stems": graded["stems"]})
        xp = quizzes.quiz_xp(graded["score"], graded["total"])
        users.award_xp(uid, xp, coins=xp // 5)
        if pending.get("quiz_id"):
            users.mark_quiz_assignment_done(uid, pending["quiz_id"])
            users.record_quiz_submission(
                pending["quiz_id"], uid, u["name"], graded["score"],
                graded["total"], graded["results"])
        users.touch_activity(uid)
        u = users.get_user(uid)
        return render_template("quiz_result.html", u=u, theme=theme(u),
                               title=pending["title"], graded=graded, xp=xp,
                               chapter_index=pending["chapter_index"])

    # ---------------- teacher portal ----------------

    def teacher_required():
        if not session.get("teacher"):
            abort(redirect(url_for("teacher_login")))

    def _roster():
        rows = []
        for u2 in users.all_users().values():
            if not u2.get("profile"):
                continue
            course = cbse_math.get_course(u2["course_id"])
            game = users.game_state(u2)
            dims = _dimensions(u2["profile"])
            progress = round(len(u2["completed_chapters"])
                             / len(course["chapters"]) * 100)
            rows.append({
                "user": u2, "game": game, "dims": dims, "progress": progress,
                "streak": game["streak"], "course": course,
                "status": teacher_engine.student_status(
                    u2, dims, game["streak"], progress),
            })
        rows.sort(key=lambda r: teacher_engine.STATUS_ORDER.index(r["status"]))
        return rows

    @app.route("/teacher")
    def teacher_login():
        if session.get("teacher"):
            return redirect(url_for("teacher_dashboard"))
        return render_template("teacher/login.html", theme="game")

    @app.route("/teacher", methods=["POST"])
    def teacher_login_post():
        name = request.form.get("name", "").strip() or "Teacher"
        session["teacher"] = name
        users.set_teacher(name)
        return redirect(url_for("teacher_dashboard"))

    @app.route("/teacher/switch")
    def teacher_switch():
        # Sign the current teacher out so another teacher can sign in.
        session.pop("teacher", None)
        return redirect(url_for("teacher_login"))

    @app.route("/teacher/dashboard")
    def teacher_dashboard():
        teacher_required()
        rows = _roster()
        return render_template("teacher/dashboard.html", theme="game",
                               rows=rows, teacher=session["teacher"],
                               insights=teacher_engine.class_insights(rows)[:2])

    @app.route("/teacher/student/<uid>")
    def teacher_student(uid):
        teacher_required()
        u = user_or_404(uid)
        if not u.get("profile"):
            return redirect(url_for("teacher_dashboard"))
        from src.ai_integration import quizzes
        row = next(r for r in _roster() if r["user"]["id"] == uid)
        guide = teacher_engine.teaching_guide(u["profile"], u["content_level"])
        return render_template("teacher/student.html", theme="game", r=row,
                               u=u, teacher=session["teacher"], guide=guide,
                               persona=persona_for(u["profile"]),
                               summary=learner_summary(u["profile"]),
                               concept_gaps=quizzes.wrong_concept_counts(
                                   u).most_common(6),
                               quiz_log=list(reversed(
                                   users.quiz_history(u)))[:8],
                               course=cbse_math.get_course(u["course_id"]))

    # ---------------- teacher quiz sets (review -> approve -> assign) ------

    @app.route("/teacher/quizzes", methods=["GET"])
    def teacher_quizzes():
        teacher_required()
        return render_template("teacher/quizzes.html", theme="game",
                               teacher=session["teacher"],
                               courses=cbse_math.COURSES,
                               quiz_sets=users.all_quiz_sets(),
                               students=[r["user"] for r in _roster()],
                               editing=None, flash=request.args.get("m"))

    @app.route("/teacher/quizzes/generate", methods=["POST"])
    def teacher_quiz_generate():
        teacher_required()
        from src.ai_integration import quizzes
        course_id = request.form.get("course_id", "cbse-12-math")
        idx = int(request.form.get("chapter", 0) or 0)
        difficulty = request.form.get("difficulty", "standard")
        course = cbse_math.get_course(course_id)
        idx = max(0, min(idx, len(course["chapters"]) - 1))
        ch = course["chapters"][idx]
        grade = "11" if "11" in course_id else "12"
        result = _ask_ai(quizzes.build_quiz_prompt(
            {}, grade, [ch["name"]] + ch["topics"][:2], "class",
            f"Difficulty: {difficulty}.", [], [], quizzes.REVISION_SIZE,
            "standard"))
        questions = (quizzes.parse_quiz(result["text"])
                     if result["available"] else None)
        if not questions:
            return redirect(url_for("teacher_quizzes",
                                    m="Generation failed — is AI configured?"))
        qid = users.save_quiz_set(idx, f"{ch['name']} — class quiz "
                                       f"({difficulty})", questions)
        return redirect(url_for("teacher_quiz_edit", qid=qid))

    @app.route("/teacher/quizzes/<qid>/edit")
    def teacher_quiz_edit(qid):
        teacher_required()
        qs = users.get_quiz_set(qid) or abort(404)
        return render_template("teacher/quizzes.html", theme="game",
                               teacher=session["teacher"],
                               courses=cbse_math.COURSES,
                               quiz_sets=users.all_quiz_sets(),
                               students=[r["user"] for r in _roster()],
                               editing=qs, flash=None)

    @app.route("/teacher/quizzes/<qid>/save", methods=["POST"])
    def teacher_quiz_save(qid):
        teacher_required()
        qs = users.get_quiz_set(qid) or abort(404)
        questions = []
        for i, q in enumerate(qs["questions"]):
            if request.form.get(f"drop{i}"):
                continue
            q = dict(q)
            q["q"] = request.form.get(f"q{i}", q["q"]).strip() or q["q"]
            q["answer"] = (request.form.get(f"a{i}", q["answer"]).strip()
                           or q["answer"])
            q["explanation"] = request.form.get(
                f"e{i}", q.get("explanation", "")).strip()
            questions.append(q)
        approved = bool(request.form.get("approve"))
        users.update_quiz_set(qid, questions=questions, approved=approved)
        m = ("Approved — you can now assign it."
             if approved else "Saved as draft.")
        return redirect(url_for("teacher_quizzes", m=m))

    @app.route("/teacher/quizzes/<qid>/assign", methods=["POST"])
    def teacher_quiz_assign(qid):
        teacher_required()
        qs = users.get_quiz_set(qid) or abort(404)
        if not qs["approved"]:
            return redirect(url_for("teacher_quizzes",
                                    m="Approve the quiz before assigning."))
        users.assign_task(request.form.get("uid", "all"),
                          qs["chapter_index"],
                          f"Quiz: {qs['title']}",
                          request.form.get("due", ""), quiz_id=qid)
        return redirect(url_for("teacher_quizzes", m="Quiz assigned."))

    @app.route("/teacher/quizzes/<qid>/results")
    def teacher_quiz_results(qid):
        teacher_required()
        qs = users.get_quiz_set(qid) or abort(404)
        analytics = teacher_engine.quiz_set_analytics(
            qs, len(users.quiz_assignees(qid)))
        return render_template("teacher/quiz_results.html", theme="game",
                               teacher=session["teacher"], qs=qs,
                               a=analytics)

    @app.route("/teacher/quizzes/<qid>/delete", methods=["POST"])
    def teacher_quiz_delete(qid):
        teacher_required()
        users.delete_quiz_set(qid)
        return redirect(url_for("teacher_quizzes", m="Quiz set deleted."))

    @app.route("/teacher/planner", methods=["GET", "POST"])
    def teacher_planner():
        teacher_required()
        plan = None
        course_id = request.form.get("course_id", "cbse-11-math")
        chapter_idx = int(request.form.get("chapter", 0) or 0)
        minutes = int(request.form.get("minutes", 40) or 40)
        if request.method == "POST":
            course = cbse_math.get_course(course_id)
            chapter_idx = max(0, min(chapter_idx, len(course["chapters"]) - 1))
            class_records = [r["user"] for r in _roster()
                             if r["user"]["course_id"] == course_id] or \
                            [r["user"] for r in _roster()]
            plan = teacher_engine.lesson_plan(
                course, course["chapters"][chapter_idx], minutes, class_records)
        return render_template("teacher/planner.html", theme="game",
                               teacher=session["teacher"],
                               courses=cbse_math.COURSES, plan=plan,
                               sel_course=course_id, sel_chapter=chapter_idx,
                               sel_minutes=minutes)

    @app.route("/teacher/insights")
    def teacher_insights():
        teacher_required()
        rows = _roster()
        # class-wide domain mastery for the constellation map
        domains = {d: 0 for d in cbse_math.DOMAINS}
        for r in rows:
            prog = cbse_math.domain_progress(r["user"]["course_id"],
                                             r["user"]["completed_chapters"])
            for d, v in prog.items():
                domains[d] += v
        n = max(1, len(rows))
        import math as _m
        nodes = []
        for i, d in enumerate(cbse_math.DOMAINS):
            angle = 2 * _m.pi * i / len(cbse_math.DOMAINS) - _m.pi / 2
            nodes.append({"name": d, "mastery": round(domains[d] / n),
                          "x": round(170 + 120 * _m.cos(angle), 1),
                          "y": round(170 + 120 * _m.sin(angle), 1)})
        return render_template("teacher/insights.html", theme="game",
                               teacher=session["teacher"], rows=rows,
                               nodes=nodes,
                               insights=teacher_engine.class_insights(rows))

    @app.route("/teacher/assign", methods=["POST"])
    def teacher_assign():
        teacher_required()
        chapter_no = max(1, int(request.form.get("chapter", 1) or 1))
        users.assign_task(request.form.get("uid", "all"),
                          chapter_no - 1,  # form is 1-based
                          request.form.get("note", ""),
                          request.form.get("due", ""))
        return redirect(request.form.get("back")
                        or url_for("teacher_dashboard"))

    @app.route("/teacher/announce", methods=["POST"])
    def teacher_announce():
        teacher_required()
        msg = request.form.get("message", "").strip()
        if msg:
            users.announce(msg)
        return redirect(url_for("teacher_dashboard"))

    # ---------------- knowledge library ----------------

    def _library_con():
        from src.library import store as lib_store
        return lib_store.connect()

    @app.route("/library/<uid>")
    def library(uid):
        u = user_or_404(uid)
        if not u["profile"]:
            return redirect(url_for("questionnaire", uid=uid))
        from src.library import search as lib_search, store as lib_store
        q = request.args.get("q", "").strip()
        con = _library_con()
        hits = (lib_search.hybrid_search(con, q, k=10, profile=u["profile"],
                                         visibility_for=uid) if q else [])
        my_docs = lib_store.list_documents(con, visibility_for=uid,
                                           source="student")
        my_docs = [d for d in my_docs if d["uploader"] == uid]
        st = lib_store.stats(con)
        con.close()
        return render_template("library.html", u=u, theme=theme(u), q=q,
                               hits=hits, my_docs=my_docs, stats=st,
                               message=None)

    @app.route("/library/<uid>/upload", methods=["POST"])
    def library_upload(uid):
        u = user_or_404(uid)
        from src.library import pipeline as lib_pipeline, store as lib_store
        title = request.form.get("title", "").strip() or "My notes"
        text = request.form.get("text", "")
        f = request.files.get("file")
        con = _library_con()
        try:
            if f and f.filename.lower().endswith(".pdf"):
                r = lib_pipeline.ingest_pdf(
                    con, f.read(), fallback_title=title, title=title,
                    source="student", license="uploader",
                    redistribute_allowed=True, uploader=uid,
                    visibility="private",
                    attribution=f"Uploaded by {u['name']}")
            else:
                if f and f.filename:
                    text = f.read().decode("utf-8", errors="ignore")
                r = lib_pipeline.ingest(
                    con, title=title, text=text, source="student",
                    license="uploader", redistribute_allowed=True,
                    uploader=uid, visibility="private",
                    attribution=f"Uploaded by {u['name']}")
            message = (f"Added “{title}” to your library "
                       f"({r['chunks']} searchable sections)."
                       if r["doc_id"] else "Nothing readable found in that upload.")
        except Exception as exc:
            message = f"Upload failed: {exc}"
        my_docs = [d for d in lib_store.list_documents(
            con, visibility_for=uid, source="student")
            if d["uploader"] == uid]
        con.close()
        return render_template("library.html", u=u, theme=theme(u), q="",
                               hits=[], my_docs=my_docs, stats=None,
                               message=message)

    @app.route("/library/<uid>/lesson")
    def library_lesson(uid):
        u = user_or_404(uid)
        if not u["profile"]:
            return redirect(url_for("questionnaire", uid=uid))
        from src.library import composer
        q = request.args.get("q", "").strip()
        if not q:
            return redirect(url_for("library", uid=uid))
        audience = "simplified" if u["mode"] == "specialized" else "standard"
        con = _library_con()
        lesson = composer.build_lesson(con, q, profile=u["profile"],
                                       audience=audience, visibility_for=uid)
        con.close()
        users.touch_activity(uid)
        return render_template("lesson.html", u=u, theme=theme(u),
                               lesson=lesson)

    @app.route("/library/<uid>/doc/<int:doc_id>", methods=["GET", "POST"])
    def library_doc(uid, doc_id):
        """'Answer from this PDF only' — Q&A scoped to one document."""
        u = user_or_404(uid)
        if not u["profile"]:
            return redirect(url_for("questionnaire", uid=uid))
        from src.library import composer, store as lib_store
        con = _library_con()
        doc = lib_store.get_document(con, doc_id)
        if (doc is None or not doc["redistribute_allowed"] or
                (doc["visibility"] == "private" and doc["uploader"] != uid)):
            con.close()
            abort(404)
        question = request.form.get("question", "").strip()
        answer = None
        if request.method == "POST" and question:
            audience = ("simplified" if u["mode"] == "specialized"
                        else "standard")
            answer = composer.answer_from_doc(con, doc, question, audience)
            users.touch_activity(uid)
        con.close()
        return render_template("doc_qa.html", u=u, theme=theme(u), doc=doc,
                               question=question, answer=answer)

    @app.route("/teacher/upload", methods=["POST"])
    def teacher_upload():
        teacher_required()
        from src.library import pipeline as lib_pipeline
        title = request.form.get("title", "").strip() or "Class material"
        rtype = request.form.get("resource_type", "notes")
        text = request.form.get("text", "")
        f = request.files.get("file")
        con = _library_con()
        try:
            common = dict(source="teacher", license="uploader",
                          redistribute_allowed=True, visibility="public",
                          teacher_endorsed=True, resource_type=rtype,
                          attribution=f"Shared by {session['teacher']}")
            if f and f.filename.lower().endswith(".pdf"):
                r = lib_pipeline.ingest_pdf(con, f.read(),
                                            fallback_title=title,
                                            title=title, **common)
            else:
                if f and f.filename:
                    text = f.read().decode("utf-8", errors="ignore")
                r = lib_pipeline.ingest(con, title=title, text=text, **common)
        finally:
            con.close()
        return redirect(url_for("teacher_dashboard"))

    # ---------------- notes ----------------

    @app.route("/notes/<uid>", methods=["GET", "POST"])
    def notes(uid):
        u = user_or_404(uid)
        summary = None
        if request.method == "POST":
            text = request.form.get("text", "")
            f = request.files.get("file")
            if f and f.filename:
                try:
                    text = f.read().decode("utf-8", errors="ignore")
                except Exception:
                    text = ""
            summary = summarize(text, max_sentences=5)
            if summary:
                title = (request.form.get("title") or "Untitled notes").strip()
                stored = u["notes"] + [{"title": title, "summary": summary}]
                users.update_user(uid, notes=stored)
                u = users.get_user(uid)
        return render_template("notes.html", u=u, theme=theme(u),
                               summary=summary)

    # ---------------- friendly error pages ----------------

    def _error_page(status, heading, detail, advice):
        return render_template(
            "error.html", theme="game", heading=heading, detail=detail,
            advice=advice), status

    @app.errorhandler(404)
    def not_found(e):
        return _error_page(
            404, "That page isn't here",
            "The link may be old, or the item it pointed to was removed.",
            "Check the address, or head back and navigate from there.")

    @app.errorhandler(413)
    def too_large(e):
        return _error_page(
            413, "That file is too large",
            "The upload exceeded the size limit.",
            "Try a smaller file, or split the material into parts.")

    @app.errorhandler(500)
    def server_error(e):
        app.logger.exception("Unhandled error: %s", e)
        return _error_page(
            500, "Something went wrong on our side",
            "The action didn't complete — this is our fault, not yours.",
            "Go back and try once more; if it keeps happening, the server "
            "log has the details.")

    return app


if __name__ == "__main__":
    # port 5050: macOS AirPlay commonly occupies 5000
    create_app().run(host="127.0.0.1", port=5050, debug=False)
