"""Fetch public IRAS reference pages into `.scratch/` as SOP generation input.

BUILD-TIME ONLY. Never imported by `src/`.

The fetched HTML is **gitignored and never committed** (`sop_design.md` S8.1):
copyright protects expression, not facts, so this project commits restatements
with citations and not a page dump. These files exist only so that facts written
into `data/sop_specs/*.yaml` can be checked against their source during the human
review pass, which is where the public-URL traceability guarantee is enforced.

Usage:
    python scripts/fetch_reference.py            # fetch all pages in the registry
    python scripts/fetch_reference.py --list     # show the registry
    python scripts/fetch_reference.py giro_iit   # fetch one page by handle
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen

SCRATCH = Path(__file__).resolve().parent.parent / ".scratch"

# Browser UA: the IRAS site serves a JS navigation shell to unknown agents.
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# handle -> url. Handles are what `data/sop_specs/*.yaml` cite in `references[].id`.
PAGES: dict[str, str] = {
    # payment
    "giro_iit": "https://www.iras.gov.sg/quick-links/payments/giro-individual-income-tax",
    "payment_iit": "https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/receive-tax-bill-pay-tax-check-refunds/how-to-pay",
    "late_payment": "https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/receive-tax-bill-pay-tax-check-refunds/late-payment-or-non-payment-of-individual-income-tax",
    "refunds": "https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/receive-tax-bill-pay-tax-check-refunds/refunds",
    # filing
    "who_must_file": "https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/understanding-my-income-tax-filing/individuals-required-to-file-tax",
    "filing_deadline": "https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/understanding-my-income-tax-filing/tax-season-2026---all-you-need-to-know",
    "no_filing_service": "https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/understanding-my-income-tax-filing/tax-season-2026---all-you-need-to-know",
    "late_filing": "https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/understanding-my-income-tax-filing/late-filing-or-non-filing-of-individual-income-tax-returns-form-b1-b-p-m",
    # assessment and amendment
    "tax_bill": "https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/receive-tax-bill-pay-tax-check-refunds/getting-my-tax-assessment",
    "object_to_assessment": "https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/receive-tax-bill-pay-tax-check-refunds/making-changes-after-filing-receiving-tax-bill",
    # residency
    "tax_residency": "https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-residency-and-tax-rates",
    "non_resident_rates": "https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-residency-and-tax-rates/individual-income-tax-rates",
    "cor": "https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-residency-and-tax-rates/apply-for-certificate-of-residence",
    # reliefs
    "reliefs_overview": "https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions",
    "qcr": "https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/qualifying-child-relief-(qcr)-child-relief-(disability)",
    "parent_relief": "https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/parent-relief-parent-relief-(disability)",
    "cpf_relief": "https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/central-provident-fund(cpf)-relief-for-employees",
    "srs_relief": "https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/supplementary-retirement-scheme-(srs)-relief",
    "wmcr": "https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/working-mother's-child-relief-(wmcr)",
    "ptr": "https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/parenthood-tax-rebate-(ptr)",
    "relief_cap": "https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs",
    "efiling": "https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/understanding-my-income-tax-filing/e-filing-your-income-tax-return",
    "paper_filing": "https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/understanding-my-income-tax-filing/filing-a-paper-income-tax-return",
    "understanding_assessment": "https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/receive-tax-bill-pay-tax-check-refunds/understanding-my-tax-assessment",
    "difficulty_paying": "https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/receive-tax-bill-pay-tax-check-refunds/experiencing-difficulties-in-paying-your-tax",
    # held-out classes
    "rental_income": "https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/what-is-taxable-what-is-not/income-from-property-rented-out",
    "foreign_income": "https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/what-is-taxable-what-is-not/income-received-from-overseas",
    "dta_relief": "https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-residency-and-tax-rates/claiming-exemptions-under-Avoidance-of-Double-Taxation-Agreements-(DTAs)",
    # escalation / redirect
    "scam_advisory": "https://www.iras.gov.sg/news-events/announcements/scam-advisory/phishing-email-scam",
    "scam_refund": "https://www.iras.gov.sg/news-events/announcements/scam-advisory/tax-refund-scam",
    "sole_prop": "https://www.iras.gov.sg/taxes/individual-income-tax/self-employed-and-partnerships",
    "corporate_tax": "https://www.iras.gov.sg/taxes/corporate-income-tax",
    "tax_clearance": "https://www.iras.gov.sg/taxes/individual-income-tax/employers/tax-clearance-for-foreign-spr-employees-(ir21)",
}


def fetch(handle: str, url: str, *, timeout: int = 30) -> dict[str, object]:
    """Fetch one page into `.scratch/<handle>.html`. Returns a manifest record."""
    SCRATCH.mkdir(exist_ok=True)
    dest = SCRATCH / f"{handle}.html"
    record: dict[str, object] = {
        "handle": handle,
        "url": url,
        "fetched": date.today().isoformat(),
    }
    try:
        with urlopen(Request(url, headers={"User-Agent": _UA}), timeout=timeout) as resp:
            body = resp.read()
            record["status"] = resp.status
    except Exception as exc:  # noqa: BLE001 - report and continue; partial fetch is fine
        record["status"] = "ERROR"
        record["error"] = f"{type(exc).__name__}: {exc}"
        return record

    dest.write_bytes(body)
    record["bytes"] = len(body)
    record["path"] = str(dest.relative_to(SCRATCH.parent))
    return record


def to_text(html: str) -> str:
    """Crude tag strip, adequate for eyeballing facts during the review pass."""
    html = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    for entity, char in (("&nbsp;", " "), ("&amp;", "&"), ("&#160;", " "),
                         ("&quot;", '"'), ("&#39;", "'"), ("&rsquo;", "'")):
        text = text.replace(entity, char)
    return re.sub(r"\s+", " ", text).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("handles", nargs="*", help="handles to fetch (default: all)")
    parser.add_argument("--list", action="store_true", help="list the registry and exit")
    parser.add_argument("--delay", type=float, default=1.0, help="seconds between requests")
    args = parser.parse_args()

    if args.list:
        for handle, url in PAGES.items():
            print(f"{handle:24s} {url}")
        return 0

    handles = args.handles or list(PAGES)
    unknown = [h for h in handles if h not in PAGES]
    if unknown:
        print(f"unknown handle(s): {', '.join(unknown)}", file=sys.stderr)
        return 2

    manifest = []
    for i, handle in enumerate(handles):
        record = fetch(handle, PAGES[handle])
        manifest.append(record)
        status = record["status"]
        size = record.get("bytes", 0)
        marker = "ok " if status == 200 else "FAIL"
        print(f"[{marker}] {handle:24s} {status} {size:>8} bytes")
        if i < len(handles) - 1:
            time.sleep(args.delay)  # courtesy rate limit

    (SCRATCH / "manifest.json").write_text(json.dumps(manifest, indent=2))
    failed = sum(1 for r in manifest if r["status"] != 200)
    print(f"\n{len(manifest) - failed}/{len(manifest)} fetched -> {SCRATCH}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
