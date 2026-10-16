#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

phase="${1:-smoke}"
scenario_filter="${2:-control_datapath_split}"
mode_filter="${3:-both}"

native_assignment="results/scr1_core_tuned_tritonpart_design_timing_aware/tritonpart_design_timing_aware_assignment.csv"
restored_assignment="results/scr1_core_tuned_baseline_feasibility_restoration/guarded/restored_assignment.csv"
restoration_summary="results/benchmark_summary/scr1_core_tuned_feasibility_restoration_summary.csv"
features_dir="results/scr1_core_tuned_features"
area_csv="results/benchmark_summary/scr1_core_tuned_openroad_instance_area.csv"
timing_report="results/timing_reports/scr1_core_tuned_report_checks_max.rpt"

scenarios=(control_datapath_split memory_near_logic state_and_clock_protected)
modes=(context_on context_off)

if [[ "${phase}" != "smoke" && "${phase}" != "formal" ]]; then
  echo "usage: $0 {smoke|formal} [scenario|all] [context_on|context_off|both]" >&2
  exit 2
fi
if [[ "${phase}" == "smoke" && ( "${scenario_filter}" == "all" || "${mode_filter}" != "both" ) ]]; then
  echo "smoke requires one explicit scenario and mode=both" >&2
  exit 2
fi

require_file() {
  if [[ ! -s "$1" ]]; then
    echo "missing required file: $1" >&2
    exit 2
  fi
}

check_paper_unchanged() {
  if ! git diff --quiet -- paper/; then
    echo "paper/ has uncommitted changes; refusing to run" >&2
    exit 2
  fi
  if git rev-parse --verify paper-v1.7 >/dev/null 2>&1 && \
     ! git diff --quiet paper-v1.7...HEAD -- paper/; then
    echo "paper/ differs from paper-v1.7; refusing to run" >&2
    exit 2
  fi
}

verify_restoration() {
  require_file "${native_assignment}"
  require_file "${restored_assignment}"
  require_file "${restoration_summary}"
  python3 - "${restoration_summary}" <<'PY'
import csv
import math
import sys
from pathlib import Path

path = Path(sys.argv[1])
rows = list(csv.DictReader(path.open(newline="", encoding="utf-8")))
row = next((item for item in rows if item.get("policy") == "guarded"), None)
if row is None:
    raise SystemExit("guarded restoration row is missing")

expected = {
    "status": "restored_guarded",
    "reconstructed_area_pass": "true",
    "moved_instances": "5",
    "baseline_crossing_nets": "272",
    "final_crossing_nets": "276",
    "guard_status": "pass",
}
for key, value in expected.items():
    if row.get(key) != value:
        raise SystemExit(f"restoration mismatch for {key}: {row.get(key)!r} != {value!r}")

numeric = {
    "baseline_tier0_area_fraction": 0.520588,
    "final_tier0_area_fraction": 0.519990,
    "cut_regret": 0.014706,
    "P_avg_cut_regret": 0.0,
    "P_wst_cut_delta": 0.0,
}
for key, value in numeric.items():
    actual = float(row[key])
    if not math.isclose(actual, value, rel_tol=0.0, abs_tol=1e-6):
        raise SystemExit(f"restoration mismatch for {key}: {actual} != {value}")

print("restoration check: OK")
PY
}

run_restoration() {
  echo "== regenerate guarded SCR1 restoration from Native =="
  bash scripts/run_baseline_feasibility_restoration.sh restore
  verify_restoration
  sha256sum "${native_assignment}" "${restored_assignment}"
}

