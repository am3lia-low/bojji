"""Orthogonal flag detection -- signals that cut across classes.

RUNTIME. Lexical rules, not a model: auditable, free, testable, and inspectable by
someone who does not trust the classifier.

Some signals cannot be classes, because they cut *across* the taxonomy rather than
partitioning it. *"How much child relief will I get"* is `tax_reliefs`, which is
auto-answerable, but it must escalate anyway. A single softmax cannot express
"escalate regardless of predicted class", so these are detected separately and
applied after the bucket rollup, leaving the taxonomy a clean partition
(``sop_design.md`` S3.1).

Two flags are implemented, and both are **measured, not merely implemented**. The
scenario spec records whether each email asked for a computation or concerned the
writer's own record, so precision and recall cost nothing to obtain. If recall is
mediocre that is a finding to report, not something to hide.

A third, ``hardship_or_waiver``, is deliberately deferred (``BUILD.md`` S10):
hardship is already a *class*, so a plain hardship plea escalates today. The
uncovered case is narrower -- a hardship mention buried inside an otherwise
ordinary question -- and a third detector adds scope without closing a comparable
risk. The corpus still declares the trigger, so this is a known unenforced
trigger rather than a hidden gap.
"""

from __future__ import annotations

import re
from typing import Final

from triage.schemas import Classification, Flag

#: Second-highest class probability above which an email is treated as asking two
#: things. Free, because the distribution already exists -- two high-scoring classes
#: IS multi-intent. Informational only: it does not itself escalate.
MULTI_INTENT_THRESHOLD: Final[float] = 0.25

#: Phrasings that demand arithmetic.
#:
#: This flag gates the single failure mode the whole design exists to prevent: the
#: agent computing a tax or relief amount. Reliefs interact through ordering rules
#: and caps -- QCR first, WMCR takes the balance, $50,000 per child, $80,000
#: overall -- and a model over prose gets that wrong, confidently.
#:
#: A closed set of phrasings is the right tool precisely because it is dumb: it can
#: be read, argued with, and tested, and it cannot drift the way a prompt can.
_COMPUTATION_PATTERNS: Final[tuple[str, ...]] = (
    r"\bhow much\b",
    r"\bwhat amount\b",
    r"\bcalculat(e|ion|ing)\b",
    r"\bcomput(e|ation|ing)\b",
    r"\bwork(ed|ing)? out (the|my|what)\b",
    r"\btell me (the|my|what) (exact |total |final )?(amount|figure|sum|total)\b",
    r"\bhow many dollars\b",
    r"\bwhat will my tax be\b",
    r"\bwhat do i owe\b",
    r"\bhow much (do|will) i\b",
    r"\btotal (amount|payable|due|relief)\b",
    r"\bexact (amount|figure|sum)\b",
    r"\bbreak ?down of (the|my)\b",
)

#: A currency figure the writer is asking to have applied to their own facts.
#:
#: Narrower than "a dollar sign somewhere in a question". *"The relief is $4,000
#: per child, is that right?"* quotes a published figure and asks for
#: confirmation -- answerable. *"I earn $80,000, what would I pay?"* asks for
#: arithmetic. The discriminator is a first-person marker near the figure, not the
#: figure itself, because a false positive escalates an email the agent could have
#: answered and coverage is the thing being traded away.
_CURRENCY_QUESTION: Final[re.Pattern[str]] = re.compile(
    r"(\$\s?[\d,]+(\.\d{2})?|\b\d[\d,]*\s?dollars\b)"
    r"[^.?!]*\b(i|my|me|we|our)\b[^.?!]*\?"
    r"|\b(i|my|me|we|our)\b[^.?!]*"
    r"(\$\s?[\d,]+(\.\d{2})?|\b\d[\d,]*\s?dollars\b)[^.?!]*\?",
    re.I,
)

