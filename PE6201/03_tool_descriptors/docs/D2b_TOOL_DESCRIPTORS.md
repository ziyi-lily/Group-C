# D2(b) Tool Descriptors and Rewrite Experiment - Problem A


## 1. Complete Tool Descriptors


The Problem A agent have seven tools. Each tool defines six required contract fields - **NAME + SIGNATURE, WHAT, INPUT, RETURNS, FAILS WHEN,** and **IRREVERSIBLE?** - and the number of returned tokens was measured by running the final fixture set (38 claims) through the tokenizer and serialising the results with `repr(result)`. On September 20, 2026, we locked the final controlled measurement data using a deterministic scripted planner, parallel calls, a six-turn cap, and confirmed autonomy.


### 1.1 get_claim


| Field | Descriptor |
|---|---|
| NAME + SIGNATURE | get_claim(claim_id: str) |
| WHAT | Retrieves the claim to be evaluated, including the member, hospital, service date, narrative, attached documents, and all claim lines. It acts as the entry-point tool and must be called before any tool that depends on claim fields. |
| INPUT | claim_id: str - an existing claim identifier such as CLM-9013.  |
| RETURNS | At most one claim object containing claim_id, member_id, hospital_id, date_of_service, narrative, documents, lines, and narrative_flags; otherwise None. Measured across 38 calls: mean 102.47, median 100, range 83-138, total 3,894 return tokens. The measured size bound is 138 tokens per return. |
| FAILS WHEN | No claim matches claim_id, or the claims data file is unavailable. |
| IRREVERSIBLE? | No. Read-only. |

### 1.2 lookup_policy

| Field | Descriptor |
|---|---|
| NAME + SIGNATURE | lookup_policy(member_id: str) |
| WHAT | Tracks the relationship between members and policies and calculates the remaining annual limit as annual_limit - used_to_date. It provides the facts necessary to verify policy status, service-date validity, exclusion clauses, and remaining financial limits. |
| INPUT | member_id: str - the member identifier returned by get_claim. Passing a policy ID, member name, or unknown member returns no result. |
| RETURNS | At most one object shaped as {member, policy, remaining}; otherwise None. Measured across 38 calls: mean 139.50, median 139, range 123-158, total 5,301 return tokens. The measured size bound is 158 tokens per return. |
| FAILS WHEN | The member does not exist, the member has no policy reference, the referenced policy does not exist, or the data file is unavailable. |
| IRREVERSIBLE? | No. Read-only. |

### 1.3 lookup_hospital

| Field | Descriptor |
|---|---|
| NAME + SIGNATURE | lookup_hospital(hospital_id: str) |
| WHAT | Searches for the treating hospital and its panel status. Non-panel hospitals may change the interpretation and payment path, but they do not automatically determine the claim outcome. |
| INPUT | hospital_id: str - the hospital identifier returned by get_claim. |
| RETURNS | At most one object containing hospital_id, name, panel, and country; otherwise None. Measured across 38 calls: mean 28.42, median 28, range 28-29, total 1,080 return tokens. The measured size bound is 29 tokens per return. |
| FAILS WHEN | No hospital matches hospital_id, or the hospital data file is unavailable. |
| IRREVERSIBLE? | No. Read-only. |

### 1.4 check_coverage

| Field | Descriptor |
|---|---|
| NAME + SIGNATURE | check_coverage(code: str, policy_id: str) |
| WHAT | Resolves one claim line under a specific policy. It determines the procedure, whether pre-authorisation is required, whether the policy excludes the procedure, the applicable exclusion rule, and any required document. It must be called once per line; independent line calls may run in parallel. |
| INPUT | code: str - one procedure code from the claim; policy_id: str - the policy returned by lookup_policy. Both are mandatory.|
| RETURNS | At most one object containing {code, description, requires_preauth, excluded, exclusion_rule, required_document}; otherwise None. Measured across 66 calls: mean 43.18, median 42, range 41-51, total 2,850 return tokens. The measured size bound is 51 tokens per return. |
| FAILS WHEN | The procedure code or policy does not exist, or a required data file is unavailable. An excluded procedure is not a tool failure: the tool returns excluded=true along with the applicable rule. |
| IRREVERSIBLE? | No. Read-only. |


