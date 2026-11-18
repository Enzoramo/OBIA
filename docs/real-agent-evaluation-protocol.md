# Real-agent pilot protocol — 2026-11-18

This protocol is fixed before the measured runs. It tests the published OBIA
implementation at `2351b6b` against reloading complete historical context.
It does not compare OBIA to a hand-written summary, native automatic compaction,
or every possible efficient baseline. It is a small synthetic task evaluation,
not a claim about all projects, models, money, or human time.

## Design fixed in advance

- Six matched pairs: short/long history × three repetitions. The same Python
  queue-selector task and requirements occur in both sizes; the long case has
  more archived diagnostic observations. Each continuation uses a fresh agent.
- Requested model `gpt-6-astra`, reasoning effort `xhigh`, matching the local
  configuration. No selection of a cheaper model for the OBIA arm. CLI version,
  timestamps and usage are recorded. Backend model identity is not independently
  inferred from the requested alias.
- Baseline: historical context is supplied in full; the agent implements and
  verifies the pending function. It need not create a checkpoint.
- OBIA: a real agent first reads the history and skill, creates a sourced note
  through the helper and verifies it. A fresh agent reads the skill, retrieves
  the note with adaptive recall, expands sources as needed, implements/verifies
  the same function, and updates/verifies the checkpoint before finishing.
- All checkpoint creation, instruction loading, source reads, retries and final
  checkpoint maintenance inside these agent executions count. Initial creation
  is a separate measured execution. Maintenance is included in the continuation
  total; its marginal tokens are not separately identifiable from turn totals.
- `queue_rules.json` changes from max_attempts=3 to 2 after initial checkpoint
  creation and before either continuation. Both agents must verify live state.
  Both can inspect historical sources; OBIA is not forbidden from reading the
  full history if it finds that necessary.
- Arm order alternates by case/repetition; two pairs may run concurrently.
  The provider's cache cannot be reset. Cached and uncached input are therefore
  reported separately; repetitions are not assumed statistically independent.
- Eighteen measured executions maximum, 480 seconds per execution, no outcome-
  driven reruns. Infrastructure failures and incomplete usage remain visible.
  A connectivity probe is reported separately, not silently included in either arm.

## Environment and boundaries

Use temporary workspaces with synthetic data, the same sandbox and common agent
boundary instructions. `--ephemeral` avoids persisted chat sessions. Per-process
`--ignore-user-config`, `project_doc_max_bytes=0` and
`skills.include_instructions=false` reduce unrelated startup instruction loading;
OBIA instructions are loaded explicitly by its arm and counted. None of these
writes personal configuration, changes hook trust or bypasses approval/sandbox
controls. Host hook definitions may still be discovered by the CLI; warnings are
retained in private traces. Neither arm may bind a real host session or invoke a
project router. The experiment measures the explicit helper workflow, not lifecycle
trigger reliability. No hook event is fabricated.

Raw traces stay outside the public repository. No old conversation, personal
note, credential, or private project artifact is used as test data. Check for
unexpected tool use, edits to protected fixtures and memory persistence failures.
Keep the public release to synthetic fixtures, harness, aggregates and analysis.

## Outcomes fixed before execution

The independent grader is not copied to agent workspaces. Thirteen functional
checks cover empty input, eligible states, cancellation, time boundaries, live
retry policy, input order, deduplication (including filtering first), limits and
input mutation. Three retention checks cover the live policy value, its evidence
file and preservation of the unverified latency claim. Report individual checks,
all-pass rates and failures; a small all-pass sample does not establish general
quality equivalence. Also inspect claimed verification against command traces.

OBIA separately requires a valid saved initial note, a changed final checkpoint
with prior history retained, and truthful progress reporting. These additional
obligations must not inflate the baseline's quality denominator.

Metering uses actual `turn.completed.usage` events, not local tokenization.
Report input, cached input (a subset), uncached input, output, reasoning output
(a subset of output), input+output total, commands and elapsed wall time.
Do not double-count cache or reasoning. For each pair compare baseline usage
against checkpoint-creation + OBIA-continuation usage. Report per-case totals,
per-pair values and median differences. Missing usage is unknown, never zero.

The earlier work that generated the historical project context is common and
outside this handoff experiment. Harness design, orchestration in the parent chat,
the parent's own OBIA checkpoints, and deterministic grading are not in the
measured agent boundary; this is not a measurement of every token spent building
this evaluation. No amortization projection substitutes for a measured handoff.

## Reproduce

Requires an authenticated Codex CLI and optional evaluation dependencies:

```sh
uv run --no-project --with ruamel.yaml==0.18.17 python tools/evaluate_real_agents.py \
  --run-dir '/private/new-evaluation-directory' \
  --model gpt-6-astra --effort xhigh --repeats 3 --workers 2
```

This command consumes model usage and refuses an existing run directory or one
inside the public repository. It does not change model or hook configuration.
The token-event schema is documented in the
[official Codex source](https://github.com/openai/codex/blob/main/codex-rs/exec/src/exec_events.rs).
CLI/config behavior was checked against the installed help and the
[official configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).
