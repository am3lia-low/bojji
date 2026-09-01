# SOP Specs — authoring format

Human-authored input to `scripts/generate_sops.py`, which renders each spec into
`data/sop/SOP-*.md`. Specs are the source of truth; the markdown is derived and
should never be hand-edited.

Design rationale is in `ref material/sop_design.md` S4 and S8.3.

---

## Why specs rather than prose

Every factual claim in an SOP must trace to a public IRAS URL (`sop_design.md`
S8.2). A spec makes that structural rather than aspirational: each fact is a
record carrying its own `source`, and the generator refuses to render a fact
without one. The traceability guarantee is therefore enforced by the build, not
by a promise in the README.

---

## Schema

```yaml
sop_id: SOP-PAY-001          # SOP-<AREA>-<NNN>; AREA in FIL REL ASM PAY RES ESC RTE INC
title: Handling GIRO enquiries
version: "1.0"
effective_date: 2026-01-01
supersedes: null             # or a sop_id
applies_to_ya: [2025, 2026]
intents: [payment]           # class name(s); builds CLASS_TO_SOPS
indexed: true                # false = authored but held out of the index
owner_queue: IIT-Payments    # INVENTED — not a real IRAS queue
handling_target: same_day    # ILLUSTRATIVE — not a real IRAS SLA
auto_reply_permitted: true
escalate_if:
  - account_specific
  - hardship_or_waiver_request
  - amount_computation_requested

references:                  # every url cited by a fact must appear here
  - id: giro                 # short handle, referenced by facts below
    url: https://www.iras.gov.sg/...
    fetched: 2026-09-01

scope: >
  One paragraph. What enquiry this procedure covers.

not_in_scope:
  - text: The status of a specific taxpayer's GIRO plan.
    route_to: account_specific

facts:                       # -> S2 "Key facts the officer may state"
  - text: Deduction date is the 6th of each month.
    source: giro             # REQUIRED. must match a references[].id

decision_steps:              # -> S3. Escalation steps come first, by convention.
  - condition: Asking about their own plan or a specific failed deduction
    action: Escalate
    reason: account_specific
  - condition: Otherwise
    action: Answer from S2 and direct to the channels listed

approved_phrasing:           # -> S4. The template-floor draft body (architecture S2.8).
  - id: giro_dates           # slots use {curly_braces}
    text: >
      Payments by GIRO are deducted on the 6th of each month.

do_not:                      # -> S5
  - Do not confirm whether a specific deduction succeeded or failed.

related: [SOP-PAY-002]       # -> S6
```

## Fields the generator treats specially

| Field | Behaviour |
|---|---|
| `facts[].source` | Required. Must resolve to a `references[].id`, else the build fails. |
| `indexed: false` | Rendered to `data/sop/` but excluded from the index. Creates the holdout. |
| `intents` | Builds `CLASS_TO_SOPS`. A class absent from every indexed spec yields `no_supporting_sop` by derivation. |
| `auto_reply_permitted` + `escalate_if` | Build `BUCKET`. Escalation policy is corpus-derived, not hardcoded. |
| `approved_phrasing` | Load-bearing: it is the `local`-mode draft. Not decorative. |
| `related` | Cross-references. One dangling ref is deliberate (`sop_design.md` S10.4). |

## Conventions

- **Synthetic banner** is added by the generator, not written in the spec.
- `owner_queue`, `handling_target` are invented/illustrative and marked so.
- Facts are restatements, never verbatim IRAS prose (`sop_design.md` S8.1).
- Never state a dollar amount as a computed result — only as a published threshold.
