# Scenario specs — how the email corpus is generated

Human-authored input to `scripts/generate_emails.py`. A scenario describes a
*situation a citizen is in*, never a class label, and the generator writes the
email from that situation.

Design rationale: `ref material/BUILD.md` S5.3.

---

## The one rule that matters

**A scenario must never mention its own label, and must never quote SOP text.**

Both are leakage. If a scenario said `class: tax_reliefs` and the generator saw
it, the resulting emails would carry vocabulary chosen *because* of the label, and
the classifier would learn the generator's tell rather than the citizen's problem.
Reported accuracy would then measure a shortcut.

So the pipeline is:

    situation (persona + circumstance)  ->  LLM  ->  email text
    label                               ->  attached AFTERWARDS, never shown

`scripts/check_leakage.py` tests this empirically: a TF-IDF + logistic regression
model is fitted on the generated text. If a bag of words separates the classes
almost perfectly, the emails contain a giveaway and the corpus is rebuilt.

---

## Schema

```yaml
scenario_id: REL-CHILD-001        # <AREA>-<TOPIC>-<NNN>
label: tax_reliefs                # ground truth. NEVER shown to the generator.
source_sops: [SOP-REL-001]        # which SOP(s) answer this. Ground truth for
                                  # grounding accuracy (BUILD.md S9.2).

situation: >                      # what the generator sees. No label, no SOP text.
  A parent wants to know whether they can claim something for their
  teenage child who did some part-time work over the holidays.

persona:
  role: employee                  # employee | self_employed | retiree | foreigner | parent
  literacy: standard              # standard | imperfect | singlish
  register: polite                # polite | frustrated | anxious | terse

season: filing                    # filing | estimates | noa | any
                                  # drives received_at, so seasonality is testable

# --- flag ground truth: free, because the scenario declares it ---
computation_requested: false      # does the email demand arithmetic?
account_specific: false           # does it ask about THIS taxpayer's own record?

# --- optional ---
plant_pii: [nric, phone]          # inject fake identifiers for scrub-recall
                                  # measurement. FABRICATED values only.
multi_intent: false               # does it genuinely ask two things?
notes: >                          # why this scenario exists, for the review pass
  Covers the $8,000 child income threshold without asking for a computation.
variants: 6                       # how many emails to generate from this scenario
```

## Fields that are ground truth

These cost nothing to record and are what the evaluation reads. Every one of them
would otherwise require hand-labelling:

| Field | Measures |
|---|---|
| `label` | classification accuracy, macro-F1 |
| `source_sops` | **grounding accuracy** — did the draft use the right SOP? |
| `computation_requested` | the computation flag's precision and recall |
| `account_specific` | the backstop flag's precision and recall |
| `plant_pii` | scrub recall against known planted values |
| `season` | whether performance holds across the tax year |

## Held-out classes

`rental_income` and `foreign_income_dta` have scenarios and labels like any other
class — the classifier must still predict them. What they do not have is an
indexed SOP, so `source_sops` names the held-out file and the router escalates on
`no_supporting_sop`. The emails are ordinary citizen questions; the system simply
has no procedure for them.

## Balance

Equal examples per class, because every class gets its own published number under
per-topic reporting. The edge-case slice is stratified *into* the per-class
allocation rather than added on top, so no class is starved.

**Consequence to remember:** a per-cell figure — say "computation-demanding relief
emails" — rests on roughly 10 test examples. Adequate for a pooled flag metric,
not for a per-class claim about it.

## Conventions

- **Fake identifiers only.** NRICs are fabricated with a valid checksum so the
  validator exercises properly; they belong to nobody.
- **No real personal data**, ever, including the author's own.
- Scenarios are authored to cover the SOP's *scope* and its *not in scope* list,
  so both the answerable and the escalating paths are represented.
