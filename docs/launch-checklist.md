# Launch checklist — before the October 10, 2026 11:59 PM IST deadline

## Schedule

Revised October 3: blocked on quota until credits arrive (see step 1).

| Dates | Focus |
|---|---|
| Oct 1–3 | Evidence-first report and report clarity |
| Oct 4–6 | Citation follow-through and the benchmark (publish `results/latest.md`) |
| Oct 7–8 | Try it with a few real users; fix what confuses them |
| Oct 9 | Record the video and submit |
| Oct 10 | Buffer only — don't plan work for it |

## 1. Get search quota — blocking

As of October 3 the account has **0 searches left and renews on October 16**, after
the deadline. Nothing in step 2 can happen until there is quota, so do this first:

- **Email SerpApi for hackathon credits today** (draft below). Replies take time.
- Fallback: a teammate's key, or one month of a paid SerpApi plan.

`python -m scripts.quota` (from `backend/`, free to run) shows what's left and how
many analyses it buys.

> Subject: SerpApi India Hackathon 2026 — credit request for testing
>
> Hi SerpApi team, I'm building PriorArt AI for the India Hackathon (Track 05). It
> uses google_patents, google_patents_details, google and google_trends to check
> invention ideas for prior art, including Indian Patent Office filings, and it
> includes a recall benchmark on real patents. I've used this month's 250 free
> searches while building, and my plan renews on October 16, after the deadline.
> Would it be possible to get extra credits to run the benchmark and record the
> demo? Account email: <your email>. Thank you!

## 2. Spend it in this order

Every raw SerpApi response is now saved in `backend/.serpapi-cache/`, so no search is
paid for twice: refreshing a report after a code change is free as long as the queries
match. Use `SEARCH_PROFILE=lean` (≤ 11 searches per analysis instead of 16) unless
quota is plentiful. Stop at whichever row the quota runs out on; each row is useful
without the ones below it.

From `backend/` with the venv active:

| # | Step | Command | Searches (lean) |
|---|---|---|---|
| 1 | The demo: Hindi crop dryer | `SEARCH_PROFILE=lean python -m scripts.warm_examples --only solar-dryer-hindi` | ≤ 11 |
| 2 | In the browser: redesign it with "no electricity" + "under ₹2,000", then **Re-check this design** on one alternative | — | ≤ 11 |
| 3 | Held-out benchmark (the number to quote) | `python -m benchmark.run --split heldout` | ≤ 20 |
| 4 | Refresh kayak with the new features (cheap if the queries repeat) | `SEARCH_PROFILE=lean python -m scripts.warm_examples --only kayak --refresh kayak` | ≤ 11 |
| 5 | Remaining gallery ideas | `SEARCH_PROFILE=lean python -m scripts.warm_examples` | ≤ 11 each |
| 6 | Rest of the benchmark | `python -m benchmark.run --resume` | ≤ 48 |

Then open each gallery report and click **See how an Indian patent examiner would
respond** once, so the previews are cached (Groq only, no searches).

Rows 1–3 are about 42 searches. If that is all you get, it covers the video, the
benchmark number, and one up-to-date gallery report.

## 3. Update the repo

- [ ] Commit `backend/.cache/*.json` (the gallery reports) and `backend/benchmark/results/`
- [ ] Put the held-out benchmark numbers in the README's benchmark section, with the
      failures and the cases refinement made worse — modest and reproducible beats impressive
- [ ] Retake screenshots: Hindi report, progress with the agent message, citation
      chasing, timing charts, "How this report was built", the gallery
- [ ] Delete `priorart-ai-build-plan.md`, or move it to `docs/`

## 4. Record the video — `docs/demo-video-script.md`

## 5. Submit

- [ ] Public repo, and a video link that opens in a private window
- [ ] Track 05, and the project description (the README intro works)
- [ ] "How SerpApi is used": paste the README's **How SerpApi powers it** table
- [ ] AI-tools disclosure (README **Disclosure**)
- [ ] Press **Submit**, not just save
