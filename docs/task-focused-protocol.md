# Task-focused recovery: prospective protocol — 2026-11-20

This is a new, bounded pilot. The prior desktop study and its original grades
remain unchanged. Freeze this document, `tools/task_focused_eval_cases.py` and
the product commit before any comparative planning agent starts. Record those
commits and input hashes in the run manifest. Do not change prompts, graders or
implementations after seeing outcomes to turn a failure into a success.

## Comparison

Run one useful developer scenario in three arms:

1. **Baseline:** no task memory; fresh continuation reads its own plaintext
   planning history, exported with `export_desktop_history.py`.
2. **Brief:** the current synchronous desktop workflow, without `--focus`.
3. **Focused:** the same synchronous workflow and checkpoint instructions,
   adding `--focus` to recovery in the fresh continuation.

Use six fresh native subagents: one planner and one continuation per arm. Each
planner receives two turns (inspection and accepted correction), each continuation
one implementation request: nine planned work turns. No model/effort overrides,
new user-owned chats, simulated lifecycle events, seeded turn identity, hook
configuration/trust changes or suppression of Stop. Record actual model/effort
metadata; differing settings make the comparison qualified, not silently equal.
The user previously chose subagents only. Native Stop coverage is not claimed.

No planning, baseline, checkpoint or implementation from an earlier study is
reused. Each arm's planner writes its own content. Initial/corrected plans and
completion updates all contribute to that arm's measured cost. Preserve every
paid failed/aborted/extra execution. No outcome-driven retries. A genuine input
or infrastructure defect must be disclosed with all costs and the original
result retained; do not quietly substitute a favorable run.

## Identical source workspaces and permitted changes

Create three isolated copies from the same frozen product commit, with identical
hashes. Include the product skill, the two public integrated-report JSONs,
`tools/summarize_integrated_evaluation.py`, the integration/hook documentation
and any direct public dependencies needed to inspect those sources. Use an
explicit allowlist recorded before agents start. Do not copy `.git`, graders,
evaluation tests/protocols, previous agents' implementations, study result prose
or private notes into the source workspaces. Keep the independent grader outside
all agent workspaces. The two existing public report JSONs are task inputs,
not answers to the new study.

Planning is read-only except the memory arms' authorized task notes. The only
implementation additions are `tools/render_measurements.py` and
`tests/test_render_measurements.py`; no pre-existing source may change. Preserve
hashes and check scope independently. Exclude generated `__pycache__` files from
the source-diff count, not from other relevant observations.

## Exact requests and context transfer

The Python protocol module exports complete canonical text:

- `INITIAL_REQUEST`: inspect the public report format and plan the renderer;
  initially consider stored aggregates. Also inspect `docs/integrations.md`,
  `docs/hooks.md` and `skills/obia/references/desktop.md` for a deferred hook
  diagnostic. This is useful secondary project context, not filler.
- `CORRECTION`: replaces aggregate-based accounting with the execution ledger
  and includes `FORMAT_CONTRACT`. Deliver the identical correction in turn two
  to all planners. Do not implement yet.
- `CONTINUE`: implement the accepted renderer in a fresh agent, inspect current
  sources and run meaningful tests. Do not redeliver the technical correction
  outside the arm's history/memory; retention is part of the task.
- `MEMORY_LAYOUT`: identical instruction for both memory arms, for notes written
  by the agents themselves. Use Resume, Constraints, Renderer accounting and
  Deferred hook diagnostics, with sources and uncertainties. Do not pad notes,
  force important information out of Resume or impose an artificial size target.
- `FOCUS`: exactly `renderer ledger accounting schema workflow unknown costs quality privacy`.

The coordinator may add only concrete workspace/helper/vault/config/task paths,
scope/runtime identity instructions and the assigned arm's workflow. Record the
actual delivered prompts. Technical evidence may cross phases only from that
arm's own planner. The baseline receives its own complete plaintext task/tool
history, preserving actual tool truncation and excluding reasoning, common
bootstrap and opaque blocks. Verify this export before dispatch; an empty or
truncated handoff is not a baseline. Do not export fuller command stdout as if
the planner saw it.

