# Human draft evaluation and judge agreement

**Status: COMPLETE**

Generated: `2026-09-04T09:51:50+00:00`

## Evaluation coverage

| Quantity | Value |
|---|---:|
| Review design | Single Reviewer |
| Successful drafts | 24 |
| LLM-judge verdicts | 24 |
| Resolved human references | 24 |

Completion checks:

- PASS — all successful drafts judged
- PASS — all successful drafts human reviewed
- PASS — no unresolved fields
- PASS — one reviewer present

## Human draft-quality ratings

Human labels are the reference. Intervals are 95% Wilson intervals for the
observed sample proportions.

| Dimension | Passing | Rate | 95% interval |
|---|---:|---:|---:|
| Groundedness | 24/24 | 100.0% | 86.2%–100.0% |
| Correct Next Step | 24/24 | 100.0% | 86.2%–100.0% |
| Safety Privacy | 24/24 | 100.0% | 86.2%–100.0% |
| Completeness | 24/24 | 100.0% | 86.2%–100.0% |
| Tone | 18/24 | 75.0% | 55.1%–88.0% |
| Overall Acceptability | 23/24 | 95.8% | 79.8%–99.3% |

Human ratings by route:

| Route | Items | Grounded | Next step | Safety | Complete | Tone | Overall |
|---|---:|---:|---:|---:|---:|---:|---:|
| auto_reply | 10 | 100.0% | 100.0% | 100.0% | 100.0% | 90.0% | 100.0% |
| redirect | 14 | 100.0% | 100.0% | 100.0% | 100.0% | 64.3% | 92.9% |

## LLM judge versus human groundedness

| Metric | Result |
|---|---:|
| Comparable items | 24 |
| Raw agreement | 91.7% |
| Cohen's κ | — |
| Human-identified ungrounded drafts | 0 |
| Judge ungrounded recall | — |
| Judge ungrounded precision | 0.0% |

Confusion matrix (rows are human reference; columns are LLM judge):

| Human \ Judge | Grounded | Ungrounded |
|---|---:|---:|
| Grounded | 22 | 2 |
| Ungrounded | 0 | 0 |

Agreement by route:

| Route | Comparable items | Agreement | Cohen's κ |
|---|---:|---:|---:|
| auto_reply | 10 | 80.0% | — |
| redirect | 14 | 100.0% | — |

## Inter-human reliability

Not measured because this run uses one human reviewer.

## Interpretation and limitations

One resolved human rating set is the reference for draft quality and judge comparison. Inter-human reliability is not measured. Wilson intervals show denominator uncertainty for the observed sample rates.

- Human review uses synthetic correspondence and authored SOPs, not real inbox mail.
- Agreement validates this judge prompt and sample, not arbitrary future prompts.
- A sample with no human-identified ungrounded draft cannot estimate judge recall.
- One reviewer supplied the human reference, so individual rating bias and inter-human reliability are not measured.
- The rating sheet did not include notes for every negative label, so some item-level rationale is unavailable.
- Positive PASS values in the overall-acceptability column were normalized to the rubric's equivalent ACCEPT label.

The full annotation rubric and procedure are in [`eval/HUMAN_EVAL.md`](../HUMAN_EVAL.md).
The machine-readable result is [`judge_human_agreement.json`](judge_human_agreement.json).
