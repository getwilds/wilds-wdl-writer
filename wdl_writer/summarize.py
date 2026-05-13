#!/usr/bin/env python3
"""Merge per-model benchmark JSONs and emit a markdown summary.

Reads one or more results JSONs (each a list of {model, tier, cases, avg_pass_rate}
records produced by benchmarking.py) and writes:
- combined_summary.json: flat concatenation, one record per (model, tier)
- combined_summary.md: human-readable tables (model x tier grid + per-case breakdown)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_records(paths: list[str]) -> list[dict]:
    combined = []
    for p in paths:
        with open(p) as f:
            combined.extend(json.load(f))
    return combined


def format_pct(rate: float) -> str:
    return f"{rate:.0%}"


def format_pair(rec: dict | None) -> str:
    """Render a cell as 'first → final' if retries happened, else just 'final'."""
    if rec is None:
        return "—"
    final = rec["avg_pass_rate"]
    first = rec.get("avg_first_attempt_pass_rate", final)
    return format_pct(final) if first == final else f"{format_pct(first)} → {format_pct(final)}"


def format_case_pair(case: dict) -> str:
    final = case["pass_rate"]
    first = case.get("first_attempt_pass_rate", final)
    return format_pct(final) if first == final else f"{format_pct(first)} → {format_pct(final)}"


TIER_ORDER = ["raw", "spec", "spec_plus_example", "spec_plus_wilds", "full"]


def render_markdown(records: list[dict]) -> str:
    models = sorted({r["model"] for r in records})
    present_tiers = {r["tier"] for r in records}
    # Keep canonical order for known tiers, append any unknowns at the end
    tiers = [t for t in TIER_ORDER if t in present_tiers]
    tiers += sorted(present_tiers - set(TIER_ORDER))
    case_ids = sorted({c["id"] for r in records for c in r["cases"]})

    by_key = {(r["model"], r["tier"]): r for r in records}
    has_retry = any("avg_first_attempt_pass_rate" in r for r in records)

    out = ["# WDL Generation Benchmark — Summary", ""]
    out.append(f"Models: {len(models)} | Tiers: {len(tiers)} | Cases: {len(case_ids)}")
    if has_retry:
        out.append("")
        out.append("Cells show `first_attempt → final` pass rate when retries changed the outcome, else just the final rate.")
    out.append("")

    # Headline: model x tier grid of avg pass rates
    out.append("## Average pass rate by model and tier")
    out.append("")
    header = ["Model"] + tiers
    out.append("| " + " | ".join(header) + " |")
    out.append("|" + "|".join(["---"] * len(header)) + "|")
    for model in models:
        row = [model]
        for tier in tiers:
            row.append(format_pair(by_key.get((model, tier))))
        out.append("| " + " | ".join(row) + " |")
    out.append("")

    # Best (model, tier)
    best = max(records, key=lambda r: r["avg_pass_rate"])
    out.append(f"**Best:** `{best['model']}` @ `{best['tier']}` — {format_pct(best['avg_pass_rate'])}")
    out.append("")

    # Per-case breakdown, one table per model
    out.append("## Per-case breakdown")
    out.append("")
    for model in models:
        out.append(f"### {model}")
        out.append("")
        header = ["Tier"] + case_ids + ["Avg"]
        out.append("| " + " | ".join(header) + " |")
        out.append("|" + "|".join(["---"] * len(header)) + "|")
        for tier in tiers:
            rec = by_key.get((model, tier))
            if not rec:
                continue
            cases_by_id = {c["id"]: c for c in rec["cases"]}
            row = [tier]
            for cid in case_ids:
                row.append(format_case_pair(cases_by_id[cid]) if cid in cases_by_id else "—")
            row.append(format_pair(rec))
            out.append("| " + " | ".join(row) + " |")
        out.append("")

    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description="Summarize benchmark results")
    parser.add_argument("inputs", nargs="+", help="Per-model results JSON files")
    parser.add_argument("--json-out", default="combined_summary.json")
    parser.add_argument("--md-out", default="combined_summary.md")
    args = parser.parse_args()

    records = load_records(args.inputs)

    Path(args.json_out).write_text(json.dumps(records, indent=2))
    Path(args.md_out).write_text(render_markdown(records))

    print(f"Merged {len(args.inputs)} model result files -> {len(records)} (model, tier) records")
    print(f"Wrote {args.json_out} and {args.md_out}")


if __name__ == "__main__":
    main()
