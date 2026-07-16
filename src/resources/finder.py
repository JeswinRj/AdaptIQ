"""Resource finder: real resources for ANY chosen subject/topic/difficulty.

Two layers:
1. LIVE fetch (free, keyless, no signup — Wikipedia REST API): finds the
   actual article for the topic and returns its title, URL and a short
   summary. Focus-audience requests use Simple English Wikipedia
   (simple.wikipedia.org), which is written in plain language.
2. CONSTRUCTED links: search URLs on curated educational sites (Khan
   Academy, YouTube, BBC Bitesize, PhET, Wikibooks, LibriVox), ordered by
   the student's engagement modality and difficulty. These always work,
   even with no network, so the app never renders an empty resource list.

Results are cached in-process per (topic, audience).
"""
from urllib.parse import quote, quote_plus

import requests

TIMEOUT = 4
_cache = {}


def _wiki_lookup(topic: str, simple: bool):
    """Search Wikipedia for the topic and return (title, url, summary).
    Returns None on any network/API failure — callers must tolerate that."""
    host = "simple.wikipedia.org" if simple else "en.wikipedia.org"
    try:
        search = requests.get(
            f"https://{host}/w/rest.php/v1/search/page",
            params={"q": topic, "limit": 1},
            headers={"User-Agent": "ADAPT-IQ/1.0 (educational demo)"},
            timeout=TIMEOUT).json()
        pages = search.get("pages") or []
        if not pages:
            return None
        title = pages[0]["title"]
        summary = requests.get(
            f"https://{host}/api/rest_v1/page/summary/{quote(title)}",
            headers={"User-Agent": "ADAPT-IQ/1.0 (educational demo)"},
            timeout=TIMEOUT).json()
        extract = (summary.get("extract") or "").strip()
        url = (summary.get("content_urls", {}).get("desktop", {}).get("page")
               or f"https://{host}/wiki/{quote(title)}")
        if len(extract) > 400:
            extract = extract[:400].rsplit(" ", 1)[0] + "…"
        return {"title": title, "url": url, "summary": extract,
                "source": "Simple English Wikipedia" if simple else "Wikipedia"}
    except Exception:
        return None


def _constructed_links(topic, subject, level, modality, simplified):
    q = quote_plus(topic)
    kid = quote_plus(f"{topic} for kids simple explanation")
    science = subject.lower() in ("physics", "science", "chemistry", "biology")

    by_modality = {
        "visual": [
            (f"YouTube: videos about {topic}", f"https://www.youtube.com/results?search_query={q}+explained"),
            (f"Khan Academy: search '{topic}'", f"https://www.khanacademy.org/search?page_search_query={q}"),
        ],
        "auditory": [
            (f"YouTube: '{topic}' explained (listen)", f"https://www.youtube.com/results?search_query={q}+explained"),
            (f"LibriVox free audiobooks: {subject}", f"https://librivox.org/search?q={quote_plus(subject)}&search_form=advanced"),
        ],
        "kinesthetic": [
            (f"PhET interactive simulations: {topic}" if science else f"Hands-on ideas for {topic} (YouTube)",
             f"https://phet.colorado.edu/en/simulations/filter?q={q}" if science
             else f"https://www.youtube.com/results?search_query={q}+hands+on+activity"),
            (f"Science Buddies activities: {topic}" if science else f"Khan Academy practice: {topic}",
             f"https://www.sciencebuddies.org/search?v=&s={q}" if science
             else f"https://www.khanacademy.org/search?page_search_query={q}"),
        ],
        "reading_writing": [
            (f"Khan Academy articles: {topic}", f"https://www.khanacademy.org/search?page_search_query={q}"),
            (f"Wikibooks (free textbooks): {topic}", f"https://en.wikibooks.org/w/index.php?search={q}"),
        ],
    }

    links = list(by_modality[modality])
    if simplified:
        # plain-language, low-stimulation options first
        links = [
            (f"BBC Bitesize (clear, simple lessons): {topic}", f"https://www.bbc.co.uk/search?q={q}&d=bitesize"),
            (f"YouTube: {topic} explained simply", f"https://www.youtube.com/results?search_query={kid}"),
        ] + links[:1]
    else:
        links.append((f"BBC Bitesize: {topic}", f"https://www.bbc.co.uk/search?q={q}&d=bitesize"))
    if level == "advanced" and not simplified:
        links.append((f"MIT OpenCourseWare: {topic}", f"https://ocw.mit.edu/search/?q={q}"))
    return links


def find_resources(topic: str, subject: str, level: str, modality: str,
                   audience: str = "standard", live: bool = True) -> dict:
    """Returns {"article": {...}|None, "links": [(title, url), ...]}."""
    topic = (topic or "Newton's Laws").strip()
    subject = (subject or "Physics").strip()
    simplified = audience == "simplified"
    key = (topic.lower(), subject.lower(), level, modality, simplified)
    if key in _cache:
        return _cache[key]

    article = _wiki_lookup(topic, simple=simplified) if live else None
    if article is None and live and simplified:
        article = _wiki_lookup(topic, simple=False)  # fall back to en.wiki

    result = {
        "article": article,
        "links": _constructed_links(topic, subject, level, modality, simplified),
    }
    _cache[key] = result
    return result
