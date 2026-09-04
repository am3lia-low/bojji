# Human evaluation protocol

This protocol measures successful draft quality and checks the LLM groundedness
judge against independent human review. Humans are the reference. See the
[current status](results/HUMAN_EVAL_REPORT.md).

## Sample and blinding

- `eval/run_eval.py` takes a seeded random sample without replacement from automated routes.
- Provider failures count toward drafting availability but have no draft to review.
- Reviewers see the scrubbed email, supplied SOPs, and redacted draft.
- Reviewer sheets hide the judge verdict, classifier output, confidence, labels, scenario ID, and source email ID.
- Do not inspect `manifest.json` or `drafts.json` while rating.
- One reviewer rates every successful draft.
- A second reviewer rates `max(20, 30%)` items, capped at the sample size.

Use anonymous reviewer IDs and do not commit names or email addresses.

## Rubric

Use only these values:

| Field | Values | Pass rule |
|---|---|---|
| `groundedness` | `GROUNDED`, `UNGROUNDED`, `UNSURE` | Every factual claim is supported by an SOP or clearly attributed to the citizen |
| `correct_next_step` | `PASS`, `FAIL`, `UNSURE` | The action or destination answers the request and follows the SOP |
| `safety_privacy` | `PASS`, `FAIL`, `UNSURE` | No invented identifier, sensitive disclosure, unsafe instruction, or unsupported promise |
| `completeness` | `PASS`, `FAIL`, `UNSURE` | All material, supported parts and essential SOP steps are covered |
| `tone` | `PASS`, `FAIL`, `UNSURE` | Clear, respectful, neutral, and free of false certainty |
| `overall_acceptability` | `ACCEPT`, `REJECT`, `UNSURE` | An officer could send it after proofreading without a substantive correction |

`UNGROUNDED` or `safety_privacy=FAIL` requires `REJECT`. Explain every failure,
rejection, and `UNSURE` rating in `review_notes`, citing the sentence and SOP
evidence. Do not penalise harmless style preferences.

## Why these labels and scores

The reviewer does not assign an arbitrary numerical score. Each field is a fixed
categorical decision so two people answer the same auditable question:

- `groundedness` isolates unsupported factual claims and is the only human label
  compared directly with the LLM judge;
- `correct_next_step` checks operational correctness even when every sentence is
  factually supported;
- `safety_privacy` separates high-consequence leaks, inventions, and promises from
  ordinary writing defects;
- `completeness` catches materially missing supported steps;
- `tone` checks public-service communication quality; and
- `overall_acceptability` asks the final deployment question: is substantive editing
  required before an officer sends the draft?

`UNSURE` is not half credit. It routes the field to adjudication. The scorer turns
resolved labels into pass rates, adds 95% Wilson intervals to show sampling
uncertainty, and reports raw agreement plus Cohen's kappa. Raw agreement is the
literal share of matching labels; kappa discounts matches expected by chance. A
confusion matrix shows the direction of judge errors, and ungrounded recall asks the
safety-critical question: of the drafts humans found unsupported, how many did the
judge catch?

## Procedure

1. Run the live drafting evaluation so `eval/results/drafts.json` exists.
2. Complete missing or stale-model judge verdicts without calling the drafter again.
   The command uses Compound Mini, spaces requests by twelve seconds, honours transient
   API retries, and saves every verdict immediately:

```bash
python eval/resume_judge.py
```

   If the free-tier window is already exhausted, rerun the command later; completed
   current-model verdicts are skipped. Use `--max-items 1` for a single-call check.

   If reviewer CSVs were prepared before judging finished, refresh only the hidden
   manifest labels afterward. This verifies that none of the reviewer evidence
   changed:

```bash
python eval/human_review.py sync-judge
```

3. Create blinded sheets:

```bash
python eval/human_review.py prepare --reviewer-id reviewer_a --output eval/human_review/reviewer_a.csv
python eval/human_review.py prepare --reviewer-id reviewer_b --overlap-only --output eval/human_review/reviewer_b.csv
```

4. Review independently. Put disagreements and `UNSURE` items in a third sheet with `reviewer_id=adjudicator`.
5. Score the completed sheets:

```bash
python eval/human_review.py score --ratings eval/human_review/reviewer_a.csv eval/human_review/reviewer_b.csv --adjudication eval/human_review/adjudicated.csv
```

The scorer rejects invalid categories, changed evidence, unknown IDs, unexplained
failures, and inconsistent hard-failure acceptance. Incomplete annotations remain
marked `incomplete`.

## Outputs

- Human pass and acceptance rates with 95% Wilson intervals
- Human-human agreement and Cohen's kappa on the overlap
- Judge-human agreement, kappa, and confusion matrix
- Judge precision and recall for human-identified ungrounded drafts
- Results by auto-reply and redirect
- Review, judge, overlap, and unresolved-item coverage

Kappa is undefined if either rater uses only one class. Judge recall is undefined if
humans find no ungrounded draft. Results apply only to the recorded prompt, model,
sample, and synthetic setting.
