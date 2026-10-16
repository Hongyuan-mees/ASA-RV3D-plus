# ASA-RV3D Method

This document describes the paper-facing ASA-RV3D method used by the public artifact. Historical development notes and older algorithm variants are archived under `docs/archive/`.

## Problem Setting

ASA-RV3D operates on a two-tier gate-level partitioning problem. Given a synthesized RISC-V design and a native timing-aware TritonPart assignment, the method performs constrained local refinement over individual instance tier assignments.

The primary refinement flow assumes that the imported assignment satisfies the reconstructed OpenROAD-area window. Because an otherwise usable native assignment may become mildly infeasible under this reconstructed criterion, ASA-RV3D also provides an optional feasibility-restoration pre-stage. This stage is invoked only when the imported assignment lies outside the prescribed area interval; an already feasible assignment proceeds directly to refinement and is left unchanged by restoration.

The goal is not to replace TritonPart or to minimize raw cut count alone. Instead, ASA-RV3D asks whether a strong native timing-aware partition can be locally refined using physical, timing, and optional recovered design-context information while preserving explicit feasibility constraints. The restoration stage serves only to recover the required starting feasibility and does not use recovered design context or replace the normal refinement objective.

## High-Level Flow

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
Gate-level, physical, and timing artifacts
        |
        v
Normalized instance-level refinement weights
        |
        v
Risk-weighted candidate move evaluation
        |
        v
Area / raw-cut / timing-path feasibility guards
        |
        v
Greedy constrained local refinement
        |
        v
Refined two-tier assignment
```

The feasibility-restoration pre-stage is scenario independent. It considers only moves from the overloaded tier toward the underloaded tier, rejects moves that do not reduce the reconstructed area violation, and stops immediately once the assignment enters the prescribed area window. Raw-cut and timing-path guards remain referenced to the original native TritonPart assignment, so restoration does not create a new guard budget for subsequent refinement.

## Context Components

ASA-RV3D combines three normalized context components:

- **Physical context** derived from OpenROAD artifacts and instance-level physical evidence.
- **Timing context** derived from OpenSTA/OpenROAD timing information.
- **Recovered design context** derived from explainable rule-based mapping of synthesized instances back to coarse RISC-V functional roles and semantic groups.

The recovered design context is optional guidance. It is not a hard architectural placement constraint and does not force complete functional blocks onto one tier.

## Context-OFF and Context-ON

The paper uses two controlled configurations:

- **Context-OFF** keeps the physical and timing components while disabling recovered design context.
- **Context-ON** enables physical, timing, and recovered design-context components under the same feasibility guards.

This comparison isolates the effect of recovered design context on scenario-sensitive crossing metrics.

## Refinement Objective and Feasibility Guards

During normal ASA-RV3D refinement, candidate moves are ranked by a normalized risk-weighted objective. Feasibility is checked separately.

A refinement move is admitted only if it respects the paper configuration:

- reconstructed tier-0 area fraction between `0.48` and `0.52`;
- maximum raw-crossing regret of `5%` relative to the original native timing-aware baseline;
- up to `100` OpenSTA maximum-delay paths;
- mean tier-transition regret limit of `0`;
- worst tier-transition increase limit of `0`;
- maximum refinement budget of `300` iterations;
- convergence window of `10` accepted moves;
- minimum recent relative gain of `1e-3`.

For an imported assignment that is already inside the reconstructed area window, the feasibility-restoration stage is a strict no-op. For a mildly infeasible imported assignment, restoration is performed before normal refinement using scenario-independent overloaded-to-underloaded moves. Recovered design-context weights and scenario-sensitive crossing counts are not used to select restoration moves.

At each restoration step, candidates that fail to reduce the area violation or violate the raw-cut or timing-path guards are rejected. The remaining candidates are deterministically ranked by whether they directly restore feasibility, residual area violation, raw-crossing disturbance, timing-path disturbance, moved area, and a final lexical tie-break. Restoration terminates as soon as the reconstructed area fraction enters the feasible interval.

Importantly, both restoration and subsequent refinement use the **original native TritonPart assignment** as the reference for the raw-cut and timing-path guard budgets. The restored assignment is therefore a feasible starting state for refinement, not a new baseline from which the allowed regret is reset.

This separation is important: restoration recovers starting feasibility with minimal guarded disturbance, whereas the normal ASA-RV3D objective ranks improving moves within the feasible region.

## Algorithm Sketch

```text
Input:
  A0: native timing-aware TritonPart assignment
  F: gate-level, physical, and timing features
  D: optional recovered design context
  S: design-context scenario
  G: feasibility guards

Output:
  A*: refined two-tier assignment

1. Evaluate A0 under the reconstructed area criterion and compute
   the native raw-crossing and timing-path reference metrics.

2. If A0 is outside the reconstructed area window:
   a. Set A <- A0.
   b. Enumerate single-instance moves from the overloaded tier
      toward the underloaded tier.
   c. Reject candidates that do not reduce the area violation or
      violate the raw-cut or timing-path guards relative to A0.
   d. Rank the remaining candidates by minimal guarded disturbance
      and accept the best deterministic candidate.
   e. Repeat until A enters the feasible area interval.
   Otherwise, set A <- A0 without modification.

3. Normalize physical, timing, and optional design-context weights
   for normal ASA-RV3D refinement.

4. Repeat until convergence, no legal improving move, or the move
   budget is reached:
   a. Enumerate candidate single-instance tier moves.
   b. Estimate objective gain for each candidate.
   c. Reject candidates that violate area, raw-cut, or timing-path
      guards, with raw-cut and timing-path limits still referenced
      to A0.
   d. Accept the best remaining improving move.
   e. Update the current assignment and incremental metrics.