### 1.5 get_preauthorisation


| Field | Descriptor |
|---|---|
| NAME + SIGNATURE | get_preauthorisation(member_id: str, procedure_code: str, date_of_service: str) |
| WHAT | Checks whether prior authorisation belongs to the correct member and procedure and is valid on the service date. It is called only when check_coverage returns requires_preauth=true. |
| INPUT | member_id: str, procedure_code: str, and date_of_service: str in YYYY-MM-DD format. All three values must match for a valid result.|
| RETURNS | V2 returns one bounded object: {found: bool, preauth: object|null, expired_candidate: object|null}. It contains at most one valid PA and one expired matching candidate. Measured across 14 calls: mean 60.71, median 68, range 17-68, total 850 return tokens. The measured size bound is 68 tokens per return. |
| FAILS WHEN | found=false when no valid PA covers the member, procedure, and service date. This is a business-state result indicating missing evidence, not a tool exception and not proof that the procedure is excluded. A malformed date or unavailable data file is a technical failure. |
| IRREVERSIBLE? | No. Read-only. |


### 1.6 check_duplicate_claim


| Field | Descriptor |
|---|---|
| NAME + SIGNATURE | check_duplicate_claim(member_id: str, hospital_id: str, date_of_service: str, lines: list) |
| WHAT | Checks whether the same episode has already been decided. An exact duplicate requires all four business facts to match: member, hospital, date of service, and normalised line items. claim_id is intentionally excluded because a resubmission has a new claim ID. |
| INPUT | member_id: str, hospital_id: str, date_of_service: str, and the complete lines: list from get_claim. A line without code or amount is invalid. |
| RETURNS | {is_duplicate: bool, exact_match: object|null, near_matches: list}. It returns at most one exact match and three one-field near matches. Measured across 38 calls: mean 25.89, median 18, range 18-105, total 984 return tokens. The measured size bound is 105 tokens per return. |
| FAILS WHEN | A required data file is unavailable or a provided line lacks code or amount. is_duplicate=false is a normal result and processing must continue. |
| IRREVERSIBLE? | No. Read-only. |


### 1.7 issue_decision_letter


| Field | Descriptor |
|---|---|
| NAME + SIGNATURE | issue_decision_letter(claim_id: str, decision: Literal['approve_in_principle', 'request_document', 'escalate'], lines_resolved: int, approved_total: int, refused_total: int = 0) |
| WHAT | Commits the insurer's first response after all claim lines have been resolved. lines_resolved makes incomplete line processing visible. This tool must be called at most once per run. |
| INPUT | claim_id, decision, lines_resolved, and approved_total are required. refused_total is optional and defaults to 0. decision must be one of the three permitted outcomes. |
| RETURNS | At most one confirmation object containing sent, claim_id, decision, lines_resolved, approved_total, and refused_total. Measured across 38 representative calls: mean 48.97, median 49, range 47-50, total 1,861 return tokens. The measured size bound is 50 tokens per return. |
| FAILS WHEN | When the autonomous gate is not satisfied, the loop blocks the call before execution, and its repeated action protection stops the same repeated call. When the required parameters are lost or wrongly named, the scheduler returns a bad-argument error. |
| IRREVERSIBLE? | Yes. It is protected by the autonomy gate (confirm) and duplicate-action prevention. |


## 2. Poka-Yoke Design Changes


The entire significance of the poka-yoke change lies in the fact that it is impossible to make mistakes structurally, rather than hoping that the model will be more cautious.


| Before | After | What the change makes impossible |
|---|---|---|
| check_coverage(code) | check_coverage(code, policy_id) | Returning a global coverage answer without identifying the member's actual policy. |
| Valid PA row or None | {found, preauth, expired_candidate} | Making an expired matching PA indistinguishable from a PA that never existed. |
| Partial duplicate criteria or a truthy row | Four mandatory matching facts plus {is_duplicate, exact_match, near_matches} | Escalating a one-field near match merely because the tool returned a non-empty object. |


### 2.1 Require the policy in every coverage check


Under the older design, check_coverage(code) could only respond at a global procedure level -  policy-specific exclusions were easily overlooked. V2 narrows this gap by requiring policy_id, which forces the tool to identify the relevant policy before returning a coverage result.


