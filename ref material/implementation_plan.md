# Implementation Plan — Calibrated Triage Agent for Citizen Correspondence

**Scope:** IRAS individual income tax (IIT) enquiries
**Timeline:** 5 days. Day 1 complete (scope, architecture, taxonomy). Now Day 2.
**Assessment:** GovTech Data Scientist Technical Assessment (AI Track)

> **Authority note.** `sop_design.md` is authoritative for the SOP corpus,
> taxonomy and routing buckets. `architecture.md` is authoritative for repository
> layout and model roles. This document is the plan of work; where it disagrees
> with either, they win.

---

## 1. One-line summary

A bounded LangGraph agent that classifies citizen email enquiries, looks up the
relevant SOP, drafts a reply where safe and escalates where not — where the
contribution is the **calibrated escalation mechanism**, evaluated as a
risk–coverage curve reported per topic, not the drafting.

---

## 2. Problem framing

**The question an agency actually has** is not "can AI draft replies to citizens".
It is: *what fraction of my inbox can I safely automate, and at what error rate?*

**A second, sharper framing surfaced on Day 1.** A substantial amount of IIT
guidance already exists on the IRAS website, but it sits several navigation levels
deep. Citizens email because they cannot find what is already published. That is
the friction the agent addresses, and it is worth stating explicitly in the README.

**Why IIT only.** High enquiry volume, the most self-contained tax type, and the
author has prior call-centre experience handling IIT enquiries, so the query
distribution and escalation practice are known first-hand. Other tax types follow
different cycles and become out-of-scope routing tests.

**Why bounded autonomy is the design, not a limitation.** Citizen correspondence
carries legal and financial consequence. Full autonomy is available and
deliberately not used. The contribution is the mechanism that decides when the
agent must *not* act.

---

## 3. Architecture

```
  mock inbox (JSON)
        |
        v
  1. PII SCRUB ............ local regex + street gazetteer
        |                   placeholders substituted before any external call
        v
  2. CLASSIFIER ........... MiniLM-L6, fine-tuned, 12 classes
        |                   softmax over a linear head
        v
  3. BUCKET ROLLUP ........ hand map: 12 classes -> 5 routing buckets
        |                   probabilities summed within bucket
        v
  4. CALIBRATION .......... temperature scaling on the summed distribution
        |
        v
  5. SOP LOOKUP ........... dictionary, built from SOP frontmatter `intents:`
        |                   NO vector search, NO embeddings, NO index
        v
  6. ROUTER ............... decide(bucket, calibrated_conf, flags)
        |                   per-BUCKET thresholds
        |
        +---> AUTO-REPLY ... template floor (SOP S4) | Gemini ceiling
        |
        +---> HUMAN QUEUE .. + escalation reason
```

Orchestrated in **LangGraph** — explicit nodes, shared state, conditional edges.
Chosen because high-stakes auditable workflows favour constrained patterns whose
execution path is traceable end to end.

---

## 4. Components

### 4.1 SOP corpus — authored, not scraped (Day 2, critical path)

**17 SOPs: 14 indexed, 3 held out.** Full inventory in `sop_design.md` S5.

- Author YAML specs in `data/sop_specs/`; `scripts/generate_sops.py` renders
  markdown into `data/sop/`.
- IRAS pages are fetched into `.scratch/` (**gitignored**) as generation input and
  never committed.
- Every factual claim traces to a public IRAS URL recorded in `references:`.
- Each file carries a synthetic banner.

**Licensing.** The constraint rests on copyright, not the IRAS Terms of Use.
Copyright protects expression, not facts; tax rates, deadlines and thresholds are
facts stated in legislation. Fetch widely; commit restatements with citations.
Full reasoning in `sop_design.md` S8.1.

**Confidentiality.** No real internal system names, queue identifiers, reference
codes, SLAs, internal wording or taxpayer data. `sop_design.md` S8.2.

