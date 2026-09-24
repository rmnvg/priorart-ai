# PriorArt AI — End-to-End Build Plan

**Project:** AI-powered patent prior-art & novelty checker
**Hackathon:** SerpApi India Hackathon 2026 — Track 05: Knowledge & Public Interest
**Goal:** Paste an invention idea in plain English → get ranked prior art (patents, academic
papers, existing products) with a novelty verdict, reasoning, citations, an interactive
patent-landscape graph, and concrete differentiation suggestions.

This document is written as a build spec. Follow it phase by phase, in order. Each phase
should be working and tested before moving to the next — don't build the frontend against
an unfinished backend, and don't add wow features until the core pipeline is solid.

---

## 0. Project setup

1. Initialize two directories in one repo: `backend/` (FastAPI, Python) and `frontend/`
   (Next.js + TypeScript, App Router).
2. `backend/`: set up a virtualenv, install `fastapi`, `uvicorn`, `serpapi` (or
   `serpapi-search-tools`), `anthropic` (for Claude API calls), `python-dotenv`,
   `sentence-transformers` (optional, for embedding similarity).
3. `frontend/`: `npx create-next-app@latest` with TypeScript + Tailwind + App Router.
4. Create a `.env` in `backend/` for `SERPAPI_API_KEY` and `ANTHROPIC_API_KEY`. Add `.env`
   to `.gitignore` immediately — never commit keys.
5. Set up CORS in FastAPI to allow the Next.js dev origin.
6. Get a SerpApi key, confirm the free-tier quota, and run a handful of raw
   `google_patents` queries (with `scholar=true` and `clustered=true`) directly against
   the API — not through your pipeline yet — just to see real response shapes before
   writing code against assumptions.
7. Define shared TypeScript interfaces (in `frontend/types/`) for what the backend will
   return, even before the backend exists. This keeps both sides honest about the
   contract as you build them in parallel later.

---

## 1. Core backend pipeline (build and test with curl/Postman — no frontend yet)

Build this as a sequence of independent, individually testable Python functions/modules
before wiring them into a single endpoint. Each stage should be callable and testable on
its own.

### 1.1 Query Generator
- Input: raw idea description (free text).
- Use an LLM call (Claude) to:
  - extract the core technical concepts from the idea
  - generate 2–4 distinct SerpApi search queries using Google Patents' boolean syntax
    (parentheses, OR, semicolon-separated multi-term queries)
  - where confident, suggest a relevant CPC classification code to narrow results
- Output: a list of query strings, not just one — a single query under-covers the idea
  space; write down explicitly which query type covers "US/major markets", "India-specific"
  and "broader/looser recall" so you're not relying on the LLM to think of these on its own.

### 1.2 Search Layer
- For each generated query, call `google_patents` with `scholar=true` and `clustered=true`.
- Also fire one query against the plain `google` engine (or `google_shopping`) for a
  market-availability check — "does a product like this already exist commercially."
- Store raw results per query — don't discard the query-to-result mapping, you'll want it
  for debugging and for the landscape graph later.

### 1.3 Rank & Dedupe
- Merge results across all queries. Dedupe by `patent_id` / `scholar_id`.
- Score each result's relevance to the original idea — either via embedding similarity
  (idea text vs. title+snippet) or an LLM relevance judgment. Pick one method and keep it
  simple; don't build both.
- Keep the CPC code (`cpc`, `cpc_description`) attached to each result — this feeds the
  landscape graph clustering later. Don't discard it during ranking.

### 1.4 Deep-Dive on Top Candidates
- For the top 5–8 ranked results, call `google_patents_details` to pull full claims and
  `prior_art_keywords`.
- Truncate/summarize long claim text before it goes anywhere near an LLM prompt — raw
  claims can be very long and this will otherwise blow up latency and cost. Summarize each
  candidate's claims to a few sentences of the technically load-bearing content before
  the novelty-comparison step.

