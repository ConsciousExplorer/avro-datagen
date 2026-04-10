.PHONY: test app docs docs-build build clean lint format typecheck check

RUN := $(shell command -v uv > /dev/null 2>&1 && echo "uv run" || echo "")

test:
	$(RUN) pytest -v --cov=avro_datagen --cov-report=term-missing --cov-branch

lint:
	$(RUN) ruff check src/ tests/

format:
	$(RUN) ruff format src/ tests/

typecheck:
	$(RUN) pyright

check: lint typecheck test

app:
	$(RUN) streamlit run app.py

docs:
	$(RUN) mkdocs serve

docs-build:
	$(RUN) mkdocs build

build:
	uv build

clean:
	rm -rf dist/ site/ .coverage