### 2.2 Return an explicit PA verdict and preserve expired evidence


V1 compresses two fundamentally different situations - "no matching PA exists" and "a matching PA exists but has expired" - into a single None. On the other hand, V2 returns an explicit found flag and keeps a bounded expired_candidate. That change makes it impossible for the interface to erase the existence, identifier, and validity dates of the most relevant expired PA without mentioning.


### 2.3 Require all four duplicate facts and an explicit verdict


The duplicate tool now demands all four business facts - member, hospital, date of service, and the full line list - and returns an explicit Boolean value of is_duplicate, along with separated exact_match and bounded near_matches. A similar match will not be mistaken for an exact repetition just because the returned object happens to be non-empty.


## 3. Descriptor and Return-Shape Rewrite


We selected get_preauthorisation for this controlled rewrite. V1 and V2 use the same agent, deterministic scripted planner, fixture data, routing rule, call mode, turn cap, autonomy setting, and non-PA descriptors. The only experimental changes are the PA descriptor and its return shape.


### 3.1 V1 contract


```
NAME + SIGNATURE
get_preauthorisation(
    member_id: str,
    procedure_code: str,
    date_of_service: str
)

WHAT
Returns a pre-authorisation only when it is valid on the date of service.

INPUT
member_id, procedure_code, and date_of_service are required.

RETURNS
One valid pre-authorisation row, or None.
Measured size: mean 41.86, median 53, range 1-53 tokens.

FAILS WHEN
Returns None when no valid matching approval is found. None cannot tell
an approval that was never issued from one that exists but has expired.

IRREVERSIBLE?
No.
```


V1 return shape:


```
preauthorisation_row | None
```


### 3.2 V2 contract


```
NAME + SIGNATURE
get_preauthorisation(
    member_id: str,
    procedure_code: str,
    date_of_service: str
)

WHAT
Checks whether prior permission belongs to the correct member and procedure
and is valid on the service date. Call it only when check_coverage returns
requires_preauth=true.

INPUT
All three values are required. All three must match for a valid PA.

RETURNS
{found: bool, preauth: object|null, expired_candidate: object|null}.
At most one valid PA and one expired candidate are returned.
Measured size: mean 60.71, median 68, range 17-68 tokens.

FAILS WHEN
found=false means that valid PA evidence is missing. It leads to a specific
request for evidence; it does not prove that the procedure is excluded.

IRREVERSIBLE?
No.
```


V2 return shape:


```
{
    "found": bool,
    "preauth": preauthorisation_row | None,
    "expired_candidate": preauthorisation_row | None,
}
```


V2 spells out three distinct states explicitly:


| Situation | found | preauth | expired_candidate |
|---|---|---|---|
| Valid matching PA | true | valid PA | null |
| No matching PA | false | null | null |
| Matching but expired PA | false | null | expired PA |


## 4. V1 versus V2 Measurements


### 4.1 Prompt-prefix size


The only difference between these two conditions is the get_preauthorisation descriptor and its returned shape. All other contents - routing, hostile-input handling, answer-format instructions, and non-PA tool descriptions - remain exactly the same.


| Measure | V1 | V2 | Difference |
|---|---|---|---|
| Prompt characters | 12,058 | 12,673 | +615 |
| Approximate prompt tokens (characters / 4) | 3,014 | 3,168 | +154 |


Among the median of the four observed rounds, before calculating the observed growth, the larger V2 prefix generated approximately 616 additional input tokens per run. This is a recurring cost, so the safety upside has to outweigh it.


### 4.2 Tool-return tokens


Both versions were tested against the same 14 PA-requiring fixture inputs.


| Measure | V1 | V2 | Difference |
|---|---|---|---|
| Calls measured | 14 | 14 | 0 |
| Mean return tokens per call | 41.86 | 60.71 | +18.85 |
| Median return tokens | 53 | 68 | +15 |
| Minimum return tokens | 1 | 17 | +16 |
| Maximum return tokens | 53 | 68 | +15 |
| Total return tokens | 586 | 850 | +264 |


Take the targeted expired-PA case CLM-8894 as an example: V1 returned None in a single token. V2 returned the full structured result with the expired candidate PA-5640 in 68 tokens - only 67 tokens for this call.


