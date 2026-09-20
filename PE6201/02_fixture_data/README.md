# Part 2 — Fixture data and tool functions

- `reference_data/` is the integrated Problem A fixture package used by the system.
- `DATA_FIELDS.md` documents the fixture fields.
- `legacy_root_package/` preserves the earlier root-level package for comparison; it is not the active runtime copy.
- The active tool implementation is `../shared_runtime/tools.py`.

Validate the integrated data with:

```bash
python PE6201/02_fixture_data/reference_data/check_my_data.py
```
