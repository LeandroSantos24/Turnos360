COMPOSE = docker compose --env-file .env -f infra/docker-compose.yml

up:          ## Levanta db + redis + api
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

ps:
	$(COMPOSE) ps

sh:          ## Terminal dentro del backend
	$(COMPOSE) exec backend bash

db-upgrade:  ## Aplica las migraciones
	$(COMPOSE) exec backend alembic upgrade head

db-revision: ## Nueva migración: make db-revision m="mensaje"
	$(COMPOSE) exec backend alembic revision --autogenerate -m "$(m)"

seed:        ## Carga las empresas ficticias
	$(COMPOSE) exec backend python -m app.seeds

psql:        ## Consola de PostgreSQL
	$(COMPOSE) exec db psql -U turnos360 -d turnos360

test:
	$(COMPOSE) exec backend python -m pytest -q

typecheck:   ## Verifica los tipos del panel contra la linea de base
	$(COMPOSE) exec -T frontend npm run typecheck

.PHONY: up down logs ps sh db-upgrade db-revision seed psql test typecheck