# Human draft evaluation and judge agreement

**Status: HUMAN REVIEW NOT RUN**

> This report is not evidence of draft quality or judge validity yet. It will be
> replaced by the scorer after independent human ratings are complete.

## Current state

The live sample attempted 50 drafts. Twenty-four succeeded and are eligible for
review; the other 26 were availability failures (12 timeouts, 10 rate limits, and 4
other API errors) with no text to score. Compound Mini judged 21 of the successful
drafts: 19 grounded and 2 ungrounded (90.5% groundedness; 87.5% judge availability).
Three judge calls were rate-limited. No human-groundedness or judge-agreement result
is reportable yet, so the machine score is not validated evidence of draft quality.

- Generate the blinded reviewer forms from the 24 successful drafts.
- Collect one full review and the fixed 20-item second-review overlap.
- Adjudicate every disagreement and `UNSURE` rating.
- Run `python eval/human_review.py score ...` to replace this file with the result.

The current [machine-readable status](judge_human_agreement.json) keeps all quality
claims disabled until those steps are complete.