### 1.5 Novelty Verdict + Differentiation Suggestions (single LLM call, richer prompt)
- For each top candidate, ask the LLM to identify:
  - specific overlapping technical elements between the idea and this prior art
  - specific differences
  - a verdict: blocking / partially overlapping / not relevant
- Then produce one **overall** response:
  - overall novelty confidence (not just per-candidate — synthesize across all of them)
  - **concrete differentiation suggestions** — what specific element(s) the user could
    change or add to distinguish their idea from the closest matches. This is what turns
    the tool from "here's what exists" into "here's what to do about it."
  - every claim must carry a citation back to the specific result it came from
    (`patent_link`, `scholar_link`, or product URL)

### 1.6 India-Specific Patentability Signal
- From the `country_status` field already present in `google_patents` results, explicitly
  compute and surface: how many of the closest-matching results are `ACTIVE` in India (`IN`)
  specifically, versus active elsewhere but not in India.
- Frame this as its own field in the output, not buried in prose — e.g. a structured
  `india_status: { blocking_in_india: n, active_elsewhere_only: n }` object. This is a
  zero-extra-API-call feature since the data is already being pulled — just don't let it
  get lost in generic result formatting.

### 1.7 Wire it all together
- Combine 1.1–1.6 into a single orchestration function.
- Expose it as a generator/async function that yields progress events at each stage
  (`"generating queries"`, `"searching patents"`, `"searching scholar"`, `"checking market
  availability"`, `"ranking results"`, `"scoring novelty"`) — this is what will power the
  staged-progress UI later, so build the staging into the pipeline itself, not bolted on
  afterward in the API layer.

**Checkpoint before moving on:** run the full pipeline against 3–4 different real invention
ideas (a mix of genuinely novel-sounding and obviously-already-invented ones) and manually
sanity-check the output makes sense. Don't proceed to the API layer until this is solid.

---

## 2. FastAPI layer

1. Build a single `POST /analyze` endpoint that accepts the idea text and streams back the
   staged progress events from 1.7 via Server-Sent Events (SSE), ending with the final
   structured result (ranked results, novelty verdicts, differentiation suggestions, India
   signal, and the raw CPC/similarity data needed for the landscape graph).
2. Add basic input validation (empty input, extremely short input) and a friendly error for
   zero-results cases — don't let this crash, since a judge might paste an obscure idea.
3. Add simple in-memory or file-based caching keyed on idea text, so re-running the same
   demo query during development/rehearsal doesn't burn API quota repeatedly.
4. Test the full endpoint with curl (or a simple SSE test client) before touching the
   frontend at all.

---

## 3. Frontend (Next.js + TypeScript)

Build in this order:

1. **Input screen** — single textarea for the idea description, a submit button, minimal
   copy explaining what the tool does.
2. **Staged progress view** — consume the SSE stream from `/analyze` and show each pipeline
   stage as it completes (a simple animated checklist is enough — this is what makes the
   multi-step pipeline visually legible to a judge watching the demo, so don't skip it or
   collapse it into a single spinner).
3. **Results view**:
   - Ranked result cards: title, source type (patent/scholar/product), novelty
     contribution, expandable citation link.
   - A prominent India-patentability summary block using the data from 1.6.
   - A clearly separated "How to differentiate your idea" section using the output from 1.5
     — make this visually distinct from the raw prior-art list, since it's your strongest
     usefulness feature.
