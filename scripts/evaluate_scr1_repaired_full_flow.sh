#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

design="scr1_core_tuned"
native="results/${design}_tritonpart_design_timing_aware/tritonpart_design_timing_aware_assignment.csv"
repaired="results/${design}_baseline_feasibility_restoration/guarded/restored_assignment.csv"
features="results/${design}_features"
timing_scores="${features}/timing_context_scores.csv"
timing_report="results/timing_reports/${design}_report_checks_max.rpt"
scenarios=(control_datapath_split memory_near_logic state_and_clock_protected)

python3 -m py_compile \
  evaluation/evaluate_scr1_repaired_structural_crossing.py \
  scripts/audit_scr1_repaired_full_flow.py

python3 evaluation/evaluate_scr1_repaired_structural_crossing.py

for scenario in "${scenarios[@]}"; do
  off="results/${design}_repaired_context_off/${scenario}/tritonpart_compatible_dynamic_guarded_repair_assignment.csv"
  on="results/${design}_repaired_context_on/${scenario}/tritonpart_compatible_dynamic_guarded_repair_assignment.csv"
  prefix="results/benchmark_summary/${design}_${scenario}_repaired_full_flow"

  python3 evaluation/evaluate_timing_crossing.py \
    --design "${design}" \
    --features-dir "${features}" \
    --timing "${timing_scores}" \
    --assignment "native=${native}" \
    --assignment "repaired=${repaired}" \
    --assignment "context_off=${off}" \
    --assignment "context_on=${on}" \
    --output "${prefix}_timing_crossing.csv"

  python3 evaluation/evaluate_timing_path_cuts.py \
    --design "${design}" \
    --timing-report "${timing_report}" \
    --max-paths 100 \
    --assignment "native=${native}" \
    --assignment "repaired=${repaired}" \
    --assignment "context_off=${off}" \
    --assignment "context_on=${on}" \
    --output "${prefix}_path_cuts.csv"
done

python3 scripts/audit_scr1_repaired_full_flow.py

if ! git diff --quiet paper-v1.7...HEAD -- paper/ || ! git diff --quiet -- paper/; then
  echo "paper/ changed during SCR1 evaluation" >&2
  exit 2
fi

