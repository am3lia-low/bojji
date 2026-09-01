# Calibrated Triage for Citizen Correspondence

**Demo video:** [URL — to be added]

> A bounded routing agent for citizen tax enquiries. It classifies intent,
> retrieves the relevant published guidance, drafts a reply where that is safe,
> and escalates where it is not. The contribution is not the drafting — it is the
> calibrated escalation mechanism, evaluated as a risk-coverage curve.

---

## 1. The problem

The question a public agency actually has is not "can AI draft replies to
citizens?" It is:

> What fraction of my inbox can I safely automate, and at what error rate?

Nobody can currently answer that, and it is the question that decides whether
anything ships. Existing routing systems use confidence thresholds picked by hand
— a common industry pattern is to fall back to a more capable model below a
confidence of 0.8 — but that number is almost never calibrated, and the coverage
and error rate it produces are almost never measured.

This project turns that arbitrary threshold into a defended one.

---

## 2. Scope, and why

Scoped to IRAS individual income tax (IIT) enquiries.

- IIT carries high enquiry volume and is the most self-contained of the tax types.
- The author has prior call-centre experience handling IIT enquiries, so the query
  distribution, phrasing patterns and escalation practice are known first-hand
  rather than assumed.
- The escalation boundary is operationally real, not invented: account-specific
  queries (activating GIRO, a specific estimated tax, a specific NOA amount)
  require a database lookup and therefore escalate. Generic guidance queries
  (which reliefs apply, when the GIRO cycle triggers) are answerable from
  published material.
- IIT has a single clean seasonal cycle — filing (Mar-Apr), estimates (May-Jun),
  NOAs (Jun-Jul) — giving a temporal axis for stratification and a concrete
  deployment risk.

Out of scope, deliberately: corporate tax, property tax, GST and stamp duty follow
different cycles and escalation rules. They are used instead as realistic
out-of-scope routing tests, alongside CPF-adjacent queries where citizens
genuinely confuse the two agencies. Correct behaviour for out-of-scope is a clean
redirect — a "no back door" policy — never a guess.

---

## 3. Architecture, and why this shape

### 3.1 This is the routing pattern, applied to its canonical use case

The system implements routing, one of the named workflow patterns in Anthropic's
engineering guide on building effective agents. Routing classifies an input and
directs it to specialized downstream processes, enabling separation of concerns
across distinct task categories. Anthropic's guide and LangChain's documentation
converge on the same taxonomy: prompt chaining, routing, parallelization,
orchestrator-workers, and evaluator-optimizer, plus an autonomous agent
architecture.

Routing is described in the pattern literature as a foundational design pattern in
agentic AI systems, in which a central router component analyses an incoming query
to determine its intent, category or type, and dispatches it to the appropriate
handler. Customer support triage is the textbook example of this pattern.

Intent classification followed by conditional dispatch is therefore not a bespoke
architecture but the standard implementation of a documented pattern, applied to
the use case it was documented for.

### 3.2 Why routing rather than a more autonomous pattern

Full autonomy is available and deliberately not used.

The pattern literature is explicit about the tradeoff: high-stakes workflows that
will be audited favour constrained patterns like chaining and routing, because
their execution paths are traceable end to end, whereas orchestrator-worker
architectures offer more reach at the cost of a wider blast radius when something
goes wrong.

Citizen tax correspondence is exactly such a workflow. An agent that decides its
own actions is both the wrong design for the domain and unevaluable — if the
action space is not fixed, there is no stable ground truth and no risk-coverage
curve. The contribution here is precisely the mechanism that decides when the
agent must not act.

### 3.3 Pipeline

```
mock inbox (JSON)
      |
      v
1. PII SCRUB  --------- local regex + street gazetteer
      |                 placeholders substituted before any external call
      v
2. CLASSIFIER --------- MiniLM-L6 fine-tuned, 12 classes, softmax head
      |                 LLM zero-shot baseline for comparison
      v
3. BUCKET ROLLUP ------ 12 classes -> 5 routing buckets, probabilities summed
      |
      v
4. CALIBRATION -------- temperature scaling on the summed distribution
      |
      v
5. SOP LOOKUP --------- dictionary built from SOP frontmatter
      |                 no vector search, no embeddings, no index
      v
6. ROUTER ------------- per-bucket thresholds + orthogonal flags
      |
      |---------------> AUTO-REPLY (template floor | Gemini ceiling)
      \---------------> HUMAN QUEUE (+ reason chip)
```

Orchestrated in LangGraph: explicit nodes, shared state, conditional edges.

