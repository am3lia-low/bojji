---
synthetic: true
sop_id: SOP-REL-003
title: CPF and SRS reliefs
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
  - https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/central-provident-fund(cpf)-relief-for-employees
  - https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/special-tax-schemes/srs-contributions
last_reviewed: 2026-09-01
---

# SOP-REL-003 - CPF and SRS reliefs

> **SYNTHETIC DOCUMENT.** Written for this assessment from the public sources cited
> in section 2. It is not an IRAS document or internal procedure. See
> [data provenance](../SOURCES.md).

## 1. Scope

Taxpayer asks which CPF contributions qualify for relief, which do not, how SRS contributions attract relief, or what the yearly SRS contribution caps are.

**Not in scope:**
- The amount of CPF or SRS relief this taxpayer will receive. -> escalate (`amount_computation_requested`)
- The taxpayer's own CPF contribution records or SRS account balance. -> escalate (`account_specific`)
- CPF scheme matters that are not tax relief — contribution rates, withdrawal rules, account balances. -> escalate (`oos_redirect`)
- Whether the total of all reliefs is limited. -> escalate (`tax_reliefs`)

## 2. Key facts the officer may state

- Compulsory employee CPF contributions under the CPF Act, or contributions to an approved pension or provident fund, qualify for CPF relief.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/central-provident-fund(cpf)-relief-for-employees</sup>
- Voluntary contributions to a MediSave Account qualify for CPF relief.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/central-provident-fund(cpf)-relief-for-employees</sup>
- Voluntary contributions made in excess of the compulsory contributions under the CPF Act are not eligible for relief.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/central-provident-fund(cpf)-relief-for-employees</sup>
- CPF contributions on additional wages that exceed the CPF cap on wages from related employers are not eligible for relief.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/central-provident-fund(cpf)-relief-for-employees</sup>
- CPF contributions made in respect of overseas employment are not eligible for relief.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/central-provident-fund(cpf)-relief-for-employees</sup>
- There is no refund for accepted voluntary CPF contributions, so a taxpayer should evaluate whether they would benefit from the relief before contributing.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-reliefs-rebates-and-deductions/tax-reliefs/central-provident-fund(cpf)-relief-for-employees</sup>
- The Supplementary Retirement Scheme is a voluntary scheme encouraging individuals to save for retirement over and above their CPF savings.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/special-tax-schemes/srs-contributions</sup>
- The yearly maximum SRS contribution is $15,300 for Singapore Citizens and Singapore Permanent Residents, and $35,700 for foreigners.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/special-tax-schemes/srs-contributions</sup>
- A foreigner must declare their foreigner status to the SRS bank operator yearly, so that the operator can calculate the maximum SRS contribution.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/special-tax-schemes/srs-contributions</sup>
- Opening SRS accounts with more than one SRS operator is an offence and a penalty may be imposed.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/special-tax-schemes/srs-contributions</sup>
- A taxpayer should check with their SRS bank operator for the cut-off date for SRS contributions.  
  <sup>Source: https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/special-tax-schemes/srs-contributions</sup>

## 3. Decision steps

1. **If** Asking how much CPF or SRS relief they will receive  
   -> Escalate (`amount_computation_requested`)
2. **If** Asking about their own contribution records or account balance  
   -> Escalate (`account_specific`)
3. **If** Asking about CPF contribution rates, withdrawals or balances rather than tax relief  
   -> Redirect to CPF Board (`oos_redirect`)
4. **If** Asking whether total reliefs are capped  
   -> Escalate (`no_supporting_sop`)
5. **If** Otherwise  
   -> State which contributions qualify, and the SRS caps, from the key facts

## 4. Approved phrasing

**`cpf_qualifying`**

> Compulsory employee CPF contributions made under the CPF Act, contributions to an approved pension or provident fund, and voluntary contributions to your MediSave Account qualify for CPF relief.

**`cpf_not_qualifying`**

> Voluntary contributions in excess of the compulsory contributions under the CPF Act do not qualify for relief. Neither do CPF contributions on additional wages exceeding the CPF wage cap from related employers, or contributions made in respect of overseas employment. Please note that accepted voluntary CPF contributions cannot be refunded.

**`srs_caps`**

> The Supplementary Retirement Scheme is a voluntary scheme for retirement savings over and above CPF. The yearly maximum contribution is $15,300 for Singapore Citizens and Permanent Residents, and $35,700 for foreigners. If you are a foreigner, you need to declare your status to your SRS operator each year so that they can calculate your contribution cap.

**`cpf_board_redirect`**

> Questions about CPF contribution rates, withdrawals or your account balance are handled by the CPF Board rather than IRAS. Please contact the CPF Board directly at cpf.gov.sg.

## 5. Do not

- Do not compute a relief amount or the resulting tax.
- Do not confirm a taxpayer's own contribution or account figures.
- Do not state the overall personal relief cap — escalate instead.
- Do not advise whether a voluntary contribution is financially worthwhile.
- Do not answer CPF scheme questions that belong to the CPF Board.

## 6. Related

- SOP-REL-005
- SOP-RTE-002
