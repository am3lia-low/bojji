# Repository Architecture

Companion to `implementation_plan.md`. Defines what files exist, where, and why.

---

## 1. Layout

```
citizen-triage-agent/            # anonymous repo name — no agency, no role
├── README.md                    # THE primary artifact (graded)
├── Dockerfile
├── docker-compose.yml
├── Makefile                     # make data | train | eval | demo | test
├── pyproject.toml               # deps + ruff/mypy/pytest config
├── .env.example                 # every key optional; documents the no-key path
├── .dockerignore .gitignore
│
├── config/                      # ← the thesis lives here, as data not code
│   ├── taxonomy.yaml            # intents + escalation policy per class
│   ├── thresholds.yaml          # per-class threshold + `justification:` string
│   ├── models.yaml              # backend registry (local | api)
│   └── pii_patterns.yaml        # regex set + street gazetteer
│
├── src/triage/                  # RUNTIME ONLY — must work with zero API keys
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
│   ├── train_encoder.py
│   ├── fit_calibration.py
│   └── check_leakage.py         # TF-IDF + logreg sanity check
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
├── app/streamlit_app.py         # view only: two queues, reason chips, slider
│
├── tests/
│   ├── test_router.py           # highest-value: the escalation logic
│   ├── test_scrubber.py
│   ├── test_calibration.py
│   ├── test_runtime_is_free.py  # asserts src/ imports no paid provider
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

---

## 2. The nine decisions this layout encodes

### 2.1 Thresholds and taxonomy are YAML, not constants

`config/thresholds.yaml` carries a `justification:` string per **routing bucket**.
The escalation policy must be readable in one file, diffable in git, and
changeable without touching code.

**Thresholds are set per bucket, not per class.** Three of the five buckets
escalate regardless of confidence, so only `auto_answerable` and `out_of_scope`
have a threshold that bites. The earlier "hand-set per-class dictionary justified
by consequence" language was self-imposed in the Day-1 brainstorm, is required by
nothing in the assessment, and is dropped. The contribution is calibration plus
the risk-coverage curve, which stands with a single threshold. Per-class overrides
may be added later only where a specific consequence justifies one.

### 2.2 A hard wall between `scripts/` and `src/`

`scripts/` is build-time and may use paid APIs. `src/` is runtime and must run on
free tier with no key. `tests/test_runtime_is_free.py` enforces this by scanning
`src/` imports. This converts the free-tier claim from an assertion into something
the grader can execute.

### 2.3 The taxonomy is designed around the SOPs, not the other way round

See `sop_design.md` for the authoritative class and SOP inventory: 12 classes
(10 indexed + 2 held out), 17 SOPs (14 indexed + 3 held out), 5 routing buckets.

Leaf granularity is the coarsest partition that still lets the drafter ground
correctly. Classes map to an SOP *group*; most are 1:1, but `tax_reliefs` pulls
four and `payment` pulls two.

Consequences:

- `class -> sop_ids` is a dictionary lookup built at startup from SOP frontmatter
  (`intents:`). **No vector search, no embedding model, no index** — one less
  failure mode upstream of the escalation decision, and one less thing to debug.
- All the difficulty concentrates in the classifier, which is where the
  calibration contribution lives.
- Ground truth stays free.

**Metric consequence:** class -> SOP group is correct by construction and is not
measured. Within-group selection by the drafter *is* measurable (grounding
accuracy) but applies to only 2 of 12 classes, so it is a secondary metric. The
headline is the risk-coverage curve, reported per topic.

### 2.4 SOPs are markdown files with frontmatter

```yaml
---
sop_id: SOP-IIT-014
synthetic: true          # SYNTHETIC — authored for this project, not an IRAS document
title: Qualifying Child Relief — eligibility enquiry
intents: [relief_eligibility_child]
applies_to_ya: [2025, 2026]
effective_date: 2025-01-01
supersedes: SOP-IIT-011
owner_queue: IIT-General
escalate_if: [amount_computation_requested, account_specific]
references:
  - https://www.iras.gov.sg/...   # cited, not reproduced
