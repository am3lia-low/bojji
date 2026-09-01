# Decision log

Design decisions taken during the build, with the reasoning and the cost accepted.
Feeds `docs/DEVELOPMENT_NARRATIVE.md` (iterations, discarded strategies, tool
selection) and the model-selection deliverable.

Design rationale that predates the build is in `ref material/sop_design.md` and
`ref material/BUILD.md`; this file records what changed and why, during Day 2
onward.

---

## D1. Class-level prediction, not SOP-level

**Decided:** the classifier predicts one of 12 classes. It does not predict a SOP.

`CLASS_TO_SOPS` maps a class to between one and four SOPs, built at startup by
inverting the `intents:` line each SOP declares in its own frontmatter. Eight of
ten indexed classes are 1:1; `tax_reliefs` pulls four SOPs and `payment` pulls two.

**The alternative considered:** predict the SOP directly, making the mapping
trivially correct and removing an unmeasured step.

**Why it was rejected — the holdouts do not survive it.** Labels would have to be
SOP ids, and both holdout kinds become unconstructible:

- *Whole-class* — `rental_income` and `foreign_income_dta` have no indexed SOP, so
  an email in those classes would have no valid label at all. The class becomes
  untrainable rather than unanswerable, and `no_supporting_sop` stops being
  derivable from an empty lookup.
- *Partial-answer* — REL-005 is held out from an otherwise-indexed class. Under
  SOP-level labels, either REL-005 is a label (and is not held out) or it is not
  (and the relief-cap email is unlabelable). The distinction between "unanswerable"
  and "partially answerable" disappears, and it is a real behavioural difference
  the evaluation exists to test.

**Secondary costs of the alternative:** per-label test data falls from ~45 to ~39,
and the hardest distinction in the corpus — REL-001 vs REL-002, near-identical
vocabulary — moves onto the classifier, which cannot see the SOP text, and away
from the drafter, which can.

**Cost accepted:** `class -> SOP group` is correct by construction and is not
measured. Mitigated by D2.

**Honest caveat:** this design earns its place because two classes pull groups. If
the corpus were uniformly 1:1, the class and SOP layers would be the same thing and
the distinction would be ornamental. Worth stating in the README.

---

## D2. Grounding accuracy is measured, not assumed

**Decided:** measure whether the drafter grounded on the SOP the email was
actually built from.

For `tax_reliefs` and `payment`, the drafter receives the whole group in the prompt
— all four relief SOPs is ~27,600 characters, roughly 6,900 tokens — and grounds on
whichever apply. That is a real selection, and it was previously unreported.

**Why the group is handed over whole rather than pre-selected:** an email such as
*"can I claim for my child and my mother?"* needs REL-001 *and* REL-002. Under the
granularity principle multi-relief questions are ordinary rather than a special
case, so a pre-selection step would have to choose "child or parent" and would get
that email wrong. Handing over the group lets the drafter use what applies.

**Why it is measurable for free:** the scenario spec that generates each email
records the SOP(s) it was built from. Comparing that against what the draft cites
costs nothing and was being discarded.

**Reported as:** a secondary metric, over 2 of 12 classes. The headline remains the
risk–coverage curve, per topic.

**Requires (not yet built):**
- `source_sops` on the scenario spec schema — stage 3
- the draft node recording which SOPs it grounded on — stage 4

Without both, this metric cannot be computed. Recorded here so the dependency is
not discovered late.

---

## D3. LLM zero-shot classifier is a baseline, never the runtime

**Decided:** build the LLM classifier as a build-time comparison only. The runtime
classifier stays MiniLM-L6.

**Why not use an LLM in the pipeline**, which would be simpler to build:

- **Calibration is the contribution.** An LLM asked to classify returns text.
  Extracting a probability needs logprobs (not always exposed, not comparable
  across providers) or repeated sampling with agreement measurement — slower,
  costlier, and coarse. The encoder emits a calibratable distribution natively,
  which is what makes temperature scaling and the risk–coverage curve possible.
- **The runtime must work with no API key.** An LLM classifier breaks the
  clean-machine path.
