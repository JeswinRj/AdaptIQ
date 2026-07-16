"""Per-user profile store (JSON file; swap for a DB later).

A profile records: identity, chosen mode (regular | specialized), course,
questionnaire answers, computed learner profile + predicted level, and real
progression state (XP, completed chapters, streak days).
"""
import json
import uuid
from datetime import date

import config

USERS_PATH = config.DATA_DIR / "users.json"
CLASSROOM_PATH = config.DATA_DIR / "classroom.json"

XP_PER_CHAPTER = 80
XP_PER_LEVEL = 150
COINS_PER_CHAPTER = 25

# Habitica-style "reward yourself" shop (real-life rewards, modern UI).
DEFAULT_REWARDS = [
    {"id": "episode", "icon": "📺", "name": "Watch an episode", "cost": 20},
    {"id": "gaming", "icon": "🎮", "name": "30 minutes of gaming", "cost": 30},
    {"id": "snack", "icon": "🍫", "name": "Favourite snack", "cost": 15},
    {"id": "music", "icon": "🎧", "name": "Music break", "cost": 10},
    {"id": "outing", "icon": "🏏", "name": "Evening out with friends", "cost": 60},
    {"id": "sleepin", "icon": "😴", "name": "Guilt-free lie-in", "cost": 50},
]


def _load() -> dict:
    if USERS_PATH.exists():
        return json.loads(USERS_PATH.read_text())
    return {}


def _save(users: dict):
    USERS_PATH.write_text(json.dumps(users, indent=2))


def create_user(name: str, mode: str, course_id: str) -> str:
    users = _load()
    uid = uuid.uuid4().hex[:10]
    users[uid] = {
        "id": uid,
        "name": name.strip() or "Learner",
        "mode": mode if mode in ("regular", "specialized") else "regular",
        "course_id": course_id,
        "answers": {},
        "profile": None,          # learner features after questionnaire
        "content_level": None,    # ML prediction
        "xp": 0,
        "coins": 0,
        "redeemed": [],           # [{"name","cost","date"}]
        "assignments": [],        # [{"id","chapter_index","note","due","done"}]
        "completed_chapters": [],
        "active_days": [],        # ISO dates with activity (streak source)
        "notes": [],              # [{"title","summary"}]
    }
    _save(users)
    return uid


def get_user(uid: str):
    return _load().get(uid)


def all_users() -> dict:
    return _load()


def update_user(uid: str, **fields):
    users = _load()
    if uid not in users:
        raise KeyError(uid)
    users[uid].update(fields)
    _save(users)
    return users[uid]


def touch_activity(uid: str):
    users = _load()
    today = date.today().isoformat()
    if today not in users[uid]["active_days"]:
        users[uid]["active_days"].append(today)
        _save(users)


def complete_chapter(uid: str, chapter_index: int) -> dict:
    users = _load()
    u = users[uid]
    if chapter_index not in u["completed_chapters"]:
        u["completed_chapters"].append(chapter_index)
        u["xp"] += XP_PER_CHAPTER
        u["coins"] = u.get("coins", 0) + COINS_PER_CHAPTER
        for a in u.get("assignments", []):
            if a.get("chapter_index") == chapter_index:
                a["done"] = True
        today = date.today().isoformat()
        if today not in u["active_days"]:
            u["active_days"].append(today)
        _save(users)
    return u


def award_xp(uid: str, xp: int, coins: int = 0):
    """Generic XP/coin award (mentor problems solved, quizzes aced...)."""
    users = _load()
    u = users[uid]
    u["xp"] = u.get("xp", 0) + max(0, xp)
    u["coins"] = u.get("coins", 0) + max(0, coins)
    _save(users)
    return u


# ---- mentor sessions (Socratic dialogue + practice problems) --------------

def mentor_state(uid: str, chapter_index: int) -> dict:
    u = _load()[uid]
    key = str(chapter_index)
    state = u.get("mentor", {}).get(key)
    return state or {"messages": [], "practice": None}


def save_mentor_state(uid: str, chapter_index: int, state: dict):
    users = _load()
    u = users[uid]
    state["messages"] = state.get("messages", [])[-16:]   # cap the thread
    u.setdefault("mentor", {})[str(chapter_index)] = state
    _save(users)


# ---- quiz history (adaptive difficulty + spaced repetition) ----------------

def record_quiz(uid: str, entry: dict):
    """entry: {kind, chapter_index, score, total, wrong_concepts, stems}."""
    users = _load()
    u = users[uid]
    entry["date"] = date.today().isoformat()
    u.setdefault("quiz_history", []).append(entry)
    u["quiz_history"] = u["quiz_history"][-40:]
    _save(users)


def quiz_history(user: dict, chapter_index=None, kind=None) -> list:
    out = user.get("quiz_history", [])
    if chapter_index is not None:
        out = [q for q in out if q.get("chapter_index") == chapter_index]
    if kind:
        out = [q for q in out if q.get("kind") == kind]
    return out


def set_pending_quiz(uid: str, quiz: dict):
    users = _load()
    users[uid]["pending_quiz"] = quiz
    _save(users)


def pop_pending_quiz(uid: str):
    users = _load()
    quiz = users[uid].pop("pending_quiz", None)
    _save(users)
    return quiz


def redeem_reward(uid: str, name: str, cost: int) -> bool:
    """Spend coins on a real-life reward. Returns False if unaffordable."""
    users = _load()
    u = users[uid]
    if u.get("coins", 0) < cost:
        return False
    u["coins"] -= cost
    u.setdefault("redeemed", []).append(
        {"name": name, "cost": cost, "date": date.today().isoformat()})
    _save(users)
    return True


