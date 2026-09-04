---
synthetic: true
sop_id: SOP-INC-001
title: Rental income
version: "1.0"
effective_date: 2026-01-01
supersedes: null
applies_to_ya: [2025, 2026]
intents: [rental_income]
indexed: false
owner_queue: IIT-General
handling_target: 5_working_days
auto_reply_permitted: true
escalate_if:
  - account_specific
  - amount_computation_requested
references:
  - https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/what-is-taxable-what-is-not/income-from-property-rented-out
last_reviewed: 2026-09-01
---

# SOP-INC-001 - Rental income

> **SYNTHETIC DOCUMENT.** Written for this assessment from the public sources cited
> in section 2. It is not an IRAS document or internal procedure. See
> [data provenance](../SOURCES.md).

> **NOT INDEXED.** This SOP is excluded from runtime retrieval. See the
> [SOP schema and corpus design](../sop_specs/README.md).

## 1. Scope

Taxpayer asks whether rent received is taxable, when rental income must be declared, what expenses may be deducted, or how the simplified claim for rental expenses works.

**Not in scope:**
- The taxpayer's own declared rental figures or assessment. -> escalate (`account_specific`)
- Computing net rental income or tax for the taxpayer. -> escalate (`amount_computation_requested`)
- Property tax, which is a different tax type. -> escalate (`oos_redirect`)

## 2. Key facts the officer may state

- Rent payments received from renting out a property are subject to income tax and must be declared in the Income Tax Return.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/what-is-taxable-what-is-not/income-from-property-rented-out</sup>
- Net rental income, after deduction of allowable expenses, is subject to income tax.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/what-is-taxable-what-is-not/income-from-property-rented-out</sup>
- Rental income is taxable from the date it is due and payable to the property owner, not the date it is actually received. Rent due in 2025 but paid in 2026 is declared for Year of Assessment 2026.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/what-is-taxable-what-is-not/income-from-property-rented-out</sup>
- Any amount recovered from insurance on a property that is rented out is taxable and should be reported as part of income.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/what-is-taxable-what-is-not/income-from-property-rented-out</sup>
- Under the simplified claim for rental expenses for tenanted residential property, deemed rental expenses calculated as 15% of gross rent are pre-filled in the online tax form.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/what-is-taxable-what-is-not/income-from-property-rented-out</sup>
- In addition to the 15% deemed rental expenses, property owners may still claim mortgage interest on the loan taken to purchase the property.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/what-is-taxable-what-is-not/income-from-property-rented-out</sup>
- The amount of taxable rental income depends on whether the property is solely or jointly owned.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/what-is-taxable-what-is-not/income-from-property-rented-out</sup>

## 3. Decision steps

1. **If** Asking about their own declared rental figures or assessment  
   -> Escalate (`account_specific`)
2. **If** Asking IRAS to compute net rental income or tax  
   -> Escalate (`amount_computation_requested`)
3. **If** Asking about property tax rather than income tax on rent  
   -> Redirect (`oos_redirect`)
4. **If** Otherwise  
   -> State the treatment of rental income from the key facts

## 4. Approved phrasing

**`taxable`**

> Rent you receive from renting out your property is subject to income tax and must be declared in your Income Tax Return. It is the net rental income, after deducting allowable expenses, that is taxed.

**`timing`**

> Rental income is taxable from the date it is due and payable to you, rather than the date you actually receive it. For example, rent due to you in 2025 but paid in January 2026 is declared for Year of Assessment 2026.

**`simplified_expenses`**

> For tenanted residential property, a simplified claim is available: deemed rental expenses of 15% of your gross rent are pre-filled in the online tax form. You may still claim mortgage interest on the loan taken to purchase the property in addition to the 15%.

## 5. Do not

- Do not compute net rental income, allowable expenses or tax payable.
- Do not confirm a taxpayer's own declared figures.
- Do not advise whether the simplified claim or actual expenses is more advantageous for a particular taxpayer.
- Do not answer property tax questions from this procedure.

## 6. Related

- SOP-FIL-001
- SOP-RTE-002
