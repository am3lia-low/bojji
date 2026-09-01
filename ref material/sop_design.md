# SOP Corpus Design

Companion to `BUILD.md`. Defines what an SOP contains, which SOPs exist,
how classes map onto them, and how retrieval works.

All IRAS facts cited below were verified against live pages on 1 Sep 2026.

**Status:** supersedes the earlier 18-class / 22-SOP draft. See S9 for what
changed and why.

---

## 1. The shape of the system in one page

    email
      -> classifier                  12 classes, one model, outputs probabilities
      -> BUCKET[class]               hand-written map -> 1 of 5 routing buckets
                                     (sums the class probabilities in that bucket)
      -> calibrate()                 temperature scaling on the summed value
      -> CLASS_TO_SOPS[class]        hand-written map -> list of SOP ids
      -> router(bucket, conf, flags) -> auto-draft | escalate
      -> drafter reads those SOPs and grounds its reply

Both maps are built at startup by reading `intents:` from SOP frontmatter. They
live in the corpus, not in code.

**There is no search anywhere in this pipeline.** "Retrieval" is a dictionary
lookup that hands the drafter between one and four short markdown files.

---

## 2. The 12 classes

10 indexed + 2 held out.

### 2.1 Auto-answerable (5)

| # | Class | SOPs | Covers |
|---|---|---|---|
| 1 | `filing` | FIL-001 | who must file, No-Filing Service, deadlines (15 Apr paper / 18 Apr e-file), e-file vs paper, late filing |
| 2 | `tax_reliefs` | REL-001..004 | child (QCR / Child Relief (Disability)), parent, CPF/SRS, WMCR/PTR |
| 3 | `assessment_and_amendment` | ASM-001 | NOA types, understanding the assessment, amendments, objections |
| 4 | `payment` | PAY-001, PAY-002 | GIRO, payment channels, late-payment penalty, refund timing |
| 5 | `residency` | RES-001 | residency test, non-resident rates, Certificate of Residence |

### 2.2 Always escalate (3)

| # | Class | SOP | Bucket / reason |
|---|---|---|---|
| 6 | `account_specific` | ESC-001 | `requires_account_lookup` — my NOA, my refund, my GIRO status |
| 7 | `hardship_or_waiver` | ESC-002 | `high_consequence` — cannot pay, instalment plea, penalty waiver |
| 8 | `scam_report` | ESC-003 | `high_consequence` — phishing, IRAS impersonation; route to ScamShield / 1799 |

### 2.3 Out-of-scope redirects — "no back door" (2)

| # | Class | SOP | Redirect to |
|---|---|---|---|
| 9 | `oos_business_tax` | RTE-001 | sole-proprietor / partnership / corporate income tax |
| 10 | `oos_other_agency` | RTE-002 | CPF Board, MOM, other IRAS tax types (GST, property, stamp duty), IR21 tax clearance |

### 2.4 Held out — SOP authored but NOT indexed (2)

| # | Class | SOP | Yields |
|---|---|---|---|
| 11 | `rental_income` | INC-001 | `no_supporting_sop` |
| 12 | `foreign_income_dta` | INC-002 | `no_supporting_sop` |

### 2.5 Granularity principle

> Leaf granularity is the **coarsest** partition that still lets the drafter
> ground correctly.

The classifier's job is a routing decision with calibrated confidence. Routing
happens at bucket level. A leaf exists only to select an SOP set, so splitting
finer than that buys nothing and costs data per class — which is what calibration
depends on.

This is why all reliefs are one class. They route identically, carry the same
computation-escalation trap, and the drafter can select among four short
documents in context. Splitting them would thin the per-class data that the
contribution rests on.

It also makes multi-relief emails ordinary rather than exceptional: *"can I claim
for my child and my mother?"* is one class, not a `multi_intent` special case.

---

## 3. The 5 routing buckets

`BUCKET` maps each class to exactly one bucket. L1 probability is the sum of the
class probabilities in that bucket.

