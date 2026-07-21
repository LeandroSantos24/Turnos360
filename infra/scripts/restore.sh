#!/usr/bin/env bash
# Restauración de un backup de Turnos360.
#
#   ./restore.sh /var/backups/turnos360/turnos360-20260718-0330.sql.gz
#
# DESTRUCTIVO: pisa el contenido actual de la base. Pide confirmación escrita.
#
# Este script existe para USARSE, no para tenerlo guardado: probá una
# restauración completa ANTES de tener datos reales de clientes.

set -euo pipefail

ARCHIVO="${1:-}"
REPO="${REPO:-/opt/turnos360}"
COMPOSE="${COMPOSE:-$REPO/infra/docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-$REPO/.env.prod}"

if [ -z "$ARCHIVO" ] || [ ! -f "$ARCHIVO" ]; then
    echo "Uso: $0 <archivo.sql.gz>" >&2
    echo "Disponibles:" >&2
    ls -1t /var/backups/turnos360/*.sql.gz 2>/dev/null | head -10 >&2 || echo "  (ninguno)" >&2
    exit 1
fi

POSTGRES_USER="$(grep -E '^POSTGRES_USER=' "$ENV_FILE" | cut -d= -f2-)"
POSTGRES_DB="$(grep -E '^POSTGRES_DB=' "$ENV_FILE" | cut -d= -f2-)"

echo "═══════════════════════════════════════════════════════"
echo " Vas a RESTAURAR:  $ARCHIVO"
echo " Sobre la base:    $POSTGRES_DB"
echo " Esto BORRA los datos actuales y los reemplaza."
echo "═══════════════════════════════════════════════════════"
read -r -p 'Escribí RESTAURAR para continuar: ' confirmacion
if [ "$confirmacion" != "RESTAURAR" ]; then
    echo "Cancelado."
    exit 1
fi

# Los servicios que escriben se apagan para que no metan datos a mitad
# de la restauración. La base queda arriba (es la que recibe el dump).
echo "→ Parando backend, worker y beat..."
docker compose --env-file "$ENV_FILE" -f "$COMPOSE" stop backend worker beat

echo "→ Restaurando..."
gunzip -c "$ARCHIVO" | docker compose --env-file "$ENV_FILE" -f "$COMPOSE" exec -T db \
    psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 --quiet

echo "→ Levantando servicios..."
docker compose --env-file "$ENV_FILE" -f "$COMPOSE" start backend worker beat

echo "→ Esperando al backend..."
sleep 10
docker compose --env-file "$ENV_FILE" -f "$COMPOSE" ps

echo
echo "Restauración terminada. Verificá a mano:"
echo "  · entrá al panel y mirá que estén tus turnos y clientes"
echo "  · docker compose ... exec backend alembic current   (debe decir head)"
