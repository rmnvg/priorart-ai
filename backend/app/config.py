import os

from dotenv import load_dotenv

load_dotenv()

SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

# Extra CORS origins for a deployed frontend, comma-separated
# (e.g. "https://priorart.vercel.app"). Any localhost port is always allowed.
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]

# Without both keys the app runs in demo mode: saved reports (the examples
# gallery, shared links) work, new analyses are refused with a clear message
# instead of failing halfway through the pipeline.
LIVE_MODE = bool(SERPAPI_API_KEY and GROQ_API_KEY)

# Agentic refinement: after the first search round, the LLM reads what came
# back and writes this many follow-up queries in the patents' own
# terminology. Each one costs one SerpApi search; 0 turns the step off.
REFINEMENT_QUERIES = int(os.getenv("REFINEMENT_QUERIES", "1"))
# Full-text/citation lookups per analysis (one SerpApi search each).
DEEP_DIVE_TOP_N = int(os.getenv("DEEP_DIVE_TOP_N", "8"))
# Google Trends market-interest lookup (one SerpApi search).
ENABLE_TRENDS = os.getenv("ENABLE_TRENDS", "true").lower() != "false"

# Where the web app is served, for report links handed out by the MCP server.
PUBLIC_APP_URL = os.getenv("PUBLIC_APP_URL", "http://localhost:3000").rstrip("/")

# Pause between progress events when replaying a cached analysis, so the
# staged checklist (and the agent's messages) can be read instead of
# flashing past. The events are the ones recorded on the real run.
REPLAY_STEP_SECONDS = float(os.getenv("REPLAY_STEP_SECONDS", "0.6"))
