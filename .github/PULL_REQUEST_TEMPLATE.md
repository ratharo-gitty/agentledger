## Summary

<!-- What changed and why? Link related issues with Fixes #N when applicable. -->

## Checklist

- [ ] `pytest -v` passes locally
- [ ] `ruff check .` is clean
- [ ] New/changed public APIs use strict type hints and Pydantic v2 (`model_dump` / `model_validate`)
- [ ] Documentation updated (`README.md` / `CONTRIBUTING.md` / docstrings) when behavior changes
- [ ] No secrets, `.env`, or `*.db` files included
- [ ] Provenance Firewall / cascade semantics preserved (or intentionally documented if changed)

## Test plan

<!-- How did you verify? e.g. agentledger demo, new unit tests, MCP tool smoke. -->

-
