"""Test whether the generated corpus is fair, or whether it leaks its labels.

BUILD-TIME ONLY. Run after ``generate_emails.py``, before training.

**This is the check that would invalidate every downstream number.** The scenarios
describe situations and never name a class, so the generator cannot encode the
answer in the wording -- but intent is not evidence. These tests look for the
evidence.

Six checks, each catching a different way a corpus can flatter the model that is
trained on it:

1. **Vocabulary leakage.** TF-IDF plus logistic regression -- a bag of words with
   no semantics -- is fitted on the emails. Topical words genuinely differ by
   class, so a moderate score is expected and healthy. A near-perfect score means a
   giveaway token exists and the classifier would learn the generator's tell.
2. **Label words.** No email may contain its own class name, or the distinctive
   vocabulary of the taxonomy itself.
3. **Length artefacts.** If a two-feature model on length alone separates the
   classes, the generator encoded the label in how much it wrote.
4. **Near-duplicates.** Variants that collapse into near-copies shrink the
   effective dataset, and a duplicate spanning the train/test boundary inflates the
   test score outright.
5. **Boilerplate.** A shared opening or sign-off that correlates with class is a
   giveaway token in disguise.
6. **Flag confounding.** If every computation-demanding email were one class, the
   flag's measured precision would really be the classifier's.

Usage:
    python scripts/check_leakage.py
    python scripts/check_leakage.py --strict     # non-zero exit on any warning
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Final

import numpy as np
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.model_selection import cross_val_predict, cross_val_score
from sklearn.pipeline import make_pipeline
from sklearn.tree import DecisionTreeClassifier

ROOT: Final[Path] = Path(__file__).resolve().parent.parent
EMAILS: Final[Path] = ROOT / "data" / "generated" / "emails.jsonl"
SEED: Final[int] = 42

#: Above this, a bag of words separates the classes so well that the text almost
#: certainly contains a giveaway. Set high on purpose: topical vocabulary SHOULD
#: be predictive, and a low threshold would fail an honest corpus.
LEAKAGE_CEILING: Final[float] = 0.95

#: Below this, the classes are barely separable at all -- which would suggest the
#: scenarios are too similar to each other, not that the corpus is clean.
LEAKAGE_FLOOR: Final[float] = 0.30

#: Length alone should be close to chance. Some signal is inevitable (a scam report
#: is naturally shorter than a relief question); a lot of signal is a generator
#: artefact.
LENGTH_CEILING: Final[float] = 0.30

#: Cosine similarity above which two emails are treated as near-copies.
DUPLICATE_THRESHOLD: Final[float] = 0.90

#: SYSTEM vocabulary -- words belonging to the machinery, not to a citizen.
#:
#: The distinction this check turns on, and which an earlier version of it got
#: wrong: a landlord writing about a flat says "rental income", because that is the
#: ordinary English name for the thing. That is not leakage. Leakage is an email
#: that reads as though it knows the taxonomy exists.
#:
#: So the test is not "does this word also name a class" but "would a member of the
#: public ever write it". Class names that double as everyday phrases -- "rental
#: income", "tax relief", "foreign income" -- are deliberately absent from this
#: list; `check_confinement` below is what would catch them if they ever did become
#: tells, and it does so from the data rather than from a hand-written list.
SYSTEM_WORDS: Final[tuple[str, ...]] = (
    "auto answerable", "no supporting sop", "out of scope", "account specific",
    "hardship or waiver", "standard operating procedure", "classify this",
    "triage", "escalation bucket", "intent label",
    "sop-", "human queue", "confidence score", "routing decision",
)

#: Words that are system vocabulary in the system's sense but ordinary English in a
#: citizen's. ``classification`` is the case: "could you confirm the classification
#: for my case" is how someone asks about their residency status, and failing the
#: corpus for it is the same mistake as failing "rental income" for naming its class
#: (S4 of the training notebook). They are caught only in a phrase that no member of
#: the public would write.
AMBIGUOUS_SYSTEM_PHRASES: Final[tuple[str, ...]] = (
    "classification bucket", "classification label", "classification model",
    "classification confidence", "the classifier",
)

#: Minimum occurrences before a word's class distribution is worth reading.
CONFINEMENT_MIN_COUNT: Final[int] = 25


def load() -> list[dict[str, object]]:
    if not EMAILS.exists():
        raise SystemExit(
            f"{EMAILS.relative_to(ROOT)} not found.\n"
            "Run: python scripts/generate_emails.py"
        )
    return [json.loads(line) for line in EMAILS.read_text(encoding="utf-8").splitlines()]


class Report:
    """Collects results so every check runs before anything exits."""

    def __init__(self) -> None:
        self.failures: list[str] = []
        self.warnings: list[str] = []

    def ok(self, title: str, detail: str) -> None:
        print(f"  [ ok ] {title}\n         {detail}")

    def warn(self, title: str, detail: str) -> None:
        self.warnings.append(title)
        print(f"  [WARN] {title}\n         {detail}")

    def fail(self, title: str, detail: str) -> None:
        self.failures.append(title)
        print(f"  [FAIL] {title}\n         {detail}")


def check_vocabulary(texts: list[str], labels: np.ndarray, report: Report) -> None:
    """Fit a bag of words and see how well it separates the classes."""
    print("\n1. Vocabulary leakage (TF-IDF + logistic regression)")
    model = make_pipeline(
        TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True),
        LogisticRegression(max_iter=2000, random_state=SEED),
    )
    predicted = cross_val_predict(model, texts, labels, cv=5)
    accuracy = float((predicted == labels).mean())
    chance = 1.0 / len(set(labels))

    detail = f"accuracy {accuracy:.3f}  (chance {chance:.3f}, ceiling {LEAKAGE_CEILING})"
    if accuracy > LEAKAGE_CEILING:
        report.fail("a bag of words is near-perfect -- the text carries a giveaway", detail)
    elif accuracy < LEAKAGE_FLOOR:
        report.warn("classes barely separable -- scenarios may be too alike", detail)
    else:
        report.ok("in the expected band", detail)

    # Whatever the score, show what the weak model keys on. A token that IS the
    # label, or a generator artefact, is visible here immediately.
    model.fit(texts, labels)
    vectoriser, classifier = model.steps[0][1], model.steps[1][1]
    names = np.array(vectoriser.get_feature_names_out())
    print("\n         top features per class:")
    for i, label in enumerate(classifier.classes_):
        top = names[np.argsort(classifier.coef_[i])[-6:]][::-1]
        print(f"           {label:26} {', '.join(top)}")


def check_system_words(rows: list[dict[str, object]], report: Report) -> None:
    """No email may read as though it knows the taxonomy exists."""
    print("\n2. System vocabulary in the email text")
    hits: list[tuple[str, str]] = []
    for row in rows:
        text = f"{row['subject']} {row['body']}".lower()
        for word in (*SYSTEM_WORDS, *AMBIGUOUS_SYSTEM_PHRASES):
            if re.search(rf"\b{re.escape(word)}", text):
                hits.append((str(row["id"]), word))
    if hits:
        shown = ", ".join(f"{i}:{w}" for i, w in hits[:6])
        report.fail(f"{len(hits)} emails use system vocabulary", shown)
    else:
        report.ok("no email uses the system's own vocabulary",
                  f"{len(SYSTEM_WORDS)} terms checked")


def check_confinement(rows: list[dict[str, object]], report: Report) -> None:
    """Look for common words that appear in exactly one class.

    The empirical version of the label-word question, and the one that actually
    answers it. A generated tell would be perfectly confined to its class; genuine
    vocabulary bleeds -- "relief" turns up in relief, hardship and foreign-income
    emails alike. Reported for inspection rather than failed, because some topic
    nouns ("scam", "rental") are legitimately confined and that is not a defect.
    """
    print("\n2b. Words confined to a single class")
    per_word: dict[str, Counter[str]] = {}
    for row in rows:
        label = str(row["label"])
        text = f"{row['subject']} {row['body']}".lower()
        for token in set(re.findall(r"[a-z]{4,}", text)):
            per_word.setdefault(token, Counter())[label] += 1

    confined = sorted(
        ((word, counts) for word, counts in per_word.items()
         if sum(counts.values()) >= CONFINEMENT_MIN_COUNT and len(counts) == 1),
        key=lambda kv: -sum(kv[1].values()),
    )
    if confined:
        shown = ", ".join(
            f"{word}({sum(counts.values())}->{next(iter(counts))})"
            for word, counts in confined[:8]
        )
        report.ok(f"{len(confined)} common words appear in one class only", shown)
        print("         inspect these: a topic noun is expected, a system word is not")
    else:
        report.ok("no common word is confined to a single class", "")


def check_length(rows: list[dict[str, object]], labels: np.ndarray, report: Report) -> None:
    """Length alone should be close to chance."""
    print("\n3. Length as a giveaway")
    features = np.array([[len(str(r["body"])), len(str(r["body"]).split())] for r in rows])
    baseline = float(cross_val_score(
        DummyClassifier(strategy="most_frequent"), features, labels, cv=5).mean())
    length_only = float(cross_val_score(
        DecisionTreeClassifier(max_depth=4, random_state=SEED), features, labels, cv=5).mean())

    detail = f"length-only {length_only:.3f}  (majority {baseline:.3f}, ceiling {LENGTH_CEILING})"
    if length_only > LENGTH_CEILING:
        report.warn("length is unexpectedly predictive", detail)
    else:
        report.ok("length carries little class signal", detail)


def check_duplicates(texts: list[str], rows: list[dict[str, object]], report: Report) -> None:
    """Variants must differ from one another."""
    print("\n4. Near-duplicates")
    matrix = TfidfVectorizer(min_df=1).fit_transform(texts)
    similarity = cosine_similarity(matrix)
    np.fill_diagonal(similarity, 0.0)

    pairs = np.argwhere(similarity > DUPLICATE_THRESHOLD)
    count = len(pairs) // 2
    detail = f"{count} pairs above {DUPLICATE_THRESHOLD}, max similarity {similarity.max():.3f}"

    if count > len(rows) * 0.02:
        report.warn("many near-duplicate pairs -- effective dataset is smaller than it looks",
                    detail)
    else:
        report.ok("variants are distinct", detail)

    if count:
        i, j = pairs[0]
        print(f"\n         closest pair ({similarity[i, j]:.3f}):")
        print(f"           {rows[i]['id']}: {str(rows[i]['body'])[:90]}")
        print(f"           {rows[j]['id']}: {str(rows[j]['body'])[:90]}")


def check_boilerplate(rows: list[dict[str, object]], report: Report) -> None:
    """A shared opening or closing that correlates with class is a giveaway."""
    print("\n5. Boilerplate")
    openings = Counter(" ".join(str(r["body"]).split()[:5]).lower() for r in rows)
    common, count = openings.most_common(1)[0]
    share = count / len(rows)
    detail = f"most common opening {share:.1%} of emails: {common!r}"
    if share > 0.10:
        report.warn("a single opening dominates", detail)
    else:
        report.ok("openings vary", detail)

    # Anchored to a sign-off POSITION, not to the words anywhere in the body.
    # "I sincerely hope my circumstances can be taken into consideration" is a
    # sentence a person in difficulty writes; "Sincerely," on its own line is a
    # template the generator failed to strip. Matching the bare word failed the
    # corpus on the former.
    placeholder = re.compile(r"\[your name\]|\[name\]|\[insert[^\]]*\]", re.I)
    signoff = re.compile(
        r"(?:^|\n)\s*(?:best regards|sincerely|yours (?:truly|faithfully|sincerely))"
        r"\s*[,.]?\s*$",
        re.I | re.M,
    )
    artefacts = [str(r["id"]) for r in rows
                 if placeholder.search(str(r["body"])) or signoff.search(str(r["body"]))]
    if artefacts:
        report.fail(f"{len(artefacts)} emails carry sign-off artefacts", ", ".join(artefacts[:5]))
    else:
        report.ok("no sign-off or placeholder artefacts", "")


def check_flag_confounding(rows: list[dict[str, object]], report: Report) -> None:
    """A flag concentrated in one class measures the classifier, not the flag."""
    print("\n6. Flag confounding")
    for flag in ("computation_requested", "account_specific"):
        positives = [r for r in rows if r.get(flag)]
        if not positives:
            report.warn(f"{flag}: no positive examples", "cannot be measured")
            continue
        spread = Counter(str(r["label"]) for r in positives)
        detail = (f"{len(positives)} positives ({len(positives)/len(rows):.1%}) "
                  f"across {len(spread)} classes: "
                  + ", ".join(f"{k}={v}" for k, v in spread.most_common(4)))
        if len(spread) < 3:
            report.warn(f"{flag} is concentrated in too few classes", detail)
        else:
            report.ok(f"{flag} spans the taxonomy", detail)



def _expected_class_count() -> int:
    """How many classes the taxonomy declares.

    Read rather than hardcoded: the class set is a projection of the SOP corpus and
    has already changed once (12 -> 10, merging the two out-of-scope classes and
    demoting ``account_specific`` to a flag). A literal here would turn the next
    such change into a spurious leakage failure.
    """
    import yaml

    path = ROOT / "config" / "taxonomy.yaml"
    if not path.exists():
        return 0
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return len(doc.get("classes") or ())


def check_balance(rows: list[dict[str, object]], report: Report) -> None:
    print("\n0. Balance")
    counts = Counter(str(r["label"]) for r in rows)
    spread = max(counts.values()) - min(counts.values())
    detail = (f"{len(rows)} emails, {len(counts)} classes, "
              f"min {min(counts.values())}, max {max(counts.values())}")
    expected = _expected_class_count()
    if len(counts) < expected:
        report.fail(f"only {len(counts)} of {expected} classes present", detail)
    elif spread > 2:
        report.warn("classes are unbalanced", detail)
    else:
        report.ok("balanced", detail)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="exit non-zero on warnings too")
    args = parser.parse_args()

    rows = load()
    texts = [f"{r['subject']}\n\n{r['body']}" for r in rows]
    labels = np.array([str(r["label"]) for r in rows])

    print(f"corpus: {len(rows)} emails from {EMAILS.relative_to(ROOT)}")
    report = Report()

    check_balance(rows, report)
    check_vocabulary(texts, labels, report)
    check_system_words(rows, report)
    check_confinement(rows, report)
    check_length(rows, labels, report)
    check_duplicates(texts, rows, report)
    check_boilerplate(rows, report)
    check_flag_confounding(rows, report)

    print("\n" + "=" * 72)
    if report.failures:
        print(f"FAILED: {len(report.failures)} check(s)")
        for title in report.failures:
            print(f"  - {title}")
        print("\nThe corpus is not fit to train on. Fix the generator and rebuild.")
        return 1
    if report.warnings:
        print(f"PASSED with {len(report.warnings)} warning(s)")
        for title in report.warnings:
            print(f"  - {title}")
        print("\nWarnings are reportable findings, not blockers. Record them in the "
              "limitations section rather than hiding them.")
        return 1 if args.strict else 0
    print("PASSED: no leakage detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
