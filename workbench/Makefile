# Canonical package checks; manuscript validation uses the project's Makefile.
PYTHON ?= python3
.PHONY: test portability check audit-reference upgrade-reference
test:
	$(PYTHON) -B -m unittest discover -s tests -v
portability:
	$(PYTHON) -B tests/portability.py
check: test portability
audit-reference:
	$(PYTHON) -B latex-ai-init audit .. --json
upgrade-reference:
	$(PYTHON) -B latex-ai-init upgrade ..