run_refinement() {
  local scenario="$1"
  local mode="$2"
  local output_dir="$3"
  local max_iterations="$4"
  local checkpoint_every="$5"
  local resume_manifest="${6:-}"
  local mode_flag=()
  local resume_flag=()

  if [[ "${mode}" == "context_off" ]]; then
    mode_flag=(--architecture-off)
  fi
  if [[ -n "${resume_manifest}" ]]; then
    resume_flag=(--resume-from "${resume_manifest}")
  fi

  mkdir -p "${output_dir}"
  python3 -u partition/partition_tritonpart_compatible_normalized_dynamic_guarded_repair.py \
    "${mode_flag[@]}" \
    "${resume_flag[@]}" \
    --design scr1_core_tuned \
    --scenario "${scenario}" \
    --initial-assignment "${restored_assignment}" \
    --guard-reference-assignment "${native_assignment}" \
    --features-dir "${features_dir}" \
    --instance-area "${area_csv}" \
    --timing-report "${timing_report}" \
    --max-paths 100 \
    --max-iterations "${max_iterations}" \
    --max-cut-regret 0.05 \
    --max-pavg-regret 0.0 \
    --max-pwst-delta 0.0 \
    --area-lo 0.48 \
    --area-hi 0.52 \
    --lambda-arch 1.0 \
    --lambda-physical 1.0 \
    --lambda-timing 1.0 \
    --checkpoint-every "${checkpoint_every}" \
    --convergence-window 10 \
    --min-relative-gain 0.001 \
    --progress-every-candidates 1000 \
    --validate-incremental \
    --output-dir "${output_dir}"
}

run_smoke() {
  local scenario="$1"
  local mode="$2"
  local output_dir="results/scr1_core_tuned_repaired_smoke_${mode}/${scenario}"
  local manifest="${output_dir}/resume_manifest.json"
  local summary="${output_dir}/tritonpart_compatible_dynamic_guarded_repair_summary.csv"

  if [[ -s "${summary}" && -s "${manifest}" ]]; then
    echo "smoke output already complete, validate only: ${output_dir}"
    return 0
  fi
  if [[ -d "${output_dir}" && ! -s "${manifest}" ]] && \
     find "${output_dir}" -mindepth 1 -print -quit | grep -q .; then
    echo "partial smoke output without resume manifest: ${output_dir}" >&2
    exit 2
  fi
  mkdir -p "${output_dir}"

  echo "== smoke fresh: ${scenario} / ${mode} =="
  run_refinement "${scenario}" "${mode}" "${output_dir}" 1 1 \
    2>&1 | tee "${output_dir}/fresh_execution.txt"
  require_file "${manifest}"

  echo "== smoke resume: ${scenario} / ${mode} =="
  run_refinement "${scenario}" "${mode}" "${output_dir}" 2 1 "${manifest}" \
    2>&1 | tee "${output_dir}/resume_execution.txt"
}

run_formal() {
  local scenario="$1"
  local mode="$2"
  local output_dir="results/scr1_core_tuned_repaired_${mode}/${scenario}"
  local assignment="${output_dir}/tritonpart_compatible_dynamic_guarded_repair_assignment.csv"
  local summary="${output_dir}/tritonpart_compatible_dynamic_guarded_repair_summary.csv"
  local manifest="${output_dir}/resume_manifest.json"
  local resume=""

  mkdir -p "${output_dir}"
  if [[ -s "${summary}" && -s "${assignment}" ]]; then
    echo "formal output already complete, skip: ${output_dir}"
    return 0
  fi
  if [[ -s "${manifest}" ]]; then
    resume="${manifest}"
    echo "resume formal run: ${manifest}"
  fi

  run_refinement "${scenario}" "${mode}" "${output_dir}" 300 10 "${resume}" \
    2>&1 | tee -a "${output_dir}/execution.txt"
}

check_paper_unchanged
python3 -m py_compile \
  partition/partition_tritonpart_compatible_normalized_dynamic_guarded_repair.py \
  partition/restore_baseline_feasibility.py \
  scripts/audit_scr1_repaired_smoke.py
require_file "${timing_report}"
require_file "${area_csv}"
require_file "${features_dir}/instance_features.csv"
if [[ "${SKIP_RESTORATION:-0}" == "1" ]]; then
  echo "== reuse verified SCR1 restoration =="
  verify_restoration
else
  run_restoration
fi

for scenario in "${scenarios[@]}"; do
  if [[ "${scenario_filter}" != "all" && "${scenario_filter}" != "${scenario}" ]]; then
    continue
  fi
  for mode in "${modes[@]}"; do
    if [[ "${mode_filter}" != "both" && "${mode_filter}" != "${mode}" ]]; then
      continue
    fi
    if [[ "${phase}" == "smoke" ]]; then
      run_smoke "${scenario}" "${mode}"
    else
      run_formal "${scenario}" "${mode}"
    fi
  done
done

if [[ "${phase}" == "smoke" ]]; then
  python3 scripts/audit_scr1_repaired_smoke.py --scenario "${scenario_filter}"
fi
check_paper_unchanged

