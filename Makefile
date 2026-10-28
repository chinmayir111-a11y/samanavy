# SAMANVAY: institution complaint coordination (SIH26264 prototype)
#
#   make setup       install everything, create and seed the database
#   make api         run the API on :8010          (terminal 1)
#   make web         run the web app on :5173      (terminal 2)
#   make demo        production build of the web app on :4180 + API
#   make demo-check  green/red readiness checklist
#   make test        every test (backend, frontend; e2e with `make e2e`)

SHELL := /bin/bash
PYTHON := $(shell command -v python3.12 || command -v python3.13 || command -v python3.11 || command -v python3)
VENV := backend/.venv
PY := $(VENV)/bin/python
PSQL := $(shell command -v psql || ls $$(brew --prefix 2>/dev/null)/opt/postgresql@18/bin/psql 2>/dev/null)

.PHONY: fit evaluate help setup venv db migrate seed api web demo demo-check test test-backend test-web e2e test-email tamper untamper shots facts docker

help: ## Show the commands
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n",$$1,$$2}'

setup: venv db migrate seed ## Install, create database, migrate, seed
	cd frontend && npm install --no-audit --no-fund
	@[ -f .env ] || (cp .env.example .env && echo "Created .env from .env.example: fill in the SMTP keys and TEST_ALERT_EMAIL.")

venv:
	@[ -d $(VENV) ] || $(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install -q -r backend/requirements.txt

db: ## Create the database role and databases (local Postgres)
	-$(PSQL) -d postgres -qc "CREATE ROLE samanvay LOGIN PASSWORD 'samanvay' CREATEDB;"
	-$(PSQL) -d postgres -qc "CREATE DATABASE samanvay OWNER samanvay;"
	-$(PSQL) -d postgres -qc "CREATE DATABASE samanvay_test OWNER samanvay;"

migrate:
	cd backend && .venv/bin/alembic upgrade head

seed: ## Reset to the demo data (synthetic)
	cd backend && .venv/bin/python scripts/seed.py

api: ## API on :8010
	cd backend && .venv/bin/uvicorn app.main:app --port 8010 --reload

web: ## Web app (dev) on :5173
	cd frontend && npx vite --port 5173

demo: ## Production build on :4180 plus the API on :8010
	cd frontend && npx tsc -b && npx vite build
	cd backend && (.venv/bin/uvicorn app.main:app --port 8010 &) && cd ../frontend && npx vite preview --port 4180

demo-check: ## Green/red readiness checklist (add SEND=1 to also send a real test email)
	cd backend && .venv/bin/python scripts/demo_check.py $(if $(SEND),--send,)

test: test-backend test-web ## Backend + frontend tests

test-backend:
	cd backend && .venv/bin/python -m pytest -q

test-web:
	cd frontend && npx vitest run

e2e: ## Playwright smoke test of the demo path (needs api + web running; reseed after)
	cd frontend && npx playwright test

test-email: ## Send one real email to TEST_ALERT_EMAIL (API=https://... to test a deployed backend)
	cd backend && .venv/bin/python scripts/test_alert_email.py $(if $(API),--api $(API),)

tamper: ## Demo: change one audit row behind the app's back
	cd backend && .venv/bin/python scripts/tamper_audit.py

untamper: ## Put the tampered audit row back
	cd backend && .venv/bin/python scripts/tamper_audit.py --restore

shots: ## Screenshot every page at 360 and 1440 px into ./screenshots
	mkdir -p screenshots && cd frontend && node scripts/shoot.mjs ../screenshots && node scripts/shoot-college.mjs ../screenshots

fit: ## Check every page fits at 320-1440 px wide (needs api + web)
	cd frontend && node scripts/fit-check.mjs

facts: ## Recompute docs/SLIDE_FACTS.md from the seeded data
	cd backend && .venv/bin/python scripts/slide_facts.py

evaluate: ## Measure the matcher on the labelled synthetic set -> docs/MATCHING_METHOD.md numbers
	cd backend && .venv/bin/python scripts/evaluate_matcher.py

docker: ## One-command run with Docker on :8080
	docker compose up --build
