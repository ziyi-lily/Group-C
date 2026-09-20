# PE6201 A2 File Index

The repository is organised by assignment part under `PE6201/`.

| Folder | Purpose |
| --- | --- |
| `00_problem_framing/` | D0(a), D0(b) and D0(c) |
| `01_agent_loop/` | Agent Loop evidence and logs |
| `02_fixture_data/` | Integrated fixture data plus the clearly separated legacy package |
| `03_tool_descriptors/` | Tool descriptors, Failure 2, scripts and results |
| `04_guardrails/` | Guardrail cases, runner, guide and results |
| `05_evaluation/` | Evaluation runner, judging prompt and model results |
| `06_cost_model/` | Cost workbook and Jupyter visualisation |
| `shared_runtime/` | Shared Python modules used by multiple parts |

## Key run commands

Run these commands from the repository root:

```bash
python PE6201/02_fixture_data/reference_data/check_my_data.py
python PE6201/04_guardrails/scripts/run_guardrails.py
python PE6201/05_evaluation/scripts/run_eval.py
python PE6201/03_tool_descriptors/scripts/run_failures.py 2
```

## Important distinctions

- `02_fixture_data/reference_data/` is the active integrated fixture package.
- `02_fixture_data/legacy_root_package/` preserves earlier parallel files and is not imported by the active runtime.
- Descriptor V1/V2 experiment results stay in Part 3 and are separate from the final model comparison in Part 5.
- `d5b_Hy3_AfterJudge.json` remains in Part 5 but should stay separate from the primary four-model table until its full model identity is confirmed.
