"""AI enhancement layer — provider-agnostic, free-tier friendly.

Supported providers (choose with AI_PROVIDER in .env):
  gemini      Google AI Studio free tier (no credit card; rate-limited)
  groq        Groq cloud free tier (fast open models, e.g. Llama)
  openrouter  OpenRouter ":free" models (no card required)
  ollama      100% free forever — runs models locally, no key, no internet
  (unset)     AI disabled -> honest offline fallback, app fully functional

All providers are called with plain HTTP (requests) — no vendor SDKs.
STATUS: implemented and ready; untested against live keys (none provided).
The Ollama path can be tested by anyone locally with `ollama serve`.
"""
import re

import requests

DEFAULT_MODELS = {
    "gemini": "gemini-2.5-flash",
    "groq": "llama-3.3-70b-versatile",
    "openrouter": "deepseek/deepseek-chat-v3-0324:free",
    "mistral": "mistral-small-latest",
    "cerebras": "llama-3.3-70b",
    "deepseek": "deepseek-chat",   # official API — cheap but NOT free
    "ollama": "llama3.2",
}

# OpenAI-compatible chat/completions endpoints.
OPENAI_BASES = {
    "groq": "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "mistral": "https://api.mistral.ai/v1",
    "cerebras": "https://api.cerebras.ai/v1",
    "deepseek": "https://api.deepseek.com/v1",
}

# When the primary gemini model is rate-limited (429) or overloaded (503),
# retry once on flash-lite, which has higher free-tier limits.
GEMINI_RELIEF_MODEL = "gemini-2.5-flash-lite"

OFFLINE_MESSAGE = (
    "AI enhancement is off (no AI provider configured). The plan above is the "
    "rule-based plan and works without AI. To enable AI tips, set AI_PROVIDER "
    "and (except for ollama) AI_API_KEY in your .env — see README 'Free AI setup'.")

TIMEOUT = 90  # gemini-2.5 models "think" before answering; allow for it


def strip_markdown(text: str) -> str:
    """Models return markdown even when asked for plain text; the templates
    render plain text, so strip the common noise (**bold**, ### headings,
    horizontal rules, bullet markers)."""
    text = re.sub(r"^\s*```\w*\s*$", "", text, flags=re.M)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.M)
    text = re.sub(r"^\s*[-*]{3,}\s*$", "", text, flags=re.M)
    text = re.sub(r"^\s*[*•]\s+", "– ", text, flags=re.M)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def build_prompt(features: dict, content_level: str, plan: dict,
                 task: dict = None, audience: str = "standard") -> str:
    task = task or {}
    topic = task.get("topic") or "Newton's Laws"
    subject = task.get("subject") or "Physics"
    prompt = (
        "You are an educational advisor. A student is studying "
        f"'{topic}' ({subject}, {plan['content_level']} difficulty). "
        f"Profile: {content_level} foundational knowledge, "
        f"'{features['learning_pace']}' learning pace, "
        f"'{features['break_frequency']}' break needs, "
        f"{features['engagement_preference'].replace('_', '/')} engagement preference, "
        f"{features['problem_solving_style']} problem-solving style. "
        f"Current rule-based plan: pacing={plan['lesson_pacing']['label']}; "
        f"breaks={plan['break_schedule']['detail']} "
        f"engagement={plan['engagement_strategy']}; "
        f"assessment={plan['assessment_method']}. "
        "Reply with 4-6 numbered tips that ADD to this plan (novel teaching "
        "ideas, motivation, remedial content, multi-modal formats). "
        "Each tip under 30 words. Plain text, no markdown."
    )
    if audience == "simplified":
        prompt += (
            " IMPORTANT: the student needs very simple language (reading age "
            "about 8): short sentences, one idea per sentence, literal words "
            "only, no metaphors, no idioms, no game language. Calm and concrete.")
    return prompt


def _call_gemini(prompt, key, model):
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:generateContent?key={key}")
    r = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]},
                      timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


def _call_openai_style(prompt, key, model, base_url):
    r = requests.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": model, "messages": [{"role": "user", "content": prompt}]},
        timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _call_ollama(prompt, model, host):
    r = requests.post(f"{host}/api/generate",
                      json={"model": model, "prompt": prompt, "stream": False},
                      timeout=120)
    r.raise_for_status()
    return r.json()["response"]


def complete(prompt: str, provider: str, api_key: str = "", model: str = "",
             ollama_host: str = "http://localhost:11434") -> str:
    """One completion against one provider. Raises on any failure.

    Gemini gets an internal relief-valve: on 429/503 it retries once with
    the higher-limit flash-lite model before giving up.
    """
    provider = (provider or "").lower().strip()
    if provider not in DEFAULT_MODELS:
        raise ValueError(f"unknown provider '{provider}'")
    if provider != "ollama" and not api_key:
        raise ValueError(f"provider '{provider}' needs an API key")
    model = model or DEFAULT_MODELS[provider]

    if provider == "gemini":
        try:
            return _call_gemini(prompt, api_key, model)
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else 0
            if status in (429, 503) and model != GEMINI_RELIEF_MODEL:
                return _call_gemini(prompt, api_key, GEMINI_RELIEF_MODEL)
            raise
    if provider == "ollama":
        return _call_ollama(prompt, model, ollama_host)
    return _call_openai_style(prompt, api_key, model, OPENAI_BASES[provider])


def resilient_complete(prompt: str, provider: str, api_key: str = "",
                       model: str = "",
                       fallback_provider: str = "", fallback_key: str = "",
                       ollama_host: str = "http://localhost:11434") -> str:
    """Try the primary provider; on any failure try the fallback provider.
    Raises only if every configured provider fails."""
    try:
        return complete(prompt, provider, api_key, model, ollama_host)
    except Exception:
        if not fallback_provider:
            raise
        return complete(prompt, fallback_provider, fallback_key, "",
                        ollama_host)


def get_ai_tips(features: dict, content_level: str, plan: dict,
                task: dict = None, audience: str = "standard",
                provider: str = "", api_key: str = "", model: str = "",
                fallback_provider: str = "", fallback_key: str = "",
                ollama_host: str = "http://localhost:11434") -> dict:
    """Returns {"available": bool, "tips": [str], "message": str}.

    Never crashes and never fabricates AI output: any failure returns the
    rule-based-only fallback with an honest message.
    """
    provider = (provider or "").lower().strip()
    if provider in ("", "off", "none"):
        return {"available": False, "tips": [], "message": OFFLINE_MESSAGE}
    if provider not in DEFAULT_MODELS:
        return {"available": False, "tips": [],
                "message": f"AI enhancement unavailable (unknown AI_PROVIDER "
                           f"'{provider}'; use one of {sorted(DEFAULT_MODELS)})."}
    if provider != "ollama" and not api_key:
        return {"available": False, "tips": [],
                "message": f"AI enhancement unavailable (AI_PROVIDER={provider} "
                           "is set but AI_API_KEY is empty)."}

    prompt = build_prompt(features, content_level, plan, task, audience)
    try:
        text = strip_markdown(resilient_complete(
            prompt, provider, api_key, model,
            fallback_provider, fallback_key, ollama_host) or "")
        if not text:
            raise ValueError("empty response")
        tips = [ln.strip(" -•*–") for ln in text.splitlines() if ln.strip()]
        return {"available": True, "tips": tips, "message": ""}
    except Exception as exc:
        return {"available": False, "tips": [],
                "message": f"AI enhancement unavailable ({provider} call failed: {exc})."}
