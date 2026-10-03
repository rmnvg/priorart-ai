# The benchmark

[← Back to the README](../README.md)

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
python -m benchmark.run --split heldout --citations 5   # + citation chasing (~45)
```

Results are written to `backend/benchmark/results/latest.md` when the benchmark is
run. It measures retrieval only, not the legal accuracy of any verdict.

## Held-out result (October 3): 0 of 5

**The search did not find the target patent in any of the 5 held-out cases**,
before or after refinement, and citation chasing over the top 5 candidates didn't
surface it either. The reports are in
[`heldout-keyword-only-2026-10-03.md`](../backend/benchmark/results/heldout-keyword-only-2026-10-03.md)
and [`latest.md`](../backend/benchmark/results/latest.md), with every query that was run.

All five held-out targets are foundational patents from 1917–1983: the zip
fastener, hook-and-loop (Velcro), the flying disc, the LEGO brick and the Rubik's
cube. Each has hundreds of later patents in the same vocabulary, and those are what
keyword search returns. Citation chasing didn't reach the originals: the closest
matches were mostly recent Chinese utility models with no recorded backward
citations, and the US ones cite 1990s–2010s work. We have not tuned anything
against these cases, so the figure stands as measured. The development set
(mostly 1990s–2010s patents) has not been run live yet.

What this means for an inventor: the tool is far better at surfacing **recent and
active** prior art, the kind that blocks a filing today, than at finding the
original patent behind a decades-old product category. It does not replace a
professional search.

See [validation status](validation-status.md) for automated checks, live
interview responses, and the remaining human-review work.

The interview can be checked independently without SerpApi calls:

```bash
cd backend
python -m scripts.check_interview
```

This records three development examples in
`backend/benchmark/results/interview-smoke.json`; it is not a held-out evaluation.
