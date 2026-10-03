"""The one SerpApi client every pipeline stage calls.

Every successful response is saved to disk, keyed on the request's
parameters, so a search is paid for once: re-running an idea after a prompt
or code change replays the same search data and spends no quota. That is the
difference between iterating freely and burning a 250-search month in a
day. Only the search data is reused; every LLM step still runs fresh.

SERPAPI_OFFLINE=true goes further and never calls SerpApi at all, so a
request that isn't cached fails like a network error instead of spending a
search.
"""
import hashlib
import json
import logging
import os
import re
import tempfile
from pathlib import Path

import serpapi

from app.config import SERPAPI_API_KEY, SERPAPI_CACHE, SERPAPI_OFFLINE

logger = logging.getLogger(__name__)

RESPONSE_CACHE_DIR = Path(__file__).resolve().parent.parent / ".serpapi-cache"

_API_KEY_PARAM = re.compile(r"(api_key=)[^&\s]+")


def redact(value: object) -> str:
    """SerpApi sends the API key as a URL query parameter, so it appears
    verbatim inside every HTTPError message. Always redact before logging —
    these logs end up on screen during demos and in shared terminals."""
    return _API_KEY_PARAM.sub(r"\1***", str(value))


class SearchOffline(RuntimeError):
    """SERPAPI_OFFLINE is on and this request has no saved response."""


def request_key(params: dict) -> str:
    """Stable across runs and argument order; the API key never enters it."""
    canonical = json.dumps(
        {k: v for k, v in params.items() if k != "api_key"}, sort_keys=True, default=str
    )
    return hashlib.sha256(canonical.encode()).hexdigest()[:24]


class CachedClient:
    def __init__(self, api_key: str, cache_dir: Path, enabled: bool = True, offline: bool = False):
        self._client = serpapi.Client(api_key=api_key)
        self.cache_dir = cache_dir
        self.enabled = enabled
        self.offline = offline

    def _path(self, params: dict) -> Path:
        return self.cache_dir / f"{request_key(params)}.json"

    def _load(self, params: dict) -> dict | None:
        if not self.enabled:
            return None
        try:
            return json.loads(self._path(params).read_text())["response"]
        except (OSError, json.JSONDecodeError, KeyError):
            return None

    def _save(self, params: dict, response: dict) -> None:
        # Stages search concurrently, so write to a temp file and rename:
        # a reader never sees half a file.
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            payload = json.dumps({"params": params, "response": response})
            fd, tmp = tempfile.mkstemp(dir=self.cache_dir, suffix=".tmp")
            with os.fdopen(fd, "w") as f:
                f.write(payload)
            os.replace(tmp, self._path(params))
        except OSError as e:
            logger.warning("Could not save SerpApi response: %s", e)

    def search(self, **params) -> dict:
        cached = self._load(params)
        if cached is not None:
            logger.info("SerpApi cache hit: %s", params.get("engine"))
            return cached
        if self.offline:
            raise SearchOffline(f"SERPAPI_OFFLINE: no saved response for {params.get('engine')} {params}")
        response = dict(self._client.search(**params))
        # An error payload (quota, bad request) must be retried next time,
        # never replayed as if it were data.
        if self.enabled and not response.get("error"):
            self._save(params, response)
        return response


client = CachedClient(
    SERPAPI_API_KEY, RESPONSE_CACHE_DIR, enabled=SERPAPI_CACHE, offline=SERPAPI_OFFLINE
)
