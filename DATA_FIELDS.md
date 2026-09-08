# Problem A Fixture Data Field Guide

This document describes the Problem A fixture-data fields.
It is derived from the teacher-supplied `data_dictionary.json`.

## `data_A/claims.json`

| Field | Type | Meaning | Example |
|---|---|---|---|
| `claim_id` | `str` | Unique id for this claim. **Not** how a duplicate is detected — a resubmission arrives with a new one. | `"CLM-8842"` |
| `member_id` | `str` | Who was treated. Join to `members.json` to reach their policy. | `"M-2214"` |
| `hospital_id` | `str` | Where they were treated. Join to `hospitals.json` for panel status. | `"H-114"` |
| `date_of_service` | `str` | When treatment happened. Tested against the policy's start/end dates and against any pre-authorisation window. | `"2026-09-02"` |
| `narrative` | `str` | Free text written by the member. Useful context — and the one field on this row an outsider controls, so treat it as untrusted input. | `"Admitted for appendix removal. Surgeon als…` |
| `documents` | `list[str]` | Documents actually attached to this claim. Compare against `required_documents.json` for the procedures claimed. | `["itemised_bill", "discharge_summary"]` |
| `lines` | `list[{code, amount}]` | **One entry per procedure claimed** — each with a `code` and the `amount` in dollars. Most claims have one line; several have three or four, and every line must be decided separately. | `[{"code": "47120", "amount": 1400}, {"code"…` |

## `data_A/members.json`

| Field | Type | Meaning | Example |
|---|---|---|---|
| `member_id` | `str` | The id a claim points at. | `"M-2214"` |
| `name` | `str` | Display name. Carries no decision information. | `"Tan Wei Ling"` |
| `policy_id` | `str` | The join onward to `policies.json`. This is the only field on this row that matters to a decision. | `"POL-3310"` |
| `join_date` | `str` | When they joined. Not a coverage date — the policy's own dates govern. | `"2024-04-01"` |

## `data_A/policies.json`

| Field | Type | Meaning | Example |
|---|---|---|---|
| `policy_id` | `str` | The id a member points at. | `"POL-3310"` |
| `product` | `str` | Plan name. Cosmetic; the rules are in the other fields. | `"Shield Plus"` |
| `status` | `str` | `active` or `lapsed`. A lapsed policy ends the run — nothing further needs checking. | `"active"` |
| `start_date` | `str` | Cover begins. A date of service before this is not covered even if the status says active. | `"2026-04-01"` |
| `end_date` | `str` | Cover ends. | `"2027-03-31"` |
| `annual_limit` | `int` | Total the policy will pay in the year, in dollars. | `12000` |
| `used_to_date` | `int` | Already spent this year. **`annual_limit` − `used_to_date` is the headroom**, and the claim total is tested against that, not against the limit. | `2800` |
| `exclusions` | `list[{code, rule}]` | Procedure codes this product never pays for, each with the `rule` id to cite. One excluded line does not refuse the whole claim — it refuses that line. | `[{"code": "31255", "rule": "EX-14 cosmetic…` |

## `data_A/procedures.json`

| Field | Type | Meaning | Example |
|---|---|---|---|
| `code` | `str` | The procedure code that a claim line refers to. | `"47120"` |
| `description` | `str` | What the code means, in words. For your decision record, not for the logic. | `"Laparoscopic appendicectomy"` |
| `requires_preauth` | `bool` | **The branch.** `true` means look for a pre-authorisation; `false` means do not. This single boolean is why the run length varies between claims. | `false` |

## `data_A/preauthorisations.json`

| Field | Type | Meaning | Example |
|---|---|---|---|
| `preauth_id` | `str` | The id to cite in the decision record when an approval is found. | `"PA-5521"` |
| `member_id` | `str` | Half of the match. An approval belongs to one member. | `"M-2214"` |
| `procedure_code` | `str` | The other half. Both must match, plus the dates. | `"62480"` |
| `valid_from` | `str` | Approval window opens. The claim's `date_of_service` must be on or after this. | `"2026-08-01"` |
| `valid_to` | `str` | Approval window closes. On or before this. Outside the window, the approval does not apply. | `"2026-10-31"` |

## `data_A/hospitals.json`

| Field | Type | Meaning | Example |
|---|---|---|---|
| `hospital_id` | `str` | The id a claim points at. | `"H-114"` |
| `name` | `str` | Display name. | `"Riverside General"` |
| `panel` | `bool` | `true` = inside the insurer's network. `false` changes the outcome and must be recorded. | `true` |
| `country` | `str` | Where the hospital is. All shipped rows are `SG`. | `"SG"` |

## `data_A/required_documents.json`

| Field | Type | Meaning | Example |
|---|---|---|---|
| `procedure_code` | `str` | The procedure that triggers the requirement. | `"62480"` |
| `document` | `str` | The document that must be present. Compare with the claim's `documents` list; a missing one is an *ask*, not a refusal. | `"discharge_summary"` |

## `data_A/decided_claims.json`

| Field | Type | Meaning | Example |
|---|---|---|---|
| `claim_id` | `str` | The id of the earlier claim — cite it in your record. Matching does **not** use it; a resubmission arrives with a new id. | `"CLM-8710"` |
| `member_id` | `str` | Part of the duplicate match. One row here differs from a queued claim on this field alone. | `"M-2214"` |
| `hospital_id` | `str` | Part of the duplicate match. | `"H-114"` |
| `date_of_service` | `str` | Part of the duplicate match. One row here differs from a queued claim on this field alone. | `"2026-08-20"` |
| `lines` | `list[{code, amount}]` | Part of the duplicate match, and the one most often skipped. **Same member + same hospital + same date + same lines = the same episode**, whatever the claim id says. One row here shares all three other facts with a queued claim and differs only in its lines — that claim is *not* a duplicate. | `[{"code": "47120", "amount": 1500}]` |
| `decision` | `str` | What was decided the first time round. | `"approve_in_principle"` |
| `decided_on` | `str` | When it was decided. | `"2026-08-22"` |

## Identifier Relationships

| Source field | Target field | Purpose |
|---|---|---|
| `claims.member_id` | `members.member_id` | Identify the member associated with the claim. |
| `members.policy_id` | `policies.policy_id` | Retrieve the member's insurance policy. |
| `claims.hospital_id` | `hospitals.hospital_id` | Retrieve hospital name, panel status, and country. |
| `claims.lines[].code` | `procedures.code` | Retrieve procedure details and determine whether pre-authorisation is required. |
| `claims.lines[].code` | `required_documents.procedure_code` | Determine which supporting document is required for each claim line. |
| `claims.member_id` + `claims.lines[].code` | `preauthorisations.member_id` + `preauthorisations.procedure_code` | Locate the applicable pre-authorisation; the service date must also fall within `valid_from` and `valid_to`. |
| Claim episode fields | `decided_claims` episode fields | Detect duplicates using the same member, hospital, service date, and complete set of claim lines. |

### Important Matching Rules

- `claim_id` is a unique record identifier, but it is not sufficient for detecting resubmitted claims.
- Duplicate detection uses `member_id`, `hospital_id`, `date_of_service`, and the complete set of `{code, amount}` claim lines.
- Every claim line must be checked separately against procedure rules, exclusions, required documents, and pre-authorisation requirements.
- Member-supplied `narrative` is untrusted context and must not be used as authoritative policy data.

