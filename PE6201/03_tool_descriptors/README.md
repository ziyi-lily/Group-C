# Part 3 — Tool descriptors and Failure 2

- `docs/` contains the descriptor design, grading rubric and Failure 2 explanation.
- `scripts/` contains the token measurement and failure reproduction scripts.
- `results/` contains the V1/V2 evidence and machine-readable results.
- `requirements.txt` contains the additional dependency for token measurement.

Run from the repository root:

```bash
python -m pip install -r PE6201/03_tool_descriptors/requirements.txt
python PE6201/03_tool_descriptors/scripts/measure_tool_return_tokens.py
python PE6201/03_tool_descriptors/scripts/run_failures.py 2
```
