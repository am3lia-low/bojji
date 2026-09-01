---
synthetic: true
sop_id: SOP-RES-001
title: Handling residency enquiries
version: "1.0"
effective_date: 2026-01-01
supersedes: null
applies_to_ya: [2025, 2026]
intents: [residency]
indexed: true
owner_queue: IIT-General
handling_target: 5_working_days
auto_reply_permitted: true
escalate_if:
  - account_specific
  - amount_computation_requested
  - foreign_income_dta
references:
  - https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-residency-and-tax-rates/individual-income-tax-rates
  - https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-residency-and-tax-rates/apply-for-certificate-of-residence
last_reviewed: 2026-09-01
---

# SOP-RES-001 - Handling residency enquiries

> **SYNTHETIC DOCUMENT.** Authored for a technical assessment. This is not an
> IRAS document and does not reflect IRAS internal material, templates or
> practice. Every factual claim is a restatement traceable to the public
> source cited beside it in section 2.

## 1. Scope

Taxpayer asks whether they are a tax resident, how the residency test works, how non-residents are taxed, or how to obtain a Certificate of Residence.

**Not in scope:**
- Confirming this particular taxpayer's residency status for a given YA. -> escalate (`account_specific`)
- Whether specific foreign income is taxable, or how DTA relief applies to it. -> escalate (`foreign_income_dta`)
- Computing tax at resident or non-resident rates for the taxpayer. -> escalate (`amount_computation_requested`)
- Tax clearance for a departing foreign employee (Form IR21). -> escalate (`oos_other_agency`)

## 2. Key facts the officer may state

- An individual is treated as a tax resident for a Year of Assessment if they are a Singapore Citizen or Singapore Permanent Resident who resides in Singapore except for temporary absences.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-residency-and-tax-rates/individual-income-tax-rates</sup>
- A foreigner is treated as a tax resident if they have stayed or worked in Singapore for at least 183 days in the previous calendar year.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-residency-and-tax-rates/individual-income-tax-rates</sup>
- A foreigner is also treated as a tax resident if they have stayed or worked in Singapore continuously for 3 consecutive years, even if the period of stay was less than 183 days in the first and/or third year.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-residency-and-tax-rates/individual-income-tax-rates</sup>
- A foreigner who has worked in Singapore for a continuous period straddling 2 calendar years, with a total period of stay of at least 183 days, is treated as a tax resident. This applies to employees who entered Singapore but excludes company directors, public entertainers and professionals.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-residency-and-tax-rates/individual-income-tax-rates</sup>
- An individual who does not meet the residency conditions is treated as a non-resident for tax purposes.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-residency-and-tax-rates/individual-income-tax-rates</sup>
- Resident tax rates are progressive; the current highest personal income tax rate is 24%.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-residency-and-tax-rates/individual-income-tax-rates</sup>
- Employment income of a non-resident individual is taxed at a flat rate of 15%, or at the progressive resident rates, whichever produces the higher tax amount.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-residency-and-tax-rates/individual-income-tax-rates</sup>
- The tax rate for non-resident individuals on director's fees, consultation fees and all other income is currently 24%. This applies to all income including rental income, pension and director's fees, except employment income and certain income taxable at reduced withholding rates.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-residency-and-tax-rates/individual-income-tax-rates</sup>
- Before YA 2024 the rate for non-resident individuals was 22%, except on employment income.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-residency-and-tax-rates/individual-income-tax-rates</sup>
- A Certificate of Residence (COR) is a letter certifying that the taxpayer is a tax resident in Singapore, for the purpose of claiming benefits under Avoidance of Double Taxation Agreements.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-residency-and-tax-rates/apply-for-certificate-of-residence</sup>
- A COR must be submitted to the foreign tax authority to prove Singapore tax residency; non-tax-residents do not enjoy DTA benefits.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-residency-and-tax-rates/apply-for-certificate-of-residence</sup>
- A COR application is processed in 2 to 3 weeks.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-residency-and-tax-rates/apply-for-certificate-of-residence</sup>
- Where notification preferences are set to digital notices, the taxpayer is notified by SMS and/or email when the certification letter is ready for viewing at myTax Portal.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-residency-and-tax-rates/apply-for-certificate-of-residence</sup>

## 3. Decision steps

1. **If** Asking IRAS to confirm their own residency status for a given year  
   -> Escalate (`account_specific`)
2. **If** Asking whether particular foreign income is taxable, or how DTA relief applies  
   -> Escalate (`foreign_income_dta`)
3. **If** Asking IRAS to compute tax at resident or non-resident rates  
   -> Escalate (`amount_computation_requested`)
4. **If** Asking about tax clearance for a departing employee  
   -> Redirect (`oos_other_agency`)
5. **If** Otherwise  
   -> State the residency test or the COR procedure from the key facts

## 4. Approved phrasing

**`residency_test`**

> You will be treated as a tax resident for a Year of Assessment if you are a Singapore Citizen or Permanent Resident residing in Singapore apart from temporary absences, or if you are a foreigner who has stayed or worked in Singapore for at least 183 days in the previous calendar year. You are also treated as a tax resident if you have stayed or worked here continuously for 3 consecutive years, or worked here for a continuous period straddling 2 calendar years with a total stay of at least 183 days. If you do not meet these conditions you are treated as a non-resident for tax purposes.

**`non_resident_rates`**

> Employment income of a non-resident is taxed at a flat rate of 15% or at the progressive resident rates, whichever gives the higher amount of tax. Other income, including director's fees, consultation fees, rental income and pension, is taxed at 24%.

**`cor`**

> A Certificate of Residence certifies that you are a Singapore tax resident, so that you can claim benefits under an Avoidance of Double Taxation Agreement with a foreign jurisdiction. Applications are processed in 2 to 3 weeks, and you will be notified when the letter is ready for viewing at myTax Portal.

## 5. Do not

- Do not confirm a specific taxpayer's residency status.
- Do not count a specific taxpayer's days of presence for them.
- Do not compute tax at either resident or non-resident rates.
- Do not advise on whether particular foreign income is taxable, or on how DTA relief applies — escalate instead.

## 6. Related

- SOP-INC-002
- SOP-RTE-002
- SOP-FIL-001
