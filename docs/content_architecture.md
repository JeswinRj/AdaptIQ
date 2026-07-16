# Content Acquisition & Knowledge Retrieval Architecture

**Status: research + recommended design (not yet implemented).**
Goal: make Adapt IQ / LearningOS the student's primary study environment —
retrieve, index and deliver learning material for any topic — while staying
strictly inside copyright, licensing and terms-of-service boundaries.

---

## 1. The governing principle: license-tiered content

Every piece of content in the system carries a mandatory license record:

```json
{
  "source": "diksha", "license": "CC-BY-4.0", "attribution": "…",
  "cache_allowed": true, "redistribute_allowed": true,
  "commercial_allowed": true, "share_alike": false
}
```

The renderer enforces it: content without `redistribute_allowed` is **never
shown as body text — only as a link + our own metadata**. This single rule
makes the whole system compliant by construction. Three tiers follow:

### Tier 1 — Ingest, cache, index full text (redistribution permitted)
| Source | License | Notes |
|---|---|---|
| **DIKSHA** (diksha.gov.in) | CC-BY / CC-BY-SA / CC-BY-NC 4.0 | Government platform, 200k+ resources, 32 languages; built on the open **Sunbird** stack with public content APIs. The backbone for CBSE. Filter to CC-BY/CC-BY-SA if the product may ever be commercial. |
| **NCERT e-content / ePathshala** | NCERT copyright, but license page **explicitly permits free digital redistribution for non-commercial use** | Textbooks + exemplar. Cache while non-commercial; auto-degrade to Tier 2 (link-only) if a paid tier ever launches. |
| **NROER** (National Repository of OER) | CC (mostly BY-SA) | Government OER repository. |
| **Wikipedia / Wikibooks / Wikiversity** | CC-BY-SA 4.0 | Use the official REST API / dumps (never scrape HTML). Share-alike: derived summaries shown with attribution + same license notice. |
| **OpenStax** (Calculus, Precalculus, Statistics) | CC-BY 4.0 | High-quality textbook chapters; map to CBSE topics, not chapters. |
| **LibreTexts Mathematics** | CC mix (check per page) | Ingest only pages whose license field permits. |
| **PhET simulations** | CC-BY 4.0 | Embeddable interactives. |
| **Project Gutenberg / Internet Archive (public domain)** | Public domain | Classic maths texts. |
| **Teacher & student uploads** | Uploader grants platform license at upload (checkbox + ToS: "I own this or have the right to share it") | Private by default; teacher chooses class-visible. DMCA-style takedown flow. |
| **AI-generated notes/summaries** | Ours | Always available as the fallback tier. |

### Tier 2 — Index metadata only, deep-link out (freely accessible, no redistribution right)
CBSE official syllabus & sample papers (cbseacademic.nic.in), Khan Academy,
GeoGebra materials (CC-BY-**NC**-SA — non-commercial constraint makes
link/embed safer), YouTube (via **YouTube Data API v3** for search/metadata +
the official embedded player — embedding is what the ToS is designed for;
never download videos). We store: title, URL, our own description, topic
tags, and an embedding of *our description* — so Tier-2 items participate in
semantic search without their content ever being copied.

