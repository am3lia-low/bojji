# Synthetic scenario design

`data/scenarios/*.yaml` defines 116 situations used by
`scripts/generate_emails.py` to create the 3,000-email corpus. For provenance and
privacy details, see [Data sources](../SOURCES.md).

## Anti-leakage rule

The generator receives the situation, persona, style, season, and generated PII. It
does **not** receive the file name, class label, source SOPs, notes, or ground-truth
flags.

```text
situation + persona + style -> GPT-4o -> email
label + metadata                         -> attached afterward
```

This prevents the model from writing toward a class name. After generation,
`scripts/check_leakage.py` checks for vocabulary shortcuts, duplicates, boilerplate,
length effects, class imbalance, and flag confounding.

## Schema

```yaml
label: tax_reliefs                  # file-level class; hidden from the generator
source_sops: [SOP-REL-001]          # file-level default

scenarios:
  - scenario_id: REL-CHILD-001
    situation: >
      A parent asks whether they can claim relief for a teenager
      who earned money from a holiday job.
    persona:
      role: parent
      literacy: standard            # standard | imperfect | singlish
      register: polite              # polite | frustrated | anxious | terse
    season: filing                  # filing | estimates | noa | any
    computation_requested: false
    account_specific: false
    source_sops: [SOP-REL-001]      # optional per-scenario override
    plant_pii: [nric, phone]        # optional generated test values
    multi_intent: false
    variants: 6
    notes: QCR child-income threshold; hidden from the generator
```

## Evaluation metadata

| Field | Used for |
|---|---|
| `label` | Classification accuracy and macro-F1 |
| `scenario_id` | Grouped data splits and scenario-level bootstrap intervals |
| `source_sops` | Draft-grounding reference |
| `computation_requested` | Computation-flag precision and recall |
| `account_specific` | Account-specific-flag precision and recall |
| `plant_pii` | PII scrub recall |
| `season` | Seasonal analysis |

## Corpus rules

- Each of the 10 classes has 300 generated emails.
- All variants of one scenario stay in the same train, calibration, or test split.
- `rental_income` and `foreign_income_dta` remain labelled normally but have no indexed SOP.
- Scenarios cover both answerable questions and conditions that should escalate.
- Generated identifiers are not sourced from people, but registry collisions were not checked.
- A small subgroup result may contain too few scenarios for a reliable standalone claim.
