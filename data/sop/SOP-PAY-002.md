---
synthetic: true
sop_id: SOP-PAY-002
title: Payment channels, late-payment penalties and refunds
version: "1.0"
effective_date: 2026-01-01
supersedes: null
applies_to_ya: [2025, 2026]
intents: [payment]
indexed: true
owner_queue: IIT-Payments
handling_target: same_day
auto_reply_permitted: true
escalate_if:
  - account_specific
  - hardship_or_waiver_request
  - amount_computation_requested
  - scam_report
references:
  - https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/receive-tax-bill-pay-tax-check-refunds/late-payment-or-non-payment-of-individual-income-tax
  - https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/receive-tax-bill-pay-tax-check-refunds/how-to-pay
  - https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/receive-tax-bill-pay-tax-check-refunds/refunds
last_reviewed: 2026-09-01
---

# SOP-PAY-002 - Payment channels, late-payment penalties and refunds

> **SYNTHETIC DOCUMENT.** Authored for a technical assessment. This is not an
> IRAS document and does not reflect IRAS internal material, templates or
> practice. Every factual claim is a restatement traceable to the public
> source cited beside it in section 2.

## 1. Scope

Taxpayer asks when tax is due, how to pay, what penalties apply to late payment, what recovery action IRAS may take, or how and when refunds are made.

**Not in scope:**
- The taxpayer's own outstanding balance, penalty imposed, or refund status. -> escalate (`account_specific`)
- Asking for a penalty to be waived, or stating they cannot pay. -> escalate (`hardship_or_waiver_request`)
- Calculating a penalty or a balance for the taxpayer. -> escalate (`amount_computation_requested`)

## 2. Key facts the officer may state

- The payment due date is 1 month from the date of the Notice of Assessment (tax bill).  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/receive-tax-bill-pay-tax-check-refunds/late-payment-or-non-payment-of-individual-income-tax</sup>
- Unless the taxpayer is on an approved instalment plan, a 5% late payment penalty is imposed on unpaid tax where full payment is not received by the due date.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/receive-tax-bill-pay-tax-check-refunds/late-payment-or-non-payment-of-individual-income-tax</sup>
- If tax remains unpaid 60 days after the 5% late payment penalty is imposed, an additional penalty of 1% per month may be imposed for every completed month the tax remains unpaid, up to a maximum of 12% of the unpaid tax.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/receive-tax-bill-pay-tax-check-refunds/late-payment-or-non-payment-of-individual-income-tax</sup>
- Where tax is unpaid, IRAS may appoint agents — such as the taxpayer's bank, employer, tenant, or a lawyer handling the sale of their property — to recover the overdue tax.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/receive-tax-bill-pay-tax-check-refunds/late-payment-or-non-payment-of-individual-income-tax</sup>
- Where an assessment is revised downward, the late payment penalty is recalculated on the revised tax and any excess penalty is refunded.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/receive-tax-bill-pay-tax-check-refunds/late-payment-or-non-payment-of-individual-income-tax</sup>
- IRAS automatically refunds tax credits and pays interest on credits not refunded within 30 days from the date the tax credit arises.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/receive-tax-bill-pay-tax-check-refunds/refunds</sup>
- Tax credits are refunded through GIRO, PayNow or Telegraphic Transfer.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/receive-tax-bill-pay-tax-check-refunds/refunds</sup>
- IRAS has fully transitioned to electronic tax refunds and no longer issues cheques from 1 January 2026.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/receive-tax-bill-pay-tax-check-refunds/refunds</sup>
- A taxpayer leaving Singapore who wishes to receive a refund before departure should maintain an active local SGD bank account registered for PayNow, and complete the steps at least 30 days prior to departure.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/receive-tax-bill-pay-tax-check-refunds/refunds</sup>

## 3. Decision steps

1. **If** Asking about their own balance, their own penalty, or where their refund is  
   -> Escalate (`account_specific`)
2. **If** Stating they cannot pay, or asking for a penalty to be waived or reduced  
   -> Escalate (`hardship_or_waiver_request`)
3. **If** Asking how much penalty they owe, or to compute a balance or refund  
   -> Escalate (`amount_computation_requested`)
4. **If** Otherwise  
   -> State the rule from the key facts without applying it to their figures

## 4. Approved phrasing

**`due_date`**

> Tax is due 1 month from the date of your Notice of Assessment.

**`late_penalty`**

> Unless you are on an approved instalment plan, a 5% late payment penalty is imposed on tax that is not paid in full by the due date. If the tax remains unpaid 60 days after that penalty is imposed, an additional penalty of 1% per month may be imposed for each completed month the tax remains unpaid, up to a maximum of 12% of the unpaid tax.

**`recovery`**

> Where tax remains unpaid, IRAS may appoint agents such as your bank, employer or tenant to recover the overdue amount.

**`refunds`**

> Tax credits are refunded automatically, through GIRO, PayNow or Telegraphic Transfer. Interest is paid on credits that are not refunded within 30 days of the date the credit arises. From 1 January 2026 IRAS no longer issues cheques, so please ensure your PayNow or GIRO details are up to date.

## 5. Do not

- Do not calculate a penalty, a balance, or a refund amount for the taxpayer.
- Do not confirm whether a payment or refund has been received or processed.
- Do not indicate whether a penalty will be waived — that is SOP-ESC-002.
- Do not state a refund date for a specific taxpayer.

## 6. Related

- SOP-PAY-001
- SOP-ESC-002
- SOP-ASM-001
