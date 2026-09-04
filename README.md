# Calibrated Triage for Citizen Correspondence

A prototype for triaging a tax authority's individual-income-tax inbox. It removes
personal data locally, classifies each email, retrieves the relevant synthetic SOP,
and either prepares a grounded response or sends the item to an officer with a clear
reason.

**The main contribution is not drafting. It is knowing when not to draft.**

> **Demo video (3-5 minutes): TODO - add the URL before submission.**

## Problem and objective

An agency inbox mixes routine questions, private-record lookups, hardship, and fraud.
The objective is to answer one operational question: **what share can be automated,
at what error rate, while reliably escalating cases that need an officer?**

## What it does

```text
email
  -> scrub PII locally
  -> classify into 1 of 10 intents with a fine-tuned MiniLM-L6 model
  -> roll up to 1 of 5 routing buckets and calibrate confidence
  -> retrieve SOPs by an exact class-to-SOP mapping
  -> route
       -> auto-reply or redirect: ask Gemini for an SOP-grounded draft
       -> officer queue: attach the SOP and an escalation reason
```

LangGraph makes the safety gate structural: escalated emails have no edge to the
drafting node. All steps are local except eligible drafting, which sends only scrubbed
text to Gemini.

The Streamlit app shows the inbox, editable drafts, escalation reasons, supporting
SOPs, and risk-coverage results. It never sends an email.

## Quick start

Requires Python 3.11 or later. The reported run used Windows 11 and Python 3.14.

```bash
git clone https://github.com/am3lia-low/bojji.git
cd bojji
python -m venv .venv

# macOS/Linux
source .venv/bin/activate

# Windows PowerShell (run this instead of the line above)
.venv\Scripts\Activate.ps1

python -m pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

Open <http://localhost:8501>. No API key is needed to inspect the inbox or run the
local routing pipeline. Without a Gemini key, routes that are eligible for drafting
record a drafting failure and remain in the officer queue with their SOP attached.

For live drafts, copy `.env.example` to `.env` and set `GEMINI_API_KEY`:

```bash
# macOS/Linux
cp .env.example .env