### Tier 3 — Never touch
Commercial ed-tech sites (Byju's, Vedantu, Toppr…), anything behind login or
paywall, anything whose robots.txt or ToS forbids automated access.
**No indiscriminate scraping, full stop.** Where a Tier-1 source offers an
API or dumps (Wikipedia, DIKSHA/Sunbird), use those instead of scraping;
"scraping" is acceptable only as *polite fetching of explicitly open-licensed
files* (rate-limited, robots.txt-respecting, User-Agent identified, cached
etags), e.g. downloading NCERT PDFs from their official download endpoints.

**India-specific note:** Copyright Act 1957 §52 provides fair-dealing and
in-course-of-instruction exemptions (private study, teacher/pupil use), which
comfortably cover *teacher-uploaded excerpts used within their own class* —
but we do not rely on §52 for platform-wide redistribution; tiers above are
stricter than the law requires, which is the right posture.

---

## 2. System architecture

```
                        ┌─────────────────────────────┐
   Source adapters      │        INGESTION LAYER       │  queue workers (RQ/Celery)
   (one per provider)   │ diksha · ncert · wikipedia · │
   same pattern as      │ openstax · uploads · drive   │
   src/data_ingestion   └──────────────┬──────────────┘
                                       ▼
                        ┌─────────────────────────────┐
                        │      PROCESSING PIPELINE     │
                        │ extract → structure → chunk  │
                        │ → tag → embed → summarize    │
                        │ → derive (flashcards/quiz)   │
                        └──────────────┬──────────────┘
                                       ▼
        ┌─────────────────┬────────────────────┬──────────────────┐
        │  Object store    │  PostgreSQL         │  Vector index    │
        │  (files, S3/disk)│  metadata, license, │  pgvector        │
        │                  │  graph edges, FTS   │  (same Postgres) │
        └─────────────────┴────────────────────┴──────────────────┘
                                       ▼
                        ┌─────────────────────────────┐
                        │   RETRIEVAL & RANKING API    │  hybrid search + learner-profile ranking
                        └──────────────┬──────────────┘
                                       ▼
                 ┌────────────────────────────────────────┐
                 │  RAG LESSON COMPOSER (AI layer we have) │
                 │  + Knowledge Library UI + Teacher repo  │
                 └────────────────────────────────────────┘
```

### 2.1 Storage & search (recommendation: one Postgres, three roles)
- **PostgreSQL + pgvector + built-in full-text search.** One database serves
  metadata, keyword (BM25-style) search and vector search. This is the
  sweet spot for this project's scale (thousands→millions of chunks); no
  extra infrastructure to operate. Dedicated vector DBs (Qdrant/Weaviate)
  only become worth their ops cost past ~10M chunks or heavy filtering loads.
- **MVP path that runs today:** SQLite + FTS5 + FAISS files — the exact same
  interfaces, swappable to Postgres later (mirrors how our CSV→gspread
  ingestion is already designed).

### 2.2 Embeddings (semantic search)
- **Default: local sentence-transformers** (`bge-small-en-v1.5` or
  `all-MiniLM-L6-v2`, ~30–130MB, CPU-fast). Zero cost, offline, no rate
  limits — consistent with our free-for-life philosophy.
- **Upgrade path:** Gemini embedding API (free tier) behind the same
  interface, chosen by env var exactly like `AI_PROVIDER`.
- **Hybrid retrieval, not pure vector:** BM25 + vector with reciprocal-rank
  fusion. Math queries are symbol-heavy ("nPr formula", "∫udv") and pure
  semantic search misses them; hybrid is the accepted fix.

### 2.3 Chunking & metadata
- Heading-aware chunks of ~300–800 tokens with 10–15% overlap; never split
  a worked example across chunks.
- Every chunk: `{doc_id, license…, topic_node_ids[], resource_type
  (notes|example|formula|quiz|pyq|video|sim), difficulty, language,
  source_rank, teacher_endorsed}`.
- **Auto-tagging to the curriculum:** embed each chunk and match against
  embeddings of our knowledge-graph node descriptions (we already have the
  chapter/topic structure in `src/curriculum/`); accept top match above a
  threshold, else queue for teacher confirmation (human-in-the-loop).

### 2.4 PDF / OCR pipeline
1. **PyMuPDF (fitz)** — text + layout + font sizes (headings) + image
   extraction. Handles 90% of digital PDFs.
2. **OCR fallback** for scanned pages: **Tesseract** (free) via ocrmypdf;
   flag low-confidence pages.
3. **Tables:** pdfplumber (rule-based) — good enough for formula sheets and
   mark-scheme tables.
4. **Formulas:** pragmatic MVP = preserve as cropped images inline (lossless
   and always correct); phase 2 = pix2tex/Texify for LaTeX conversion where
   confidence is high. (Full math-OCR like Nougat is GPU-heavy; not MVP.)
5. Output → structure (heading tree) → chunker → the standard pipeline
   (embed, tag, summarize, derive flashcards/quiz/revision sheet via the
   existing AI layer; our offline extractive summarizer remains the no-key
   fallback).
6. **"Answer from this PDF only"** mode: RAG restricted to that document's
   chunks, with the prompt instructed to refuse content not grounded in
   retrieved chunks and to cite page numbers.

### 2.5 Smart Content Retrieval ("Teach me Integration by Parts")
1. Query → hybrid retrieve top-40 chunks across all tiers (filtered to the
   student's course + adjacent graph nodes).
2. **Personalized re-rank** (see §3).
3. **Compose, don't list:** the AI (existing multi-provider layer) receives
   the top chunks with their license/attribution records and builds one
   structured lesson: overview → key idea → worked examples (verbatim from
   Tier-1 sources, attributed) → formula box → practice questions → Tier-2
   links ("Official NCERT section →", YouTube embeds) → quick-revision
   summary. Every block cites its source; Tier-2 material appears only as
   link cards. If retrieval is empty → **Automatic Note Generation** (§4).

### 2.6 Knowledge Graph
Extend `src/curriculum/cbse_math.py` from a chapter list into a node graph:
`node = {id, name, parent, prerequisites[], description}` (Functions →
Domain & Range → Graphs → Transformations → Inverse → Applications).
Resources attach to nodes via the auto-tagger; the existing constellation
skill-map UI already renders node mastery — the graph gives it depth
(unlock logic = prerequisites mastered). Stored as plain tables/JSON — a
graph database (Neo4j) is unnecessary at this scale and adds ops burden.

---

## 3. Personalized ranking

`score = relevance × source_weight × profile_match × difficulty_match × freshness`

- **relevance** — hybrid-search score.
- **source_weight** — teacher-endorsed 1.5 · official (NCERT/CBSE) 1.3 ·
  OER 1.1 · peer notes 0.9.
- **profile_match** — resource type ↔ learner method (worked examples boosted
  for example-driven "Detectives", derivations for "Analysts", interactive
  sims for practice-driven "Builders", diagram-led for "Explorers",
  formula-sheets for "Strategists"); long videos down-weighted for
  low-attention-endurance profiles; simple-language variants boosted in
  Special Learning Support mode.
- **difficulty_match** — distance from student's current level ± mastery of
  the node's prerequisites.
- **behavioural feedback loop (phase 2):** clicks, completion, quiz-after
  performance per resource feed a simple learning-to-rank adjustment — this
  is also what makes the learner profile continuously self-updating.

Different students therefore genuinely receive different resources for the
same query — from the same index.

## 4. Automatic note generation
When retrieval is thin, the AI generates CBSE-syllabus-aligned structured
notes (overview · key concepts · definitions · formula box · worked examples
· common mistakes · practice questions · quick revision), styled by learner
profile, then **stores them into the library as a Tier-1 resource** tagged
`ai-generated` — so the library densifies itself over time and the next
student gets an instant answer.

## 5. Offline Learning Library
- Saved items, bookmarks, highlights and annotations stored per user
  (annotations as text-anchor JSON, robust to re-rendering).
- Export bundles (single-file HTML or PDF) for Tier-1 + own content only —
  the license record gates what can be exported.
- Phase 2: PWA + service worker for true in-browser offline caching.

## 6. Teacher Content Repository
Upload (PDF/PPT/DOCX/images) → same pipeline → auto: topic tags, summary,
generated quiz, and a **suggested curriculum placement** the teacher
confirms in one click. Teacher-endorsed resources get the ranking boost and
surface in their students' lessons first. Cloud-drive import (Google Drive /
OneDrive / Dropbox) via each provider's official OAuth picker API — the user
authorizes access to their own files; nothing is scraped.

## 7. Scalability & expansion
- **Source adapters** are plugins (fetch → normalize → license-record →
  emit documents) — adding a source never touches the pipeline.
- **Curriculum-as-data:** a new board/subject = a new curriculum JSON +
  source-adapter config (which DIKSHA filters, which NCERT books). Nothing
  in retrieval, ranking or UI changes.
- Ingestion on queue workers; index rebuilds are incremental; Postgres
  scales vertically far beyond this product's medium-term needs.
- Language expansion: DIKSHA's 32-language corpus + multilingual embedding
  model (`bge-m3`) when needed.

## 8. Phased roadmap (maps onto the existing codebase)
1. **Phase 1 — SHIPPED:** SQLite+FTS5 + brute-force cosine (`src/library/`)
   · fastembed bge-small (hashing fallback) · PyMuPDF pipeline for
   user/teacher uploads · curriculum auto-tagging · library search UI ·
   RAG lesson composer with citations through the existing AI layer ·
   personalized ranking · teacher repository upload.
2. **Phase 2 — SHIPPED:** source adapters (`src/library/adapters/`:
   `ncert.py` full chapter PDFs under the ePathshala license, `wikipedia.py`
   full articles CC-BY-SA, `diksha.py` CC-licensed link records) driven by
   `scripts/sync_sources.py` · "answer from this PDF only" doc-scoped Q&A
   (`composer.answer_from_doc`, `/library/<uid>/doc/<id>`) · KaTeX math
   rendering with LaTeX-notation content and prompts.
3. **Phase 3:** Postgres/pgvector migration · behavioural re-ranking ·
   offline PWA · cloud-drive importers · more boards/subjects.

## 9. Key licensing references
- NCERT/ePathshala license (non-commercial digital redistribution permitted):
  https://epathshala.nic.in/pages.php?id=license&ln=en
- DIKSHA terms (CC-BY/BY-SA/BY-NC contributor framework):
  https://diksha-ncte.freshdesk.com/support/solutions/articles/35000139640-terms-and-conditions-on-diksha
- NCERT OER & licensing overview (CIET): https://ciet.ncert.gov.in/activity/oere
- NCERT copyright-infringement notice (what NOT to do — commercial reprints):
  https://www.ncert.nic.in/pdf/announcement/notices/Press_Release_Copyright_Infringement-NCERT.pdf
- Creative Commons on NCERT textbooks:
  https://wiki.creativecommons.org/wiki/National_Council_of_Educational_Research_and_Training_(NCERT)_-_NCERT_Textbooks
