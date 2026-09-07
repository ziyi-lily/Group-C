## D0(a) Problem Definition & Rung 7 Justification
Problem A covers the automated handling of health insurance claims. Processing requires cross‑checking against member records, insurance policies, and clinical procedure guidelines. Three real‑world factors make strict rule‑based automation a poor fit for this use case:

1. **Unstructured and inconsistent input data**
Claims submitted by members are written in free‑form natural language. Entries frequently include vague wording, conflicting symptom descriptions, and non‑standard terminology. Hard‑coded parsing logic such as regular expressions or static conditional branches will break when processing unforeseen phrasing.
2. **Multi‑step workflows with conditional branching**
There is no fixed linear path to decide whether a claim should be approved, flagged for additional information, or sent to human reviewers. Based on the details of each submitted claim, the system needs to make runtime decisions: it may check a member’s policy coverage limits, validate procedure codes, or pull up past claim history.
3. **Intricate, interconnected policy rules**
Insurance policies contain clauses that depend on one another — for example waiting periods, tiered co‑payment requirements, and pre‑authorization exclusions. Validating one claim cannot be done with a single database lookup; it needs repeated, flexible data retrieval.


D0(c) What Good Looks Like
A good run of the health-insurance claim first-response agent must satisfy all five criteria:

Correct and traceable outcome:
The agent returns the correct routing outcome — approve, request_document, or escalate — according to the supplied routing rules and authoritative records. The reason must be traceable to specific policy, procedure, pre-authorisation, hospital, claim, or decided-claim records, rather than to an unsupported assumption.

Complete claim-line assessment:
Every claim line receives a clear disposition and supporting evidence. Any amounts and totals shown in the final response must reconcile with the values in the claim records.

Safe use of the gated action:
The agent calls issue_decision_letter at most once, and only after the relevant facts have been established and the required confirmation gate has passed. It must never issue the letter repeatedly or before confirmation.

No unsupported invention:
If required information is missing, invalid, contradictory, or cannot be verified from the available records, the agent does not invent an answer. It identifies the exact missing document or information and returns request_document or escalate according to the routing rules.

Efficient and bounded execution:
The agent calls only the tools necessary for the case, avoids duplicate lookups, stops once sufficient evidence supports an outcome, and remains within the documented turn, tool-call, token, and cost limits. Its measured per-case cost will later be compared with the stated manual-processing baseline.
