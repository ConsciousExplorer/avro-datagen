# CI/CD Pipelines

## Workflows

| File | Trigger | What it does |
|------|---------|-------------|
| `ci.yml` | Pull requests to `main` | Lint, format, typecheck, test |
| `publish.yml` | Push to `main` or `v*` tag | CI checks + docs deploy + PyPI publish (tags only) |

## Pipeline flow

```
PR opened/updated ──> ci.yml
                        |
                        +-- ruff check (lint)
                        +-- ruff format --check
                        +-- pyright (typecheck)
                        +-- pytest (tests + coverage)
                        |
                      All pass? ──> Ready to merge


Push to main ──> publish.yml
                   |
                   +-- check (same as ci.yml)
                   +-- docs-build ──> docs-deploy (GitHub Pages)


Tag v* pushed ──> publish.yml
                    |
                    +-- check (same as ci.yml)
                    +-- docs-build ──> docs-deploy (GitHub Pages)
                    +-- build (uv build) ──> publish (PyPI via trusted publishing)
```

## Branching rules

- **`main` is protected** -- no direct pushes, PRs required
- All changes go through feature branches + pull requests
- CI must pass before merging

## Branch naming

| Prefix | Use | Example |
|--------|-----|---------|
| `feat/` | New feature | `feat/decimal-support` |
| `fix/` | Bug fix | `fix/union-null-handling` |
| `chore/` | Tests, docs, CI, refactoring | `chore/add-map-tests` |
| `hotfix/` | Urgent production fix | `hotfix/crash-on-empty-schema` |

## How to contribute

```bash
# 1. Create a branch
git checkout -b feat/your-feature

# 2. Make changes, commit
git add <files>
git commit -m "feat: Description of change"

# 3. Push and open a PR
git push -u origin feat/your-feature
gh pr create --title "feat: Description" --body "Closes #123"

# 4. CI runs automatically -- merge after it passes
```

## How releases work

Releases are triggered by pushing a version tag. Only maintainers do this.

```bash
# 1. Update version in pyproject.toml and CHANGELOG.md
# 2. Commit and merge to main
# 3. Tag and push
git tag v0.3.0
git push origin v0.3.0
# 4. CI builds and publishes to PyPI automatically
```

## Security notes

- The `build` and `publish` jobs are separate -- only `publish` has `id-token: write` permission
- PyPI publishing uses [trusted publishing](https://docs.pypi.org/trusted-publishers/) (no API tokens)
- The `publish` job runs in a `pypi` environment with deployment protection rules
