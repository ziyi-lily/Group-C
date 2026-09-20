# LLM-as-Judge Prompt
You are an objective evaluator for a health-insurance claim processing system.
For the following case, evaluate each item in 'must_record' based on the 'decision' and 'reason' fields.
Return ONLY a raw JSON array of booleans corresponding to each item, in exact order.
Do not add markdown, explanations, or extra text.

Decision: {decision}
Reason: {reason}
Must Record: {must_record}

Output format: [true, false, true, ...]