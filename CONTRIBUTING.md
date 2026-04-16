# Contributing

Thanks for taking the time to contribute to avro-datagen.

## Getting started

```bash
git clone https://github.com/ConsciousExplorer/avro-datagen.git
cd avro-datagen
uv sync --all-extras
```

Run the full check suite before opening a PR:

```bash
make check   # lint + typecheck + tests
```

Individual commands:

```bash
make lint       # ruff check
make format     # ruff format
make typecheck  # pyright
make test       # pytest with coverage
```

## Making changes

- Keep changes focused. One logical change per PR.
- Add or update tests for any new behavior.
- All checks in `make check` must pass.
- Follow the existing code style — ruff and pyright enforce it.

## Submitting a PR

1. Fork the repo and create a branch from `main`.
2. Make your changes.
3. Run `make check` and confirm everything passes.
4. Open a pull request against `main` using the PR template.

## Reporting a bug

Open an issue using the **Bug report** template. Include a minimal schema and the command you ran so the problem is reproducible.

## Suggesting a feature

Open an issue using the **Feature request** template. Describe the use case, not just the solution.

## License

By contributing you agree that your changes will be licensed under the [MIT License](LICENSE).
