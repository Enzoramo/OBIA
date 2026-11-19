# Integrated handoff with context reuse: protocol — 2026-11-19

This is a separate prospective round after the first integrated-handoff study.
Retain that round's costs and negative outcomes. Do not replay its checkpoints or
reuse its baseline measurements. Freeze this protocol and the revised production
instructions before launching another 18 executions.

Everything in [the original protocol](integrated-handoff-protocol.md) remains:
the identical baseline prompt, task histories, fixtures, grader, 16 criteria,
model `gpt-6-astra`, effort `xhigh`, three short/long repetitions, alternating arm
order, two workers, timeout, inclusive accounting and semantic quality gates.
The same harness runs the production adapter; no scenario-specific answer hints
are added. Report all pairs and both sizes, even if aggregate savings occur.

Only the adapter's generic model instructions change:

- Reuse historical evidence already supplied in context. A source locator is for
  targeted recovery, not a mandatory reread checklist. Reopen sources for missing,
  ambiguous or contradictory context; inspect current files and test volatile
  implementation claims as before. Do not skip meaningful task verification.
- For a checkpoint-only request, synthesize the supplied evidence without
  filesystem discovery unless the request or a material gap needs it. Attribute
  supplied historical observations accurately instead of converting them into
  claims of fresh inspection.
- Batch independent observations where practical. This is an instruction change
  within the OBIA treatment; the experiment cannot isolate its contribution from
  memory reuse. No tool-call ceiling, test cap or lower reasoning effort applies.
- Record task state in the checkpoint. Capture/save status and temporary adapter
  phase restrictions belong to the caller, not to task memory. The actual receipt
  is still required before the host can claim storage success.

The observed motivations are redundant history reads and saved notes describing
their own persistence as still pending. This round must pass the same initial
retention and final reconciliation audit; functional correctness alone cannot
turn inconsistent memory into success. A fresh complete cohort is necessary to
test initial generation as well as continuation, charging both in full.

Primary success remains aggregate inclusive OBIA tokens below this round's fresh
baseline **and** all frozen quality/storage/metering gates. A small synthetic
study cannot establish general savings or quality equivalence. If this round
does not meet the gates, report that outcome rather than dropping cases or
retrying unchanged instructions until a favorable result appears.
