# Integrated handoff: frozen real-agent protocol — 2026-11-19

The target is net model-token savings relative to reloading complete history,
including checkpoint creation and maintenance, with no loss on the frozen quality
criteria or observed semantic memory audit. This protocol is fixed before runs.
It does not redefine the baseline to make OBIA win.

## Treatment and comparison

Use the same synthetic queue task, short/long histories, policy change 3→2,
protected files, 13 functional +3 retention checks, model `gpt-6-astra`, effort
`xhigh`, three repetitions per size and alternating arm order. Two pair workers,
480 seconds per model execution, 18 planned fresh executions. Baseline prompt,
answer schema and grader remain identical to the previous study. Both arms retain
normal access to their fixtures and meaningful verification tools.

The treatment changes the memory integration:

- One real model execution receives the historical context and generic structured
  checkpoint schema/instructions from production `handoff.py`. It creates the
  initial checkpoint in its response. No hand-authored answer or rule extractor
  supplies its content. Any tools it chooses to use are counted.
- The adapter validates and persists that exact output through existing OBIA
  storage, verifies its ownership and readback, and prepares the next snapshot.
- A fresh real agent receives the complete note/SHA in its request. It implements
  and verifies the same task, returning `{answer, checkpoint}`. Only `answer` goes
  to the original independent grader. The adapter captures the reconciled
  checkpoint with the SHA from preparation, preserving history.
- Initial generation is charged in full, not described as free or merely marginal.
  Continuation usage includes instructions/schema, injected memory and final
  checkpoint output. Deterministic prepare/capture operations are separately
  logged with elapsed time/receipts; no model calls are hidden behind them.

This is an opt-in host-adapter workflow, not the earlier manual helper workflow
or automatic lifecycle-hook injection. Config, trust and ack logic are unchanged.
No hook events are fabricated. The adapter is generic production code: it knows
no queue requirements, historical Hxx labels, expected policy or grading answers.

## Success and failure fixed in advance

Primary success requires all six complete pairs to have measured usage, aggregate
inclusive OBIA tokens below the fresh baseline, all 16 criteria passing in every
arm, protected fixtures intact, valid initial/final checkpoints with history, and
no remaining current-state contradiction or source/uncertainty loss observed in
manual audit. Report short/long and every pair, including regressions; aggregate
success must not be described as every task saving tokens or general equivalence.

Audit meaningful source attribution, volatile policy verification, cancellation,
accepted corrections, unverified latency and reconciliation of old current state.
This is the same additional semantic audit that exposed the previous regressions;
it does not inflate the 16-point grader. Initial notes must retain required
context, not merely produce a passing final implementation by rediscovery.

Every actual usage event remains in a separate execution ledger, including paid
executions followed by capture, schema, index or ownership failure. Missing final
usage is unknown, never zero. Failures cannot disappear by dropping their pairs.
No outcome-driven retries. Any later implementation correction requires a new
protocol/run and retains this attempt's cost/outcomes separately.

Raw evidence remains private, using only synthetic fixtures/new agents. No old
personal chats, credentials or personal notes enter the sample. Parent-chat
orchestration, implementation/review work and its checkpoints are excluded and
must not be claimed as measured. Tokens are input + output; cached input and
reasoning output are subsets, not extra sums. Pricing and human hours are not
inferred. Model/cache variation and the small single-task sample limit conclusions.

## Reproduce

```sh
uv run --no-project --with ruamel.yaml==0.18.17 python tools/evaluate_integrated_agents.py \
  --run-dir '/private/new-integrated-evaluation' --model gpt-6-astra --effort xhigh \
  --repeats 3 --workers 2
```

The generic adapter and its preservation tests must be committed before this run.
The original histories and grader remain unchanged.
