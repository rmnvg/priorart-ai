"""How much SerpApi quota is left, and what it buys. The account endpoint is
free, so this never spends a search.

Usage, from backend/:

    python -m scripts.quota
"""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

from app.config import MAX_SEARCHES_PER_ANALYSIS, SEARCH_PROFILE, SERPAPI_API_KEY
from app.serpapi_client import RESPONSE_CACHE_DIR, redact

# From benchmark/run.py's docstring: 3 searches + 1 refinement per case.
HELDOUT_BENCHMARK = 20
FULL_BENCHMARK = 68


def main() -> int:
    if not SERPAPI_API_KEY:
        print("No SERPAPI_API_KEY in backend/.env.", file=sys.stderr)
        return 2
    url = f"https://serpapi.com/account?api_key={SERPAPI_API_KEY}"
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            account = json.load(response)
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        print(f"Could not reach SerpApi: {redact(e)}", file=sys.stderr)
        return 1

    left = account.get("total_searches_left", 0)
    saved = len(list(Path(RESPONSE_CACHE_DIR).glob("*.json")))
    print(f"Plan:            {account.get('plan_name')} (renews {account.get('plan_renewal_date')})")
    print(f"Searches left:   {left}   (used this month: {account.get('this_month_usage')})")
    print(f"Saved responses: {saved} in {RESPONSE_CACHE_DIR.name}/ (replayed free)")
    print()
    print(f"Fresh analyses ({SEARCH_PROFILE} profile, ≤{MAX_SEARCHES_PER_ANALYSIS} each): {left // MAX_SEARCHES_PER_ANALYSIS}")
    print(f"Held-out benchmark (~{HELDOUT_BENCHMARK}):  {'yes' if left >= HELDOUT_BENCHMARK else 'no'}")
    print(f"Full benchmark (~{FULL_BENCHMARK}):      {'yes' if left >= FULL_BENCHMARK else 'no'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
