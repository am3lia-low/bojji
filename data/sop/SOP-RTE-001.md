---
synthetic: true
sop_id: SOP-RTE-001
title: "Redirect: business and corporate income tax"
version: "1.0"
effective_date: 2026-01-01
supersedes: null
applies_to_ya: [2025, 2026]
intents: [oos_redirect]
indexed: true
owner_queue: IIT-General
handling_target: same_day
auto_reply_permitted: true
escalate_if:
  - account_specific
  - amount_computation_requested
references:
  - https://www.iras.gov.sg/taxes/individual-income-tax/self-employed-and-partnerships
  - https://www.iras.gov.sg/taxes/corporate-income-tax
last_reviewed: 2026-09-01
---

# SOP-RTE-001 - Redirect: business and corporate income tax

> **SYNTHETIC DOCUMENT.** Written for this assessment from the public sources cited
> in section 2. It is not an IRAS document or internal procedure. See
> [data provenance](../SOURCES.md).

## 1. Scope

Enquiry concerns the tax affairs of a business rather than an individual's employment income: sole proprietorship or partnership trade income, filing Form B or Form P, corporate income tax, Form C-S or Form C, or business expenses and capital allowances.

**Not in scope:**
- An individual's own employment income, reliefs, assessment or payment. -> escalate (`filing / tax_reliefs / assessment_and_amendment / payment`)
- GST, property tax, stamp duty, or another agency entirely. -> escalate (`oos_redirect`)

## 2. Key facts the officer may state

- Self-employed persons and partners have distinct tax obligations covering trade income, record keeping, and the calculation of business income, set out in the IRAS guidance for the self-employed and partnerships.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/self-employed-and-partnerships</sup>
- Corporate income tax is a separate tax type with its own filing obligations, including Form C-S, Form C-S (Lite) and Form C.  
  <sup>Source: https://www.iras.gov.sg/taxes/corporate-income-tax</sup>
- A sole proprietor or partner declares business income in their individual Income Tax Return, but the computation of that business income follows the self-employed guidance rather than the employment income rules.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/self-employed-and-partnerships</sup>

## 3. Decision steps

1. **If** The enquiry concerns a company's tax affairs  
   -> Redirect to the corporate income tax guidance
2. **If** The enquiry concerns sole proprietorship or partnership trade income  
   -> Redirect to the self-employed and partnerships guidance
3. **If** The enquiry asks IRAS to compute business income or tax  
   -> Escalate (`amount_computation_requested`)
4. **If** The enquiry concerns a specific business's own records or filings  
   -> Escalate (`account_specific`)
5. **If** Never  
   -> Do not answer a business tax question from individual income tax knowledge

## 4. Approved phrasing

**`corporate_redirect`**

> Your enquiry relates to corporate income tax, which is handled separately from individual income tax. Guidance on company filing obligations, including Form C-S and Form C, is available at iras.gov.sg/taxes/corporate-income-tax.

**`self_employed_redirect`**

> Your enquiry relates to income from a sole proprietorship or partnership. While business income is declared in your individual Income Tax Return, it is computed under separate rules. Guidance for self-employed persons and partners, including record keeping and calculating business income, is available at iras.gov.sg/taxes/individual-income-tax/self-employed-and-partnerships.

## 5. Do not

- Do not answer a business or corporate tax question using individual income tax rules — redirect instead.
- Do not state corporate tax rates, deadlines or thresholds from this procedure.
- Do not compute business income, capital allowances or corporate tax.
- Do not treat the redirect as a refusal — it is the correct outcome, and the citizen must be told exactly where to go.

## 6. Related

- SOP-RTE-002
- SOP-FIL-001