5. Return A* and write the assignment, summary, and trace artifacts.
```

The restoration step is optional and precedes the Context-OFF / Context-ON comparison. It does not use recovered design context and does not alter the definition of the subsequent refinement objective.

## SCR1 Full-Flow Evaluation Following Restoration

The optional restoration stage in the submitted method is scenario independent and precedes normal ASA-RV3D refinement. The frozen manuscript evaluates `scr1_core_tuned` only through this restoration stage. A separate subsequent evaluation completes the remaining refinement steps for that design without redefining the method, objective, or feasibility guards.

For SCR1, let `A0` denote the native timing-aware TritonPart assignment and `Ar` the assignment produced by guarded restoration. The imported `A0` is mildly infeasible under the reconstructed-area interval (`0.520588` against an upper limit of `0.52`), whereas `Ar` is feasible (`0.519990`). The restored assignment is obtained after five instance moves, with raw crossings changing from `272` to `276`.

Normal Context-OFF and Context-ON refinement both initialize their current tier state at `Ar`. Their raw-cut and timing-path reference metrics, however, are evaluated at `A0`. Thus, the refinement *starting assignment* and the *guard reference assignment* are distinct. The implementation exposes this distinction through `--initial-assignment` and `--guard-reference-assignment`, respectively. The accepted move sequence remains subject to the original 5% raw-cut regret ceiling, zero mean tier-transition regret, zero worst tier-transition increase, and the `0.48-0.52` reconstructed-area interval. No additional cut or path allowance is granted by restoration.

Both refinement modes use the existing normalized, risk-weighted move objective and the same parameter settings as the manuscript (`300` maximum iterations, `100` evaluated paths, a convergence window of `10` accepted moves, and a minimum recent relative gain of `1e-3`). Context-OFF disables the recovered design-context term while retaining physical and timing information; Context-ON enables all three terms. The restoration algorithm itself remains independent of those scenario-specific terms.

The subsequent SCR1 evaluation contains three scenarios and two refinement modes per scenario. Each run accepts 39-40 moves and ends with `285` raw crossing nets, corresponding to `4.78%` regret relative to `A0`. The final assignments satisfy the reconstructed-area guard. The evaluated mean and worst tier-transition counts remain zero, and the timing-weighted crossing proxy is unchanged. These measures are independent of the optimization objective and should not be interpreted as evidence of improvement in routed 3-D timing.

The scenario-sensitive counts are `143` (OFF) versus `142` (ON) for control/datapath and `39` (OFF) versus `37` (ON) for state/clock. For memory-near-logic, both counts are zero, so a relative context gain is undefined. In both nonzero scenarios, Context-ON has fewer scenario-sensitive crossings than Context-OFF, but does not improve upon the native SCR1 assignment. This is a scenario-dependent boundary result, not a new positive benchmark claim for the frozen paper comparison. Likewise, objective-reduction percentages from Context-OFF and Context-ON are relative to their respective objective definitions and should not be used as direct cross-mode performance comparisons.

The selected 100 SCR1 OpenSTA paths used for this evaluation belong to the `asynchronous` path group and contain no tier transitions. Accordingly, the unchanged mean and worst path-cut values establish guard compliance for the evaluated path set only, not protection of every synchronous critical path or final timing closure.

Supporting refinement traces, assignments, and independent evaluations are retained under `results/scr1_core_tuned_repaired_context_off/`, `results/scr1_core_tuned_repaired_context_on/`, and `results/benchmark_summary/scr1_repaired_full_flow_*.csv`. They extend the available experimental evidence but do not change the submitted manuscript's six primary design-scenario pairs or any frozen file under `paper/`.

## Paper-Facing Result Source

The manuscript-facing result snapshot is stored under `paper/`:

- `paper/table2_partition_results.csv` records the primary partition-level Context-OFF / Context-ON comparison for PicoRV32 and riscv32i.
- `paper/table3_path_validation.csv` records the downstream path-level validation snapshot for the same primary designs.
- `paper/scr1_feasibility_restoration.csv` records the separate SCR1 boundary-case feasibility-restoration snapshot.
- `paper/artifact_manifest.md` documents provenance, interpretation, and scope.

The SCR1 restoration snapshot does not extend Table 2 to a third primary benchmark and does not modify the six design-scenario pairs used for the Context-OFF / Context-ON comparison. It records only the evidence required to show that a mildly infeasible imported baseline can be restored to the prescribed area window under the retained raw-cut and timing-path guards.

Generated outputs under `results/` are retained as supporting, historical, and development artifacts. They may include earlier terminology or intermediate method variants and should not be used as the final manuscript source of truth unless explicitly referenced by the files under `paper/`.

## Scope

ASA-RV3D is an early-stage partition-refinement prototype. It does not claim signoff-quality 3-D placement, routing, TSV or hybrid-bonding insertion, extracted 3-D parasitics, thermal closure, IR-drop closure, or final routed PPA.

The feasibility-restoration extension is demonstrated on one mildly infeasible imported baseline, `scr1_core_tuned`. Its purpose is to show that the evaluated boundary case can be brought into the reconstructed area window without resetting or violating the retained raw-cut and timing-path guard budgets. This evidence should not be interpreted as a guarantee that arbitrary or severely imbalanced native assignments can always be recovered.

The primary Context-OFF / Context-ON evaluation remains the six PicoRV32 and riscv32i design-scenario pairs recorded in the frozen paper snapshot.