# ---- classroom (teacher portal): assignments + announcements --------------

def _load_classroom() -> dict:
    if CLASSROOM_PATH.exists():
        return json.loads(CLASSROOM_PATH.read_text())
    return {"teacher_name": "", "announcements": []}


def _save_classroom(c: dict):
    CLASSROOM_PATH.write_text(json.dumps(c, indent=2))


def set_teacher(name: str):
    c = _load_classroom()
    c["teacher_name"] = name.strip() or "Teacher"
    _save_classroom(c)


def teacher_name() -> str:
    return _load_classroom().get("teacher_name", "")


def announce(message: str):
    c = _load_classroom()
    c["announcements"].append(
        {"message": message.strip(), "date": date.today().isoformat()})
    _save_classroom(c)


def announcements(limit: int = 3) -> list:
    return list(reversed(_load_classroom().get("announcements", [])))[:limit]


def assign_task(uid: str, chapter_index: int, note: str, due: str,
                quiz_id: str = ""):
    """Assign a chapter (or an approved quiz set) to one student or 'all'."""
    users = _load()
    targets = list(users) if uid == "all" else [uid]
    for t in targets:
        users[t].setdefault("assignments", []).append({
            "id": uuid.uuid4().hex[:6],
            "chapter_index": chapter_index,
            "note": note.strip(),
            "due": due,
            "quiz_id": quiz_id,
            "done": (not quiz_id and
                     chapter_index in users[t].get("completed_chapters", [])),
        })
    _save(users)


def mark_quiz_assignment_done(uid: str, quiz_id: str):
    users = _load()
    for a in users[uid].get("assignments", []):
        if a.get("quiz_id") == quiz_id:
            a["done"] = True
    _save(users)


# ---- teacher quiz sets (review -> edit -> approve -> assign) ---------------

def save_quiz_set(chapter_index: int, title: str, questions: list) -> str:
    c = _load_classroom()
    qid = uuid.uuid4().hex[:8]
    c.setdefault("quiz_sets", []).append({
        "id": qid, "chapter_index": chapter_index, "title": title,
        "questions": questions, "approved": False,
        "created": date.today().isoformat()})
    _save_classroom(c)
    return qid


def get_quiz_set(qid: str):
    for qs in _load_classroom().get("quiz_sets", []):
        if qs["id"] == qid:
            return qs
    return None


def update_quiz_set(qid: str, **fields):
    c = _load_classroom()
    for qs in c.get("quiz_sets", []):
        if qs["id"] == qid:
            qs.update(fields)
            _save_classroom(c)
            return qs
    raise KeyError(qid)


def delete_quiz_set(qid: str):
    c = _load_classroom()
    c["quiz_sets"] = [q for q in c.get("quiz_sets", []) if q["id"] != qid]
    _save_classroom(c)


def all_quiz_sets() -> list:
    return list(reversed(_load_classroom().get("quiz_sets", [])))


def quiz_assignees(qid: str) -> list:
    """User ids that have been assigned this quiz set (participation base)."""
    return [uid for uid, u in _load().items()
            if any(a.get("quiz_id") == qid for a in u.get("assignments", []))]


def record_quiz_submission(qid: str, uid: str, name: str, score: int,
                           total: int, results: list):
    """Attach a student's graded submission to the quiz set so the teacher can
    review participation and solutions. One submission per student — a retake
    replaces the earlier attempt but keeps the first-seen timestamp."""
    c = _load_classroom()
    for qs in c.get("quiz_sets", []):
        if qs["id"] != qid:
            continue
        subs = qs.setdefault("submissions", [])
        existing = next((s for s in subs if s["uid"] == uid), None)
        entry = {"uid": uid, "name": name, "score": score, "total": total,
                 "results": results, "date": date.today().isoformat(),
                 "attempts": (existing["attempts"] + 1) if existing else 1}
        if existing:
            entry["first_date"] = existing.get("first_date", existing["date"])
            subs[subs.index(existing)] = entry
        else:
            entry["first_date"] = entry["date"]
            subs.append(entry)
        _save_classroom(c)
        return
    # No such quiz set (e.g. deleted mid-quiz) — nothing to attach to.


def streak(user: dict) -> int:
    """Consecutive active days ending today (or yesterday)."""
    days = sorted(user.get("active_days", []), reverse=True)
    if not days:
        return 0
    from datetime import datetime, timedelta
    run, cursor = 0, date.today()
    day_set = set(days)
    if cursor.isoformat() not in day_set:
        cursor -= timedelta(days=1)   # streak survives until a full day is missed
    while cursor.isoformat() in day_set:
        run += 1
        cursor -= timedelta(days=1)
    return run


def game_state(user: dict) -> dict:
    xp = user["xp"]
    level = 1 + xp // XP_PER_LEVEL
    s = streak(user)
    hp = min(50, 25 + 5 * s)          # display energy, grows with streak
    badges = []
    n_done = len(user["completed_chapters"])
    if n_done >= 1:
        badges.append(("⚔️", "First Chapter Cleared"))
    if n_done >= 5:
        badges.append(("🏰", "Five Strongholds Taken"))
    if s >= 3:
        badges.append(("🔥", f"{s}-day streak"))
    if user.get("profile") and user["profile"]["metacognition"] >= 3:
        badges.append(("🪞", "Self-Aware Learner"))
    if not badges:
        badges.append(("🌱", "Adventure Begins"))
    return {"xp": xp, "level": level, "xp_into_level": xp % XP_PER_LEVEL,
            "xp_for_level": XP_PER_LEVEL, "hp": hp, "hp_max": 50,
            "streak": s, "badges": badges,
            "chapters_done": n_done}
