"""Thin wrapper around the LLM provider (Groq, OpenAI-compatible API).

All pipeline modules should call `complete` / `complete_json` from here rather
than instantiating a client directly — keeps the provider swappable behind
one file.
"""
import json

from openai import OpenAI

from app.config import GROQ_API_KEY, GROQ_MODEL

_client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")


def complete(prompt: str, system: str | None = None, temperature: float = 0.2) -> str:
    """Single-turn text completion. Returns the raw text response."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    response = _client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        temperature=temperature,
    )
    return response.choices[0].message.content or ""


def complete_json(prompt: str, system: str | None = None, temperature: float = 0.2) -> dict:
    """Completion constrained to JSON output. Raises ValueError if the model
    doesn't return parseable JSON — callers should catch and retry/fallback,
    since open-weight models are less reliable at this than Claude."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    response = _client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content or ""
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM did not return valid JSON: {raw[:500]}") from e
