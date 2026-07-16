import pytest

import config
from src.dashboard import users
from src.dashboard.app import create_app
from tests.conftest import full_answers


@pytest.fixture(scope="module", autouse=True)
def offline_resources():
    old = config.LIVE_RESOURCES
    config.LIVE_RESOURCES = False
    yield
    config.LIVE_RESOURCES = old


@pytest.fixture(scope="module")
def client():
    app = create_app()
    app.testing = True
    return app.test_client()


def _onboard(client, mode="regular", name="Test Learner",
             course="cbse-12-math"):
    resp = client.post(f"/start/{mode}",
                       data={"name": name, "course_id": course})
    assert resp.status_code == 302
    uid = resp.location.rstrip("/").split("/")[-1]
    resp = client.post(f"/questionnaire/{uid}", data=full_answers())
    assert resp.status_code == 302 and "/report/" in resp.location
    return uid


def test_landing_shows_all_entries(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Regular Student" in resp.data
    assert b"Special Learning Support" in resp.data
    assert b"Teacher Portal" in resp.data and b"Enter" in resp.data


def test_full_regular_flow(client):
    uid = _onboard(client)
    u = users.get_user(uid)
    assert u["profile"]["learning_method"] in (
        "memorizer", "example_driven", "conceptual", "visual_learner",
        "practice_driven")
    assert u["content_level"] in ("basic", "intermediate", "advanced")

    report = client.get(f"/report/{uid}")
    assert report.status_code == 200
    assert b"Learning Report" in report.data
    assert b"Based on your responses" in report.data
    # never a fixed learning-style label
    assert b"visual learner" not in report.data.lower()

    profile = client.get(f"/profile/{uid}")
    assert profile.status_code == 200
    for token in (b"XP", b"Learning health", b"Skill map", b"streak"):
        assert token in profile.data

    course = client.get(f"/course/{uid}")
    assert b"Matrices" in course.data  # class 12 chapter

    chapter = client.get(f"/chapter/{uid}/2")  # Matrices
    assert chapter.status_code == 200
    assert b"Session plan" in chapter.data
    assert b"NCERT" in chapter.data


def test_chapter_completion_awards_xp(client):
    uid = _onboard(client)
    before = users.get_user(uid)["xp"]
    resp = client.post(f"/chapter/{uid}/0/complete")
    assert resp.status_code == 302
    after = users.get_user(uid)
    assert after["xp"] == before + users.XP_PER_CHAPTER
    assert 0 in after["completed_chapters"]
    # completing again does not double-award
    client.post(f"/chapter/{uid}/0/complete")
    assert users.get_user(uid)["xp"] == after["xp"]


def test_specialized_mode_is_parent_guided_and_simplified(client):
    uid = _onboard(client, mode="specialized", name="Ravi")
    report = client.get(f"/report/{uid}")
    assert b"For the parent" in report.data

    chapter = client.get(f"/chapter/{uid}/0")
    assert b"For the parent" in chapter.data
    assert b"Today's steps" in chapter.data
    assert b"Session plan" not in chapter.data   # no game framing
    profile = client.get(f"/profile/{uid}")
    assert b"XP" not in profile.data             # no game stats in calm mode
    assert b"progress" in profile.data.lower()


def test_questionnaire_required_before_results(client):
    resp = client.post("/start/regular",
                       data={"name": "Skipper", "course_id": "cbse-11-math"})
    uid = resp.location.rstrip("/").split("/")[-1]
    for page in ("report", "profile", "course"):
        resp = client.get(f"/{page}/{uid}")
        assert resp.status_code == 302
        assert "/questionnaire/" in resp.location


def test_mentor_offline_fallback(client):
    uid = _onboard(client)
    resp = client.post(f"/chapter/{uid}/0/mentor",
                       data={"message": "What is a relation?"})
    assert resp.status_code == 200
    assert b"AI is not configured yet" in resp.data
    # the student's message is kept in the thread
    assert b"What is a relation?" in resp.data


def test_coins_earned_and_rewards_redeemed(client):
    uid = _onboard(client)
    assert users.get_user(uid)["coins"] == 0
    client.post(f"/chapter/{uid}/0/complete")
    assert users.get_user(uid)["coins"] == users.COINS_PER_CHAPTER
    resp = client.post(f"/rewards/{uid}",
                       data={"name": "Favourite snack", "cost": "15"})
    assert b"redeemed" in resp.data
    assert users.get_user(uid)["coins"] == 10
    resp = client.post(f"/rewards/{uid}",
                       data={"name": "Evening out with friends", "cost": "60"})
    assert b"Not enough coins" in resp.data
    assert users.get_user(uid)["coins"] == 10


def test_quiz_generation_offline_fallback(client):
    uid = _onboard(client)
    resp = client.post(f"/chapter/{uid}/0/quiz")
    assert resp.status_code == 200
    assert b"Quiz generation needs AI" in resp.data


def test_teacher_portal_flow(client):
    student = _onboard(client, name="Priya Gupta")
    # login
    resp = client.get("/teacher")
    assert b"Teacher Portal" in resp.data
    resp = client.post("/teacher", data={"name": "Mrs. Nair"})
    assert resp.status_code == 302
    # roster
    resp = client.get("/teacher/dashboard")
    assert resp.status_code == 200
    assert b"Priya Gupta" in resp.data
    # student detail with adaptive teaching guide
    resp = client.get(f"/teacher/student/{student}")
    assert b"Adaptive teaching guide" in resp.data
    assert b"Introducing concepts" in resp.data
    # lesson planner
    resp = client.post("/teacher/planner", data={
        "course_id": "cbse-12-math", "chapter": "2", "minutes": "40"})
    assert b"Matrices" in resp.data and b"Sequence" in resp.data
    # insights
    resp = client.get("/teacher/insights")
    assert resp.status_code == 200
    assert b"Class mastery map" in resp.data


def test_assignment_reaches_student_and_completes(client):
    student = _onboard(client, name="Dev Menon")
    client.post("/teacher", data={"name": "Mrs. Nair"})
    client.post("/teacher/assign", data={
        "uid": student, "chapter": "3", "note": "Before Friday", "due": "Friday"})
    client.post("/teacher/announce", data={"message": "Unit test on Monday."})
    # appears on the student's home page
    resp = client.get(f"/profile/{student}")
    assert b"Before Friday" in resp.data
    assert b"Unit test on Monday." in resp.data
    # completing the chapter marks it done
    client.post(f"/chapter/{student}/2/complete")  # chapter 3 is index 2
    u = users.get_user(student)
    assert all(a["done"] for a in u["assignments"]
               if a["chapter_index"] == 2)


def test_friendly_error_pages(client):
    resp = client.get("/definitely/not/a/page")
    assert resp.status_code == 404
    assert b"That page" in resp.data          # friendly page, not a stack trace
    assert b"Go to the start page" in resp.data
    resp = client.get("/profile/no-such-user")
    assert resp.status_code == 404
    assert b"That page" in resp.data


def test_loading_states_wired(client):
    """Slow actions carry data-busy hooks so busy.js can show progress."""
    uid = _onboard(client)
    resp = client.get(f"/chapter/{uid}/0")
    assert b"busy.js" in resp.data
    assert b'data-busy="mentor"' in resp.data
    assert b'data-busy="practice"' in resp.data
    assert b'data-busy="quiz"' in resp.data
    resp = client.get(f"/library/{uid}")
    assert b'data-busy="search"' in resp.data
    assert b'data-busy="upload"' in resp.data


def test_home_page_has_nav_tiles(client):
    uid = _onboard(client)
    resp = client.get(f"/profile/{uid}")
    assert b"home-tiles" in resp.data
    # each destination is reachable as a clickable tile from home
    for token in (b"Course", b"Report", b"Library", b"Notes", b"Rewards"):
        assert token in resp.data
    assert f"/course/{uid}".encode() in resp.data
    assert f"/library/{uid}".encode() in resp.data


def test_notes_summarize(client):
    uid = _onboard(client)
    text = ("Integration is the reverse of differentiation. "
            "The integral of x^n is x^(n+1)/(n+1) plus a constant. "
            "I had lunch at noon. "
            "Definite integrals compute the area under a curve. "
            "Substitution simplifies composite integrals.")
    resp = client.post(f"/notes/{uid}",
                       data={"title": "Integrals", "text": text})
    assert resp.status_code == 200
    assert b"Summary" in resp.data
    assert users.get_user(uid)["notes"][-1]["title"] == "Integrals"