Here's how V2's return sizes looked across all seven tools:


| Tool | Calls | Mean | Median | Min | Max | Total |
|---|---|---|---|---|---|---|
| get_claim | 38 | 102.47 | 100 | 83 | 138 | 3,894 |
| lookup_policy | 38 | 139.50 | 139 | 123 | 158 | 5,301 |
| lookup_hospital | 38 | 28.42 | 28 | 28 | 29 | 1,080 |
| check_coverage | 66 | 43.18 | 42 | 41 | 51 | 2,850 |
| get_preauthorisation V2 | 14 | 60.71 | 68 | 17 | 68 | 850 |
| check_duplicate_claim | 38 | 25.89 | 18 | 18 | 105 | 984 |
| issue_decision_letter | 38 | 48.97 | 49 | 47 | 50 | 1,861 |


### 4.3 Evaluation pass rate and guardrails


The final evaluation pool holds 38 cases - 10 of them negative. Run each ordinary case once and each negative case three times, and you get 58 trials per condition.


#### Deterministic scripted regression


| Measure | V1 | V2 | Difference |
|---|---|---|---|
| Code-check pass rate | 48/58 (82.8%) | 58/58 (100.0%) | +17.2 percentage points |
| Negative code-check pass rate | 30/30 (100.0%) | 30/30 (100.0%) | No change |
| Median turns | 4 | 4 | No change |
| Worst-case turns | 4 | 5 | +1 |
| Step-cap hits | 0 | 0 | No change |
| Estimated input tokens | 847,350 | 927,107 | +79,757 |
| Estimated cost | US$0.096936 | US$0.105383 | +US$0.008447 |


Every single one of the ten scripted V1 failures occured after get_preauthorisation of claims that actually carried valid PA evidence: CLM-8842, CLM-8861, CLM-9013, CLM-9015, CLM-9016, CLM-9020, CLM-9021, CLM-9165, CLM-9180, and CLM-9103. V2 restores these to normal by restoring compatibility with the structured PA processing of the working agent.


Now, the scripted backend is deterministic - it tests the interface and the evaluation harness, not live-model judgement. The controlled live comparison below measures V1 and V2 on one model for D2(b); the team's separate D5 battery still requires three live models.


#### Live controlled comparison


Both conditions used `openai/gpt-4o-mini`, the same 38-case fixture set, parallel tool calls, a six-turn cap, confirm autonomy, and the same trial policy. Each ordinary case ran once and each of the 10 negative cases ran three times, producing 58 trials per condition. The runs and second-model grading were completed on 20 September 2026.


The L2 grader was `OpenAI Codex (GPT-5)`, which is different from the evaluated model. It read the complete decision record and judged every `must_record` criterion semantically; it did not use substring matching. All 58 trials in each condition were judged. An L2 trial passed only when every required criterion passed. A mixed trial passed only when both the automatic code check and the L2 judgement passed.


| Measure | V1 | V2 | Difference |
|---|---:|---:|---:|
| Code-check pass rate | 39/58 (67.2%) | 40/58 (69.0%) | +1 trial; +1.7 percentage points |
| L2 all-criteria pass rate | 7/58 (12.1%) | 13/58 (22.4%) | +6 trials; +10.3 percentage points |
| Mixed pass rate | 7/58 (12.1%) | 13/58 (22.4%) | +6 trials; +10.3 percentage points |
| Negative code-check pass rate | 22/30 (73.3%) | 21/30 (70.0%) | -1 trial; -3.3 percentage points |
| Negative mixed pass rate | 3/30 (10.0%) | 9/30 (30.0%) | +6 trials; +20.0 percentage points |
| Individual `must_record` criteria passed | 58/159 (36.5%) | 73/159 (45.9%) | +15 criteria; +9.4 percentage points |
| Median turns | 3 | 3 | No change |
| Worst-case turns | 5 | 5 | No change |
| Step-cap hits | 0 | 0 | No change |
| Input tokens | 754,126 | 828,172 | +74,046 |
| Output tokens | 17,502 | 17,704 | +202 |
| Total tokens | 771,628 | 845,876 | +74,248 |
| Cost | US$0.082417 | US$0.089897 | +US$0.007480 |


