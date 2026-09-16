import re

import serpapi

from app.config import SERPAPI_API_KEY

client = serpapi.Client(api_key=SERPAPI_API_KEY)

_API_KEY_PARAM = re.compile(r"(api_key=)[^&\s]+")


def redact(value: object) -> str:
    """SerpApi sends the API key as a URL query parameter, so it appears
    verbatim inside every HTTPError message. Always redact before logging —
    these logs end up on screen during demos and in shared terminals."""
    return _API_KEY_PARAM.sub(r"\1***", str(value))
