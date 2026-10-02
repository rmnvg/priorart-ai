"""Live, three-case interview smoke check (Groq only; zero SerpApi calls).

Run from backend: python -m scripts.check_interview
Records actual responses, not an accuracy score. Inspect the questions manually.
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from app.pipeline.interview import plan_interview

CASES = [
    ("vague-en", "A cheap crop dryer that works without electricity."),
    ("detailed-en", "A crop dryer with a black metal solar air collector connected below "
     "stacked mesh trays, and a tall chimney that draws warm air upward by natural "
     "convection. A wax actuator opens an exhaust flap as temperature rises. "
     "My proposed difference is a detachable insulated clay heat-storage sleeve "
     "around the collector. It must work without electricity."),
    ("vague-hi", "मैं बिना बिजली के अनाज सुखाने वाला सस्ता यंत्र बनाना चाहता हूँ।"),
]


def main() -> int:
    results = []
    for case_id, idea in CASES:
        start = time.monotonic()
        try:
            plan = plan_interview(idea)
            result = {"id": case_id, "idea": idea, "response": plan.model_dump(), "error": None}
        except Exception as exc:
            # Provider exceptions can contain credentials or request metadata.
            result = {"id": case_id, "idea": idea, "response": None, "error": type(exc).__name__}
        result["seconds"] = round(time.monotonic() - start, 2)
        results.append(result)
        print(f"{case_id}: {'recorded' if not result['error'] else result['error']} ({result['seconds']}s)", flush=True)
    path = Path(__file__).resolve().parents[1] / "benchmark/results/interview-smoke.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "run_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Live interview responses only; not retrieval accuracy or legal validation.",
        "serpapi_calls": 0, "results": results,
    }, ensure_ascii=False, indent=2) + "\n")
    return int(any(r["error"] for r in results))


if __name__ == "__main__":
    raise SystemExit(main())
