# Follow-up: checkpoint reconciliation and grouped citations

After the complete 18-execution economical study, manual audit found a quality
limitation despite all 16 task checks passing: final notes sometimes retained
present-tense assertions of unfinished implementation in Corrections, alongside
a correct completed Resume. Comma-grouped citations also escaped the individual-ID
matcher. These observations justify a correction, not discarding that study.

The helper now recognizes `[S1, S2]` consistently in validation, source bundling
and project checks. The skill explicitly requires reconciling current-state
statements across Resume, Facts, Constraints and Corrections when state changes;
appending a superseding statement alone is insufficient. Missing sections must
be read; already visible sections can be reused. Hooks remain unchanged.

This protocol is fixed before the additional agents run:

- Replay **all six initial checkpoints** created by real agents in the completed
  economical study, with six fresh real continuation agents, same model/effort,
  unchanged continuation prompt, live policy and independent 16-check grader.
- Initial notes are restored byte-for-byte from their verified history snapshots
  into fresh synthetic workspaces. No final solution, audit finding or prior
  continuation answer is supplied to the new agents. Their copied skill/helper
  contains the correction; fixture implementation starts as the same stub.
- Do not regenerate creation/baseline stages or choose favorable cases. Their
  original events and usage are retained and explicitly marked reused. Per-pair
  inclusive scenario totals combine the **measured original creation cost** with
  the **new measured continuation cost**. These are paired replays, not six new
  independent end-to-end pairs or another 18 unique executions.
- Report the original economical results and all replay outcomes. Add only the
  six newly executed continuation usages to the unique experiment token ledger;
  never charge copied evidence as additional model execution.
- Two workers, 480 seconds per continuation, no outcome-driven reruns. Missing
  usage and infrastructure/quality failures remain visible. Existing boundaries,
  protected files, checkpoint validity and history retention checks remain.
- Manual audit additionally checks final current-state consistency and cited
  source discoverability. These are secondary observations motivated by the first
  study, not silently added to its original 16-point rubric. No retrospective
  replacement of its outcomes is allowed.

```sh
uv run --no-project --with ruamel.yaml==0.18.17 python tools/replay_agent_continuations.py \
  --source-run '/private/completed-economical-study' \
  --run-dir '/private/new-reconciliation-replay' --workers 2
```

This is a focused behavioral validation of the fix. Cache/time/backend variation
and shared initial notes limit causal/general conclusions; the original fresh
paired baseline remains the primary end-to-end comparison.
