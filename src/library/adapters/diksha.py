"""DIKSHA adapter — India's national school platform, CC-licensed content.

DIKSHA items (videos, interactive lessons, question sets) play on DIKSHA
itself, so they are indexed as link records: we store OUR OWN metadata text
(name/description/keywords) for search, record the item's actual CC license
verbatim, and results open on diksha.gov.in. Only CC-licensed items are
accepted; anything else is dropped at normalization.
"""
import time

import requests

from src.library import pipeline, store

SEARCH_API = "https://diksha.gov.in/api/content/v1/search"
PLAY_URL = "https://diksha.gov.in/play/content/{id}"
PLAY_COLLECTION_URL = "https://diksha.gov.in/play/collection/{id}"
FIELDS = ["name", "description", "keywords", "subject", "gradeLevel",
          "license", "identifier", "mimeType", "primaryCategory"]
GRADES = ["Class 11", "Class 12"]
PER_GRADE = 12
DELAY = 0.8


def _query(grade: str, limit: int) -> list:
    r = requests.post(SEARCH_API, timeout=30, json={"request": {
        "filters": {"board": ["CBSE"], "medium": ["English"],
                    "gradeLevel": [grade], "subject": ["Mathematics"]},
        "limit": limit, "fields": FIELDS}})
    r.raise_for_status()
    return r.json().get("result", {}).get("content", []) or []


def normalize(item: dict, grade: str) -> dict:
    """One DIKSHA item -> a link-record document, or {} if not CC-licensed."""
    license = (item.get("license") or "").strip()
    if not license.upper().startswith("CC"):
        return {}
    mime = item.get("mimeType", "")
    is_collection = mime.endswith("content-collection")
    url = (PLAY_COLLECTION_URL if is_collection else PLAY_URL).format(
        id=item["identifier"])
    rtype = "video" if "video" in mime else "reference"
    parts = [item.get("name", ""), item.get("description", ""),
             " ".join(item.get("keywords") or []),
             f"CBSE {grade} Mathematics on DIKSHA."]
    text = ". ".join(p.strip() for p in parts if p and p.strip())
    return {"title": f"{item.get('name', 'DIKSHA resource')} (DIKSHA, {grade})",
            "url": url, "text": text, "resource_type": rtype,
            "license": f"{license} — plays on DIKSHA"}


def sync(con, limit: int = 0, log=print) -> int:
    added = 0
    for grade in GRADES:
        time.sleep(DELAY)
        try:
            items = _query(grade, PER_GRADE)
        except Exception as exc:
            log(f"  diksha SKIP {grade}: {exc}")
            continue
        for item in items:
            doc = normalize(item, grade)
            if not doc or store.doc_id_by_url(con, doc["url"]):
                continue
            if limit and added >= limit:
                return added
            pipeline.ingest(
                con, title=doc["title"], text=doc["text"], source="diksha",
                url=doc["url"], resource_type=doc["resource_type"],
                license=doc["license"], redistribute_allowed=False,
                attribution="DIKSHA (Ministry of Education, Govt. of India)")
            added += 1
            log(f"  diksha: {doc['title']}")
    return added
