# The project configuration is .latex-ai.json. Keep validation in one place.
PYTHON ?= python3
.DEFAULT_GOAL := build
export ISSUE_NOTE ISSUE_COMMAND SNAPSHOT_NOTE DOC
.PHONY: check
check:
	@$(PYTHON) .latex-ai/workbench.py check
.PHONY: validate
validate:
	@$(PYTHON) .latex-ai/workbench.py validate
.PHONY: validation-plan
validation-plan:
	@$(PYTHON) .latex-ai/workbench.py plan
.PHONY: status
status:
	@$(PYTHON) .latex-ai/workbench.py status
.PHONY: doctor
doctor:
	@$(PYTHON) .latex-ai/workbench.py doctor
.PHONY: help
help:
	@$(PYTHON) .latex-ai/workbench.py help
.PHONY: guide
guide:
	@$(PYTHON) .latex-ai/workbench.py guide
.PHONY: build
build:
	@$(PYTHON) .latex-ai/workbench.py build --document "$$DOC"
.PHONY: all
all:
	@$(PYTHON) .latex-ai/workbench.py build --all
.PHONY: lint
lint:
	@$(PYTHON) .latex-ai/workbench.py lint --document "$$DOC"
.PHONY: documents
documents:
	@$(PYTHON) .latex-ai/workbench.py documents
.PHONY: document-check
document-check:
	@$(PYTHON) .latex-ai/workbench.py document-check --document "$$DOC"
.PHONY: lint-baseline
lint-baseline:
	@$(PYTHON) .latex-ai/workbench.py lint-baseline --document "$$DOC"
.PHONY: bib-check
bib-check:
	@$(PYTHON) .latex-ai/workbench.py bib-check --document "$$DOC"
.PHONY: pdf-artifact
pdf-artifact:
	@$(PYTHON) .latex-ai/workbench.py artifact --document "$$DOC"
.PHONY: clean
clean:
	@$(PYTHON) .latex-ai/workbench.py clean --document "$$DOC"
.PHONY: issue
issue:
	@$(PYTHON) .latex-ai/workbench.py issue --note "$$ISSUE_NOTE" --command "$$ISSUE_COMMAND"
.PHONY: snapshot
snapshot:
	@$(PYTHON) .latex-ai/workbench.py snapshot --note="$$SNAPSHOT_NOTE"
.PHONY: snapshots
snapshots:
	@$(PYTHON) .latex-ai/workbench.py snapshots
