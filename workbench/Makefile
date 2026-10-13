# Canonical package checks; manuscript validation uses the project's Makefile.
PYTHON ?= python3
.PHONY: test portability check audit-reference upgrade-reference
test:
	$(PYTHON) -B -m unittest discover -s tests -v
portability:
	$(PYTHON) -B tests/portability.py
check: test portability
audit-reference:  # how the reference differs from this release (runtime files; exit 1 if any differ)
	$(PYTHON) -B latex-ai-init diff ..
upgrade-reference:  # refresh the reference's runtime files; its policy, Makefile and editor files are edited by hand (docs/upgrading.md)
	$(PYTHON) -B latex-ai-init runtime ..
