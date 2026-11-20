#!/usr/bin/env python3
"""Prospective task-focused retrieval acceptance checks (2026-11-20).

Independent copy: the prior protocol and scores are never rewritten.

Only evaluation code. No model calls, hook events, settings or vault writes.
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys


INITIAL_REQUEST = """Plan a useful OBIA developer change; do not implement yet.
Add tools/render_measurements.py, using only Python's standard library, to render
the existing exported integrated-study JSON reports as compact Markdown.
Inspect docs/integrated-agent-measurements-2026-11-19.json and
docs/integrated-reuse-measurements-2026-11-19.json and relevant exporter code.
The intended APIs are summarize(report: dict) -> dict and
render_markdown(report: dict) -> str; CLI: python3 tools/render_measurements.py REPORT.
Initially consider using the report's stored aggregate totals and flags. Show
every case/pair, including regressions, and separate creation from continuation.
Do not claim financial or speed savings from total tokens. Do not mutate inputs,
read credentials, use network/delegation or edit anything in the planning phase.
Also inspect docs/integrations.md, docs/hooks.md and
skills/obia/references/desktop.md for a separate future hook
status diagnostic. Record observed distinctions between stored context, ack and
actual lifecycle validation, with sources and uncertainty. That diagnostic is
DEFERRED: do not implement it or alter hooks/configuration/trust. This secondary
context is real project planning, not instructions to pad a note.
Return a concise plan, observed source locators, uncertainties and next actions.
"""

CORRECTION = """Accepted correction to the plan; still do not implement yet:
do NOT trust stored aggregate/by_case totals or complete_metering/primary_success.
Recompute costs from execution_ledger. Derive planned stages from every pair's
case/repeat: baseline-resume, obia-checkpoint, obia-resume. planned_executions must
match that set. Missing/unknown/unexpected stages make metering incomplete;
retain every known paid cost, including extra/failed executions. Duplicate stage
identities, negative/noninteger token counts and inconsistent usage are invalid
input (ValueError), not zero. Input+output are total; cached input/reasoning output
are subsets. A non-null reported total must agree. Do not mutate the report.

summarize returns baseline_tokens, checkpoint_tokens, resume_tokens, obia_tokens,
known_total_tokens, metering_complete, quality_pass, net_reduction_percent,
success, and pairs. Unknown arm totals are null. Each pair contains case, repeat,
the four arm/phase totals, metering_complete and net_reduction_percent. Order
pairs by case/repeat and retain regressions. quality_pass requires every pair's
storage_pass/task_quality_pass/manual_audit_pass/execution_pass to be exactly true,
with no failures/infrastructure_error. An empty study is not successful.
net_reduction_percent (aggregate and pair) is null unless metering and quality
pass and baseline >0; otherwise it is 100*(baseline-OBIA)/baseline. success also
requires OBIA < baseline. known_total_tokens includes every known ledger usage,
even when no comparison can be established. Missing usage is never counted as 0
in an arm total. Unsupported/malformed structures fail visibly.

Markdown must label Baseline, Creation, Resume, OBIA, include every pair and its
actual numbers/unknown markers, and state 'Metering: complete' or 'incomplete',
'Quality: passed' or 'failed', and 'Result: savings' or 'not established'. Use
only safe numeric/boolean fields and validated case/repeat labels; never dump
arbitrary report text, private paths, error bodies or prompt content. The existing
reports use case labels short/long and nonnegative integer repeats. Report invalid
input without echoing its contents. The CLI writes only stdout/stderr and exits
nonzero on invalid input. Final work may edit only tools/render_measurements.py
and tests/test_render_measurements.py in your isolated repository copy.
"""

FORMAT_CONTRACT = """Required format, replacing any uncertainty in the initial plan:
every report must be a JSON object with schema exactly integer 1 (not bool or
float) and workflow exactly the string integrated_handoff. Missing/unsupported
schema or workflow raises ValueError. Valid small reports need these metadata
fields too; no inference from filenames. Extra unrelated fields are ignored.

