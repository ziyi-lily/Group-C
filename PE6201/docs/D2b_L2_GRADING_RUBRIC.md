# D2(b) Live V1/V2 L2 Grading Rubric

## Grading setup

- Evaluated model: `openai/gpt-4o-mini`
- Grader: `OpenAI Codex (GPT-5)`
- Grader type: second-model judgement, not human grading
- Grading date: 14 September 2026
- Conditions: V1 and V2, 38 cases, 10 negative cases, 58 trials per condition

## Grading instruction

For every live trial, read the complete decision record and assess each
`must_record` criterion independently.

Mark a criterion `true` only when the decision record explicitly communicates
the required fact with sufficient identifying detail. Semantically equivalent
wording and correctly populated structured fields count. Do not require an
exact substring match.

Mark a criterion `false` when the fact is absent, incomplete, contradicted, or
only inferable from background fixture data. A tool name in the `evidence` list
proves only that the tool was called; it does not prove that the tool's returned
identifier, date, amount, status, or rule was recorded.

Judge the evidence independently of the automatic code check. A trial passes
the L2 judgement only when every `must_record` criterion is true. A trial passes
the mixed check only when both the automatic code check and the L2 judgement
pass.

Every ordinary case has one trial. Every negative case has three trials, and
all three are judged separately so stochastic omissions are visible.
