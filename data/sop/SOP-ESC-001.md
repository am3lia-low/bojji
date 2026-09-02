---
synthetic: true
sop_id: SOP-ESC-001
title: Account-specific enquiries
version: "1.0"
effective_date: 2026-01-01
supersedes: null
applies_to_ya: [2025, 2026]
intents: []
indexed: true
reachable_via: account_specific_flag
owner_queue: IIT-General
handling_target: 3_working_days
auto_reply_permitted: false
escalate_if:
  - account_specific
references:
  - https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/receive-tax-bill-pay-tax-check-refunds/getting-my-tax-assessment
  - https://www.iras.gov.sg/contact-us/individual-income-tax
last_reviewed: 2026-09-01
---

# SOP-ESC-001 - Account-specific enquiries

> **SYNTHETIC DOCUMENT.** Authored for a technical assessment. This is not an
> IRAS document and does not reflect IRAS internal material, templates or
> practice. Every factual claim is a restatement traceable to the public
> source cited beside it in section 2.

## 1. Scope

Any enquiry whose answer requires looking up a specific taxpayer's record: the content of their own assessment, the status of their own refund, payment, objection or GIRO plan, whether their return was received, or what a figure on their own tax bill represents.

**This SOP declares no intent, and no class routes to it.** Being account-specific is a property an enquiry *has*, not a topic it is *about*: the same question about an instalment plan is account-specific when it asks after the sender's own arrangement and generic when it asks how instalments work. A classifier cannot separate those from the text, because the text is nearly identical — so the condition is detected by the `account_specific` flag and escalated by the router before any confidence is consulted, and this document is what the officer receives.

**Not in scope:**
- Generic questions about how a procedure works, with no reference to the taxpayer's own record. -> escalate (`filing / payment / assessment_and_amendment / residency / tax_reliefs`)

## 2. Key facts the officer may state

- All IRAS notices and letters to taxpayers are deposited in myTax Portal at mytax.iras.gov.sg, which taxpayers access using Singpass authentication.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/receive-tax-bill-pay-tax-check-refunds/getting-my-tax-assessment</sup>
- Taxpayers who have updated their mobile number or email address are informed by SMS or email to log in to myTax Portal to view their notices or letters.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/receive-tax-bill-pay-tax-check-refunds/getting-my-tax-assessment</sup>
- A taxpayer may view their own assessment, payment and GIRO details through the digital services at myTax Portal.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/receive-tax-bill-pay-tax-check-refunds/getting-my-tax-assessment</sup>

## 3. Decision steps

1. **If** The enquiry refers to the taxpayer's own record in any way  
   -> Escalate (`requires_account_lookup`)
2. **If** Always  
   -> Escalate — this class never auto-replies

## 4. Approved phrasing

**`acknowledgement`**

> Thank you for writing in. Your enquiry relates to your own tax records, so it has been passed to an officer who will review your account and reply to you directly. In the meantime, you may be able to view your notices, assessments and payment details by logging in to myTax Portal at mytax.iras.gov.sg with your Singpass.

## 5. Do not

- Do not state, confirm or speculate about any figure, date or status on a specific taxpayer's record.
- Do not guess why a payment, refund or deduction did or did not occur.
- Do not auto-reply with substantive content — acknowledge and escalate only.
- Do not ask the taxpayer to send an NRIC or other identifiers by email.

## 6. Related

- SOP-ESC-002
- SOP-PAY-001
- SOP-ASM-001
