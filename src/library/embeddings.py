"""Embedding provider chain for semantic search.

Priority:
 1. fastembed (ONNX, BAAI/bge-small-en-v1.5, ~34MB, CPU-fast, no torch) —
    real semantic embeddings, downloaded once, then fully offline.
 2. sklearn HashingVectorizer character n-grams — deterministic, dependency-
    free fallback so the library never breaks even without fastembed's model
    (weaker semantics; hybrid keyword search carries more weight then).

The active backend is recorded so tests and the UI can report it honestly.
"""
import numpy as np

_state = {"backend": None, "model": None, "hasher": None}

FASTEMBED_MODEL = "BAAI/bge-small-en-v1.5"
_HASH_DIM = 512


def _try_fastembed():
    try:
        from fastembed import TextEmbedding
        _state["model"] = TextEmbedding(model_name=FASTEMBED_MODEL)
        _state["backend"] = "fastembed"
        return True
    except Exception:
        return False


def _hashing_backend():
    from sklearn.feature_extraction.text import HashingVectorizer
    _state["hasher"] = HashingVectorizer(
        analyzer="char_wb", ngram_range=(3, 5), n_features=_HASH_DIM,
        norm="l2", alternate_sign=False)
    _state["backend"] = "hashing"


def backend() -> str:
    if _state["backend"] is None:
        embed_texts(["warmup"])
    return _state["backend"]


def embed_texts(texts: list) -> np.ndarray:
    """L2-normalised float32 matrix, one row per text."""
    texts = [(t or " ")[:4000] for t in texts]
    if _state["backend"] is None:
        if not _try_fastembed():
            _hashing_backend()
    if _state["backend"] == "fastembed":
        try:
            vecs = np.array(list(_state["model"].embed(texts)),
                            dtype=np.float32)
            vecs = np.nan_to_num(vecs)   # glyph-heavy PDF text can yield NaN
            norms = np.linalg.norm(vecs, axis=1, keepdims=True)
            return vecs / np.clip(norms, 1e-9, None)
        except Exception:
            _hashing_backend()   # runtime failure -> degrade gracefully
    return np.asarray(_state["hasher"].transform(texts).todense(),
                      dtype=np.float32)


def embed_query(text: str) -> np.ndarray:
    return embed_texts([text])[0]