---
```

One file per SOP makes deterministic `intent -> sop_id` lookup auditable, gives
effective-date and supersession complexity for free, and makes the holdout a
matter of excluding files from the index rather than an arbitrary cut.

Register: semi-formal, internal, officer-facing. Terse and bullet-heavy —
`if X -> do Y`, canned phrasing blocks, explicit escalation triggers. Not legalese.

Storage: a flat directory loaded and validated into memory at startup. At ~20
documents and ~100KB there is no vector DB, no external service and no index to
rebuild. This is a large part of why the free-tier constraint is satisfiable at
all, and should be stated in the README rather than left implicit.

### 2.5 Classifiers sit behind a Protocol

`models/base.py` defines `predict(text) -> (label, probs)`. The encoder and the
LLM baseline both satisfy it, so the ablation harness swaps them with no
special-casing, and the calibration layer is written once.

**MiniLM-L6 (22M) is the primary runtime classifier**, not DistilBERT. At ~90MB
the weights commit to the repository in plain git (under GitHub's 100MB limit —
see S6), which removes the Hugging Face Hub dependency at Docker build time
entirely: the clean-machine run needs no network and no account. DistilBERT (66M, ~250MB) moves to KIV as the second point
on the size/accuracy/calibration curve if time allows.

### 2.6 `eval/results/` is committed

The README cites files in `eval/results/`, never remembered numbers. This is the
structural guard against the code–writeup mismatch failure mode.

### 2.7 Streamlit holds no logic

`app/` calls the graph and reads `eval/results/`. Nothing is computed there that
isn't computed in the pipeline, so the demo cannot drift from the measured system.

### 2.8 Drafting has a template floor and an LLM ceiling

The runtime must produce a reply with **no API key of any kind**. Therefore:

| Mode | Mechanism | Requires |
|---|---|---|
| `local` (default) | emit the SOP's S4 *Approved phrasing* block, slots filled | nothing |
| `api` | LLM rewrites that block for tone and the citizen's phrasing | a key |

This makes SOP S4 load-bearing rather than decorative, and guarantees the
clean-machine path without shipping a multi-GB Ollama image.

**It also answers draft quality for free.** In `local` mode the reply is SOP text
with slots filled, so it cannot assert a fact absent from the SOP — groundedness
holds by construction and is stated, not measured. Only `api` mode can paraphrase
its way into an error, and that is where a sampled groundedness check would be
warranted if the mode is used.

Gives a free ablation: template vs LLM drafting.

### 2.9 Redirects count as coverage

`out_of_scope` produces an automated redirect. That is an automated action, so it
counts toward per-topic coverage — consistent with the "no back door" policy,
where a clean redirect is the correct outcome rather than a failure.

---

## 3. SOP corpus: provenance, and the confidentiality boundary

The corpus is **authored for this project**, not scraped. Two reasons, and the
second is the stronger one.

**The brief asks about *internal* SOPs**, which no agency publishes. Any honest
version of this project must author them.

**Licensing** is the secondary reason, and the framing matters. IRAS Terms of Use
restrict reproduction of site contents (verified 1 Sep 2026; `/robots.txt` returns
404, so robots is not the constraint). Read literally the same document also
requires written permission to hyperlink to an internal page, which places it as
boilerplate that is not observed in practice — by news outlets, tax advisory firms
or other agencies. This project does not rely on it either way.

The operative principle is **copyright protects expression, not facts**. Tax rates,
deadlines and thresholds are facts stated in legislation. Pages are fetched freely
as reference; only restatements with citations are committed. See `sop_design.md`
S8.1.

### 3.1 The confidentiality line

The author has prior IRAS call-centre experience. Singapore tax officers are bound
by official secrecy provisions (Income Tax Act s.6) and typically the Official
Secrets Act. The line drawn here:

**Every factual claim in an SOP must be traceable to a public IRAS URL, recorded in
that SOP's `references:` frontmatter.**

Prior experience is used only to choose *which topics matter* and to state the
escalation boundary in principle — account-specific queries require a database
lookup and therefore escalate. That boundary is a structural fact about any tax
authority, not privileged information.

Explicitly excluded from every SOP:

| Excluded | Substituted with |
|---|---|
| Real internal system names | Generic (`case management system`) |
| Real queue identifiers | Invented (`IIT-General`, `IIT-Escalation`) |
| Real internal reference codes | Invented `SOP-IIT-NNN` scheme |
| Real internal SLAs | Illustrative, flagged as such |
| Reproduced internal wording | Written from public sources |
| Taxpayer data of any kind | Fabricated personas, fake NRICs only |

### 3.2 The misrepresentation guard

A synthetic SOP that looks like a real IRAS document is its own problem. Therefore:

- Every file carries a header banner marking it synthetic.
- The README states plainly, and prominently rather than buried in limitations:
  SOPs are authored for this project, structured as a plausible officer-facing
  procedure, factually grounded in public IRAS guidance, and reflect no internal
  IRAS material, template or practice.

### 3.3 Generation pipeline — the author writes specs, not prose

```
data/sop_specs/*.yaml     (human-authored: topic, intents, escalation
        │                  triggers, effective dates, supersessions)
        │
        ├── .scratch/*.html   (public IRAS pages, fetched at author time,
        │                      GITIGNORED, used as input, never committed)
        ▼
scripts/generate_sops.py
        ▼
data/sop/SOP-IIT-NNN-*.md    (committed: generated prose + URL citations)
```

Committing only derived text keeps this licensing-clean. Tax rules are facts, and
facts are not copyrightable — expression is. Text stating the same public rules in
a different structure is defensible; a committed copy of IRAS pages is not.

Roughly two hours of authoring, against a day or more of scraping, parsing and
chunking that the previous plan put on the critical path.

### 3.4 Honest cost: circularity

The same author writes the SOPs and specifies the test emails. Mitigations:

1. SOP topic coverage mirrors the structure of real IRAS guidance, so the corpus
   shape is externally anchored rather than invented to suit the classifier.
2. Emails are generated from *scenario* specs, never from SOP text, using a
   different model than the LLM classification baseline.
3. A hand-written adversarial set is held out entirely from generation.
4. Messiness is injected deliberately — superseded versions, dangling annexe
   references, overlapping scope between two SOPs — because real SOP corpora are
   not internally consistent and a clean one would flatter the system.

This must be stated in the limitations section, not defended away.

---

## 4. Where confidence comes from, and how it is corrected

    email -> MiniLM-L6 encoder -> pooled embedding (384 dims)
                               -> linear head -> 12 logits
                               -> softmax     -> 12 probabilities, sum to 1

The largest probability is the model's confidence. It is native to the
architecture — the linear head is added at fine-tuning time.

**Raw softmax is systematically overconfident.** A network reporting 0.95 may be
right 85% of the time. This is exactly why an off-the-shelf 0.8 cutoff is unsound,
and it is the gap the project measures.

Correction, fitted on the 20% calibration split and applied to the summed bucket
distribution:

| Method | Shape | Status |
|---|---|---|
| **Temperature scaling** | divide logits by one learned scalar before softmax | **implemented** |
| Isotonic regression | non-parametric monotonic map, raw -> corrected | KIV |

**Temperature scaling is chosen on data volume, not convenience.** The calibration
split is 360 examples across 5 buckets — roughly 72 per bucket. Isotonic
regression is non-parametric and would overfit at that size; temperature scaling
fits a single scalar. Isotonic becomes worth revisiting only if the dataset grows.

Reported as Expected Calibration Error plus reliability diagrams, before and
after. The threshold sweep over corrected confidence produces the risk-coverage
curve.

**This is the operational argument for an encoder over an LLM classifier.** An LLM
asked to classify returns text; extracting probabilities needs logprobs (not
always exposed) or repeated sampling with agreement measurement. The encoder emits
a calibratable distribution natively. Feeds the model-selection deliverable.

---

## 5. Model roles, and why each is separable

| Role | Model | Runs at | Cost |
|---|---|---|---|
| Runtime classifier | MiniLM-L6, fine-tuned | local CPU | free |
| Classifier baseline | an API LLM | build/eval | free tier |
| Email generation | an API LLM | build time | may be paid |
| **Drafting** | **Gemini** (free tier) | runtime, `api` mode | free tier |
| **Groundedness judge (primary)** | **Groq** free tier | eval time | free |
| **Groundedness judge (bonus)** | **OpenAI** | eval time | paid, droppable |

**No drafting model is fine-tuned.** Rejected in `implementation_plan.md`: no gold
reference drafts, fuzzy evaluation, competes with the calibration day, and the
encoder already supplies the fine-tuning story.

**Three separation rules, all for the same reason — a model must not be scored on
its own output:**

1. The email generator must differ from the LLM classification baseline.
2. The drafter (Gemini) must differ from the judge.
3. The judge must differ from the generator.

**Two judges give three-way agreement.** Groq, OpenAI and the author's own labels
over the same ~50 drafts. Agreement across all three makes the groundedness result
solid; divergence is itself reportable. OpenAI is eval-time and droppable if
budget bites — the Groq + human pair still stands on its own.

**Reproducibility:** judge outputs are committed to `eval/results/`, exactly as the
generated dataset is. A grader reads the judgments without re-running anything or
holding any key. Record each judge's model identifier and date — free-tier rosters
rotate.

---

## 6. Runtime details that are easy to get wrong

**Model weights and git-lfs.** A fine-tuned MiniLM-L6 lands near 90MB, under
GitHub's 100MB hard limit, so it commits to **plain git with no LFS**. This is
deliberate: with LFS, a grader who clones without `git-lfs` installed receives
pointer files instead of weights and the application fails confusingly. Check the
real size after training; use LFS only if it exceeds the limit, and document the
install step if so.

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

**API failure falls back to the template.** If the Gemini call rate-limits, times
out or errors, drafting degrades to the S2.8 template floor and the reply is
flagged as degraded. Free, because the floor already exists — but state it rather
than improvise it on Day 5.

**`no_supporting_sop` is derived, not hand-mapped.** The router checks whether
`CLASS_TO_SOPS[class]` came back empty rather than reading a hand-written bucket
entry. One source of truth, and holding out a further SOP later needs no code
change.

**Seeds are pinned** for splits, generation and training, and recorded in
`eval/results/`.

**Placeholder threshold for Day 3.** The pipeline must run end to end before
calibration exists on Day 4. Ship `0.5` in `config/thresholds.yaml` and replace it
with the fitted value — never report a number produced under the placeholder.

---

## 7. Design rule forced by the domain research

**The agent never computes a relief amount.**

IIT rules are conjunctive with numeric caps, ordering rules and interaction caps
(QCR first, WMCR takes the balance, combined $50,000/child, overall $80,000 relief
cap). LLM-over-prose fails at exactly this and fails confidently. The agent states
qualifying conditions and escalates any arithmetic as `requires_computation`.

This is defensible as product policy and it removes a failure mode that could not
be fixed within the timeline.

---

## 8. Build order

| Order | Build | Gate before moving on |
|---|---|---|
| 1 | `data/sop_specs/` -> `generate_sops.py` -> `data/sop/` | ~20 SOPs validate |
| 1b | `config/taxonomy.yaml` derived *from* the SOP set | Taxonomy frozen |
| 2 | `schemas.py`, `sop/loader.py`, `tests/` skeleton | SOPs load and validate |
| 3 | `scripts/generate_emails.py` -> `emails.jsonl` | Leakage check passes |
| 4 | `nodes/` + `graph.py` | End-to-end run on 10 emails |
| 5 | `models/calibration.py` + `eval/` | Risk–coverage curve exists |
| 6 | `app/`, `Dockerfile`, README | Clean-machine run verified |

Steps 1–2 are cheap and unblock everything. Step 5 is the graded contribution and
must not be reached later than Day 4.
