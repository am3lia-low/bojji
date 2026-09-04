---
synthetic: true
sop_id: SOP-REL-002
title: Parent Relief and Parent Relief (Disability)
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
  - scam_report
references:
  - https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/parent-relief-parent-relief-(disability)
last_reviewed: 2026-09-01
---

# SOP-REL-002 - Parent Relief and Parent Relief (Disability)

> **SYNTHETIC DOCUMENT.** Written for this assessment from the public sources cited
> in section 2. It is not an IRAS document or internal procedure. See
> [data provenance](../SOURCES.md).

## 1. Scope

Taxpayer asks whether they qualify for Parent Relief or Parent Relief (Disability) in respect of a parent, grandparent, parent-in-law or grandparent-in-law, what the conditions are, how many dependants may be claimed, or how the relief is shared between claimants.

**Not in scope:**
- How much relief this taxpayer will receive, or their resulting tax. -> escalate (`amount_computation_requested`)
- Whether a claim already made has been allowed. -> escalate (`account_specific`)
- Whether the total of all reliefs is limited. -> escalate (`tax_reliefs`)

## 2. Key facts the officer may state

- Parent Relief recognises individuals supporting their parents, grandparents, parents-in-law or grandparents-in-law in Singapore.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/parent-relief-parent-relief-(disability)</sup>
- Qualifying dependants include parents, parents-in-law, grandparents, grandparents-in-law, step-parents, step-grandparents, adoptive parents and adoptive grandparents.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/parent-relief-parent-relief-(disability)</sup>
- The dependant must have been 55 years of age or above.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/parent-relief-parent-relief-(disability)</sup>
- The dependant must not have had annual income of more than $8,000 in 2025. For YA 2024 and before, the threshold was $4,000.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/parent-relief-parent-relief-(disability)</sup>
- The dependant must have been living with the taxpayer in the same household in Singapore, or otherwise meet the alternative residence condition.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/parent-relief-parent-relief-(disability)</sup>
- Where the dependant did not live with the taxpayer, the relief applies only if the dependant stayed in Singapore for at least 8 months in 2025.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/parent-relief-parent-relief-(disability)</sup>
- Parent Relief is $9,000 per dependant where the taxpayer stays with the dependant, and $5,500 per dependant where they do not.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/parent-relief-parent-relief-(disability)</sup>
- Parent Relief (Disability) is $14,000 per dependant where the taxpayer stays with the dependant, and $10,000 per dependant where they do not.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/parent-relief-parent-relief-(disability)</sup>
- Parent Relief or Parent Relief (Disability) may be claimed for up to 2 dependants.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/parent-relief-parent-relief-(disability)</sup>
- Where more than one individual maintains the same dependant and each meets the qualifying conditions, the relief may be shared between the claimants.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/parent-relief-parent-relief-(disability)</sup>

## 3. Decision steps

1. **If** Asking how much relief they will get, or what their tax will be  
   -> Escalate (`amount_computation_requested`)
2. **If** Asking whether their own claim was allowed  
   -> Escalate (`account_specific`)
3. **If** Asking whether total reliefs are capped  
   -> Escalate (`no_supporting_sop`)
4. **If** Otherwise  
   -> State the qualifying conditions and the applicable rates from the key facts

## 4. Approved phrasing

**`conditions`**

> To claim Parent Relief you must have supported a dependant who was 55 years of age or above, who did not have annual income of more than $8,000 in 2025, and who was living with you in the same household in Singapore. If your dependant did not live with you, the relief applies only if they stayed in Singapore for at least 8 months in the year. Qualifying dependants include parents, grandparents, parents-in-law and grandparents-in-law, as well as step-parents and adoptive parents.

**`amounts`**

> Parent Relief is $9,000 per dependant if you stay with your dependant, and $5,500 if you do not. Parent Relief (Disability) is $14,000 per dependant if you stay with your dependant, and $10,000 if you do not.

**`number_and_sharing`**

> You may claim the relief for up to 2 dependants. If more than one person supports the same dependant and each meets the qualifying conditions, the relief may be shared between you.

## 5. Do not

- Do not compute a relief amount or the resulting tax.
- Do not confirm whether a specific claim has been allowed.
- Do not state the overall personal relief cap — escalate instead.
- Do not advise claimants on how to apportion a shared claim between themselves.

## 6. Related

- SOP-REL-005
- SOP-ASM-001
