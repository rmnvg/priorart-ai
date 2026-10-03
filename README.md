# PriorArt AI

[![CI](https://github.com/rmnvg/priorart-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/rmnvg/priorart-ai/actions/workflows/ci.yml)

**Has my invention already been done? Ask in your own language and get the answer
with the evidence: the exact patent passages, checked word for word.**

A farmer in Maharashtra, a student in Chennai, a founder in Bengaluru: anyone with an
idea gets a first-pass prior-art search that normally means a paid search, in English,
through a patent professional. Describe the idea (typed or spoken, in English, Hindi,
Tamil, Bengali, Marathi and more). PriorArt AI searches patents, papers and products
through SerpApi and answers with a decision, not a dashboard:

- **What we found:** "We found overlap in these three features. This fourth wasn't
  found in the evidence reviewed." Every finding quotes the patent passage, verified
  against the document's text in code, and says whether it came from the claims or the
  abstract. "Not found" is always bounded by what was reviewed.
- **What you could change:** concrete differentiation suggestions, a redesign studio
  that works under your constraints ("no electricity", "under ₹2,000"), and a re-check
  that tests the revised idea against the *original* closest patents.
- **Explore the research:** the patent landscape, citations, India status, timeline,
  and every query and SerpApi call behind the report.

## Why it's different

1. **Evidence, not a score.** The LLM never gets the last word: a quote that isn't in
   the patent's text is rejected in code. The novelty estimate is shown, small and
   labelled as an estimate, below the evidence.
2. **It searches like a professional.** An agent reads the first results, learns the
   patents' own vocabulary ("patents call this a *sectional shaft*, not a folding
   paddle") and searches again. Then it chases citations, which keyword search can't.
3. **Built for India.** It works in Indian languages end to end, searches Indian Patent
   Office filings, and previews how an Indian examiner would read the idea
   (Patents Act s. 3, 2(1)(j), 2(1)(ja)), labelled as a simulation.
4. **It finds what's free to use.** Patents in your space whose protection is reported
   as ended, and exactly where. The patent bargain says these are public; this tool
   makes them findable.

## Try it without API keys

```bash
cd backend && python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt && uvicorn app.main:app --port 8000
# second terminal
cd frontend && npm install && npm run dev
```

With no keys the backend runs in **demo mode**: every saved report in the examples
gallery opens fully interactive. Full setup with live search is [below](#setup).

**Hackathon:** SerpApi India Hackathon 2026, **Track 05: Knowledge & Public Interest**.
Patent information is public data that is locked behind expensive, jargon-heavy tools;
this project makes that knowledge accessible to anyone who can describe an idea,
in their own language, which is squarely a "public interest" use of freely searchable
government/patent-office data. The public-domain finder pushes that further: the
patent bargain is that inventions become public once protection lapses, but in
practice almost nobody can find out *which* ones have. This surfaces them.

[How it works](#how-it-works) · [How SerpApi powers it](#how-serpapi-powers-it) ·
[Everything it does](#everything-it-does) · [Benchmark](#does-it-actually-find-prior-art-the-benchmark) ·
[MCP server](#use-it-from-claude-desktop-cursor-or-any-mcp-client) · [Limitations](#known-limitations)

---

## How it works

```mermaid
flowchart TD
    idea(["💡 Idea<br/><i>typed or spoken, any Indian language</i>"])

    subgraph pipeline [" "]
        direction TB
        q["<b>1 · Understand + Query Generator</b> — LLM<br/>translate to technical English if needed, then 3 Google Patents boolean queries<br/><span style='font-size:11px'>major markets · India-specific · broad recall</span>"]
        s["<b>2 · Search Layer</b> — SerpApi, run concurrently<br/>google_patents (patents + scholar) per query, India query filtered to IN<br/><span style='font-size:11px'>+ google (market availability) + google_trends (market interest)</span>"]
        r["<b>3 · Rank & Dedupe</b><br/>merge, dedupe by id<br/><span style='font-size:11px'>score relevance via sentence-transformer embeddings</span>"]
        a["<b>3b · Refinement Agent</b> — LLM + SerpApi<br/>reads the first results, learns the patents' own vocabulary<br/><span style='font-size:11px'>searches again in their terms, re-ranks everything</span>"]
        d["<b>4 · Deep-Dive</b> — SerpApi, run concurrently<br/>full claims/abstract + citations for top 8 candidates<br/><span style='font-size:11px'>via google_patents_details, truncated/condensed</span>"]
        n["<b>5 · Novelty Verdict</b> — LLM<br/>overlap/differences/verdict per candidate<br/><span style='font-size:11px'>+ idea features with verified quotes + differentiation + claim spans</span>"]
        i["<b>6 · India Signal · Public Domain · Citation Chasing</b><br/><span style='font-size:11px'>computed from data already pulled in steps 2 and 4 — no extra API calls</span>"]
        f["<b>6a · Citation Follow-up</b> — SerpApi + LLM<br/>fetch the top 2 shared citations, check them against the idea's features<br/><span style='font-size:11px'>a newly shown feature updates the conclusion, with the citation named</span>"]
        l["<b>6b · Localize</b> — LLM<br/><span style='font-size:11px'>summary, suggestions and labels written back in the inventor's language</span>"]
        o["<b>7 · Orchestrator</b><br/><span style='font-size:11px'>async generator → staged progress events → one structured result</span>"]

        q --> s --> r --> a --> d --> n --> i --> f --> l --> o
    end

    api{{"⚡ FastAPI · POST /analyze<br/><i>Server-Sent Events</i>"}}

    mcp["🤖 <b>MCP server</b><br/>the same pipeline inside Claude Desktop / Cursor"]
    o --> mcp
    fe["🖥️ <b>Next.js frontend</b><br/>staged progress checklist<br/>ranked result cards<br/>India signal + differentiation<br/>landscape graph with citation edges<br/>filing timeline + market interest<br/>claim chart · shareable report · attorney brief"]

    idea --> q
    o --> api --> fe

    classDef stage fill:#eef2ff,stroke:#6366f1,stroke-width:1.5px,color:#1e1b4b,text-align:left
    classDef endpoint fill:#fef3c7,stroke:#d97706,stroke-width:1.5px,color:#451a03
    classDef terminus fill:#ecfdf5,stroke:#059669,stroke-width:1.5px,color:#064e3b
    classDef ideaNode fill:#fce7f3,stroke:#db2777,stroke-width:1.5px,color:#500724

    class q,s,r,a,d,n,i,l,o stage
    class api endpoint
    class fe,mcp terminus
    class idea ideaNode
    style pipeline fill:none,stroke:none
```

**Backend:** Python, FastAPI, Server-Sent Events for streaming progress.
**Frontend:** Next.js (App Router) + TypeScript + Tailwind, `react-force-graph-2d`
for the landscape graph.
**LLM:** Groq (`openai/gpt-oss-120b`, OpenAI-compatible API) — swapped in for Claude
to keep the project free to run; all LLM calls go through one wrapper
(`backend/app/llm.py`) so the provider can be swapped again in one file.
**Search:** SerpApi (`google_patents`, `google_patents_details`, `google`, `google_trends`).

---

## How SerpApi powers it

Nothing in a report is made up by the LLM. Every document, status, date and
citation comes from SerpApi; the LLM only writes the queries and compares texts.

| SerpApi engine | Calls per analysis | What it provides |
|---|---|---|
| `google_patents` (`scholar=true`, `clustered=true`) | 3 + 1 refinement | Prior-art patents **and** academic papers in one call per query angle. The India angle adds `country=IN`, so it searches Indian Patent Office filings for real. Each result's `country_status` feeds the India signal and the public-domain finder, and the clustered `summary` feeds the assignee breakdown. |
| `google_patents_details` | up to 8 + 2 | Full abstract + claims for the feature evidence and claim chart, plus `patent_citations` / `cited_by` for **citation chasing** and the citation edges in the landscape graph. Up to 2 more calls **follow up** the strongest citation discoveries, so a document keyword search missed can change the conclusion. |
| `google` | 1 | Market-availability check: is a product like this already sold? |
| `google_trends` | 1 | Five years of search interest in the product category: does anyone want this? |

The refinement agent's follow-up query goes through the same `google_patents`
engine, so its extra search is counted in that row.

Every report ends with a **"How this report was built"** panel. It lists the exact
queries, the result count for each, and the SerpApi calls behind that report, and
each query opens in Google Patents so the user can keep searching from there.

---

## Everything it does

**AI-powered patent prior-art & novelty checker.** Describe an invention idea in
plain words (typed or spoken, in English, Hindi or another Indian language) and get
back ranked prior art (patents, academic papers, and existing
products), a feature-by-feature evidence check, an interactive patent-landscape graph,
and concrete suggestions for how to differentiate your idea from what already exists.

**Clarify before searching.** The optional inventor interview asks up to three
questions in the inventor's language about missing mechanisms, relationships, or
distinguishing features. Already specific descriptions can proceed without questions.
The inventor can skip unknown details, edit the exact combined description, and
confirm it before any search runs. Original wording and inventor-written answers
are preserved; the interview does not generate a replacement invention.

The report leads with **evidence, not a score**: *"We found overlap in these three
features. This fourth feature wasn't found in the evidence reviewed."* Under each
feature is the exact passage from the document that shows it, checked word for word
against that document's text in code, and whether it came from the patent's claims, its
abstract, or only a search snippet. "Not found" is always bounded by what was reviewed.
The model's overall novelty estimate is still shown, as a small, labelled estimate.

**Inspect the source.** New reports keep the abstract and numbered claims separate.
Click a finding to see its highlighted passage in the actual reviewed section;
expand review scope to see the retrieved claim count and any truncation. The initial
review uses up to 2,400 characters of the abstract and 1,600 characters from each of
the first six claims per patent. Matching a quote verifies its presence, not the
correctness of the model's interpretation. Older saved reports remain readable and
explicitly indicate when section-level coverage was not recorded.

**Challenge this finding:** every feature marked “not found” in a saved report
can trigger a targeted second investigation. Two searches try the feature's
mechanism and alternative patent terminology; up to three patents are checked
against that specific feature. The follow-up shows the original finding alongside
the new result, exact verified passages, their abstract/claim sections, the queries,
and whether each document was previously reviewed. A failed or incomplete check
is distinguished from a completed search with no supporting passage.

Challenges use at most **5 additional SerpApi calls** (2 searches + 3 detail
lookups). Completed findings are saved with the report and reload without searches,
including in demo mode. Incomplete attempts can be retried. This is supplemental
evidence: the original report, score, Q&A context and exports remain unchanged.
The scope is patents only, reviewing up to 4,000 characters of the abstract and
1,500 characters from each of the first 12 claims; excerpts are labelled.

API: `GET /report/{report_id}/challenge/{feature_id}` loads a saved challenge or
returns `null`; `POST` runs it or returns its saved result. Only features without
evidence in the original report are eligible. Concurrent identical requests are
coalesced within one backend process.

It also does the inverse, which most prior-art tools don't: it identifies the patents
in your space whose **protection is reported as ended**. Those usually aren't
obstacles: once a patent lapses or expires in a country, what it describes is generally
free to use there. Each one lists exactly where it's reported lapsed, and where its
status isn't reported. In testing, a typical search surfaced 10 such patents out of 26.

And it goes past keyword search the way a professional searcher would: it **chases
citations**. The patents closest to your idea cite older work and are cited by newer
work, and documents that several close matches all point to are almost always
relevant, whatever words they use. Keyword search can't find those. Citation chasing
can, from data the deep-dive already fetched.

Then it **follows them up**. The two strongest citation discoveries are fetched in full
(`google_patents_details`) and checked against the same features as everything else.
If one shows a feature no searched document did, the conclusion changes, and the report
names the citation that changed it.

The search is an **agent**, not a single query. After the first round it reads the
results, notices the vocabulary the relevant patents use ("patents call this a
*sectional shaft*, not a folding paddle"), and searches again in their terms. That's
the step a professional searcher takes by instinct, and the one keyword tools skip.

It speaks the inventor's language. A farmer can **dictate an idea in Hindi** (or
Tamil, Bengali, Marathi and more) and read the verdict, summary and suggestions in
Hindi. The patent evidence and the downloadable attorney brief stay in English,
which is the language patent offices and agents actually work in.

Improving the idea is evidence-based, not a score that moves. **"Apply & re-check"**
folds a suggestion into the idea and re-runs everything. It then tests the revised
idea against the *original* closest patents, so an overlap can't disappear just because
a new search ranked it lower. For each patent it shows whether the change is already in
it and what's still shared, all backed by quotes verified in code. It also lists the
new close matches the change ran into.

It also reads **drawings**. An inventor can upload a rough sketch or a photo of a
prototype. A vision model reads it into parts and how they connect, and lists the
details it couldn't make out. Nothing is searched until the inventor corrects that
reading, and the exact text that will be searched is shown before they do.

And it helps **redesign around what exists**. In the redesign studio the inventor locks
the features that must stay and sets constraints ("no electricity", "under ₹2,000 per
unit"). It proposes three alternative designs, each tied to a quoted passage, verified in
code, from one of the original closest matches it moves away from. Cost and performance
are treated as design targets, and every design is labelled a hypothesis until the
inventor re-checks it through the same evidence-backed re-check as above.

The report is organised as a decision, not a dashboard: **What we found** (the
feature evidence, the closest match with its passage, what sets the idea apart, the
next step), **What you could change** (differentiation suggestions, the redesign
studio, re-check, the examination preview), and **Explore the research** (the graph,
citations, timeline, assignees, India status, every result and query), which stays
folded until opened.

And the report is a conversation, not a dead end: **ask it follow-up questions**
("which patent is the real risk?", "can I sell this in India?") and get short answers
drawn only from what the search found, each one citing its source documents. Ask in
Hindi, and the answer comes back in Hindi.

Finally, it reads the evidence **the way an Indian patent examiner would**. The
examination preview screens the idea against **Section 3 of the Patents Act** (the
exclusions: software "as such", farming methods, traditional knowledge, and more).
It then checks every element of the idea against the patents found, and a
"disclosed" mark only counts if it quotes the patent and the quote is verified in
code. From that it works out, deterministically, whether a **lack-of-novelty
(s. 2(1)(j))** or **lack-of-inventive-step (s. 2(1)(ja))** objection is likely. It
ends with the idea's *novelty core*: the elements no patent discloses. It's labelled
as a simulation throughout, and it drafts no claims; that's a patent agent's job.

It's built for independent inventors, students, and early-stage founders who want a
first read on "has this already been done?" before spending money on a formal patent
search — patent search tools built for law firms are expensive and not designed for
someone doing a first-pass sanity check on a raw idea.

---

## Project structure

```
priorart-ai/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, POST /analyze SSE endpoint
│   │   ├── llm.py                # Groq LLM wrapper (all model calls go through here)
│   │   ├── cache.py              # memory + on-disk cache keyed on idea text
│   │   ├── models.py             # SSE event / result Pydantic models
│   │   ├── serpapi_client.py     # shared SerpApi client: response cache, offline mode, key redaction
│   │   ├── service.py            # cache + demo-mode + pipeline, shared by API and MCP
│   │   ├── mcp_server.py         # MCP server (Claude Desktop, Cursor, ...)
│   │   ├── report_markdown.py    # report → Markdown for AI assistants
│   │   └── pipeline/
│   │       ├── language.py           # Indian-language input + localized reports
│   │       ├── query_generator.py    # 1.1
│   │       ├── search.py             # 1.2
│   │       ├── rank.py               # 1.3
│   │       ├── refine.py             # refinement agent (search in patent vocabulary)
│   │       ├── ask.py                # follow-up Q&A grounded in a report
│   │       ├── examination.py        # Indian examination preview (s. 3, 2(1)(j), 2(1)(ja))
│   │       ├── recheck.py            # evidence comparison for "Apply & re-check"
│   │       ├── sketch.py             # sketch / prototype photo → parts and connections
│   │       ├── redesign.py           # constrained redesign around the closest matches
│   │       ├── deepdive.py           # 1.4
│   │       ├── novelty.py            # 1.5 (+ claim chart)
│   │       ├── india_status.py       # 1.6
│   │       ├── public_domain.py      # expired-patent finder
│   │       ├── citation_chase.py     # backward/forward citation chasing
│   │       ├── citation_followup.py  # fetch + assess top citation discoveries
│   │       ├── evidence.py           # idea features, verified quotes, headline
│   │       ├── market_trends.py      # Google Trends market-interest signal
│   │       └── orchestrator.py       # 1.7 — wires it all together
│   ├── tests/test_pipeline.py    # pure-logic tests (no keys/network needed)
│   ├── benchmark/                # search-recall benchmark on 17 real patents (12 dev + 5 held-out)
│   ├── scripts/warm_examples.py  # fills the examples gallery
│   ├── scripts/quota.py          # searches left and what they buy (free to run)
│   ├── .cache/                   # persisted analyses — survives restarts
│   ├── .serpapi-cache/           # raw SerpApi responses, each search paid once (not committed)
│   └── requirements.txt
└── frontend/
    ├── app/page.tsx               # top-level view state machine
    ├── components/                # IdeaForm, ProgressChecklist, ResultsView,
    │                               # LandscapeGraph, ClaimChart, CompetitorLandscape,
    │                               # CitationDiscoveries, FilingTimeline,
    │                               # MarketTrendChart, IndiaSignal,
    │                               # SearchStrategyPanel, ReportActions,
    │                               # VoiceInput, ExamplesGallery,
    │                               # SketchReview, RedesignStudio
    ├── lib/                       # analyzeStream.ts (SSE client), landscapeGraph.ts,
    │                               # highlightText.tsx, reportBrief.ts, i18n.ts
    └── types/analysis.ts          # shared contract with the backend
```

---

## Setup

### Prerequisites

- Python 3.11+
- Node.js 20+
- A [SerpApi](https://serpapi.com) API key (free tier works for local testing)
- A [Groq](https://console.groq.com) API key (free tier)

### Backend

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

### Frontend

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

### API quota and caching

A single analysis costs **up to 16 SerpApi searches** (3 patent queries + 1
refinement query + 1 market query + 1 Trends lookup + up to 8 detail lookups + up to 2
citation follow-ups). SerpApi's free tier allows 250/month, so roughly 15 fresh analyses. The independent calls run concurrently, so
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
| `SEARCH_PROFILE` | `full` | `full` is up to 16 searches per analysis; `lean` is up to 11 (5 detail lookups, 1 citation follow-up, no Trends). The individual settings above still override it. |
| `SERPAPI_CACHE` | `true` | Save and replay raw SerpApi responses |
| `SERPAPI_OFFLINE` | `false` | Never call SerpApi: an uncached request fails instead of spending a search |

Check what's left, and what it buys, without spending a search:
`python -m scripts.quota`.

Every analysis gets a **shareable report link** (`/?report=<id>`), served from this
cache by `GET /report/{id}`. Opening a link never triggers a new (billable) run.

If the search quota runs out, the app says so explicitly rather than reporting
"no results found" — an empty result and a failed search are reported differently
on purpose.

### Running the tests

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

---

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

---

## Does it actually find prior art? The benchmark

`backend/benchmark/` holds 17 real, granted patents, each verified on Google
Patents: the one-click checkout, slide-to-unlock, the coffee pod, the bladeless
fan, and more. Each one is paired with a plain description of the invention,
written the way an inventor would say it and **deliberately avoiding the patent's
own wording**. The benchmark runs the search on each description and records where
the real patent lands, **before and after the refinement agent**.

The cases are split. The 12 **development** cases were available while the search was
being built. The 5 **held-out** cases were written afterwards and are never used for
tuning. Three of them are in Hindi and go through the same translation step as the
app. The report gives each split its own figures, and it lists every case where
refinement made the ranking worse, every failure with the queries that were run, and
the runtime and searches used.

```bash
cd backend
python -m benchmark.run --dry-run         # cases + SerpApi cost (~68 searches)
python -m benchmark.run                   # writes benchmark/results/latest.md + latest.json
python -m benchmark.run --split heldout   # held-out cases only (~20 searches)
```

Results are written to `backend/benchmark/results/latest.md` when the benchmark is
run. It measures retrieval only, not the legal accuracy of any verdict.

As of October 2, the configured SerpApi account has no searches remaining, so no
live retrieval figures are published. The held-out run requires up to 20 searches.
See [validation status](docs/validation-status.md) for automated checks, live
interview responses, and the remaining retrieval and human-review work.

The interview can be checked independently without SerpApi calls:

```bash
cd backend
python -m scripts.check_interview
```

This records three development examples in
`backend/benchmark/results/interview-smoke.json`; it is not a held-out evaluation.

---

## Screenshots

**Input screen**

![Input screen](docs/screenshots/input-screen.png)

**Staged progress** — each pipeline stage checks off live as it runs, so the
multi-step pipeline is visibly real, not a single spinner:

![Staged progress](docs/screenshots/staged-progress.png)

**Novelty verdict** — the headline answer, with a severity-coded meter and the
counts behind it:

![Novelty verdict](docs/screenshots/results-hero.png)

**Free to build on** — prior art whose protection has lapsed, separated into patents
past the 20-year term and those abandoned early:

![Public domain](docs/screenshots/public-domain.png)

**Patent-landscape graph** — nodes are search results, sized and pulled closer to
the idea node by relevance, colored by CPC patent classification:

![Landscape graph](docs/screenshots/landscape-graph.png)

**Who owns this space** — assignee concentration from SerpApi's clustered search
summary, with an explicit note when the field is too fragmented for any holder to
dominate:

![Competitor landscape](docs/screenshots/competitor-landscape.png)

**Differentiation suggestions** — concrete, cited changes that would move the idea
away from its closest matches. "Apply & re-check" folds a suggestion into the idea
and re-runs the whole pipeline, showing the verdict shift:

![Differentiation](docs/screenshots/differentiation.png)

**Claim chart** — a side-by-side comparison of the idea against its closest match,
with matching colors marking the same technical concept in both texts (the
technique patent professionals call "claim charting"):

![Claim chart](docs/screenshots/claim-chart.png)

---

## Known limitations

- **India legal-status data**: Google Patents' legal-status tracking for the Indian
  Patent Office is often `UNKNOWN` rather than `ACTIVE`/`NOT_ACTIVE` — a real gap in
  Google's own data coverage, not a bug in this tool. The India signal is accurate
  to what Google Patents reports, which is sometimes incomplete for `IN` filings.
  It is a legal-status count ("related patents reported active in India"), not a
  finding that those patents overlap the idea.
- **Public-domain status is indicative, not legal advice.** It relies on the legal
  status Google Patents reports, which is incomplete for some jurisdictions, and a
  patent lapsed early for unpaid fees can occasionally be revived. The tool
  deliberately requires positive evidence of lapse (never treating "unknown" as
  free) and labels the two cases differently, but verify with an attorney before
  relying on it commercially.
- **The feature evidence is bounded by what was reviewed**: abstracts and leading
  claims of the top documents, not full specifications. "Not found" means not in
  those texts. The model's overall novelty estimate is not a calibrated probability,
  which is why it's shown below the evidence and labelled as an estimate. Neither one
  says anything about technical plausibility.
- **Result similarity** ("High / Medium / Low text similarity") is embedding
  similarity between the result's text and the idea. It orders results; it is not a
  probability of overlap, so it is never shown as a percentage.
- **Claim-chart highlighting** depends on the LLM copying spans verbatim from the
  source text; when it paraphrases instead (common with longer patent claim text),
  that pair is silently skipped rather than mis-highlighted. Expect it to show
  fewer highlighted pairs on some runs than others.
- **Citation chasing** only covers patents: academic papers and products have no
  citation data in Google Patents. It follows one hop, the references of the top 8
  candidates, so a document linked only through a chain of citations won't surface.
- **Market interest** uses Google Trends, which has no data for very niche product
  categories. When interest is too low to measure, the section is left out rather
  than shown as a flat line that would wrongly suggest zero demand.
- **Embedding-based relevance ranking** uses a general-purpose English
  sentence-transformer model, not one specifically trained for multilingual or
  patent-domain text — ranking quality is best for English, technically-worded
  ideas.

---

## Disclosure

This is a new project, built from scratch for the SerpApi India Hackathon 2026.

**AI tools used in development:** [Claude Code](https://claude.com/claude-code)
(Anthropic) was used as an AI pair-programmer throughout development — writing and
testing the backend pipeline, the frontend, and this documentation.
Codex (OpenAI) helped implement and test the inventor interview, source-section
evidence review, and validation documentation.

**AI/APIs used at runtime by the app itself:** Groq (hosting `openai/gpt-oss-120b`)
powers the LLM reasoning steps (translation, query generation, search refinement,
novelty assessment, claim charting, report localization, redesign proposals), and
Groq-hosted `qwen/qwen3.8-27b` reads uploaded sketches; SerpApi powers all
patent, scholar, product and Trends search. Voice input uses the browser's built-in
Web Speech API.