Each pair has case short or long and repeat a nonnegative integer (not bool).
Pair identities and ledger stage identities must be unique. execution_ledger and
pairs are lists; planned_executions is a nonnegative integer (not bool). Expected
stage names are case-repeat/baseline-resume, case-repeat/obia-checkpoint and
case-repeat/obia-resume. A nonnegative planned_executions count differing from
3*len(pairs) makes metering incomplete rather than hiding known paid costs.

Unexpected ledger entries with nonempty string stage names contribute any known
usage ONLY to known_total_tokens; do not allocate them to an arm by guessing
from a prefix. Their existence makes global metering incomplete and suppresses
all comparison percentages, including pair percentages. Planned arm totals still
reflect their own expected stages: known expected usage remains known even when
an unrelated extra stage exists. Missing/null usage or missing/null input_tokens
or output_tokens means unknown cost, never zero. Every present non-null token
counter must be a nonnegative integer, never bool/float; invalid counts raise
ValueError. Cache and reasoning counters, when absent, default to zero; validate
their subset bounds whenever the corresponding base count is known. Any known
reported total must equal input+output when both are known. An isolated reported
total does not turn unknown input/output into complete measured usage.

An empty pairs list with planned_executions=0 and empty ledger has zero known
cost, quality_pass=false, success=false and net_reduction_percent=null. For
nonempty studies, required quality booleans must be exactly true, failures must
be an empty list and infrastructure_error must be exactly false. The stricter
failure wins over stored aggregate/success flags. The renderer need not verify
raw trace bytes or perform a semantic memory audit: do not claim it did.

