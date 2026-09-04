---
synthetic: true
sop_id: SOP-ESC-003
title: Scam and impersonation reports
version: "1.0"
effective_date: 2026-01-01
supersedes: null
applies_to_ya: [2025, 2026]
intents: [scam_report]
indexed: true
owner_queue: IIT-Integrity
handling_target: same_day
auto_reply_permitted: false
escalate_if:
  - scam_report
  - account_specific
references:
  - https://www.iras.gov.sg/news-events/announcements/scam-advisory/phishing-email-scam
  - https://www.iras.gov.sg/news-events/announcements/scam-advisory/tax-refund-scam
last_reviewed: 2026-09-01
---

# SOP-ESC-003 - Scam and impersonation reports

> **SYNTHETIC DOCUMENT.** Written for this assessment from the public sources cited
> in section 2. It is not an IRAS document or internal procedure. See
> [data provenance](../SOURCES.md).

## 1. Scope

Taxpayer reports a suspicious email, SMS, WhatsApp message, call or website purporting to be from IRAS; asks whether a message they received is genuine; or reports that they have already responded to one, disclosed information or made a payment.

**Not in scope:**
- Reporting suspected tax evasion by another person. -> escalate (`oos_redirect`)
- A genuine IRAS notice the taxpayer disputes. -> escalate (`assessment_and_amendment`)

## 2. Key facts the officer may state

- All IRAS correspondence on confidential tax matters is done through myTax Portal, and all notices and letters are deposited at mytax.iras.gov.sg.  
  <sup>Source: https://www.iras.gov.sg/news-events/announcements/scam-advisory/phishing-email-scam</sup>
- Taxpayers will never receive confidential tax information or tax documents such as tax returns, notices of assessment or tax refund letters by email or SMS.  
  <sup>Source: https://www.iras.gov.sg/news-events/announcements/scam-advisory/phishing-email-scam</sup>
- myTax Portal is a secured, personalised portal that taxpayers access using Singpass authentication.  
  <sup>Source: https://www.iras.gov.sg/news-events/announcements/scam-advisory/phishing-email-scam</sup>
- Taxpayers who have updated their mobile number or email address are notified by SMS or email to log in to myTax Portal to view notices or letters, rather than receiving the documents themselves.  
  <sup>Source: https://www.iras.gov.sg/news-events/announcements/scam-advisory/phishing-email-scam</sup>
- In tax refund and payout scams, unsolicited emails purporting to be from IRAS state that the recipient is eligible for a refund, and link to a phishing website imitating the IRAS website that asks them to select a refund method using debit or credit card details.  
  <sup>Source: https://www.iras.gov.sg/news-events/announcements/scam-advisory/tax-refund-scam</sup>

## 3. Decision steps

1. **If** The enquiry reports or asks about a suspected IRAS impersonation  
   -> Escalate (`high_consequence`)
2. **If** The taxpayer indicates they have already disclosed details or paid  
   -> Escalate with priority (`high_consequence`)
3. **If** Always  
   -> Escalate — this class never auto-replies

## 4. Approved phrasing

**`acknowledgement`**

> Thank you for alerting us. Your report has been passed to an officer who will follow up with you directly. It may help to know that IRAS conducts all correspondence on confidential tax matters through myTax Portal at mytax.iras.gov.sg, which is accessed using Singpass. IRAS will never send you confidential tax documents such as tax returns, notices of assessment or refund letters by email or SMS, and will never ask for your card details in order to pay you a refund. If you have already provided any information or made a payment, please contact your bank immediately and report the matter to the police.

## 5. Do not

- Do not confirm or deny that a specific message, sender address or website is genuine — an officer must verify this.
- Do not ask the taxpayer to forward attachments or click any link to check it.
- Do not request Singpass credentials, card details or an NRIC by email.
- Do not auto-reply in a way that reads as routine correspondence — this is time-sensitive.

## 6. Related

- SOP-ESC-001
- SOP-PAY-002
