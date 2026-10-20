"""AI provider integrations for HumanWrite AI v1.

Supported kinds: openai (any OpenAI-compatible endpoint), gemini, ollama.
The 'offline' kind never calls an API — rewriting falls back to the
rule-based engine in rewriter.py.

cfg shape: {"kind", "model", "api_key", "base_url"}

Every failure raises ProviderError carrying the REAL error message — the
caller must surface it, never claim success falsely. No API keys are
hardcoded anywhere; credentials arrive in cfg from the SettingsStore.
"""

from __future__ import annotations

import json
import re

import requests

REQUEST_TIMEOUT = 90  # seconds

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


class ProviderError(Exception):
    """Raised for any provider failure, carrying the real error message."""


def _post_json(url: str, payload: dict, headers: dict | None = None) -> dict:
    try:
        resp = requests.post(url, json=payload, headers=headers or {},
                             timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        raise ProviderError(f"Request failed: {exc}") from exc
    if resp.status_code >= 400:
        body = (resp.text or "").strip()[:500]
        raise ProviderError(f"HTTP {resp.status_code} from provider: {body}")
    try:
        data = resp.json()
    except ValueError as exc:
        raise ProviderError(
            f"Provider returned non-JSON response: {(resp.text or '')[:200]}"
        ) from exc
    if not isinstance(data, dict):
        raise ProviderError("Provider returned an unexpected response shape")
    return data


def _strip_fences(text: str) -> str:
    match = _FENCE_RE.search(text or "")
    return match.group(1) if match else (text or "").strip()


def _call_openai(cfg: dict, messages: list[dict], as_json: bool = True) -> str:
    base_url = (cfg.get("base_url") or "https://api.openai.com/v1").rstrip("/")
    model = cfg.get("model") or "gpt-4o-mini"
    api_key = cfg.get("api_key") or ""
    if not api_key:
        raise ProviderError("OpenAI API key is not configured (see Settings)")
    payload: dict = {"model": model, "messages": messages, "temperature": 0.7}
    if as_json:
        payload["response_format"] = {"type": "json_object"}
    data = _post_json(
        f"{base_url}/chat/completions",
        payload,
        {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    try:
        return data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderError(
            f"Unexpected OpenAI response shape: {json.dumps(data)[:200]}"
        ) from exc


def _call_gemini(cfg: dict, prompt: str) -> str:
    model = cfg.get("model") or "gemini-3.8-flash"
    api_key = cfg.get("api_key") or ""
    if not api_key:
        raise ProviderError("Gemini API key is not configured (see Settings)")
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    data = _post_json(
        url,
        {"contents": [{"parts": [{"text": prompt}]}]},
        {"Content-Type": "application/json"},
    )
    feedback = (data.get("promptFeedback") or {}).get("blockReason")
    if feedback:
        raise ProviderError(f"Gemini blocked the prompt: {feedback}")
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"] or ""
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderError(
            f"Unexpected Gemini response shape: {json.dumps(data)[:200]}"
        ) from exc


def _call_ollama(cfg: dict, prompt: str) -> str:
    base_url = (cfg.get("base_url") or "http://localhost:11434").rstrip("/")
    model = cfg.get("model") or ""
    if not model:
        raise ProviderError("Ollama model is not configured (see Settings)")
    data = _post_json(
        f"{base_url}/api/generate",
        {"model": model, "prompt": prompt, "stream": False,
         "format": "json", "options": {"temperature": 0.7}},
    )
    if not isinstance(data.get("response"), str):
        raise ProviderError("Unexpected Ollama response shape")
    return data["response"]


def _complete(cfg: dict, system: str, user: str) -> str:
    kind = (cfg.get("kind") or "").lower()
    if kind == "openai":
        return _call_openai(cfg, [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ])
    if kind == "gemini":
        return _call_gemini(cfg, f"{system}\n\n{user}")
    if kind == "ollama":
        return _call_ollama(cfg, f"{system}\n\n{user}")
    raise ProviderError(f"Unknown provider kind: {kind!r}")


# ---------------------------------------------------------------------------
# rewriting via AI provider
# ---------------------------------------------------------------------------

_REWRITE_SYSTEM = (
    "You are a writing assistant that rewrites text to sound natural while "
    "preserving meaning. Rules you MUST follow:\n"
    "1. Preserve the author's meaning, factual claims, and intent.\n"
    "2. NEVER alter numbers, units, dates, citation markers like [1] or "
    "(Author, 2020), or text inside quotation marks — copy them exactly.\n"
    "3. Keep specialist terminology unchanged.\n"
    "4. Do not invent anecdotes, personal experiences, or new facts.\n"
    "5. Rewrite ONLY the sentences listed; return valid JSON only, no markdown."
)

_MODE_GUIDANCE = {
    "natural": "Improve fluency and naturalness; keep the meaning.",
    "academic": "Use precise, natural academic language; keep terminology and evidence.",
    "professional": "Polished, concise business style; avoid excessive formality.",
    "conversational": "Friendly, approachable tone; contractions are fine.",
    "simple": "Plain vocabulary; short, easy-to-follow sentences.",
    "creative": "More varied, expressive phrasing; keep imagery and intent.",
    "native": "Fix grammar, collocations and idiomatic usage; sound native-level.",
    "voice": "Make only minimal edits; preserve the author's tone and rhythm.",
    "technical": "Keep precise terms; improve clarity and logical structure.",
    "minimal": "Change only what demonstrably benefits from improvement.",
}

_INTENSITY_GUIDANCE = {
    1: "Very light: fix only minor grammar/readability issues.",
    2: "Light: fix awkward wording; keep the original structure.",
    3: "Balanced: improve flow, vocabulary and coherence.",
    4: "Strong: substantially revise prose; preserve all facts.",
    5: "Comprehensive: reconstruct sentences for clarity and style.",
}


def rewrite_with_provider(cfg: dict, sentences: list[str], mode: str,
                          intensity: int) -> list[dict]:
    """Rewrite sentences via the configured AI provider.

    Returns [{index, original, rewritten, notes, changed}]. Raises
    ProviderError on any failure — the caller falls back or surfaces it.
    """
    mode = mode if mode in _MODE_GUIDANCE else "natural"
    intensity = max(1, min(5, int(intensity or 3)))
    numbered = "\n".join(f"[{i}] {s}" for i, s in enumerate(sentences))
    user = (
        f"Mode: {_MODE_GUIDANCE[mode]}\n"
        f"Intensity: {_INTENSITY_GUIDANCE[intensity]}\n\n"
        f"Sentences to rewrite:\n{numbered}\n\n"
        'Return JSON: {"rewrites": [{"index": <number>, "rewritten": "<text>", '
        '"note": "<what changed>"}]}. Include every input index exactly once.'
    )
    raw = _complete(cfg, _REWRITE_SYSTEM, user)
    try:
        parsed = json.loads(_strip_fences(raw))
    except json.JSONDecodeError as exc:
        raise ProviderError(
            f"Model returned invalid JSON: {exc}; excerpt: {_strip_fences(raw)[:200]}"
        ) from exc
    rewrites = parsed.get("rewrites") if isinstance(parsed, dict) else None
    if not isinstance(rewrites, list):
        raise ProviderError("Model response did not contain a 'rewrites' list")
    by_index = {}
    for r in rewrites:
        if isinstance(r, dict) and isinstance(r.get("index"), int):
            by_index[r["index"]] = r
    results = []
    for i, original in enumerate(sentences):
        r = by_index.get(i)
        rewritten = (r.get("rewritten") or "").strip() if r else ""
        if not rewritten:
            raise ProviderError(
                f"Model did not return a rewrite for sentence {i}")
        results.append({
            "index": i,
            "original": original,
            "rewritten": rewritten,
            "notes": [r.get("note", "Rewritten by AI provider.")] if r else [],
            "changed": rewritten != original,
        })
    return results


# ---------------------------------------------------------------------------
# connection test
# ---------------------------------------------------------------------------

def test_connection(cfg: dict) -> bool:
    """Minimal round-trip check. Raises ProviderError on failure."""
    kind = (cfg.get("kind") or "").lower()
    if kind == "openai":
        _call_openai(cfg, [{"role": "user", "content": "Reply with exactly: OK"}],
                     as_json=False)
    elif kind == "gemini":
        out = _call_gemini(cfg, "Reply with exactly: OK")
        if "OK" not in out:
            raise ProviderError("Gemini test reply was unexpected")
    elif kind == "ollama":
        base = (cfg.get("base_url") or "http://localhost:11434").rstrip("/")
        try:
            resp = requests.get(f"{base}/api/tags", timeout=15)
        except requests.RequestException as exc:
            raise ProviderError(f"Ollama is not reachable: {exc}") from exc
        if resp.status_code >= 400:
            raise ProviderError(f"Ollama returned HTTP {resp.status_code}")
    else:
        raise ProviderError(f"Unknown provider kind: {kind!r}")
    return True
