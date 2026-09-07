COMPOSE = docker compose --env-file .env -f infra/docker-compose.yml

up:          ## Levanta db + redis + api
	$(COMPOSE) up -d --build

deps-front:  ## Rehace node_modules del contenedor (usar al sumar una dependencia)
	# POR QUÉ HACE FALTA UN COMANDO APARTE
	# El compose monta ../frontend sobre /app, y para que eso no tape el
	# node_modules instalado en la imagen hay un volumen ANÓNIMO en
	# /app/node_modules. Ese volumen sobrevive a `up --build`: docker reusa el
	# de la corrida anterior. Resultado: la imagen nueva TIENE la dependencia,
	# el contenedor monta encima el node_modules viejo que NO la tiene, y el
	# build falla con "Module not found" señalando un paquete que sí está en
	# package.json y en el lock. Es de los errores que peor apuntan a su causa.
	#
	# -V (--renew-anon-volumes) descarta ese volumen y lo rehace desde la
	# imagen. Se corre cuando cambia package.json, no en cada arranque.
	$(COMPOSE) up -d --build -V frontend

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

test:        ## Corre la suite. -rs para que los tests salteados digan por qué
	# El -rs no es un adorno. Siete tests de la suite comparan TypeScript
	# contra Python y necesitan que el frontend esté montado en el contenedor;
	# cuando no lo está se saltean, y un salteo callado es una `s` perdida
	# entre novecientas `.`. Con -rs, cada salteo dice su motivo al final.
	$(COMPOSE) exec backend python -m pytest -q -rs

recrear:     ## Rehace los contenedores para tomar cambios del compose
	# CUÁNDO USAR ESTO Y NO `restart`, que es la confusión que ya costó dos
	# corridas con siete tests salteados sin que se notara:
	#
	#   restart          → reinicia el PROCESO adentro del contenedor que ya
	#                      existe. Alcanza para cambios de código Python, que
	#                      va montado y se relee solo.
	#   up --force-recreate → rehace el CONTENEDOR. Hace falta cada vez que
	#                      cambia infra/docker-compose.yml: volúmenes nuevos,
	#                      variables de entorno, puertos. `restart` no relee
	#                      ese archivo NUNCA, y no avisa.
	#
	# --no-build a propósito: recrear no debería salir a internet a buscar
	# imágenes. Si además cambió el Dockerfile, usá `make up`.
	$(COMPOSE) up -d --force-recreate --no-build backend worker beat

typecheck:   ## Verifica los tipos del panel contra la linea de base
	$(COMPOSE) exec -T frontend npm run typecheck

.PHONY: up down logs ps sh db-upgrade db-revision db-reset seed seed-minimo psql test typecheck dbml recrear