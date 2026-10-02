# Validation status — October 2, 2026

Branch: `feat/inventor-interview-evidence`.

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

## Retrieval benchmark: blocked by search quota

The SerpApi account endpoint reported 0 searches remaining and 250 used this
month. No retrieval benchmark was attempted after this check, and no retrieval
accuracy number is claimed. The dry run confirmed five held-out cases requiring
up to 20 searches at the current configuration.

When quota is available:

```bash
cd backend
venv/bin/python -m benchmark.run --split heldout
venv/bin/python -m benchmark.run --resume
```

Publish `backend/benchmark/results/latest.md`, including failures, exact-publication
recall, and refinement regressions. Do not substitute interview results for
retrieval results. The feature changes do not invalidate existing saved reports;
refresh demo examples to demonstrate new section attribution and review scope.

## Human review: still to collect

For a small evidence review, take ten feature/quote pairs across at least three
live reports. Have a technically informed reviewer mark each as supports,
partially supports, does not support, or unclear. Record source section, passage,
feature, and rationale. Quote-presence verification alone is not this assessment.

For usefulness, have three to five intended users describe an invention, inspect
one finding, and re-check one redesign. Record task completion, misunderstandings,
and what decision changed. No user-study or human-review results are claimed yet.
