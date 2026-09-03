"""Tests for PII detection, the placeholder vault and the rehydrate round-trip.

The scrub node gates every external call, so a miss here leaks a citizen's
identifier to a third-party API. These tests are correspondingly strict about
recall on the patterns claimed in the writeup, and explicit about the gaps that
are known and reported rather than fixed.
"""

from __future__ import annotations

import re

import pytest

from triage.pii.nric import expected_check_letter, is_valid_nric
from triage.pii.scrubber import PLACEHOLDER_RE, Scrubber


@pytest.fixture(scope="module")
def scrubber() -> Scrubber:
    return Scrubber()


# --------------------------------------------------------------------------- #
# NRIC checksum
# --------------------------------------------------------------------------- #

# Fabricated identifiers whose check letter is computed, never real ones.
VALID_NRICS = ["S1234567D", "T1234567J", "F1234567N", "G1234567X", "M1234567K"]


@pytest.mark.parametrize("nric", VALID_NRICS)
def test_valid_nrics_accepted(nric: str) -> None:
    assert is_valid_nric(nric)


@pytest.mark.parametrize("nric", VALID_NRICS)
def test_wrong_check_letter_rejected(nric: str) -> None:
    """A single wrong check letter must fail, or the validator is decorative."""
    wrong = "A" if nric[-1] != "A" else "B"
    assert not is_valid_nric(nric[:-1] + wrong)


@pytest.mark.parametrize("prefix", list("STFGM"))
def test_every_prefix_family_has_a_table(prefix: str) -> None:
    letter = expected_check_letter(prefix, "1234567")
    assert letter.isalpha() and len(letter) == 1


def test_lowercase_nric_accepted() -> None:
    """Citizens type identifiers in lower case; the validator normalises."""
    assert is_valid_nric("s1234567d")


@pytest.mark.parametrize("bad", ["S123456D", "S12345678D", "1234567D", "SS123456D", ""])
def test_malformed_shapes_rejected(bad: str) -> None:
    assert not is_valid_nric(bad)


def test_expected_check_letter_rejects_bad_digits() -> None:
    with pytest.raises(ValueError):
        expected_check_letter("S", "12345")


def test_unsupported_prefix_rejected() -> None:
    with pytest.raises(ValueError):
        expected_check_letter("A", "1234567")


# --------------------------------------------------------------------------- #
# Detection recall, per pattern family
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    ("text", "placeholder"),
    [
        ("My NRIC is S1234567D thanks", "NRIC"),
        ("reach me at jane.tan@example.com", "EMAIL"),
        ("call 91234567", "PHONE"),
        ("call 9123 4567", "PHONE"),
        ("call +65 91234567", "PHONE"),
        ("landline 61234567", "PHONE"),
        ("Singapore 520123", "POSTAL"),
        ("I live at Blk 123 #04-56", "ADDRESS"),
        ("unit #12-345 please", "ADDRESS"),
        ("15 Bukit Timah Road", "ADDRESS"),
        ("at Jalan Besar", "ADDRESS"),
        ("I paid $1,234.50", "AMOUNT"),
        ("I paid 2500.00 SGD", "AMOUNT"),
        ("on 12/04/2025", "DATE"),
        ("on 3 Jan 2025", "DATE"),
    ],
)
def test_pattern_family_detected(scrubber: Scrubber, text: str, placeholder: str) -> None:
    result = scrubber.scrub(text)
    assert any(placeholder in token for token in result.placeholders), (
        f"{placeholder} not detected in {text!r}; got {result.text!r}"
    )


def test_invalid_checksum_not_scrubbed(scrubber: Scrubber) -> None:
    """A token of NRIC shape with a bad check letter is not an identifier."""
    result = scrubber.scrub("order reference S1234567A")
    assert result.vault == {}


# --------------------------------------------------------------------------- #
# Round-trip
# --------------------------------------------------------------------------- #

FULL_EMAIL = (
    "Hi, I am S1234567D, contact me at jane.tan@example.com or 9123 4567. "
    "I live at Blk 123 #04-56 Jalan Besar, Singapore 520123. "
    "I paid $1,234.50 on 12/04/2025 for YA 2025."
)


