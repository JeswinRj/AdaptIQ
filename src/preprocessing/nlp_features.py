"""NLP feature extraction for open-ended answers (report §6.2).

Implements the four techniques named in the report:
  - keyword frequency analysis        (keyword_coverage)
  - TF-IDF vectorization              (tfidf_matrix, used for cognitive_complexity)
  - sentence complexity               (sentence_complexity)
  - sentiment analysis                (sentiment, via TextBlob PatternAnalyzer)
"""
import re

from sklearn.feature_extraction.text import TfidfVectorizer
from textblob import TextBlob

_WORD_RE = re.compile(r"[a-zA-Z']+")
_SENT_RE = re.compile(r"[.!?]+")

# Connectives signal structured reasoning in an answer.
_CONNECTIVES = {
    "because", "therefore", "however", "so", "unless", "although",
    "since", "which", "while", "whereas", "if", "then", "for example",
}


def tokenize(text: str):
    return [w.lower() for w in _WORD_RE.findall(text or "")]


def keyword_coverage(text: str, keyword_groups, points_per_group: int = 2) -> int:
    """Keyword frequency analysis: points for each concept group matched.

    A group counts once no matter how many of its synonyms appear.
    """
    low = (text or "").lower()
    score = 0
    for group in keyword_groups:
        if any(kw in low for kw in group):
            score += points_per_group
    return score


def sentence_complexity(text: str) -> float:
    """0-1 score from average sentence length, vocabulary richness and
    connective usage."""
    words = tokenize(text)
    if not words:
        return 0.0
    sentences = [s for s in _SENT_RE.split(text) if s.strip()] or [text]
    avg_len = len(words) / len(sentences)          # words per sentence
    richness = len(set(words)) / len(words)        # type/token ratio
    low = text.lower()
    connectives = sum(1 for c in _CONNECTIVES if c in low)
    # normalise: 20+ words/sentence -> 1.0; 3+ connectives -> 1.0
    len_score = min(avg_len / 20.0, 1.0)
    conn_score = min(connectives / 3.0, 1.0)
    return round(0.4 * len_score + 0.3 * richness + 0.3 * conn_score, 3)


def complexity_bonus(text: str, max_bonus: int = 2) -> int:
    """Bonus points (0-max_bonus) added to knowledge answers for structure."""
    return round(sentence_complexity(text) * max_bonus)


def sentiment(text: str) -> float:
    """Polarity in [-1, 1] via TextBlob's bundled PatternAnalyzer
    (no corpus download required)."""
    if not (text or "").strip():
        return 0.0
    return round(TextBlob(text).sentiment.polarity, 3)


def tfidf_density(texts):
    """TF-IDF vectorization over a corpus of answers; returns each document's
    mean non-zero TF-IDF weight (a proxy for informative vocabulary use).

    Returns a list of floats aligned with `texts`.
    """
    cleaned = [(t or "").strip() or "empty" for t in texts]
    try:
        vec = TfidfVectorizer(stop_words="english", min_df=1)
        matrix = vec.fit_transform(cleaned)
    except ValueError:  # corpus of only stop words / empties
        return [0.0] * len(cleaned)
    densities = []
    for i in range(matrix.shape[0]):
        row = matrix.getrow(i)
        densities.append(round(float(row.sum() / row.nnz), 3) if row.nnz else 0.0)
    return densities