# Windows PowerShell
Copy-Item .env.example .env
```

Optional fallback and evaluation keys are documented in `.env.example`.

### Free-tier scope

The Streamlit app, local routing pipeline, Docker image, tests, and offline
evaluation do not require a paid service. Live drafting requires your own Gemini
free-tier key. A Groq key is needed only to regenerate the evaluation judge outputs;
Streamlit does not call Groq. The judge uses `groq/compound-mini`, disables its
external tools, conservatively spaces long requests to respect the rolling token
limit, and saves each verdict as it completes.

A full 50-item drafting evaluation can reach free-tier quotas, so its outputs are
committed for inspection and the reproducible offline command uses `--no-draft`.
GPT-4o was used only at build time to create the frozen synthetic emails; running
the solution does not require an OpenAI key. Free-tier access is a constraint, not
the model-selection rationale: the choices are based on privacy, latency, task fit,
and the ability to evaluate complete SOP evidence.

### Tests and evaluation

```bash
python -m pytest
python eval/run_eval.py --no-draft
```

The second command regenerates offline reports in `eval/results/` without an API.
Omit `--no-draft` only to run the quota-using drafting evaluation.

After a successful live drafting run, prepare blinded human-review sheets and score
them without another API call:

```bash
python eval/human_review.py prepare --reviewer-id reviewer_a --output eval/human_review/reviewer_a.csv
python eval/human_review.py prepare --reviewer-id reviewer_b --overlap-only --output eval/human_review/reviewer_b.csv
python eval/human_review.py score --ratings eval/human_review/reviewer_a.csv eval/human_review/reviewer_b.csv
```

### Docker

```bash
docker build -t citizen-triage-agent .
docker run --rm -p 8501:8501 citizen-triage-agent
```

Add `--env-file .env` to `docker run` for live drafting. The image uses CPU-only
PyTorch and includes the model weights.

## Why this design

- **Bounded routing:** risky, private, unsupported, and low-confidence cases go to an officer.
- **Local classification:** MiniLM keeps original emails off external services and returns calibratable probabilities.
- **Measured model choice:** on 30 emails, MiniLM reached 0.809 macro-F1 at 0.67 s/email; the LLM baseline reached 0.540 at 10.6 s/email.
- **Per-bucket thresholds:** two buckets can automate; the other three always escalate.
- **Exact SOP lookup:** 14 indexed documents do not need uncertain vector search; see the [SOP schema and corpus design](data/sop_specs/README.md).
- **Visible failure:** missing keys, timeouts, and provider failures stay in the officer queue instead of using a fallback draft.

## Data

[Data sources, licensing, and privacy](data/SOURCES.md) documents the detailed
provenance and handling of every input. The short version is:

| Asset | Origin and use | Privacy and licensing position |
|---|---|---|
| 17 synthetic SOPs | Author-written from public IRAS individual-income-tax guidance | Original wording with source URLs; no internal agency material or copied pages |
| [116 scenario specifications](data/scenarios/README.md) | Author-written situations used as generation inputs | No real citizen correspondence |
| 3,000 emails | Generated once by GPT-4o at build time; no OpenAI key is needed to run the solution | Fabricated identifiers only; generated values were not checked against official registries |
| CFPB complaints | Register/style reference only | No complaint text is committed, copied into the corpus, or used for training/evaluation |
| MiniLM-L6 weights | `sentence-transformers/all-MiniLM-L6-v2` | Apache 2.0 license and notices are stored beside the weights |

The generator saw the situation, persona, style, and season - never the class label.
A leakage check covers balance, system vocabulary, duplicates, boilerplate, length,
and flag confounding.

Scenario-grouped splits prevent variants of one situation crossing partitions: 1,477
train, 646 calibration, and 877 test emails.

## Evaluation methodology

The primary question is: **what share of emails can the system automate, and what
error rate does it incur on that share?** That makes risk-coverage the primary metric,
not raw accuracy alone.

- **Benchmarking:** macro-F1, bucket accuracy, escalation recall, PII recall, and risk-coverage measure routing effectiveness.
- **Calibration:** temperature scaling is fitted on `calibration` and evaluated on `test` using expected calibration error.
- **Ablations:** calibration, threshold policy, and PII scrubbing are varied separately.
- **Comparison:** MiniLM and a zero-shot LLM use the same 30-email sample and fixed labels.
- **Uncertainty:** 95% intervals bootstrap 2,000 whole scenarios within class strata.

A separate model judges unsupported draft claims. It judged 21 of 24 successful
drafts and marked 19 grounded (90.5%); three calls were rate-limited. The
[human-evaluation protocol](eval/HUMAN_EVAL.md) specifies blinded double review and
agreement measures. Human labels are still missing, so this machine score is not
validated evidence of draft quality. See the
[human-evaluation status](eval/results/HUMAN_EVAL_REPORT.md).

Thresholds were frozen before test evaluation: `auto_answerable=0.93` first met the
10% development-risk target; `out_of_scope=0.58` was the first with no observed
development errors.

## Results

Offline results use the 877-email test split and seed 42.

| Metric | Result |
|---|---:|
| Macro-F1, 10 classes | **0.859** (95% interval 0.769-0.923) |
| Macro-F1, 5 buckets | 0.917 (0.862-0.971) |
| Bucket accuracy | 0.928 (0.874-0.976) |
| Must-escalate recall | **1.000** (456/456) |
| Unsafe must-escalate automations | **0/456** |
| Coverage at the frozen operating point | **11.6%** (102/877) |
| Risk among automated actions | **1.0%** (1/102; interval 0.0%-3.7%) |
| PII scrub recall on planted values | **1.000** (99/99) |
| Area under the risk-coverage curve | 0.0513 |
| Live drafting availability | **48.0%** (24/50 successful) |

The 26 live drafting failures were 12 timeouts, 10 rate limits, and 4 other API
errors. They are availability failures, not fabricated zero-quality drafts, and
remain outside the groundedness denominator because no text existed to review.

The aggregate coverage figure describes this deliberately balanced benchmark, not a
production inbox. Real coverage depends on the agency's seasonal topic mix.

Ablations were modest: calibration changed ECE from 0.1507 to 0.1502 without changing
AURC; per-bucket thresholds improved AURC from 0.0584 to 0.0513; PII scrubbing changed
macro-F1 by -0.0011. The fitted temperature (`T=0.998`) is a negative result.

## Limitations

- **Limited breadth:** 3,000 emails come from only 116 situations, producing wide scenario-level intervals.
- **Synthetic ceiling:** results do not establish performance on real correspondence.
- **PII scope:** recall covers planted shapes, not every form a citizen may write.
- **Scam language:** the lexical flag reached 95.2% test recall but misses indirect reports.
- **Incomplete human evidence:** independent draft ratings and judge-human agreement are not yet reported.
- **Narrow corpus:** one tax type, English-only single emails, synthetic SOPs, and no attachments or threads.
- **Provider risk:** free-tier models and quotas change; routing quality and drafting availability need separate monitoring.

## Deployment considerations

The target user is a correspondence officer working inside an agency environment,
not a citizen. The classifier and routing policy can run on an on-premise CPU; only
scrubbed text from routes eligible for drafting crosses the boundary to Gemini. The
fine-tuned checkpoint is 87.4 MiB, while the repository carries roughly 175 MiB across
the base and fine-tuned weight copies. Measured sequential classification was about
0.67 seconds per email, or roughly 19 single-core hours per 100,000 messages before
batching improvements. If a production inbox matched the balanced benchmark, the
11.6% operating coverage would imply about 11,600 drafting calls per 100,000 emails;
the real cost must be recalculated from the agency's topic mix and provider pricing.
Production-scale drafting would likely require paid provider capacity or a
self-hosted model; this prototype does not claim that free-tier quotas support that
volume.

Post-deployment monitoring should track bucket-level accuracy and calibration,
officer overrides, escalation-reason mix, route-specific coverage and risk, PII
leakage tests, and drafting availability. The clearest deployment risk is seasonal
distribution shift: filing, assessment, and payment periods change both volume and
topic mix. Confidence may then stop matching correctness even when aggregate
accuracy looks stable. Mitigations are rolling labelled samples, seasonal
recalibration, alerts on confidence distributions and override rates, and a policy
that keeps high-consequence or unsupported cases outside automated drafting.

## Development narrative

- **Taxonomy:** 12 classes became 10; two identical redirect classes merged, while `account_specific` became a cross-topic flag.
- **Retrieval:** vector search was dropped because exact lookup is safer for 14 indexed SOPs.
- **Calibration:** isotonic regression was dropped as too flexible for 646 calibration emails.
- **PII:** broad address rules were removed after they scrubbed ordinary language without useful recall gains.
- **Auditing:** tests found PII ordering, punctuation, citation parsing, and stale-metric bugs.
- **Operations:** provider retirements led to recorded model IDs and explicit drafting failures.

## Coding-agent usage

Claude Code (Claude Opus) supported implementation, test creation, and adversarial
audits. Codex was used to audit this README against the repository and assessment
brief, simplify it, and verify the documented commands. Agent output was reviewed by
the author, and numerical claims were checked against committed evaluation artifacts
or reproduced at the command line.

Project-specific Codex and Claude Code records are listed in the
[coding-agent log index](AI%20assistant%20logs/README.md). The directory contains
sanitized JSONL session exports, an audit manifest, and the consolidated brainstorm
log. Credentials, personal paths, and identifying assessment details are redacted.
