# Part 1 — Agent Loop and integration

The shared implementation is in `../shared_runtime/`:

- `agent.py` — ReAct loop and orchestration
- `backends.py` — scripted and live model backends
- `config.py` — backend, model, limits and cost settings
- `prompt.py` — system prompt and tool descriptors
- `trace.py` — trace and decision logging
- `tools.py` — claim-processing tools

The `logs/` directory contains the submitted run evidence.
