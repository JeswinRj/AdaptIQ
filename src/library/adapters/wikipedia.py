"""Wikipedia full-article adapter — CC-BY-SA 4.0, Tier 1.

Upgrades the Phase-1 lead-summary records to full article text (plaintext
extracts via the official Action API, sections preserved as '## ' headings,
housekeeping sections dropped). Replaces any existing document for the
same article URL, so re-running upgrades in place.
"""
import re
import time

import requests

from src.curriculum import cbse_math
from src.library import pipeline, store

API = "https://en.wikipedia.org/w/api.php"
HEADERS = {"User-Agent": "AdaptIQ-Library/1.0 (educational; contact via repo)"}
MAX_CHARS = 25000   # cap very long articles; the lead + core sections suffice
DROP_SECTIONS = {"references", "external links", "see also", "further reading",
                 "notes", "bibliography", "sources", "citations", "footnotes"}
DELAY = 0.6


def clean_extract(text: str) -> str:
    """'== Heading ==' -> '## Heading'; drop housekeeping sections."""
    out, skipping = [], False
    for line in (text or "").split("\n"):
        m = re.match(r"^\s*(={2,6})\s*(.+?)\s*={2,6}\s*$", line)
        if m:
            skipping = m.group(2).strip().lower() in DROP_SECTIONS
            if not skipping:
                out.append(f"## {m.group(2).strip()}")
            continue
        if not skipping:
            out.append(line)
    return "\n".join(out).strip()[:MAX_CHARS]


def fetch_article(title: str) -> dict:
    r = requests.get(API, headers=HEADERS, timeout=30, params={
        "action": "query", "prop": "extracts", "explaintext": 1,
        "exsectionformat": "wiki", "redirects": 1, "format": "json",
        "titles": title})
    r.raise_for_status()
    pages = r.json()["query"]["pages"]
    page = next(iter(pages.values()))
    if "extract" not in page or int(next(iter(pages))) < 0:
        return {}
    resolved = page["title"]
    return {"title": resolved, "text": clean_extract(page["extract"]),
            "url": "https://en.wikipedia.org/wiki/"
                   + resolved.replace(" ", "_")}


def sync(con, limit: int = 0, log=print) -> int:
    added, seen = 0, set()
    for course in cbse_math.COURSES.values():
        for ch in course["chapters"]:
            topic = ch["wiki"]
            if topic in seen:
                continue
            seen.add(topic)
            if limit and added >= limit:
                return added
            time.sleep(DELAY)
            try:
                art = fetch_article(topic)
            except Exception as exc:
                log(f"  wikipedia SKIP {topic}: {exc}")
                continue
            if not art or len(art["text"]) < 200:
                continue
            old = store.doc_id_by_url(con, art["url"])
            if old:                      # replace the Phase-1 lead summary
                store.delete_document(con, old)
            r = pipeline.ingest(
                con, title=f"{art['title']} (Wikipedia)", text=art["text"],
                source="wikipedia", url=art["url"], resource_type="reference",
                license="CC-BY-SA-4.0", redistribute_allowed=True,
                attribution=f"From Wikipedia, '{art['title']}', CC BY-SA 4.0")
            added += 1
            log(f"  wikipedia: {art['title']} ({r['chunks']} chunks)")
    return added
