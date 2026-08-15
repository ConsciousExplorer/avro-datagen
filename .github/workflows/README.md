# CI/CD Pipelines

## Workflows

| File | Trigger | What it does |
|------|---------|-------------|
| `checks.yml` | called by the other two | Lint, format, typecheck, test. The single definition of "green" |
| `ci.yml` | Pull requests to `main` | Conventional PR title + `checks.yml` |
| `release.yml` | Push to `main` | `checks.yml` + docs deploy + release-please; on a release, tag + GitHub Release + PyPI |

## Pipeline flow

```
PR opened / retitled / pushed ──> ci.yml
                                    |
                                    +-- pr-title    (conventional title, else fail)
                                    +-- check       ──> checks.yml
                                    |
                                  All pass? ──> Ready to merge (squash)


Push to main ──> release.yml
                   |
                   +-- check          ──> checks.yml
                   +-- docs           ──> mkdocs build ──> GitHub Pages   [every push]
                   +-- release-please ──> keeps a release PR open, up to date
                         |
                         |  ...that release PR gets merged ──> push to main ──>
                         |
                         +-- tag + GitHub Release created
                               |  release_created == true
                               +-- build   (uv build, version/tag cross-check)
                               +-- publish (PyPI, trusted publishing)
```

Docs, tagging and publishing all happen in **one run**. That is not a style
choice: a tag or release created with `GITHUB_TOKEN` deliberately does not
trigger another workflow, so the PyPI jobs must sit in the same run as
release-please, gated on its `release_created` output.

## How releases work

**There is no manual tagging step.** Merge normal PRs; release-please watches
`main` and keeps a PR titled `chore(main): release X.Y.Z` open, continuously
updated with the version bump and the changelog entries your commits imply.
When you want to ship, merge that PR. That single merge cuts the release:

1. `pyproject.toml` and `uv.lock` are bumped
2. `CHANGELOG.md` gains a new section (existing entries are never rewritten)
3. the `vX.Y.Z` tag is created
4. a GitHub Release is published with those notes
5. the package is built and uploaded to PyPI
6. the docs are redeployed

### What decides the version

The conventional-commit types on the PR titles merged since the last release:

| Title prefix | Changelog section | Version effect (pre-1.0) |
|--------------|-------------------|--------------------------|
| `feat:` | Added | minor — `0.4.1` → `0.5.0` |
| `fix:` | Fixed | patch — `0.4.1` → `0.4.2` |
| `perf:` `refactor:` `revert:` `deps:` | Changed | patch |
| `docs:` | Documentation | patch |
| `chore:` `style:` `test:` `build:` `ci:` | hidden | patch |
| any with `!`, e.g. `feat!:` | flagged as breaking | minor while below 1.0 |

`ci.yml` fails a PR whose title is not one of these, because an unrecognised
title would silently drop the change from the release notes.

To override the computed version, put `Release-As: 1.0.0` in a commit body.

### Editing the notes

The generated changelog entries are just PR titles. If a release deserves
richer prose — as most do here — edit `CHANGELOG.md` directly in the
release PR before merging it. release-please will not overwrite your edits.

## Branching rules

- **`main` is protected** — no direct pushes, PRs required, `check` must pass
- All changes go through feature branches + pull requests
- PRs are **squash-merged**: the PR title becomes the commit subject on `main`,
  and therefore the changelog line

## Branch naming

| Prefix | Use | Example |
|--------|-----|---------|
| `feat/` | New feature | `feat/decimal-support` |
| `fix/` | Bug fix | `fix/union-null-handling` |
| `docs/` | Documentation only | `docs/faker-examples` |
| `chore/` | Tests, refactoring, housekeeping | `chore/add-map-tests` |
| `ci/` | Pipeline changes | `ci/release-please` |
| `hotfix/` | Urgent production fix | `hotfix/crash-on-empty-schema` |

There is no `release/` prefix any more — release branches are the bot's job.

## How to contribute

```bash
# 1. Create a branch
git checkout -b feat/your-feature

# 2. Make changes, commit
git add <files>
git commit -m "feat: description of change"

# 3. Push and open a PR — the title is what matters, it becomes the
#    squash commit subject and the changelog line
git push -u origin feat/your-feature
gh pr create --title "feat: description of change" --body "Closes #123"

# 4. CI runs automatically — merge after it passes
```

## Dependency updates

`.github/dependabot.yml` opens grouped monthly PRs for GitHub Actions and for
the Python lockfile. Keeping actions current is what prevents another round of
"Node.js 20 is deprecated" warnings — the pinned versions are only ever as
fresh as the last bump.

Note that `astral-sh/setup-uv` publishes exact versions only (no floating `v10`
tag, unlike the `actions/*` repos), so it is pinned to a full version and relies
on Dependabot to move.

## Security notes

- `build` and `publish` are separate jobs — only `publish` has `id-token: write`
- PyPI publishing uses [trusted publishing](https://docs.pypi.org/trusted-publishers/) (no API tokens), and emits PEP 740 attestations
- `publish` runs in a `pypi` environment with deployment protection rules
- `build` cross-checks the built version against the tag before uploading
- Workflows default to `permissions: contents: read`; each job widens only what it needs
