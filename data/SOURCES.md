# Data sources, licensing, and privacy

Nothing in `data/` is real citizen correspondence or an internal agency procedure.

## Inventory

| Asset | Origin | Use and licence position |
|---|---|---|
| `data/sop/*.md` | 17 author-written synthetic SOPs | Original wording based on public IRAS facts; source pages are cited, not copied |
| `data/scenarios/*.yaml` | 116 author-written situations | Inputs for synthetic email generation |
| `data/generated/emails.jsonl` | 3,000 GPT-4o outputs | Training and evaluation corpus |
| `data/splits/splits.json` | Seeded, scenario-grouped split | 1,477 train / 646 calibration / 877 test |
| IRAS guidance | 30 public URLs | Fact-checking only; fetched pages are not committed or redistributed |
| CFPB complaints | Public database, accessed through Hugging Face | Writing-style reference only; no complaint text is retained or reused |
| MiniLM-L6 | Hugging Face | Apache 2.0; see the [base-model notice](../models/all-MiniLM-L6-v2/NOTICE.md) and [fine-tuned-model notice](../models/classifier/NOTICE.md) |

## Synthetic SOPs

- The SOPs are not scraped and do not represent IRAS internal material, wording, queues, or service levels.
- Each of 148 facts names a public IRAS source in its YAML spec.
- `python scripts/generate_sops.py --check` rejects missing source handles and broken holdout rules.
- The runtime loader rejects SOPs without `synthetic: true` or without a public reference.
- The [SOP schema and corpus design](sop_specs/README.md) explains routing fields and deliberate knowledge holdouts.

### Use of public guidance

`scripts/fetch_reference.py` fetched a fixed list of pages into the gitignored
`.scratch/` directory on 1 September 2026. The fetch used a delay and did not crawl
links. IRAS's `robots.txt` was checked on 3 September 2026 and returned HTTP 404;
the absence of crawler rules was not treated as permission to redistribute content.

The repository contains author-written restatements and source URLs, not copies of
the pages. Rates, caps, and deadlines are therefore a dated snapshot and may become
stale. A production corpus would need effective dates, scheduled source review, and
approval by the responsible agency.

## Synthetic emails

Real tax correspondence would contain sensitive personal and financial information,
so it was not suitable for this exercise. Instead, GPT-4o generated 3,000 emails from
the [scenario specifications](scenarios/README.md).

Controls against synthetic shortcuts:

- The generator sees the situation, persona, style, and season, but never the class label.
- Labels and source SOPs are attached after generation.
- Content, writing style, and season vary independently.
- Train, calibration, and test splits are grouped by scenario, not individual email.
- `python scripts/check_leakage.py` checks balance, vocabulary leakage, duplicates, boilerplate, length, and flag confounding.
- The generator, classifier baseline, drafter, and judge use separated model roles defined in `config/models.yaml`.

### Generated identifiers

- Identifiers were generated for testing and were not sourced from real people.
- NRIC-shaped values use valid checksums so the scrubber can be tested realistically.
- Addresses, phone numbers, and postal codes use plausible formats.
- Values were not checked against official registries, so accidental collision cannot be ruled out.
- `plant_pii` records what was inserted, making scrub recall measurable.

### Runtime privacy

- PII is scrubbed locally before classification or any external drafting call.
- Rehydration happens locally after drafting.
- Missed identifiers are masked before evaluation results are written.
- `.env` is gitignored, and key-status code exposes only booleans.

## CFPB style reference

The [CFPB Consumer Complaint Database](https://www.consumerfinance.gov/data-research/consumer-complaints/)
was viewed through a Hugging Face copy to understand how people write when confused,
frustrated, or under financial stress. It was used only as a register reference:

- no complaint text is committed;
- no complaint text was copied into prompts or generated emails; and
- no complaint text was used for model training or evaluation.

## Model and API assets

- The repository contains an 87.3 MiB MiniLM base checkpoint and an 87.4 MiB fine-tuned checkpoint.
- Both model directories include Apache 2.0 licence and attribution files.
- Gemini, Groq, and OpenAI are accessed under their provider terms; their weights are not redistributed.

## Coverage limits

- **Situation breadth:** 3,000 emails represent only 116 underlying situations.
- **Synthetic distribution:** performance may not transfer to a real inbox.
- **Scope:** individual income tax, English, and single-message emails only.
- **Missing formats:** no attachments, threads, or forwarded chains.
- **Author influence:** scenario choice and class balance reflect the project author's judgement.

The most useful next data step is more distinct situations plus a validation-only
sample of lawfully obtained, properly anonymised real correspondence.
