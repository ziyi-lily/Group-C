# PE6201 A2 File Index

This index classifies the repository without moving, renaming, deleting, or changing any existing project file. Keeping the current paths intact avoids breaking Python imports, relative data paths, and reproduction commands.

## Quick map

| Area | Primary location | Status |
|---|---|---|
| D0 problem framing and quality criteria | Repository root and `PE6201/D0(a)` | Present |
| 1. Agent Loop and integration | `PE6201/project_files/` | Present |
| 2. Fixture data and tool functions | `A2_reference_data/` and `tools.py` | Present |
| 3. Tool descriptors and Failure 2 | `PE6201/docs/`, scripts and results | Present |
| 4. Guardrails and safety tests | Guardrail code, guide and checklists | Present |
| 5. Evaluation Harness and Model Battery | Harness, grader, model results and logs | Present |
| 6. Cost Model and visualisation | Cost workbook and Jupyter notebook | Present |

## D0 — problem framing and quality criteria

- `PE6201/D0(a)` — problem definition and Rung 7 justification.
- `D0(b).ipynb` — two safety checks and arithmetic illustration.
- `README.md` — D0(c), “What Good Looks Like”.
- `DATA_FIELDS.md` — field guide for the Problem A fixture data.

## 1 — Agent Loop and system integration

Core implementation:

- `PE6201/project_files/agent.py`
- `PE6201/project_files/backends.py`
- `PE6201/project_files/config.py`
- `PE6201/project_files/prompt.py`
- `PE6201/project_files/trace.py`

Runtime evidence:

- `PE6201/project_files/logs/decisions.jsonl`
- `PE6201/project_files/logs/traces.jsonl`

## 2 — Fixture data and tool functions

Reference-data package:

- `PE6201/project_files/A2_reference_data/README.md`
- `PE6201/project_files/A2_reference_data/check_my_data.py`
- `PE6201/project_files/A2_reference_data/make_fixtures_A.py`
- `PE6201/project_files/A2_reference_data/expected_outcomes_A.json`
- `PE6201/project_files/A2_reference_data/data_dictionary.json`

Problem A data tables:

- `data_A/claims.json`
- `data_A/members.json`
- `data_A/policies.json`
- `data_A/hospitals.json`
- `data_A/procedures.json`
- `data_A/preauthorisations.json`
- `data_A/required_documents.json`
- `data_A/decided_claims.json`

Tool implementation: `PE6201/project_files/tools.py`.

## 3 — Tool descriptors and second failure experiment

Documentation:

- `PE6201/README_INTEGRATION.md`
- `PE6201/docs/D2b_TOOL_DESCRIPTORS.md`
- `PE6201/docs/D2b_L2_GRADING_RUBRIC.md`
- `PE6201/docs/D7_FAILURE_2_TOOL_INTERFACE.md`

Scripts and dependencies:

- `PE6201/project_files/measure_tool_return_tokens.py`
- `PE6201/project_files/run_failures.py`
- `PE6201/requirements_d2b.txt`

Primary evidence:

- `PE6201/results/d2b_tool_token_measurements.json`
- `PE6201/results/d7_failure_2_tool_interface.json`
- `PE6201/results/results_scripted_planner_parallel_v1.json`
- `PE6201/results/results_scripted_planner_parallel_v2.json`
- `PE6201/results/results_live_gpt-4o-mini_parallel_v1.json`
- `PE6201/results/results_live_gpt-4o-mini_parallel_v1_graded.json`
- `PE6201/results/results_live_gpt-4o-mini_parallel_v2.json`
- `PE6201/results/results_live_gpt-4o-mini_parallel_v2_graded.json`

The V1/V2 files are descriptor/failure-experiment comparisons and should not be mixed with the final four-model D5 comparison.

## 4 — Guardrails and safety testing

- `PE6201/project_files/guardrails.py`
- `PE6201/project_files/guardrail_cases.py`
- `PE6201/project_files/run_guardrails.py`
- `PE6201/docs/D3_Guardrails_Guide.md`
- `PE6201/results/guardrail_checklist_v1.json`
- `PE6201/results/guardrail_checklist_v2.json`

## 5 — Evaluation Harness and Model Battery

Evaluation implementation:

- `PE6201/project_files/harness.py`
- `PE6201/project_files/run_eval.py`
- `PE6201/project_files/judging_prompt.md`
- `PE6201/project_files/backends.py` (shared with Part 1)

Scripted baseline: `PE6201/results/d5a_Scripted.json`.

Four primary live-model results:

- `PE6201/results/d5b_Gemma 3 27B_AfterJudge.json`
- `PE6201/results/d5b_Mistral Medium3.5_AfterJudge.json`
- `PE6201/results/d5b_gpt-4o-mini_AfterJudge.json`
- `PE6201/results/d5b_qwen3.8-flash_AfterJudge.json`

Additional result requiring model-name confirmation:

- `PE6201/results/d5b_Hy3_AfterJudge.json`

Keep `Hy3` separate from the primary four-model table until its full model identity and comparable evaluation settings are confirmed.

## 6 — Cost Model and result visualisation

- `PE6201/PE6201_A2_Cost_Model.xlsx` — cost-model tables, monthly cost, sensitivity, break-even analysis and cost levers.
- `PE6201_A2_Cost_Visualisation.ipynb` — reproducible charts and written interpretation.

Part 6 uses the Part 5 model results, Agent Loop token/turn evidence, configured operating limits, and the assignment's monthly-volume and fallback-cost assumptions.

## Shared files

These files support more than one workstream and should stay in their current locations:

- `backends.py` — Parts 1 and 5.
- `config.py` — Parts 1, 4, 5 and 6.
- `prompt.py` — Parts 1 and 3.
- `tools.py` — Parts 1, 2 and 3.
- `trace.py` and `logs/` — Parts 1, 5 and 6.

## Root-level parallel fixture package

These root files form an earlier or parallel fixture/tool package and are not byte-identical to the integrated files under `PE6201/project_files/`:

- `expected_outcomes_A.json`
- `make_fixtures_A.py`
- `test_tools.py`
- `tools.py`
- `DATA_FIELDS.md`

Do not delete or overwrite these files without comparing them with the integrated package and confirming ownership with the group.

## Recommended reading order

1. Read D0(a), D0(b), and D0(c).
2. Read the reference-data README and field guide.
3. Review the Agent Loop core files and integration guide.
4. Reproduce guardrail, failure and evaluation results.
5. Review the Part 6 workbook and Jupyter visualisation.
