# ASA-RV3D

**ASA-RV3D** is a constrained post-partition refinement framework for two-tier RISC-V gate-level partitioning. It starts from a native timing-aware TritonPart assignment and explores local instance moves using normalized physical and timing information, with recovered RISC-V design context introduced as an optional guidance term.

The method is designed to improve a strong timing-aware baseline without discarding the properties already established by the underlying partitioner. Candidate moves are accepted only when they satisfy explicit area, raw-cut, and timing-path feasibility guards.

This is the extended research repository for ASA-RV3D. It preserves the primary PicoRV32/riscv32i results reported in the manuscript and adds the SCR1 feasibility-restoration and full-flow refinement results. All three designs are presented together in the unified results table below; the six manuscript-reported rows remain identifiable, while the SCR1 rows document subsequent work without changing the frozen manuscript snapshot under `paper/`. The separate paper-version repository is [ASA-RV3D](https://github.com/Hongyuan-mees/ASA-RV3D).

---

## Results at a Glance

The unified table below brings together nine design-scenario rows: the six primary manuscript results for PicoRV32 and riscv32i, plus three subsequent SCR1 full-flow rows. In the six manuscript rows, Context-ON reduces scenario-sensitive crossings in five cases; PicoRV32 control/datapath remains the negative case (`-11.2%`). The SCR1 rows extend the evaluation to a mildly area-infeasible native assignment and show both the feasibility-restoration step and the subsequent Context-OFF / Context-ON refinement. They do not change the frozen manuscript results under `paper/`.

For SCR1, guarded restoration moves five instances to bring the reconstructed tier-0 area fraction from `0.520588` to `0.519990`, while keeping raw-cut regret at `1.47%` relative to Native. The six subsequent refinement runs end at `285` raw crossings (`4.78%` regret against the original Native assignment) and pass the recorded area, raw-cut, and path guards. The detailed per-scenario results are included in the same table as the earlier designs below.

---

## Method Overview

ASA-RV3D operates after native timing-aware TritonPart partitioning. Before local refinement, the imported assignment is checked under the reconstructed OpenROAD-area criterion. An assignment that already satisfies the area window proceeds directly to refinement. For a mildly infeasible imported assignment, ASA-RV3D can optionally apply a scenario-independent guarded feasibility-restoration stage before the normal refinement flow.

```text
Native timing-aware TritonPart assignment
        |
        v
Reconstructed-area feasibility check
        |
        +-- feasible -----------------------------+
        |                                        |
        +-- mildly infeasible                     |
                |                                 |
                v                                 |
        Guarded feasibility restoration           |
                |                                 |
                +---------------------------------+
                                                  |
                                                  v
Gate-level + physical + timing information
        |
        v
Normalized instance-level refinement weights
        |
        v
Risk-weighted local move evaluation
        |
        v
Area / raw-cut / timing-path feasibility guards
        |
        v
Greedy constrained refinement
        |
        v
Refined two-tier assignment
```

The feasibility-restoration stage is deliberately separate from the normal ASA-RV3D refinement objective. It moves instances only from the overloaded tier toward the underloaded tier, stops as soon as the reconstructed area fraction enters the feasible interval, and does not use recovered design-context information.

For each movable instance during normal refinement, ASA-RV3D combines three normalized components:

- recovered RISC-V design context;
- physical context derived from OpenROAD artifacts;
- timing context derived from OpenSTA/OpenROAD information.

Two controlled configurations are used in the paper:

- **Context-OFF** retains the physical and timing components while disabling recovered design context;
- **Context-ON** enables all three components under the same feasibility guards.

The recovered design context is used as soft guidance rather than as a hard architectural partitioning constraint.

A longer paper-facing method note is available at:

```text
docs/method.md
```

---

## Refinement Constraints

A locally improving move is accepted only when it remains feasible with respect to the original native timing-aware TritonPart assignment.

The paper uses the following settings:

- reconstructed tier-0 area fraction: **0.48-0.52**;
- maximum raw-crossing regret: **5%**;
- OpenSTA maximum-delay paths: up to **100**;
- mean tier-transition regret limit: **0**;
- worst tier-transition increase limit: **0**;
- maximum refinement budget: **300 iterations**;
- convergence window: **10 accepted moves**;
- minimum recent relative gain: **1e-3**.

For an imported assignment outside the reconstructed area window, the optional feasibility-restoration stage first moves the assignment into the feasible interval while enforcing the same raw-cut and timing-path guard limits. The **original native TritonPart assignment remains the reference for these guard budgets after restoration**; the restoration step does not reset the raw-cut or timing-path allowance before subsequent refinement.

For an already feasible imported assignment, the restoration stage is a strict no-op. This behavior is verified on PicoRV32 and riscv32i in the retained restoration regression artifacts.

The completed SCR1 boundary case demonstrates why this pre-stage is useful: its imported native assignment had a reconstructed tier-0 area fraction of `0.520588`, just above the `0.52` upper bound. Scenario-independent guarded restoration moved five instances and reached `0.519990`; raw crossings changed from `272` to `276`, a `1.47%` regret, while the evaluated mean and worst tier-transition guard deltas remained zero. The subsequent six refinement runs started from this restored assignment but kept the original native assignment as the guard reference. Each finished at `285` raw crossings (`4.78%` regret against Native), below the `5%` ceiling. Thus, the added restoration step makes this mildly infeasible starting point usable without resetting the cut or path budgets; it is not a claim that arbitrary infeasible assignments can always be recovered.

These constraints separate candidate quality from candidate feasibility: the refinement objective ranks local moves, while the guards protect the baseline area, cut, and timing-path properties.

---

## Design Context

The current implementation uses an explainable rule-based recovery procedure to associate synthesized gate-level instances with coarse RISC-V functional units and semantic groups.

The paper evaluates three design-context scenarios:

- **control/datapath**;
- **memory-near-logic**;
- **state/clock**.

These scenarios provide different soft preferences during Context-ON refinement. They do not force complete architectural blocks onto a specific tier.

---

## Benchmark Designs

The following statistics describe the synthesized designs used in the evaluation. PicoRV32 and riscv32i form the primary manuscript comparison; SCR1 is included as an extended boundary-case evaluation.

| Design | Instances | Nets | Reconstructed area (um^2) |
| --- | ---: | ---: | ---: |
| PicoRV32 | 6,779 | 6,868 | 95,512 |
| riscv32i | 5,737 | 5,819 | 76,420 |
| SCR1 (`scr1_core_tuned`) | 23,254 | 24,875 | 227,377 |

SCR1's design statistics are taken from `results/scr1_core_tuned_features/manifest.json`. Its feasibility-restoration record is retained in `paper/scr1_feasibility_restoration.csv`, and the subsequent full-flow results are included in the unified partition-results table below. The SCR1 extension does not change the frozen manuscript comparison.

---

## Partition Results Across Designs and Scenarios

`R/S` denotes raw / scenario-sensitive crossing nets. `Restored R/S` is the assignment after the optional guarded feasibility-restoration stage. For PicoRV32 and riscv32i, restoration is a strict no-op, so this column matches Native. The first six rows are the manuscript-reported comparison; the three SCR1 rows are the subsequent full-flow extension and do not alter the frozen manuscript tables.

| Design | Scenario | Native R/S | Restored R/S | Context-OFF R/S | Context-ON R/S | Context gain |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| PicoRV32 | control/datapath | 346 / 205 | 346 / 205 | 207 / 116 | 217 / 129 | -11.2% |
| PicoRV32 | memory-near-logic | 346 / 157 | 346 / 157 | 207 / 95 | 202 / 88 | +7.4% |
| PicoRV32 | state/clock | 346 / 211 | 346 / 211 | 207 / 98 | 214 / 90 | +8.2% |
| riscv32i | control/datapath | 230 / 119 | 230 / 119 | 229 / 126 | 241 / 116 | +7.9% |
| riscv32i | memory-near-logic | 230 / 104 | 230 / 104 | 229 / 105 | 226 / 96 | +8.6% |
| riscv32i | state/clock | 230 / 97 | 230 / 97 | 229 / 72 | 241 / 58 | +19.4% |
| scr1_core_tuned | control/datapath | 272 / 136 | 276 / 136 | 285 / 143 | 285 / 142 | +0.7% |
| scr1_core_tuned | memory-near-logic | 272 / 0 | 276 / 0 | 285 / 0 | 285 / 0 | N/A |
| scr1_core_tuned | state/clock | 272 / 35 | 276 / 39 | 285 / 39 | 285 / 37 | +5.1% |

Context gain is the percentage reduction in scenario-sensitive crossings from Context-OFF to Context-ON. Positive values indicate fewer scenario-sensitive crossings after enabling recovered design context; it is undefined when the Context-OFF scenario-sensitive count is zero.

Across the six manuscript rows, Context-ON produces positive context gain in five cases. The PicoRV32 control/datapath case remains a negative case, demonstrating that recovered design context is not universally beneficial. In SCR1, Context-ON reduces scenario-sensitive crossings relative to Context-OFF by `0.7%` for control/datapath and `5.1%` for state/clock, while memory-near-logic has zero scenario-sensitive crossings in both modes. These are gains relative to Context-OFF, not improvements over Native: SCR1's refined scenario-sensitive counts remain above Native for control/datapath and state/clock.

All six SCR1 refinement runs (three scenarios times Context-OFF / Context-ON) passed the recorded guards and accepted 39-40 moves. Each ends at `285` raw crossings, or `4.78%` regret against the original Native assignment; final reconstructed tier-0 area fractions remain within `0.48-0.52`, and the evaluated mean and worst tier-transition guard deltas remain zero. The raw-crossing count is a feasibility guard, not the quantity directly minimized by the normalized refinement objective, so an objective-improving move can increase raw crossings while remaining admissible.

The machine-readable manuscript snapshot remains at `paper/table2_partition_results.csv`. Additional SCR1 traces, assignments, and audits are retained under `results/scr1_core_tuned_repaired_context_off/`, `results/scr1_core_tuned_repaired_context_on/`, and `results/benchmark_summary/scr1_repaired_full_flow_*.csv`.

---

## Path-Level Validation

ASA-RV3D is additionally evaluated using an independent downstream proxy based on OpenSTA maximum-delay paths and fixed vertical-link delays of 20, 50, and 100 ps.

For PicoRV32, the evaluated path-level behavior is unchanged by refinement.

For riscv32i, Context-OFF and Context-ON both reduce the mean tier-transition count from **0.41 to 0.35** and the maximum observed transition count from **2 to 1**. The total negative slack degradation proxy is also lower than the native baseline under all evaluated vertical-delay assumptions.

The identical Context-OFF and Context-ON path-level results indicate that this path-continuity benefit comes from constrained refinement rather than from the additional design-context term.

The corresponding manuscript-facing data for PicoRV32 and riscv32i are stored at:

```text
paper/table3_path_validation.csv
```

For SCR1, the selected 100 OpenSTA maximum-delay paths belong to the `asynchronous` path group and contain no tier transitions in any of the four assignments. The unchanged mean and worst path-cut metrics establish guard compliance for this evaluated path set only; they do not establish synchronous critical-path improvement or signoff-quality 3-D timing behavior. The SCR1 path-cut outputs are retained as `results/benchmark_summary/scr1_core_tuned_*_repaired_full_flow_path_cuts.csv`.

The vertical-delay study is a validation proxy and is not a replacement for full post-refinement 3-D routing or signoff timing analysis.
---

## Repository Layout## Repository Layout

```text
classifier/    Rule-based RISC-V design-context recovery.
configs/       Design and scenario configurations.
partition/     TritonPart-compatible refinement algorithms.
evaluation/    Metric extraction and evaluation scripts.
scripts/       Experiment and reproduction utilities.
results/       Generated and historical experiment artifacts.
docs/          Additional method notes and archived development documentation.
paper/         Frozen paper-facing tables and artifact manifest.
```

Historical files under `results/` and `docs/archive/` may contain intermediate algorithm variants or earlier terminology. Use this README and `docs/method.md` for the current extended research method and scope. Files under `paper/` are a frozen manuscript snapshot; the subsequent SCR1 full-flow extension is documented in the SCR1 section above and in `results/benchmark_summary/`.

---

## Reproduction

The principal refinement implementation is:

```text
partition/partition_tritonpart_compatible_normalized_dynamic_guarded_repair.py
```

After the OpenROAD/OpenSTA features and the native timing-aware TritonPart assignment are available, a representative refinement run is:

```bash
python3 partition/partition_tritonpart_compatible_normalized_dynamic_guarded_repair.py \
  --design picorv32 \
  --scenario state_and_clock_protected \
  --initial-assignment results/picorv32_tritonpart_design_timing_aware/tritonpart_design_timing_aware_assignment.csv \
  --features-dir results/picorv32_features \
  --instance-area results/benchmark_summary/picorv32_openroad_instance_area.csv \
  --timing-report results/timing_reports/picorv32_report_checks_max.rpt \
  --max-paths 100 \
  --max-iterations 300 \
  --max-cut-regret 0.05 \
  --max-pavg-regret 0.0 \
  --max-pwst-delta 0.0 \
  --convergence-window 10 \
  --min-relative-gain 0.001 \
  --output-dir results/picorv32_refinement/state_and_clock_protected
```

The paper-facing snapshot can be checked with:

```bash
python3 scripts/audit_paper_snapshot.py
```

Repository-level summaries and consistency checks can be refreshed using:

```bash
bash scripts/reproduce_core_results.sh
```

The optional native-baseline feasibility-restoration study can be reproduced separately. To refresh the native-baseline feasibility audit only, run:

```bash
bash scripts/run_baseline_feasibility_restoration.sh audit
```

To rerun the SCR1 feasibility restoration under the retained area, raw-cut, and timing-path guards, run:

```bash
bash scripts/run_baseline_feasibility_restoration.sh restore
```

The strict no-op regression on the already feasible PicoRV32 and riscv32i native assignments can be checked with:

```bash
bash scripts/run_baseline_restoration_noop_regression.sh
```

The frozen manuscript-facing SCR1 restoration values remain those recorded in:

```text
paper/scr1_feasibility_restoration.csv
```

To reproduce the subsequent SCR1 repaired-start refinement, first run the smoke and resume checks, then the three-scenario Context-OFF / Context-ON evaluation:

```bash
bash scripts/run_scr1_repaired_full_flow.sh smoke control_datapath_split both
bash scripts/run_scr1_repaired_full_flow.sh formal all both
bash scripts/evaluate_scr1_repaired_full_flow.sh
python3 scripts/audit_scr1_repaired_full_flow.py
```

The full-flow runner uses the restored SCR1 assignment as `--initial-assignment` and explicitly supplies the original native assignment through `--guard-reference-assignment`. Its outputs are written under `results/scr1_core_tuned_repaired_context_off/`, `results/scr1_core_tuned_repaired_context_on/`, and `results/benchmark_summary/`; the manuscript-facing files under `paper/` are not updated. Details and input prerequisites are given in `docs/reproduction-guide.md`.

Large OpenROAD physical-design artifacts such as ODB, GDS, SPEF, and full run logs are not committed to the repository.

---

## Scope and Limitations

ASA-RV3D is an early-stage two-tier partition-refinement research prototype, not a complete 3-D physical-design implementation.

The repository does not claim:

- signoff 3-D placement and routing;
- explicit TSV or hybrid-bonding insertion;
- extracted post-3-D parasitics;
- thermal or IR-drop closure;
- final routed 3-D PPA.

The vertical-link-delay study and crossing metrics should therefore be interpreted as controlled partition-level and path-level proxies.

The design-context recovery is rule-based and explainable; it is not a trained machine-learning classifier.

The feasibility-restoration extension is demonstrated on **one mildly infeasible imported baseline**. The SCR1 example shows that this assignment can be moved back inside the reconstructed area window while preserving the original raw-cut and timing-path guard budgets; it does not establish that arbitrary or severely imbalanced native assignments can always be recovered.

## Frozen Manuscript Snapshot

The manuscript-facing snapshot is frozen under:

```text
paper/
```

See:

```text
paper/artifact_manifest.md
paper/table2_partition_results.csv
paper/table3_path_validation.csv
paper/scr1_feasibility_restoration.csv
```

`table2_partition_results.csv` and `table3_path_validation.csv` retain the primary PicoRV32 and riscv32i comparison. `scr1_feasibility_restoration.csv` separately records the SCR1 boundary-case restoration snapshot and does not change the six-case Context-OFF / Context-ON comparison.

These files provide the explicit mapping between the public repository and the values reported in the manuscript.

## Citation

If you use ASA-RV3D in academic work, please cite the associated manuscript and repository:

```bibtex
@misc{duan2026asarv3d,
  author = {Hongyuan Duan},
  title  = {Constrained Post-Partition Refinement for RISC-V 3-D Tier Partitioning},
  year   = {2026},
  note   = {Manuscript and open-source implementation},
  url    = {https://github.com/Hongyuan-mees/ASA-RV3D}
}
```

Publication metadata will be updated after the paper is formally published.

---

## License

ASA-RV3D is released under the BSD 3-Clause License. See `LICENSE` for details.