#: Possessive framing that marks an enquiry about the writer's own record.
#:
#: THE PRIMARY DETECTOR, not a backstop any more. It was written as one, while
#: ``account_specific`` was still a class and the classifier carried the decision.
#: That class was removed -- being account-specific is a property an enquiry has,
#: not a topic it is about, and the two read identically -- so
#: ``requires_account_lookup`` is now reachable ONLY through this flag, at router
#: reason 5, before any confidence is consulted. Nothing else catches these.
#:
#: A miss means auto-drafting about a real taxpayer's account, so the patterns are
#: deliberately tuned towards recall: over-escalating costs coverage and is
#: recoverable, under-escalating is the citizen-facing failure (``BUILD.md`` S9.6).
#:
#: The vocabulary below is measured, not guessed. On the test split the original
#: list caught 7 of 64 positives; the misses were dominated by three phrasings it
#: had no entry for -- "my tax status" (34 occurrences), "my new/current/mailing
#: address" (28) and "my records" (18) -- because the list was assembled around
#: billing nouns when the class still existed to catch everything else.
_ACCOUNT_PATTERNS: Final[tuple[str, ...]] = (
    # Possessive + a noun naming something only this taxpayer's record holds.
    r"\bmy (noa|notice of assessment|tax bill|bill|refund|giro|deduction|assessment"
    r"|account|case|claim|relief|payment|return|instalment|installment"
    r"|tax status|status|residency status|resident status|tax residency"
    r"|records?|tax records?|correspondence|tax correspondence"
    r"|address|new address|current address|mailing address|contact details"
    r"|submission|filing|objection|appeal|arrangement|plan)\b",
    # The same thing asked the other way round.
    r"\b(status|confirmation|copy|record|details|breakdown) of my\b",
    r"\b(confirm|verify|check|update|change|correct) (my|the) "
    r"(tax )?(status|address|records?|details|particulars|assessment|account)\b",
    # Something the authority did TO this writer specifically.
    r"\bwhy (was|were|did|has|have|is|are) my\b",
    r"\b(applied|assigned|given|charged|granted|allowed|rejected) to (me|my)\b",
    r"\bthat was applied to\b",
    r"\bi (was|am) (charged|billed|assessed|classified|treated|placed|put)\b",
    # Waiting on an outcome that only a lookup can report.
    r"\bwhen will i (receive|get|be)\b",
    r"\bi (still )?(have not|haven't|did not|didn't|never) (receive|received|get|got)\b",
    r"\bhas my .{0,30} been (received|processed|approved|allowed|updated|recorded)\b",
    r"\bwhether (my|i) .{0,40}(been|was|am) (received|processed|placed|put|on)\b",
    # Reading a figure off this taxpayer's own document.
    r"\bcheck (on )?my\b",
    r"\bmy (payment|refund|return|form|appeal|objection|application) (was|has|is|did)\b",
    r"\bon my (bill|statement|account|record|notice)\b",
)

#: Foreign-income and treaty vocabulary -- a MISFILE guard, not a topic detector.
#:
#: `foreign_income_dta` is a held-out class: no indexed SOP serves it, so when the
#: classifier gets it right the empty lookup already escalates it. This flag exists
#: for when the classifier gets it WRONG, and the direction of that error is the
#: problem. SOP-RES-001 (residency, auto-answerable) declares `foreign_income_dta`
#: in `escalate_if` precisely because the two share vocabulary -- both are about
#: living or working across a border -- and a residency email that is really a
#: foreign-income question would otherwise be auto-answered from the residency SOP.
#:
#: The discriminator is WHERE THE INCOME AROSE, not where the person lives.
#: Residency asks about days present in Singapore; this asks about money earned
#: elsewhere. So the patterns anchor on income, employment or treaty terms tied to
#: an overseas source, and deliberately do not match "I moved to Singapore".
_FOREIGN_INCOME_PATTERNS: Final[tuple[str, ...]] = (
    r"\bforeign(-|\s)?(source|sourced)?\s?income\b",
    r"\boverseas (income|work|earnings|employment|assignment)\b",
    r"\bincome (earned|derived|received|from) .{0,20}(overseas|abroad|outside singapore)\b",
    r"\bdouble tax(ation)? agreement\b",
    r"\bdta\b",
    r"\btax treaty\b",
    r"\bdual taxation\b",
    r"\bdouble(-|\s)?tax(ed|ation)\b",
    r"\btaxed (twice|in both|on the same income)\b",
    r"\bwork(ing|ed)? (overseas|abroad|outside singapore)\b",
    r"\bearn(ed|ings|ing)? .{0,25}(overseas|abroad)\b",
    r"\bforeign (tax|employer|salary|dividend|pension|rental|company|shares?|bank)\b",
    r"\bremit(ted|tance|ting)\b",
    r"\b(savings|money|funds|salary|income) .{0,30}(from|earned) (abroad|overseas)\b",
    r"\btransferr?(ed)? .{0,40}(from )?(abroad|overseas)\b",
    r"\bjob abroad\b",
    r"\bperform(ed|ing)? .{0,25}(overseas|abroad)\b",
    r"\btaxed .{0,25}\bin (both|another) countr(y|ies)\b",
)

