"""Tests for the SOP corpus, the loader, and the routing maps derived from it.

The corpus is the system's integration seam: ``CLASS_TO_SOPS`` and ``BUCKET`` are
built from frontmatter, so escalation policy lives in these files rather than in
code. That makes a corpus regression a *routing* regression -- it would surface as
a wrong decision on a citizen's email, not as an exception -- so the structural
guarantees are asserted here rather than assumed.

The design commitments under test, each from ``sop_design.md``:

* 17 SOPs, 14 indexed and 3 held out (S5)
* two whole-class holdouts yielding ``no_supporting_sop`` by DERIVATION, and one
  single-SOP holdout inside an indexed class yielding a partial answer (S5)
* the $80,000 relief cap does not leak into any indexed SOP (S5, S11)
* every SOP carries the synthetic banner and at least one public reference (S8.2)
* section 4 phrasing parses, because it is the template floor the runtime emits
  in ``local`` mode (``BUILD.md`` S5.8)
"""

from __future__ import annotations

import sys

import pytest

from triage.sop.index import (
    AUTO_ANSWERABLE,
    BUCKETS,
    HIGH_CONSEQUENCE,
    NO_SUPPORTING_SOP,
    OUT_OF_SCOPE,
    REQUIRES_ACCOUNT_LOOKUP,
    SOPIndex,
    build_index,
)
from triage.sop.loader import SOP, CorpusError, load_corpus

#: The 10 classes (``sop_design.md`` S2).
#:
#: Was 12. ``account_specific`` stopped being a class: it is a property an enquiry
#: has rather than a topic it is about, carried by the flag and escalated at router
#: reason 5. ``oos_business_tax`` and ``oos_other_agency`` merged into
#: ``oos_redirect``: same bucket, same action, and the classifier could not separate
#: them (0.000 on the held-out split).
ALL_CLASSES = [
    "filing", "tax_reliefs", "assessment_and_amendment", "payment", "residency",
    "hardship_or_waiver", "scam_report", "oos_redirect",
    "rental_income", "foreign_income_dta",
]

#: Classes whose SOPs are deliberately absent from the index (``sop_design.md`` S5).
HELD_OUT_CLASSES = ["rental_income", "foreign_income_dta"]

#: The expected bucket for every class. Written out rather than derived, so that a
#: change to the derivation logic fails here instead of silently agreeing with itself.
EXPECTED_BUCKETS = {
    "filing": AUTO_ANSWERABLE,
    "tax_reliefs": AUTO_ANSWERABLE,
    "assessment_and_amendment": AUTO_ANSWERABLE,
    "payment": AUTO_ANSWERABLE,
    "residency": AUTO_ANSWERABLE,
    "hardship_or_waiver": HIGH_CONSEQUENCE,
    "scam_report": HIGH_CONSEQUENCE,
    "oos_redirect": OUT_OF_SCOPE,
    "rental_income": NO_SUPPORTING_SOP,
    "foreign_income_dta": NO_SUPPORTING_SOP,
}


@pytest.fixture(scope="module")
def index() -> SOPIndex:
    return build_index()


@pytest.fixture(scope="module")
def sops(index: SOPIndex) -> tuple[SOP, ...]:
    return index.sops


# --------------------------------------------------------------------------- #
# Corpus shape
# --------------------------------------------------------------------------- #

def test_corpus_loads(sops: tuple[SOP, ...]) -> None:
    assert len(sops) == 17


def test_indexed_and_held_out_counts(index: SOPIndex) -> None:
    assert len(index.indexed) == 14
    assert len(index.held_out) == 3


def test_held_out_sops_are_the_expected_three(index: SOPIndex) -> None:
    """REL-005 is the partial-answer holdout; INC-001/002 are whole-class."""
    assert {s.sop_id for s in index.held_out} == {
        "SOP-REL-005", "SOP-INC-001", "SOP-INC-002",
    }


def test_sop_ids_are_unique(sops: tuple[SOP, ...]) -> None:
    ids = [s.sop_id for s in sops]
    assert len(ids) == len(set(ids))


# --------------------------------------------------------------------------- #
# Provenance and the misrepresentation guard
# --------------------------------------------------------------------------- #

def test_every_sop_carries_the_synthetic_banner(sops: tuple[SOP, ...]) -> None:
    """A synthetic SOP that reads as a real IRAS document is its own problem."""
    for sop in sops:
        assert "SYNTHETIC DOCUMENT" in sop.body, sop.sop_id


