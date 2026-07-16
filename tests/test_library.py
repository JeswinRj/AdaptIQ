import pytest

from src.library import composer, pipeline, search, store


@pytest.fixture
def con(tmp_path):
    c = store.connect(tmp_path / "test_library.db")
    yield c
    c.close()


def _ingest(con, title, text, **kw):
    args = dict(source="platform", license="platform",
                redistribute_allowed=True, resource_type="notes")
    args.update(kw)
    return pipeline.ingest(con, title=title, text=text, **args)


def test_chunking_respects_structure():
    text = "## Heading one\n" + ("alpha beta gamma. " * 30) + \
           "\n\n## Heading two\n" + ("delta epsilon zeta. " * 30)
    chunks = pipeline.chunk_text(text)
    assert len(chunks) >= 2
    assert all(len(c) <= pipeline.CHUNK_MAX for c in chunks)


def test_ingest_and_hybrid_search_roundtrip(con):
    _ingest(con, "Integration by parts guide",
            "Integration by parts: the integral of u dv equals uv minus the "
            "integral of v du. Choose u using the ILATE rule for products "
            "of functions.", resource_type="formula")
    _ingest(con, "Probability basics",
            "The probability of an event is favourable outcomes divided by "
            "total outcomes. For a union, add the probabilities and subtract "
            "the intersection.")
    hits = search.hybrid_search(con, "how to integrate a product of two functions")
    assert hits and hits[0]["title"] == "Integration by parts guide"
    assert store.stats(con)["documents"] == 2


def test_license_gating_link_only(con):
    _ingest(con, "Official textbook portal",
            "Official mathematics textbooks for class 11 and 12: calculus, "
            "algebra, probability.", redistribute_allowed=False,
            url="https://example.org/books", source="ncert")
    hits = search.hybrid_search(con, "class 12 mathematics textbook")
    assert hits
    assert hits[0]["link_only"] is True
    assert hits[0]["text"] == ""          # body never rendered
    assert hits[0]["url"]                  # but the link is


def test_profile_boost_prefers_matching_resource_type(con):
    body = ("The quadratic formula gives roots of a x squared plus b x "
            "plus c equals zero as minus b plus or minus root of the "
            "discriminant over two a.")
    _ingest(con, "Quadratic notes", body, resource_type="notes")
    _ingest(con, "Quadratic formula sheet", body, resource_type="formula")
    hits = search.hybrid_search(con, "quadratic formula",
                                profile={"learning_method": "memorizer"})
    assert hits[0]["resource_type"] == "formula"


def test_private_uploads_visibility(con):
    _ingest(con, "Aarav's secret notes",
            "Personal shortcuts for trigonometry identities and revision.",
            uploader="user-a", visibility="private", source="student")
    mine = search.hybrid_search(con, "trigonometry shortcuts",
                                visibility_for="user-a")
    others = search.hybrid_search(con, "trigonometry shortcuts",
                                  visibility_for="user-b")
    assert any(h["title"] == "Aarav's secret notes" for h in mine)
    assert not any(h["title"] == "Aarav's secret notes" for h in others)


def test_pdf_ingest_roundtrip(con):
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Binomial Theorem Summary", fontsize=20)
    page.insert_text((72, 120),
                     "The binomial theorem expands (a plus b) to the power n "
                     "using combinations nCr as coefficients of each term.",
                     fontsize=11)
    data = doc.tobytes()
    doc.close()
    r = pipeline.ingest_pdf(con, data, fallback_title="Binomial PDF",
                            title="Binomial PDF", source="teacher",
                            license="uploader", redistribute_allowed=True,
                            teacher_endorsed=True)
    assert r["chunks"] >= 1
    hits = search.hybrid_search(con, "binomial expansion coefficients")
    assert hits and hits[0]["title"] == "Binomial PDF"
    assert hits[0]["teacher_endorsed"]


def test_composer_offline_assembles_sections(con):
    _ingest(con, "Limits formulas", "Standard limits: sin x over x tends to "
            "one as x tends to zero. The limit of e to the x minus one over "
            "x is also one.", resource_type="formula")
    _ingest(con, "Limits worked example", "Example: evaluate the limit of "
            "sin three x over x as x tends to zero. Multiply and divide by "
            "three to get three.", resource_type="example")
    lesson = composer.build_lesson(con, "limits of trigonometric functions")
    assert lesson["mode"] == "assembled"     # AI hermetically off in tests
    labels = [s["label"] for s in lesson["sections"]]
    assert "Formulas" in labels and "Worked examples" in labels
    assert lesson["sources"]


def test_store_document_helpers(con):
    r = _ingest(con, "Vectors summary",
                "A vector has magnitude and direction. The dot product of "
                "perpendicular vectors is zero.", uploader="user-a",
                visibility="private", source="student", url="local://v1")
    doc = store.get_document(con, r["doc_id"])
    assert doc["title"] == "Vectors summary"
    assert store.doc_id_by_url(con, "local://v1") == r["doc_id"]
    docs = store.list_documents(con, visibility_for="user-a")
    assert docs and docs[0]["chunk_count"] >= 1
    assert store.list_documents(con, visibility_for="user-b") == []


