"""Notes summarizer: extractive, fully offline (no AI required).

Scores each sentence by the frequency of its content words across the whole
document (a classic frequency-based extractive method) and returns the top
sentences in original order. When an AI provider is configured, the app can
additionally ask it for an abstractive summary — this module is the
always-available baseline.
"""
import re
from collections import Counter

_SENT_RE = re.compile(r"(?<=[.!?])\s+")
_WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z'-]+")

_STOP = set("""a an the and or but if then else for while of in on at to from
by with about as is are was were be been being have has had do does did this
that these those it its they them their there here he she his her you your i
we our us not no nor so very can could will would shall should may might must
which who whom what when where why how all any both each few more most other
some such only own same than too s t just don now""".split())


def summarize(text: str, max_sentences: int = 5) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    sentences = [s.strip() for s in _SENT_RE.split(text) if s.strip()]
    if len(sentences) <= max_sentences:
        return " ".join(sentences)

    freq = Counter(w.lower() for w in _WORD_RE.findall(text)
                   if w.lower() not in _STOP)
    if not freq:
        return " ".join(sentences[:max_sentences])
    top = freq.most_common(1)[0][1]

    scored = []
    for i, s in enumerate(sentences):
        words = [w.lower() for w in _WORD_RE.findall(s)
                 if w.lower() not in _STOP]
        if not words:
            continue
        score = sum(freq[w] / top for w in words) / len(words)
        scored.append((score, i, s))
    best = sorted(sorted(scored, reverse=True)[:max_sentences], key=lambda t: t[1])
    return " ".join(s for _, _, s in best)