def test_every_sop_cites_a_public_source(sops: tuple[SOP, ...]) -> None:
    """Every factual claim must trace to a public URL (``sop_design.md`` S8.2)."""
    for sop in sops:
        assert sop.references, sop.sop_id
        assert all(url.startswith("https://www.iras.gov.sg/") for url in sop.references), sop.sop_id


def test_every_fact_carries_a_source_annotation(sops: tuple[SOP, ...]) -> None:
    for sop in sops:
        section = sop.body.split("## 2. Key facts")[1].split("## 3.")[0]
        assert section.count("<sup>Source:") == len(sop.facts), sop.sop_id


def test_invented_metadata_is_not_presented_as_real(sops: tuple[SOP, ...]) -> None:
    """Queue names and handling targets are invented; none may look like an SLA."""
    for sop in sops:
        if sop.owner_queue is not None:
            assert sop.owner_queue.startswith("IIT-"), sop.sop_id


# --------------------------------------------------------------------------- #
# CLASS_TO_SOPS
# --------------------------------------------------------------------------- #

def test_every_indexed_class_resolves(index: SOPIndex) -> None:
    for cls in ALL_CLASSES:
        if cls not in HELD_OUT_CLASSES:
            assert index.sops_for(cls), cls


def test_tax_reliefs_pulls_a_group(index: SOPIndex) -> None:
    """Four SOPs, so within-group selection is a real decision (``sop_design.md`` S6)."""
    assert [s.sop_id for s in index.sops_for("tax_reliefs")] == [
        "SOP-REL-001", "SOP-REL-002", "SOP-REL-003", "SOP-REL-004",
    ]


def test_payment_pulls_a_group(index: SOPIndex) -> None:
    assert [s.sop_id for s in index.sops_for("payment")] == ["SOP-PAY-001", "SOP-PAY-002"]


def test_index_covers_exactly_the_indexed_classes(index: SOPIndex) -> None:
    assert set(index.class_to_sops) == set(ALL_CLASSES) - set(HELD_OUT_CLASSES)


def test_no_class_routes_to_requires_account_lookup(index: SOPIndex) -> None:
    """The bucket is reachable through the FLAG only, never through a class.

    ``account_specific`` was a class and is not any more. The distinction it asked
    the classifier to draw was not in the text -- "how do instalments work" and
    "what is happening with my instalment" differ by one possessive -- so it was
    unlearnable by construction, and it pulled 63 test emails away from five other
    classes. The condition is now carried by the ``account_specific`` flag, which
    the router escalates at reason 5, before any confidence is consulted.

    If a future frontmatter change gives some class this bucket, that is a design
    regression rather than a detail, and it fails here.
    """
    assert all(bucket != REQUIRES_ACCOUNT_LOOKUP for bucket in index.bucket.values())


def test_the_account_specific_sop_is_still_reachable(index: SOPIndex) -> None:
    """Declaring no intent must not make SOP-ESC-001 fall out of the corpus.

    It is what the officer receives when the flag fires, so it has to load and stay
    indexed even though nothing retrieves it by class.
    """
    sop = index.by_id["SOP-ESC-001"]

    assert sop.intents == ()
    assert sop.indexed
    assert not sop.auto_reply_permitted


# --------------------------------------------------------------------------- #
# Buckets, and the derivation of no_supporting_sop
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("cls", ALL_CLASSES)
def test_bucket_for_each_class(index: SOPIndex, cls: str) -> None:
    assert index.bucket_for(cls) == EXPECTED_BUCKETS[cls]


def test_all_buckets_are_known(index: SOPIndex) -> None:
    for cls in ALL_CLASSES:
        assert index.bucket_for(cls) in BUCKETS


@pytest.mark.parametrize("cls", HELD_OUT_CLASSES)
def test_held_out_class_yields_no_supporting_sop(index: SOPIndex, cls: str) -> None:
    """The bucket is DERIVED from an empty lookup, never hand-mapped.

    Asserted together: an empty SOP list and the bucket must move as one, so a
    future hand-written entry cannot drift out of step with the corpus.
    """
    assert index.sops_for(cls) == ()
    assert cls not in index.class_to_sops
    assert index.bucket_for(cls) == NO_SUPPORTING_SOP


def test_unknown_class_is_treated_as_unanswerable(index: SOPIndex) -> None:
    """Fail safe: an unrecognised label escalates rather than auto-replying."""
    assert index.bucket_for("no_such_class") == NO_SUPPORTING_SOP


def test_unanswerable_reports_exactly_the_held_out_classes(index: SOPIndex) -> None:
    assert set(index.unanswerable(ALL_CLASSES)) == set(HELD_OUT_CLASSES)