### 4.2 Taxonomy — 12 classes, 5 buckets

Authoritative in `sop_design.md` S2–S3.

| Bucket | Classes |
|---|---|
| `auto_answerable` | `filing`, `tax_reliefs`, `assessment_and_amendment`, `payment`, `residency` |
| `requires_account_lookup` | `account_specific` |
| `high_consequence` | `hardship_or_waiver`, `scam_report` |
| `out_of_scope` | `oos_business_tax`, `oos_other_agency` |
| `no_supporting_sop` | `rental_income`*, `foreign_income_dta`* |

\* SOP authored but excluded from the index, so these are genuinely unanswerable.

**Orthogonal flags**, applied after the rollup: `computation_requested` (lexical,
**measured**), `multi_intent` (second-highest class probability above a
threshold), `under_specified` (KIV).

### 4.3 Synthetic email corpus (Day 3)

**~1,800 emails**, balanced across the 12 classes, split 50/20/30
(train / calibration / test). Frozen and committed.

Three axes crossed:

- **Content** — persona + life situation + SOP content. Never generated from the
  label name, to avoid vocabulary leakage.
- **Style** — standard English; imperfect English (typos, run-ons, all-caps);
  lightly Singlish-inflected, author-specified. Register grounded on sampled CFPB
  Consumer Complaints exemplars.
- **Season** — filing (Mar–Apr), estimates (May–Jun), NOA (Jun–Jul).

**Edge-case slice:** answerable only from held-out SOPs; account-specific;
computation-demanding; author-recalled genuine edge cases. Plus planted PII for
scrub-recall measurement.

**Balance matters more than before.** Under per-topic reporting every class gets
its own published number, so no class may be starved when the edge-case slice is
stratified in. Target ~45 test examples per class.

**Anti-leakage:** generated by a different model than the LLM classification
baseline; specs authored by a human; deliberate variation in length, tone and
literacy; fake NRICs only.

### 4.4 Classifier

| Model | Role | Runs | Cost |
|---|---|---|---|
| **MiniLM-L6 (22M)** | **primary runtime classifier** | local CPU | free |
| DistilBERT (66M) | KIV second point on the curve | local CPU | free |
| API LLM zero-shot | comparison baseline | build/eval | free tier |

**MiniLM is primary, not DistilBERT.** At ~90MB the weights commit to **plain
git** — under GitHub's 100MB limit, so no git-lfs and therefore no risk of a
grader cloning pointer files. This removes the Hugging Face Hub dependency from
the Docker build entirely: the clean-machine run needs no network and no account.

**Not distillation.** Emails are generated from known intents, so labels exist by
construction. This is ordinary supervised fine-tuning; naming it distillation
would be an overclaim.

**Free-tier scoping.** The *runtime* must be free: local encoder plus free-tier
drafter. *Build time* may use paid credits — dataset generation is a
data-preparation step, not part of the shipped system. The generated dataset and
trained weights are committed so no grader re-runs a paid step.

### 4.5 Confidence and calibration — the contribution

```
email -> MiniLM -> pooled embedding (384) -> linear head -> 12 logits
      -> softmax -> 12 probabilities -> summed into 5 buckets
```

The largest probability is the confidence, native to the architecture.

**Raw softmax is systematically overconfident** — a network reporting 0.95 may be
right 85% of the time. This is why an off-the-shelf 0.8 cutoff is unsound, and it
is the gap this project measures.

Fit **temperature scaling** on the calibration split (20%); report on the test
split (30%), never the calibration split. Metrics: **Expected Calibration Error**,
reliability diagrams, before and after.

**Temperature scaling, not isotonic — chosen on data volume.** The calibration
split is ~72 examples per bucket. Isotonic regression is non-parametric and would
overfit at that size; temperature scaling fits a single scalar. Isotonic is KIV.

For the LLM baseline: logprobs where exposed, otherwise self-consistency (sample
k, measure agreement) — provider-independent.

