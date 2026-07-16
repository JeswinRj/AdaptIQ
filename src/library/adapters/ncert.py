"""NCERT textbook adapter — official chapter PDFs, Tier 1.

The ePathshala license permits free NON-COMMERCIAL digital redistribution
of NCERT textbooks (docs/content_architecture.md §9), so full chapter text
is cached and searchable, with the official PDF linked as the original.

Chapter PDF codes follow NCERT's rationalised (2023-24) books and map 1:1,
in order, onto src/curriculum/cbse_math.py:
  Class 11  kemh101..kemh114
  Class 12  lemh101..lemh106 (Part I) + lemh201..lemh207 (Part II)
"""
import time

import requests

from src.curriculum import cbse_math
from src.library import pipeline, store

PDF_URL = "https://ncert.nic.in/textbook/pdf/{code}.pdf"

BOOK_CODES = {
    "cbse-11-math": [f"kemh1{i:02d}" for i in range(1, 15)],
    "cbse-12-math": [f"lemh1{i:02d}" for i in range(1, 7)]
                    + [f"lemh2{i:02d}" for i in range(1, 8)],
}

LICENSE = "NCERT — free non-commercial redistribution (ePathshala license)"
ATTRIBUTION = ("NCERT textbook, © National Council of Educational Research "
               "and Training — redistributed non-commercially under the "
               "ePathshala license")
TIMEOUT = 60
DELAY = 1.0   # polite fetching


def sync(con, limit: int = 0, log=print) -> int:
    """Download + ingest NCERT chapter PDFs not yet in the library."""
    added = 0
    for course_id, codes in BOOK_CODES.items():
        course = cbse_math.get_course(course_id)
        chapters = course["chapters"]
        if len(codes) != len(chapters):
            raise RuntimeError(f"{course_id}: {len(codes)} PDF codes for "
                               f"{len(chapters)} chapters — fix BOOK_CODES")
        for n, (code, ch) in enumerate(zip(codes, chapters), start=1):
            url = PDF_URL.format(code=code)
            if store.doc_id_by_url(con, url):
                continue
            if limit and added >= limit:
                return added
            time.sleep(DELAY)
            try:
                resp = requests.get(url, timeout=TIMEOUT)
                resp.raise_for_status()
                r = pipeline.ingest_pdf(
                    con, resp.content,
                    fallback_title=f"NCERT {course['short']} — Ch {n}",
                    title=f"NCERT {course['short']} — Ch {n}: {ch['name']}",
                    source="ncert", url=url, resource_type="textbook",
                    license=LICENSE, redistribute_allowed=True,
                    attribution=ATTRIBUTION)
            except Exception as exc:
                log(f"  ncert SKIP {code}: {exc}")
                continue
            added += 1
            log(f"  ncert: Ch {n} {ch['name']} ({course['short']}, "
                f"{r['chunks']} chunks)")
    return added