def test_round_trip_is_lossless(scrubber: Scrubber) -> None:
    result = scrubber.scrub(FULL_EMAIL)
    assert scrubber.rehydrate(result.text, result.vault) == FULL_EMAIL


def test_scrubbed_text_leaks_no_original_value(scrubber: Scrubber) -> None:
    """The whole point: no vaulted value may survive into the outgoing text."""
    result = scrubber.scrub(FULL_EMAIL)
    for value in result.vault.values():
        assert value not in result.text


def test_repeated_value_gets_one_placeholder(scrubber: Scrubber) -> None:
    result = scrubber.scrub("S1234567D ... again S1234567D")
    assert result.text.count("[NRIC_1]") == 2
    assert len(result.vault) == 1


def test_distinct_values_get_distinct_placeholders(scrubber: Scrubber) -> None:
    result = scrubber.scrub("S1234567D and T1234567J")
    assert len(result.vault) == 2
    assert result.text.count("[NRIC_") == 2


def test_clean_text_is_unchanged(scrubber: Scrubber) -> None:
    clean = "How do I file my income tax return this year?"
    result = scrubber.scrub(clean)
    assert result.text == clean
    assert result.vault == {}


def test_counts_reported_per_pattern(scrubber: Scrubber) -> None:
    """Counts feed the scrub-recall metric, so they must be populated."""
    result = scrubber.scrub(FULL_EMAIL)
    assert result.counts["nric"] == 1
    assert sum(result.counts.values()) == len(PLACEHOLDER_RE.findall(result.text))


# --------------------------------------------------------------------------- #
# Precedence and allowlist
# --------------------------------------------------------------------------- #

def test_nric_wins_over_phone(scrubber: Scrubber) -> None:
    """The seven digits inside an NRIC must not be claimed by the phone rule."""
    result = scrubber.scrub("S9123456D")
    assert list(result.vault) == ["[NRIC_1]"]


def test_email_digits_not_split_by_numeric_patterns(scrubber: Scrubber) -> None:
    result = scrubber.scrub("write to tan123456@example.com")
    assert list(result.vault) == ["[EMAIL_1]"]


def test_long_digit_run_is_not_a_postal_code(scrubber: Scrubber) -> None:
    result = scrubber.scrub("case reference 1234567890")
    assert result.vault == {}


@pytest.mark.parametrize(
    "text",
    [
        "100000 dollars",
        "I earned 100000 dollars last year",
        "I paid $100000",
        "SGD 100000",
        "assessed at 123456 dollars",
        "I paid 2500.00 SGD",
    ],
)
def test_six_digit_amount_labelled_money_not_postal(scrubber: Scrubber, text: str) -> None:
    """A six-digit run with a currency marker is an amount, not a postal code.

    Both patterns scrub, so this is not a leak — but ``counts`` feeds the
    per-pattern scrub-recall metric the README reports, and a six-figure income
    counted as a postal code would misstate it.
    """
    result = scrubber.scrub(text)
    assert "money" in result.counts
    assert "postal_code_bare" not in result.counts
    assert "postal_code_sg" not in result.counts


def test_currency_marker_is_inside_the_placeholder(scrubber: Scrubber) -> None:
    """Postal matching first would strand the dollar sign outside the token."""
    result = scrubber.scrub("I paid $100000 last year")
    assert "$" not in result.text
    assert result.vault["[AMOUNT_1]"] == "$100000"


@pytest.mark.parametrize("text", ["Singapore 520123", "postal code 520123", "S(123456)"])
def test_context_anchored_postal_preferred(scrubber: Scrubber, text: str) -> None:
    """A postal marker gives the high-precision pattern, not the bare fallback."""
    result = scrubber.scrub(text)
    assert "postal_code_sg" in result.counts


