# CLAUDE.md — Ymerflow Plugin SDK

This file provides guidance to Claude Code when working with this repository.

## Project Overview

This is the shared SDK for building Nagelfluh/Ymerflow plugins. It provides:
- `ymerflow_plugin_build` — Python build tooling that compiles frontend plugin source packages via Vite + Module Federation.
- `js/` — JavaScript/TypeScript helpers that plugin frontend packages can import from the SDK.
- `tests/` — test suite for the build tooling.

## Development Workflow — Critical Rules

1. **Plan before implementing** - Every non-trivial change requires a written plan first. The full workflow is:
   1. **Create a plan file** in `docs/plans/` (e.g., `docs/plans/my-feature.md`) before writing any code. Read existing plans for the expected structure.
   2. **Discuss all design decisions** with the user before finalising the plan. Claude suggests options with trade-offs; the user decides. Never take design or architecture decisions unilaterally.
   3. **Wait for the user to commit the plan** to git. The plan must be in the repository before implementation begins.
   4. **Implement in a separate session** — implementation only starts after the committed plan exists.
   5. **Move the plan to `docs/plans/done/`** when implementation is complete. The user commits the code changes and the plan move together in the same commit.

2. **DO NOT commit to git** - Never create git commits or push changes. The user handles all version control.

3. **Package installation** - Update `setup.py` and ask the user for approval before adding new dependencies.

## Key Source Locations

- Python build tooling: `ymerflow_plugin_build/`
- JavaScript SDK helpers: `js/`
- Tests: `tests/`
- Package metadata and entry-point registration: `setup.py`
