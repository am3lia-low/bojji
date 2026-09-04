---
synthetic: true
sop_id: SOP-ASM-001
title: Handling assessment and amendment enquiries
version: "1.0"
effective_date: 2026-01-01
supersedes: null
applies_to_ya: [2025, 2026]
intents: [assessment_and_amendment]
indexed: true
owner_queue: IIT-General
handling_target: 5_working_days
auto_reply_permitted: true
escalate_if:
  - account_specific
  - amount_computation_requested
  - hardship_or_waiver_request
  - scam_report
references:
  - https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/receive-tax-bill-pay-tax-check-refunds/understanding-my-tax-assessment
  - https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/receive-tax-bill-pay-tax-check-refunds/making-changes-after-filing-receiving-tax-bill
  - https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/receive-tax-bill-pay-tax-check-refunds/getting-my-tax-assessment
last_reviewed: 2026-09-01
---

# SOP-ASM-001 - Handling assessment and amendment enquiries

> **SYNTHETIC DOCUMENT.** Written for this assessment from the public sources cited
> in section 2. It is not an IRAS document or internal procedure. See
> [data provenance](../SOURCES.md).

## 1. Scope

Taxpayer asks what a Notice of Assessment means, what the different NOA types are, how to read the terms on a tax bill, how to amend an assessment, how to object to one, or what happens while an objection is under review.

**Not in scope:**
- The figures in this taxpayer's own assessment, or the status of their own objection. -> escalate (`account_specific`)
- How or when to submit a return, and filing deadlines. -> escalate (`filing`)
- Recomputing tax, reliefs or a revised balance for the taxpayer. -> escalate (`amount_computation_requested`)
- Asking for a penalty arising from the assessment to be waived. -> escalate (`hardship_or_waiver_request`)

## 2. Key facts the officer may state

- A Notice of Assessment (Original) is the tax bill computed from the tax form(s) submitted and information sent by organisations participating in the Auto-Inclusion Scheme.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/receive-tax-bill-pay-tax-check-refunds/understanding-my-tax-assessment</sup>
- A Notice of Assessment (Amended) is issued when an assessment is amended downwards, resulting in a reduction in tax payable — for example on the inclusion of reliefs or a reduction in income.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/receive-tax-bill-pay-tax-check-refunds/understanding-my-tax-assessment</sup>
- A Notice of Assessment (Additional) is issued when an assessment is amended upwards, resulting in additional tax payable — for example on the withdrawal of reliefs or the inclusion of additional income.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/receive-tax-bill-pay-tax-check-refunds/understanding-my-tax-assessment</sup>
- A Notice of Assessment (Estimated) may be issued where a return has not been filed by the due date, estimating tax from available information. The taxpayer must still file the return for IRAS to issue an amended or additional assessment.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/receive-tax-bill-pay-tax-check-refunds/understanding-my-tax-assessment</sup>
- Year of Assessment (YA) is the tax year in which income tax is calculated and charged, on income earned in the preceding calendar year. Income taxed in YA 2026 is income earned from 1 January 2025 to 31 December 2025.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/receive-tax-bill-pay-tax-check-refunds/understanding-my-tax-assessment</sup>
- A return filed online may be re-filed once, by 18 April. Otherwise the tax bill is amended through the 'Amend Tax Bill' digital service at myTax Portal.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/receive-tax-bill-pay-tax-check-refunds/making-changes-after-filing-receiving-tax-bill</sup>
- Amendments must be filed within 30 days from the date stated on the income tax bill (the Notice of Assessment). IRAS reviews the amendment and informs the taxpayer of the outcome.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/receive-tax-bill-pay-tax-check-refunds/making-changes-after-filing-receiving-tax-bill</sup>
- The 'Amend Tax Bill' digital service may be used to revise an income declaration, to add or amend claims for deductions and reliefs, and to claim Parenthood Tax Rebate.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/receive-tax-bill-pay-tax-check-refunds/making-changes-after-filing-receiving-tax-bill</sup>
- The obligation to pay is not suspended by an objection: tax must be paid within 1 month of the Notice of Assessment, and a late payment penalty applies to tax outstanding after 1 month, even where an objection is under review.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/receive-tax-bill-pay-tax-check-refunds/making-changes-after-filing-receiving-tax-bill</sup>
- Where an assessment is revised after an objection is reviewed, any credit balance is refunded within 30 days from the date of the new tax bill, the Notice of Assessment (Amended).  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/receive-tax-bill-pay-tax-check-refunds/making-changes-after-filing-receiving-tax-bill</sup>
- The re-filing route by 18 April does not apply to taxpayers under the Direct Notice of Assessment (D-NOA) scheme.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/receive-tax-bill-pay-tax-check-refunds/making-changes-after-filing-receiving-tax-bill</sup>

## 3. Decision steps

1. **If** Asking about the figures in their own assessment, or the status of their own objection  
   -> Escalate (`account_specific`)
2. **If** Asking IRAS to recompute their tax, relief or revised balance  
   -> Escalate (`amount_computation_requested`)
3. **If** Asking for a penalty to be waived because of the assessment  
   -> Escalate (`hardship_or_waiver_request`)
4. **If** Asking only how or when to file a return, with no dispute about figures  
   -> Route to SOP-FIL-001 (`tie_break_filing_mechanics`)
5. **If** Otherwise  
   -> Explain the assessment type and the amendment route from the key facts

## 4. Approved phrasing

**`noa_types`**

> A Notice of Assessment (Original) is the tax bill computed from the return you filed together with information provided under the Auto-Inclusion Scheme. A Notice of Assessment (Amended) is issued when your assessment is revised downwards, and a Notice of Assessment (Additional) when it is revised upwards. A Notice of Assessment (Estimated) may be issued where a return has not been filed by the due date; you must still file the return so that the assessment can be revised.

**`amend_window`**

> If you need to make a change after receiving your tax bill, you may file an amendment using the 'Amend Tax Bill' digital service at myTax Portal within 30 days from the date on your Notice of Assessment. IRAS will review the amendment and inform you of the outcome.

**`pay_while_objecting`**

> Please note that filing an objection does not defer payment. Tax is due within 1 month of the date of your Notice of Assessment, and a late payment penalty applies to tax outstanding after that date even while an objection is being reviewed. If your assessment is revised, any credit balance is refunded within 30 days from the date of the amended tax bill.

**`ya_meaning`**

> The Year of Assessment is the year in which tax is calculated and charged on income earned in the preceding calendar year. For example, Year of Assessment 2026 covers income earned from 1 January to 31 December 2025.

## 5. Do not

- Do not comment on the figures in a specific taxpayer's assessment.
- Do not predict the outcome of an objection or amendment.
- Do not recompute tax, reliefs or a revised balance.
- Do not advise that payment may be withheld pending an objection.

## 6. Related

- SOP-FIL-001
- SOP-PAY-002
- SOP-REL-005
