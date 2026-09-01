---
synthetic: true
sop_id: SOP-REL-004
title: "Working Mother's Child Relief and Parenthood Tax Rebate"
version: "2.0"
effective_date: 2025-01-01
supersedes: SOP-REL-004-v1.0
applies_to_ya: [2025, 2026]
intents: [tax_reliefs]
indexed: true
owner_queue: IIT-General
handling_target: 5_working_days
auto_reply_permitted: true
escalate_if:
  - account_specific
  - amount_computation_requested
references:
  - https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/working-mother's-child-relief-(wmcr)
  - https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/parenthood-tax-rebate-(ptr)
last_reviewed: 2026-09-01
---

# SOP-REL-004 - Working Mother's Child Relief and Parenthood Tax Rebate

> **SYNTHETIC DOCUMENT.** Authored for a technical assessment. This is not an
> IRAS document and does not reflect IRAS internal material, templates or
> practice. Every factual claim is a restatement traceable to the public
> source cited beside it in section 2.

## 1. Scope

Taxpayer asks whether they qualify for Working Mother's Child Relief, how the amount is determined, how child order is decided, how WMCR interacts with QCR, or how the Parenthood Tax Rebate works including carry-forward and transfer.

**Not in scope:**
- How much WMCR or PTR this taxpayer will receive, or their resulting tax. -> escalate (`amount_computation_requested`)
- The taxpayer's own PTR balance or whether a claim was allowed. -> escalate (`account_specific`)
- Whether the total of all reliefs is limited. -> escalate (`tax_reliefs`)

## 2. Key facts the officer may state

- With effect from YA 2025, WMCR changed from a percentage of an eligible working mother's annual earned income to a fixed dollar tax relief, for Singaporean children born or adopted on or after 1 January 2024.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/working-mother's-child-relief-(wmcr)</sup>
- For a qualifying Singaporean child born or adopted on or after 1 January 2024, WMCR is $8,000 for the first child, $10,000 for the second, and $12,000 for the third and each subsequent child.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/working-mother's-child-relief-(wmcr)</sup>
- For a qualifying Singaporean child born or adopted before 1 January 2024, WMCR is 15% of the mother's earned income for the first child, 20% for the second, and 25% for the third and each subsequent child.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/working-mother's-child-relief-(wmcr)</sup>
- Where a child was born or adopted before 1 January 2024 but became a Singapore Citizen only after that date, the fixed dollar rate applies. The amount is based on the date the child became a Singapore Citizen.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/working-mother's-child-relief-(wmcr)</sup>
- Child order is determined by date of birth for a child born to the taxpayer and their spouse or ex-spouse; by date of marriage where the child was born before the marriage; by date of birth for a step-child; and by the date of legal adoption for an adopted child.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/working-mother's-child-relief-(wmcr)</sup>
- A deceased or stillborn child is counted in determining the order of children.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/working-mother's-child-relief-(wmcr)</sup>
- Where a mother claims WMCR for multiple children, the amounts are added together and the total claim is capped at 100% of her earned income.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/working-mother's-child-relief-(wmcr)</sup>
- WMCR may be claimed even where the taxpayer or her husband or ex-husband has already claimed QCR or Child Relief (Disability) on the same child.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/working-mother's-child-relief-(wmcr)</sup>
- QCR or Child Relief (Disability) is allowed first, and WMCR is limited to the remaining balance. The combined cap is $50,000 per child.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/working-mother's-child-relief-(wmcr)</sup>
- WMCR may be claimed for YA 2026 even where the child passed away in 2025.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/working-mother's-child-relief-(wmcr)</sup>
- Parenthood Tax Rebate is given to tax residents, is a one-off rebate of up to $20,000 per child, and may be claimed on a qualifying child only once.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/parenthood-tax-rebate-(ptr)</sup>
- PTR amounts by child order are $5,000 for the first child, $10,000 for the second, and $20,000 for the third and fourth child.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/parenthood-tax-rebate-(ptr)</sup>
- Any unutilised PTR is carried forward to offset income tax payable in subsequent years until it is fully utilised.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/parenthood-tax-rebate-(ptr)</sup>
- Unutilised PTR may be transferred to a spouse, and where one spouse passes away the surviving spouse may continue to use the credit balance remaining in their respective PTR accounts.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/parenthood-tax-rebate-(ptr)</sup>
- For PTR purposes no child is considered a member of two households, and children from a previous marriage are taken into account in determining child order.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/parenthood-tax-rebate-(ptr)</sup>

## 3. Decision steps

1. **If** Asking how much WMCR or PTR they will get, or what their tax will be  
   -> Escalate (`amount_computation_requested`)
2. **If** Asking about their own PTR balance, or whether their claim was allowed  
   -> Escalate (`account_specific`)
3. **If** Child born or adopted on or after 1 Jan 2024 (or became a Singapore Citizen after that date)  
   -> Apply the fixed dollar basis
4. **If** Child born or adopted before 1 Jan 2024  
   -> Apply the percentage-of-earned-income basis
5. **If** Asking whether total reliefs are capped  
   -> Escalate (`no_supporting_sop`)
6. **If** Otherwise  
   -> State the qualifying basis and the ordering rule from the key facts

## 4. Approved phrasing

**`wmcr_post_2024`**

> For a qualifying Singaporean child born or adopted on or after 1 January 2024, Working Mother's Child Relief is a fixed amount: $8,000 for the first child, $10,000 for the second, and $12,000 for the third and each subsequent child.

**`wmcr_pre_2024`**

> For a qualifying Singaporean child born or adopted before 1 January 2024, Working Mother's Child Relief is calculated as a percentage of your earned income: 15% for the first child, 20% for the second, and 25% for the third and each subsequent child.

**`wmcr_ordering`**

> You may claim Working Mother's Child Relief even if you or your husband or ex-husband has already claimed Qualifying Child Relief or Child Relief (Disability) on the same child. Qualifying Child Relief is allowed first, and Working Mother's Child Relief is limited to the remaining balance, with a combined cap of $50,000 per child.

**`ptr`**

> The Parenthood Tax Rebate is a one-off rebate for tax residents, of $5,000 for the first child, $10,000 for the second, and $20,000 for the third and fourth child. Any unutilised amount is carried forward to offset your income tax in later years until it is fully used, and it may also be transferred to your spouse.

**`computation_escalation`**

> Because these reliefs interact with one another and are subject to caps, we have passed your enquiry to an officer who will confirm the amounts that apply to your circumstances.

## 5. Do not

- Do not compute a WMCR amount, a PTR balance, or resulting tax.
- Do not apply the percentage basis to a child born on or after 1 Jan 2024, or the fixed dollar basis to a child born before that date.
- Do not confirm whether a specific claim has been allowed.
- Do not state the overall personal relief cap — escalate instead.

## 6. Related

- SOP-REL-001
- SOP-REL-005
- SOP-ASM-001
- ANNEX-REL-A