@pytest.mark.parametrize("text", ["call 100000 times", "my income is 100000", "I owe 250000"])
def test_unmarked_six_digit_run_still_scrubbed(scrubber: Scrubber, text: str) -> None:
    """The known over-scrub, kept deliberately and reported in the writeup.

    An unmarked six-digit run cannot be told from a postal code by pattern
    alone. Over-scrubbing is the correct failure direction for an identifier
    that localises a residence, and the round-trip makes it lossless.
    """
    result = scrubber.scrub(text)
    assert "postal_code_bare" in result.counts
    assert scrubber.rehydrate(result.text, result.vault) == text


def test_five_digit_run_is_not_a_postal_code(scrubber: Scrubber) -> None:
    result = scrubber.scrub("I earn 85000 a year")
    assert result.vault == {}


def test_decimal_fragment_is_not_a_postal_code(scrubber: Scrubber) -> None:
    """Lookarounds must stop the bare pattern biting into a larger figure."""
    result = scrubber.scrub("the rate was 1.234567 per cent")
    assert "postal_code_bare" not in result.counts


@pytest.mark.parametrize("topical", ["YA 2025", "Year of Assessment 2025"])
def test_allowlisted_topical_vocabulary_survives(scrubber: Scrubber, topical: str) -> None:
    """Scrubbing a Year of Assessment would destroy the classifier's signal."""
    result = scrubber.scrub(f"question about {topical} please")
    assert topical in result.text


# --------------------------------------------------------------------------- #
# Rehydration safety
# --------------------------------------------------------------------------- #

def test_unknown_placeholder_survives_rehydration(scrubber: Scrubber) -> None:
    """A model that invents a placeholder must not crash the pipeline."""
    out = scrubber.rehydrate("see [NRIC_9]", {"[NRIC_1]": "S1234567D"})
    assert out == "see [NRIC_9]"


def test_unresolved_flags_invented_placeholders(scrubber: Scrubber) -> None:
    unresolved = scrubber.unresolved("[NRIC_1] and [NRIC_9]", {"[NRIC_1]": "S1234567D"})
    assert unresolved == ["[NRIC_9]"]


def test_unresolved_empty_on_faithful_draft(scrubber: Scrubber) -> None:
    assert scrubber.unresolved("[NRIC_1] only", {"[NRIC_1]": "S1234567D"}) == []


# --------------------------------------------------------------------------- #
# Isolation
# --------------------------------------------------------------------------- #

def test_vaults_do_not_leak_between_calls(scrubber: Scrubber) -> None:
    """One scrubber serves many emails; values must never cross between them."""
    first = scrubber.scrub("S1234567D")
    second = scrubber.scrub("T1234567J")
    assert first.vault["[NRIC_1]"] == "S1234567D"
    assert second.vault["[NRIC_1]"] == "T1234567J"


def test_known_gap_untyped_street_is_not_detected(scrubber: Scrubber) -> None:
    """Documents the residual gap the writeup reports rather than claims fixed.

    A street name carrying no street-type token and no block number is not
    reachable by a gazetteer-anchored pattern. If this test ever fails, the
    coverage claim in the README has improved and should be updated.
    """
    result = scrubber.scrub("I stay at Pasir Panjang near the market")
    assert result.vault == {}


# --------------------------------------------------------------------------- #
# Full-address spans
# --------------------------------------------------------------------------- #

CORPUS_ADDRESSES = (
    "Blk 857 Tampines Street 21 #04-029",
    "Blk 88 Lorong Chuan #23-172",
    "Blk 673 Bukit Batok Ave 3 #09-188",
    "Blk 745 Ang Mo Kio Ave 10 #10-022",
    "Blk 695 Jalan Membina #06-156",
    "Blk 123 Bedok North Ave 1 #05-06",
)


@pytest.mark.parametrize("address", CORPUS_ADDRESSES)
def test_full_address_is_one_placeholder(scrubber: Scrubber, address: str) -> None:
    """Block, street and unit are claimed as a single span.

    Regression test. ``block_unit`` previously matched only "Blk 857" and consumed
    the span, stranding the street name between two placeholders: the leading house
    number ``street_address`` requires had already been taken, so nothing could
    reach "Tampines Street 21". Every planted address in the corpus is this shape,
    so the street name leaked on all of them.
    """
    result = scrubber.scrub(f"I live at {address}.")
    assert result.text == "I live at [ADDRESS_1]."
    assert result.vault == {"[ADDRESS_1]": address}