#: Suspected impersonation or phishing -- the other misfile guard.
#:
#: `scam_report` IS an indexed class routing to `high_consequence`, so a correctly
#: classified scam report already escalates. This flag catches the misfile, and
#: SOP-RTE-002 declares it for exactly that reason: a redirect SOP that sends a
#: scam report off to "another agency" is a visible citizen-facing failure, and an
#: automated redirect is the one out-of-scope action taken without a human.
#:
#: Active fraud is the highest-consequence thing in the corpus and the asymmetry is
#: extreme -- a false positive escalates one answerable email, a false negative
#: redirects a fraud victim elsewhere -- so this list is allowed to be broad. On the
#: committed corpus it costs nothing to be: precision is 1.000.
_SCAM_PATTERNS: Final[tuple[str, ...]] = (
    r"\bscam\b",
    r"\bphish(ing|ed)?\b",
    r"\bfraud(ulent|ster)?\b",
    r"\bimpersonat(e|ing|ion)\b",
    r"\bsuspicious\b",
    r"\bis this (email|message|sms|letter|call|notice) (legitimate|genuine|real|from|actually)\b",
    r"\blegitimate\?",
    r"\bverify (the )?(authenticity|legitimacy)\b",
    r"\bpretend(ing)? to be\b",
    r"\bfake\b",
    r"\bclaim(s|ing) to be from\b",
    r"\bconfirm my bank details\b",
    r"\bunsolicited\b",
    r"\bnot sure if (it|this) (is|was) (real|genuine|legitimate)\b",
    r"\blook(s|ed) (a bit )?(odd|off|strange|suspicious)\b",
)

_COMPUTATION_RE: Final[tuple[re.Pattern[str], ...]] = tuple(
    re.compile(p, re.I) for p in _COMPUTATION_PATTERNS
)
_ACCOUNT_RE: Final[tuple[re.Pattern[str], ...]] = tuple(
    re.compile(p, re.I) for p in _ACCOUNT_PATTERNS
)
_FOREIGN_INCOME_RE: Final[tuple[re.Pattern[str], ...]] = tuple(
    re.compile(p, re.I) for p in _FOREIGN_INCOME_PATTERNS
)
_SCAM_RE: Final[tuple[re.Pattern[str], ...]] = tuple(
    re.compile(p, re.I) for p in _SCAM_PATTERNS
)


def detect_computation_requested(text: str) -> bool:
    """Whether the email asks to be told an amount."""
    return any(p.search(text) for p in _COMPUTATION_RE) or bool(_CURRENCY_QUESTION.search(text))


def detect_account_specific(text: str) -> bool:
    """Whether the email concerns the writer's own record."""
    return any(p.search(text) for p in _ACCOUNT_RE)


def detect_foreign_income(text: str) -> bool:
    """Whether the email is really about income arising outside Singapore."""
    return any(p.search(text) for p in _FOREIGN_INCOME_RE)


def detect_scam_report(text: str) -> bool:
    """Whether the email reports a suspected impersonation or phishing attempt."""
    return any(p.search(text) for p in _SCAM_RE)


def detect_flags(text: str, classification: Classification | None = None) -> frozenset[Flag]:
    """Detect every orthogonal flag present.

    Args:
        text: The scrubbed email. Scrubbed rather than raw, so detection sees
            exactly what the classifier and any external call saw -- a flag that
            fired on a value the model never saw would be untraceable.
        classification: The distribution, for ``multi_intent``. Optional, since the
            lexical flags do not need it.
    """
    flags: set[Flag] = set()

    if detect_computation_requested(text):
        flags.add(Flag.COMPUTATION_REQUESTED)
    if detect_account_specific(text):
        flags.add(Flag.ACCOUNT_SPECIFIC_SIGNAL)
    if detect_foreign_income(text):
        flags.add(Flag.FOREIGN_INCOME_SIGNAL)
    if detect_scam_report(text):
        flags.add(Flag.SCAM_SIGNAL)

    if classification is not None:
        runner_up = classification.runner_up
        if runner_up is not None and runner_up[1] >= MULTI_INTENT_THRESHOLD:
            flags.add(Flag.MULTI_INTENT)

    return frozenset(flags)
