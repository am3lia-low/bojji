---
synthetic: true
sop_id: SOP-FIL-001
title: Handling filing enquiries
version: "1.0"
effective_date: 2026-01-01
supersedes: null
applies_to_ya: [2025, 2026]
intents: [filing]
indexed: true
owner_queue: IIT-General
handling_target: 3_working_days
auto_reply_permitted: true
escalate_if:
  - account_specific
  - amount_computation_requested
  - hardship_or_waiver_request
  - scam_report
references:
  - https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/understanding-my-income-tax-filing/individuals-required-to-file-tax
  - https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/understanding-my-income-tax-filing/e-filing-your-income-tax-return
  - https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/understanding-my-income-tax-filing/filing-a-paper-income-tax-return
  - https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/understanding-my-income-tax-filing/late-filing-or-non-filing-of-individual-income-tax-returns-form-b1-b-p-m
last_reviewed: 2026-09-01
---

# SOP-FIL-001 - Handling filing enquiries

> **SYNTHETIC DOCUMENT.** Authored for a technical assessment. This is not an
> IRAS document and does not reflect IRAS internal material, templates or
> practice. Every factual claim is a restatement traceable to the public
> source cited beside it in section 2.

## 1. Scope

Taxpayer asks whether they must file, how to file, when filing is due, what the No-Filing Service means, how to obtain an extension, or what happens if they file late. Covers both e-filing and paper filing.

**Not in scope:**
- Whether this particular taxpayer has been selected for NFS, or whether their own return has been received. -> escalate (`account_specific`)
- Disputing the figures in a Notice of Assessment, including an estimated NOA. -> escalate (`assessment_and_amendment`)
- Requesting waiver of a composition amount or late-filing penalty. -> escalate (`hardship_or_waiver_request`)
- Filing obligations for a sole proprietorship, partnership or company. -> escalate (`oos_business_tax`)

## 2. Key facts the officer may state

- A taxpayer is generally required to file an Income Tax Return if, in the preceding calendar year, total income exceeded $22,000; or self-employment income produced a net profit exceeding $6,000; or they are a non-resident who derived income from Singapore.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/understanding-my-income-tax-filing/individuals-required-to-file-tax</sup>
- A taxpayer who receives a letter, form or SMS from IRAS informing them to file must file, regardless of how much they earned and regardless of whether their employer participates in the Auto-Inclusion Scheme (AIS).  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/understanding-my-income-tax-filing/individuals-required-to-file-tax</sup>
- Non-residents who derived income from Singapore in the preceding year must file regardless of the amount earned.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/understanding-my-income-tax-filing/individuals-required-to-file-tax</sup>
- The e-filing due date is 18 April each year.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/understanding-my-income-tax-filing/individuals-required-to-file-tax</sup>
- The paper filing due date is 15 April each year.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/understanding-my-income-tax-filing/filing-a-paper-income-tax-return</sup>
- An extension of up to 14 days may be granted, requested through the 'Apply for Extension of Time to File' digital service at myTax Portal.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/understanding-my-income-tax-filing/individuals-required-to-file-tax</sup>
- Under the No-Filing Service (NFS), a taxpayer who receives a letter or SMS informing them of selection is not required to file a return. They may log in to myTax Portal to verify the auto-included information, and may preview the tax bill from 1 March to 18 April.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/understanding-my-income-tax-filing/individuals-required-to-file-tax</sup>
- A taxpayer on NFS whose pre-filled information is inaccurate must file a return to correct it. No filing extension is available under NFS.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/understanding-my-income-tax-filing/individuals-required-to-file-tax</sup>
- Where a return was e-filed, it may be re-filed once, and re-filing must be done by 18 April. After that date, changes are made by amending the tax bill instead.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/understanding-my-income-tax-filing/individuals-required-to-file-tax</sup>
- Under Direct Notice of Assessment (D-NOA), some taxpayers receive a tax bill directly without being required to file.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/understanding-my-income-tax-filing/individuals-required-to-file-tax</sup>
- Failure to file an Income Tax Return by the due date is an offence.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/understanding-my-income-tax-filing/late-filing-or-non-filing-of-individual-income-tax-returns-form-b1-b-p-m</sup>
- Where a return is not filed on time, IRAS may issue an estimated Notice of Assessment, offer to compound the offence, or issue a Notice to Attend Court / Summons.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/understanding-my-income-tax-filing/late-filing-or-non-filing-of-individual-income-tax-returns-form-b1-b-p-m</sup>
- Tax under an estimated Notice of Assessment must be paid within 1 month of the date of the Notice, even if the taxpayer intends to object or is awaiting the outcome of an objection.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/understanding-my-income-tax-filing/late-filing-or-non-filing-of-individual-income-tax-returns-form-b1-b-p-m</sup>
- A composition amount of up to $5,000 per offence may be offered instead of prosecution, depending on past compliance records.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/understanding-my-income-tax-filing/late-filing-or-non-filing-of-individual-income-tax-returns-form-b1-b-p-m</sup>
- Where an estimated assessment has been raised, the taxpayer should file the outstanding return immediately for review; any excess tax paid is refunded.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/understanding-my-income-tax-filing/late-filing-or-non-filing-of-individual-income-tax-returns-form-b1-b-p-m</sup>

