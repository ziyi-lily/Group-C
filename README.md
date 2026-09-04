


## D0(c) What Good Looks Like

A good run of the health-insurance claim first-response agent must satisfy all five criteria:

1. **Correct and traceable outcome:**  
   The agent returns the correct routing outcome — `approve`, `request_document`, or `escalate` — according to the supplied routing rules and authoritative records. The reason must be traceable to specific policy, procedure, pre-authorisation, hospital, claim, or decided-claim records, rather than to an unsupported assumption.

2. **Complete claim-line assessment:**  
   Every claim line receives a clear disposition and supporting evidence. Any amounts and totals shown in the final response must reconcile with the values in the claim records.

3. **Safe use of the gated action:**  
   The agent calls `issue_decision_letter` at most once, and only after the relevant facts have been established and the required confirmation gate has passed. It must never issue the letter repeatedly or before confirmation.

4. **No unsupported invention:**  
   If required information is missing, invalid, contradictory, or cannot be verified from the available records, the agent does not invent an answer. It identifies the exact missing document or information and returns `request_document` or `escalate` according to the routing rules.

5. **Efficient and bounded execution:**  
   The agent calls only the tools necessary for the case, avoids duplicate lookups, stops once sufficient evidence supports an outcome, and remains within the documented turn, tool-call, token, and cost limits. Its measured per-case cost will later be compared with the stated manual-processing baseline.