- **It would not fix accuracy anyway.** An LLM can still misroute
  `account_specific` as `filing`; the error becomes harder to measure, not rarer.
- **Escalation guarantees would weaken.** "These three buckets always escalate" is
  currently a property of a dictionary — inspectable, testable, true regardless of
  model behaviour. Asking an LLM to decide escalation makes it a prompt one hopes
  holds.

**What the baseline buys:** the model-selection deliverable is graded on
justification. Reporting encoder vs LLM on accuracy, latency, size, cost and ECE
turns "the encoder is better calibrated" from an assertion into a measurement.

**Where LLMs are used:** drafting in `api` mode, the comparison baseline, the
groundedness judge, and email generation at build time. Never in the classification
or escalation path at runtime.

---

## D4. Escalation is a wrapper around the model, not inside it

**Decided:** keep bucket rollup, calibration and routing as separate layers outside
the classifier.

**Why:** the model reports what it sees; policy decides what to do about it. These
change independently — a policy shift should be a config edit, not a retrain.

- Three of five buckets escalate regardless of confidence. That must hold even when
  the classifier is confidently wrong.
- `BUCKET` derives from `auto_reply_permitted` in SOP frontmatter, so an agency
  conforming real internal SOPs to the schema changes routing with no code change
  and no retraining. Baking escalation into weights forfeits that.
- The orthogonal flags cannot be classes. `computation_requested` cuts across
  classes: *"how much QCR will I get"* is `tax_reliefs` and auto-answerable, but
  must escalate anyway. There is no way to express "escalate regardless of
  predicted class" inside a single softmax.

**Eval consequence:** rolling up 12 classes into 5 buckets gives ~108 test examples
per bucket against ~45 per class. Thresholds set on 45 examples are not defensible
— the binomial interval is wider than the effect. The rollup is only possible
because the layers are separate.

**What this does and does not guarantee.** By construction: *if the class is right,
the policy is right*. It says nothing about whether the class is right. A
confidently misrouted `account_specific` email will have `filing` policy applied
faithfully. That is why the `account_specific` backstop flag exists (D5) and why
its precision and recall are reported rather than assumed.

---

## D5. Escalation accuracy: what is guaranteed vs what must be measured

Recorded because the distinction is easy to blur in a writeup, and blurring it
would be a code–writeup mismatch.

**Guaranteed by construction, already covered by tests:**

| Property | Mechanism |
|---|---|
| Three buckets escalate unconditionally | no confidence value is consulted |
| `no_supporting_sop` fires on an empty lookup | derived, not hand-mapped |
| An unknown label escalates | `bucket_for` falls through to `no_supporting_sop` |

**Must be measured — not yet measured, as no corpus or model exists:**

| What | How | Level |
|---|---|---|
| Escalation accuracy | per escalation *reason* | 6 reasons |
| Risk–coverage | threshold sweep, AURC | per topic |
| Calibration | ECE, reliability, before/after | 5 buckets |
| `computation_requested` | precision / recall | flag |
| `account_specific` backstop | precision / recall | flag |
| Grounding accuracy | vs scenario spec source SOP (D2) | 2 classes |

**The asymmetry that drives reporting.** A false escalation costs coverage: an
officer reads an email they need not have. A false auto-reply is the citizen-facing
failure — answering someone in financial distress, asserting something about a
taxpayer's account, or computing a relief amount. So the headline is **recall on
must-escalate cases, per reason**, never a single blended accuracy figure, which
would let good performance on easy classes mask a miss on `hardship_or_waiver`.

**Two limitations to state rather than defend away:**

1. **Ground truth is free but circular.** The same author writes the SOPs and
   specifies the emails. Mitigations — a different generation model, specs not
   written from SOP text, a hand-written adversarial set held out entirely — reduce
   this; they do not remove it.
2. **~45 test examples per class is thin.** It supports macro-F1. It does not
   support a defensible per-class threshold, which is why thresholds are per bucket.
   The edge-case slice is stratified *into* those 45, so a per-cell figure such as
   "computation-demanding relief emails" rests on roughly 10 examples — adequate for
   a pooled flag metric, not for a per-class claim about it.
