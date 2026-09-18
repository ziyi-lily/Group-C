# D2(b) Live V1/V2 L2 Grading Rubric

## Grading Setup

- **Evaluated model:** `openai/gpt-4o-mini`
- **Grader:** `OpenAI Codex (GPT-5)`
- **Grader type:** Second-model judgment (not human grading)
- **Grading date:** 14 September 2026
- **Conditions:** V1 and V2, 38 cases, 10 negative cases, 58 trials per condition

## Grading Instructions

For each live test, read the complete decision record and evaluate every `must_record` criterion independently.

`true` is marked only when the decision record explicitly conveys the required fact with sufficient identifying detail. Semantically equivalent phrasing and correctly populated structured fields are acceptable. An exact substring match is not required.

`false` is marked when the fact is absent, incomplete, contradicted, or derivable only from background fixture data. The presence of a tool name in the `evidence` list confirms only that the tool was invoked; it does not establish that the tool's returned identifier, date, amount, status, or rule was actually recorded.

Evaluate the evidence independently of the automatic code check. A trial passes the L2 judgment only when every `must_record` criterion is marked true. A trial passes the mixed check only when both the automatic code check and the L2 judgment pass.

Each ordinary case comprises one trial. Each negative case comprises three trials, all judged separately so that stochastic omissions remain visible.
