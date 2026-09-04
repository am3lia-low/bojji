---
synthetic: true
sop_id: SOP-ESC-002
title: Hardship and waiver requests
version: "1.0"
effective_date: 2026-01-01
supersedes: null
applies_to_ya: [2025, 2026]
intents: [hardship_or_waiver]
indexed: true
owner_queue: IIT-Recovery
handling_target: 5_working_days
auto_reply_permitted: false
escalate_if:
  - hardship_or_waiver_request
  - account_specific
  - amount_computation_requested
references:
  - https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/receive-tax-bill-pay-tax-check-refunds/experiencing-difficulties-in-paying-your-tax
  - https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/receive-tax-bill-pay-tax-check-refunds/late-payment-or-non-payment-of-individual-income-tax
last_reviewed: 2026-09-01
---

# SOP-ESC-002 - Hardship and waiver requests

> **SYNTHETIC DOCUMENT.** Written for this assessment from the public sources cited
> in section 2. It is not an IRAS document or internal procedure. See
> [data provenance](../SOURCES.md).

## 1. Scope

Taxpayer states they cannot pay, asks for a longer or restructured instalment plan, asks for a late-payment penalty or composition amount to be waived or reduced, or describes financial hardship, retrenchment, illness or bereavement in connection with a tax debt.

**Not in scope:**
- Generic questions about how GIRO instalments work, with no hardship stated. -> escalate (`payment`)
- Disputing that the tax is owed at all, rather than asking for time to pay. -> escalate (`assessment_and_amendment`)

## 2. Key facts the officer may state

- IRAS states that taxpayers facing difficulties paying their tax may approach IRAS for a payment arrangement that takes their circumstances into account.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/receive-tax-bill-pay-tax-check-refunds/experiencing-difficulties-in-paying-your-tax</sup>
- A taxpayer should not ignore a tax bill or a demand for payment; otherwise a 5% late payment penalty is imposed on the overdue tax.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/receive-tax-bill-pay-tax-check-refunds/experiencing-difficulties-in-paying-your-tax</sup>
- Longer payment plan arrangements and financial and other support services are described on the IRAS page on difficulties in paying tax.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/receive-tax-bill-pay-tax-check-refunds/experiencing-difficulties-in-paying-your-tax</sup>
- Unless the taxpayer is on an approved instalment plan, a 5% late payment penalty is imposed on tax not paid in full by the due date.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/receive-tax-bill-pay-tax-check-refunds/late-payment-or-non-payment-of-individual-income-tax</sup>

## 3. Decision steps

1. **If** The taxpayer states or implies they cannot pay, or requests a waiver or reduction  
   -> Escalate (`high_consequence`)
2. **If** Always  
   -> Escalate — this class never auto-replies

## 4. Approved phrasing

**`acknowledgement`**

> Thank you for writing in. We understand that paying tax can be difficult, and your enquiry has been passed to an officer who will review your circumstances and reply to you directly. In the meantime, please do not disregard your tax bill or any demand for payment, as a late payment penalty may otherwise be imposed on the overdue amount while your request is being considered.

## 5. Do not

- Do not indicate, suggest or imply whether a waiver or instalment request will be approved or refused.
- Do not quote a possible instalment amount or duration.
- Do not compute penalties, interest or an outstanding balance.
- Do not tell the taxpayer to stop paying while the request is considered.
- Do not request financial documents or personal circumstances by email.

## 6. Related

- SOP-PAY-001
- SOP-PAY-002
- SOP-ESC-001
