# Launch checklist — before the October 5, 2026 11:59 PM IST deadline

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

## 2. Spend it in this order (~140 searches)

From `backend/` with the venv active:

| Step | Command | Searches |
|---|---|---|
| Fill the gallery (5 ideas, refreshing the old kayak report) | `python -m scripts.warm_examples --refresh kayak` | ≤ 70 |
| Cache one re-check for the video: open the Hindi report in the app, click **Apply & re-check** on one suggestion | (in the browser) | ≤ 14 |
| Benchmark | `python -m benchmark.run` (rerun with `--resume` if interrupted) | ≤ 48 |

Check the remaining quota at any point without spending any:
`curl "https://serpapi.com/account?api_key=$SERPAPI_API_KEY"`.

## 3. Update the repo

- [ ] Commit `backend/.cache/*.json` (the gallery reports) and `backend/benchmark/results/`
- [ ] Put the benchmark numbers in the README's benchmark section
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