def test_doc_scoped_search_stays_in_one_doc(con):
    a = _ingest(con, "Doc A about limits",
                "The limit of sin x over x as x tends to zero equals one. "
                "This is a standard trigonometric limit result.")
    _ingest(con, "Doc B about limits",
            "Limits describe the value a function approaches. The limit of "
            "sin x over x is a famous example covered elsewhere.")
    hits = search.doc_search(con, a["doc_id"], "standard limit of sin x over x")
    assert hits
    assert all(h["doc_id"] == a["doc_id"] for h in hits)


def test_answer_from_doc_offline_returns_excerpts(con):
    r = _ingest(con, "Probability chapter",
                "Bayes theorem reverses conditional probabilities. It uses "
                "prior probabilities and likelihoods to compute posteriors.")
    doc = store.get_document(con, r["doc_id"])
    ans = composer.answer_from_doc(con, doc, "what does Bayes theorem do")
    assert ans["mode"] == "excerpts"          # AI hermetically off in tests
    assert ans["excerpts"]
    off_topic = composer.answer_from_doc(con, doc, "irrelevant zebra query")
    assert off_topic["mode"] in ("excerpts", "empty")


def test_adapter_normalization_offline():
    from src.library.adapters import diksha, ncert, wikipedia
    # NCERT chapter-code maps must stay aligned with the curriculum
    from src.curriculum import cbse_math
    for cid, codes in ncert.BOOK_CODES.items():
        assert len(codes) == len(cbse_math.COURSES[cid]["chapters"])
    # Wikipedia extract cleaning: wiki headings -> '## ', junk sections gone
    cleaned = wikipedia.clean_extract(
        "Lead paragraph.\n== Properties ==\nBody.\n== See also ==\nJunk.\n"
        "== References ==\nMore junk.")
    assert "## Properties" in cleaned
    assert "Junk" not in cleaned and "References" not in cleaned
    # DIKSHA: CC items become link records; non-CC items are dropped
    item = {"identifier": "do_1", "name": "Integrals video",
            "description": "Class 12 integrals", "license": "CC BY 4.0",
            "mimeType": "video/mp4", "keywords": ["integrals"]}
    doc = diksha.normalize(item, "Class 12")
    assert doc["url"].endswith("/play/content/do_1")
    assert doc["resource_type"] == "video"
    assert doc["license"].startswith("CC BY 4.0")
    item["license"] = "All Rights Reserved"
    assert diksha.normalize(item, "Class 12") == {}


def _isolated_real_db(tmp_path, monkeypatch):
    """Route tests read the seeded library but must never write to it —
    run them against a throwaway copy."""
    import shutil
    from src.library import store as lib_store
    db_copy = tmp_path / "library_copy.db"
    if lib_store.DB_PATH.exists():
        shutil.copy(lib_store.DB_PATH, db_copy)
    monkeypatch.setattr(lib_store, "DB_PATH", db_copy)


def test_doc_qa_route(tmp_path, monkeypatch):
    import config
    from src.dashboard.app import create_app
    from src.library import store as lib_store
    from tests.test_app import _onboard
    config.LIVE_RESOURCES = False
    _isolated_real_db(tmp_path, monkeypatch)
    app = create_app()
    app.testing = True
    client = app.test_client()
    uid = _onboard(client, name="Doc QA Tester")

    client.post(f"/library/{uid}/upload", data={
        "title": "My vectors sheet",
        "text": "The cross product of two vectors is perpendicular to both. "
                "Its magnitude equals the area of the parallelogram."})
    con = lib_store.connect()
    doc_id = [d["id"] for d in lib_store.list_documents(
        con, visibility_for=uid) if d["title"] == "My vectors sheet"][0]
    con.close()

    resp = client.get(f"/library/{uid}/doc/{doc_id}")
    assert resp.status_code == 200 and b"Ask this document" in resp.data
    resp = client.post(f"/library/{uid}/doc/{doc_id}",
                       data={"question": "what is the cross product"})
    assert resp.status_code == 200 and b"cross product" in resp.data
    # private doc is invisible to another user
    uid2 = _onboard(client, name="Someone Else")
    assert client.get(f"/library/{uid2}/doc/{doc_id}").status_code == 404


def test_library_routes(tmp_path, monkeypatch):
    # reads the seeded corpus via an isolated copy; uploads stay in tmp
    import config
    from src.dashboard.app import create_app
    from tests.test_app import _onboard
    config.LIVE_RESOURCES = False
    _isolated_real_db(tmp_path, monkeypatch)
    app = create_app()
    app.testing = True
    client = app.test_client()
    uid = _onboard(client, name="Lib Tester")

    resp = client.get(f"/library/{uid}?q=integration by parts")
    assert resp.status_code == 200
    assert b"Integrals" in resp.data or b"Integration" in resp.data
    # chapter routing: a topical query must not surface other chapters
    assert b"Vector Algebra" not in resp.data

    resp = client.post(f"/library/{uid}/upload", data={
        "title": "My revision sheet",
        "text": "Inverse trigonometric functions have principal value "
                "branches. arcsin has range minus pi by two to pi by two."})
    assert b"searchable sections" in resp.data

    resp = client.get(f"/library/{uid}/lesson?q=integration by parts")
    assert resp.status_code == 200
    assert b"Sources" in resp.data
