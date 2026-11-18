# Economical checkpoints: implementation and frozen follow-up protocol

This follow-up is fixed before its model executions. It preserves the original
[task, quality rubric and metering](real-agent-evaluation-protocol.md): six pairs,
short/long × three repeats, 18 real fresh-context Codex executions, requested
`gpt-6-astra`/`xhigh`, two pair workers, 480 seconds per execution. No outcome-driven
retries or model changes. Baseline prompts, synthetic history, live policy change,
protected files and all 16 independent quality checks are unchanged.

The goal is to test whether reducing OBIA calls and checkpoint repetition lowers
**inclusive** tokens without an observed loss on the same quality criteria.
Success relative to the earlier OBIA run is distinct from net savings against the
new no-memory baseline. Both comparisons will be reported, including negative
outcomes, individual pairs, cached/uncached input and actual output tokens.
Historical before/after comparisons are descriptive: backend/cache/time effects
cannot be isolated by this small study. The fresh paired baseline is primary.

## Implementation under test

- `save`/`patch` now return a compact readback receipt inside the existing write
  lock. It verifies the stored note's decoded UTF-8 text, identity, source definitions and
  links (the existing SHA contract normalizes CRLF to LF). `project_index_current` separately checks the project index. Warning
  semantics for a saved note with failed index rebuilding remain explicit.
  No-op writes also verify actual storage; no extra history snapshot is created.
- `recall --view brief --with-sources` bundles only definitions cited in the
  projection plus an inventory of defined IDs, from the same loaded snapshot.
  Serialized budgets, explicit omissions, atomic essential sections and adaptive
  full-note fallback remain. It does not fetch the referenced files or URLs.
- The skill's common path includes minimal creation/patch examples, recommends
  concise state deltas and reuses evidence/SHA already visible. A successful
  storage receipt avoids separate read/check calls. Section replacement still
  requires its current content; source IDs cannot collide with omitted records.
  Instructions no longer require reference-file loading for an ordinary note.
- Host acknowledgement remains separate. No hook implementation, receipt turn
  identity, host configuration or hook trust is changed.

Tests cover real disk readback, altered/missing writes, stale/no-op indexes,
source collisions, snapshot consistency, budget overflow and existing conflict,
human-edit, history and hook behavior. The raw traces will determine whether
agents actually follow the shorter workflow; the design does not assume they do.

## Only prompt difference

The OBIA continuation requests `--with-sources` and asks it to follow the skill's
checkpoint workflow instead of mandating a redundant final read. The creation
prompt and baseline prompt remain byte-for-byte unchanged in the harness.
The copied skill/helper changes are the treatment, including their instruction
cost. Agents may still expand sources, reread history or perform extra checks;
all that usage counts. No artificial command or note-length cap is imposed.

Initial checkpoint creation and final checkpoint maintenance remain mandatory
and included. The grader requires the same initial active note, valid completed
checkpoint, retained prior version, and factual reporting of work performed.
A smaller note does not compensate for missing requirements or unsupported claims.
Scope deviations and incomplete executions remain visible.

As before, these are explicit helper calls in isolated synthetic workspaces, not
a test of automatic hook injection. No hook events are simulated. Parent-chat
orchestration, implementation/review agents and deterministic grading are outside
the measured executions and will not be claimed as included research costs.

## Run

Commit the implementation and this protocol before executing:

```sh
uv run --no-project --with ruamel.yaml==0.18.17 python tools/evaluate_real_agents.py \
  --run-dir '/private/new-economical-run' --model gpt-6-astra --effort xhigh \
  --repeats 3 --workers 2 --workflow economical
```

Raw events, prompts, tool outputs and answers stay in private storage. Public
outputs contain aggregates, synthetic code and audit findings. Original results
remain available; this follow-up will not overwrite them.