**Why no vector search.** The corpus is 14 indexed SOPs and the class set is
closed; each SOP declares the intents it serves in its frontmatter, so the mapping
is complete by construction. Semantic search would add a failure mode upstream of
the escalation decision without adding capability. This is a reasoned choice, not
a measured one — a comparison against vector retrieval is listed under future work.

---

## 4. Data

### 4.1 Provenance

| Source | Use | Notes |
|---|---|---|
| IRAS IIT guidance pages | Factual reference for SOP authoring | Fetched to a gitignored scratch directory; **not redistributed** |
| CFPB Consumer Complaints (Hugging Face) | Register exemplars only | Real citizen writing; PII pre-redacted by publisher |
| Author-authored SOP and scenario specs | Corpus and email generation | Grounded in prior call-centre experience |

**The SOP corpus is authored, not scraped.** No agency publishes its internal
SOPs, so any honest version of this project must author them. Each SOP is a
synthetic officer-facing procedure whose every factual claim traces to a public
IRAS URL recorded in its frontmatter. Every file carries a banner marking it
synthetic; none reflects internal IRAS material, template or practice.

**Licensing.** IRAS Terms of Use restrict reproduction of site contents — and, read
literally, also require written permission to hyperlink to an internal page, which
places the document as boilerplate that is not observed in practice. This project
does not rely on it either way. The operative principle is that **copyright
protects expression, not facts**: tax rates, deadlines and thresholds are facts
stated in legislation. Pages were read as reference; only restatements with
citations are committed. Full detail in `data/SOURCES.md`.

### 4.2 Synthetic generation, and its defence

Emails are synthetic. Real citizen correspondence cannot ethically be used, and no
public corpus of Singapore government email enquiries exists.

Generation crosses three independent axes:

- Content — persona + life situation + relevant guidance. Never generated from the
  label name, to avoid vocabulary leakage.
- Style — standard English, imperfect English (typos, run-ons, all-caps), lightly
  Singlish-inflected. Register grounded on sampled real CFPB complaints.
- Season — filing / estimates / NOA periods.

Plus an edge-case slice: answerable only from held-out guidance, account-specific,
and author-recalled genuine edge cases.

Anti-leakage measures:
- Generated by a different model than the one that classifies
- Scenario specifications authored by a human with relevant call-centre experience
- Deliberate variation in length, tone and literacy level
- Fake NRICs only — no real identifiers, including the author's own

### 4.3 Representativeness — what this data does and does not cover

[To be completed after EDA. Must state honestly: synthetic ceiling, single agency,
single tax type, English-only, author-shaped distribution.]

---

## 5. Evaluation methodology and rationale

Chosen methods: **benchmarking + ablation + a bounded LLM-as-judge**.

| Measure | Method | Rationale |
|---|---|---|
| Classification | Macro-F1, per class, held-out test split | Baseline capability |
| Calibration | ECE, reliability diagrams, before/after | Confidence must be trustworthy before it can gate anything |
| Risk-coverage | Threshold sweep, curve, AURC, **per topic** | The decision an agency actually faces |
| Escalation quality | Accuracy per escalation reason | Richer than a blended number |
| `computation_requested` | Precision / recall | Gates the failure mode the design exists to prevent |
| Scrub recall | Planted-PII detection rate | Honest guardrail measurement |
| Draft groundedness | LLM judge, binary, + judge-human agreement | The drafter can paraphrase into error |
| Encoder vs LLM baseline | Accuracy, latency, size, cost, ECE | On-device viability |

**Results are reported per topic, not as a single inbox percentage.** An aggregate
figure depends on class volume mix, which is unpublished, varies seasonally and
cannot be ascertained; asserting one would be a fabricated denominator. Per-topic
coverage is also composable — an operator knows their own mix and can multiply
through. Automated redirects count toward coverage: under the no-back-door policy
a clean redirect is the correct outcome, not a failure.

**On the judge.** Scope is deliberately narrow: ~50 sampled drafts, one binary
question — *does this reply assert any fact not present in the provided SOP?* The
same 50 are reviewed by hand and **judge-human agreement is reported**. A narrow
question with a binary outcome and measured agreement is defensible; a broad
"which draft is better" score would not be. The judge is not the drafting model,
so no model is scored on its own output.

Ablations: calibrated vs uncalibrated - template vs LLM drafting - scrubbed vs
unscrubbed input - per-bucket vs single global threshold.

Ground truth is free by construction: emails are generated from known intents
against known SOPs, and unanswerable items are created by holding SOPs out of the
index.

---

## 6. Results

[To be completed. Write only after results exist — no claimed numbers before they
are measured.]

Headline format — **per topic, never a single inbox percentage**:
> Across N of 10 indexed enquiry types, the agent reaches >=P% routing precision
> at >=C% coverage within that type. Three types never auto-respond by policy.
> Two are unanswerable from the indexed corpus and escalate correctly. Aggregate
> inbox coverage depends on volume mix, which is not published and varies
> seasonally; per-type figures are reported so an operator can compute their own.

