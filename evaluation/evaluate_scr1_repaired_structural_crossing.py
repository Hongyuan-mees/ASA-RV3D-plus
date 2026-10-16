#!/usr/bin/env python3
"""Evaluate SCR1 Native, Repaired, Context-OFF, and Context-ON assignments."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.evaluate_architecture_structural_crossing import (  # noqa: E402
    load_context_units,
    summarize_assignment,
    write_csv,
)


SCENARIOS = (
    "control_datapath_split",
    "memory_near_logic",
    "state_and_clock_protected",
)


def reduction(before: float, after: float) -> float:
    return (before - after) / before if before else 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path("results/benchmark_summary/scr1_repaired_full_flow_structural_summary.csv"),
    )
    parser.add_argument(
        "--rollup",
        type=Path,
        default=Path("results/benchmark_summary/scr1_repaired_full_flow_structural_rollup.csv"),
    )
    args = parser.parse_args()

    root = args.root
    design = "scr1_core_tuned"
    features = root / "results" / f"{design}_features" / "instance_features.csv"
    context_units = load_context_units(
        root / "results" / f"{design}_features" / "timing_context_scores.csv"
    )
    native = (
        root
        / "results"
        / f"{design}_tritonpart_design_timing_aware"
        / "tritonpart_design_timing_aware_assignment.csv"
    )
    repaired = (
        root
        / "results"
        / f"{design}_baseline_feasibility_restoration"
        / "guarded"
        / "restored_assignment.csv"
    )

    rows: list[dict[str, object]] = []
    rollup: list[dict[str, object]] = []
    for scenario in SCENARIOS:
        assignments = {
            "native": native,
            "repaired": repaired,
            "context_off": (
                root
                / "results"
                / f"{design}_repaired_context_off"
                / scenario
                / "tritonpart_compatible_dynamic_guarded_repair_assignment.csv"
            ),
            "context_on": (
                root
                / "results"
                / f"{design}_repaired_context_on"
                / scenario
                / "tritonpart_compatible_dynamic_guarded_repair_assignment.csv"
            ),
        }
        missing = [str(path) for path in assignments.values() if not path.is_file()]
        if missing:
            raise SystemExit("missing assignment(s): " + ", ".join(missing))

        scenario_rows = {
            case: summarize_assignment(
                design=design,
                scenario=scenario,
                case=case,
                assignment=path,
                features=features,
                context_units=context_units,
            )
            for case, path in assignments.items()
        }
        rows.extend(scenario_rows.values())

        raw = {case: float(row["structural_crossing_nets"]) for case, row in scenario_rows.items()}
        sensitive = {
            case: float(row["scenario_sensitive_crossing_nets"])
            for case, row in scenario_rows.items()
        }
        rollup.append(
            {
                "design": design,
                "scenario": scenario,
                "native_raw_crossing_nets": f"{raw['native']:.0f}",
                "repaired_raw_crossing_nets": f"{raw['repaired']:.0f}",
                "context_off_raw_crossing_nets": f"{raw['context_off']:.0f}",
                "context_on_raw_crossing_nets": f"{raw['context_on']:.0f}",
                "restoration_raw_cut_regret_vs_native": f"{(raw['repaired'] - raw['native']) / raw['native'] if raw['native'] else 0.0:.6f}",
                "context_off_raw_cut_regret_vs_native": f"{(raw['context_off'] - raw['native']) / raw['native'] if raw['native'] else 0.0:.6f}",
                "context_on_raw_cut_regret_vs_native": f"{(raw['context_on'] - raw['native']) / raw['native'] if raw['native'] else 0.0:.6f}",
                "native_sensitive_crossing_nets": f"{sensitive['native']:.0f}",
                "repaired_sensitive_crossing_nets": f"{sensitive['repaired']:.0f}",
                "context_off_sensitive_crossing_nets": f"{sensitive['context_off']:.0f}",
                "context_on_sensitive_crossing_nets": f"{sensitive['context_on']:.0f}",
                "context_off_sensitive_reduction_vs_repaired": f"{reduction(sensitive['repaired'], sensitive['context_off']):.6f}",
                "context_on_sensitive_reduction_vs_repaired": f"{reduction(sensitive['repaired'], sensitive['context_on']):.6f}",
                "context_on_sensitive_reduction_vs_native": f"{reduction(sensitive['native'], sensitive['context_on']):.6f}",
                "context_gain_vs_off": f"{reduction(sensitive['context_off'], sensitive['context_on']):.6f}",
                "context_gain_defined": str(sensitive["context_off"] > 0.0).lower(),
            }
        )

    write_csv(root / args.summary, rows)
    write_csv(root / args.rollup, rollup)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

