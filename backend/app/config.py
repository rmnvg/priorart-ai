import os

from dotenv import load_dotenv

load_dotenv()

SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
# Reads uploaded sketches and prototype photos. GROQ_MODEL is text-only, so
# images go to a separate vision model on the same Groq key.
GROQ_VISION_MODEL = os.getenv("GROQ_VISION_MODEL", "qwen/qwen3.8-27b")

# Extra CORS origins for a deployed frontend, comma-separated
# (e.g. "https://priorart.vercel.app"). Any localhost port is always allowed.
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]

# Without both keys the app runs in demo mode: saved reports (the examples
# gallery, shared links) work, new analyses are refused with a clear message
# instead of failing halfway through the pipeline.
LIVE_MODE = bool(SERPAPI_API_KEY and GROQ_API_KEY)

# Save every SerpApi response to backend/.serpapi-cache/ and replay it for an
# identical request, so each search is paid for once.
SERPAPI_CACHE = os.getenv("SERPAPI_CACHE", "true").lower() != "false"
# Never call SerpApi: a request without a saved response fails instead.
# For iterating on prompts and code with no quota at risk.
SERPAPI_OFFLINE = os.getenv("SERPAPI_OFFLINE", "false").lower() == "true"

# Search budget per analysis. "full" (the default) is up to 17 searches;
# "lean" is up to 12: fewer full-text lookups, one citation follow-up, no
# Trends. Each setting below still overrides the profile.
SEARCH_PROFILE = os.getenv("SEARCH_PROFILE", "full").lower()
_PROFILE_DEFAULTS = {
    "full": {"REFINEMENT_QUERIES": "1", "DEEP_DIVE_TOP_N": "8", "CITATION_FOLLOWUPS": "2", "ENABLE_TRENDS": "true"},
    "lean": {"REFINEMENT_QUERIES": "1", "DEEP_DIVE_TOP_N": "5", "CITATION_FOLLOWUPS": "1", "ENABLE_TRENDS": "false"},
}
if SEARCH_PROFILE not in _PROFILE_DEFAULTS:
    raise ValueError(f"SEARCH_PROFILE must be one of {sorted(_PROFILE_DEFAULTS)}, not {SEARCH_PROFILE!r}")


def _budget(name: str) -> str:
    return os.getenv(name) or _PROFILE_DEFAULTS[SEARCH_PROFILE][name]


# Agentic refinement: after the first search round, the LLM reads what came
# back and writes this many follow-up queries in the patents' own
# terminology. Each one costs one SerpApi search; 0 turns the step off.
REFINEMENT_QUERIES = int(_budget("REFINEMENT_QUERIES"))
# Full-text/citation lookups per analysis (one SerpApi search each).
DEEP_DIVE_TOP_N = int(_budget("DEEP_DIVE_TOP_N"))
# Citation follow-up: documents found by citation chasing that are fetched
# and assessed against the idea's features (one SerpApi search each).
CITATION_FOLLOWUPS = int(_budget("CITATION_FOLLOWUPS"))
# Google Trends market-interest lookup (one SerpApi search).
ENABLE_TRENDS = _budget("ENABLE_TRENDS").lower() != "false"

# Most searches one analysis can make: 3 patent queries, the refinement
# queries, 1 paper query, 1 market query, Trends, the deep-dive and the
# citation follow-ups.
MAX_SEARCHES_PER_ANALYSIS = 3 + REFINEMENT_QUERIES + 1 + 1 + int(ENABLE_TRENDS) + DEEP_DIVE_TOP_N + CITATION_FOLLOWUPS

# Where the web app is served, for report links handed out by the MCP server.
PUBLIC_APP_URL = os.getenv("PUBLIC_APP_URL", "http://localhost:3000").rstrip("/")

# Pause between progress events when replaying a cached analysis, so the
# staged checklist (and the agent's messages) can be read instead of
# flashing past. The events are the ones recorded on the real run.
REPLAY_STEP_SECONDS = float(os.getenv("REPLAY_STEP_SECONDS", "0.6"))
