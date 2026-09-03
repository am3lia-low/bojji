# Build Design — Calibrated Triage Agent for Citizen Correspondence

**Scope:** IRAS individual income tax (IIT) enquiries
**Timeline:** 5 days. Day 1 complete (scope, architecture, taxonomy).
**Assessment:** GovTech Data Scientist Technical Assessment (AI Track)

> **Authority.** `sop_design.md` is authoritative for the SOP corpus, taxonomy,
> routing buckets, licensing, confidentiality and result reporting. This document
> is authoritative for repository layout, model roles, runtime behaviour and the
> plan of work. Where this document touches a `sop_design.md` topic it states the
> *consequence* for the build and points at the section, rather than restating it.
>
> Supersedes `architecture.md` and `implementation_plan.md`, which it merges.

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

**A sharper second framing.** A substantial amount of IIT guidance already exists
on the IRAS website, but it sits several navigation levels deep. Citizens email
because they cannot find what is already published. That is the friction the agent
addresses, and it belongs in the README.

**Why IIT only.** High enquiry volume, the most self-contained tax type, and the
author has prior call-centre experience handling IIT enquiries, so the query
distribution and escalation practice are known first-hand. Other tax types follow
different cycles and become out-of-scope routing tests.

**Why bounded autonomy is the design, not a limitation.** Citizen correspondence
carries legal and financial consequence. Full autonomy is available and
deliberately not used. The contribution is the mechanism that decides when the
agent must *not* act.

---

## 3. The pipeline

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
  3. BUCKET ROLLUP ........ BUCKET[class]: 12 classes -> 5 routing buckets
        |                   probabilities summed within bucket
        v
  4. CALIBRATION .......... temperature scaling on the summed distribution
        |
        v
  5. SOP LOOKUP ........... CLASS_TO_SOPS[class], built from frontmatter `intents:`
        |                   NO vector search, NO embeddings, NO index
        v
  6. ROUTER ............... decide(bucket, calibrated_conf, flags)
        |                   per-BUCKET thresholds
        |
        +---> AUTO-REPLY ... Gemini, grounded in the retrieved SOP
        |
        +---> HUMAN QUEUE .. + escalation reason
```

Orchestrated in **LangGraph** — explicit nodes, shared state, conditional edges.
Chosen because high-stakes auditable workflows favour constrained patterns whose
execution path is traceable end to end.

Both maps are built at startup by reading SOP frontmatter. They live in the
corpus, not in code. Full pipeline semantics: `sop_design.md` S1.

---

## 4. Repository layout

```
citizen-triage-agent/            # anonymous repo name — no agency, no role
├── README.md                    # THE primary artifact (graded)
├── Dockerfile
├── docker-compose.yml
├── Makefile                     # make data | train | eval | demo | test
├── pyproject.toml               # deps + ruff/mypy/pytest config
├── .env.example                 # GEMINI_API_KEY (runtime) + GROQ_API_KEY (eval)
├── .dockerignore .gitignore
│
├── config/                      # ← the thesis lives here, as data not code
│   ├── taxonomy.yaml            # intents + escalation policy per class
│   ├── thresholds.yaml          # per-bucket threshold + `justification:` string
│   ├── models.yaml              # backend registry (local | api)
│   └── pii_patterns.yaml        # regex set + street gazetteer
│
├── src/triage/                  # RUNTIME — free-tier keys only (Gemini)
│   ├── schemas.py               # pydantic: Email, TriageState, Decision, Draft
│   ├── graph.py                 # LangGraph assembly: nodes + conditional edges
│   ├── nodes/                   # one file per node, each pure(state) -> state
│   │   ├── scrub.py  classify.py  calibrate.py
│   │   └── retrieve.py  route.py  draft.py
│   ├── models/
│   │   ├── base.py              # Classifier Protocol: predict -> (label, probs)
│   │   ├── encoder.py           # MiniLM-L6 (primary); DistilBERT (KIV 2nd point)
│   │   ├── llm_zeroshot.py      # comparison baseline
│   │   └── calibration.py       # temperature scaling; fit() / apply()
│   ├── sop/
│   │   ├── loader.py            # parse data/sop/*.md frontmatter
│   │   └── index.py             # intent -> sop_id mapping
│   ├── pii/
│   │   ├── scrubber.py          # scrub / rehydrate, placeholder vault
│   │   └── nric.py              # NRIC checksum validation
│   └── llm/
│       ├── client.py            # provider-agnostic; MODEL_BACKEND switch
│       └── prompts/             # versioned templates, one file each
│
├── data/
│   ├── SOURCES.md               # provenance · licence · robots · fetch date
│   ├── sop_specs/               # human-authored SOP specs (YAML) — the real input
│   ├── sop/                     # THE CORPUS — generated markdown + frontmatter
│   ├── scenarios/               # human-authored email generation specs (YAML)
│   ├── generated/emails.jsonl   # frozen, committed
│   └── splits/                  # train/calib/test ids — seeded, committed
│
├── scripts/                     # BUILD-TIME ONLY — never imported by src/
│   ├── fetch_reference.py       # IRAS pages -> .scratch/ (GITIGNORED, never committed)
│   ├── generate_sops.py         # spec + reference -> data/sop/*.md
│   ├── generate_emails.py       # may use paid API
│   ├── train_encoder.py         # headless equivalent of the notebook below
│   ├── fit_calibration.py
│   └── check_leakage.py         # 7 fairness checks; gates training
│
├── models/                      # weights + the notebook that produced them
│   ├── 01_dataset_eda_and_training.ipynb   # EDA -> fairness checks -> training
│   ├── all-MiniLM-L6-v2/        # base encoder, vendored (no Hub at run time)
│   └── classifier/              # fine-tuned: model.pt, labels.json, training.json
│
├── eval/                        # 30% of the grade — first-class, not a notebook
│   ├── run_eval.py              # single entrypoint -> eval/results/
│   ├── metrics/
│   │   ├── classification.py    # macro-F1, per-class
│   │   ├── calibration.py       # ECE, reliability diagram
│   │   ├── risk_coverage.py     # threshold sweep, AURC
│   │   └── pii_recall.py        # planted-PII detection rate
│   ├── ablations/
│   └── results/                 # committed JSON + PNG — README cites these
│
├── app/streamlit_app.py         # view only: two queues, reason chips, SOP pane, slider
│
├── tests/
│   ├── test_router.py           # highest-value: the escalation logic
│   ├── test_scrubber.py
│   ├── test_calibration.py
│   ├── test_draft_failure.py    # failed draft escalates, keeps auto_reply_intended
│   └── test_graph_smoke.py
│
├── docs/
│   ├── DEVELOPMENT_NARRATIVE.md  MODEL_SELECTION.md
│   └── DEPLOYMENT.md             LIMITATIONS.md
│
└── agent_logs/                  # .jsonl sessions + README pointing at them

.scratch/                        # GITIGNORED. Fetched IRAS reference pages live
                                 # here as generation input and are never committed.
