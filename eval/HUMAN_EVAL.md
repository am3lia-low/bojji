# Human evaluation protocol

This protocol measures successful draft quality and checks the LLM groundedness
judge against blinded human review. Human labels are the reference. The committed
report uses one resolved reviewer sheet, so it does not measure inter-human
reliability. See the [current report](results/HUMAN_EVAL_REPORT.md).

## Sample and blinding

- `eval/run_eval.py` takes a seeded random sample without replacement from automated routes.
- Provider failures count toward drafting availability but have no draft to review.
- Reviewers see the scrubbed email, supplied SOPs, and redacted draft.
- Reviewer sheets hide the judge verdict, classifier output, confidence, labels, scenario ID, and source email ID.
- Do not inspect `manifest.json` or `drafts.json` while rating.
- One reviewer rates every successful draft.
- An optional second reviewer rates `max(20, 30%)` items, capped at the sample size,
  when inter-human reliability is required.

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

For a redirect, completeness means that the draft performs every step required by
the redirect SOP. It does not need to answer the out-of-scope question. A redirect
may therefore pass completeness while still receiving a lower tone or overall
decision if it is too abrupt for the citizen's situation.

## Why these labels and scores

The reviewer does not assign an arbitrary numerical score. Each field is a fixed
categorical decision that answers one auditable question:

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

   If an underlying model's free-tier daily window is exhausted, the command stops
   after the first 429. Rerun it after the reported window clears; completed
   current-model verdicts are skipped. Use `--max-items 1` for a single-call check.

   If reviewer CSVs were prepared before judging finished, refresh only the hidden
   manifest labels afterward. This verifies that none of the reviewer evidence
   changed:

```bash
python eval/human_review.py sync-judge
```

3. Create the blinded primary-reviewer sheet. Create the optional overlap sheet only
   when running the stronger double-review design:

```bash
python eval/human_review.py prepare --reviewer-id reviewer_a --output eval/human_review/reviewer_a.csv
python eval/human_review.py prepare --reviewer-id reviewer_b --overlap-only --output eval/human_review/reviewer_b.csv
```

4. Resolve every `UNSURE` value before scoring. If using two reviewers, review
   independently, preserve both original sheets before discussion, and adjudicate
   every disagreement in a separate sheet. Agreement must use the original ratings.
5. Reproduce the committed single-reviewer report:

```bash
python eval/human_review.py score --ratings eval/human_review/reviewer_a.csv --single-reviewer --normalize-overall-pass --allow-missing-rating-notes
```

The command records three limitations rather than hiding them: there is one reviewer,
some negative labels lack notes, and positive `PASS` values entered in the overall
column are normalized to the equivalent allowed label, `ACCEPT`.

For a double-review run, use:

```bash
python eval/human_review.py score --ratings <original-reviewer-a.csv> <original-reviewer-b.csv> --adjudication <adjudicated.csv>
```

The scorer rejects invalid categories, changed evidence, unknown IDs, unexplained
adjudication failures, unresolved adjudication fields, and inconsistent hard-failure
acceptance. Reviewer working CSVs are gitignored; the generated JSON and Markdown
reports are committed. Incomplete annotations remain marked `incomplete`.

## Outputs

- Human pass and acceptance rates with 95% Wilson intervals
- Human-human agreement and Cohen's kappa when an overlap is supplied
- Judge-human agreement, kappa, and confusion matrix
- Judge precision and recall for human-identified ungrounded drafts
- Results by auto-reply and redirect
- Review, judge, overlap, and unresolved-item coverage

Kappa is undefined if either rater uses only one class. Judge recall is undefined if
humans find no ungrounded draft. Results apply only to the recorded prompt, model,
sample, and synthetic setting.