@pytest.mark.parametrize("address", CORPUS_ADDRESSES)
def test_street_name_does_not_survive_scrubbing(scrubber: Scrubber, address: str) -> None:
    """The locating part of the address must not remain in the scrubbed text.

    Guards the failure that scrub recall could not see: the metric asks whether the
    WHOLE planted value survives verbatim, so a partly-scrubbed address scored as
    detected while the street name was still readable.
    """
    street = address.split(" ", 2)[2].split("#")[0].strip()
    scrubbed = scrubber.scrub(f"My address is {address}, please update it.").text
    assert street.lower() not in scrubbed.lower()


@pytest.mark.parametrize(
    "ordinary",
    [
        "Is there any way to appeal?",
        "I clicked the link in the email.",
        "Please advise on the best way forward.",
        "My block of flats was reassessed.",
    ],
)
def test_ordinary_prose_is_not_scrubbed_as_an_address(
    scrubber: Scrubber, ordinary: str
) -> None:
    """The address pattern is anchored on a block token for exactly this reason.

    A standalone street pattern was prototyped and rejected: the gazetteer's English
    members (WAY, LINK, VIEW, PLACE, ST) are ordinary words, and it fired on 80+
    non-address phrases across the corpus, scrubbing the text the classifier reads.
    """
    assert scrubber.scrub(ordinary).text == ordinary


@pytest.mark.parametrize(
    "public",
    [
        "Can I visit the IRAS office at Revenue House?",
        "I went to the Orchard Road branch.",
        "The office on Robinson Road handles this.",
        "I dropped it off at Tampines Regional Library.",
        "Is your Bedok branch open on Saturday?",
        "The seminar was held at Marina Bay Sands.",
        "I attended the talk at Suntec City.",
    ],
)
def test_public_landmarks_are_not_scrubbed(scrubber: Scrubber, public: str) -> None:
    """A public building or branch is not a residence and must survive.

    Over-scrubbing is not free: these strings are topical content the classifier
    reads, and replacing them with [ADDRESS_n] removes signal without protecting
    anyone. Measured on the generated corpus, ADDRESS placeholders that do not
    correspond to a planted address number zero.
    """
    assert scrubber.scrub(public).text == public


@pytest.mark.parametrize(
    "text",
    [
        "My address is Blk 88 Lorong Chuan #23-172, postcode 648913.",
        "Blk 457 Bukit Batok Ave 3 #10-181, postcode 324993. Could you update it?",
        "Blk 564 Bukit Batok Ave 3 #24-017, postcode: 668507, and my NRIC follows.",
        "Blk 141 Tampines Street 21 #04-147, Singapore 655178?",
        "The post code 590110. Please confirm.",
    ],
)
def test_postcode_scrubbed_regardless_of_trailing_punctuation(
    scrubber: Scrubber, text: str
) -> None:
    """A sentence-ending postcode must scrub the same as a question-ending one.

    Regression test for a silent 0.4375 recall on the postcode type. Two gaps
    combined: the context-anchored pattern did not know the one-word spelling
    "postcode" (which is what the corpus writes), and the bare pattern's
    lookahead ``(?![\d.,])`` rejected any trailing "." or "," -- so the same
    value leaked after a full stop and scrubbed after a question mark.
    """
    assert not re.search(r"(?<!\d)\d{6}(?!\d)", scrubber.scrub(text).text)


@pytest.mark.parametrize(
    "text",
    [
        "I owe $123456.78 this year",
        "a refund of 234567 dollars",
        "the figure 1,234,567 appears on the notice",
    ],
)
def test_digit_run_inside_a_larger_number_is_not_a_postcode(
    scrubber: Scrubber, text: str
) -> None:
    """The relaxed lookahead must still reject fragments of a larger figure.

    ``(?![\d.,]?\d)`` disqualifies a separator FOLLOWED BY A DIGIT, which is what
    "this run continues into a bigger number" actually looks like -- while leaving
    ordinary sentence punctuation alone.
    """
    assert "[POSTAL_1]" not in scrubber.scrub(text).text