| Bucket | Classes | Router behaviour |
|---|---|---|
| `auto_answerable` | 1-5 | draft if calibrated confidence clears the threshold |
| `requires_account_lookup` | 6 | always escalate |
| `high_consequence` | 7, 8 | always escalate |
| `out_of_scope` | 9, 10 | redirect, never guess |
| `no_supporting_sop` | 11, 12 | always escalate |

**No second model and no second training run.** One classifier over 12 classes;
the bucket layer is a hand-written map derived from SOP frontmatter
(`auto_reply_permitted`, `escalate_if`).

Calibration does not disappear: temperature scaling is fitted on the summed
bucket distribution against the calibration split. That is a fitting step,
not a training run — but it is the contribution, so it stays explicit.

**Why the two levels exist — eval statistics.** At 1,800 emails, 50/20/30:

| Level | Units | Test examples each | Supports |
|---|---|---|---|
| Bucket | 5 | ~108 | calibration, thresholds, risk-coverage |
| Class | 12 | ~45 | accuracy / macro-F1 only |

Thresholds set on ~45 examples are not defensible; the binomial interval is wider
than the effect. Each metric goes where its data supports it.

### 3.1 Orthogonal flags and their detection

Some signals cut *across* classes rather than partitioning them, so they cannot be
classes. They are detected separately and applied **after** the bucket rollup, so
the taxonomy stays a clean partition:

    route = decide(bucket, calibrated_conf, flags)

| Flag | Mechanism | Status | Rationale |
|---|---|---|---|
| `computation_requested` | lexical rules | **implemented + measured** | closed set of phrasings; auditable, free, testable |
| `multi_intent` | 2nd-highest class prob above threshold | implemented | free — the distribution already exists; two high-scoring classes *is* multi-intent |
| `under_specified` | — | KIV | hard to separate from ordinary low confidence |

**`computation_requested` must be measured, not merely implemented.** The class
`tax_reliefs` is auto-answerable, but an email demanding arithmetic must escalate
regardless. A missed flag means the agent computes a relief amount — the single
failure mode the design exists to prevent (S11).

Ground truth is free: the scenario spec records whether it asked for a
computation, so precision and recall cost nothing to obtain. Report them. If
recall is mediocre, that is a finding, not something to hide.

Detection patterns: `how much`, `what amount`, `calculate`, `compute`, `total`,
`how many dollars`, `what will my tax be`, plus a currency figure in an
interrogative sentence.

