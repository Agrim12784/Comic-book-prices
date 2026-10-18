.PHONY: install test lint ingest
install:
	pip install -e ".[dev]"
test:
	pytest
lint:
	ruff check src tests
ingest:
	comicprice ingest --source ebay --query "$(Q)" --limit 50