### 4.6 Router

```python
def route(email):
    scrubbed              = scrub(email)
    cls, probs            = classify(scrubbed)
    bucket, raw_conf      = rollup(probs)
    conf                  = calibrate(raw_conf)
    flags                 = detect_flags(scrubbed, probs)

    if bucket != "auto_answerable":       return HUMAN, bucket
    if "computation_requested" in flags:  return HUMAN, "computation_requested"
    if conf < THRESHOLDS[bucket]:         return HUMAN, "low_confidence"
    return AUTO_REPLY, None
```

**Thresholds are per bucket, not per class.** Three of five buckets escalate
regardless of confidence, so only `auto_answerable` and `out_of_scope` have a
threshold that bites. The earlier per-class formulation was authored in the Day-1
brainstorm, is required by nothing in the assessment, and is dropped. Sweeping a
global multiplier over `THRESHOLDS` generates the risk–coverage curve.

**Escalation reasons:** `requires_account_lookup`, `high_consequence`,
`out_of_scope`, `no_supporting_sop`, `computation_requested`, `low_confidence`.

### 4.7 PII handling — scrub, call, rehydrate

1. Local regex replaces PII with placeholders (`S1234567D` -> `[NRIC_1]`)
2. Scrubbed text goes to the classifier and any external call
3. Draft returns containing `[NRIC_1]`
4. Real values substituted back **locally**

Patterns: NRIC/FIN `[STFGM]\d{7}[A-Z]` with checksum, SG phone (8 digits starting
6/8/9), 6-digit postal codes, emails, dollar amounts, dates. Plus a street-token
gazetteer (Jalan, Lorong, Bukit, Taman, Avenue, Road, Crescent, Close, Walk, Rise,
Drive, Link) and block/unit patterns (`Blk 123 #04-56`).

**Measure and report scrub recall** against planted PII. Free-text addresses are
the known residual gap — state it rather than claim completeness.

### 4.8 Drafting — template floor, LLM ceiling

| Mode | Mechanism | Requires |
|---|---|---|
| `local` (default) | emit SOP S4 *Approved phrasing*, slots filled | nothing |
| `api` (demo) | **Gemini** rewrites for tone and register | free-tier key |

**No drafting model is fine-tuned** — no gold reference drafts, fuzzy evaluation,
and it would compete with the calibration day.

In `local` mode the reply is SOP text with slots filled, so it cannot assert a
fact absent from the SOP: groundedness holds by construction. `api` mode can
paraphrase into error, which is what the judge in S5 checks.

### 4.9 Demo UI

Streamlit, timeboxed to half a day. Three elements:

- Two queues side by side: auto-replied / needs-review
- A **reason chip** on every escalated item (`low confidence 0.61 < 0.75`)
- The risk–coverage plot with a **live threshold slider**

Runs in `api` mode so drafts are live.

---

## 5. Evaluation

**Methodology: benchmarking + ablation + a bounded LLM-as-judge.**

### 5.1 Reported per topic, not as an aggregate

An aggregate "X% of the inbox" depends on class volume mix, which is unpublished,
seasonal and unascertainable. Asserting one would be a fabricated denominator.
Per-topic coverage is also **composable** — an agency knows its own mix and can
multiply through. Full reasoning in `sop_design.md` S7.

Automated redirects **count** toward coverage: under the no-back-door policy a
clean redirect is the correct outcome, not a failure.

### 5.2 Metrics

| What | How | Level |
|---|---|---|
| Classification | macro-F1, per class | 12 classes |
| **Calibration** | ECE + reliability, before/after | 5 buckets |
| **Risk–coverage** | threshold sweep, curve, AURC | per topic |
| Escalation quality | accuracy per escalation *reason* | 6 reasons |
| `computation_requested` | precision / recall | flag |
| Scrub recall | planted-PII detection rate | — |
| Grounding accuracy | correct SOP within group | `tax_reliefs`, `payment` only |
| Draft groundedness | LLM judge, binary, + judge–human agreement | ~50 sampled drafts |
| Encoder vs LLM baseline | accuracy, latency, size, cost, ECE | — |

