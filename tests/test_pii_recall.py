"""Tests for the scrub-recall metric's own output hygiene.

The module that measures PII containment writes to ``eval/results/scrub_recall.json``,
which is committed to git by design. It must therefore be the last module in the
repository that would ever write an identifier to disk.
"""

from __future__ import annotations

import json

import pytest
from eval.metrics.pii_recall import mask, scrub_report


@pytest.mark.parametrize(
    "value,expected",
    [
        ("S0433218J", "S0*****8J"),
        ("91234567", "91****67"),
        ("648913", "64**13"),
        ("abcd", "****"),
        ("ab", "**"),
        ("", ""),
    ],
)
def test_mask_keeps_the_shape_and_drops_the_value(value: str, expected: str) -> None:
    """The diagnostic question is which SHAPE escaped, not which person.

    Prefix, length and final character survive -- enough to tell an NRIC from a
    phone number and to spot a pattern that is off by one character -- while the
    identifier itself does not.
    """
    assert mask(value) == expected


def test_mask_never_returns_the_input_for_a_realistic_identifier() -> None:
    """A short value is fully starred rather than partly revealed."""
    for value in ("S0433218J", "91234567", "648913", "ab", "abcd"):
        assert mask(value) != value


def test_a_real_leak_is_recorded_as_a_shape_not_a_value() -> None:
    """The failing case the mask exists for.

    ``missed_shapes`` is empty today only because recall is 1.0. This forces a miss
    and asserts that what lands in the serialised report is masked -- the check that
    matters, since serialisation is what reaches the committed file.
    """
    report = scrub_report(
        [("e1", {"nric": "S0433218J", "phone": "91234567"},
          "my nric is S0433218J and [PHONE_1]")]
    )

    serialised = json.dumps(report.as_dict())

    assert "S0433218J" not in serialised
    assert "S0*****8J" in serialised
    assert report.recall == pytest.approx(0.5)


def test_clean_scrub_reports_full_recall_and_no_shapes() -> None:
    report = scrub_report(
        [("e1", {"nric": "S0433218J"}, "my nric is [NRIC_1]")]
    )

    assert report.recall == pytest.approx(1.0)
    assert all(not t.missed_shapes for t in report.by_type)
