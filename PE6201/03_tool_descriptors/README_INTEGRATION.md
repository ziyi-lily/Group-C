# D2(b) and D7 Failure 2 — Integration Guide

This package contains only the files owned by the Tool Descriptors and Second Failure Experiment strand. It does not replace the team's agent, backend, harness, fixtures, or other deliverables.

## Integrated repository locations

| Component | Current location |
| --- | --- |
| Active tool and prompt modules | `PE6201/shared_runtime/` |
| Token measurement and failure scripts | `PE6201/03_tool_descriptors/scripts/` |
| Descriptor and Failure 2 documents | `PE6201/03_tool_descriptors/docs/` |
| Machine-readable evidence | `PE6201/03_tool_descriptors/results/` |
| Extra dependency list | `PE6201/03_tool_descriptors/requirements.txt` |

Review any newer teammate edits before replacing a root Python file. If the team's copies changed after `a(2).zip`, merge the marked descriptor/prompt changes instead of overwriting their work.

## Reproduce the submitted evidence

```powershell
python -m pip install -r PE6201/03_tool_descriptors/requirements.txt

$env:A2_BACKEND="scripted"
python PE6201/03_tool_descriptors/scripts/measure_tool_return_tokens.py
python PE6201/04_guardrails/scripts/run_guardrails.py
python PE6201/03_tool_descriptors/scripts/run_failures.py 2

$env:A2_PROMPT_VERSION="v1"
python PE6201/05_evaluation/scripts/run_eval.py

$env:A2_PROMPT_VERSION="v2"
python PE6201/05_evaluation/scripts/run_eval.py
```

Expected headline results:

- Tool-return measurement: V1 PA mean 41.86 tokens; V2 mean 60.71; difference +18.85.
- Scripted evaluation: V1 48/58; V2 58/58.
- Guardrail checklist: V1 12/12; V2 12/12; three hostile-request cases.
- Targeted `CLM-8894`: V1 evidence FAIL 0/3; V2 evidence PASS 3/3.

The live three-model battery belongs to D5 and is not required to reproduce this D2(b)/D7 package.
