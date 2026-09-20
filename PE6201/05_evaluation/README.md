# Part 5 — Evaluation Harness and Model Battery

- `scripts/run_eval.py` runs the reproducible scripted evaluation or a configured live model.
- `judging_prompt.md` is the judgement-grader prompt.
- `results/` contains the scripted baseline and submitted live-model results.
- The reusable harness is `../shared_runtime/harness.py`.

Run the free deterministic baseline from the repository root:

```bash
python PE6201/05_evaluation/scripts/run_eval.py
```
