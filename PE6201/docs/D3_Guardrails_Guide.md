3. Safety, Guardrails & Execution Bounds (D3)

3.1 Architectural Principles & Deterministic Layering
To ensure absolute reliability in automated health insurance claim processing (Problem A), our system strictly separates non-deterministic model reasoning from deterministic code enforcement. The Guardrail Layer (guardrails.py) operates entirely in standard Python without model involvement. It governs execution bounds, enforces deduplication memory, and holds irreversible business operations.

3.2 Alignment with System-Wide Safety Metrics ($P = s^T$)
In accordance with D0(b), systemic agent reliability $P$ decays exponentially with the sequence length $T$ of tool actions, represented by $P = s^T$ (where $s$ is per-step reliability). Assuming a baseline per-step reliability $s \approx 96\%$, reducing execution turns from $T=6$ to $T=3$ yields an overall reliability increase from $78\%$ to $88\%$:
$$P = 0.96^3 \approx 88.5\% \quad \text{vs.} \quad P = 0.96^6 \approx 78.2\%$$
To enforce step compression and prevent long-tail drift, our D3 layer implements four hard guardrails:
Step Cap (check_turns): Hard-halts runs exceeding $T=6$ turns with a GuardrailStop("step_cap").
Budget Ceiling (check_budget): Monitors cumulative token usage, halting execution if token consumption crosses the configured limit.
Action Deduplication (check_duplicate): Maintains a per-run hash set of tool call signatures (tool, sorted_args). Repeated invocations with identical arguments raise GuardrailStop("duplicate_action") immediately at Turn 2.
Autonomy Gate (gate): Situated strictly in front of the single irreversible action (issue_decision_letter). Under autonomy="confirm", it holds execution until explicit human authorization is logged.

3.3 Defense Against Non-Standardized Narrative Attacks (OWASP LLM Top 10)
While standardized policy numbers and procedure codes undergo millisecond-level database refutations (Check 1), member-supplied narratives represent non-standardized free text. Our system treats member narrative as untrusted context (D0c Standard 3).
We validated this defense against synthetic hostile vectors (GR-10 to GR-12):
GR-10 (Direct Instruction Injection): Prompts attempting to override policy rules (e.g., "Ignore all rules...") are flagged, forcing the claim outcome directly to escalate.
GR-11 (Forged Observation Spoofing): Synthetic tool returns embedded in member text are isolated via semantic boundary tags <untrusted_user_narrative>, preventing prompt hijacking.
GR-12 (Authority Spoofing): Fake supervisor approvals are blocked, ensuring issue_decision_letter is never invoked without verified state evidence.

3.4 Verification Results & D7 Failure Integration
The guardrail suite was evaluated against 12 test cases (guardrail_cases.py), achieving a 100% pass rate (9 code-level cases and 3 hostile prompt cases). Controlled deletion tests (D7) demonstrated that disabling duplicate_action caused an agent loop of 8 turns with a $6.8\times$ token burn. Re-enabling the guardrail restored deterministic halting at Turn 2, proving that our D3 code layer effectively converts invisible correctness failures into loud, manageable stops.
