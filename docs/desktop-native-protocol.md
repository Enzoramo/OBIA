# Codex desktop integration: prospective protocol — 2026-11-19

The target is the existing Codex desktop chat, not a replacement CLI wrapper.
The production change combines project binding/sourced recovery and combines
save/partial-patch/readback/ack in the app's existing synchronous shell tool.
It neither changes hook configuration/trust nor makes a future final response
available to a command hook. Hook turn identity remains fail-closed.

## Native-agent calibration

A fresh native subagent reported no directly supplied SessionStart context.
Its actual metadata identifies Codex Desktop, `gpt-6-astra`, effort `xhigh`; its
thread has no OBIA hook state. `CODEX_THREAD_ID` identifies the child, whereas
`CODEX_SESSION_ID` still identifies the parent. Never infer the child's binding
from that inherited value. The calibration consumed 46,640 actual tokens and
must remain outside, but visible alongside, the comparison.

Thus a subagent-only benchmark cannot establish Stop execution/cost in a normal
desktop chat. No fabricated event, seeded turn identity, config override or
hook-trust bypass may repair that missing evidence.

## Reviewable full-app comparison

**Not executed:** the user chose to keep only subagents and document the
limitation. The following proposed four-chat design remains a future option;
it is not authorization to create chats in this task.

Four explicitly authorized temporary desktop chats are required: planning and
fresh continuation for each of two arms. Creation/control messages and archival
need the user's explicit authorization; use the app's supported thread tools.
Until authorization exists, do not create user-owned chats or claim this
comparison ran. Use the same model/effort in both arms and report the actual
metadata; no outcome-driven retries or cherry-picked continuations.

Use two isolated copies of the same committed OBIA repository. The useful
developer workload is a Markdown renderer for exported evaluation measurements,
using the two existing integrated-study JSONs as real project inputs. The agent
may edit only its copy's `tools/render_measurements.py` and its own tests. No
publication, settings edits, other chats or personal-data access.

Each planning chat first inspects the format and proposes a renderer. A second
control message supplies the same accepted correction in each arm: derive cost
from the execution ledger rather than trusting stored aggregate totals, preserve
failed/missing stages, and never convert unknown usage to zero or claim savings
without complete metering and quality. Do not implement in the planning phase.

The baseline receives an explicit experimental exception to task-memory use and
remains unbound, with hooks/config still enabled. Its fresh continuation receives
the full visible history of its planning chat (user/assistant/tool observations,
without hidden reasoning). OBIA planning uses the installed desktop workflow,
records both meaningful states, and its fresh continuation recovers only the
saved task note plus the same current implementation request. Inspect current
project files as needed in both arms; no tool/test ceiling applies.

Quality checks must be frozen before implementation agents start. They cover
correct totals and cache subsets, creation plus continuation accounting, every
case/pair including regressions, unknown and failed stages, quality gates,
source/uncertainty retention, privacy-safe output, read-only inputs, and actual
tests. A semantic audit must inspect all OBIA checkpoints and source claims.

Count all actual model input + output for both planning turns, fresh continuation
and any real Stop continuation. Include checkpoint generation/updates/recovery,
skill loading and model-visible tool receipts. Parse only usage/identity/lifecycle
metadata from the four exact authorized session traces; no unrelated histories.
Do not sum repeated cumulative snapshots or count reasoning/cache twice. Missing
terminal evidence or reset counters make cost incomplete, never zero. Preserve
every paid failed execution and all negative results.

Record real hook/session evidence separately from task correctness. Successful
save or a receipt for an earlier observed turn does not prove Stop approval.
All configuration/trust hashes must match before and after. Archive the four test
chats only after final observations and only with the authorized scope.

A single paired project task can establish a measured result for that task; it
cannot confirm universal daily savings. Report total tokens, uncached input,
output, duration and quality separately, whether the result is positive or
negative. Parent development/orchestration and this protocol's review are outside
the paired workload and must not be presented as measured workload savings.

## Authorized subagent comparison

Before comparative agents run, freeze three arms of the same workload:
baseline without task memory, the prior manual OBIA workflow from `6c7ba8e`,
and the synchronous desktop workflow. Each arm gets a fresh planning subagent
(two requested turns: inspection then accepted correction) and a fresh
implementation subagent. Six fresh native agents, nine requested work turns;
all actual paid continuations remain counted. No model/effort override.

Use the frozen request/correction and independent checks in
`tools/desktop_eval_cases.py`. The grader stays outside agent workspaces. It
tests the renderer using real exported project reports and small explicit
accounting fixtures; these fixtures are never described as real hook events.

The initial/continuation costs for all three arms are included, not treated as
common free work. Both OBIA arms record initial and corrected planning state,
recover in a fresh agent, reconcile completion, and retain note history. The
manual arm reads its frozen skill/helper copy; the new arm uses the installed
desktop helper. The baseline receives its own full visible planning history,
excluding hidden reasoning. No memory prose or implementation is authored by
the evaluator for an agent. Only each arm's own evidence may cross its phases.

For the subagent identity, use the directly observed CODEX_THREAD_ID and verify
it against session metadata. Never use inherited CODEX_SESSION_ID. Bind explicit
task IDs, not another chat's inferred task. With no lifecycle events, null turn
IDs stay null; save verification and ack_scope do not become Stop verification.
No hook run/handle, seeded turn state, new user-owned chat, configuration or
trust change is allowed. Model-generated note writes and acknowledgements are
normal task operations; their tool rounds and outputs are counted.

Primary numeric comparison: inclusive synchronous OBIA versus the no-memory
baseline. Secondary: synchronous versus manual OBIA. Functional and semantic
quality must pass independently of token results. Even if both show savings,
the conclusion is restricted to this subagent task: **daily end-to-end savings
with native Stop are not established**. Calibration cost stays visible outside
the comparison; parent development/review/orchestration remains excluded.