## 3. Decision steps

1. **If** Asking whether IRAS has received *their* return, or whether *they* were selected for NFS  
   -> Escalate (`account_specific`)
2. **If** Asking IRAS to compute their tax, or to confirm an amount payable  
   -> Escalate (`amount_computation_requested`)
3. **If** Asking for a composition amount or late-filing penalty to be waived or reduced  
   -> Escalate (`hardship_or_waiver_request`)
4. **If** Disputing figures in a Notice of Assessment rather than asking how to file  
   -> Route to SOP-ASM-001 (`tie_break_objection_belongs_to_assessment`)
5. **If** Filing obligations of a business, partnership or company  
   -> Redirect (`oos_business_tax`)
6. **If** Otherwise  
   -> Answer from the key facts and direct to myTax Portal

## 4. Approved phrasing

**`who_must_file`**

> You are generally required to file an Income Tax Return if your total income for the preceding calendar year was more than $22,000, or if your self-employment income produced a net profit of more than $6,000, or if you are a non-resident who derived income from Singapore. If you have received a letter, form or SMS from IRAS asking you to file, you must file regardless of the amount you earned.

**`due_dates`**

> The filing deadline is 18 April each year for e-filing, and 15 April for paper returns. You can file at myTax Portal using your Singpass.

**`nfs`**

> If you have been informed that you are on the No-Filing Service, you are not required to file a return. You may log in to myTax Portal to check that the auto-included information is correct, and you can preview your tax bill between 1 March and 18 April. If any of the pre-filled information is inaccurate, please file a return to correct it.

**`extension`**

> If you need more time, an extension of up to 14 days may be granted through the 'Apply for Extension of Time to File' digital service at myTax Portal.

**`late_filing`**

> Filing after the due date is an offence. Where a return is outstanding, IRAS may issue an estimated Notice of Assessment, offer to compound the offence for up to $5,000, or issue a Notice to Attend Court. If you have received an estimated Notice of Assessment, please file the outstanding return as soon as possible so that the assessment can be reviewed; any excess tax paid will be refunded.

## 5. Do not

- Do not confirm whether a specific return has been received or processed.
- Do not state whether a specific taxpayer is on NFS or has a D-NOA.
- Do not compute tax payable, or estimate what a composition amount will be.
- Do not advise that a deadline can be missed without consequence.
- Do not comment on the merits of an objection — that is SOP-ASM-001.

## 6. Related

- SOP-ASM-001
- SOP-PAY-002
- SOP-RTE-001
