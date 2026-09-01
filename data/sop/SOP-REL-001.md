---
synthetic: true
sop_id: SOP-REL-001
title: Qualifying Child Relief and Child Relief (Disability)
version: "1.0"
effective_date: 2026-01-01
supersedes: null
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
  - https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/qualifying-child-relief-(qcr)-child-relief-(disability)
last_reviewed: 2026-09-01
---

# SOP-REL-001 - Qualifying Child Relief and Child Relief (Disability)

> **SYNTHETIC DOCUMENT.** Authored for a technical assessment. This is not an
> IRAS document and does not reflect IRAS internal material, templates or
> practice. Every factual claim is a restatement traceable to the public
> source cited beside it in section 2.

## 1. Scope

Taxpayer asks whether they qualify for Qualifying Child Relief or Child Relief (Disability), what the conditions are, how the relief is shared between parents, or how to claim it.

**Not in scope:**
- How much relief this taxpayer will receive, or their resulting tax. -> escalate (`amount_computation_requested`)
- Whether a claim already made has been allowed. -> escalate (`account_specific`)
- How WMCR interacts with QCR, and the per-child cap. -> escalate (`tax_reliefs`)
- Whether the total of all reliefs is limited. -> escalate (`tax_reliefs`)

## 2. Key facts the officer may state

- To claim Qualifying Child Relief for Year of Assessment 2026, all conditions must be satisfied in 2025.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/qualifying-child-relief-(qcr)-child-relief-(disability)</sup>
- The child must be unmarried, and must be born to the taxpayer and their spouse or ex-spouse, be a step-child, or be legally adopted.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/qualifying-child-relief-(qcr)-child-relief-(disability)</sup>
- The child must have been below 16 years old, or 16 years old or above and studying full-time at any university, college or other educational institution at any time in the year.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/qualifying-child-relief-(qcr)-child-relief-(disability)</sup>
- The child must not have had annual income exceeding $8,000 in the year. For YA 2024 and before, the annual income threshold was $4,000.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/qualifying-child-relief-(qcr)-child-relief-(disability)</sup>
- Qualifying Child Relief is $4,000 per qualifying child.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/qualifying-child-relief-(qcr)-child-relief-(disability)</sup>
- Child Relief (Disability) is $7,500 per qualifying child.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/qualifying-child-relief-(qcr)-child-relief-(disability)</sup>
- Where a working mother has met the conditions for Working Mother's Child Relief, QCR or Child Relief (Disability) and WMCR may both be claimed on the same child.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/qualifying-child-relief-(qcr)-child-relief-(disability)</sup>
- QCR or Child Relief (Disability) plus WMCR is capped at $50,000 per child.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/qualifying-child-relief-(qcr)-child-relief-(disability)</sup>
- QCR or Child Relief (Disability) is allowed first, regardless of whether it is claimed by the father or the mother, and WMCR is limited to the remaining balance.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/qualifying-child-relief-(qcr)-child-relief-(disability)</sup>
- Parents may share the relief on the same child according to an apportionment they agree between themselves.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/qualifying-child-relief-(qcr)-child-relief-(disability)</sup>

## 3. Decision steps

1. **If** Asking how much relief they will get, or what their tax will be  
   -> Escalate (`amount_computation_requested`)
2. **If** Asking whether their own claim was allowed, or about their own tax bill  
   -> Escalate (`account_specific`)
3. **If** Asking specifically about the WMCR interaction or the per-child cap  
   -> Also ground on SOP-REL-004
4. **If** Asking whether total reliefs are capped  
   -> Escalate (`no_supporting_sop`)
5. **If** Otherwise  
   -> State the qualifying conditions from the key facts

## 4. Approved phrasing

**`qcr_conditions`**

> To claim Qualifying Child Relief for Year of Assessment 2026, all the conditions must have been met in 2025. Your child must be unmarried, and must be your own child, a step-child, or legally adopted. The child must have been below 16 years old, or 16 or above and studying full-time at a university, college or other educational institution at any time during the year. The child must also not have had annual income of more than $8,000.

**`qcr_amounts`**

> Qualifying Child Relief is $4,000 per qualifying child, and Child Relief (Disability) is $7,500 per qualifying child.

**`sharing`**

> Parents may share the relief for the same child in a proportion they agree between themselves.

**`wmcr_ordering`**

> If you are a working mother who also qualifies for Working Mother's Child Relief, both reliefs may be claimed on the same child. Qualifying Child Relief or Child Relief (Disability) is allowed first, and Working Mother's Child Relief is limited to the remaining balance, with a combined cap of $50,000 per child.

**`computation_escalation`**

> The amount of relief you will actually receive depends on how these reliefs interact and on the overall cap on personal reliefs, so we have passed your enquiry to an officer who will confirm the position for your circumstances.

## 5. Do not

- Do not compute a relief amount, a combined relief total, or resulting tax.
- Do not confirm whether a specific claim has been allowed.
- Do not state the overall personal relief cap — that is SOP-REL-005, which is not available to this procedure. Escalate instead.
- Do not advise on how parents should apportion relief between themselves.

## 6. Related

- SOP-REL-004
- SOP-REL-005
- SOP-ASM-001
