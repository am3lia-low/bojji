---
synthetic: true
sop_id: SOP-PAY-001
title: Handling GIRO enquiries
version: "1.0"
effective_date: 2026-01-01
supersedes: null
applies_to_ya: [2025, 2026]
intents: [payment]
indexed: true
owner_queue: IIT-Payments
handling_target: same_day
auto_reply_permitted: true
escalate_if:
  - account_specific
  - hardship_or_waiver_request
  - amount_computation_requested
references:
  - https://www.iras.gov.sg/quick-links/payments/giro-individual-income-tax
last_reviewed: 2026-09-01
---

# SOP-PAY-001 - Handling GIRO enquiries

> **SYNTHETIC DOCUMENT.** Authored for a technical assessment. This is not an
> IRAS document and does not reflect IRAS internal material, templates or
> practice. Every factual claim is a restatement traceable to the public
> source cited beside it in section 2.

## 1. Scope

Taxpayer asks how GIRO works, how to apply, when deductions occur, what happens when a deduction fails, how the provisional instalment plan works, or how to edit, cancel or re-activate an arrangement.

**Not in scope:**
- The status of a specific taxpayer's GIRO plan, or why their deduction failed. -> escalate (`account_specific`)
- Restructuring instalments because the taxpayer cannot afford them. -> escalate (`hardship_or_waiver_request`)
- Computing an instalment amount for a specific taxpayer. -> escalate (`amount_computation_requested`)

## 2. Key facts the officer may state

- Tax may be paid by GIRO either in monthly instalments of up to 12 months, or as a one-time yearly payment.  
  <sup>Source: https://www.iras.gov.sg/quick-links/payments/giro-individual-income-tax</sup>
- Monthly GIRO deductions are made on the 6th of each month.  
  <sup>Source: https://www.iras.gov.sg/quick-links/payments/giro-individual-income-tax</sup>
- If the deduction date falls on a weekend or public holiday, the deduction is made on the next working day.  
  <sup>Source: https://www.iras.gov.sg/quick-links/payments/giro-individual-income-tax</sup>
- If a GIRO deduction is unsuccessful, a second deduction is attempted on the 20th of the month.  
  <sup>Source: https://www.iras.gov.sg/quick-links/payments/giro-individual-income-tax</sup>
- A GIRO arrangement is cancelled after 2 consecutive months of failed deductions, that is, 4 failed deductions in a row.  
  <sup>Source: https://www.iras.gov.sg/quick-links/payments/giro-individual-income-tax</sup>
- The Provisional Instalment Plan (PIP) commences yearly from May, based on the previous year's tax or the current year's estimated tax payable.  
  <sup>Source: https://www.iras.gov.sg/quick-links/payments/giro-individual-income-tax</sup>
- Once the assessment is finalised, the monthly GIRO arrangement is revised based on the actual tax payable.  
  <sup>Source: https://www.iras.gov.sg/quick-links/payments/giro-individual-income-tax</sup>
- Where a taxpayer joins GIRO after May, instalment deductions commence in the month after the application is approved and end in April of the following year.  
  <sup>Source: https://www.iras.gov.sg/quick-links/payments/giro-individual-income-tax</sup>
- eGIRO applications may be made through myTax Portal (set up within minutes), through the DBS/POSB, OCBC or UOB bank portals (within 3 working days), or at AXS stations (within 3 working days).  
  <sup>Source: https://www.iras.gov.sg/quick-links/payments/giro-individual-income-tax</sup>
- Hard copy GIRO applications require up to 21 working days to process, and the exact timeline is subject to the respective bank's processing.  
  <sup>Source: https://www.iras.gov.sg/quick-links/payments/giro-individual-income-tax</sup>
- GIRO must be applied for using an SGD savings or current account with a participating bank.  
  <sup>Source: https://www.iras.gov.sg/quick-links/payments/giro-individual-income-tax</sup>
- For a successful deduction the account must hold sufficient funds on the deduction date and have a suitable payment limit set. Some banks may impose charges for unsuccessful GIRO deductions.  
  <sup>Source: https://www.iras.gov.sg/quick-links/payments/giro-individual-income-tax</sup>
- A cancelled GIRO arrangement may be re-activated through the 'Apply/Manage GIRO Plan' digital service at myTax Portal.  
  <sup>Source: https://www.iras.gov.sg/quick-links/payments/giro-individual-income-tax</sup>
- To terminate a GIRO arrangement entirely, the taxpayer must contact their bank directly; a cancelled arrangement can still be re-activated with IRAS.  
  <sup>Source: https://www.iras.gov.sg/quick-links/payments/giro-individual-income-tax</sup>

## 3. Decision steps

1. **If** Asking about their own plan, a specific failed deduction, or their own instalment amount  
   -> Escalate (`account_specific`)
2. **If** Requesting penalty waiver, or restructuring because they cannot afford the instalments  
   -> Escalate (`hardship_or_waiver_request`)
3. **If** Asking IRAS to calculate an instalment amount or a balance  
   -> Escalate (`amount_computation_requested`)
4. **If** Otherwise  
   -> Answer from the key facts and direct to the application channels

## 4. Approved phrasing

**`giro_dates`**

> Payments by GIRO are deducted on the 6th of each month. If the 6th falls on a weekend or public holiday, the deduction is made on the next working day. Where a deduction is unsuccessful, a second attempt is made on the 20th of the month.

**`giro_failure`**

> A GIRO arrangement is cancelled after two consecutive months of failed deductions, that is, four failed deductions in a row. Please ensure that your account holds sufficient funds on the deduction date and that a suitable payment limit is set. If your arrangement has been cancelled, you may re-activate it through the 'Apply/Manage GIRO Plan' digital service at myTax Portal.

**`giro_apply`**

> You can apply for eGIRO through myTax Portal, which is set up within minutes, or through the DBS/POSB, OCBC and UOB bank portals and AXS stations, which take up to 3 working days. GIRO must be set up using an SGD savings or current account with a participating bank.

**`pip`**

> The Provisional Instalment Plan begins in May each year and is based on the previous year's tax or the current year's estimated tax payable. Once your assessment is finalised, your monthly instalments are revised to reflect the actual tax payable.

## 5. Do not

- Do not confirm whether a specific deduction succeeded or failed.
- Do not advise on bank charges — refer the taxpayer to their bank.
- Do not compute instalment amounts or outstanding balances.
- Do not state when a specific taxpayer's plan will be revised.

## 6. Related

- SOP-PAY-002
- SOP-ESC-002
