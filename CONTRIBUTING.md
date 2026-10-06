# Contributing

Contributions are welcome through focused issues and pull requests. Use Python 3.11 and uv; do not commit local databases, secrets, or generated environments.

## Daily Development Contract

**After the multi-feature bootstrap MVP, each autonomous daily run must complete exactly one roadmap checkbox.** The initial staged MVP is the documented bootstrap exception; it established the tested foundation and checked only work present in that tree.

1. Pick the first dependency-ready unchecked item in `ROADMAP.md`; do not skip ahead without documenting the blocked dependency.
2. Use strict vertical TDD: write one behavioral test, run it and preserve expected RED evidence, implement the smallest end-to-end change, then preserve GREEN evidence.
3. Run the full regression suite, Ruff, compile checks, security checks, and a realistic entry-point/API smoke test.
4. Obtain independent review of the staged diff. Fix every security or logic blocker and repeat verification before checking the item.
5. Update README and relevant docs to match actual behavior, then change only that genuinely completed roadmap checkbox to `[x]`.
6. Create exactly one verified commit for the item and push the current branch to `origin`.
7. Never commit or publish failed, unreviewed, secret-bearing, or misleading work.
8. Report the roadmap item, commit SHA/message, test and quality-gate results, review verdict, and push result.

## Workflow

```bash
uv sync --all-groups
uv run pytest -q
uv run ruff check .
uv run python -m compileall -q src tests
git diff --check
git status --short
```

Tests must inject a temporary database path and must never read or write `./data/open-garage.db`. Keep monetary values as integer cents. Add migrations before changing persisted schemas after a release. Make error responses follow the documented envelope.

Keep commits narrow and use a descriptive conventional message such as `feat: add appointment creation`. By contributing, you agree that your work is licensed under MIT.
