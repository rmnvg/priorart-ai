# Launch checklist — before the October 10, 2026 11:59 PM IST deadline

## Schedule

| Dates | Focus |
|---|---|
| Oct 1–3 | Evidence-first report and report clarity |
| Oct 4–6 | Citation follow-through and the benchmark (publish `results/latest.md`) |
| Oct 7–8 | Try it with a few real users; fix what confuses them |
| Oct 9 | Record the video and submit |
| Oct 10 | Buffer only — don't plan work for it |

## 1. Get search quota

The free plan's 250 searches/month reset on your account's billing date (see the
SerpApi dashboard). Optionally, ask for hackathon credits — draft:

> Subject: SerpApi India Hackathon 2026 — credit request for testing
>
> Hi SerpApi team, I'm building PriorArt AI for the India Hackathon (Track 05). It
> uses google_patents, google_patents_details, google and google_trends to check
> invention ideas for prior art, including Indian Patent Office filings, and it
> includes a recall benchmark on real patents. I've used this month's 250 free
> searches while building. Would it be possible to get extra credits to run the
> benchmark and record the demo? Account email: <your email>. Thank you!

## 2. Spend it in this order (~185 searches)

From `backend/` with the venv active:

| Step | Command | Searches |
|---|---|---|
| Fill the gallery (6 ideas, refreshing the old kayak report and anything saved before feature evidence) | `python -m scripts.warm_examples --refresh kayak` | ≤ 96 |
| Open each gallery report and click **See how an Indian patent examiner would respond** once, so the previews are cached for the video | (in the browser) | 0 (Groq only) |
| Cache the demo journey: open the Hindi crop-dryer report, run the redesign studio with "no electricity" + "under ₹2,000", and click **Re-check this design** on one alternative | (in the browser) | ≤ 16 |
| Benchmark, held-out first so the number to quote exists even if quota runs out | `python -m benchmark.run --split heldout`, then `python -m benchmark.run --resume` | ≤ 68 |

Check the remaining quota at any point without spending any:
`curl "https://serpapi.com/account?api_key=$SERPAPI_API_KEY"`.

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
