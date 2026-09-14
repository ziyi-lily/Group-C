# D7 Failure 2 - Tool-Interface Information Loss


## 1. Failure definition


This is the second failure case we have reproduced, which is different from the loop control failures we have been tracking all along. The root cause sits in the **tool-interface layer**.


Here's the setup: CLM-8894 involves procedure 29881, which requires pre-authorisation. PA-5640 is tied to member M-6118 and procedure 29881, but it expired on 2026-05-31. The service date in question is 2026-09-09.


The right call here is request_document. But a proper record also needs to say that PA-5640 was found, log its expiry date, and spell out why it doesn't authorise this particular claim.


## 2. Deletion from the working agent


We kept everything else constant across both conditions - same claim, same fixture data, same scripted planner, same routing rule, same call mode, same turn cap, same autonomy setting, same V2 system prompt. The only thing we changed was the registered get_preauthorisation implementation.


**Before - working agent minus the structured interface:**


```
preauthorisation_row | None
```


V1 only hands back a PA that's valid on the service date. If a matching PA has expired, it just collapses everything into None.


**After - structured interface restored:**


```
{
    "found": bool,
    "preauth": preauthorisation_row | None,
    "expired_candidate": preauthorisation_row | None,
}
```


V2 keeps at most one expired candidate alive, which means the decision record can actually cite evidence that exists rather than working with nothing.


## 3. Reproduction and graders


Run this from the project root:


```
$env:A2_BACKEND="scripted"
python run_failures.py 2
```


We hooked up two graders to evaluate the results:


- **Code check**: the decision must equal request_document, and issue_decision_letter must not be called because this is a non-acting outcome. No escalation trigger applies to this case.


- **Evidence check**: the reason must name PA-5640, record 2026-05-31, and explain why the expired PA doesn't authorise the claim.


## 4. Before-and-after evidence


Measurements taken on **14 September 2026**.


| Measure | V1 before | V2 after | Result |
|---|---|---|---|
| Decision | request_document | request_document | unchanged |
| Code check | PASS | PASS | broad outcome alone cannot expose the failure |
| Required evidence criteria passed | 0/3 - FAIL | 3/3 - PASS | failure recovered |
| Turns | 4 | 4 | unchanged |
| Estimated input tokens | 17,329 | 17,374 | +45 |
| Estimated output tokens | 600 | 600 | unchanged |
| Estimated cost | US$0.001973 | US$0.001977 | approximately +US$0.000004 |


The 0/3 and 3/3 figures refer to three evidence criteria in one deterministic run, not three separate trials.


V1's answer was essentially "no pre-authorisation found." That's incomplete - PA-5640 was right there. The moment V1 returns None, the identifier and validity dates are gone for good.


V2 tells a different story. It captured that PA-5640 ran from 2026-03-01 to 2026-05-31, while the treatment happened on 2026-09-09. With those facts on the table, the record can lay out exactly why the existing PA doesn't qualify as valid evidence for this claim.


## 5. Correct fix layer


The evidence got discarded at the **tool interface**, so that's where the fix has to land.


- **Not the prompt layer**: once the tool hands back None, no prompt can magically reconstruct an identifier and expiry date that were never passed through.


- **Not the loop-control layer**: the agent didn't loop endlessly, blow past a cap, or fail to reach a conclusion. Both versions wrapped up in four turns.


- **Tool-interface fix**: keep a bounded structured verdict around - one that carries either the valid match or the most relevant expired candidate.


This isn't about saving tokens, by the way. V2 adds 18.85 mean return tokens per PA call and 67 extra tokens on CLM-8894. The justification is purely about preserving evidence: the required-evidence score jumps from 0/3 to 3/3, and neither the decision nor the turn count budges.


The machine-readable output gets saved to results/d7_failure_2_tool_interface.json.