Retain the accepted ledger correction, this format contract and source locators
for the renderer continuation. The separate hook diagnostic stays deferred.
"""

CORRECTION += "\n\n" + FORMAT_CONTRACT

FOCUS = "renderer ledger accounting schema workflow unknown costs quality privacy"

MEMORY_LAYOUT = """Use the same ordinary note layout in either OBIA arm: a concise
Resume describing current state and next actions, Constraints for non-negotiable
scope, Renderer accounting for technical details needed to implement the accepted
contract, and Deferred hook diagnostics for the secondary future investigation.
Use source citations and record uncertainty where it belongs. Write the content
yourself from observed task/source evidence; do not pad to a target size or omit
important context to favor a retrieval mode. Initial/corrected planning states
and completed implementation are meaningful checkpoint boundaries. Recovery may
expand any needed section using its actual SHA. A heading is not evidence.
"""

CONTINUE = """Resume the accepted renderer task and implement it in the allowed
files. Inspect current relevant files, run meaningful local checks, and report
only tests actually observed. Retain the accepted correction and uncertainties.
Do not edit source reports, exporter/helper code, settings or grader files.
The result is evaluated for behavior, evidence, source preservation and scope;
do not infer or seek hidden grader answers. End with a concise factual result.
"""


def fixture():
    ledger = []
    for stage, cost in (('baseline-resume', 100), ('obia-checkpoint', 20), ('obia-resume', 50)):
        ledger.append({'stage': 'short-0/' + stage, 'usage': {
            'input_tokens': cost - 5, 'cached_input_tokens': 10,
            'output_tokens': 5, 'reasoning_output_tokens': 2, 'total_tokens': cost}})
    return {'schema': 1, 'workflow': 'integrated_handoff', 'planned_executions': 3, 'execution_ledger': ledger,
            'aggregate': {'usage_known': {'baseline': {'total_tokens': 999999}}},
            'complete_metering': False, 'primary_success': False,
            'pairs': [{'case': 'short', 'repeat': 0, 'storage_pass': True,
                       'task_quality_pass': True, 'manual_audit_pass': True,
                       'execution_pass': True, 'failures': [], 'infrastructure_error': False}]}


def grade(workspace):
    target = workspace / 'tools/render_measurements.py'
    checks = {}
    try:
        spec = importlib.util.spec_from_file_location('evaluated_renderer', target)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception:
        return {'checks': {'import': False}, 'passed': 0, 'total': 1, 'all_pass': False}

    def check(name, assertion):
        try:
            checks[name] = bool(assertion())
        except Exception:
            checks[name] = False

    def normal():
        d = fixture(); before = copy.deepcopy(d); r = module.summarize(d)
        return (d == before and r['baseline_tokens'] == 100 and
                r['checkpoint_tokens'] == 20 and r['resume_tokens'] == 50 and
                r['obia_tokens'] == 70 and r['known_total_tokens'] == 170 and
                r['metering_complete'] is True and r['quality_pass'] is True and
                r['success'] is True and abs(r['net_reduction_percent'] - 30) < 1e-8)
    check('derived_totals_subsets_and_no_mutation', normal)

    def unknown(remove=False):
        d = fixture()
        if remove: d['execution_ledger'].pop()
        else: d['execution_ledger'][-1]['usage'] = None
        d['complete_metering'] = True; d['primary_success'] = True
        r = module.summarize(d)
        return (r['metering_complete'] is False and r['success'] is False and
                r['baseline_tokens'] == 100 and r['checkpoint_tokens'] == 20 and
                r['resume_tokens'] is None and r['obia_tokens'] is None and
                r['known_total_tokens'] == 120 and r['net_reduction_percent'] is None)
    check('unknown_usage_not_zero', unknown)
    check('missing_stage_not_zero', lambda: unknown(True))

    def extra():
        d = fixture(); d['execution_ledger'].append({'stage': 'short-0/obia-retry',
            'usage': {'input_tokens': 5, 'output_tokens': 2, 'total_tokens': 7}})
        r = module.summarize(d)
        return r['known_total_tokens'] == 177 and r['metering_complete'] is False and r['success'] is False and r['net_reduction_percent'] is None
    check('unexpected_paid_stage_retained', extra)

    for field in ('storage_pass', 'task_quality_pass', 'manual_audit_pass', 'execution_pass'):
        def failed_quality(key=field):
            d = fixture(); d['pairs'][0][key] = False; r = module.summarize(d)
            return r['quality_pass'] is False and r['success'] is False and r['net_reduction_percent'] is None and r['known_total_tokens'] == 170
        check('quality_gate_' + field, failed_quality)

    def failure():
        d = fixture(); d['pairs'][0]['failures'] = [{'error': '/private/sensitive-body'}]
        r = module.summarize(d)
        return not r['success'] and not r['quality_pass'] and r['known_total_tokens'] == 170 and '/private/' not in module.render_markdown(d)
    check('failure_cost_and_privacy', failure)

    def rejected(change):
        d = fixture(); change(d)
        try: module.summarize(d)
        except ValueError: return True
        return False
    for field in ('schema', 'workflow'):
        check('missing_' + field + '_rejected', lambda key=field: rejected(lambda d: d.pop(key)))
    for value, label in ((2, 'unsupported'), (True, 'boolean'), (1.0, 'float')):
        check(label + '_schema_rejected', lambda v=value: rejected(lambda d: d.update(schema=v)))
    check('unsupported_workflow_rejected', lambda: rejected(lambda d: d.update(workflow='other')))

    def extra_allocation():
        d = fixture()
        d['execution_ledger'].append({'stage': 'short-0/obia-retry',
            'usage': {'input_tokens': 5, 'output_tokens': 2, 'total_tokens': 7}})
        r = module.summarize(d)
        return (r['known_total_tokens'] == 177 and r['baseline_tokens'] == 100 and
                r['checkpoint_tokens'] == 20 and r['resume_tokens'] == 50 and
                r['obia_tokens'] == 70 and not r['metering_complete'] and
                r['pairs'][0]['net_reduction_percent'] is None)
    check('extra_cost_not_guessed_into_arm', extra_allocation)

    def partial_usage():
        d = fixture(); d['execution_ledger'][-1]['usage'].pop('input_tokens')
        r = module.summarize(d)
        return (r['known_total_tokens'] == 120 and r['resume_tokens'] is None and
                r['obia_tokens'] is None and not r['metering_complete'] and not r['success'])
    check('partial_usage_unknown_despite_total', partial_usage)

    def planned_mismatch():
        d = fixture(); d['planned_executions'] = 4
        r = module.summarize(d)
        return r['known_total_tokens'] == 170 and not r['metering_complete'] and not r['success']
    check('planned_count_mismatch_incomplete', planned_mismatch)

    def empty():
        d = fixture(); d.update(pairs=[], execution_ledger=[], planned_executions=0)
        r = module.summarize(d)
        return r['known_total_tokens'] == 0 and not r['quality_pass'] and not r['success'] and r['net_reduction_percent'] is None
    check('empty_study_not_success', empty)

    check('duplicate_stage_rejected', lambda: rejected(lambda d: d['execution_ledger'].append(copy.deepcopy(d['execution_ledger'][0]))))
    check('negative_usage_rejected', lambda: rejected(lambda d: d['execution_ledger'][0]['usage'].update(input_tokens=-1)))
    check('boolean_usage_rejected', lambda: rejected(lambda d: d['execution_ledger'][0]['usage'].update(output_tokens=True)))
    check('inconsistent_usage_rejected', lambda: rejected(lambda d: d['execution_ledger'][0]['usage'].update(total_tokens=999)))
    check('invalid_subset_rejected', lambda: rejected(lambda d: d['execution_ledger'][0]['usage'].update(cached_input_tokens=999)))

    def regression():
        d = fixture(); second = fixture(); second['pairs'][0]['case'] = 'long'
        for item in second['execution_ledger']: item['stage'] = item['stage'].replace('short', 'long')
        second['execution_ledger'][-1]['usage'].update(input_tokens=145, total_tokens=150)
        d['pairs'] += second['pairs']; d['execution_ledger'] += second['execution_ledger']; d['planned_executions'] = 6
        r = module.summarize(d)
        return len(r['pairs']) == 2 and r['pairs'][0]['case'] == 'long' and r['pairs'][0]['net_reduction_percent'] == -70 and r['obia_tokens'] == 240 and not r['success']
    check('all_pairs_and_regressions_retained', regression)

    def public(name, expected_b, expected_o, expected_quality):
        data = json.loads((workspace / 'docs' / name).read_text())
        r = module.summarize(data)
        return r['baseline_tokens'] == expected_b and r['obia_tokens'] == expected_o and r['quality_pass'] is expected_quality and len(r['pairs']) == 6
    check('real_negative_study', lambda: public('integrated-agent-measurements-2026-11-19.json', 899761, 1092867, False))
    check('real_final_study', lambda: public('integrated-reuse-measurements-2026-11-19.json', 965327, 801966, True))

    def markdown():
        d = fixture(); d['private_detail'] = '/Users/private/never-echo'
        md = module.render_markdown(d)
        return all(s in md for s in ('Baseline', 'Creation', 'Resume', 'OBIA', '100', '20', '50', '70', 'Metering: complete', 'Quality: passed', 'Result: savings', 'short')) and '/Users/' not in md
    check('markdown_labels_numbers_and_privacy', markdown)
    def cli():
        source = workspace / 'docs/integrated-reuse-measurements-2026-11-19.json'
        raw = source.read_bytes()
        result = subprocess.run([sys.executable, '-B', str(target), str(source)], cwd=workspace,
                                capture_output=True, text=True, timeout=10)
        return result.returncode == 0 and 'OBIA' in result.stdout and source.read_bytes() == raw
    check('cli_read_only', cli)
    return {'checks': checks, 'passed': sum(checks.values()), 'total': len(checks), 'all_pass': all(checks.values())}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace', type=Path)
    args = parser.parse_args()
    print(json.dumps(grade(args.workspace.resolve()), indent=2))
