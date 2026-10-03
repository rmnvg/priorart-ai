# Known limitations

[← Back to the README](../README.md)

- **India legal-status data**: Google Patents' legal-status tracking for the Indian
  Patent Office is often `UNKNOWN` rather than `ACTIVE`/`NOT_ACTIVE` — a real gap in
  Google's own data coverage, not a bug in this tool. The India signal is accurate
  to what Google Patents reports, which is sometimes incomplete for `IN` filings.
  It is a legal-status count ("related patents reported active in India"), not a
  finding that those patents overlap the idea.
- **Indian filings in Google Patents are sparse.** Even a query as broad as
  `(solar) (dryer OR drying)` restricted to `country=IN` returns 7 filings, mostly
  without titles. The India-only query angle therefore often comes back empty; that
  reflects Google Patents' coverage of the Indian Patent Office, and the report says
  "0 results" for that query rather than hiding it.
- **Old foundational patents are hard to find** (see the benchmark): keyword search
  surfaces the many later patents in the same field first.
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
