# Admin Replacement Calculator

It tells you which parts of an admin role software can take, which parts stay human, and what the honest savings range is.

A CPU-only, rule-based Python CLI for conservative sales diagnostics on fictional synthetic roles. No model downloads, GPU packages, salary data, external services or runtime dependencies. Reports always lead with human-kept work and show assumptions.

## Quickstart

Requires Python 3.10 or newer. In PowerShell from this repository:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[test]"
.\.venv\Scripts\arc fixtures --out fixtures
.\.venv\Scripts\arc parse fixtures/inbox-triage.md --decompose
.\.venv\Scripts\arc classify fixtures/inbox-triage.md
.\.venv\Scripts\arc estimate fixtures/inbox-triage.md
.\.venv\Scripts\arc propose fixtures/inbox-triage.md
.\.venv\Scripts\arc report fixtures/inbox-triage.md --format md
.\.venv\Scripts\arc report fixtures/bookkeeping.md --format json
.\.venv\Scripts\python -m pytest -q
```

`python -m arc` also runs every subcommand without installing the console entry point. Output goes to stdout, errors go to stderr with exit code 2 and the named exception. Use shell redirection to save a report. `report` defaults to Markdown; all other commands emit JSON. Each command accepts a role file and performs its required preceding stages automatically.

## Role format and parser

```text
# Fictional example admin
Synthetic: yes
Weekly hours: 40
## Tools
- Fictional mailbox
## Responsibilities
- 80%: Route structured messages using fixed rules; send template replies using fixed rules
- 20%: Resolve disputes with discretion
```

The title, positive finite weekly hours, synthetic label, at least one tool and at least one responsibility are required. Responsibility lines use `- percentage%: text`. Nonnegative decimal percentages must sum to exactly 100. The parser raises `TimeSplitError` for an incorrect sum and `RoleFormatError` for a malformed schema. Unrecognized fields are rejected. Only explicitly labelled fictional synthetic inputs are supported; the label is a user declaration, not independent provenance verification. Do not enter real company roles or salary data.

## Architecture

```text
Markdown/text role
    |
    v
parse: validate schema, hours and 100% split
    |
    v
decompose: semicolon segments with source line references
    |
    v
classify <--- arc/rules.json
    |
    v
estimate: Decimal arithmetic and low/high scenarios
    |
    +---> propose: prerequisite pilot, value/complexity order
    |
    v
