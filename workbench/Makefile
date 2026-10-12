# Canonical package checks; manuscript validation uses the project's Makefile.
PYTHON ?= python3
.PHONY: test portability check audit-reference upgrade-reference handbook
test:
	$(PYTHON) -B -m unittest discover -s tests -v
portability:
	$(PYTHON) -B tests/portability.py
check: test portability
audit-reference:
	$(PYTHON) -B latex-ai-init audit .. --json
upgrade-reference:
	$(PYTHON) -B latex-ai-init upgrade ..
handbook:  # regenerate docs/handbook.md and docs/handbook.html from handbook.py
	$(PYTHON) -B -c "import handbook, pathlib; pathlib.Path('docs/handbook.md').write_text(handbook.render_markdown(), encoding='utf-8'); pathlib.Path('docs/handbook.html').write_text(handbook.render_html(), encoding='utf-8')"
