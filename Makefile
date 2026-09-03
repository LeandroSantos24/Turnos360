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

seed:        ## Carga las empresas ficticias (Barbería La Cueva + consultorio)
	$(COMPOSE) exec backend python -m app.seeds

seed-minimo: ## Solo lo que no se puede crear desde la app: super-admin + rubros
	$(COMPOSE) exec backend python -m app.seeds_minimo

db-reset:    ## BORRA la base y la deja limpia con el seed mínimo. make db-reset CONFIRMO=si
ifneq ($(CONFIRMO),si)
	@echo "Esto BORRA la base de datos entera, sin vuelta atrás."
	@echo "Si es lo que querés:  make db-reset CONFIRMO=si"
	@exit 1
endif
	$(COMPOSE) down -v
	$(COMPOSE) up -d --build
	@echo "  esperando a que la base levante…"
	@sleep 6
	$(COMPOSE) exec backend alembic upgrade head
	$(COMPOSE) exec backend python -m app.seeds_minimo

dbml:        ## Regenera docs/turnos360.dbml desde los modelos
	$(COMPOSE) exec -T backend python -m app.tools.generar_dbml --stdout > docs/turnos360.dbml
	@echo "  docs/turnos360.dbml regenerado ($$(grep -c '^Table ' docs/turnos360.dbml) tablas)"

psql:        ## Consola de PostgreSQL
	$(COMPOSE) exec db psql -U turnos360 -d turnos360

test:
	$(COMPOSE) exec backend python -m pytest -q

typecheck:   ## Verifica los tipos del panel contra la linea de base
	$(COMPOSE) exec -T frontend npm run typecheck

.PHONY: up down logs ps sh db-upgrade db-revision db-reset seed seed-minimo psql test typecheck dbml