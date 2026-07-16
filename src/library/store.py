"""Knowledge-library store: SQLite + FTS5 keyword index + vector blobs.

Design (docs/content_architecture.md §1-2):
- EVERY document carries a mandatory license record; the search layer
  suppresses body text for documents where redistribution is not allowed
  (Tier 2: metadata + link only). Compliance is enforced by construction.
- Chunks carry curriculum node tags and a resource_type so the ranking and
  the lesson composer can assemble structured lessons.
- Vectors are stored as float32 blobs and searched by brute-force cosine —
  simple and exact, comfortably fast below ~100k chunks. The interface is
  the swap-point for pgvector/FAISS later.
"""
import json
import sqlite3
from pathlib import Path

import numpy as np

import config

DB_PATH = Path(getattr(config, "LIBRARY_DB", config.DATA_DIR / "library.db"))

RESOURCE_TYPES = ["notes", "formula", "example", "practice", "summary",
                  "reference", "textbook", "video", "syllabus"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    source TEXT NOT NULL,            -- platform|teacher|student|wikipedia|...
    url TEXT DEFAULT '',
    resource_type TEXT DEFAULT 'notes',
    license TEXT NOT NULL,           -- e.g. CC-BY-SA-4.0, platform, uploader
    attribution TEXT DEFAULT '',
    redistribute_allowed INTEGER NOT NULL,
    uploader TEXT DEFAULT '',        -- user id for uploads
    visibility TEXT DEFAULT 'public',-- public|private
    teacher_endorsed INTEGER DEFAULT 0,
    created TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY,
    doc_id INTEGER NOT NULL REFERENCES documents(id),
    position INTEGER NOT NULL,
    text TEXT NOT NULL,
    node_ids TEXT DEFAULT '[]',      -- JSON list of curriculum node names
    embedding BLOB
);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text, content='chunks', content_rowid='id'
);
CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
  INSERT INTO chunks_fts(rowid, text) VALUES (new.id, new.text);
END;
CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
  INSERT INTO chunks_fts(chunks_fts, rowid, text)
  VALUES ('delete', old.id, old.text);
END;
"""


def connect(db_path=None) -> sqlite3.Connection:
    path = Path(db_path or DB_PATH)
    path.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(_SCHEMA)
    return con


def add_document(con, *, title, source, license, redistribute_allowed,
                 url="", resource_type="notes", attribution="",
                 uploader="", visibility="public", teacher_endorsed=False) -> int:
    cur = con.execute(
        "INSERT INTO documents (title, source, url, resource_type, license,"
        " attribution, redistribute_allowed, uploader, visibility,"
        " teacher_endorsed) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (title, source, url, resource_type, license, attribution,
         int(redistribute_allowed), uploader, visibility,
         int(teacher_endorsed)))
    con.commit()
    return cur.lastrowid


def add_chunks(con, doc_id: int, chunks: list, embeddings: np.ndarray,
               node_ids_per_chunk: list):
    rows = [(doc_id, i, text,
             json.dumps(node_ids_per_chunk[i]),
             np.asarray(embeddings[i], dtype=np.float32).tobytes())
            for i, text in enumerate(chunks)]
    con.executemany(
        "INSERT INTO chunks (doc_id, position, text, node_ids, embedding)"
        " VALUES (?,?,?,?,?)", rows)
    con.commit()


def get_document(con, doc_id: int):
    row = con.execute("SELECT * FROM documents WHERE id=?",
                      (doc_id,)).fetchone()
    return dict(row) if row else None


def list_documents(con, visibility_for: str = "", source: str = "") -> list:
    """Documents visible to a user (public + their own), newest first,
    with chunk counts. Optionally filtered by source."""
    q = ("SELECT d.*, COUNT(c.id) AS chunk_count FROM documents d"
         " LEFT JOIN chunks c ON c.doc_id = d.id"
         " WHERE (d.visibility='public' OR d.uploader=?)")
    args = [visibility_for]
    if source:
        q += " AND d.source=?"
        args.append(source)
    q += " GROUP BY d.id ORDER BY d.id DESC"
    return [dict(r) for r in con.execute(q, args).fetchall()]


def doc_id_by_url(con, url: str):
    """Existing document id for a source URL (adapter idempotency)."""
    if not url:
        return None
    row = con.execute("SELECT id FROM documents WHERE url=?",
                      (url,)).fetchone()
    return row["id"] if row else None


def doc_vectors(con, doc_id: int):
    """(chunk_ids, matrix) for one document — doc-scoped Q&A."""
    rows = con.execute(
        "SELECT id, embedding FROM chunks WHERE doc_id=? ORDER BY position",
        (doc_id,)).fetchall()
    if not rows:
        return [], np.zeros((0, 1), dtype=np.float32)
    ids = [r["id"] for r in rows]
    mat = np.vstack([np.frombuffer(r["embedding"], dtype=np.float32)
                     for r in rows])
    return ids, mat


def delete_document(con, doc_id: int):
    con.execute("DELETE FROM chunks WHERE doc_id=?", (doc_id,))
    con.execute("DELETE FROM documents WHERE id=?", (doc_id,))
    con.commit()


def all_vectors(con, visibility_for: str = ""):
    """(chunk_ids, matrix) for cosine search. visibility_for: a user id whose
    private docs are included alongside public ones."""
    rows = con.execute(
        "SELECT c.id, c.embedding FROM chunks c JOIN documents d"
        " ON d.id = c.doc_id WHERE d.visibility='public' OR d.uploader=?",
        (visibility_for,)).fetchall()
    if not rows:
        return [], np.zeros((0, 1), dtype=np.float32)
    ids = [r["id"] for r in rows]
    mat = np.vstack([np.frombuffer(r["embedding"], dtype=np.float32)
                     for r in rows])
    return ids, mat


def get_chunks(con, chunk_ids: list) -> list:
    """Chunk rows joined with their document (license enforced downstream)."""
    if not chunk_ids:
        return []
    marks = ",".join("?" * len(chunk_ids))
    rows = con.execute(
        f"SELECT c.id, c.doc_id, c.text, c.node_ids, c.position,"
        f" d.title, d.source, d.url, d.resource_type, d.license,"
        f" d.attribution, d.redistribute_allowed, d.uploader,"
        f" d.teacher_endorsed"
        f" FROM chunks c JOIN documents d ON d.id = c.doc_id"
        f" WHERE c.id IN ({marks})", chunk_ids).fetchall()
    by_id = {r["id"]: dict(r) for r in rows}
    return [by_id[i] for i in chunk_ids if i in by_id]


def keyword_search(con, query: str, limit: int = 30,
                   visibility_for: str = "") -> list:
    """FTS5 BM25 search -> [(chunk_id, rank_position)]."""
    sanitized = " ".join(t for t in query.replace('"', " ").split()
                         if t.isalnum() or "-" in t)
    if not sanitized:
        return []
    rows = con.execute(
        "SELECT c.id FROM chunks_fts f JOIN chunks c ON c.id = f.rowid"
        " JOIN documents d ON d.id = c.doc_id"
        " WHERE chunks_fts MATCH ? AND"
        " (d.visibility='public' OR d.uploader=?)"
        " ORDER BY bm25(chunks_fts) LIMIT ?",
        (sanitized, visibility_for, limit)).fetchall()
    return [r["id"] for r in rows]


def stats(con) -> dict:
    docs = con.execute("SELECT COUNT(*) n FROM documents").fetchone()["n"]
    chunks = con.execute("SELECT COUNT(*) n FROM chunks").fetchone()["n"]
    return {"documents": docs, "chunks": chunks}
