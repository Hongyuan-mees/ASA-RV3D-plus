#!/usr/bin/env python3
"""Check SCR1 repaired-start smoke outputs without interpreting research gain."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NATIVE = Path(
    "results/scr1_core_tuned_tritonpart_design_timing_aware/"
    "tritonpart_design_timing_aware_assignment.csv"
)
RESTORED = Path(
    "results/scr1_core_tuned_baseline_feasibility_restoration/guarded/"
    "restored_assignment.csv"
)


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def one_row(path: Path) -> dict[str, str]:
    if not path.is_file():
        fail(f"missing summary: {path}")
    rows = list(csv.DictReader(path.open(newline="", encoding="utf-8")))
    if len(rows) != 1:
        fail(f"expected one summary row in {path}, found {len(rows)}")
    return rows[0]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit_mode(scenario: str, mode: str) -> dict[str, str]:
    output = Path(f"results/scr1_core_tuned_repaired_smoke_{mode}") / scenario
    summary_path = output / "tritonpart_compatible_dynamic_guarded_repair_summary.csv"
    assignment_path = output / "tritonpart_compatible_dynamic_guarded_repair_assignment.csv"
    trace_path = output / "tritonpart_compatible_dynamic_guarded_repair_trace.csv"
    manifest_path = output / "resume_manifest.json"

    row = one_row(summary_path)
    if not assignment_path.is_file() or not trace_path.is_file() or not manifest_path.is_file():
        fail(f"incomplete smoke artifacts under {output}")

    expected_text = {
        "initial_assignment_file": str(RESTORED),
        "guard_reference_assignment_file": str(NATIVE),
        "initial_area_balance_pass": "true",
        "initial_crossing_nets": "276",
        "baseline_crossing_nets": "272",
    }
    for key, expected in expected_text.items():
        if row.get(key) != expected:
            fail(f"{mode}/{scenario} {key}: {row.get(key)!r} != {expected!r}")

    if float(row["cut_regret"]) > 0.05 + 1e-12:
        fail(f"{mode}/{scenario} exceeds raw-cut guard")
    if float(row["P_avg_cut_regret"]) > 0.0:
        fail(f"{mode}/{scenario} exceeds mean path guard")
    if float(row["P_wst_cut_delta"]) > 0.0:
        fail(f"{mode}/{scenario} exceeds worst path guard")
    if row.get("final_area_balance_pass") != "true":
        fail(f"{mode}/{scenario} final area balance failed")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("original_initial_assignment") != str(RESTORED):
        fail(f"{mode}/{scenario} manifest lost repaired start")
    if manifest.get("guard_reference_assignment") != str(NATIVE):
        fail(f"{mode}/{scenario} manifest lost Native guard reference")
    if int(manifest.get("last_completed_iteration", 0)) < 1:
        fail(f"{mode}/{scenario} resume checkpoint was not written")

    return {
        "mode": mode,
        "accepted_moves": row.get("accepted_moves", ""),
        "final_crossing_nets": row.get("final_crossing_nets", ""),
        "cut_regret": row.get("cut_regret", ""),
        "P_avg_cut_regret": row.get("P_avg_cut_regret", ""),
        "P_wst_cut_delta": row.get("P_wst_cut_delta", ""),
        "assignment_sha256": sha256(assignment_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", required=True)
    args = parser.parse_args()

    if args.scenario == "all":
        fail("smoke audit requires one explicit scenario")
    if not NATIVE.is_file() or not RESTORED.is_file():
        fail("Native or restored assignment is missing")

    rows = [audit_mode(args.scenario, mode) for mode in ("context_on", "context_off")]
    if sha256(RESTORED) == sha256(NATIVE):
        fail("restored assignment unexpectedly matches Native byte-for-byte")

    paper_diff = subprocess.run(
        ["git", "diff", "--quiet", "paper-v1.7...HEAD", "--", "paper/"],
        cwd=ROOT,
        check=False,
    )
    if paper_diff.returncode != 0:
        fail("paper/ differs from paper-v1.7")

    output = Path("results/benchmark_summary/scr1_repaired_smoke_audit.csv")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(output)
    print("SCR1 repaired-start smoke audit: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

