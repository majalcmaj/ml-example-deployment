
.PHONY: test
test: 
	uv run pytest

.PHONY: check
check: 
	uv run ruff check
	$(MAKE) test

