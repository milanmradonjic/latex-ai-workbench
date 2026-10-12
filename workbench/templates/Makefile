# The project configuration is .latex-ai.json. Keep validation in one place.
PYTHON ?= python3
.DEFAULT_GOAL := build
.PHONY: build lint check
build: latex-ai-build
lint:
	@$(PYTHON) .latex-ai/workbench.py lint
check:
	@$(PYTHON) .latex-ai/workbench.py check