### 5.3 The judge

~50 sampled drafts, **one binary question**: *does this reply assert any fact not
present in the provided SOP?* The same 50 reviewed by hand, and **judge–human
agreement reported**. Narrow question, binary outcome, agreement measured — which
is what makes an LLM judge defensible rather than decorative.

**Judge must not be Gemini** (the drafter). **Groq** is the primary judge (free,
fast, different model family). **OpenAI** is a bonus second judge — eval-time,
paid, and droppable if budget bites.

Two judges plus the author's own labels give **three-way agreement** over the same
50 drafts. Agreement across all three makes the result solid; divergence is itself
reportable.

**Judge outputs are committed** to `eval/results/`, with model identifier and
date. A grader reads the judgments without re-running anything or holding a key.

### 5.4 Model separation rules

No model may be scored on its own output:

1. Email generator != LLM classification baseline
2. Drafter (Gemini) != judge
3. Judge != generator

### 5.5 Ablations

- Calibrated vs uncalibrated confidence
- Template vs LLM drafting
- Scrubbed vs unscrubbed input (does scrubbing cost accuracy?)
- Per-bucket vs single global threshold

Ground truth is free by construction: emails are generated from known intents
against known SOPs, and unanswerable items are created by holding SOPs out.

---

## 6. Day plan

| Day | Focus | Must finish |
|---|---|---|
| 1 ✅ | Scope, licensing, architecture, taxonomy | Design locked |
| **2** | 17 SOP specs -> generate SOPs; repo skeleton; agent-log capture | Corpus exists and validates |
| **3** | Email generation -> 1,800 frozen; leakage check; LangGraph end-to-end | Pipeline runs on real data |
| **4** | Train MiniLM, calibration, curves, ablations, judge | **The 30% is earned here** |
| **5** | Docker, README, demo video, logs, final commit | Submission complete |

**Cut order if slipping:** `multi_intent` flag → Singlish slice → DistilBERT
second point → scrub ablation → judge (fall back to template-only drafting, where
groundedness holds by construction). **Never cut calibration.**

---

## 7. KIV

- Vector search as a measured comparison against dictionary lookup
- DistilBERT as the second point on the size/accuracy/calibration curve
- `under_specified` flag
- TF-IDF + logistic regression leakage check (15 min, high value)
- Hand-written adversarial set (~30 emails) as an unbiased slice
- Full EDA: class balance, length distribution, inter-class vocabulary overlap
- **Reserve 3 hours of manual time for the demo video**
- Batch throughput demonstration (async, rate-limit aware)
- Interview prep: an answer on throughput and scaling architecture

---

## 8. Future improvements (for README)

- Live guidance refresh with effective-date metadata and re-indexing cadence
- Learning from officer corrections: few-shot pool updates, scheduled threshold
  recalibration, calibration-drift monitoring
- Fine-tuning a drafting model on officer-approved replies once such a corpus exists
- Fully local generation, removing the external API dependency
- Multilingual support (Chinese, Malay, Tamil)
- NER-based PII detection for free-text addresses
- Mailbox integration, with its privacy implications
- Extension to other tax types with their own seasonal cycles
- Human-in-the-loop A/B evaluation in a live inbox
- **Real internal SOPs conformed to the frontmatter schema** — the integration
  seam described in `sop_design.md` S12

---

## 9. Companion documents

- `architecture.md` — repository layout, the nine decisions it encodes, model roles
- `sop_design.md` — SOP corpus, taxonomy, buckets, licensing, reporting
- `README_draft.md` — README skeleton
- `deliverables_checklist.md` — full deliverables list from the assessment PDF
- `brainstorm_log.txt` — session log and decision history
