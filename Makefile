.PHONY: help start-build start stop restart logs delete frontend

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

start-build: ## Build and start backend containers
	cd backend && docker compose up --build -d

start: ## Start backend containers
	cd backend && docker compose up -d

frontend: ## Start frontend dev server
	cd frontend && npm run dev

stop: ## Stop backend containers
	cd backend && docker compose down

restart: ## Restart backend containers
	$(MAKE) stop
	$(MAKE) start

logs: ## Show backend logs
	cd backend && docker compose logs -f

delete: ## Remove containers, volumes, and images
	cd backend && docker compose down -v --rmi all --remove-orphans

seed: ## Seed the database with initial data
	cd backend && docker compose exec web python manage.py seed_demo
