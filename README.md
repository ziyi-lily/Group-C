## D0(a) Problem Definition & Rung 7 Justification
Problem A covers the automated handling of health insurance claims. Processing requires cross‑checking against member records, insurance policies, and clinical procedure guidelines. Three real‑world factors make strict rule‑based automation a poor fit for this use case:

1. **Unstructured and inconsistent input data**
Claims submitted by members are written in free‑form natural language. Entries frequently include vague wording, conflicting symptom descriptions, and non‑standard terminology. Hard‑coded parsing logic such as regular expressions or static conditional branches will break when processing unforeseen phrasing.
2. **Multi‑step workflows with conditional branching**
There is no fixed linear path to decide whether a claim should be approved, flagged for additional information, or sent to human reviewers. Based on the details of each submitted claim, the system needs to make runtime decisions: it may check a member’s policy coverage limits, validate procedure codes, or pull up past claim history.
3. **Intricate, interconnected policy rules**
Insurance policies contain clauses that depend on one another — for example waiting periods, tiered co‑payment requirements, and pre‑authorization exclusions. Validating one claim cannot be done with a single database lookup; it needs repeated, flexible data retrieval.
