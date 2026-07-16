"""Source adapters: fetch -> normalize -> license record -> ingest.

Plugin registry (docs/content_architecture.md §7): each adapter exposes
sync(con, limit=0, log=print) -> number of documents ingested. Adding a
source never touches the pipeline; every emitted document carries a
mandatory license record, enforced downstream by the search layer.
"""
from src.library.adapters import diksha, ncert, wikipedia

ADAPTERS = {
    "ncert": ncert.sync,
    "wikipedia": wikipedia.sync,
    "diksha": diksha.sync,
}
