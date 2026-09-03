# Calibrated Triage for Citizen Correspondence

A triage agent for a tax authority's individual-income-tax inbox. It reads a
citizen's email, classifies the intent, looks up the governing internal procedure,
and either drafts a grounded reply or escalates to an officer with a stated reason.

**The contribution is not the drafting. It is knowing when not to draft.**

> **Demo video:** _[URL to be added before submission]_

---

## 1. The problem

An agency inbox is not one problem. It is a mixture of questions that a published
FAQ already answers, questions that require reading a specific taxpayer's record,
and questions where a wrong answer causes real harm — a citizen mid-fraud, or one
who cannot pay.

The naive framing is "use an LLM to answer citizen emails". That framing fails on
the only question an agency actually has, which is not *can it draft?* but:

> **What share of this inbox can I safely automate, and at what error rate?**

That is a coverage/risk trade-off, and it is a curve rather than a number. A system
that answers 100% of emails at 15% error is unusable in a public-sector context; one
that answers 35% at 9% error, and hands the rest to a human *with a reason attached*,
is deployable. This project is built around producing and defending that curve.

This is Annex A sketch 12 (triage agent for citizen emails), taken deliberately at
its hardest reading: **calibrated confidence and clean human escalation**, not
autocomplete for officers.

---

## 2. What it does

```
  mock inbox (JSON)
        |
        v
  1. PII SCRUB ......... local regex + gazetteer; placeholders substituted
        |                BEFORE any external call
        v
  2. CLASSIFIER ........ MiniLM-L6, fine-tuned, 10 classes, local CPU
        |
        v
  3. BUCKET ROLLUP ..... 10 classes -> 5 routing buckets
        |
        v
  4. CALIBRATION ....... temperature scaling on the bucket distribution
        |
        v
  5. SOP LOOKUP ........ CLASS_TO_SOPS[class] from SOP frontmatter
        |                no vector search, no embeddings
        v
  6. ROUTER ............ decide(bucket, calibrated confidence, flags)
        |
        +---> AUTO-REPLY .... Gemini, grounded in the retrieved SOP
        +---> REDIRECT ...... out-of-scope, still SOP-grounded
        +---> HUMAN QUEUE ... with an escalation reason
```

Orchestrated in **LangGraph**. The execution path is a declared graph rather than an
implicit consequence of control flow, so "what happened to this email" is answerable
by reading the edges.

**The escalation gate is structural.** An escalated item does not reach the drafting
node — not because of an early return inside the drafter that a later edit could
delete, but because *no edge leads there*.

---

## 3. Why this shape

**Routing, not autonomy.** The agent has one decision to make and no tools to call.
An autonomous pattern would add failure modes to the one path in the system that must
not have any. Constrained patterns whose path is traceable end to end are the right
shape for high-stakes public-sector workflows.

**An encoder, not an LLM, for classification.** This is the load-bearing model choice
and it is justified on operational grounds, measured rather than asserted (§6.3):