In both memory arms, the planner explicitly binds its own directly observed
`CODEX_THREAD_ID`, writes the initial state and patches the accepted correction.
Never use inherited `CODEX_SESSION_ID` as the child's identity. The fresh agent
binds its own thread to the arm's explicit task and recovers the actual saved
note. Brief uses ordinary `desktop.py recover`; focused adds the fixed `--focus`.
Both may read any omitted relevant sections/sources with the actual SHA, inspect
current files and perform as many meaningful tests as needed. Missing context
must not be concealed to lower token usage. Each memory arm reconciles a final
completion checkpoint and acknowledges its exact SHA. A null/old turn identity
remains unverified for native lifecycle purposes.

## Corrected contract and functional acceptance

Unlike the previous ambiguous protocol, **schema must be integer 1 (not bool
or float) and workflow must be `integrated_handoff`**. Missing or unsupported
metadata raises ValueError. All valid minimal fixtures include these fields.
Do not amend old grades based on this new contract.

The canonical correction also defines unknown partial usage, optional subset
counters, unexpected-stage allocation, count mismatches, empty studies and
strict quality booleans. Unexpected stages retain their known paid cost only in
`known_total_tokens`; their existence suppresses all comparison percentages.
An isolated reported total cannot replace unknown input/output counts.

The new independent grader retains the former 19 behavioral checks with valid
metadata and adds ten checks: six metadata rejection cases, unallocated extra
costs, partial usage despite a reported total, planned-count mismatch and empty
study behavior. **All 29 must pass** in each compared implementation. Grader
inputs are data fixtures, never simulated hook events. Do not provide the
grader or its results to implementation agents for repair during this study.

The original task sources are public and may contain unrelated implementation
details. Report facts the agent actually verified. Claims that the renderer
verified raw traces or independently audited note quality would be unsupported.

## Independent memory and resumption audit

Functional acceptance and semantic retention are separate gates. Audit all
three final implementations and both memory arms' three checkpoint versions:

- Accepted ledger correction replaces the initial stored-aggregate proposal.
- Explicit schema/workflow contract, unknown-cost treatment, unexpected costs,
  strict quality gate and safe output survive the handoff.
- Sources correspond to observed task files; uncertainties remain marked.
- Hook diagnostics remain deferred; no configuration/trust changes occur.
- Completion notes reconcile planning restrictions and current state; reported
  tests match actual observations and no stale persistence claim remains.
- Every saved note/snapshot matches its receipt SHA; storage/index and ack scope
  are reported separately. These checks do not prove native Stop execution.

Inspect actual recovery packets and any follow-up section reads. Record included
and omitted headings and payload sizes, but do not equate fewer characters with
fewer model tokens. Failure to retrieve needed evidence is a quality failure.
A large section or fallback full read is a valid outcome with its full cost.

## Metering and decision rule

For each of the six exact authorized session traces, use `desktop_usage.py` to
validate identity, terminal turn evidence and the final cumulative input/output
counters. Never sum repeated cumulative snapshots or count cache/reasoning twice.
Missing terminal usage is unknown, not zero. Export only allowlisted metadata;
do not publish prompts, bootstrap, reasoning, credentials or private paths.

Per arm, add both planning turns and the fresh continuation. This includes
inspection, skill loading, initial/corrected checkpoint generation, storage/ack
calls, recovery/expansion, implementation, tests and the completion checkpoint.
Any actual extra work turn or observed Stop continuation also remains counted.
Do not assign a causal checkpoint-only cost by subtracting unrelated executions.
Report input, cached/uncached input, output, total tokens, tool calls and observed
turn duration separately. No financial or speed inference from token totals.

Primary comparison: focused versus baseline, including all arm costs. Secondary:
focused versus brief. A successful comparison requires complete metering, all
29 functional checks, scope/storage/semantic audit approval and lower focused
total tokens. Report quality and numeric differences even when success is false.
Preserve negative results and missing evidence. Parent implementation,
orchestration, independent review and publication are outside the measured
workload; the executor sum is not total project expenditure.

One scenario and independently generated plans cannot estimate variance or
establish universal savings. The baseline's new-agent history read differs from
continuing an already cached desktop chat. Subagents without real lifecycle
events cannot confirm daily end-to-end Stop cost. No retrospective diagnostic
may replace this frozen acceptance gate.
