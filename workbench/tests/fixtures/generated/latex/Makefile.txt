# The project configuration is .latex-ai.json. Keep validation in one place.
PYTHON ?= python3
.DEFAULT_GOAL := build
.PHONY: build lint check
build: latex-ai-build
lint:
	@$(PYTHON) .latex-ai/workbench.py lint
check:
	@$(PYTHON) .latex-ai/workbench.py check
export ISSUE_NOTE ISSUE_COMMAND
export DOC
.PHONY: latex-ai-validate
latex-ai-validate:
	@$(PYTHON) .latex-ai/workbench.py validate
.PHONY: validate
validate: latex-ai-validate
.PHONY: latex-ai-plan
latex-ai-plan:
	@$(PYTHON) .latex-ai/workbench.py plan
.PHONY: validation-plan
validation-plan: latex-ai-plan
.PHONY: latex-ai-status
latex-ai-status:
	@$(PYTHON) .latex-ai/workbench.py status
.PHONY: status
status: latex-ai-status
.PHONY: latex-ai-doctor
latex-ai-doctor:
	@$(PYTHON) .latex-ai/workbench.py doctor
.PHONY: doctor
doctor: latex-ai-doctor
.PHONY: latex-ai-help
latex-ai-help:
	@$(PYTHON) .latex-ai/workbench.py help
.PHONY: help
help: latex-ai-help
.PHONY: latex-ai-guide
latex-ai-guide:
	@$(PYTHON) .latex-ai/workbench.py guide
.PHONY: guide
guide: latex-ai-guide
.PHONY: latex-ai-build
latex-ai-build:
	@$(PYTHON) .latex-ai/workbench.py build --document "$$DOC"
.PHONY: latex-ai-build-all
latex-ai-build-all:
	@$(PYTHON) .latex-ai/workbench.py build --all
.PHONY: all
all: latex-ai-build-all
.PHONY: latex-ai-lint
latex-ai-lint:
	@$(PYTHON) .latex-ai/workbench.py lint --document "$$DOC"
.PHONY: document-lint
document-lint: latex-ai-lint
.PHONY: latex-ai-documents
latex-ai-documents:
	@$(PYTHON) .latex-ai/workbench.py documents
.PHONY: documents
documents: latex-ai-documents
.PHONY: latex-ai-document-check
latex-ai-document-check:
	@$(PYTHON) .latex-ai/workbench.py document-check --document "$$DOC"
.PHONY: document-check
document-check: latex-ai-document-check
.PHONY: latex-ai-lint-baseline
latex-ai-lint-baseline:
	@$(PYTHON) .latex-ai/workbench.py lint-baseline --document "$$DOC"
.PHONY: lint-baseline
lint-baseline: latex-ai-lint-baseline
.PHONY: latex-ai-bib-check
latex-ai-bib-check:
	@$(PYTHON) .latex-ai/workbench.py bib-check --document "$$DOC"
.PHONY: bib-check
bib-check: latex-ai-bib-check
.PHONY: latex-ai-pdf-artifact
latex-ai-pdf-artifact:
	@$(PYTHON) .latex-ai/workbench.py artifact --document "$$DOC"
.PHONY: pdf-artifact
pdf-artifact: latex-ai-pdf-artifact
.PHONY: latex-ai-clean
latex-ai-clean:
	@$(PYTHON) .latex-ai/workbench.py clean --document "$$DOC"
.PHONY: clean
clean: latex-ai-clean
.PHONY: latex-ai-modules
latex-ai-modules:
	@$(PYTHON) .latex-ai/workbench.py modules
.PHONY: modules
modules: latex-ai-modules
.PHONY: latex-ai-issue
latex-ai-issue:
	@$(PYTHON) .latex-ai/workbench.py issue --note "$$ISSUE_NOTE" --command "$$ISSUE_COMMAND"
.PHONY: issue
issue: latex-ai-issue
