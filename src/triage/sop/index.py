"""Build the routing maps from the loaded corpus.

RUNTIME. No search anywhere in this module.

"Retrieval" in this system is a dictionary lookup that hands the drafter between
one and four short markdown files. The SOPs declare ``intents:`` in frontmatter,
so the class -> SOP mapping is explicit and complete by construction; searching
for something already hand-indexed would solve a problem that does not exist, and
would add a failure mode immediately upstream of the escalation decision
(``sop_design.md`` S6).

Two maps are built here, both derived from frontmatter rather than written in
code:

``CLASS_TO_SOPS``
    From ``intents:`` on each INDEXED SOP. Held-out SOPs are excluded, which is
    what makes a holdout a matter of omitting a file rather than an arbitrary cut.

``BUCKET``
    From ``auto_reply_permitted``. Escalation policy is therefore corpus-derived:
    an agency conforming real SOPs to this schema changes routing behaviour with
    no code change (``sop_design.md`` S4, S12).

``no_supporting_sop`` is **derived, not hand-mapped** — the router asks whether
``sops_for()`` came back empty rather than reading a bucket entry. One source of
truth, and holding out a further SOP later needs no code change (``BUILD.md``
S5.6).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import cached_property
from typing import Final

from triage.sop.loader import SOP, CorpusError, load_corpus

#: The five routing buckets (``sop_design.md`` S3).
AUTO_ANSWERABLE: Final[str] = "auto_answerable"
REQUIRES_ACCOUNT_LOOKUP: Final[str] = "requires_account_lookup"
HIGH_CONSEQUENCE: Final[str] = "high_consequence"
OUT_OF_SCOPE: Final[str] = "out_of_scope"
NO_SUPPORTING_SOP: Final[str] = "no_supporting_sop"

BUCKETS: Final[tuple[str, ...]] = (
    AUTO_ANSWERABLE, REQUIRES_ACCOUNT_LOOKUP, HIGH_CONSEQUENCE,
    OUT_OF_SCOPE, NO_SUPPORTING_SOP,
)

#: Which always-escalate bucket a non-auto-answerable class belongs to.
#:
#: `auto_reply_permitted: false` says a class must not auto-reply; it does not say
#: why, and the reason is what the officer queue and the citizen-facing reason chip
#: need. The distinction is a policy judgement about consequence rather than a
#: property of any single document, so it is declared here as data.
#:
#: `out_of_scope` is deliberately absent: those classes DO auto-reply, with a
#: redirect, and that redirect counts toward coverage (``BUILD.md`` S5.6).
ESCALATION_BUCKETS: Final[Mapping[str, str]] = {
    "account_specific": REQUIRES_ACCOUNT_LOOKUP,
    "hardship_or_waiver": HIGH_CONSEQUENCE,
    "scam_report": HIGH_CONSEQUENCE,
}

#: Classes that auto-reply with a redirect rather than a substantive answer.
OUT_OF_SCOPE_CLASSES: Final[frozenset[str]] = frozenset({
    "oos_business_tax", "oos_other_agency",
})


@dataclass(frozen=True)
class SOPIndex:
    """The routing maps, derived from a loaded corpus."""

    sops: tuple[SOP, ...]

    @cached_property
    def by_id(self) -> Mapping[str, SOP]:
        return {sop.sop_id: sop for sop in self.sops}

    @cached_property
    def indexed(self) -> tuple[SOP, ...]:
        """SOPs available to the runtime. Held-out SOPs are authored but excluded."""
        return tuple(sop for sop in self.sops if sop.indexed)

    @cached_property
    def held_out(self) -> tuple[SOP, ...]:
        return tuple(sop for sop in self.sops if not sop.indexed)

    @cached_property
    def class_to_sops(self) -> Mapping[str, tuple[str, ...]]:
        """``CLASS_TO_SOPS``: class -> the indexed SOP ids serving it."""
        mapping: dict[str, list[str]] = {}
        for sop in self.indexed:
            for intent in sop.intents:
                mapping.setdefault(intent, []).append(sop.sop_id)
        return {cls: tuple(ids) for cls, ids in mapping.items()}

    @cached_property
    def bucket(self) -> Mapping[str, str]:
        """``BUCKET``: class -> routing bucket, derived from frontmatter."""
        mapping: dict[str, str] = {}
        for sop in self.indexed:
            for intent in sop.intents:
                mapping[intent] = self._bucket_for(intent, sop)
        return mapping

    @staticmethod
    def _bucket_for(intent: str, sop: SOP) -> str:
        if not sop.auto_reply_permitted:
            return ESCALATION_BUCKETS.get(intent, HIGH_CONSEQUENCE)
        return OUT_OF_SCOPE if intent in OUT_OF_SCOPE_CLASSES else AUTO_ANSWERABLE

    def sops_for(self, cls: str) -> tuple[SOP, ...]:
        """Return the SOPs serving ``cls``. Empty means the class is unanswerable."""
        return tuple(self.by_id[sid] for sid in self.class_to_sops.get(cls, ()))

    def bucket_for(self, cls: str) -> str:
        """Return the routing bucket for ``cls``.

        A class with no indexed SOP yields ``no_supporting_sop`` by derivation:
        the emptiness of the lookup *is* the signal, so no hand-written entry can
        drift out of step with the corpus.
        """
        return self.bucket.get(cls, NO_SUPPORTING_SOP)

    def unanswerable(self, classes: Iterable[str]) -> tuple[str, ...]:
        """Return those ``classes`` that no indexed SOP serves."""
        return tuple(cls for cls in classes if not self.class_to_sops.get(cls))


def build_index(sops: Iterable[SOP] | None = None) -> SOPIndex:
    """Build the index, loading the corpus from disk when none is supplied."""
    return SOPIndex(sops=tuple(sops) if sops is not None else load_corpus())


__all__ = [
    "AUTO_ANSWERABLE", "BUCKETS", "HIGH_CONSEQUENCE", "NO_SUPPORTING_SOP",
    "OUT_OF_SCOPE", "REQUIRES_ACCOUNT_LOOKUP", "CorpusError", "SOPIndex",
    "build_index",
]
