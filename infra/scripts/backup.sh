#!/usr/bin/env bash
# Backup diario de la base de Turnos360.
#
# Hace un dump comprimido, lo guarda con la fecha en el nombre y borra los
# más viejos que RETENCION_DIAS. Pensado para cron.
#
# Instalación (en el servidor, como root):
#   cp infra/scripts/backup.sh /usr/local/bin/turnos360-backup
#   chmod +x /usr/local/bin/turnos360-backup
#   crontab -e   ->   30 3 * * * /usr/local/bin/turnos360-backup >> /var/log/turnos360-backup.log 2>&1
#
# OJO: un backup que nunca restauraste no es un backup. Probá restore.sh
# antes de confiar en esto (el runbook tiene el paso).

set -euo pipefail

REPO="${REPO:-/opt/turnos360}"
COMPOSE="${COMPOSE:-$REPO/infra/docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-$REPO/.env.prod}"
DESTINO="${DESTINO:-/var/backups/turnos360}"
RETENCION_DIAS="${RETENCION_DIAS:-14}"

# Usuario y base salen del .env.prod (no se hardcodean acá).
# shellcheck disable=SC1090
POSTGRES_USER="$(grep -E '^POSTGRES_USER=' "$ENV_FILE" | cut -d= -f2-)"
POSTGRES_DB="$(grep -E '^POSTGRES_DB=' "$ENV_FILE" | cut -d= -f2-)"

mkdir -p "$DESTINO"
FECHA="$(date +%Y%m%d-%H%M)"
ARCHIVO="$DESTINO/turnos360-$FECHA.sql.gz"

echo "[$(date -Is)] Backup -> $ARCHIVO"

# pg_dump corre DENTRO del contenedor (la base no está expuesta afuera).
docker compose --env-file "$ENV_FILE" -f "$COMPOSE" exec -T db \
    pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists \
    | gzip > "$ARCHIVO"

# Un dump vacío o mínimo es señal de que algo falló: mejor gritar ahora.
TAMANO=$(stat -c%s "$ARCHIVO")
if [ "$TAMANO" -lt 1024 ]; then
    echo "ERROR: el backup pesa $TAMANO bytes. Algo salió mal." >&2
    exit 1
fi

echo "[$(date -Is)] OK — $(du -h "$ARCHIVO" | cut -f1)"

# Rotación
BORRADOS=$(find "$DESTINO" -name 'turnos360-*.sql.gz' -mtime +"$RETENCION_DIAS" -print -delete | wc -l)
echo "[$(date -Is)] Rotación: $BORRADOS archivo(s) viejo(s) borrado(s). Quedan $(ls -1 "$DESTINO"/turnos360-*.sql.gz 2>/dev/null | wc -l)."

# RECORDATORIO: esto guarda el backup EN EL MISMO SERVIDOR. Si el servidor
# muere, se va con él. Copiá los dumps afuera (scp a tu máquina, Object
# Storage, otro proveedor). En staging alcanza con lo local; en producción no.
