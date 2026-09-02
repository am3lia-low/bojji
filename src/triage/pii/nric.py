"""NRIC/FIN checksum validation.

Singapore NRIC and FIN identifiers carry a check letter derived from the seven
digits. Validating it lets the scrubber distinguish a real-shaped identifier
from any other ``letter + 7 digits + letter`` token, which keeps the false
positive rate down on strings such as order references.

The algorithm is public and widely documented; no internal source is used.
"""

from __future__ import annotations

import re
from typing import Final

#: Structural shape of an NRIC/FIN: prefix, seven digits, check letter.
NRIC_RE: Final[re.Pattern[str]] = re.compile(r"\b([STFGM])(\d{7})([A-Z])\b")

#: Positional weights applied to the seven digits before summing.
_WEIGHTS: Final[tuple[int, ...]] = (2, 7, 6, 5, 4, 3, 2)

#: Check letters indexed by ``11 - (weighted_sum % 11)``, per prefix family.
#: S/T are citizens and PRs; F/G are foreign identification numbers; M is the
#: series introduced for newer FIN holders.
_CHECKSUM_TABLES: Final[dict[str, str]] = {
    "ST": "JZIHGFEDCBA",
    "FG": "XWUTRQPNMLK",
    "M": "XWUTRQPNJLK",
}

#: Constant added to the weighted sum before the modulus, by prefix. The
#: later series (T, G) are offset by four from their earlier counterparts.
_OFFSETS: Final[dict[str, int]] = {"S": 0, "T": 4, "F": 0, "G": 4, "M": 3}


def _table_for(prefix: str) -> str:
    for family, table in _CHECKSUM_TABLES.items():
        if prefix in family:
            return table
    raise ValueError(f"unsupported NRIC prefix: {prefix!r}")


def expected_check_letter(prefix: str, digits: str) -> str:
    """Return the check letter implied by ``prefix`` and seven ``digits``.

    Args:
        prefix: One of ``S``, ``T``, ``F``, ``G`` or ``M``.
        digits: Exactly seven decimal digits.

    Raises:
        ValueError: If the prefix is unsupported or ``digits`` is malformed.
    """
    prefix = prefix.upper()
    if len(digits) != 7 or not digits.isdigit():
        raise ValueError(f"expected seven digits, got {digits!r}")

    table = _table_for(prefix)
    total = sum(int(d) * w for d, w in zip(digits, _WEIGHTS, strict=True)) + _OFFSETS[prefix]
    return table[total % 11]


def is_valid_nric(candidate: str) -> bool:
    """Return whether ``candidate`` is a structurally valid NRIC/FIN.

    Validity here means the check letter agrees with the digits. It says
    nothing about whether the identifier was ever issued.
    """
    match = NRIC_RE.fullmatch(candidate.strip().upper())
    if match is None:
        return False
    prefix, digits, check = match.groups()
    try:
        return expected_check_letter(prefix, digits) == check
    except ValueError:
        return False
