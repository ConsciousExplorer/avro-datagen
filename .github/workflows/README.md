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
| `release/` | Version bump + changelog for a release cut | `release/v0.3.2` |

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
# 1. Cut a release branch from up-to-date main
git checkout main && git pull
git checkout -b release/v0.3.2

# 2. Bump version in pyproject.toml, add a section to CHANGELOG.md
# 3. Commit, push, open a PR release/v0.3.2 -> main, merge it
# 4. Tag the merge commit on main and push the tag
git checkout main && git pull
git tag -a v0.3.2 -m "v0.3.2"
git push origin v0.3.2
# 5. CI builds and publishes to PyPI automatically
```

**Tag after the merge, not before.** The tag must point at the merge commit
on `main` so the `publish.yml` tag-triggered job builds exactly what's on
`main`. Tagging the release branch before merge would publish a commit that
isn't on `main`.

## Security notes

- The `build` and `publish` jobs are separate -- only `publish` has `id-token: write` permission
- PyPI publishing uses [trusted publishing](https://docs.pypi.org/trusted-publishers/) (no API tokens)
- The `publish` job runs in a `pypi` environment with deployment protection rules
