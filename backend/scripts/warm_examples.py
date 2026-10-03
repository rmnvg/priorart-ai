"""Fill the examples gallery: run a fixed set of ideas through the full
pipeline so their reports are cached and open instantly — for demos, for
judges without API keys, and for the two sample buttons on the home page.

Usage, from backend/:

    python -m scripts.warm_examples --dry-run     # list ideas + SerpApi cost
    python -m scripts.warm_examples               # run the ones not cached yet
    python -m scripts.warm_examples --refresh kayak
        # re-run a cached one (e.g. to pick up new pipeline features)
    python -m scripts.warm_examples --only solar-dryer-hindi
        # run just these, so scarce quota goes to the demo first

Each fresh analysis costs up to 17 SerpApi searches (3 patent queries, 1
refinement query, 1 paper search, 1 market search, 1 Trends lookup, up to 8
detail lookups, up to 2 citation follow-up lookups), or up to 12 with
SEARCH_PROFILE=lean.
Searches already in backend/.serpapi-cache/ cost nothing, so a refresh after
a pipeline change is often free.
"""
import argparse
import asyncio
import sys

from app import service
from app.cache import evict, get_cached
from app.config import MAX_SEARCHES_PER_ANALYSIS

# The first two must match frontend/lib/sampleIdea.ts exactly (a test
# checks), or the sample buttons turn into slow, billable live runs.
EXAMPLES: dict[str, str] = {
    "kayak": (
        "A collapsible kayak paddle that splits into four interlocking segments, each hollow "
        "and buoyant, so the whole paddle also serves as an emergency flotation device when "
        "disassembled."
    ),
    "solar-dryer-hindi": (
        "एक सौर ऊर्जा से चलने वाला फसल सुखाने का यंत्र, जिसमें काले रंग की टिन की चादर हवा को "
        "गर्म करती है और एक छोटा पंखा गर्म हवा को जाली वाली ट्रे के ऊपर से गुज़ारता है, ताकि "
        "किसान टमाटर और मिर्च बिना बिजली के सुखा सकें।"
    ),
    "clay-fridge": (
        "A refrigerator made entirely of clay that keeps vegetables and milk cool without "
        "electricity: water from a reservoir on top seeps through the porous clay walls and "
        "evaporates, cooling the storage chamber inside."
    ),
    "cattle-collar": (
        "A low-cost collar for dairy cows with a temperature sensor and a motion sensor that "
        "detects early signs of fever or heat, and sends an SMS alert to the farmer's basic "
        "feature phone without needing a smartphone app."
    ),
    # Shows the examination preview's Section 3 screen: traditional
    # knowledge (3(p)) and admixture (3(e)) are the likely flags.
    "herbal-wound-paste": (
        "A wound-healing paste made by grinding fresh neem leaves with turmeric and honey, "
        "applied to cuts and burns to speed healing and prevent infection, packed in "
        "single-use sachets for rural first-aid kits."
    ),
    "erickshaw-swap": (
        "A battery-swapping station for electric rickshaws where the driver slides out a "
        "depleted battery pack and slides in a charged one in under a minute; each pack has an "
        "RFID tag so the station tracks its charge cycles and bills the driver per swap."
    ),
}


def _is_cached(idea: str) -> bool:
    return get_cached(service.cache_text_for(idea, None)) is not None


async def _run(name: str, idea: str) -> bool:
    print(f"→ {name}: analyzing...", flush=True)
    async for event in service.analyze(idea):
        if event.type == "progress":
            print(f"    {event.message}", flush=True)
        elif event.type == "error":
            print(f"  ✗ {name}: {event.message}", flush=True)
            return False
        elif event.type == "result":
            pct = round(event.data.overall_novelty_confidence * 100)
            print(f"  ✓ {name}: {pct}% novelty · report {event.data.report_id}", flush=True)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Fill the examples gallery.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--refresh", help="comma-separated example names to re-run")
    parser.add_argument("--only", help="comma-separated example names; skip the rest")
    args = parser.parse_args()

    refresh = {n.strip() for n in (args.refresh or "").split(",") if n.strip()}
    only = {n.strip() for n in (args.only or "").split(",") if n.strip()}
    unknown = (refresh | only) - EXAMPLES.keys()
    if unknown:
        print(f"Unknown examples: {', '.join(sorted(unknown))}", file=sys.stderr)
        return 2

    todo = [
        n for n in EXAMPLES
        if (not only or n in only) and (n in refresh or not _is_cached(EXAMPLES[n]))
    ]
    print(
        f"{len(todo)} of {len(EXAMPLES)} examples to run, up to "
        f"{len(todo) * MAX_SEARCHES_PER_ANALYSIS} SerpApi searches (fewer if already in the response cache)."
    )
    for name in EXAMPLES:
        if name in todo:
            state = "to run"
        elif only and name not in only:
            state = "skipped (--only)"
        else:
            state = "cached"
        print(f"  {name:20} {state}")
    if args.dry_run or not todo:
        return 0

    for name in todo:
        if name in refresh:
            evict(service.report_id_for(EXAMPLES[name], None))
        if not asyncio.run(_run(name, EXAMPLES[name])):
            print("Stopping — fix the error above, then rerun (finished ones stay cached).")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