```

### 4.1 What the layout encodes

**Thresholds and taxonomy are YAML, not constants.** `config/thresholds.yaml`
carries a `justification:` string per routing bucket. The escalation policy must
be readable in one file, diffable in git, and changeable without touching code.

**A hard wall between `scripts/` and `src/`.** `scripts/` is build-time and may
use paid APIs for corpus and email generation. `src/` is runtime and reaches only
free-tier backends (Gemini for drafting). The separation keeps generation cost out
of the deployed path and keeps the runtime reproducible on a grader's own free key.

**The training notebook lives with the weights, not in a `notebooks/` folder.**
`models/01_dataset_eda_and_training.ipynb` sits beside the artefacts it produces, so
a reader who opens `models/` finds the weights *and* the record of how they were
made: the dataset audit, the fairness checks that gated training, the loss curve,
and the epoch where overfitting began. Separating them would leave a binary blob
with no visible provenance.

The notebook and `scripts/train_encoder.py` do the same work for different
audiences -- the notebook is where the decisions are legible, the script is what a
Makefile target or a clean-machine rebuild calls. Neither defines the architecture:
both import `triage.models.head`, which is also what the runtime loads, so a
notebook run and a script run cannot train differently shaped models.

**`eval/results/` is committed.** The README cites files there, never remembered
numbers. This is the structural guard against the code–writeup mismatch failure
mode (`deliverables_checklist.md` K).

**Streamlit holds no logic.** `app/` calls the graph and reads `eval/results/`.
Nothing is computed there that isn't computed in the pipeline, so the demo cannot
drift from the measured system.

**SOP storage is a flat directory** loaded and validated into memory at startup.
At ~17 documents and ~100KB there is no vector DB, no external service and no
index to rebuild. This is a large part of why the free-tier constraint is
satisfiable at all, and should be stated in the README rather than left implicit.

---

## 5. Components

### 5.1 SOP corpus — authored, not scraped (Day 2, critical path)

**17 SOPs: 14 indexed, 3 held out.** Inventory, contents, worked example,
licensing, confidentiality and the generation pipeline: `sop_design.md` S4–S5, S8.

Build consequences:

- Author YAML specs in `data/sop_specs/`; `scripts/generate_sops.py` renders
  markdown into `data/sop/`.
- IRAS pages fetch into `.scratch/` (**gitignored**) as generation input, never
  committed. Committing only derived text keeps this licensing-clean.
- One file per SOP makes deterministic `intent -> sop_id` lookup auditable, gives
  effective-date and supersession complexity for free, and makes the holdout a
  matter of excluding files from the index rather than an arbitrary cut.
- Register: semi-formal, internal, officer-facing. Terse and bullet-heavy —
  `if X -> do Y`, canned phrasing blocks, explicit escalation triggers. Not
  legalese.
- The human review pass (~1.5h) is not optional: it is where the public-URL
  traceability guarantee is actually enforced.

**Effort:** ~2 hours of authoring, against a day or more of scraping, parsing and
chunking that the abandoned plan put on the critical path.

**The misrepresentation guard.** Every file carries a synthetic banner, and the
README states plainly — prominently, not buried in limitations — that the SOPs are
authored for this project, structured as a plausible officer-facing procedure,
factually grounded in public IRAS guidance, and reflect no internal IRAS material,
template or practice.

### 5.2 Taxonomy — 12 classes, 5 buckets

Authoritative: `sop_design.md` S2–S3, including the granularity principle, the
orthogonal flags and their detection mechanisms.

**The taxonomy is designed around the SOPs, not the other way round.** This is a
build-order constraint, not a preference — see S8.

Build consequences:

- `CLASS_TO_SOPS` is a dictionary lookup built at startup from SOP frontmatter
  (`intents:`). **No vector search, no embedding model, no index** — one less
  failure mode upstream of the escalation decision, and one less thing to debug.
- `BUCKET` is likewise derived, from `auto_reply_permitted` and `escalate_if`.
  Escalation policy is corpus-derived, not hardcoded.
- All the difficulty concentrates in the classifier, which is where the
  calibration contribution lives.
- Ground truth stays free.

**Metric consequence:** class -> SOP group is correct by construction and is not
measured. Within-group selection by the drafter *is* measurable (grounding
accuracy) but applies to only 2 of 12 classes, so it is secondary. The headline is
the risk–coverage curve, reported per topic.

### 5.3 Synthetic email corpus (Day 3)

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

**Balance is correct here, not a compromise.** Under per-topic reporting every
class gets its own published number, so equal statistical power per topic is
exactly what is wanted, and no class may be starved when the edge-case slice is
stratified in. Target ~45 test examples per class. Reasoning: `sop_design.md` S7.

**Anti-leakage:** generated by a different model than the LLM classification
baseline; specs authored by a human; deliberate variation in length, tone and
literacy; fake NRICs only.

Deliberate messiness to inject — supersession, cross-document dependency,
overlapping scope, a dangling reference: `sop_design.md` S10.

### 5.4 Classifier

| Model | Role | Runs | Cost |
|---|---|---|---|
| **MiniLM-L6 (22M)** | **primary runtime classifier** | local CPU | free |
| DistilBERT (66M) | KIV second point on the curve | local CPU | free |
| API LLM zero-shot | comparison baseline | build/eval | free tier |

**MiniLM is primary, not DistilBERT.** At ~90MB the weights commit to **plain
git** — under GitHub's 100MB hard limit, so no git-lfs and therefore no risk of a
grader cloning pointer files instead of weights and hitting a confusing failure.
This removes the Hugging Face Hub dependency from the Docker build entirely: the
clean-machine run needs no network and no account. Check the real size after
training; use LFS only if it exceeds the limit, and document the install step if
so. DistilBERT (66M, ~250MB) is KIV as the second point on the
size/accuracy/calibration curve if time allows.

**Classifiers sit behind a Protocol.** `models/base.py` defines
`predict(text) -> (label, probs)`. The encoder and the LLM baseline both satisfy
it, so the ablation harness swaps them with no special-casing, and the calibration
layer is written once.

**Not distillation.** Emails are generated from known intents, so labels exist by
construction. This is ordinary supervised fine-tuning; naming it distillation
would be an overclaim.

**Free-tier scoping.** The *runtime* must be free: local encoder plus free-tier
drafter. *Build time* may use paid credits — dataset generation is a
data-preparation step, not part of the shipped system. The generated dataset and
trained weights are committed so no grader re-runs a paid step.

### 5.5 Confidence and calibration — the contribution

```
email -> MiniLM-L6 encoder -> pooled embedding (384 dims)
                           -> linear head -> 12 logits
                           -> softmax     -> 12 probabilities, sum to 1
                           -> summed into 5 buckets
