"""Ingestion pipeline: text/PDF -> structured chunks -> tagged -> embedded.

extract -> structure-aware chunking -> curriculum auto-tag -> embed -> store
(docs/content_architecture.md §2.3-2.4).
"""
import re

import numpy as np

from src.curriculum import cbse_math
from src.library import embeddings, store

CHUNK_TARGET = 1100   # characters (~250 tokens)
CHUNK_MAX = 1600
NODE_TAG_THRESHOLD = 0.45

_node_cache = {"names": None, "vecs": None}


def chunk_text(text: str) -> list:
    """Heading/paragraph-aware chunking; never splits mid-paragraph."""
    text = re.sub(r"\r\n?", "\n", text or "").strip()
    if not text:
        return []
    # split into blocks on headings or blank lines
    blocks, current = [], []
    for line in text.split("\n"):
        is_heading = bool(re.match(r"^\s*(#{1,6}\s|\d+[.)]\s+[A-Z]|[A-Z][A-Z .]{6,}$)",
                                   line)) and len(line) < 90
        if is_heading and current:
            blocks.append("\n".join(current).strip())
            current = [line]
        elif not line.strip() and current and len("\n".join(current)) > CHUNK_TARGET:
            blocks.append("\n".join(current).strip())
            current = []
        else:
            current.append(line)
    if current:
        blocks.append("\n".join(current).strip())

    # merge small blocks / split oversized ones
    chunks, buf = [], ""
    for b in blocks:
        if not b:
            continue
        if len(buf) + len(b) <= CHUNK_TARGET:
            buf = f"{buf}\n\n{b}".strip()
            continue
        if buf:
            chunks.append(buf)
        while len(b) > CHUNK_MAX:              # hard split giant blocks
            cut = b.rfind(". ", 0, CHUNK_MAX)
            cut = cut + 1 if cut > CHUNK_TARGET // 2 else CHUNK_MAX
            chunks.append(b[:cut].strip())
            b = b[cut:].strip()
        buf = b
    if buf:
        chunks.append(buf)
    return [c for c in chunks if len(c) > 40]


def _curriculum_nodes():
    """Embed every curriculum topic once: 'Chapter — topic1, topic2 (domain)'."""
    if _node_cache["names"] is None:
        names, texts = [], []
        for cid, course in cbse_math.COURSES.items():
            for ch in course["chapters"]:
                names.append(ch["name"])
                texts.append(f"{ch['name']} — {', '.join(ch['topics'])} "
                             f"({ch['domain']}, {course['short']})")
        _node_cache["names"] = names
        _node_cache["vecs"] = embeddings.embed_texts(texts)
    return _node_cache["names"], _node_cache["vecs"]


def tag_chunks(chunk_vecs: np.ndarray) -> list:
    """Curriculum node names per chunk via embedding similarity."""
    names, node_vecs = _curriculum_nodes()
    sims = chunk_vecs @ node_vecs.T
    tags = []
    for row in sims:
        order = np.argsort(row)[::-1][:2]
        tags.append([names[i] for i in order if row[i] >= NODE_TAG_THRESHOLD])
    return tags


def _is_wordy(text: str) -> bool:
    """Real words, not maths glyphs — required before a line can be a
    heading (a display-size '∫' must not become '## ∫')."""
    letters = sum(ch.isalpha() for ch in text)
    return letters >= 4 and letters >= len(text.replace(" ", "")) * 0.5


def _readable(text: str) -> bool:
    """Keep prose; drop typeset-equation debris ('= 2 2 0 4 a a x dx −'),
    stray page numbers and reprint watermarks. Long lines must be mostly
    words — glyph soup with a stray 'log' or 'tan' still gets dropped."""
    if re.fullmatch(r"(Reprint\s+\d{4}-?\d{0,4}|\d+|[ivxlc]+)\.?", text,
                    re.I):
        return False
    tokens = text.split()
    words = [t for t in tokens if re.search(r"[A-Za-z]{3}", t)]
    if not words:
        return False
    if len(tokens) >= 6 and len(words) < len(tokens) * 0.2:
        return False
    return True


def _clean_page_lines(raw: list, body_size: float) -> list:
    """raw [(text, max_font_size)] -> readable lines. Maths PDFs explode
    equations into one-glyph lines; merge those runs and keep them only if
    the result reads as text."""
    out, frag = [], []

    def flush():
        if frag:
            joined = " ".join(frag)
            if _readable(joined):
                out.append(joined)
            frag.clear()

    for text, size in raw:
        if len(text) <= 4:                 # exploded equation glyph
            frag.append(text)
            continue
        flush()
        if size > body_size * 1.25 and len(text) < 90 and _is_wordy(text):
            out.append(f"## {text}")
        elif _readable(text):
            out.append(text)
    flush()
    return out


def extract_pdf(data: bytes) -> tuple:
    """(title, text) from PDF bytes via PyMuPDF, headings marked with '## '."""
    import fitz
    doc = fitz.open(stream=data, filetype="pdf")
    title = (doc.metadata or {}).get("title") or ""
    sizes, pages = [], []
    for page in doc:
        d = page.get_text("dict")
        for block in d.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if span["text"].strip():
                        sizes.append(span["size"])
    body_size = float(np.median(sizes)) if sizes else 11.0
    for page in doc:
        raw = []
        for block in page.get_text("dict").get("blocks", []):
            for line in block.get("lines", []):
                text = "".join(s["text"] for s in line.get("spans", [])).strip()
                if text:
                    raw.append((text, max(s["size"] for s in line["spans"])))
        pages.append("\n".join(_clean_page_lines(raw, body_size)))
    doc.close()
    return title, "\n\n".join(pages)


def ingest(con, *, title, text, source, license, redistribute_allowed,
           url="", resource_type="notes", attribution="", uploader="",
           visibility="public", teacher_endorsed=False) -> dict:
    """Full pipeline for one document. Returns {'doc_id', 'chunks'}."""
    chunks = chunk_text(text)
    if not chunks:
        return {"doc_id": None, "chunks": 0}
    doc_id = store.add_document(
        con, title=title, source=source, url=url,
        resource_type=resource_type, license=license,
        attribution=attribution, redistribute_allowed=redistribute_allowed,
        uploader=uploader, visibility=visibility,
        teacher_endorsed=teacher_endorsed)
    vecs = embeddings.embed_texts(chunks)
    store.add_chunks(con, doc_id, chunks, vecs, tag_chunks(vecs))
    return {"doc_id": doc_id, "chunks": len(chunks)}


def ingest_pdf(con, data: bytes, *, fallback_title, **kwargs) -> dict:
    """Caller-provided title wins; else PDF metadata; else fallback_title."""
    pdf_title, text = extract_pdf(data)
    title = kwargs.pop("title", "") or pdf_title or fallback_title
    return ingest(con, title=title, text=text, **kwargs)
