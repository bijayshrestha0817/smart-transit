# Smart Transit AI — developer task runner.
#
# Two workflows:
#   • Local loop (fast): backend uses backend/.venv (sqlite test settings), frontend uses npm.
#   • Docker stack:      the full compose stack (postgres, redis, web, ws, worker, beat).
#
# docker-compose.yml lives at the repo ROOT, so all compose targets run from here.
# Run `make` (or `make help`) to list everything.

# NOTE: no inline `#` comments on the assignments below — make folds the whitespace
# before an inline comment into the value, which would corrupt $(PYBIN) paths.
BACKEND := backend
FRONTEND := frontend
# VENV is relative to $(BACKEND); PYBIN holds its binaries (used after `cd $(BACKEND)`).
VENV := .venv
PYBIN := $(VENV)/bin
# docker-compose.yml is at the repo root, so DC runs from here.
DC := docker compose
TEST_ENV := DJANGO_SETTINGS_MODULE=config.settings.test

.DEFAULT_GOAL := help
.PHONY: help install be-install fe-install \
        test lint fmt fmt-check check schema migrations-check \
        fe-dev frontend fe-lint fe-typecheck fe-test fe-build \
        test-all lint-all ci verify clean clean-all \
        build start-build start up stop down restart logs ps delete \
        migrate makemigrations seed superuser sh dbshell

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'

# ── Setup ─────────────────────────────────────────────────────────────────────
install: be-install fe-install ## Install backend (venv) + frontend deps

be-install: ## Create backend/.venv and install dev requirements
	cd $(BACKEND) && python3 -m venv $(VENV) && $(PYBIN)/pip install --upgrade pip && $(PYBIN)/pip install -r requirements/dev.txt

fe-install: ## Install frontend deps (npm ci)
	cd $(FRONTEND) && npm ci

# ── Backend (local venv — no Docker needed) ───────────────────────────────────
test: ## Run the backend test suite (pytest, sqlite test settings)
	cd $(BACKEND) && $(PYBIN)/python -m pytest

lint: ## Ruff lint the backend
	cd $(BACKEND) && $(PYBIN)/ruff check .

fmt: ## Ruff auto-format the backend
	cd $(BACKEND) && $(PYBIN)/ruff format .

fmt-check: ## Ruff format check (no writes) — CI gate
	cd $(BACKEND) && $(PYBIN)/ruff format --check .

check: ## Django system check
	cd $(BACKEND) && $(TEST_ENV) $(PYBIN)/python manage.py check

schema: ## Validate the OpenAPI schema (--fail-on-warn)
	cd $(BACKEND) && $(TEST_ENV) $(PYBIN)/python manage.py spectacular --validate --fail-on-warn >/dev/null && echo "schema OK"

migrations-check: ## Fail if a model change is missing a migration
	cd $(BACKEND) && $(TEST_ENV) $(PYBIN)/python manage.py makemigrations --check --dry-run

# ── Frontend (local npm) ──────────────────────────────────────────────────────
fe-dev frontend: ## Start the frontend dev server (Next.js)
	cd $(FRONTEND) && npm run dev

fe-lint: ## ESLint the frontend
	cd $(FRONTEND) && npm run lint

fe-typecheck: ## TypeScript type-check the frontend
	cd $(FRONTEND) && npm run typecheck

fe-test: ## Run the frontend unit tests (vitest)
	cd $(FRONTEND) && npm run test

fe-build: ## Production build the frontend (Next.js)
	cd $(FRONTEND) && npm run build

# ── Aggregate / CI ────────────────────────────────────────────────────────────
test-all: test fe-test ## Run backend + frontend tests

lint-all: lint fe-lint ## Lint backend + frontend

ci: lint fmt-check check test fe-lint fe-typecheck fe-test fe-build ## Mirror the GitHub Actions CI gates

verify: ci schema migrations-check ## Full local gate (CI + schema + migration guard)

clean: ## Remove Python caches (pycache, .pytest_cache, .ruff_cache)
	find $(BACKEND) -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf $(BACKEND)/.pytest_cache $(BACKEND)/.ruff_cache

clean-all: clean ## Also remove backend/.venv and frontend/node_modules
	rm -rf $(BACKEND)/$(VENV) $(FRONTEND)/node_modules

# ── Docker stack (postgres, redis, web, ws, worker, beat) ─────────────────────
build start-build: ## Build images and start the stack (detached)
	$(DC) up --build -d

start up: ## Start the stack (detached)
	$(DC) up 

stop down: ## Stop the stack
	$(DC) down

restart: ## Restart the stack
	$(MAKE) stop
	$(MAKE) start

logs: ## Tail stack logs
	$(DC) logs -f

ps: ## Show stack container status
	$(DC) ps

delete: ## Remove containers, volumes, and images (destructive)
	$(DC) down -v --rmi all --remove-orphans

# ── Database / management (via the Docker stack) ──────────────────────────────
migrate: ## Apply database migrations
	$(DC) run --rm migrate

makemigrations: ## Generate new migrations
	$(DC) run --rm web python manage.py makemigrations

seed: ## Seed the database with demo data
	$(DC) run --rm web python manage.py seed_demo

superuser: ## Create a Django superuser (interactive)
	$(DC) run --rm web python manage.py createsuperuser

sh: ## Shell into the running web container
	$(DC) exec web sh

dbshell: ## Open a database shell
	$(DC) run --rm web python manage.py dbshell