V2 passed one more broad live code-check trial than V1, while it passed one fewer negative code-check trial. These one-trial differences are not sufficient evidence of a broad accuracy gain or loss.


The semantic results show a narrower benefit. V2 raised the mixed pass rate from 7/58 to 13/58 and the negative mixed pass rate from 3/30 to 9/30. However, the low absolute L2 rates in both versions show that the agent often reached a broad outcome without recording all required identifiers, dates, amounts, limits, exclusions, or line-level evidence. The structured interface makes expired-PA evidence available, but does not guarantee that a stochastic model will cite it in every run.


#### Guardrail checklist


| Measure | V1 | V2 | Difference |
|---|---|---|---|
| Guardrail cases passed | 12/12 (100.0%) | 12/12 (100.0%) | No regression |
| Hostile-request cases included | 3 | 3 | Identical set |


The checklist runs through the step cap, budget ceiling, action de-duplication, autonomy gate, boundary behaviour, false-positive prevention, and three hostile member narratives. Guardrail code and cases stayed identical between V1 and V2.


### 4.4 Targeted expired-PA failure


CLM-8894 carries procedure 29881, which needs pre-authorisation. PA-5640 is tied to the right member and procedure but expired on 2026-05-31 - before the service date of 2026-09-09.


| Measure | V1 row-or-None | V2 structured result | Change |
|---|---|---|---|
| Decision | request_document | request_document | No change |
| Code check | PASS | PASS | No change |
| Required evidence criteria passed | 0/3 - FAIL | 3/3 - PASS | Failure recovered |
| Turns | 4 | 4 | No change |
| Estimated input tokens | 17,499 | 17,544 | +45 |
| Estimated output tokens | 600 | 600 | No change |
| Estimated cost | US$0.001990 | US$0.001994 | approximately +US$0.000004 |


The 0/3 and 3/3 figures refer to three evidence criteria in one deterministic run, not three separate trials.


V1 basically said "no pre-authorisation found." It couldn't point to PA-5640, couldn't record when it expired, and couldn't explain why the existing PA didn't cover this claim. V2 kept all three facts intact:


```
PA-5640 was found.
Its validity ended on 2026-05-31.
The 2026-09-09 service date falls outside that period, so it does not
authorise this claim.
```


This failure lives squarely in the **tool-interface layer**. Once the tool discards a PA identifier and its expiry date, no prompt can reconstruct them - and loop-control guardrails aren't even in play here because the run wraps up cleanly without repetition or cap violations.


## 5. Interpretation


V2 is bigger. It tacks on 18.85 mean return tokens per PA call, 264 total across the 14 measured PA calls, and an average increase of approximately 45.0% of tokens in PA returns. That recurring observation cost is real and measurable, so it shouldn't be  disguised as some kind of savings.


The deterministic regression increased from 82.8% to 100.0%, indicating that the structured V2 result is compatible with the working agent and prevents valid PA records from being misread as lost by the scripted planner. Both versions passed all 12 guardrail cases, so the rewrite  did not introduce measurable guardrail regression.


The live comparison showed a one-trial broad code-check difference: V1 passed 39/58 trials and V2 passed 40/58. The second model judgment identified a semantic improvement, with the hybrid pass rate moving from 7/58 to 13/58, but the absolute L2 rate remained low because many records omitted the required evidence. The reports of these data do not take the code check differences from a single trial as general model quality results.


The failure of the target provides the clearest reason for the change.  V1 removed the existence and date of the expired PA-5640 from the tool return. In the deterministic reproduction, V2 changed the required-evidence result from 0/3 to 3/3 without altering the decision or the number of rounds. In the live battery, V1 did not record the three required PA facts in all three CLM-8894 tests. V2 recorded all three facts in all three experiments. Therefore, V2 is regarded as an interface constraint for preserving evidence rather than a comprehensive accuracy or token-preserving fix.

The L2 judgement used a different model from the evaluated agent and covered all 58 trials per condition. The complete verdicts are stored in `results_live_gpt-4o-mini_parallel_v1_graded.json` and `results_live_gpt-4o-mini_parallel_v2_graded.json`; the grading instructions are stored in `D2b_L2_GRADING_RUBRIC.md` so the reported mixed rates can be audited.
