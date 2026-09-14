# D2(b) and D7 Failure 2 — Integration Guide

This package contains only the files owned by the Tool Descriptors and Second Failure Experiment strand. It does not replace the team's agent, backend, harness, fixtures, or other deliverables.

## Files to copy into the team repository

| Package path | Team repository destination |
| --- | --- |
| `project_files/tools.py` | repository root `tools.py` |
| `project_files/prompt.py` | repository root `prompt.py` |
| `project_files/measure_tool_return_tokens.py` | repository root `measure_tool_return_tokens.py` |
| `project_files/run_failures.py` | repository root `run_failures.py` |
| `docs/D2b_TOOL_DESCRIPTORS.md` | `docs/D2b_TOOL_DESCRIPTORS.md` |
| `docs/D7_FAILURE_2_TOOL_INTERFACE.md` | `docs/D7_FAILURE_2_TOOL_INTERFACE.md` |
| `results/*.json` | `results/` |
| `requirements_d2b.txt` | repository root, or merge `tiktoken` into the team's `requirements.txt` |

Review any newer teammate edits before replacing a root Python file. If the team's copies changed after `a(2).zip`, merge the marked descriptor/prompt changes instead of overwriting their work.

## Reproduce the submitted evidence

```powershell
python -m pip install -r requirements_d2b.txt

$env:A2_BACKEND="scripted"
python measure_tool_return_tokens.py
python run_guardrails.py
python run_failures.py 2

$env:A2_PROMPT_VERSION="v1"
python run_eval.py

$env:A2_PROMPT_VERSION="v2"
python run_eval.py
```

Expected headline results:

- Tool-return measurement: V1 PA mean 41.86 tokens; V2 mean 60.71; difference +18.85.
- Scripted evaluation: V1 48/58; V2 58/58.
- Guardrail checklist: V1 12/12; V2 12/12; three hostile-request cases.
- Targeted `CLM-8894`: V1 evidence FAIL 0/3; V2 evidence PASS 3/3.

The live three-model battery belongs to D5 and is not required to reproduce this D2(b)/D7 package.
