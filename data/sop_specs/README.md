# SOP schema and corpus design

`data/sop_specs/*.yaml` is the human-authored source of truth for the synthetic
officer procedures. `scripts/generate_sops.py` validates those specs and renders
the Markdown corpus in `data/sop/`; generated SOPs should not be edited directly.

For source provenance, licensing, and privacy details, see
[Data sources](../SOURCES.md).

## Design decisions

### The corpus controls routing

Each SOP declares the intents it supports, whether automated replies are permitted,
and which conditions require escalation. At startup the application inverts those
fields into the class-to-SOP and class-to-bucket mappings. Routing policy therefore
lives in the corpus rather than in a duplicate table in application code.

The runtime uses exact lookup instead of vector search. With 17 authored documents
and a closed 10-class taxonomy, the mapping is complete, deterministic, and easy to
audit. A similarity model would add a failure threshold directly before the
escalation decision without solving an ambiguity present in this corpus.

### Holdouts test missing knowledge

Fourteen SOPs are indexed and three are deliberately held out:

- `SOP-INC-001` and `SOP-INC-002` remove all indexed support for
  `rental_income` and `foreign_income_dta`. The router derives
  `no_supporting_sop` from the empty lookup and escalates.
- `SOP-REL-005` removes the overall personal-relief cap from an otherwise
  supported class. This creates a partial-knowledge case without making all tax
  relief questions unanswerable.

The agent never computes a citizen's tax or relief amount. Computation requests are
flagged and escalated because caps, ordering rules, and interacting reliefs cannot be
handled safely from a short prose procedure.

### The SOPs are synthetic

The files are author-written procedures based only on public IRAS guidance. Every
fact in a spec names a source handle, every handle resolves to a URL declared in the
same spec, and every rendered document carries a synthetic banner. Invented queue
names and handling targets are marked as illustrative.

Approved phrasing is rendered into each SOP as grounded source material. Live replies
are still produced only by the configured drafter; the application has no local
template fallback.

## Corpus inventory

| SOP | Intent | Indexed |
|---|---|---:|
| `SOP-FIL-001` | filing | yes |
| `SOP-REL-001` to `SOP-REL-004` | tax_reliefs | yes |
| `SOP-REL-005` | tax_reliefs | no |
| `SOP-ASM-001` | assessment_and_amendment | yes |
| `SOP-PAY-001`, `SOP-PAY-002` | payment | yes |
| `SOP-RES-001` | residency | yes |
| `SOP-ESC-001` | account-specific officer guidance; reached by flag | yes |
| `SOP-ESC-002` | hardship_or_waiver | yes |
| `SOP-ESC-003` | scam_report | yes |
| `SOP-RTE-001`, `SOP-RTE-002` | oos_redirect | yes |
| `SOP-INC-001` | rental_income | no |
| `SOP-INC-002` | foreign_income_dta | no |

## Spec schema

```yaml
sop_id: SOP-PAY-001
title: Handling GIRO enquiries
version: "1.0"
effective_date: 2026-01-01
supersedes: null
applies_to_ya: [2025, 2026]
intents: [payment]           # builds the class-to-SOP mapping
indexed: true                # false keeps the SOP out of runtime lookup
owner_queue: IIT-Payments    # invented, not a real agency queue
handling_target: same_day    # illustrative, not a real SLA
auto_reply_permitted: true
escalate_if:
  - account_specific
  - hardship_or_waiver_request
  - amount_computation_requested

references:
  - id: giro
    url: https://www.iras.gov.sg/...
    fetched: 2026-09-01

scope: >
  What this procedure covers.

not_in_scope:
  - text: The status of a specific taxpayer's GIRO plan.
    route_to: account_specific

facts:
  - text: Deduction date is the 6th of each month.
    source: giro             # must match a references[].id

decision_steps:
  - condition: Asking about a specific failed deduction or amount
    action: Escalate
    reason: account_specific
  - condition: Otherwise
    action: Answer only from the listed facts

approved_phrasing:
  - id: giro_dates
    text: >
      Payments by GIRO are deducted on the 6th of each month.

do_not:
  - Do not confirm whether a specific deduction succeeded or failed.

related: [SOP-PAY-002]
```

## Fields with runtime or build behavior

| Field | Behavior |
|---|---|
| `facts[].source` | Required; generation fails if it does not resolve to a declared reference |
| `indexed: false` | Renders the SOP but excludes it from runtime lookup |
| `intents` | Builds the class-to-SOP mapping |
| `reachable_via` | Names a non-classifier route for an indexed SOP with no intent |
| `auto_reply_permitted` and `escalate_if` | Determine routing buckets and escalation triggers |
| `approved_phrasing` | Becomes part of the rendered SOP supplied to the drafter |
| `related` | Adds cross-references; one dangling reference is retained deliberately as a missing-knowledge case |

## Validation

```bash
python scripts/generate_sops.py --check
python scripts/derive_taxonomy.py --check
```

The checks reject missing citations, an accidental leak of the held-out relief cap,
held-out classes that have become indexed, and a taxonomy projection that no longer
matches the corpus.
