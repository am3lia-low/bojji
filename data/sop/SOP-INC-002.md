---
synthetic: true
sop_id: SOP-INC-002
title: Foreign income and DTA relief
version: "1.0"
effective_date: 2026-01-01
supersedes: null
applies_to_ya: [2025, 2026]
intents: [foreign_income_dta]
indexed: false
owner_queue: IIT-General
handling_target: 5_working_days
auto_reply_permitted: true
escalate_if:
  - account_specific
  - amount_computation_requested
references:
  - https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/what-is-taxable-what-is-not/income-received-from-overseas
  - https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-residency-and-tax-rates/claiming-exemptions-under-Avoidance-of-Double-Taxation-Agreements-(DTAs)
last_reviewed: 2026-09-01
---

# SOP-INC-002 - Foreign income and DTA relief

> **SYNTHETIC DOCUMENT.** Written for this assessment from the public sources cited
> in section 2. It is not an IRAS document or internal procedure. See
> [data provenance](../SOURCES.md).

> **NOT INDEXED.** This SOP is excluded from runtime retrieval. See the
> [SOP schema and corpus design](../sop_specs/README.md).

## 1. Scope

Taxpayer asks whether income earned or received from overseas is taxable in Singapore, whether it must be declared, or how relief under an Avoidance of Double Taxation Agreement applies.

**Not in scope:**
- The taxpayer's own foreign income figures or assessment. -> escalate (`account_specific`)
- Computing tax or foreign tax credit for the taxpayer. -> escalate (`amount_computation_requested`)
- How to obtain a Certificate of Residence, and the residency test itself. -> escalate (`residency`)

## 2. Key facts the officer may state

- Generally, overseas income received in Singapore, including overseas income deposited into a Singapore bank account, is not taxable, and overseas income that is not taxable does not need to be declared.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/what-is-taxable-what-is-not/income-received-from-overseas</sup>
- Overseas income is taxable in Singapore if it is received through partnerships based in Singapore.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/what-is-taxable-what-is-not/income-received-from-overseas</sup>
- Overseas income is taxable in Singapore if the overseas employment is incidental to the taxpayer's Singapore employment, such as where they travel abroad as part of their job.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/what-is-taxable-what-is-not/income-received-from-overseas</sup>
- Overseas income is taxable in Singapore where the taxpayer works in Singapore for a foreign employer.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/what-is-taxable-what-is-not/income-received-from-overseas</sup>
- Overseas income is taxable in Singapore where the taxpayer is employed overseas on behalf of the Singapore Government.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/what-is-taxable-what-is-not/income-received-from-overseas</sup>
- A Double Taxation Agreement is an agreement between Singapore and another jurisdiction that relieves double taxation of income earned in one jurisdiction by a resident of the other.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-residency-and-tax-rates/claiming-exemptions-under-Avoidance-of-Double-Taxation-Agreements-(DTAs)</sup>
- Under a DTA, jurisdictions may provide tax credits or exemptions to Singapore tax residents on income derived from their jurisdictions. Non-residents do not enjoy these benefits.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-residency-and-tax-rates/claiming-exemptions-under-Avoidance-of-Double-Taxation-Agreements-(DTAs)</sup>

## 3. Decision steps

1. **If** Asking about their own foreign income figures or assessment  
   -> Escalate (`account_specific`)
2. **If** Asking IRAS to compute tax or a foreign tax credit  
   -> Escalate (`amount_computation_requested`)
3. **If** Asking only how to obtain a Certificate of Residence or about the residency test  
   -> Route to SOP-RES-001
4. **If** Otherwise  
   -> State the treatment of overseas income from the key facts

## 4. Approved phrasing

**`general_rule`**

> Generally, overseas income received in Singapore, including income deposited into a Singapore bank account, is not taxable, and you do not need to declare overseas income that is not taxable.

**`exceptions`**

> Overseas income is taxable in Singapore in certain cases: where it is received through a partnership based in Singapore; where your overseas employment is incidental to your Singapore employment, such as travelling abroad as part of your job; where you work in Singapore for a foreign employer; or where you are employed overseas on behalf of the Singapore Government.

**`dta`**

> A Double Taxation Agreement between Singapore and another jurisdiction relieves the double taxation of income earned in one jurisdiction by a resident of the other, and may provide a tax credit or exemption. These benefits are available to Singapore tax residents.

## 5. Do not

- Do not determine whether a particular taxpayer's foreign income is taxable — the exceptions turn on facts only an officer can establish.
- Do not compute tax, foreign tax credit or relief amounts.
- Do not interpret the terms of a specific Double Taxation Agreement.
- Do not advise on the tax treatment in the foreign jurisdiction.

## 6. Related

- SOP-RES-001
- SOP-FIL-001