```

The largest probability is the model's confidence. It is native to the
architecture — the linear head is added at fine-tuning time.

**Raw softmax is systematically miscalibrated.** The textbook case is
overconfidence — a network reporting 0.95 that is right 85% of the time — and it is
the case this document assumed while the design was being written. Either way, an
off-the-shelf 0.8 cutoff is unsound, and the gap is what this project measures.

**Measured on this corpus, the error runs the other way, and the correction is
therefore the opposite of the one anticipated.** Recorded here rather than quietly
reworded, because the assumption was load-bearing in the design and a writeup that
still asserted overconfidence would contradict its own artefacts:

| | |
|---|---|
| Mean confidence, test split | **0.363** |
| Actual accuracy, test split | **0.612** |
| Direction | **under**confident by 0.249 |
| Fitted temperature | **0.683** (below 1.0, so it *sharpens*) |
| ECE, calibration split | 0.288 -> 0.168 |

Small fine-tuned encoders on modest data are often underconfident rather than
overconfident: 879 training examples across 12 classes leaves the head hedging
across several plausible labels, and the softmax stays flat.

**The argument for the contribution survives this intact, and is arguably
strengthened.** The strongest evidence for calibrating rather than guessing is not
that raw confidence is too high — it is that **its direction cannot be assumed at
all**. Concretely, on this system: no test prediction exceeds **0.738**, so a
conventional 0.8 cutoff would have escalated **100% of the inbox** and delivered
zero coverage. The threshold has to be chosen from a fitted curve, which is exactly
what the risk–coverage sweep produces.

Correction, fitted on the 20% calibration split and applied to the summed bucket
distribution:

| Method | Shape | Status |
|---|---|---|
| **Temperature scaling** | divide logits by one learned scalar before softmax | **implemented** |
| Isotonic regression | non-parametric monotonic map, raw -> corrected | KIV |

**Temperature scaling is chosen on data volume, not convenience.** The calibration
split is ~360 examples across 5 buckets — roughly 72 per bucket. Isotonic
regression is non-parametric and would overfit at that size; temperature scaling
fits a single scalar. Isotonic becomes worth revisiting only if the dataset grows.

Fit on the calibration split; report on the **test** split, never the calibration
split. Metrics: Expected Calibration Error plus reliability diagrams, before and
after. The threshold sweep over corrected confidence produces the risk–coverage
curve.

For the LLM baseline: logprobs where exposed, otherwise self-consistency (sample
k, measure agreement) — provider-independent.

**This is the operational argument for an encoder over an LLM classifier.** An LLM
asked to classify returns text; extracting probabilities needs logprobs (not
always exposed) or repeated sampling with agreement measurement. The encoder emits
a calibratable distribution natively. Feeds the model-selection deliverable.

### 5.6 Router

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
threshold that bites. Sweeping a global multiplier over `THRESHOLDS` generates the
risk–coverage curve. Per-class overrides may be added later only where a specific
consequence justifies one.

**Escalation reasons:** `requires_account_lookup`, `high_consequence`,
`out_of_scope`, `no_supporting_sop`, `computation_requested`, `low_confidence`.

**`no_supporting_sop` is derived, not hand-mapped.** The router checks whether
`CLASS_TO_SOPS[class]` came back empty rather than reading a hand-written bucket
entry. One source of truth, and holding out a further SOP later needs no code
change.

**Redirects count as coverage.** `out_of_scope` produces an automated redirect.
That is an automated action, so it counts toward per-topic coverage — consistent
with the "no back door" policy, where a clean redirect is the correct outcome
rather than a failure.

### 5.7 PII handling — scrub, call, rehydrate

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

### 5.8 Drafting — Gemini, grounded in the SOP

**Gemini (free tier) is the drafter.** It is given the retrieved SOP and the
scrubbed email, and writes the reply in the citizen's register while staying
inside the SOP's approved phrasing.

There is deliberately **no template fallback**. An earlier version of this
document required the runtime to work with *no API key of any kind* and kept the
SOP S4 block as a zero-dependency floor. That constraint was self-imposed and
stricter than the assessment asks: the deliverable is *free-tier operation*
(`deliverables_checklist.md` A), which a free Gemini key satisfies directly. The
floor bought a second drafting path, a second thing to document and a second way
for the demo to diverge from the measured system.

**Failure is surfaced, not absorbed.** If the Gemini call rate-limits, times out
or errors, the item does not receive a degraded draft. It is routed to the human
queue carrying the failure as its escalation reason. A visible failure is the
honest outcome; a quietly worse reply is not. Free-tier rate limits are real and
will fire during an eval sweep, so this path is exercised rather than
hypothetical.

**Who sees the failure.** Not the citizen — they are waiting on a reply and their
email simply stays queued. The audience is the **officer working the review
queue**, so the failure is a queue-side signal, not an error page.

**The officer receives a workable item, not a dead one.** Drafting is the last
node in the chain, so everything upstream has already succeeded when it fails.
The item is handed over with:

- the predicted class and its calibrated confidence
- **the retrieved SOP, rendered in full** — the officer writes the reply from the
  same source the drafter would have used, so the failure costs a paraphrase, not
  the research
- the failure reason as an escalation chip (`draft failed: rate limit`)

This is the argument for surfacing over degrading. A degraded template reply hides
that anything went wrong; a flagged item plus its SOP is strictly more useful than
either a silent fallback or a bare error.

**Two invariants this must not break:**

1. **Drafting failure is not a routing signal.** A rate-limit says nothing about
   whether the email was safe to auto-reply. The item must not be relabelled
   low-confidence, or a Gemini outage would leak into the risk–coverage curve —
   the headline result. It is recorded as `auto_reply_intended=True` with
   `draft_status=failed`, so evaluation can separate *the router declined* from
   *the drafter broke*.
2. **Eval treats a failed draft as missing, not wrong.** There is no text to
   score, so the item leaves the groundedness denominator (S6.3) and is reported
   separately as a drafting availability rate. Counting it as a groundedness
   failure would blame the model for an infrastructure problem.

Shape:

    DraftResult
      status:         ok | failed
      text:           str | None
      failure_reason: str | None      # rate_limit | timeout | api_error
      sop_id:         str             # always present — the officer's fallback

    # router decided AUTO_REPLY, drafting then failed:
    #   -> human queue, escalation_reason = "draft_failed: rate_limit"
    #   -> SOP rendered alongside for the officer
    #   -> auto_reply_intended stays True for eval

**Consequences to carry forward:**

- **Groundedness must be measured, not assumed.** The removed template path held
  groundedness by construction. Every draft now comes from a model that can
  paraphrase its way into an error, so the S6.3 judge is load-bearing rather
  than a check on one of two modes. It moves off the cut list.
- **The template-vs-LLM ablation is gone** (S6.5). The remaining ablations —
  calibration, scrub, per-bucket thresholds, multi-SOP grounding — are unaffected.
- **The README states both free-tier keys as prerequisites**, with links to obtain
  them. Graders run their own keys, so this is now the whole reproducibility
  story rather than a backstop behind a keyless path.

**No drafting model is fine-tuned.** No gold reference drafts, fuzzy evaluation,
it competes with the calibration day, and the encoder already supplies the
fine-tuning story.

### 5.9 Demo UI

Streamlit, timeboxed to half a day. This is the officer's view — the human queue
is where a reviewer actually works, so it carries what they need to act.

- Two queues side by side: auto-replied / needs-review
- A **reason chip** on every escalated item, covering all three escalation
  causes (S5.8):

  | Cause | Chip |
  |---|---|
  | below threshold | `low confidence 0.61 < 0.75` |
  | bucket policy | `bucket requires review` |
  | drafting failed | `draft failed: rate limit` |

- **A SOP pane on the selected item**, rendering the retrieved SOP in full. This
  is what makes a drafting failure workable rather than dead: the officer writes
  the reply from the same source the drafter would have used.
- The risk–coverage plot with a **live threshold slider**

Drafts are live, so free-tier rate limits are visible in the demo rather than
hidden — which is the intended behaviour, not a defect to apologise for.

---

## 6. Evaluation

**Methodology: benchmarking + ablation + a bounded LLM-as-judge.**

### 6.1 Reported per topic, not as an aggregate

Authoritative: `sop_design.md` S7. In short: an aggregate "X% of the inbox"
depends on class volume mix, which is unpublished, seasonal and unascertainable —
asserting one would be a fabricated denominator. Per-topic coverage is composable;
an agency knows its own mix and can multiply through.

### 6.2 Metrics

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
| **Drafting availability** | share of intended auto-replies that drafted | free-tier failure rate |
| Encoder vs LLM baseline | accuracy, latency, size, cost, ECE | — |

Why calibration sits at bucket level and accuracy at class level — the eval
statistics argument: `sop_design.md` S3.

### 6.3 The judge

~50 sampled drafts, **one binary question**: *does this reply assert any fact not
present in the provided SOP?* The same 50 reviewed by hand, and **judge–human
agreement reported**. Narrow question, binary outcome, agreement measured — which
is what makes an LLM judge defensible rather than decorative.

**The judge is no longer optional.** With the template floor removed (S5.8) every
draft is model-written, so groundedness is not held by construction for any item.
This is the only evidence for it, which is why S8.1 moves it off the cut list.

**Failed drafts leave the denominator.** A draft that errored has no text to
score, so it is excluded from groundedness and counted in *drafting availability*
instead. Scoring an infrastructure failure as a groundedness failure would blame
the model for a rate limit, and would make the metric move with free-tier load
rather than with model behaviour.

**Groq** is the primary judge (free, fast, different model family). **OpenAI** is a
bonus second judge — eval-time, paid, and droppable if budget bites; the Groq +
human pair still stands on its own. Two judges plus the author's own labels give
**three-way agreement** over the same 50 drafts. Agreement across all three makes
the result solid; divergence is itself reportable.

**Judge outputs are committed** to `eval/results/`, exactly as the generated
dataset is, with each judge's model identifier and date — free-tier rosters
rotate. A grader reads the judgments without re-running anything or holding a key.

### 6.4 Model roles and separation

| Role | Model | Runs at | Cost |
|---|---|---|---|
| Runtime classifier | MiniLM-L6, fine-tuned | local CPU | free |
| Classifier baseline | an API LLM | build/eval | free tier |
| Email generation | an API LLM | build time | may be paid |
| Drafting | **Gemini** (free tier) | runtime, `api` mode | free tier |
| Groundedness judge (primary) | **Groq** free tier | eval time | free |
| Groundedness judge (bonus) | **OpenAI** | eval time | paid, droppable |

**Three separation rules, all for the same reason — a model must not be scored on
its own output:**

1. Email generator != LLM classification baseline
2. Drafter (Gemini) != judge
3. Judge != generator

### 6.5 Ablations

- Calibrated vs uncalibrated confidence
- Scrubbed vs unscrubbed input (does scrubbing cost accuracy?)
- Per-bucket vs single global threshold
- Does handing the drafter four SOPs instead of one degrade grounding?

Ground truth is free by construction: emails are generated from known intents
against known SOPs, and unanswerable items are created by holding SOPs out.

---

## 7. Runtime details that are easy to get wrong

**CPU-only torch in Docker.** `pip install torch` pulls CUDA wheels (~2GB) by
default. Pin the CPU build (~200MB) — the runtime is CPU-only, so the CUDA payload
is waste that slows every image pull.

**Inbox schema.** The entry point, needed by the demo and by the seasonality axis:

    {
      "id": "...",
      "received_at": "2026-04-12T09:31:00+08:00",   # drives the season axis
      "from": "...",
      "subject": "...",
      "body": "..."
    }

**Seeds are pinned** for splits, generation and training, and recorded in
`eval/results/`.

**Placeholder threshold for Day 3.** The pipeline must run end to end before
calibration exists on Day 4. Ship `0.5` in `config/thresholds.yaml` and replace it
with the fitted value — **never report a number produced under the placeholder.**

**The classifier straddles Day 3 and Day 4.** The graph needs *a* classifier to run
end to end before the trained MiniLM exists. Plan a stub or untrained head so
build stage 4 is not blocked on training.

---

## 8. Build order

| Order | Build | Components | Gate before moving on |
|---|---|---|---|
| 0 | Agent-log capture | — | Logs writing before any code |
| 1 | `data/sop_specs/` -> `generate_sops.py` -> `data/sop/` | 5.1 | 17 SOPs validate |
| 1b | `config/taxonomy.yaml` derived *from* the SOP set | 5.2 | Taxonomy frozen |
| 2 | `schemas.py`, `sop/loader.py`, `tests/` skeleton | — | SOPs load and validate |
| 3 | `scripts/generate_emails.py` -> `emails.jsonl` | 5.3 | Leakage check passes |
| 4 | `nodes/` + `graph.py` | 5.7, 5.4, 5.6, 5.8 | End-to-end run on 10 emails |
| 5 | `models/calibration.py` + `eval/` | 5.5, S6 | Risk–coverage curve exists |
| 6 | `app/`, `Dockerfile`, README | 5.9 | Clean-machine run verified |

**1 before 1b is deliberate.** Writing classes first and authoring SOPs to fit them
would produce a corpus shaped to flatter the classifier. Steps 1–2 are cheap and
unblock everything.

**Within stage 4** the nodes have a real dependency chain: scrub -> classify ->
rollup -> calibrate -> lookup -> route -> draft. Scrub first (it gates every
external call), drafting last (it depends on the retrieved SOP and is the only
node that can fail without invalidating the triage decision).

**Stage 5 is the graded contribution and must not be reached later than Day 4.**

### 8.1 Day plan

| Day | Focus | Must finish |
|---|---|---|
| 1 ✅ | Scope, licensing, architecture, taxonomy | Design locked |
| **2** | 17 SOP specs -> generate SOPs; repo skeleton; agent-log capture | Corpus exists and validates |
| **3** | Email generation -> 1,800 frozen; leakage check; LangGraph end-to-end | Pipeline runs on real data |
| **4** | Train MiniLM, calibration, curves, ablations, judge | **The 30% is earned here** |
| **5** | Docker, README, demo video, logs, final commit | Submission complete |

**Cut order if slipping:** `multi_intent` flag → Singlish slice → DistilBERT second
point → scrub ablation. **Never cut calibration, and never cut the judge** — with
the template floor removed (S5.8) every draft is model-written, so groundedness is
no longer held by construction and the judge is the only evidence for it.

---

## 9. Build-log decisions

Decisions taken during the build, after the design was locked. Recorded here rather
than in a separate file so the design is read from one place. Feeds
`docs/DEVELOPMENT_NARRATIVE.md` and the model-selection deliverable.

### 9.1 Class-level prediction, not SOP-level

The classifier predicts one of 12 classes, never a SOP. `CLASS_TO_SOPS` maps a class
to between one and four SOPs, built at startup by inverting the `intents:` line each
SOP declares. Eight of ten indexed classes are 1:1; `tax_reliefs` pulls four and
`payment` pulls two.

**Alternative considered:** predict the SOP directly, making the mapping trivially
correct and removing an unmeasured step.

**Rejected because neither holdout survives it.** Labels would be SOP ids, so:

- *Whole-class* — `rental_income` and `foreign_income_dta` have no indexed SOP, so
  their emails would have no valid label. The class becomes untrainable rather than
  unanswerable, and `no_supporting_sop` stops being derivable from an empty lookup.
- *Partial-answer* — REL-005 is held out from an otherwise-indexed class. Either it
  is a label (and is not held out) or it is not (and the relief-cap email is
  unlabelable). The distinction between unanswerable and partially answerable
  disappears, and that is a real behavioural difference the eval exists to test.

Secondary costs: per-label test data falls ~45 -> ~39, and the hardest distinction in
the corpus (REL-001 vs REL-002, near-identical vocabulary) moves onto the classifier,
which cannot see SOP text, and away from the drafter, which can.

**Cost accepted:** `class -> SOP group` is correct by construction and unmeasured.
Mitigated by S9.2.

**Caveat for the README:** this layer earns its place only because two classes pull
groups. Under a uniformly 1:1 corpus the class and SOP layers would be the same thing
and the distinction would be ornamental.

### 9.2 Grounding accuracy is measured, not assumed

For `tax_reliefs` and `payment` the drafter receives the whole group — all four
relief SOPs is ~27,600 chars, roughly 6,900 tokens — and grounds on whichever apply.
That is a real selection, and it was previously unreported.

**Why the group goes over whole rather than pre-selected:** *"can I claim for my
child and my mother?"* needs REL-001 *and* REL-002. Multi-relief questions are
ordinary rather than exceptional under the granularity principle, so a pre-selection
step would have to choose "child or parent" and would get that email wrong.

**Measurable for free:** the scenario spec records the SOP(s) each email was built
from. Comparing that against what the draft cites costs nothing and was being
discarded.

**Reported as** a secondary metric over 2 of 12 classes; the headline stays the
risk–coverage curve.

**Requires, and does not yet exist:** `source_sops` on the scenario spec schema
(stage 3), and the draft node recording which SOPs it grounded on (stage 4). Without
both, the metric cannot be computed.

**Context size is not the constraint.** Worst case is ~6,900 tokens; the *entire*
indexed corpus is ~20,100. Free-tier limits are per-request-rate, not per-token, so
this sits well inside them. The real risk is attention, not capacity — four documents
give a model more room to pull in something irrelevant, which is what this metric
measures and what the multi-SOP grounding ablation (S6.5) tests.

### 9.3 LLM zero-shot is a baseline, never the runtime classifier

**Why not classify with an LLM**, which would be simpler to build:

- **Calibration is the contribution.** An LLM asked to classify returns text.
  Extracting a probability needs logprobs (not always exposed, not comparable across
  providers) or repeated sampling with agreement measurement — slower, costlier,
  coarse. The encoder emits a calibratable distribution natively, which is what makes
  temperature scaling and the risk–coverage curve possible at all.
- **It would not fix accuracy.** An LLM can still misroute `account_specific` as
  `filing`; the error becomes harder to measure, not rarer.
- **Escalation guarantees would weaken.** "These three buckets always escalate" is a
  property of a dictionary — inspectable, testable, and true regardless of model
  behaviour. Asking an LLM to decide escalation makes it a prompt one hopes holds.

Note this argument is about the *classifier*, not about API dependence: since S5.8
removed the template floor, the runtime already requires a Gemini key.

**What the baseline buys:** model selection is graded on justification. Encoder vs
LLM on accuracy, latency, size, cost and ECE turns "better calibrated" from an
assertion into a measurement.

### 9.4 Escalation is a wrapper around the model, not inside it

The model reports what it sees; policy decides what to do about it. They change
independently — a policy shift should be a config edit, not a retrain.

- Three of five buckets escalate regardless of confidence, and must keep doing so
  when the classifier is confidently wrong.
- `BUCKET` derives from `auto_reply_permitted` in frontmatter, so an agency
  conforming real SOPs to the schema changes routing with no code change and no
  retraining. Baking escalation into weights forfeits that.
- The orthogonal flags cannot be classes. `computation_requested` cuts across them:
  *"how much QCR will I get"* is `tax_reliefs` and auto-answerable but must escalate
  anyway. A single softmax cannot express "escalate regardless of predicted class".

**Eval consequence:** rolling 12 classes into 5 buckets gives ~108 test examples per
bucket against ~45 per class. Thresholds set on 45 are not defensible — the binomial
interval is wider than the effect. The rollup is only possible because the layers are
separate.

**What this does and does not guarantee.** By construction: *if the class is right,
the policy is right*. It says nothing about whether the class is right. A confidently
misrouted `account_specific` email gets `filing` policy applied faithfully. Hence the
backstop flag in S9.6.

### 9.5 Escalation accuracy: guaranteed vs measured

Recorded because blurring these in the writeup would be a code–writeup mismatch.

**Guaranteed by construction, already covered by tests:**

| Property | Mechanism |
|---|---|
| Three buckets escalate unconditionally | no confidence value is consulted |
| `no_supporting_sop` fires on an empty lookup | derived, not hand-mapped |
| An unknown label escalates | `bucket_for` falls through to `no_supporting_sop` |

**Must be measured — nothing is measured yet, as no corpus or model exists:**

| What | How | Level |
|---|---|---|
| Escalation accuracy | per escalation *reason* | 7 reasons |
| Risk–coverage | threshold sweep, AURC | per topic |
| Calibration | ECE, reliability, before/after | 5 buckets |
| `computation_requested` | precision / recall | flag |
| `account_specific` backstop | precision / recall | flag |
| Grounding accuracy | vs scenario spec source SOP (S9.2) | 2 classes |

**The asymmetry that drives reporting.** A false escalation costs coverage: an
officer reads an email they need not have. A false auto-reply is the citizen-facing
failure — answering someone in financial distress, asserting something about a
taxpayer's account, computing a relief amount. The headline is therefore **recall on
must-escalate cases, per reason**, never a blended accuracy figure that would let
strong performance on easy classes mask a miss on `hardship_or_waiver`.

**Two limitations to state rather than defend away:**

1. **Ground truth is free but circular.** The same author writes the SOPs and
   specifies the emails. The mitigations (different generation model, specs not
   written from SOP text, a held-out hand-written adversarial set) reduce this; they
   do not remove it.
2. **~45 test examples per class is thin.** It supports macro-F1, not a defensible
   per-class threshold — which is why thresholds are per bucket. The edge-case slice
   is stratified *into* those 45, so a per-cell figure such as
   "computation-demanding relief emails" rests on ~10 examples: adequate pooled, not
   for a per-class claim.

### 9.6 An `account_specific` lexical backstop flag

`account_specific` is a class but structurally a flag (`sop_design.md` S3.1). The
sharper statement of the risk: it will be confused with whichever topic the email is
about, because topical vocabulary dominates a one-or-two-token possessive signal —
and the confusion lands on the unsafe side, since a miss means auto-drafting about a
real taxpayer's account.

A lexical backstop mirroring `computation_requested` is therefore specified in
SOP-ESC-001. It fires independently of the predicted class and forces escalation:
cheap, auditable, and it converts a known taxonomy compromise into a measured safety
net. Precision and recall are reported alongside the computation flag.

### 9.7 FIL-001 / ASM-001 tie-break

Both SOPs touch objecting to a Notice of Assessment (`sop_design.md` S10.3), which
makes it a labelling problem and not only a drafting one: *"I disagree with my NOA,
how do I object"* is genuinely both classes, and under single-label classification one
of them is wrong by definition — costing macro-F1 with no defect in the system.

**Rule, binding on the email generator:** an enquiry that *disputes the figures* in an
assessment, including an estimated NOA raised for late filing, is
`assessment_and_amendment`. `filing` covers only how and when to submit a return.
Recorded in both specs' `not_in_scope`.

### 9.8 Both out-of-scope classes kept separate

The granularity principle would merge `oos_business_tax` and `oos_other_agency`:
identical routing, identical bucket. Kept separate because the redirect destinations
are unrelated — another IRAS tax type versus another agency entirely — and a wrong
redirect is a visible citizen-facing failure rather than an internal one.

**Cost accepted:** one more confusable pair, and ~4 fewer test examples per class than
an 11-class taxonomy would give.

---

### 9.9 Two router bugs found by testing, and what they cost

Recorded because both were silent: neither raised at the point of the mistake, and
both would have surfaced as a wrong number rather than an error.

**The threshold multiplier exceeded a probability.** The risk-coverage curve is
generated by sweeping a global multiplier over every per-bucket threshold, so the
curve comes from the real router rather than a reimplementation of it. Above ~1.33
the product exceeded 1.0 and `RoutingDecision.threshold` -- declared as a
probability -- rejected it. The failure sat precisely at the conservative end of
the sweep, which is the region an agency cares about most ("how little error can we
accept, and what coverage survives?"). Every test written before the sweep used a
multiplier of 1.0 or below and passed. Fixed by clamping to `[0, 1]`: a threshold
of 1.0 means "escalate everything", which is the correct semantics rather than an
error.

**The computation flag fired on a published figure.** The pattern matched any
currency amount in a sentence ending in a question mark, so *"The relief is $4,000
per child, is that right for everyone?"* escalated -- an answerable email, lost
coverage, no safety gained. Narrowed to require a first-person marker adjacent to
the figure, in either order: the discriminator is *whose facts*, not the presence
of a dollar sign.

The asymmetry that settles how hard to tune this: a false positive escalates an
answerable email and costs coverage, which is recoverable; a false negative lets
the agent compute a relief amount, which is the failure the design exists to
prevent. So the phrase list ("how much", "calculate", "what will my tax be") stays
deliberately broad and carries the safety burden, while the currency pattern stays
narrow. **Deliberately not extended further:** this is a prototype, and the flag is
measured rather than assumed -- precision and recall are reported against the
scenario spec's ground truth, so a mediocre recall is a finding rather than
something hidden.

---

### 9.10 The generated corpus, and what the fairness checks found

**1,800 emails, 150 per class, zero generation failures.** Written by GPT-4o from
113 authored scenarios; ~50 minutes, ~$15.

`scripts/check_leakage.py` runs seven checks before training. Results on the
committed corpus:

| Check | Result | Reading |
|---|---|---|
| Balance | 150 per class exactly | equal power per topic |
| Vocabulary (TF-IDF + logreg) | **0.754** | in band: chance 0.083, ceiling 0.95 |
| System vocabulary | none | no email reads as though it knows the taxonomy |
| Single-class confinement | 19 words | all natural topic nouns |
| Length-only classifier | 0.118 | ~chance (0.083); no length artefact |
| Near-duplicates | 8 pairs >0.9 | 0.4% of the corpus |
| Flag confounding | 6 classes each | not a proxy for the classifier |

**0.754 is the number to explain in the README.** Chance is 0.083 and the failure
ceiling is 0.95. A bag of words with no semantics separating the classes three
quarters of the time is what an honest corpus looks like: topical vocabulary
genuinely differs -- "instalment" really does indicate payment -- and that is the
task, not a leak. Near-perfect separation would have meant a giveaway token.

**A correction worth recording, because the first version of the check was wrong.**
It failed 121 emails for containing "rental income", "tax relief" or "foreign
income" -- on the reasoning that these are class names. But a landlord writing
about a spare room says "rental income", because that is the ordinary English name
for the thing. The check was conflating *the class is named after the topic* with
*the generator leaked the label*.

Two pieces of evidence settled it: none of those phrases appears anywhere in the
scenario text the generator saw, and words like "relief" and "overseas" bleed
across class boundaries the way real vocabulary does rather than sitting confined
to one class. The check was replaced with two better ones -- a list of *system*
vocabulary a citizen would never write, and a data-driven confinement scan that
finds candidate tells without a hand-written list.

---

### 9.11a Per-class scores rest on 2-5 situations, not 36-49 emails

Measured after the split was made, and it bounds what every per-class figure can
mean -- so it belongs in results, not only in limitations.

Test emails per class look adequate at 36-49. The number that actually governs the
statistics is the count of **distinct situations** behind them:

| Class | Scenarios in test | Emails |
|---|---|---|
| `account_specific` | **2** | 37 |
| `hardship_or_waiver` | **2** | 36 |
| `scam_report` | **2** | 42 |
| `rental_income`, `foreign_income_dta` | **2** | 40, 42 |
| `oos_business_tax`, `oos_other_agency` | **2** | 48, 41 |
| `assessment_and_amendment`, `residency` | 3 | 49, 49 |
| `payment` | 4 | 44 |
| `filing`, `tax_reliefs` | 5 | 48, 44 |

Because grouping keeps all ~16 variants of a situation inside one split, a class
served by two scenarios has an effective sample size closer to **2** than to 37 for
any claim about generalisation. If both of its situations happen to be easy, the
class scores well and the number says little.

This is a consequence of the grouping decision, not an argument against it:
splitting at random would raise the apparent sample size while quietly measuring
memorisation. The right response is to widen the situation set (S11), and meanwhile
to report per-class figures with the scenario count beside them so a reader can see
what each rests on.

---

### 9.11 Splits are grouped by scenario

50/20/30 stratified by class, seeded, committed -- and **grouped**, so every variant
of one scenario lands in the same split.

Variants of a scenario share a situation by construction, so they are near-neighbours
in text. Splitting at random would place near-duplicates on both sides of the
train/test boundary and the test score would partly measure memorisation. Grouping
makes the test strictly harder and more honest: the model must generalise to
situations it has never seen, not to paraphrases of ones it has.

**Cost accepted:** scenarios are indivisible and unequally sized (8-15 emails), so
the realised split is 48.8 / 22.3 / 28.9 rather than exactly 50/20/30, and
test-per-class ranges 36-49 rather than a uniform 45. Allocation is greedy
largest-first within each class -- placing the awkward groups while there is room
lets small ones fill the gaps. A per-class figure therefore rests on 36-49
examples, which supports macro-F1 but not a per-class threshold; thresholds stay
per bucket for exactly this reason.

`scripts/make_splits.py --check` asserts that no scenario spans a boundary.

---

### 9.17 The escalation metric did not know account_specific had become a flag

When ``account_specific`` was demoted from a CLASS to a per-email FLAG in the 10-class
reshape, ``eval/metrics/escalation.py::expected_reason`` was not updated with it. It
derives the reason an email SHOULD have escalated under from the ground truth, and it
only ever consulted the bucket of the true class plus ``computation_requested``. It
could therefore never return ``ACCOUNT_SPECIFIC_SIGNAL``.

The consequence was a metric that reported a working component as broken:

    reason                     before              after
    account_specific_signal    P 0.000  R 0.000    P 0.771  R 0.844
                               support 0           support 64
                               FP 70               FP 16

All 70 escalations the flag correctly made were scored as false positives against a
support of zero. The headline numbers moved too, in the direction of honesty:
must-escalate support 392 -> 456, recall 0.980 -> 0.961, false escalations 181 -> 127.
The lower recall is the true one -- the earlier figure was computed over a
denominator that excluded every account-specific email.

The fix reads ``row.item.account_specific``, which the generator has been planting
all along, and places it in the router's own precedence: bucket reasons first, then
``account_specific``, then ``computation_requested``.

**The lesson is about where a taxonomy change propagates.** The runtime was migrated
correctly and the router never misbehaved -- the flag fired on 70 emails and every
one of them escalated. What went stale was the EVALUATION's model of the ground
truth, which is the layer least likely to raise an error when it drifts, because a
metric that is wrong still returns a number. Independent confirmation is what caught
it: measuring the flag's coverage cost directly gave 16 false positives, against the
70 the committed results claimed.

Note that ``foreign_income_signal`` still reports support 0 with 8 false positives,
and that one is CORRECT rather than a bug of the same kind. It is a misfile guard: it
fires when the classifier put a foreign-income email somewhere else, so there is no
ground-truth reason for it to match -- a correctly classified foreign-income email
escalates as ``no_supporting_sop`` instead. Its precision is measured separately in
``flags.json`` (1.000), which is the number to quote.

---

### 9.16 The two thresholds are set independently, and the curve says why

Thresholds were placeholders (0.5 / 0.5) until the 10-class retrain. They are now
chosen from the risk-coverage curve on the 877-email test split, and the two that
bite are set to DIFFERENT values because the two buckets do not behave alike:

    threshold   auto_answerable            out_of_scope
                automated  risk            automated  risk
      0.40      290/435    0.097            84/111    0.131
      0.50      286/435    0.094            62/111    0.016
      0.60      262/435    0.099            40/111    0.025
      0.70      237/435    0.097            20/111    0.000

**auto_answerable is flat.** Risk holds near 0.095 across the whole range, so
raising the cutoff removes coverage without removing error. The errors a higher
threshold would need to catch are CONFIDENT misclassifications, which a confidence
threshold cannot see by construction -- that is what the flags and the
always-escalate buckets exist for. Set at 0.50, the bottom of the flat.

**out_of_scope has a real knee.** Risk falls 0.131 -> 0.016 between 0.40 and 0.50,
an eightfold reduction for 22 items. Set at 0.65, past the knee, keeping roughly a
third of the bucket automated.

The asymmetry is deliberate and worth defending: a wrong redirect is harder for a
citizen to recover from than a wrong-but-grounded answer, because it sends them to
an organisation that cannot help them and has no record of them. Paying coverage
for precision is the right trade in that direction and the wrong one in the other.

**The reportability flag now reads the config.** It previously read
``scaler.fitted`` alone, which is True as soon as any temperature exists -- so a run
could stamp ``calibrated_numbers_reportable: true`` onto a summary whose coverage
and risk were computed under placeholder cutoffs, while ``config/thresholds.yaml``
still said in capitals that no number under it may be reported. Whichever a reader
believed, one file was wrong. ``run_eval.py`` now ANDs ``scaler.fitted`` with a
check that the config declares itself fitted, and ``summary.json`` carries
``thresholds_fitted`` separately so the two conditions are visible apart.

Operating point at these thresholds, on test: **coverage 0.356, risk 0.090,
AURC 0.061**, must-escalate recall 0.980, 8 unsafe automations out of 877.

---

### 9.15 Per-topic risk is grouped by TRUE class, so "risk 1.0" is not a router failure

`eval/results/risk_coverage.json` reports, at the operating point:

    topic                       coverage    risk     n   automated   wrong
    account_specific             0.4054    1.0000    37      15        15
    hardship_or_waiver           0.3889    1.0000    36      14        14
    oos_other_agency             0.0488    1.0000    41       2         2

Read quickly, those rows say the router auto-answers 40% of account-specific
enquiries and is wrong every time -- which would contradict the invariant that
`requires_account_lookup` and `high_consequence` always escalate.

They do not say that. `run_eval.py` builds each `Outcome` as

    label     = row.item.label        # the TRUE class
    automated = decision.is_automated # from routing the PREDICTED class

so a per-topic row groups by what the email **actually was**, while the routing
decision was made on what the classifier **said it was**. The `account_specific`
row therefore counts emails that are genuinely account-specific but were misfiled
into an auto-answerable class -- and every such automation is wrong by construction,
because the predicted class differs from the true one. Risk 1.0 is arithmetic, not
a routing defect.

Grouping the same run by PREDICTED class shows the invariant intact:

    predicted class              n   automated
    account_specific            78       0
    hardship_or_waiver          36       0
    scam_report                 42       0
    foreign_income_dta          47       0
    rental_income               59       0

Zero automation in every always-escalate class, and zero in both held-out classes.
The router never acted on an item it classified into one of them.

**Both framings are legitimate and they answer different questions.** Grouped by
predicted class, the number describes the ROUTER: given what the system believed,
did it apply the right policy? Grouped by true class, it describes the SYSTEM as a
citizen experiences it: I sent an account enquiry, what happened to it? The second
is the one an agency should care about, and keeping it is correct -- an escalation
policy that is perfect on correctly-classified items and silent about misfiles
would be measuring the wrong thing.

What must change is the presentation, not the metric. Reporting "risk 1.0" beside a
row labelled `account_specific` invites exactly the misreading above, and the
writeup cannot afford a reader concluding the safety invariant is broken when it is
provably not. Three fixes, in order of value:

1. State in the results narrative that per-topic rows are keyed on TRUE class and
   that risk on always-escalate topics is a **classifier misfile rate**, not a
   routing error rate.
2. Report the by-predicted-class automation table alongside it, since that is the
   direct evidence the escalation invariant holds end to end on real data.
3. Consider renaming the per-topic risk field to something like
   `misroute_risk_by_true_class`, so the JSON is self-describing to a grader who
   never reads the narrative.

Note also that `Outcome.correct` is `predicted == true label` -- CLASS equality, not
bucket equality. An email misfiled from `filing` to `payment` counts as wrong even
though both are auto-answerable and the reply policy is the same. That is the
conservative choice and the right one, but it means per-topic risk slightly
overstates citizen-visible harm, and the writeup should say so rather than leave a
reader to discover it.

---

### 9.14 The scam flag's 0.976 recall is a test-split artefact

`ARCHITECTURE_AUDIT` section 2.9 reports the scam misfile guard at precision 1.000,
recall 0.976 on the test split and treats that as the guard's performance. Measured
across all three splits, the test figure is the outlier:

    split          precision   recall   support   missed scenarios
    test             1.000      0.976      42     SCAM-SITE-001 (1)
    calibration      1.000      0.692      39     SCAM-CALL-001 (8), SCAM-WHATSAPP-001 (4)
    train            1.000      0.739      69     SCAM-VERIFY-001 (12), SCAM-PAID-001 (6)

Precision is genuinely 1.000 everywhere -- zero false positives on all 1,800 emails
-- so the guard still costs no coverage. But recall is **0.793 corpus-wide (119/150)**,
not 0.976. **31 of 150 scam emails match no pattern at all**, across 5 of the 7
scenarios.

The reason the test split looks clean is scenario assignment, not detector quality.
`scam_report` has only **7 scenarios**, and the grouped split puts SCAM-SMS-001 and
SCAM-SITE-001 in test while the two hardest situations (SCAM-CALL-001,
SCAM-VERIFY-001) land in calibration and train. The test split simply did not draw
the phrasings the patterns miss. This is S9.11a's warning again: a per-class figure
resting on 2 test scenarios describes those 2 situations, not the class.

**What the misses have in common** is the substance of the finding. The patterns key
on a *label* the writer supplies -- "scam", "phishing", "suspicious", "is this
legitimate". The missed emails describe the *event* instead, and never name it:

    "i got a call this morning from a man who said he was from the tax office and
     said i needed to pay him immediately or I would be arrested ... he told me to
     call back on this number and pay straight away"

That is a textbook impersonation report containing no scam vocabulary whatsoever.
The writer is frightened and describing what happened; naming it as fraud is the
conclusion they are writing in to ask for. **A distressed citizen is the least
likely author to supply the keyword**, which makes this failure mode correlated with
exactly the cases that matter most.

The event-shaped signal is available and unused: an unsolicited contact channel
(call, SMS, WhatsApp) plus a payment or credential demand plus urgency or an arrest
threat. That is a different pattern family from the current list, not a longer
version of it.

Consequences, in order:

1. **The number to report is 0.793 corpus-wide, not 0.976.** Quoting the test figure
   would be reporting the easiest 2 of 7 situations as though they were the class.
2. The guard remains worth keeping exactly as argued -- precision 1.000 means it
   costs nothing, and 119 caught misfiles is 119 fraud victims not redirected to
   another agency. The claim needs weakening, not the mechanism.
3. Correctly-classified scam emails still escalate via the `high_consequence`
   bucket regardless of this flag, which never consults it. The flag matters only
   for MISFILES, so its recall bounds the residual risk rather than the primary
   path -- worth stating plainly so 0.793 is not read as "20% of fraud reports are
   auto-answered".

---

### 9.13 The temperature is fitted on 27 situations, and the splits disagree

Two facts about the fitted temperature that the calibration section did not
anticipate, both measured rather than argued.

**The fit optimises a different quantity from the one the router reads.**
`scripts/fit_calibration.py::_confidences` takes `max(p)` over the five buckets.
`triage.nodes.calibrate.calibrate` returns `p[predicted]`, where the predicted
bucket follows the predicted CLASS rather than the argmax -- which is S9.x's
deliberate and correct choice, pinned by
`test_rollup_follows_the_class_not_the_argmax_bucket`. The two quantities differ
whenever the class-bucket and the argmax-bucket disagree, which on the calibration
split is **38 of 401 emails (9.5%)**, mean gap 0.109. So the NLL objective the
temperature minimises is not scored on the number the threshold is compared
against.

Measured cost on the test split, reproducing `eval/results/calibration.json`
exactly (0.2312 -> 0.1459):

    quantity                             ECE raw   ECE at T=0.6831
    max(p)     [what the fit optimises]   0.2039        0.1216
    p[pred]    [what the router uses]     0.2312        0.1459

The reported figures are the second row, so **the committed numbers are the honest
ones** -- `run_eval.py` reads `BucketScore.confidence` and is correct. The defect is
confined to the fit: the temperature was chosen against `max(p)` and then applied
to `p[pred]`.

**Refitting on the router's quantity does NOT improve the reported ECE.** This was
the expected easy win and it is not available. Sweeping T on the calibration split
against `p[pred]` selects T = 0.27, whose test ECE is **0.2668 -- worse than the
0.1459 the current temperature achieves.** The two splits disagree about the
optimum:

    T        calibration ECE    test ECE
    0.27          0.1640         0.2668
    0.50          0.1821         0.1784
    0.6831        0.2344         0.1459   <- committed
    1.00          0.3390         0.2312

**The reason is that the calibration split is easier than the test split**, and by
a wide margin, at almost identical mean confidence:

    split          n     scenarios   bucket accuracy   mean confidence
    calibration   401       27           0.8429            0.6085
    test          520       34           0.7058            0.5739

A 13.7-point accuracy gap at matched confidence is exactly the condition under
which a temperature fitted on one split mis-serves the other. There is no leakage
-- scenario overlap between every pair of splits is zero, verified -- so this is
not a bug in `make_splits.py`. It is S9.11a's warning arriving at the calibration
layer: **the temperature is fitted on 27 situations, not on 401 independent
examples.**

Bootstrapping the fit over scenarios (the real unit of independence, 60 resamples)
puts the uncertainty in the open:

    fitted T: median 0.677, 90% interval [0.456, 0.836]

The committed 0.6831 sits at the median, so it is not a fluke -- but a parameter
with that interval should not be reported to four decimal places as though it were
determined. **What the writeup can claim** is that temperature scaling reduces ECE
on the held-out split (0.2312 -> 0.1459, a 36.9% reduction), which is true, measured
on data the temperature never saw, and the honest form of the contribution. **What
it cannot claim** is that 0.6831 is the right temperature for this system in
general, or that the calibration split's ECE is evidence about the test split.

Two consequences for the work:

1. `_confidences` should be corrected to score `p[predicted]` so the fit and its
   application are the same transformation, as the module docstring already claims.
   This is a correctness fix, not a metric improvement -- expect the reported ECE to
   move little or to worsen slightly, and report it either way.
2. The direction that would actually improve calibration is more SITUATIONS in the
   calibration split, not more emails. That is S11's first future improvement, and
   this is a second independent argument for it.

One further note, correcting S5.5's premise: the fitted temperature SHARPENS
(T < 1) rather than flattens. Raw softmax over 12 classes is overconfident, but the
12->5 rollup sums probability mass scattered across several classes within one
bucket, and the summed bucket score is therefore UNDER-confident. The rollup, not
the network, sets the direction of the correction.

---

### 9.12 The free-tier claim is argued, not executed

`tests/test_runtime_is_free.py` was removed. It had scanned `src/` imports to prove
the runtime touched no paid provider, which made the free-tier claim executable by
a grader.

With the template floor gone (S5.8) the runtime requires a Gemini key, and both
runtime providers -- Gemini for drafting, Groq for the judge -- are free tier by
deliberate selection rather than by a property the code can assert. The test would
now be checking a list it was itself given.

**Consequence for the README:** the free-tier claim moves from demonstrated to
argued, and must be stated as such. It joins the absence of vector search as a
design position defended in prose rather than a measurement -- and, like that one,
the writeup must not imply it was verified.

---

## 10. KIV

- Vector search as a measured comparison against dictionary lookup
- DistilBERT as the second point on the size/accuracy/calibration curve
- Isotonic regression, if the dataset grows
- `under_specified` flag
- TF-IDF + logistic regression leakage check (15 min, high value)
- Hand-written adversarial set (~30 emails) as an unbiased slice
- Full EDA: class balance, length distribution, inter-class vocabulary overlap
- **A `hardship_or_waiver` lexical flag.** `hardship_or_waiver` is already a
  CLASS (bucket `high_consequence`, SOP-ESC-002), so an email that is a hardship
  plea escalates today. The gap is narrower: a hardship mention *buried inside*
  an otherwise ordinary question -- *"when is the filing deadline? also I am
  struggling to pay and hope the penalty can be waived"* -- which the classifier
  will likely label `filing` because most of the email is about filing. Every
  auto-answerable SOP already declares `hardship_or_waiver_request` in
  `escalate_if`, so the corpus expects a detector that does not yet exist.
  Deferred rather than built: the two flags on the critical path
  (`computation_requested`, `account_specific`) each guard a failure mode the
  design exists to prevent, and a third detector adds scope without closing a
  comparable risk. Stated in limitations as a known unenforced trigger.
- **Reserve 3 hours of manual time for the demo video**
- Batch throughput demonstration (async, rate-limit aware)
- Interview prep: an answer on throughput and scaling architecture

---

## 11. Future improvements (for README)

**Corpus breadth is the binding constraint, not corpus size.** The 1,800 emails
come from **113 authored situations**, roughly 16 variants each. Variation across
literacy, register, persona and season is what forces the classifier to find the
intent underneath the wording rather than memorising a phrasing — but the *number
of distinct situations* is what determines how much of a real inbox the corpus
represents, and 113 is far fewer than a live queue contains.

The consequence to state plainly rather than imply away: **1,800 is not 1,800
independent examples.** Reported per-class figures rest on 36–49 test emails drawn
from a handful of situations each, so a class can look strong because its few
situations happen to be easy. The measured near-duplicate rate is low (8 pairs
above 0.9 cosine, 0.4% of the corpus) and splits are grouped so paraphrases cannot
straddle the train/test boundary — but neither fact widens the situation set.

Two ways to widen it, in order of value:

1. **More situations, not more variants per situation.** Authoring another ~100
   scenarios would buy more than doubling the variants of the existing ones.
2. **Real anonymised enquiries as a validation slice.** Even a few hundred genuine
   emails, used only for evaluation and never for training, would test whether the
   synthetic situation set resembles the real distribution — which is the one thing
   this project cannot currently check about itself.

- Live guidance refresh with effective-date metadata and re-indexing cadence
- Learning from officer corrections: few-shot pool updates, scheduled threshold
  recalibration, calibration-drift monitoring
- Fine-tuning a drafting model on officer-approved replies once such a corpus exists
- Fully local generation, removing the external API dependency
- Multilingual support (Chinese, Malay, Tamil)
- **An LLM for scam detection, because lexical patterns structurally cannot do it.**
  The scam flag is a misfile guard over regex, and its recall is **0.793 corpus-wide
  (119/150)** -- not the 0.976 the test split alone suggests, which is an artefact of
  `scam_report` having only 7 scenarios and the two hardest landing outside test.

  The 31 missed emails share a property that no pattern list fixes: **they describe
  the event and never name it.** The patterns key on a label the writer supplies
  ("scam", "phishing", "suspicious", "is this legitimate"); the misses read like

      "i got a call this morning from a man who said he was from the tax office and
       said i needed to pay him immediately or I would be arrested"

  That is a textbook impersonation report containing no scam vocabulary at all. The
  writer is frightened and recounting what happened -- naming it as fraud is the
  conclusion they are writing in to ask for. **The most distressed citizen is the
  least likely to supply the keyword**, so the failure mode correlates with the cases
  that matter most.

  Event-shaped patterns were prototyped (unsolicited channel + arrest or legal
  threat + payment or credential demand). They recover 5 emails for **0.827 recall at
  precision 1.000**, and one tempting pattern -- `pay (immediately|right now|...)` --
  had to be dropped because it fires on genuine payment-deadline enquiries, costing
  4 false positives. That is the whole shape of the problem in one line: the signal
  that separates a scam from a payment question is *who is demanding and why*, which
  is semantics, not vocabulary. The remaining ~26 misses are bare narrative with no
  threat language whatsoever, and no regex reaches them.

  **An LLM is the right instrument here**, and unusually the cost argument favours it:
  the classification is a single yes/no on a short text, the class is rare (150 of
  1,800), and it need only run as a second opinion on emails the encoder did NOT
  route to `scam_report` -- so the spend is bounded and small. The precision-1.000
  regex stays as the cheap first pass; the model covers the semantic tail. This is
  the one place in the pipeline where a generative model earns its unreliability,
  because the failure direction is asymmetric: a false positive escalates one
  answerable email, a false negative auto-answers a fraud victim.

  Until that exists, the honest framing for the writeup is that **scam detection is
  the weakest guarantee in the system**: ~79% of fraud reports carry a lexical
  signal, escalation is certain for those that do, and correctly-classified reports
  escalate on the `high_consequence` bucket regardless -- so the residual exposure is
  misfiled-and-unworded reports, not one in five fraud victims.

- **An offline PII model in place of the regex set.** `config/pii_patterns.yaml`
  is deliberately a placeholder for this. A local NER model would catch the
  shapes a pattern set cannot enumerate -- free-text addresses with no street-type
  token, unusual name forms, and identifiers written in ways the corpus never
  showed. The regex set is not a partial version of that model: it is the
  correct choice under the current constraints, because it is readable,
  diffable, testable per pattern, and adds no runtime dependency or inference
  cost to the one path that gates every external call. Detection lives in
  config rather than code precisely so the swap is a change of implementation
  behind `Scrubber`, not a change to the pipeline.

  The residual gap the regex set leaves is stated rather than closed: an
  address carrying neither a block number nor a street-type token is
  unreachable by a gazetteer-anchored pattern, and the trade in the other
  direction is real too -- a leading Malay street type cannot distinguish
  "Jalan Besar station" from a residential "Jalan Membina". Both are
  documented in `tests/test_scrubber.py` rather than claimed fixed.
- Mailbox integration, with its privacy implications
- Extension to other tax types with their own seasonal cycles
- Human-in-the-loop A/B evaluation in a live inbox
- **Real internal SOPs conformed to the frontmatter schema** — the integration
  seam described in `sop_design.md` S12

---

## 12. Companion documents

- `sop_design.md` — SOP corpus, taxonomy, buckets, flags, licensing, reporting
- `README_draft.md` — README skeleton
- `deliverables_checklist.md` — full deliverables list from the assessment PDF
- `brainstorm_log.txt` — session log and decision history

---

## Appendix: conflicts resolved during the merge

Resolved per the authority rule — `sop_design.md` wins on corpus and taxonomy,
`architecture.md` wins on layout and model roles, `implementation_plan.md` loses to
both.

| Conflict | Resolved to | Basis |
|---|---|---|
| `owner_queue` for a payment SOP: `IIT-General` (arch S2.4) vs `IIT-Payments` (sop_design S4.1) | Per-SOP, not global. PAY-001 = `IIT-Payments`; `IIT-General` is the IIT default queue. Both are invented names, so both are valid examples. | sop_design S4.1 is the worked example |
| SOP id scheme: `SOP-IIT-NNN` (arch S2.4, S3.1) vs `SOP-XXX-NNN` where XXX is the topic (sop_design S5, S8.2) | `SOP-<TOPIC>-NNN` — FIL, REL, ASM, PAY, RES, ESC, RTE, INC | sop_design S5 inventory is authoritative and lists all 17 |
| Corpus size: "~20 SOPs" / "~20 documents" (arch S2.4, S8) vs 17 (sop_design S5) | 17 | sop_design S5 supersedes the earlier draft |
| Held-out SOPs: 2 (arch S2.3, implying only INC-001/002) vs 3 (sop_design S5, adding REL-005) | 3 held out, 14 indexed. REL-005 is the *partial answer* holdout, a distinct case from the two whole-class holdouts. | sop_design S5 |
| Held-out classes vs held-out SOPs conflated | Unrelated counts: 2 held-out *classes* -> `no_supporting_sop`; 3 held-out *SOPs*. REL-005 sits inside an indexed class. | sop_design S5 |
| Calibration split size: "360 examples" (arch S4) vs "~72 per bucket" (plan S4.5) | Both, and consistent: 1,800 × 20% = 360, ÷ 5 buckets ≈ 72 | arithmetic |
| Dangling xref `architecture.md S3b` (sop_design S6) | `architecture.md` S5 → now BUILD.md S6.3 | S3b does not exist |
| Dangling xref `S7.1` (sop_design S9, re: scraping) | `sop_design.md` S8.1 | S7.1 does not exist |
| Judge specified in three places (arch S5, plan S5.3, sop_design S6) | Single statement in BUILD.md S6.3; sop_design S6 keeps its retrieval-measurement framing | deduplication |
| `escalate_if` naming: `amount_computation_requested` (frontmatter) vs `computation_requested` (flag/router) | Both retained — different layers. Frontmatter uses `amount_computation_requested`; the runtime flag is `computation_requested`. Alias explicitly in `sop/loader.py`. | not a conflict, but a trap |