def test_escalating_classes_do_not_permit_auto_reply(index: SOPIndex) -> None:
    """The bucket must follow the frontmatter, not the other way round."""
    for cls in ("hardship_or_waiver", "scam_report"):
        for sop in index.sops_for(cls):
            assert not sop.auto_reply_permitted, sop.sop_id


def test_out_of_scope_classes_do_auto_reply(index: SOPIndex) -> None:
    """A redirect is an automated action and counts toward coverage (S5.6)."""
    for cls in ("oos_redirect",):
        for sop in index.sops_for(cls):
            assert sop.auto_reply_permitted, sop.sop_id


# --------------------------------------------------------------------------- #
# The relief-cap holdout
# --------------------------------------------------------------------------- #

def test_relief_cap_does_not_leak_into_indexed_sops(index: SOPIndex) -> None:
    """The $80,000 cap is a property of the SUM of all reliefs, so it cannot be
    derived from any single relief's rules. If an indexed SOP stated it, the agent
    could answer the cap question from the index and the partial-answer holdout
    would collapse into an ordinary answerable case.
    """
    for sop in index.indexed:
        assert "80,000" not in sop.body, f"{sop.sop_id} leaks the relief cap"


def test_the_held_out_relief_sop_does_state_the_cap(index: SOPIndex) -> None:
    """The counterpart: re-indexing REL-005 must actually restore the capability."""
    assert "80,000" in index.by_id["SOP-REL-005"].body


def test_relief_cap_holdout_leaves_its_class_answerable(index: SOPIndex) -> None:
    """REL-005 differs in kind from INC-001/002: `tax_reliefs` still resolves, so
    the router does NOT fire `no_supporting_sop` and the agent must give a partial
    answer plus escalation rather than a confident total.
    """
    assert index.sops_for("tax_reliefs")
    assert index.bucket_for("tax_reliefs") == AUTO_ANSWERABLE


def test_indexed_relief_sops_forbid_stating_the_cap(index: SOPIndex) -> None:
    for sop in index.sops_for("tax_reliefs"):
        assert "relief cap" in sop.body.split("## 5. Do not")[1].lower(), sop.sop_id


# --------------------------------------------------------------------------- #
# The template floor
# --------------------------------------------------------------------------- #

def test_every_auto_replying_sop_has_approved_phrasing(index: SOPIndex) -> None:
    """In ``local`` mode the reply IS this text, so an empty block means no reply."""
    for sop in index.indexed:
        assert sop.approved_phrasing, sop.sop_id


def test_phrasing_blocks_are_non_empty(sops: tuple[SOP, ...]) -> None:
    for sop in sops:
        for block_id, text in sop.approved_phrasing.items():
            assert text.strip(), f"{sop.sop_id}:{block_id}"


def test_phrasing_parses_for_a_known_block(index: SOPIndex) -> None:
    text = index.by_id["SOP-PAY-001"].approved_phrasing["giro_dates"]
    assert "6th of each month" in text
    assert "\n" not in text


def test_escalation_only_sops_still_acknowledge(index: SOPIndex) -> None:
    """An always-escalate class still needs a citizen-facing acknowledgement."""
    for sop_id in ("SOP-ESC-001", "SOP-ESC-002", "SOP-ESC-003"):
        assert "acknowledgement" in index.by_id[sop_id].approved_phrasing


# --------------------------------------------------------------------------- #
# Deliberate complexity (``sop_design.md`` S10)
# --------------------------------------------------------------------------- #

def test_supersession_is_present_and_versioned(index: SOPIndex) -> None:
    """REL-004 v2.0 supersedes v1.0: the real 1 Jan 2024 WMCR basis change."""
    sop = index.by_id["SOP-REL-004"]
    assert sop.version == "2.0"
    assert sop.supersedes == "SOP-REL-004-v1.0"
    assert isinstance(sop.version, str), "version must not round-trip as a float"


def test_both_wmcr_bases_are_stated(index: SOPIndex) -> None:
    """Both are live simultaneously, selected by the child's date of birth."""
    body = index.by_id["SOP-REL-004"].body
    assert "on or after 1 January 2024" in body
    assert "before 1 January 2024" in body


def test_a_dangling_reference_exists(index: SOPIndex) -> None:
    """One SOP cites an annexe that does not exist (``sop_design.md`` S10.4).

    Correct behaviour is to escalate rather than invent the missing content, so
    the dangling reference is deliberate and must survive regeneration.
    """
    known = {s.sop_id for s in index.sops}
    dangling = {
        sop.sop_id: [
            ref for ref in _related_ids(sop.body)
            if ref.startswith(("SOP-", "ANNEX-")) and ref not in known
        ]
        for sop in index.sops
    }
    assert any(dangling.values()), "the deliberate dangling reference has vanished"