---

## 7. Model selection justification

[To be completed. Must justify on: confidence-signal availability, free-tier
operability, data residency, latency, cost at scale, on-device viability. Never on
"it was free" or "I had it available".]

**Runtime classification uses a fine-tuned encoder, not an LLM.** The operative
reason is the confidence signal. An LLM asked to classify returns text; extracting
probabilities requires logprobs, which are not always exposed, or repeated
sampling with agreement measurement. A fine-tuned encoder emits a softmax
distribution natively, which is what the calibration layer needs. An LLM zero-shot
classifier is retained as a comparison baseline across accuracy, latency, model
size, cost and calibration error.

This is not distillation — emails are generated from known intents, so labels
exist by construction and training is ordinary supervised fine-tuning.

**MiniLM-L6 (22M) is the primary classifier, not DistilBERT.** At ~90MB the
weights commit to this repository in plain git — under GitHub's 100MB limit, so
no git-lfs and no risk of a grader cloning pointer files instead of weights. This
removes the Hugging Face Hub dependency from the Docker build entirely: the
clean-machine run requires no network and no account. DistilBERT is retained as a second point on the
size/accuracy/calibration curve where time allows.

**Model roles are separated so that no model is scored on its own output.** The
email generator differs from the LLM classification baseline; the drafter
(Gemini) differs from the groundedness judge; the judge differs from the
generator.

**Free-tier compliance.** The assessment requires the *solution* to operate within
free-tier limits. The runtime path does: a local CPU encoder plus a free-tier
drafter. `MODEL_BACKEND=local` emits the SOP's approved phrasing directly and
requires no key at all; `MODEL_BACKEND=api` uses a free-tier Gemini key for
naturally worded replies and is what the demo shows.

Build-time steps (synthetic email generation) used paid API credits. This is a
data-preparation dependency, not part of the shipped system, and the generated
dataset, trained encoder weights and judge outputs are all committed so no grader
needs to re-run a paid step. Costs are documented in section 9.

---

## 8. Limitations

[To be completed honestly. Known items: synthetic data ceiling; scrub recall gap
on free-text addresses; single agency and tax type; English-only; author-shaped
query distribution; no live inbox validation.]

---

## 9. Deployment considerations (150-250 words)

[To be written. Must cover: target user and environment; projected inference cost
and compute footprint at scale; key post-deployment monitoring metrics; one
specific deployment risk.]

Candidate monitoring metrics: escalation rate over time · per-intent accuracy on
sampled human-reviewed cases · calibration drift as the recalibration trigger ·
routing accuracy · human intervention rate.

Candidate deployment risk: seasonal distribution shift. The system is calibrated
at one point in the tax cycle; query mix changes materially between filing,
estimates and NOA periods, and thresholds calibrated in one period may under- or
over-escalate in another.

---

## 10. Setup and execution

[To be completed. Must run from these instructions on a clean machine, with no
paid API key required.]

---

## 11. Development narrative

[To be completed: iterations, discarded strategies, tool selection rationale,
decision justification.]

Must include — prior work disclosure:

The author has prior public work implementing an LLM-orchestrated intent router
with a retrieval grounding layer. This project shares that scaffolding, which is
the standard routing pattern described in section 3.1, but the contribution —
calibration, consequence-weighted thresholds, risk-coverage analysis and the
encoder-versus-LLM comparison — is absent from that earlier work. A plain-language
fidelity guardrail project was considered and rejected during scoping precisely
because it would have duplicated the earlier contribution rather than extending
it.

Discarded strategies to document: benefits-matching assistant (duplicated shipped
government products, unbounded corpus) · dialect robustness benchmark (occupied by
existing national work) · contradiction detection across agency pages (expected
null result) · fine-tuning a drafting model (no gold references, competes with
calibration work) · live mailbox integration (privacy and reproducibility risk).

---

## 12. Coding agent usage

[To be completed: how agents were used, and the location of session logs in this
repository.]

---

## 13. Future improvements

- Live guidance refresh with effective-date metadata and re-indexing cadence
- Learning from officer corrections: few-shot pool updates, scheduled threshold
  recalibration, calibration-drift monitoring
- Fine-tuning a drafting model on officer-approved replies, once such a corpus
  exists
- Fully local generation, removing external API dependency entirely
- Multilingual support (Chinese, Malay, Tamil)
- NER-based PII detection for free-text addresses
- Mailbox integration, with its privacy implications
- Extension to other tax types with their own seasonal cycles
- Human-in-the-loop A/B evaluation in a live inbox