report: human-kept work first, residual role, ranges, rules, plan
```

The declared segmentation rule splits on semicolons only, rejects empty segments, retains original one-based line numbers and divides the responsibility's time equally across segments. It deliberately avoids guessing how natural-language conjunctions divide time. Split distinct tasks into separate responsibility rows for a more precise allocation. Tools are retained as context; their presence does not establish API access or automation feasibility.

## Classification taxonomy and rules

The complete editable configuration is [arc/rules.json](arc/rules.json) and is printed in every report. Matching is deterministic, case-insensitive substring matching, including stems such as `negotiat` and `ambig`. Conservative false positives are possible; this is a transparent heuristic, not semantic understanding. Negation does not cancel a fired indicator.

| Family | Indicators |
| --- | --- |
| Judgment | negotiat, discretion, relationship, ambig, judgment, decide, approve, resolve disputes, sensitive |
| Routine action | route, categorize, copy, validate, match, schedule, send, record, reconcile |
| Assistance | draft, summarize, prepare |
| Structured evidence | rules, template, structured, fixed, checklist, exact |

Ordered decisions:

1. Any judgment indicator vetoes automatable classification. With an assistance indicator the task is hybrid; otherwise it is human-judgment.
2. Assistance without a judgment indicator is still hybrid and requires human review.
3. Routine action plus structured evidence, without judgment or assistance, is automatable.
4. Everything else is human-judgment because deterministic automation has not been established.

Automatable means a candidate for structured, deterministic software handling, subject to validation. Human-judgment means discretion, relationships or insufficient evidence keep the task human. Hybrid means software prepares or drafts and a human decides. Every task carries rationale and the exact firing indicators.

## How ranges are computed

For each task, `weekly_hours = role_hours * responsibility_percent / 100 / segment_count`. All arithmetic uses Decimal. Reported hours have six decimal places; rounding is presentation only. Totals use the unrounded task calculations rather than adding rounded display cells.

| Classification | Low saved fraction | High saved fraction |
| --- | --- | --- |
| Automatable | 0.60 | 0.85 |
| Hybrid | 0.15 | 0.35 |
| Human-judgment | 0 | 0 |

Each task's hours are multiplied by both fractions, and the endpoints are summed independently. These are scenario ranges, not statistical confidence intervals. Residual hours run from weekly hours minus high savings to weekly hours minus low savings. The eligible-hours cap is the total automatable plus hybrid hours. Reported savings never exceed eligible hours; the configured rates leave residual work even in an all-routine role.

For the inbox fixture, 36 routine hours yield 21.6 to 30.6 saved hours, leaving 9.4 to 18.4 hours. The coordinator has 4 routine hours and 4 assisted hours: 2.4 + 0.6 to 3.4 + 1.4, or 3.0 to 4.8 saved hours. Bookkeeping has 20 routine and 12 assisted hours: 12 + 1.8 to 17 + 4.2, or 13.8 to 21.2 saved hours.

The assumptions are a typical declared week, equal segment allocation, clean inputs, stable rules, approved access and exception review. Hybrid work assumes human review of every decision. Setup, adoption and poor data can reduce realized savings, including to zero. Human-kept oversight is included in unsaved time, not added as a second counted task. No salary savings are calculated.

## Implementation proposals

Every plan starts with P0: validate access, input quality and a baseline in a human-supervised pilot. Routine task phases then sort by low estimated weekly savings divided by declared complexity (1 for routine candidates), descending, with task ID as a stable tie breaker. Each candidate depends on P0, so prerequisite dependencies precede value-ranked work. Hybrid tasks remain in the diagnostic and human-kept list rather than being offered as automatic decision workflows. Every phase lists risks and measurements: errors, exception rates, observed time saved and review time. Savings are potential steady-state scenarios and do not deduct one-time project effort. Review the role-specific dependencies with the prospect before implementation.

## Fixture catalogue

`arc fixtures --out <directory>` writes these fixed, UTF-8 fictional files. Existing files with the same names are overwritten. No RNG is used, so no seed is needed.

| File | Purpose |
| --- | --- |
| inbox-triage.md | High routine share with human dispute resolution |
| client-coordinator.md | High judgment share and a small assisted workflow |
| bookkeeping.md | Routine matching, assisted summaries and human disputes |
| malformed.md | Invalid 110% split, intentionally rejected with TimeSplitError |

Reports for all three valid fixtures are reproducible byte for byte in repeated runs in the same environment. There are no timestamps, random identifiers or input path fields. The malformed fixture produces an error, not a report.

## HONESTY BOUNDARY

This tool produces estimates, not promises. Savings are ranges with visible assumptions. Reports must never claim a role can be fully replaced and always lead with what stays human. Judgment-heavy tasks stay human; assisted tasks retain human decisions. Even a 100% routine input keeps exception review, approvals and automation oversight, and explicitly states the residual role. A human remains accountable.

Every report carries: "Estimates are heuristic ranges from declared assumptions on synthetic fixtures. They are not promises or guaranteed outcomes."

All fixtures are fictional and labelled. No real salary data or real company roles are included. Heuristic savings are not a commitment, staffing recommendation or measured outcome. Validate actual time, accuracy, access and exceptions in a pilot before relying on a proposal. If an estimate could be read as a guaranteed outcome, it fails this boundary.

## Verification

The pytest suite covers parsing and named errors, source-preserving segmentation, routine/judgment/hybrid firing rules, every judgment veto, hand-computed savings, residual guardrails including an all-routine role, proposal ordering and dependencies, deterministic fixture bytes and reports, CLI commands, and end-to-end reports in both formats. Implementation is CPU only using the standard library. Publishing is a separate verification step and is not performed by this build.
