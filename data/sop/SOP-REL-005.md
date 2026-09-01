---
synthetic: true
sop_id: SOP-REL-005
title: Personal income tax relief cap
version: "1.0"
effective_date: 2026-01-01
supersedes: null
applies_to_ya: [2025, 2026]
intents: [tax_reliefs]
indexed: false
owner_queue: IIT-General
handling_target: 5_working_days
auto_reply_permitted: true
escalate_if:
  - account_specific
  - amount_computation_requested
references:
  - https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs
  - https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/working-mother's-child-relief-(wmcr)
last_reviewed: 2026-09-01
---

# SOP-REL-005 - Personal income tax relief cap

> **SYNTHETIC DOCUMENT.** Authored for a technical assessment. This is not an
> IRAS document and does not reflect IRAS internal material, templates or
> practice. Every factual claim is a restatement traceable to the public
> source cited beside it in section 2.

> **HELD OUT OF THE INDEX.** This procedure is authored but excluded from
> the runtime lookup, so the classes it serves resolve to no SOP. See
> `sop_design.md` S5.

## 1. Scope

Taxpayer asks whether there is a limit on the total amount of personal reliefs they may claim, how the cap applies across different reliefs, or what happens when their claims exceed it.

**Not in scope:**
- Whether this taxpayer's own reliefs exceed the cap, and by how much. -> escalate (`account_specific`)
- Computing the taxpayer's total reliefs or resulting tax. -> escalate (`amount_computation_requested`)

## 2. Key facts the officer may state

- A personal income tax relief cap of $80,000 applies to the total amount of all tax reliefs claimed for each Year of Assessment.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs</sup>
- A taxpayer is affected by the cap if the total amount of personal reliefs they claim exceeds $80,000.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs</sup>
- The overall personal income tax relief cap takes effect from Year of Assessment 2018.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs</sup>
- The cap applies to the total of all personal reliefs taken together. It is not a limit within any single relief, so it cannot be determined from the rules of one relief alone.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs</sup>
- Where the cap applies, the reliefs allowed are limited to $80,000, and this is reflected in the Notice of Assessment.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs</sup>
- The cap applies to the total of all reliefs, including relief on compulsory and voluntary CPF contributions.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs</sup>
- The $80,000 cap operates on top of the individual caps within specific reliefs, such as the $50,000 per-child cap on QCR or Child Relief (Disability) combined with WMCR.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/working-mother's-child-relief-(wmcr)</sup>
- There is no refund of accepted voluntary CPF or SRS contributions where the relief cap means they attract no tax relief.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs</sup>

## 3. Decision steps

1. **If** Asking whether their own reliefs exceed the cap  
   -> Escalate (`account_specific`)
2. **If** Asking IRAS to total their reliefs or compute the effect of the cap  
   -> Escalate (`amount_computation_requested`)
3. **If** Otherwise  
   -> State the cap and how it applies from the key facts

## 4. Approved phrasing

**`cap`**

> A personal income tax relief cap of $80,000 applies to the total amount of all tax reliefs you claim in each Year of Assessment. If the total of your personal reliefs exceeds $80,000, the reliefs allowed to you are limited to $80,000, and this is reflected in your Notice of Assessment.

**`interaction`**

> The $80,000 cap applies on top of the caps within individual reliefs, such as the $50,000 combined cap per child on Qualifying Child Relief and Working Mother's Child Relief.

**`no_refund`**

> Please note that voluntary CPF and SRS contributions cannot be refunded if the relief cap means they do not attract tax relief, so it is worth considering the cap before making a voluntary contribution.

## 5. Do not

- Do not total a taxpayer's reliefs or compute the effect of the cap for them.
- Do not confirm whether a specific taxpayer is affected by the cap.
- Do not advise whether a voluntary contribution is financially worthwhile.

## 6. Related

- SOP-REL-001
- SOP-REL-002
- SOP-REL-003
- SOP-REL-004
