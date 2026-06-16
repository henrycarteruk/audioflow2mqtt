.DEFAULT_GOAL := help
.PHONY: help install run lint format typecheck test coverage hooks docker

IMAGE ?= audioflow2mqtt:latest

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

install: ## Create the virtualenv and install pinned dependencies
	uv sync

run: ## Run the gateway
	uv run python -m audioflow2mqtt

lint: ## Check code with ruff
	uv run ruff check .

format: ## Format code with ruff
	uv run ruff format .

typecheck: ## Run the static type checker
	uv run mypy audioflow2mqtt

test: ## Run the test suite
	uv run pytest

coverage: ## Run the test suite with a coverage report
	uv run pytest --cov=audioflow2mqtt --cov-report=term-missing

hooks: ## Install the pre-commit hooks (ruff lint + format on commit)
	uv run pre-commit install

docker: ## Build the Docker image
	docker build -t $(IMAGE) .
