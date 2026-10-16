#!/usr/bin/env python3
"""Audit completed SCR1 repaired-start runs and their guard provenance."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path


SCENARIOS = (
    "control_datapath_split",
    "memory_near_logic",
    "state_and_clock_protected",
)
MODES = ("context_off", "context_on")
NATIVE = Path(
    "results/scr1_core_tuned_tritonpart_design_timing_aware/"
    "tritonpart_design_timing_aware_assignment.csv"
)
REPAIRED = Path(
    "results/scr1_core_tuned_baseline_feasibility_restoration/guarded/"
    "restored_assignment.csv"
)


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        fail(f"missing file: {path}")
    return list(csv.DictReader(path.open(newline="", encoding="utf-8")))


def close(actual: float, expected: float, tolerance: float = 1e-6) -> bool:
    return math.isclose(actual, expected, rel_tol=0.0, abs_tol=tolerance)


def audit_case(scenario: str, mode: str) -> dict[str, object]:
    output = Path(f"results/scr1_core_tuned_repaired_{mode}") / scenario
    summary_path = output / "tritonpart_compatible_dynamic_guarded_repair_summary.csv"
    trace_path = output / "tritonpart_compatible_dynamic_guarded_repair_trace.csv"
    assignment_path = output / "tritonpart_compatible_dynamic_guarded_repair_assignment.csv"
    manifest_path = output / "resume_manifest.json"

    summary_rows = read_rows(summary_path)
    if len(summary_rows) != 1:
        fail(f"expected one summary row: {summary_path}")
    row = summary_rows[0]
    trace = read_rows(trace_path)
    if not assignment_path.is_file() or not manifest_path.is_file():
        fail(f"incomplete output: {output}")

    expected = {
        "scenario": scenario,
        "initial_assignment_file": str(REPAIRED),
        "guard_reference_assignment_file": str(NATIVE),
        "initial_area_balance_pass": "true",
        "final_area_balance_pass": "true",
        "initial_crossing_nets": "276",
        "baseline_crossing_nets": "272",
        "baseline_P_avg_cut": "0.000000",
        "baseline_P_wst_cut": "0.000000",
    }
    for key, value in expected.items():
        if row.get(key) != value:
            fail(f"{mode}/{scenario} {key}: {row.get(key)!r} != {value!r}")

    moves = int(row["accepted_moves"])
    if len(trace) != moves:
        fail(f"{mode}/{scenario} trace rows {len(trace)} != accepted moves {moves}")
    if float(row["cut_regret"]) > 0.05 + 1e-12:
        fail(f"{mode}/{scenario} final raw-cut guard failed")
    if float(row["P_avg_cut_regret"]) > 0.0 or float(row["P_wst_cut_delta"]) > 0.0:
        fail(f"{mode}/{scenario} final path guard failed")
    if not 0.48 <= float(row["final_tier0_area_fraction"]) <= 0.52:
        fail(f"{mode}/{scenario} final area guard failed")

    previous_iteration = 0
    for trace_row in trace:
        iteration = int(trace_row["iteration"])
        if iteration <= previous_iteration:
            fail(f"{mode}/{scenario} trace iterations are not increasing")
        previous_iteration = iteration
        if float(trace_row["cut_regret_after"]) > 0.05 + 1e-12:
            fail(f"{mode}/{scenario} trace raw-cut guard failed at iteration {iteration}")
        area = float(trace_row["tier0_area_fraction_after"])
        if not 0.48 <= area <= 0.52:
            fail(f"{mode}/{scenario} trace area guard failed at iteration {iteration}")
        if float(trace_row["P_avg_cut_after"]) > 0.0 or float(trace_row["P_wst_cut_after"]) > 0.0:
            fail(f"{mode}/{scenario} trace path guard failed at iteration {iteration}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("original_initial_assignment") != str(REPAIRED):
        fail(f"{mode}/{scenario} manifest initial assignment mismatch")
    if manifest.get("guard_reference_assignment") != str(NATIVE):
        fail(f"{mode}/{scenario} manifest guard reference mismatch")

    return {
        "design": "scr1_core_tuned",
        "scenario": scenario,
        "mode": mode,
        "status": "pass",
        "accepted_moves": moves,
        "objective_reduction": row["objective_reduction"],
        "native_crossing_nets": row["baseline_crossing_nets"],
        "repaired_crossing_nets": row["initial_crossing_nets"],
        "final_crossing_nets": row["final_crossing_nets"],
        "raw_cut_regret_vs_native": row["cut_regret"],
        "initial_tier0_area_fraction": row["initial_tier0_area_fraction"],
        "final_tier0_area_fraction": row["final_tier0_area_fraction"],
        "P_avg_cut_regret_vs_native": row["P_avg_cut_regret"],
        "P_wst_cut_delta_vs_native": row["P_wst_cut_delta"],
        "stopped_no_legal_move": row["stopped_no_legal_move"],
        "stopped_converged": row["stopped_converged"],
        "summary_file": str(summary_path),
        "trace_file": str(trace_path),
        "assignment_file": str(assignment_path),
    }


def audit_independent_path_outputs() -> None:
    for scenario in SCENARIOS:
        path = Path(
            f"results/benchmark_summary/scr1_core_tuned_{scenario}_"
            "repaired_full_flow_path_cuts.csv"
        )
        rows = read_rows(path)
        cases = {row["case"]: row for row in rows}
        if set(cases) != {"native", "repaired", "context_off", "context_on"}:
            fail(f"unexpected path cases in {path}: {sorted(cases)}")
        for case, row in cases.items():
            if not close(float(row["P_avg_cut"]), 0.0) or not close(float(row["P_wst_cut"]), 0.0):
                fail(f"independent path guard failed for {scenario}/{case}")


def main() -> int:
    rows = [audit_case(scenario, mode) for scenario in SCENARIOS for mode in MODES]
    if len(rows) != 6:
        fail(f"expected six cases, found {len(rows)}")

    structural = read_rows(
        Path("results/benchmark_summary/scr1_repaired_full_flow_structural_rollup.csv")
    )
    if len(structural) != 3:
        fail(f"expected three structural rollup rows, found {len(structural)}")
    for row in structural:
        for key in ("context_off_raw_cut_regret_vs_native", "context_on_raw_cut_regret_vs_native"):
            if float(row[key]) > 0.05 + 1e-12:
                fail(f"structural raw-cut guard failed for {row['scenario']}/{key}")

    audit_independent_path_outputs()

    output = Path("results/benchmark_summary/scr1_repaired_full_flow_audit.csv")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(output)
    print("SCR1 repaired full-flow audit: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

