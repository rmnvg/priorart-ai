# Setup, quota and tests

[← Back to the README](../README.md)

## Prerequisites

- Python 3.11+
- Node.js 20+
- A [SerpApi](https://serpapi.com) API key (free tier works for local testing)
- A [Groq](https://console.groq.com) API key (free tier)

## Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in `backend/.env`:

```
SERPAPI_API_KEY=your_serpapi_key
GROQ_API_KEY=your_groq_key
GROQ_MODEL=openai/gpt-oss-120b
```

Run it:

```bash
uvicorn app.main:app --port 8000
```

Confirm it's up: `curl http://localhost:8000/health` → `{"status":"ok","live":true}`

**No API keys? It still runs.** Without keys the backend starts in **demo mode**:
every saved report in the examples gallery opens fully interactive, and a new idea
gets a clear "demo mode" message instead of a half-run pipeline. That's the fastest
way to see the project: skip the `.env` step entirely.

Optional settings in `backend/.env`:

| Variable | Default | What it does |
|---|---|---|
| `REFINEMENT_QUERIES` | `1` | Follow-up queries the refinement agent may run (1 search each); `0` turns it off |
| `GROQ_VISION_MODEL` | `qwen/qwen3.8-27b` | Groq model that reads uploaded sketches (`GROQ_MODEL` is text-only) |
| `DEEP_DIVE_TOP_N` | `8` | Candidates pulled in full (1 search each) |
| `CITATION_FOLLOWUPS` | `2` | Citation discoveries fetched and assessed (1 search each); `0` turns it off |
| `ENABLE_TRENDS` | `true` | Google Trends market-interest lookup (1 search) |
| `ALLOWED_ORIGINS` | none | Extra CORS origins for a deployed frontend |
| `PUBLIC_APP_URL` | `http://localhost:3000` | Where report links from the MCP server point |
| `REPLAY_STEP_SECONDS` | `0.6` | Pause between progress steps when replaying a saved analysis, so the stages stay readable |

## Frontend

```bash
cd frontend
npm install
```

Create `frontend/.env.local`:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Run it:

```bash
npm run dev
```

Open the printed local URL (defaults to `http://localhost:3000`, or the next free
port if that one's taken) and paste in an invention idea.

## API quota and caching

A single analysis costs **up to 17 SerpApi searches** (3 patent queries + 1
refinement query + 1 papers query + 1 market query + 1 Trends lookup + up to 8 detail
lookups + up to 2 citation follow-ups). SerpApi's free tier allows 250/month, so
roughly 14 fresh analyses (about 20 with `SEARCH_PROFILE=lean`). The independent calls run concurrently, so
a fresh run takes seconds of search time, not a minute.

Because of that, every completed analysis is cached to `backend/.cache/`, keyed on
a hash of the idea text. The cache is **persistent across restarts** — re-running
the same idea replays the saved result instantly and costs nothing, which is what
makes a demo reproducible without live quota. Delete a file from `backend/.cache/`
to force a fresh run of that idea.

Underneath that, every raw SerpApi response is saved to `backend/.serpapi-cache/`,
keyed on the request's parameters, so **each search is paid for once**. Re-running an
idea after a prompt or code change replays the same search data while every LLM step
runs fresh. An error response (such as an exhausted quota) is never saved.

| Variable | Default | What it does |
|---|---|---|
| `SEARCH_PROFILE` | `full` | `full` is up to 17 searches per analysis; `lean` is up to 12 (5 detail lookups, 1 citation follow-up, no Trends). The individual settings above still override it. |
| `SERPAPI_CACHE` | `true` | Save and replay raw SerpApi responses |
| `SERPAPI_OFFLINE` | `false` | Never call SerpApi: an uncached request fails instead of spending a search |

Check what's left, and what it buys, without spending a search:
`python -m scripts.quota`.

Every analysis gets a **shareable report link** (`/?report=<id>`), served from this
cache by `GET /report/{id}`. Opening a link never triggers a new (billable) run.

If the search quota runs out, the app says so explicitly rather than reporting
"no results found" — an empty result and a failed search are reported differently
on purpose.

## Running the tests

```bash
cd backend
source venv/bin/activate
python -m pytest tests/ -q
```

The suite covers the pipeline's pure logic: dedupe/merge rules, the India status
tally, LLM-output validation guards, claim truncation, cache persistence, citation
chasing, Trends parsing, the country-filtered India query, and report-link
validation, language handling, the refinement agent, the whole orchestrator (with
every external call faked), demo mode, and benchmark scoring. It needs no API keys
and no network, and runs in under a second.

The frontend has its own unit tests (claim-chart highlighting, landscape-graph
construction, the attorney brief, localization, the filing timeline, cited answers):

```bash
cd frontend
npm test            # vitest
npm run typecheck
```

Both suites, plus a production build, run on every push via GitHub Actions
(`.github/workflows/ci.yml`).

## Use it from Claude Desktop, Cursor, or any MCP client

The same pipeline runs as an [MCP](https://modelcontextprotocol.io) server, so an
AI assistant can check an idea for prior art in the middle of a conversation:

> *"I'm thinking of building a clay fridge that cools by evaporation. Has this been
> done?"* → the assistant calls `check_prior_art` and answers with the verdict,
> cited patents, ones reported as expired, and a link to the full report.

Tools: `check_prior_art(idea, language?)`, `get_prior_art_report(report_id)`,
`ask_about_report(report_id, question)`, `preview_examination_report(report_id)`,
`list_saved_reports()`. It shares the web app's cache and report ids, so a check
started in the assistant opens as the full interactive report in the browser.

Claude Desktop (`claude_desktop_config.json`), using absolute paths:

```json
{
  "mcpServers": {
    "priorart-ai": {
      "command": "/path/to/priorart-ai/backend/venv/bin/python",
      "args": ["-m", "app.mcp_server"],
      "env": { "PYTHONPATH": "/path/to/priorart-ai/backend" }
    }
  }
}
```

Keys are read from `backend/.env` as usual. With no keys, the saved-report tools
still work.
