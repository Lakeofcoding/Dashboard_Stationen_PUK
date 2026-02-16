# Makefile für PUK Dashboard
# Vereinfacht häufige Entwicklungs- und Deployment-Aufgaben

.PHONY: help install dev build up down logs clean test health

# Farben für Output
GREEN  := $(shell tput -Txterm setaf 2)
YELLOW := $(shell tput -Txterm setaf 3)
WHITE  := $(shell tput -Txterm setaf 7)
RESET  := $(shell tput -Txterm sgr0)

help: ## Zeigt diese Hilfe an
	@echo ''
	@echo '${GREEN}PUK Dashboard - Verfügbare Befehle:${RESET}'
	@echo ''
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  ${YELLOW}%-15s${RESET} %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ''

install: ## Installiert alle Dependencies (Backend + Frontend)
	@echo "${GREEN}Installiere Backend-Dependencies...${RESET}"
	cd backend && python -m venv .venv && .venv/bin/pip install -r requirements.txt
	@echo "${GREEN}Installiere Frontend-Dependencies...${RESET}"
	cd frontend && npm ci
	@echo "${GREEN}✓ Installation abgeschlossen${RESET}"

dev: ## Startet Entwicklungsumgebung (Backend + Frontend)
	@echo "${GREEN}Starte Entwicklungsumgebung...${RESET}"
	@echo "${YELLOW}Backend: http://localhost:8000${RESET}"
	@echo "${YELLOW}Frontend: http://localhost:5173${RESET}"
	@trap 'kill 0' EXIT; \
	cd backend && DASHBOARD_ALLOW_DEMO_AUTH=1 DASHBOARD_DEBUG=1 .venv/bin/uvicorn main:app --reload & \
	cd frontend && npm run dev

dev-backend: ## Startet nur Backend (Entwicklung)
	@echo "${GREEN}Starte Backend...${RESET}"
	cd backend && DASHBOARD_ALLOW_DEMO_AUTH=1 DASHBOARD_DEBUG=1 .venv/bin/uvicorn main:app --reload

dev-frontend: ## Startet nur Frontend (Entwicklung)
	@echo "${GREEN}Starte Frontend...${RESET}"
	cd frontend && npm run dev

build: ## Baut Docker-Images
	@echo "${GREEN}Baue Docker-Images...${RESET}"
	docker-compose build --no-cache
	@echo "${GREEN}✓ Build abgeschlossen${RESET}"

up: ## Startet alle Container (Produktion)
	@echo "${GREEN}Starte Container...${RESET}"
	docker-compose up -d
	@echo "${GREEN}✓ Container gestartet${RESET}"
	@echo "${YELLOW}Frontend: http://localhost:8080${RESET}"
	@echo "${YELLOW}Backend:  http://localhost:8000${RESET}"
	@$(MAKE) health

down: ## Stoppt alle Container
	@echo "${YELLOW}Stoppe Container...${RESET}"
	docker-compose down
	@echo "${GREEN}✓ Container gestoppt${RESET}"

restart: down up ## Neustart aller Container

logs: ## Zeigt Logs aller Container
	docker-compose logs -f --tail=100

logs-backend: ## Zeigt nur Backend-Logs
	docker-compose logs -f backend --tail=100

logs-frontend: ## Zeigt nur Frontend-Logs
	docker-compose logs -f frontend --tail=100

logs-db: ## Zeigt nur Datenbank-Logs
	docker-compose logs -f postgres --tail=100

clean: ## Löscht Container, Volumes und Build-Artefakte
	@echo "${YELLOW}Lösche Container und Volumes...${RESET}"
	docker-compose down -v
	@echo "${YELLOW}Lösche Build-Artefakte...${RESET}"
	rm -rf backend/.venv backend/__pycache__ backend/**/__pycache__
	rm -rf frontend/node_modules frontend/dist
	@echo "${GREEN}✓ Cleanup abgeschlossen${RESET}"

test: ## Führt alle Tests aus
	@echo "${GREEN}Führe Backend-Tests aus...${RESET}"
	cd backend && .venv/bin/pytest -v
	@echo "${GREEN}Führe Frontend-Tests aus...${RESET}"
	cd frontend && npm run test || true
	@echo "${GREEN}✓ Tests abgeschlossen${RESET}"

test-backend: ## Führt nur Backend-Tests aus
	cd backend && .venv/bin/pytest -v

test-coverage: ## Backend-Tests mit Coverage-Report
	cd backend && .venv/bin/pytest --cov=app --cov-report=html --cov-report=term
	@echo "${GREEN}Coverage-Report: backend/htmlcov/index.html${RESET}"

lint: ## Code-Linting (Backend + Frontend)
	@echo "${GREEN}Backend Linting...${RESET}"
	cd backend && .venv/bin/black app/ --check || true
	cd backend && .venv/bin/pylint app/ || true
	@echo "${GREEN}Frontend Linting...${RESET}"
	cd frontend && npm run lint || true

