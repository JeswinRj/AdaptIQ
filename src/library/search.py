"""Hybrid retrieval + personalized ranking + license-gated result shaping.

score = RRF(keyword, vector) × source_weight × profile_match × endorsement
(docs/content_architecture.md §2.2, §3).

License enforcement happens HERE: results from documents without
redistribution rights carry no body text — title/attribution/link only.
"""
import json

import numpy as np

from src.library import embeddings, store

RRF_K = 60

# Chapter routing: when the query clearly points at specific chapters,
# chunks tagged to OTHER chapters are demoted (an "integration by parts"
# search must not surface Vector Algebra). Generic queries pass untouched.
NODE_MIN = 0.70     # measured: topical queries >=0.74, generic <=0.70
NODE_BAND = 0.05    # accept every chapter this close to the best match
NODE_BOOST = 1.15
NODE_DEMOTE = 0.5
CUTOFF = 0.35       # drop hits scoring below this fraction of the top hit

SOURCE_WEIGHTS = {"teacher": 1.35, "platform": 1.2, "ncert": 1.3,
                  "wikipedia": 1.05, "diksha": 1.1, "student": 0.9,
                  "ai-generated": 1.0}

# learner method -> resource types that suit it (docs §3)
PROFILE_BOOST = {
    "example_driven": {"example": 1.3, "practice": 1.1},
    "practice_driven": {"practice": 1.3, "example": 1.1},
    "memorizer": {"formula": 1.3, "summary": 1.15},
    "conceptual": {"notes": 1.2, "reference": 1.15, "textbook": 1.15},
    "visual_learner": {"video": 1.3, "notes": 1.05},
}


def doc_search(con, doc_id: int, query: str, k: int = 6) -> list:
    """Vector search restricted to ONE document ('answer from this PDF').
    License gating still applies — a Tier-2 doc yields no body text."""
    ids, mat = store.doc_vectors(con, doc_id)
    if not len(ids):
        return []
    sims = mat @ embeddings.embed_query(query)
    order = np.argsort(sims)[::-1][:k]
    chunks = store.get_chunks(con, [ids[i] for i in order])
    out = []
    for i, c in zip(order, chunks):
        c["score"] = round(float(sims[i]), 5)
        c["node_ids"] = json.loads(c["node_ids"])
        c["link_only"] = not c["redistribute_allowed"]
        if c["link_only"]:
            c["text"] = ""
        out.append(c)
    return out


def _query_nodes(qvec) -> list:
    """Chapters the query is clearly about; [] for generic queries (no
    filtering then). Only trustworthy with real semantic embeddings."""
    if embeddings.backend() != "fastembed":
        return []
    from src.library import pipeline
    names, vecs = pipeline._curriculum_nodes()
    sims = vecs @ qvec
    best = float(sims.max()) if len(sims) else 0.0
    if best < NODE_MIN:
        return []
    return [n for n, s in zip(names, sims) if s >= best - NODE_BAND]


def hybrid_search(con, query: str, k: int = 12, profile: dict = None,
                  visibility_for: str = "") -> list:
    """Top-k chunks with fused, personalized scores. Never returns body text
    for non-redistributable documents."""
    qvec = embeddings.embed_query(query)
    kw_ids = store.keyword_search(con, query, limit=40,
                                  visibility_for=visibility_for)
    ids, mat = store.all_vectors(con, visibility_for=visibility_for)
    vec_ids = []
    if len(ids):
        sims = mat @ qvec
        order = np.argsort(sims)[::-1][:40]
        vec_ids = [ids[i] for i in order if sims[i] > 0.30]

    # reciprocal-rank fusion
    scores = {}
    for rank, cid in enumerate(kw_ids):
        scores[cid] = scores.get(cid, 0) + 1.0 / (RRF_K + rank)
    for rank, cid in enumerate(vec_ids):
        scores[cid] = scores.get(cid, 0) + 1.0 / (RRF_K + rank)
    if not scores:
        return []

    chunks = store.get_chunks(con, list(scores))
    method = (profile or {}).get("learning_method", "")
    boosts = PROFILE_BOOST.get(method, {})
    qnodes = _query_nodes(qvec)
    results = []
    for c in chunks:
        c["node_ids"] = json.loads(c["node_ids"])
        s = scores[c["id"]]
        s *= SOURCE_WEIGHTS.get(c["source"], 1.0)
        s *= boosts.get(c["resource_type"], 1.0)
        if c["teacher_endorsed"]:
            s *= 1.25
        if not c["redistribute_allowed"]:
            s *= 0.85   # links support a lesson; body content should lead
        if qnodes and c["node_ids"]:
            s *= (NODE_BOOST if any(n in qnodes for n in c["node_ids"])
                  else NODE_DEMOTE)
        c["score"] = round(s, 5)
        if not c["redistribute_allowed"]:      # Tier 2: metadata + link only
            c["text"] = ""
            c["link_only"] = True
        else:
            c["link_only"] = False
        results.append(c)
    results.sort(key=lambda c: c["score"], reverse=True)

    # at most 2 chunks per document, for source diversity
    seen, out = {}, []
    for c in results:
        if seen.get(c["doc_id"], 0) >= 2:
            continue
        seen[c["doc_id"]] = seen.get(c["doc_id"], 0) + 1
        out.append(c)
        if len(out) >= k:
            break
    if out:                       # relevance cutoff: no barely-related tail
        top = out[0]["score"]
        out = [c for c in out if c["score"] >= top * CUTOFF]
    return out
