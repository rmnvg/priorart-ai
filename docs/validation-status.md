# Validation status — October 3, 2026

Branch: `feat/hackathon-final` (interview work from `feat/inventor-interview-evidence`).

## Implemented

- Optional inventor interview: up to three questions, in the input language;
  questions can be skipped and unknown answers excluded. A source-grounded
  completeness check can skip questions for an already specific idea.
- The final description is editable and requires confirmation. The application
  combines original text and user answers without asking an LLM to rewrite them.
  Interview questions are marked as context, not asserted invention features.
- Patent abstract and claim excerpts retain their own labels and review bounds.
  Feature evidence in the initial assessment and citation follow-up is verified
  against a single section, preventing abstract passages being labelled as claims.
- A source viewer highlights the matched passage, distinguishes an excerpt from a
  complete retrieved section, and shows how many retrieved claims were reviewed.
  Existing saved reports show when section-level records are unavailable.

The initial review allows 2,400 abstract characters and 1,600 characters from each
of the first six claims per patent. These limits do not constitute full-document
review. Larger prompts may increase model latency or hit provider token limits;
live full-pipeline performance has not been measured for this change.

## Automated and browser checks

- Backend: `cd backend && venv/bin/python -m pytest tests -q` — 141 tests passed.
- Frontend: `cd frontend && npm test && npm run typecheck` — 45 tests passed;
  type checking passed.
- Production: `cd frontend && npm run build -- --webpack`.
- Chrome against the production frontend with intercepted fixture API responses:
  answered questions, unknown-answer exclusion, editable confirmation, no search
  before confirmation, sufficiently detailed description bypass, interview-error
  skip, evidence highlighting, coverage inspection, and mobile horizontal overflow.
  No browser runtime errors were observed. This is a UI integration check, not a
  live end-to-end retrieval test.

Turbopack's default build cannot bind its CSS-worker port in this environment;
the supported Webpack production build succeeds. The default build command is
unchanged for normal development/CI environments.

## Live interview checks

Run `cd backend && venv/bin/python -m scripts.check_interview`.
Actual responses are in
[`interview-smoke.json`](../backend/benchmark/results/interview-smoke.json).

| Development example | Questions | Response time |
|---|---:|---:|
| Vague English crop dryer | 3 | 0.88 s |
| Detailed English crop dryer | 0 | 4.79 s |
| Vague Hindi crop dryer | 3, in Hindi | 4.37 s |

These three examples were used while refining the prompt. They are **not a
held-out benchmark**, and their timings are individual observations. The model
can still include examples in questions despite the prompt discouraging that;
questions are labelled context-only and every final description is editable.
No search requests were made by this check. It does not establish legal accuracy
or validate whether generated questions improve retrieval.

## Search fixes found during live runs — October 3

New SerpApi quota (250 searches) became available on October 3. The first live
run of the Hindi crop-dryer demo exposed three defects, all fixed and covered by
tests on branch `feat/hackathon-final`:

1. **Papers crowded out patents.** With `scholar=true` on every query, the three
   English queries returned 30 papers and 0 patents; a 20-result page with
   `scholar=true` was 19 papers and 1 patent. Patent queries are now patents-only
   with 20 results (same cost), and papers come from one separate
   `scholar=true, patents=false` call. Detail lookups go to patents first.
2. **Model-written document ids were mangled** (`patent/CN205448635U en` for
   `patent/CN205448635U/en`), so every assessment and quote was discarded by an
   exact-match lookup. Ids now resolve tolerantly (punctuation and case ignored;
   a bare publication number only when unambiguous), in novelty and challenge.
3. **Elided quotes were rejected.** The model joins fragments with "..." despite
   instructions. An elided quote now resolves to the continuous source passage
   from its first fragment to its last (each fragment ≥ 2 words, passage ≤ 60
   words, in order); the stored quote is copied from the document, never from the
   model, so strict verification still holds.

Hindi crop dryer, before → after: 1 → 21 patents ranked, 0 → 5 assessments kept,
0 → 4 of 4 features with verified claim/abstract evidence, 0 → 12 public-domain
patents. Offline re-runs of the novelty step on the same cached documents gave
3–4 of 4–5 features with evidence per run; some pairings remain weak (a
controller clause offered for "no external electricity"). Verification checks a
quote's presence, not the model's interpretation.

## Retrieval benchmark: held-out run, October 3

Held-out (5 cases, 3 in Hindi): **0 of 5** in the top 10, before and after
refinement, and 0 of 5 among citation discoveries with the top 5 candidates
deep-dived. 20 searches for the keyword-only run
([report](../backend/benchmark/results/heldout-keyword-only-2026-10-03.md)) and 42
for the run with citation chasing
([report](../backend/benchmark/results/latest.md)). The patent-only search change
above was made before either run; nothing was tuned on these cases afterwards.

All five targets are 1917–1983 foundational patents. The top candidates were
mostly recent CN utility models with no backward citations, or US patents citing
later work. The development split (12 cases, ~48 searches) has not been run.

## Quota used on October 3

170 of 250 searches: the Hindi demo, its re-runs and single-search diagnostic
probes 45, the held-out benchmark 62, the gallery (5 reports, lean profile) 63.
80 remain until the November 3 renewal.

## Human review: still to collect

For a small evidence review, take ten feature/quote pairs across at least three
live reports. Have a technically informed reviewer mark each as supports,
partially supports, does not support, or unclear. Record source section, passage,
feature, and rationale. Quote-presence verification alone is not this assessment.

For usefulness, have three to five intended users describe an invention, inspect
one finding, and re-check one redesign. Record task completion, misunderstandings,
and what decision changed. No user-study or human-review results are claimed yet.
