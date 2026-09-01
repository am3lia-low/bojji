---
synthetic: true
sop_id: SOP-RTE-002
title: "Redirect: other agencies and other tax types"
version: "1.0"
effective_date: 2026-01-01
supersedes: null
applies_to_ya: [2025, 2026]
intents: [oos_other_agency]
indexed: true
owner_queue: IIT-General
handling_target: same_day
auto_reply_permitted: true
escalate_if:
  - account_specific
  - scam_report
references:
  - https://www.iras.gov.sg/taxes/individual-income-tax/employers/tax-clearance-for-foreign-spr-employees-(ir21)
  - https://www.iras.gov.sg/contact-us/individual-income-tax
last_reviewed: 2026-09-01
---

# SOP-RTE-002 - Redirect: other agencies and other tax types

> **SYNTHETIC DOCUMENT.** Authored for a technical assessment. This is not an
> IRAS document and does not reflect IRAS internal material, templates or
> practice. Every factual claim is a restatement traceable to the public
> source cited beside it in section 2.

## 1. Scope

Enquiry belongs to another IRAS tax type — GST, property tax, stamp duty, withholding tax, or tax clearance for a departing foreign employee — or to another agency entirely, such as the CPF Board, the Ministry of Manpower, or ACRA.

**Not in scope:**
- Tax relief on CPF or SRS contributions, which is an individual income tax matter. -> escalate (`tax_reliefs`)
- Business or corporate income tax. -> escalate (`oos_business_tax`)
- Reporting a suspected IRAS impersonation scam. -> escalate (`scam_report`)

## 2. Key facts the officer may state

- Tax clearance for foreign and Singapore Permanent Resident employees who are ceasing employment or leaving Singapore is handled through the Form IR21 process, which is an employer obligation.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/employers/tax-clearance-for-foreign-spr-employees-(ir21)</sup>
- IRAS administers several distinct tax types — individual income tax, corporate income tax, GST, property tax and stamp duty — each with its own guidance and contact channels.  
  <sup>Source: https://www.iras.gov.sg/contact-us/individual-income-tax</sup>
- Enquiries about CPF contribution rates, account balances and withdrawals are matters for the CPF Board rather than IRAS. IRAS administers only the tax relief arising from qualifying CPF contributions.  
  <sup>Source: https://www.iras.gov.sg/contact-us/individual-income-tax</sup>

## 3. Decision steps

1. **If** The enquiry concerns tax clearance or Form IR21  
   -> Redirect to the tax clearance guidance and note it is an employer obligation
2. **If** The enquiry concerns CPF contributions, balances or withdrawals  
   -> Redirect to the CPF Board
3. **If** The enquiry concerns GST, property tax, stamp duty or withholding tax  
   -> Redirect to the guidance for that tax type
4. **If** The enquiry concerns employment disputes, work passes or company registration  
   -> Redirect to MOM or ACRA as applicable
5. **If** The enquiry reports an IRAS impersonation  
   -> Escalate (`scam_report`)
6. **If** The enquiry concerns a specific taxpayer's own record in another tax type  
   -> Escalate (`account_specific`)
7. **If** Never  
   -> Do not answer another agency's or another tax type's question from IIT knowledge

## 4. Approved phrasing

**`cpf_redirect`**

> Your enquiry relates to CPF contributions, which are administered by the CPF Board rather than IRAS. IRAS handles only the income tax relief arising from qualifying CPF contributions. For questions about contribution rates, your account balance or withdrawals, please contact the CPF Board at cpf.gov.sg.

**`tax_clearance_redirect`**

> Your enquiry relates to tax clearance for an employee who is ceasing employment or leaving Singapore. This is handled through the Form IR21 process, which is an obligation on the employer. Guidance is available at iras.gov.sg under tax clearance for foreign and Singapore Permanent Resident employees.

**`other_tax_type_redirect`**

> Your enquiry relates to a tax type other than individual income tax. IRAS administers each tax type separately, with its own guidance and contact channels, which you can find at iras.gov.sg.

**`other_agency_redirect`**

> Your enquiry is handled by another agency rather than IRAS. Employment matters and work passes are handled by the Ministry of Manpower at mom.gov.sg, and company registration by ACRA at acra.gov.sg.

## 5. Do not

- Do not answer another tax type's or another agency's question from individual income tax knowledge.
- Do not state GST rates, property tax rates or stamp duty rates from this procedure.
- Do not conflate CPF relief (IRAS) with CPF contributions (CPF Board).
- Do not leave the citizen without a destination — always name where to go.

## 6. Related

- SOP-RTE-001
- SOP-REL-003
- SOP-ESC-003