- **Calibratable confidence.** A softmax over a linear head is native to the
  architecture. Extracting a distribution from a text-generating model needs logprobs
  (not always exposed) or repeated sampling — and self-consistency at *k* samples can
  only ever express multiples of 1/*k*. Measured: **30 distinct confidence values vs 3.**
  When the threshold *is* the product, that resolution cap is disqualifying.
- **Latency and cost.** 0.67 s/email local CPU vs 10.6 s/email via API.
- **Data sensitivity.** The classifier never leaves the machine. Only the drafter
  makes an external call, and only ever on scrubbed text.
- **Deployment size.** MiniLM-L6 at ~88 MB commits to plain git under GitHub's 100 MB
  limit, so a grader cloning this repo gets real weights, not LFS pointers.

**Thresholds are per bucket, not per class.** At 3,000 emails a bucket carries ~110
test examples against ~90 for a class. Each number goes where its data supports it.

**Retrieval is a dictionary lookup.** 17 SOPs, ~100 KB. A vector store would buy
nothing and would put a similarity threshold immediately upstream of the escalation
decision. `CLASS_TO_SOPS` is built at startup by inverting the `intents:` line each
SOP declares — so routing policy lives in the corpus, not in code.

---

## 4. Data

### 4.1 Provenance

| Source | Use | Licensing / privacy |
|---|---|---|
| IRAS individual-income-tax guidance pages | Factual reference for authoring SOPs | Read as reference; fetched to a gitignored scratch dir, **not redistributed**. Only restatements-with-citations are committed. |
| CFPB Consumer Complaints (Hugging Face) | Register/style exemplars only | Public dataset; PII pre-redacted by the publisher. No text copied into the corpus. |
| Author-written SOP + scenario specifications | Corpus and email generation | Original work. |

**The SOP corpus is authored, not scraped.** No agency publishes its internal SOPs,
so any honest version of this project must author them. Each of the 17 SOPs is a
synthetic officer-facing procedure whose every factual claim traces to a public IRAS
URL recorded in its frontmatter — validated at startup, and `scripts/generate_sops.py
--check` fails the build if a citation does not resolve. Every file carries a banner
marking it synthetic. None reflects internal IRAS material, template, or practice.

**Licensing position.** Copyright protects expression, not facts: tax rates,
deadlines and relief caps are facts stated in legislation. Pages were read as
reference; nothing is reproduced.

### 4.2 Synthetic emails, and the defence for them

3,000 emails from **116 authored scenarios**, generated by GPT-4o. Real citizen
correspondence cannot ethically be used, and no public corpus of Singapore government
email enquiries exists.

The generation is structured to avoid the failure mode that makes synthetic data
worthless — a model learning the generator's tells rather than the intent:

- **The generator never sees the label.** It receives a *situation* description. The
  label is attached afterward from the scenario file. It cannot write toward a class name.
- **Three independent axes of variation:** content (persona + life situation), style
  (standard English, imperfect English with typos and all-caps, lightly Singlish-inflected),
  and season (filing / estimates / NOA periods).
- **Separation of models.** The generator (GPT-4o) differs from the zero-shot baseline
  and the judge (Groq/Qwen). No model in the evaluation path scores its own output.
- **Fake NRICs only**, checksum-valid but not issued.

`scripts/check_leakage.py` tests this rather than assuming it: a TF-IDF + logistic
regression probe should be *able* to classify but not perfectly (a near-perfect score
means a giveaway token exists). It also checks that no email contains the system's
own vocabulary.

### 4.3 What this data does not cover

Stated plainly, because it bounds every number below:

- **Situation breadth is the binding constraint, not size.** 3,000 emails come from
  116 situations, ~26 variants each. Per-class figures rest on ~90 test emails drawn
  from a handful of situations, so a class can look strong because its few situations
  are easy.
- **Synthetic ceiling.** This measures performance on a distribution the author and
  GPT-4o jointly imagined. It cannot tell you the real inbox looks like this.
- Single agency, single tax type, English-only (with Singlish inflection, not Chinese/
  Malay/Tamil).
- Splits are **grouped by scenario** — every variant of a situation lands in the same
  split, so the model is asked to generalise to unseen *situations*, not unseen
  paraphrases. This is stricter than a random split and lowers the headline numbers.

---

## 5. Evaluation methodology, and why

**Benchmarking + ablation + a bounded LLM-as-judge.** Three methods because they
answer different questions, and the primary metric is a curve, not a score.

**5.1 Risk–coverage, reported per topic.** The headline. Coverage is the share acted
on without a human (auto-replies *and* redirects — under a no-back-door policy a clean
redirect is the correct outcome, not a failure). Risk is the share of those automated
actions that were wrong. The curve is swept by scaling every threshold through 37
multipliers **using the real router**, not a reimplementation, so the published curve
cannot drift from the system it describes.

Reported **per topic, never as one inbox figure**: an aggregate depends on the class
volume mix, which is unpublished and seasonal. Per-topic coverage is composable — an
agency multiplies through its own mix.

**5.2 Calibration.** ECE plus reliability diagrams, before and after temperature
scaling. Fitted on a dedicated `calibration` split, reported on `test`. Fitting and
reporting on the same data would make the headline meaningless.

**5.3 Ablations.** Three, each isolating one design claim: does calibration change any
*decision* or only the ECE; do per-bucket thresholds beat one global number; does
scrubbing PII cost accuracy.

**5.4 Comparison.** Fine-tuned encoder vs LLM zero-shot with self-consistency, on the
same stratified sample with a **fixed label set** for both (deriving the label set from
the data makes the two macro-F1 figures averages over different denominators — a
0.11–0.22 discrepancy on identical predictions).

**5.5 LLM-as-judge — declared incomplete.** A Groq-hosted judge scores draft
groundedness, deliberately a different model family from the drafter. BUILD.md commits
to reporting judge–human agreement, because agreement is what makes an LLM judge
defensible rather than decorative. **That agreement figure has not been computed, so
no groundedness number is claimed here.** See §8.

---

## 6. Results

All figures: `test` split, n=877, seed 42. Regenerate with `python eval/run_eval.py`.
Committed to `eval/results/`. `summary.json` carries
`calibrated_numbers_reportable`, which is `true` only when the temperature is fitted
**and** `config/thresholds.yaml` declares itself fitted rather than placeholder.

### 6.1 Headline

| Metric | Value |
|---|---|
| macro-F1 (10 classes) | **0.859** |
| macro-F1 (5 buckets) | 0.917 |
| Bucket accuracy | 0.928 |
| **Must-escalate recall** | **0.961** (n=456) |
| Unsafe automations | 18 / 877 |
| AURC (overall) | 0.061 |
| Coverage @ operating point | **35.6%** at **9.0% risk** |
| PII scrub recall | 1.000 (99/99 planted values) |

### 6.2 Operating point, and how the thresholds were chosen

Two thresholds bite; three buckets escalate regardless of confidence. They are set
**independently**, because the buckets do not behave alike:

| threshold | `auto_answerable` risk | `out_of_scope` risk |
|---|---|---|
| 0.40 | 0.097 | 0.131 |
| 0.50 | 0.094 | 0.016 |
| 0.60 | 0.099 | 0.025 |
| 0.70 | 0.097 | 0.000 |

`auto_answerable` is **flat** — raising the cutoff removes coverage without removing
error, because the remaining errors are *confident* misclassifications that a
confidence threshold cannot see. Set at 0.50.

`out_of_scope` has a real knee — risk falls 8× between 0.40 and 0.50. Set at **0.65**.
The asymmetry is deliberate: a wrong redirect sends a citizen to an organisation that
cannot help them and has no record of them, which is harder to recover from than a
wrong-but-grounded answer.

### 6.3 Model selection, measured

n=30 stratified, k=3 self-consistency:

| | encoder | LLM zero-shot |
|---|---|---|
| accuracy | **0.800** | 0.533 |
| macro-F1 | **0.809** | 0.540 |
| ECE | 0.169 | **0.073** |
| sec/email | **0.67** | 10.6 |
| distinct confidence values | **30** | 3 |
| API calls | **0** | 90 |

The encoder wins on accuracy, latency and cost. The LLM's better ECE is real and
reported — but it is computed over **3 distinct confidence values**, which is the
resolution cap at 1/*k*. No amount of data removes it, and it is the operational
argument for an encoder when the threshold is the product.

### 6.4 Ablations

| Question | Result |
|---|---|
| Does calibration change any decision? | ECE 0.1507 → 0.1502; AURC 0.0607 → 0.0613. **Essentially nothing.** |
| Do per-bucket thresholds beat one global? | AURC 0.0613 per-bucket vs 0.0584 global |
| Does scrubbing PII cost accuracy? | macro-F1 0.8593 scrubbed vs 0.8582 raw (**−0.0011**) |

**The calibration ablation is a negative result and is reported as one.** The fitted
temperature is 0.998 — essentially the identity. The retrained model is already
well-calibrated at the bucket level, so temperature scaling has almost nothing to
correct. The *architecture* for calibrated routing is sound and the machinery works;
the *correction* is currently near-zero. Claiming calibration as the win would be
overclaiming. The defensible claim is the resolution argument in §6.3.

The threshold ablation is also honest: a single global 0.5 scores marginally better on
AURC. Per-bucket thresholds are kept because AURC integrates over the whole curve
while the operating point is what ships, and at the operating point the `out_of_scope`
knee is worth 8× risk reduction.

### 6.5 Safety guarantees, verified

The always-escalate invariant is enforced in **two independent places** — the router's
logic and a pydantic validator on `RoutingDecision` — so a future edit that breaks the
router raises rather than silently auto-replying. Verified exhaustively over the full
power set of flags × confidences, and on real data grouped by predicted class:

```
predicted class      n    automated
hardship_or_waiver   80   ->   0
scam_report          84   ->   0
foreign_income_dta   87   ->   0
rental_income        80   ->   0
```

331 of 877 emails land in a class that must never be automated, and none of them was.
(`account_specific` is absent because it is a flag rather than a class — it escalates
64 emails as a *reason*, across every topic.)

---

## 7. Setup and execution

Requires Python 3.11+. Verified on Windows 11 / Python 3.14. **No Dockerfile yet** —
see §8.

```bash
git clone <repo-url> && cd <repo>
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env          # add GEMINI_API_KEY for drafting (free tier)

python -m pytest              # 387 tests
python eval/run_eval.py       # regenerates eval/results/
streamlit run app/streamlit_app.py
```

**The pipeline runs with no API key at all.** Classification, calibration, retrieval
and routing are entirely local. A missing or rate-limited key means every auto-reply
records a drafting failure and escalates *carrying its SOP* — the designed path, not a
crash.

**Free-tier note.** Gemini's free drafting quota is a *daily* budget. `.env` supports
`GEMINI_API_KEY_2` and `_3`; the client rotates on 429 and continues. Rotation fires
only on rate limit — a timeout would fail identically on the next key.

---

## 8. Limitations

Stated rather than defended away.

- **The judge–human agreement figure is not computed**, so no groundedness number is
  claimed. `eval/results/drafting.json` reads `{"skipped": true}`. Drafting availability
  and grounding accuracy require Gemini quota this build ran out of.
- **Calibration is currently a near-no-op** (T=0.998). See §6.4.
- **Scam detection is the weakest guarantee.** The lexical flag has precision 1.000
  (zero false positives on all 3,000 emails), but recall is **0.827 corpus-wide** —
  not the 0.952 the test split alone reports. The 52 misses describe the *event*
  without ever naming it ("a man called saying I'd be arrested"), and the most
  distressed citizen is the least likely to write "scam". An LLM second pass is the
  right instrument; regex cannot reach these. Note this bounds *misfile* risk only: a
  correctly classified scam report escalates on its bucket without consulting the flag.
- **PII scrubbing is regex + gazetteer**, deliberately a stand-in for an offline NER
  model. Recall is 1.000 on *planted* values — which measures detection of shapes the
  generator knew to plant, not of everything a citizen might write. Addresses with
  neither a block number nor a street-type token are unreachable; conversely
  "Jalan Besar station" can over-scrub.
- **Per-topic risk is keyed on the TRUE class**, so a row like `account_specific`
  showing risk 1.0 is a *classifier misfile rate*, not a routing failure.
- **116 situations is the binding constraint** (§4.3).
- `data/SOURCES.md` and the Dockerfile are referenced by this README but **not yet
  written** — see the repo tree before relying on them.

---

## 9. Deployment considerations

**Target user and environment.** The user is a correspondence officer, not a citizen:
the interface is a two-queue review screen, and the output is a routing decision plus
a draft an officer approves. It sits inside an agency network — classifier on
on-premise CPU, only scrubbed text crossing the boundary to a drafting API.

**Compute footprint at scale.** The classifier is 88 MB at ~0.67 s/email on one CPU
core, so 100k emails/year is a few CPU-hours and no GPU. Cost is entirely in drafting:
at ~35% coverage that is ~35k API calls/year — inside free-tier limits at this volume,
low four figures annually at commercial rates. Retraining takes ~11 minutes on CPU.

**Post-deployment monitoring.** Four signals: **calibration drift** (rolling ECE
between claimed confidence and officer-confirmed correctness — the leading indicator
that thresholds need refitting); **escalation-reason mix**, since a shift means the
inbox has changed shape; **officer override rate** on auto-replies, the closest thing
to production ground truth; and **drafting availability**, a supplier-risk metric.

**A specific risk: seasonal distribution shift.** The inbox is not stationary. Filing
season, NOA issuance and payment deadlines each spike volume with a different class
mix. A threshold fitted off-peak will be mis-set exactly when volume is highest and
automation matters most — and because temperature scaling is monotonic, the failure is
silent: accuracy looks unchanged while confidence stops meaning what it did.
Mitigation is seasonal recalibration on a rolling window, plus alerting on the
confidence *distribution* rather than its mean.

---

## 10. Development narrative

The build log with full decision history is `ref material/BUILD.md`. In brief:

**What changed along the way.** The taxonomy was **reshaped from 12 classes to 10**
mid-build: `oos_business_tax` and `oos_other_agency` were merged (they shared a bucket
*and* an action, so the split bought nothing downstream, and the classifier could not
separate them — one scored F1 0.000 with half its errors landing on its sibling), and
`account_specific` was **demoted from a class to a flag**. That second change is the
more interesting one: being about your own record is a property an enquiry *has*, not
a topic it is *about* — "how do instalments work" and "what is the status of my
instalment plan" differ by one possessive. Topical vocabulary dominated the one or two
tokens carrying the actual signal, so as a class it failed; as a lexical flag consulted
before any confidence, it works.

Two precisions are reported for that flag and they answer different questions. Raw
detection is **P 0.495 / R 0.844** (`flags.json`) — but 39 of its 55 false positives
land on classes that escalate regardless, where the flag costs nothing. Measured as an
*escalation reason*, where a false positive actually changes an outcome, it is
**P 0.771 / R 0.844** with 16 false positives (`escalation.json`) — a real coverage
cost of 1.8% of the inbox.

**Discarded strategies.** A vector store for SOP retrieval (17 documents — nothing to
buy, and a similarity threshold immediately upstream of the escalation decision is a
failure mode you don't want). A standalone street-address regex (it fired on 80+
non-address phrases like "is there any way" — the gazetteer's English members are
ordinary words). Isotonic regression for calibration (non-parametric, would overfit
646 examples).

**Things that broke and what they taught.** Two free-tier models were *withdrawn*
mid-build — Groq's `llama-3.3-70b` and Gemini's `gemini-2.0-flash`, both returning 404.
They failed differently, and that contrast shaped the design: the Groq withdrawal was
silent (dropped samples fell back to a uniform distribution, so numbers were quietly
wrong), while the Gemini one was loud (drafting has an explicit failure path, so items
escalated with their SOPs and the error was recorded on the state). That is why the
model identifier is stamped into every result file and why the drafter has **no
template fallback** that would mask an outage.

**Tool selection.** LangGraph for the traceable execution path. MiniLM-L6 over
DistilBERT on deployment size. Gemini for drafting and Groq for judging, chosen from
different families so no model is scored on its own output. GPT-4o for generation
only — build-time and paid, with its output frozen and committed so no grader re-runs
a paid step.

---

## 11. Coding agent usage

This project was built with **Claude Code** (Claude Opus) as a pair-programming and
audit partner, used in three distinct modes:

1. **Implementation.** Most module code and tests were drafted with the agent against
   a design I specified in `BUILD.md`, then reviewed and corrected by me.
2. **Adversarial audit.** The agent was asked to attack its own output — probing
   invariants exhaustively rather than reading them. This is where the highest-value
   findings came from, each reproduced at the command line before being fixed:

   - an **ordering bug** in the PII patterns — `block_unit` consumed "Blk 857" first,
     stranding the street name where no later pattern could reach it. Every planted
     address leaked its street. Scrub recall still read 1.000, because the metric
     asked whether the *whole* planted string survived verbatim, and a partly-scrubbed
     address does not.
   - a **postcode lookahead** that rejected any trailing `.` or `,`, so
     `postcode 648913.` leaked while `postcode: 624108?` scrubbed. It dropped over half
     the planted postcodes on the corpus of the day.
   - a **citation parser** taking the *first* `CITED:` line rather than the last, which
     both recorded the wrong SOP against the grounding metric and shipped internal SOP
     identifiers into citizen-facing text.
   - a **stale eval metric**: after `account_specific` became a flag,
     `expected_reason()` could no longer return it, so all 70 correct escalations
     scored as false positives against a support of zero.
3. **Verification.** Every claim in this README that carries a number was reproduced at
   the command line before being written down.

Where the agent and I disagreed, the disagreement is recorded in `BUILD.md` rather than
silently resolved — including one case where I asked it to broaden PII detection and
the measurement showed the change would damage classifier input for no real gain.

**Session logs** are in `AI assistant logs/`.

---

## 12. Future improvements

- **An LLM second pass for scam detection.** The one place a generative model earns its
  unreliability: rare class, short text, and it need only run on emails the encoder did
  *not* route to `scam_report`, so the spend is bounded.
- **An offline NER model for PII**, replacing the regex set. The config-driven design
  means this is an implementation swap behind `Scrubber`, not a pipeline change.
- **More situations, not more variants.** Another ~100 authored scenarios would buy
  more than doubling the variants of the existing ones, and would widen the calibration
  split — currently the binding constraint on the temperature fit.
- Real anonymised enquiries as a validation-only slice, to test whether the synthetic
  situation set resembles the real distribution — the one thing this project cannot
  currently check about itself.
- Learning from officer corrections: scheduled threshold recalibration and
  calibration-drift monitoring.
- Multilingual support (Chinese, Malay, Tamil).
