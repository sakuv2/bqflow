#!/usr/bin/env make

default:
	$(MAKE) help

init: ## dev init
	@echo DEV INIT
	poetry install
	pre-commit install

x: ## total check for develop
	@echo START check
	@pre-commit run --all-files

t: ## run test
	@echo TEST START
	@poetry run pytest --cov=src --cov-report xml --cov-report=term --disable-warnings

lf: ## run test only last failed
	@echo TEST START
	@poetry run pytest -s --disable-warnings --lf

help: ## show help
	@echo Usage: make [target]
	@echo $(\n)
	@echo Targets:
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