def test_cross_document_dependency_on_a_held_out_sop(index: SOPIndex) -> None:
    """A child-relief question needs REL-001 + REL-004 + the held-out REL-005."""
    assert "SOP-REL-005" in index.by_id["SOP-REL-001"].body


def _related_ids(body: str) -> list[str]:
    section = body.split("## 6. Related")[-1]
    return [
        line.lstrip("- ").split()[0]
        for line in section.splitlines()
        if line.startswith("- ")
    ]


# --------------------------------------------------------------------------- #
# Escalation vocabulary
# --------------------------------------------------------------------------- #

def test_frontmatter_trigger_is_aliased_to_the_runtime_flag(index: SOPIndex) -> None:
    """``amount_computation_requested`` (corpus) is ``computation_requested``
    (runtime). The two vocabularies are a known trap; the loader normalises them.
    """
    sop = index.by_id["SOP-PAY-001"]
    assert "amount_computation_requested" in sop.escalate_if
    assert "computation_requested" in sop.escalation_triggers
    assert "amount_computation_requested" not in sop.escalation_triggers


def test_every_relief_sop_escalates_computation(index: SOPIndex) -> None:
    """The rule the corpus exists to enforce: never compute an amount (S11)."""
    for sop in index.sops_for("tax_reliefs"):
        assert "computation_requested" in sop.escalation_triggers, sop.sop_id


# --------------------------------------------------------------------------- #
# Loader failure modes
# --------------------------------------------------------------------------- #

def test_missing_corpus_directory_raises(tmp_path) -> None:
    with pytest.raises(CorpusError, match="not found"):
        load_corpus(tmp_path / "absent")


def test_empty_corpus_directory_raises(tmp_path) -> None:
    with pytest.raises(CorpusError, match="no SOPs"):
        load_corpus(tmp_path)


def test_missing_frontmatter_raises(tmp_path) -> None:
    (tmp_path / "SOP-BAD-001.md").write_text("# no frontmatter here", encoding="utf-8")
    with pytest.raises(CorpusError, match="frontmatter"):
        load_corpus(tmp_path)


def test_unflagged_synthetic_document_is_rejected(tmp_path) -> None:
    """The misrepresentation guard is structural: an un-flagged file must not load."""
    (tmp_path / "SOP-BAD-002.md").write_text(
        "---\nsynthetic: false\nsop_id: SOP-BAD-002\ntitle: t\nversion: \"1.0\"\n"
        "intents: [filing]\nindexed: true\nauto_reply_permitted: true\n"
        "escalate_if: []\nreferences:\n  - https://www.iras.gov.sg/x\n---\n\nbody\n",
        encoding="utf-8",
    )
    with pytest.raises(CorpusError, match="synthetic"):
        load_corpus(tmp_path)


def test_sop_without_references_is_rejected(tmp_path) -> None:
    """No claim without a public source: the traceability guarantee, enforced."""
    (tmp_path / "SOP-BAD-003.md").write_text(
        "---\nsynthetic: true\nsop_id: SOP-BAD-003\ntitle: t\nversion: \"1.0\"\n"
        "intents: [filing]\nindexed: true\nauto_reply_permitted: true\n"
        "escalate_if: []\nreferences: []\n---\n\nbody\n",
        encoding="utf-8",
    )
    with pytest.raises(CorpusError, match="references"):
        load_corpus(tmp_path)


# --------------------------------------------------------------------------- #
# config/taxonomy.yaml is a projection, and must not drift
# --------------------------------------------------------------------------- #

def test_taxonomy_yaml_matches_the_corpus() -> None:
    """``config/taxonomy.yaml`` is derived from the corpus, so it can go stale.

    The runtime never reads it -- it derives the maps from frontmatter -- but the
    training and evaluation label list does. A stale file would silently train a
    classifier on a taxonomy the router no longer implements, so staleness is
    a test failure rather than a warning.
    """
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "scripts/derive_taxonomy.py", "--check"],
        cwd=root, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_taxonomy_labels_match_the_classes() -> None:
    from pathlib import Path

    import yaml as _yaml

    path = Path(__file__).resolve().parents[1] / "config" / "taxonomy.yaml"
    doc = _yaml.safe_load(path.read_text(encoding="utf-8"))
    assert doc["labels"] == sorted(ALL_CLASSES)