**Known simplification:** `account_specific` is a class, but the
generic-versus-my-case distinction genuinely cuts across every topic ("what is
the GIRO deduction date" vs "why did *my* deduction fail") and strictly belongs
as a flag. It is kept as a class for the prototype because a flag needs a second
detector and the lexical signal is weak ("what is my filing deadline" is
generic). Recorded as a scoping decision, not taxonomy.

---

## 4. What goes in an SOP

An SOP is an **officer-facing handling procedure**, not a knowledge article. It
answers "what do I do with this email", not "what is the tax rule". Semi-formal:
terse, bullet-heavy, `if X -> do Y`.

SOPs are structured around **procedures**, not around IRAS website pages. One SOP
covers a handling procedure end to end, with internal tables for variants.

| Part | Purpose | Consumed by |
|---|---|---|
| Frontmatter | routing + policy metadata | `sop/loader.py`, router |
| Synthetic banner | misrepresentation guard | human readers |
| S1 Scope / Not in scope | boundary of the procedure | classifier design |
| S2 Key facts | what the officer may state | draft node (grounding) |
| S3 Decision steps | ordered if/then, escalation first | router logic |
| S4 Approved phrasing | canned blocks | draft node (scaffolding) |
| S5 Do not | negative constraints | tests + eval |
| S6 Related | cross-references | complexity, dangling refs |

**The frontmatter is the integration seam.** `intents` builds `CLASS_TO_SOPS`;
`auto_reply_permitted` and `escalate_if` build `BUCKET`. Escalation policy is
therefore corpus-derived, not hardcoded. An agency conforming its real SOPs to
this schema changes system behaviour without touching code — worth stating in the
README, as it reframes the synthetic corpus as a documented interface contract.

### 4.1 Worked example

Frontmatter:

    ---
    sop_id: SOP-PAY-001
    synthetic: true
    title: Handling GIRO enquiries
    version: 1.0
    effective_date: 2026-01-01
    supersedes: null
    applies_to_ya: [2025, 2026]
    intents: [payment]
    owner_queue: IIT-Payments          # invented, not an IRAS queue
    handling_target: same_day          # illustrative
    auto_reply_permitted: true
    escalate_if:
      - account_specific
      - hardship_or_waiver_request
      - amount_computation_requested
    references:
      - https://www.iras.gov.sg/quick-links/payments/giro-individual-income-tax
    last_reviewed: 2026-09-01
    ---

Body:

    # SOP-PAY-001 - Handling GIRO enquiries

    > **SYNTHETIC DOCUMENT.** Authored for a technical assessment. Not an IRAS
    > document; does not reflect IRAS internal practice. All facts are traceable
    > to the public sources in `references`.

    ## 1. Scope
    Taxpayer asks how GIRO works, how to apply, when deductions occur, or what
    happens when a deduction fails.

    **Not in scope:** the status of a specific taxpayer's plan, or why *their*
    deduction failed -> escalate (`account_specific`).

    ## 2. Key facts the officer may state
    - GIRO is available as up to 12 monthly instalments or a one-time yearly
      payment.
    - Deduction date is the **6th of each month**. If the 6th falls on a weekend
      or public holiday, deduction is made the next working day.
    - If a deduction is unsuccessful, a **second attempt is made on the 20th**.
    - The arrangement is **cancelled after 2 consecutive months of failed
      deductions** (4 failed deductions in a row).
    - The provisional instalment plan begins in **May** each year.
    - Channels: myTax Portal (minutes); DBS/POSB, OCBC, UOB bank portals and AXS
      (up to 3 working days); hard copy (up to 21 working days).
    - Requires an SGD savings or current account with a participating bank.

    ## 3. Decision steps
    1. Asking about their own plan, a specific failed deduction, or an amount?
       -> **Escalate** (`account_specific`). Never speculate on why one failed.
    2. Requesting penalty waiver or hardship restructuring?
       -> **Escalate** (`hardship_or_waiver_request`).
    3. Otherwise answer from S2 and direct to the channels above.

    ## 4. Approved phrasing
    > "Payments by GIRO are deducted on the 6th of each month. If the 6th falls
    > on a weekend or public holiday, deduction is made on the next working day.
    > Where a deduction is unsuccessful, a second attempt is made on the 20th."

    ## 5. Do not
    - Do not confirm whether a specific deduction succeeded or failed.
    - Do not advise on bank charges - refer the taxpayer to their bank.
    - Do not compute instalment amounts.

    ## 6. Related
    - SOP-PAY-002 (payment channels and late-payment penalties)
    - SOP-ESC-002 (difficulty paying - always escalates)

---

## 5. The 17 SOPs

14 indexed, 3 held out.

| SOP | Class | Indexed |
|---|---|---|
| FIL-001 Handling filing enquiries | `filing` | yes |
| REL-001 Child reliefs (QCR / Child Relief (Disability)) | `tax_reliefs` | yes |
| REL-002 Parent reliefs | `tax_reliefs` | yes |
| REL-003 CPF and SRS reliefs | `tax_reliefs` | yes |
| REL-004 WMCR and Parenthood Tax Rebate | `tax_reliefs` | yes |
| REL-005 Personal income tax relief cap ($80,000) | `tax_reliefs` | **held out** |
| ASM-001 Handling assessment and amendment enquiries | `assessment_and_amendment` | yes |
| PAY-001 Handling GIRO enquiries | `payment` | yes |
| PAY-002 Payment channels and late-payment penalties | `payment` | yes |
| RES-001 Handling residency enquiries | `residency` | yes |
| ESC-001 Account-specific enquiries | `account_specific` | yes |
| ESC-002 Hardship and waiver requests | `hardship_or_waiver` | yes |
| ESC-003 Scam and impersonation reports | `scam_report` | yes |
| RTE-001 Redirect: business and corporate income tax | `oos_business_tax` | yes |
| RTE-002 Redirect: other agencies and other tax types | `oos_other_agency` | yes |
| INC-001 Rental income | `rental_income` | **held out** |
| INC-002 Foreign income and DTA relief | `foreign_income_dta` | **held out** |

Two kinds of holdout, deliberately:

- **INC-001 / INC-002** hold out a whole class, producing genuinely unanswerable
  emails -> `no_supporting_sop`.
- **REL-005** holds out one SOP from an otherwise-indexed class, producing a
  *partial answer* case: the agent can state relief eligibility but cannot reason
  about the $80,000 cap. Correct behaviour is a partial answer plus escalation,
  not a confident wrong total.

---

## 6. Measuring retrieval

Under the earlier one-class-one-SOP design, hit-rate was a tautology — it equalled
classification accuracy. Consolidation changes that, but only partly. Be precise
about what is measurable:

| Stage | Mechanism | Measured? |
|---|---|---|
| email -> class | encoder classifier | **Yes** — macro-F1 |
| class -> SOP group | dictionary lookup | No — correct by construction |
| group -> grounding | drafter, in context | **Yes** — grounding accuracy |

**SOP grounding accuracy**: did the draft ground on the SOP the scenario spec was
built from? Ground truth is free — the spec records its source SOP.

Only `tax_reliefs` (4 SOPs) and `payment` (2 SOPs) pull groups, so this applies to
2 of 12 classes. It is a **secondary metric, not the headline.** The headline
remains the risk-coverage curve.

**Draft quality is evaluated separately** — see `BUILD.md` S6.3. A bounded
LLM-as-judge groundedness check over ~50 sampled drafts asks one binary question
("does this reply assert any fact not present in the provided SOP?"), with the
same 50 reviewed by hand so judge-human agreement is reported. Narrow question,
binary outcome, agreement measured — which is what makes an LLM judge defensible
rather than decorative. Judge must not be the drafting model.

Two things it does buy:

1. **A real ablation** — does handing the drafter four SOPs instead of one degrade
   grounding?
2. **A comparison slot for vector search — KIV, not planned.** SOPs declare
   `intents:` in frontmatter, so the mapping is explicit and complete by
   construction; searching for something already hand-indexed solves a problem
   that does not exist. Consequence: the README must *argue* the absence
   (bounded corpus, closed class set, auditability, one fewer failure mode
   upstream of the escalation decision) rather than cite a measurement. That
   argument holds — but it must not drift into "we measured it".

---

## 7. How results are reported

**Per-topic, not aggregate.** The original headline format was "X% of the inbox
handled autonomously at a Y% error rate". X depends on class volume mix, which is
not published, varies seasonally, and cannot be ascertained — asserting it would
be a fabricated denominator presented as a finding.

Per-topic coverage is also the **composable** result. An agency knows its own mix
and can multiply through to its own aggregate. A single blended figure derived
from a guessed mix is useless to them and unfalsifiable.

Result statement takes this shape:

> Across N of 10 indexed enquiry types, the agent reaches >=95% routing precision
> at >=70% coverage within that type. Three types never auto-respond by policy.
> Two are unanswerable from the indexed corpus and escalate correctly. Aggregate
> inbox coverage depends on volume mix, which is not published and varies
> seasonally; per-type figures are reported so an operator can compute their own.

**This also settles the test-set design.** Balanced sampling was a compromise
under an aggregate headline — it produced a coverage number that did not match any
real inbox. Under per-topic reporting, balanced is correct: equal statistical
power per topic is exactly what is wanted when every topic gets its own number.

An aggregate may still be shown as an *illustration* ("under a uniform mix this
would be X%"), clearly labelled illustrative and never as a finding.

---

## 8. Provenance, licensing and the confidentiality line

### 8.1 Licensing — what the constraint actually is

IRAS Terms of Use state that site Contents "shall not be reproduced, republished,
uploaded, posted, transmitted or otherwise distributed in any way, without the
prior permission of IRAS". The same document also requires written permission to
*hyperlink to an internal page*, and written notification to link to the homepage
— which places it as early-2000s boilerplate that is universally not observed, by
news outlets, tax advisory firms and other agencies alike.

The line this project actually relies on is copyright, not the ToU:

> **Copyright protects expression, not facts.**

Tax rates, filing deadlines, GIRO deduction dates and relief thresholds are facts,
and facts stated in legislation at that. Restating them in a different structure
is not reproduction.

| Activity | Status |
|---|---|
| Fetching IRAS pages for reference | Fine — public site, public access |
| Extracting facts, restating in our own structure | Fine — facts are not copyrightable |
| Citing source URLs in frontmatter | Fine, and standard practice |
| Committing a dump of IRAS pages as a corpus | Avoided |
| Copying distinctive prose verbatim | Avoided |

So: **fetch as widely as useful.** A substantial amount of IIT information already
exists on the site but sits several navigation levels deep — which is precisely
why citizens email in the first place, and is worth stating in the README as the
problem framing. The only constraint is that `.scratch/` stays gitignored and the
committed SOPs contain restatements with citations.

### 8.2 Confidentiality

The author has prior IRAS call-centre experience. Singapore tax officers are bound
by official secrecy provisions (Income Tax Act s.6) and typically the Official
Secrets Act. The line:

> **Every factual claim in an SOP must trace to a public IRAS URL recorded in that
> SOP's `references:` frontmatter.**

Prior experience is used only to choose which topics matter and to state the
escalation boundary in principle — account-specific queries require a database
lookup and therefore escalate. That is a structural fact about any tax authority,
not privileged information.

| Excluded | Substituted with |
|---|---|
| Real internal system names | Generic (`case management system`) |
| Real queue identifiers | Invented (`IIT-General`, `IIT-Payments`) |
| Real internal reference codes | Invented `SOP-XXX-NNN` scheme |
| Real internal SLAs | Illustrative, flagged as such |
| Reproduced internal wording | Written from public sources |
| Taxpayer data of any kind | Fabricated personas, fake NRICs only |

Every file carries a synthetic banner, and the README states prominently that the
SOPs reflect no internal IRAS material, template or practice.

### 8.3 Generation pipeline

    data/sop_specs/*.yaml      (human-authored: topic, intents, escalate_if,
            |                   effective dates, references)
            |
            +-- .scratch/*.html    (public IRAS pages, fetched at author time,
            |                       GITIGNORED, never committed)
            v
    scripts/generate_sops.py
            v
    data/sop/SOP-*.md          (committed: restated prose + URL citations)

| Step | Effort |
|---|---|
| Write 17 YAML specs | ~1.5 h |
| `scripts/fetch_reference.py` -> `.scratch/` | ~30 min |
| `scripts/generate_sops.py` -> `data/sop/*.md` | ~1 h |
| Human review pass over 17 SOPs | ~1.5 h |

The review pass is not optional — it is where the public-URL traceability
guarantee is actually enforced.

### 8.4 Honest cost: circularity

The same author writes the SOPs and specifies the test emails. Mitigations:

1. SOP topic coverage mirrors the structure of real IRAS guidance, so the corpus
   shape is externally anchored.
2. Emails are generated from *scenario* specs, never from SOP text, using a
   different model than the LLM classification baseline.
3. A hand-written adversarial set is held out entirely from generation.
4. Messiness is injected deliberately (S10).

State this in limitations; do not defend it away.

---

## 9. What changed from the earlier draft, and why

| Was | Now | Why |
|---|---|---|
| 18 classes / 22 SOPs | 12 classes / 17 SOPs | Granularity principle (S2.5): coarsest partition that still grounds correctly |
| 4 separate relief classes | 1 `tax_reliefs` class | They route identically; splitting thinned per-class data that calibration depends on |
| SOPs mirrored IRAS page structure | SOPs are handling procedures | Page-per-SOP was a holdover from the abandoned scraping plan |
| `oos_tax_clearance` separate | folded into `oos_other_agency` | Same redirect behaviour; prototype scope |
| Retrieval hit-rate dropped as tautology | Grounding accuracy, secondary metric | Group-pulling classes make within-group selection a real decision |
| Vector search as optional ablation | KIV, not planned | SOPs declare `intents:`; the mapping is complete by construction |
| Headline "X% of the inbox" | Per-topic coverage (S7) | Volume mix is unpublished and seasonal; per-topic is composable by an operator |
| Flags named but unspecified | Detection mechanism + measurement specified (S3.1) | `computation_requested` gates the failure mode the design exists to prevent |
| Per-class consequence-weighted thresholds | Per-bucket thresholds | The per-class claim was self-imposed in the Day-1 brainstorm, required by nothing in the assessment, and only 2 of 5 buckets have a threshold that bites |
| Drafting mechanism unspecified | Template floor (SOP S4) + LLM ceiling | Runtime must produce a reply with no API key; also makes draft groundedness true by construction |
| DistilBERT primary | MiniLM-L6 primary | ~90MB commits in plain git, removing the Hugging Face dependency from the clean-machine run |
| Scraping "disallowed" | Fetching fine; committing avoided | Earlier framing was overstated — see S8.1 |
| ~800 emails | ~1,800 emails | Bucket-level calibration needs ~100 test examples per bucket |

Dropped from the candidate list entirely, and not part of the taxonomy: course
fees / NSman / grandparent caregiver reliefs; newborn; retrenchment and
retirement; deceased estate; platform workers and gig income; tax evasion
reporting; Certificate of Residence as a standalone class.

---

## 10. Deliberate complexity to inject

Real SOP corpora are not internally consistent. A clean one flatters the system.

1. **Supersession** — REL-004 v1.0 (children born before 1 Jan 2024) superseded by
   v2.0. `applies_to_ya` disambiguates. Tests whether the agent respects effective
   dates.
2. **Cross-document dependency** — a child relief question needs REL-001 + REL-004
   + the held-out REL-005 cap.
3. **Overlapping scope** — ASM-001 and FIL-001 both touch objecting to an NOA. Both
   are pulled; the drafter must not contradict itself.
4. **A dangling reference** — one SOP cites an annexe that does not exist. Correct
   behaviour is to escalate, not to invent it.

---

## 11. The rule this corpus enforces

**The agent never computes a tax or relief amount.**

IIT reliefs are conjunctive with caps, ordering rules and interaction limits (QCR
allowed first, WMCR takes the balance, $50,000 combined per child, $80,000 overall
cap). LLMs over prose fail at this confidently. Every SOP carries
`amount_computation_requested` in `escalate_if`.

Defensible as policy, and it removes a failure mode that could not be fixed in
five days.

---

## 12. Internal SOPs — deferred to future work

Real internal SOPs are not public and cannot be reconstructed without breaching
confidentiality (S8.2). State the deferral positively:

> The corpus is synthetic and grounded in published guidance. The SOP schema in S4
> is the integration point: an agency holding real internal SOPs — with their
> actual queue ownership, verification steps, SLAs and escalation matrices —
> conforms them to this frontmatter and the system routes against them with no
> code change. What this project cannot demonstrate is whether real SOPs carry
> ambiguity of a kind the synthetic corpus does not model.

The last sentence is the honest limitation and should not be dropped.