format: ## Code-Formatierung
	@echo "${GREEN}Formatiere Backend-Code...${RESET}"
	cd backend && .venv/bin/black app/
	@echo "${GREEN}Formatiere Frontend-Code...${RESET}"
	cd frontend && npm run lint --fix || true

health: ## Prüft Health-Status
	@echo "${GREEN}Prüfe Health-Status...${RESET}"
	@curl -s http://localhost:8000/health | python -m json.tool || echo "${YELLOW}Backend nicht erreichbar${RESET}"

db-shell: ## Öffnet Datenbank-Shell
	@echo "${GREEN}Öffne Datenbank-Shell...${RESET}"
	docker-compose exec postgres psql -U dashboard_user -d puk_dashboard

db-migrate: ## Führt Datenbank-Migrationen aus
	@echo "${GREEN}Führe Migrationen aus...${RESET}"
	docker-compose exec backend alembic upgrade head
	@echo "${GREEN}✓ Migrationen abgeschlossen${RESET}"

db-migration-create: ## Erstellt neue Migration (NAME=<name> angeben)
	@if [ -z "$(NAME)" ]; then \
		echo "${YELLOW}Fehler: Bitte NAME angeben${RESET}"; \
		echo "Beispiel: make db-migration-create NAME='add_user_table'"; \
		exit 1; \
	fi
	docker-compose exec backend alembic revision --autogenerate -m "$(NAME)"

db-reset: ## Setzt Datenbank zurück (ACHTUNG: Löscht alle Daten!)
	@echo "${YELLOW}WARNUNG: Dies löscht alle Daten!${RESET}"
	@read -p "Fortfahren? (yes/no): " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		docker-compose down -v; \
		docker-compose up -d; \
		echo "${GREEN}✓ Datenbank zurückgesetzt${RESET}"; \
	else \
		echo "${YELLOW}Abgebrochen${RESET}"; \
	fi

ps: ## Zeigt Status aller Container
	docker-compose ps

stats: ## Zeigt Ressourcen-Nutzung
	docker stats --no-stream

shell-backend: ## Öffnet Shell im Backend-Container
	docker-compose exec backend /bin/bash

shell-frontend: ## Öffnet Shell im Frontend-Container
	docker-compose exec frontend /bin/sh

shell-db: ## Öffnet Shell im DB-Container
	docker-compose exec postgres /bin/bash

update: ## Aktualisiert Dependencies
	@echo "${GREEN}Aktualisiere Backend-Dependencies...${RESET}"
	cd backend && .venv/bin/pip install --upgrade -r requirements.txt
	@echo "${GREEN}Aktualisiere Frontend-Dependencies...${RESET}"
	cd frontend && npm update
	@echo "${GREEN}✓ Dependencies aktualisiert${RESET}"

docs: ## Öffnet API-Dokumentation im Browser
	@echo "${GREEN}Öffne API-Dokumentation...${RESET}"
	@command -v xdg-open >/dev/null && xdg-open http://localhost:8000/docs || \
	command -v open >/dev/null && open http://localhost:8000/docs || \
	echo "Öffne manuell: http://localhost:8000/docs"

prod-check: ## Prüft Produktions-Bereitschaft
	@echo "${GREEN}Prüfe Produktions-Konfiguration...${RESET}"
	@echo "Checking .env file..."
	@grep -q "ALLOW_DEMO_AUTH=0" .env && echo "✓ Demo-Auth deaktiviert" || echo "✗ WARNUNG: Demo-Auth aktiv!"
	@grep -q "DEBUG=0" .env && echo "✓ Debug-Modus aus" || echo "✗ WARNUNG: Debug-Modus aktiv!"
	@grep -q "SECRET_KEY=CHANGE" .env && echo "✗ WARNUNG: Standard SECRET_KEY!" || echo "✓ SECRET_KEY gesetzt"
	@echo "${GREEN}Prüfe Firewall...${RESET}"
	@sudo ufw status 2>/dev/null | grep -q "Status: active" && echo "✓ Firewall aktiv" || echo "⚠ Firewall nicht aktiv"
	@echo "${GREEN}Prüfe SSL...${RESET}"
	@curl -k https://localhost 2>/dev/null && echo "✓ HTTPS verfügbar" || echo "⚠ HTTPS nicht konfiguriert"

version: ## Zeigt Versionen an
	@echo "${GREEN}PUK Dashboard Versionen:${RESET}"
	@echo "Dashboard: $(shell grep -m1 version docker-compose.yml | cut -d'"' -f2)"
	@echo "Python: $(shell python --version 2>&1 | cut -d' ' -f2)"
	@echo "Node: $(shell node --version)"
	@echo "Docker: $(shell docker --version | cut -d' ' -f3 | sed 's/,//')"
	@echo "Docker Compose: $(shell docker-compose --version | cut -d' ' -f4 | sed 's/,//')"

.DEFAULT_GOAL := help