4. **Patent-landscape graph** (wow feature — build after the above is working end-to-end):
   - Use a force-directed graph library (`react-force-graph` or D3 directly).
   - Nodes = each ranked result, clustered/colored by CPC code (you already have this data
     from step 1.3 — reuse it, don't recompute).
   - The user's idea is a distinctly highlighted node, positioned near its closest matches
     by similarity score.
   - This should be the visual centerpiece of the demo video — budget real UI polish time
     here specifically.
5. **Claim-chart highlighting view** (second wow feature, build only if the graph is done
   and stable):
   - Side-by-side: the user's idea text vs. the closest matching patent's claim text.
   - Ask the LLM (extend the prompt from step 1.5, don't add a new call) to return matched
     technical concept spans in both texts, then highlight them with matching colors in the
     UI.
   - This is a real technique patent professionals use ("claim charting"), so frame it that
     way in the UI copy — it signals domain awareness, not generic AI-wrapper output.

If you're short on time, cut in this order: claim-chart view first, then market-availability
check, then embedding-based ranking (fall back to LLM-only ranking). Do not cut the
landscape graph or the differentiation suggestions — those are your two strongest
differentiators relative to a generic "search wrapper" project.

---

## 4. Edge cases & robustness pass

Go through these explicitly, don't just wait to discover them during the demo:
- Idea description too vague/short to generate meaningful queries
- Zero search results returned
- An idea in a domain SerpApi's patent data covers poorly (very new tech, non-English idea)
- SerpApi rate limit / quota exhaustion mid-pipeline — fail gracefully, don't crash the UI
- Very long invention descriptions (multi-paragraph) — make sure query generation still
  extracts the core concept rather than choking on the length

---

## 5. Documentation

1. **README.md** must include:
   - What the project does and who it's for (one paragraph)
   - Architecture overview (the pipeline diagram, in text or as an image)
   - Setup instructions precise enough that someone unfamiliar with the project can run it
     locally (env vars needed, install commands, how to start backend and frontend)
   - Screenshots or a GIF of the landscape graph and results view
   - Which track this targets and why
   - Disclosure section: confirm this is a new project built for the hackathon, and list
     which AI tools were used in development
2. Keep the README itself readable — this is graded directly, not just a formality.

---

## 6. Demo video (under 3 minutes — plan the shot list before recording)

1. **Opening (≈20s):** State the problem in one sentence — patent search is expensive and
   inaccessible for independent inventors and small startups.
2. **Live run (≈70s):** Paste a real invention idea, show the staged progress UI actually
   running (proves the multi-step pipeline is real), then land on the results view.
3. **Landscape graph (≈30s):** Show the interactive graph, point out clustering and where
   the user's idea sits relative to existing prior art. This is your visual wow moment —
   give it real screen time.
4. **Differentiation + India signal (≈30s):** Show the "how to differentiate" section and
   the India-specific patentability summary — this is where usefulness lands hardest.
5. **Claim chart (≈15s, if built):** Quick highlight-matched-text moment.
6. **Close (≈10s):** Brief glance at the repo/architecture, end.

Video quality itself doesn't affect judging — a clean screen recording is enough. What
matters is that every claimed feature is visibly demonstrated working, not just described.

---

## 7. Submission checklist

- [ ] Public GitHub repository with the README from section 5
- [ ] Demo video (<3 minutes), public or unlisted link, tested in a private/incognito
      browser window before submitting
- [ ] Project description and track selection (Knowledge & Public Interest)
- [ ] Participant details: name, email, phone, occupation, years of experience
- [ ] Disclosures: confirm the project is newly built for this hackathon, list AI tools used
- [ ] Repository and video links both open without requiring access/login, verified in a
      private browser window
- [ ] Submit (not just save as draft) through the official submission dashboard

---

## Priority order if time runs short

Build in this order, and if you have to stop early, stop at the end of a completed tier —
never leave a tier half-built:

1. Core pipeline (section 1) — non-negotiable, this is the whole project
2. FastAPI layer + basic frontend results view (sections 2–3.3) — non-negotiable, this is
   the demoable product
3. India-patentability signal + differentiation suggestions (1.5, 1.6, 3.3) — cheap, high
   usefulness impact, build these before any visual wow feature
4. Patent-landscape graph (3.4) — the single highest-impact visual differentiator
5. Claim-chart highlighting (3.5) — nice-to-have, cut first under time pressure
6. Market-availability check — nice-to-have, cut first under time pressure
