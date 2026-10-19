"""Benchmark indexed title queries against forced collection scans."""

from __future__ import annotations

import csv
import sys
import time
from pathlib import Path
from typing import Any

import plotly.express as px
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from db import get_titles  # noqa: E402


RUNS = 20
OUTPUT_CSV = ROOT / "docs" / "benchmark.csv"
OUTPUT_HTML = ROOT / "docs" / "benchmark.html"

QUERIES: dict[str, dict[str, Any]] = {
    "text search": {
        "filter": {"$text": {"$search": "Avatar"}},
        # MongoDB rejects any hint combined with $text. This equivalent
        # regex query permits the required $natural collection-scan baseline.
        "scan_filter": {
            "$or": [
                {"title": {"$regex": "Avatar", "$options": "i"}},
                {"alt_titles": {"$regex": "Avatar", "$options": "i"}},
                {"synopsis": {"$regex": "Avatar", "$options": "i"}},
            ]
        },
        "sort": [],
    },
    "genre filter": {
        "filter": {"genres": "Action"},
        "sort": [],
    },
    "filter + sort by rating": {
        "filter": {"media_type": "movie", "rating": {"$gte": 7.5}},
        "sort": [("rating", -1), ("votes", -1)],
    },
    "mood filter": {
        "filter": {"mood_tags": "epic"},
        "sort": [],
    },
}


def _plan_stages(plan: dict[str, Any]) -> list[str]:
    """Collect stage names recursively from an explain plan."""
    stages: list[str] = []
    if "stage" in plan:
        stages.append(str(plan["stage"]))
    for key in ("inputStage", "outerStage", "innerStage"):
        child = plan.get(key)
        if isinstance(child, dict):
            stages.extend(_plan_stages(child))
    for child in plan.get("inputStages", []):
        if isinstance(child, dict):
            stages.extend(_plan_stages(child))
    return stages


def _winning_stage(explain: dict[str, Any]) -> str:
    """Classify the winning plan as IXSCAN, COLLSCAN, or its top-level stage."""
    stages = _plan_stages(explain["queryPlanner"]["winningPlan"])
    if "IXSCAN" in stages or "TEXT_MATCH" in stages:
        return "IXSCAN"
    if "COLLSCAN" in stages:
        return "COLLSCAN"
    return stages[0] if stages else "UNKNOWN"


def benchmark_query(name: str, specification: dict[str, Any], forced_scan: bool) -> dict[str, Any]:
    """Run one query repeatedly and collect timing and execution statistics."""
    collection = get_titles()
    query = specification.get("scan_filter", specification["filter"]) if forced_scan else specification["filter"]
    sort = specification["sort"]
    cursor = collection.find(query, {"_id": 0})
    if sort:
        cursor = cursor.sort(sort)
    if forced_scan:
        cursor = cursor.hint({"$natural": 1})

    # Warm the same cursor shape used for the timing loop.
    list(cursor)
    timings: list[float] = []
    for _ in range(RUNS):
        timed_cursor = collection.find(query, {"_id": 0})
        if sort:
            timed_cursor = timed_cursor.sort(sort)
        if forced_scan:
            timed_cursor = timed_cursor.hint({"$natural": 1})
        started = time.perf_counter()
        list(timed_cursor)
        timings.append((time.perf_counter() - started) * 1000)

    explain_find: dict[str, Any] = {
        "find": collection.name,
        "filter": query,
        "projection": {"_id": 0},
    }
    if sort:
        explain_find["sort"] = dict(sort)
    if forced_scan:
        explain_find["hint"] = {"$natural": 1}
    explain = collection.database.command(
        "explain",
        explain_find,
        verbosity="executionStats",
    )
    stats = explain["executionStats"]
    return {
        "query": name,
        "mode": "without indexes (COLLSCAN)" if forced_scan else "with indexes",
        "average_ms": round(sum(timings) / len(timings), 3),
        "totalDocsExamined": stats.get("totalDocsExamined", 0),
        "nReturned": stats.get("nReturned", 0),
        "winning_stage": _winning_stage(explain),
    }


def main() -> None:
    """Run all benchmarks and write console, CSV, and Plotly reports."""
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    print(
        "Note: MongoDB does not allow hint($natural) with $text; "
        "the text-search scan baseline uses an equivalent regex query."
    )
    results: list[dict[str, Any]] = []
    for name, specification in QUERIES.items():
        for forced_scan in (True, False):
            results.append(benchmark_query(name, specification, forced_scan))

    fieldnames = [
        "query",
        "mode",
        "average_ms",
        "totalDocsExamined",
        "nReturned",
        "winning_stage",
    ]
    print(f"Benchmark results ({RUNS} runs per query/mode)")
    print("-" * 112)
    print(
        f"{'Query':<28} {'Mode':<28} {'Avg ms':>10} "
        f"{'Docs examined':>15} {'Returned':>10} {'Stage':>12}"
    )
    print("-" * 112)
    for row in results:
        print(
            f"{row['query']:<28} {row['mode']:<28} {row['average_ms']:>10.3f} "
            f"{row['totalDocsExamined']:>15} {row['nReturned']:>10} "
            f"{row['winning_stage']:>12}"
        )

    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    frame = pd.DataFrame(results)
    figure = px.bar(
        frame,
        x="query",
        y="average_ms",
        color="mode",
        barmode="group",
        title=f"MongoDB query benchmark ({RUNS} runs per mode)",
        labels={"average_ms": "Average time (ms)", "query": "Query"},
    )
    figure.write_html(OUTPUT_HTML)
    print(f"\nSaved CSV: {OUTPUT_CSV}")
    print(f"Saved chart: {OUTPUT_HTML}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: benchmark failed: {exc}", file=sys.stderr)
        raise
