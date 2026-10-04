#!/usr/bin/env bash
# Backup diario de la base de Turnos360 + las fotos/comprobantes subidos.
#
# Hace un dump comprimido, lo valida, lo copia fuera del servidor y borra los
# locales más viejos que RETENCION_DIAS. Pensado para cron.
#
# Instalación (en el servidor, como root):
#   cp infra/scripts/backup.sh /usr/local/bin/turnos360-backup
#   chmod +x /usr/local/bin/turnos360-backup
#   crontab -e  (ver DEPLOY_PRODUCCION.md: BACKUP_REMOTO y BACKUP_PING_URL)
#
# Regla de este script: un backup que "parece" haber andado no cuenta. Sale
# con código != 0 si CUALQUIER paso falla (base caída, disco lleno, dump
# incompleto, copia remota fallida) y en ese caso no deja ningún archivo a
# medias en DESTINO: lo que queda ahí siempre es un backup entero.
#
# Alerta: cron no avisa a nadie por sí solo (la salida va a un log y un VPS
# recién instalado no tiene servidor de correo para MAILTO). Con
# BACKUP_PING_URL (un check de Healthchecks.io o compatible) el script avisa
# al empezar, al terminar bien y al fallar; y si un día NO corre (cron roto,
# VPS apagado), el servicio avisa igual porque no le llegó el aviso a tiempo.
#
# OJO: un backup que nunca restauraste no es un backup. verificar-backup.sh
# lo restaura en una base temporal sin tocar la real (ver el runbook).

set -euo pipefail
umask 077   # los dumps tienen TODOS los datos: solo root los puede leer

REPO="${REPO:-/opt/turnos360}"
COMPOSE="${COMPOSE:-$REPO/infra/docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-$REPO/.env.prod}"
DESTINO="${DESTINO:-/var/backups/turnos360}"
RETENCION_DIAS="${RETENCION_DIAS:-14}"
BACKUP_REMOTO="${BACKUP_REMOTO:-}"
BACKUP_PING_URL="${BACKUP_PING_URL:-}"

PASO="inicio"
PARCIALES=()

# ── Aviso al servicio de monitoreo (opcional, nunca rompe el backup) ──────
ping() {   # ping [sufijo] [mensaje]
    [ -n "$BACKUP_PING_URL" ] || return 0
    curl -fsS -m 10 --retry 3 -o /dev/null --data-raw "${2:-}" \
        "${BACKUP_PING_URL%/}${1:+/$1}" \
        || echo "[$(date -Is)] AVISO: no se pudo avisar al monitor de backups." >&2
}

al_salir() {
    local codigo=$?
    # Nada a medias en DESTINO: si falló, lo parcial se borra.
    for f in "${PARCIALES[@]}"; do rm -f "$f"; done
    if [ "$codigo" -eq 0 ]; then
        ping "" "backup OK"
    else
        echo "[$(date -Is)] ERROR: el backup FALLÓ en el paso «$PASO» (código $codigo)." >&2
        ping "fail" "falló en: $PASO (código $codigo)"
    fi
}
trap al_salir EXIT

fallar() { echo "ERROR: $1" >&2; exit 1; }

ping "start"

# Usuario y base salen del .env.prod (no se hardcodean acá).
PASO="leer $ENV_FILE"
[ -r "$ENV_FILE" ] || fallar "no puedo leer $ENV_FILE"
POSTGRES_USER="$(grep -E '^POSTGRES_USER=' "$ENV_FILE" | cut -d= -f2- || true)"
POSTGRES_DB="$(grep -E '^POSTGRES_DB=' "$ENV_FILE" | cut -d= -f2- || true)"
[ -n "$POSTGRES_USER" ] && [ -n "$POSTGRES_DB" ] \
    || fallar "faltan POSTGRES_USER o POSTGRES_DB en $ENV_FILE"

mkdir -p "$DESTINO"
FECHA="$(date +%Y%m%d-%H%M)"
ARCHIVO="$DESTINO/turnos360-$FECHA.sql.gz"
FOTOS="$DESTINO/uploads-$FECHA.tar.gz"

# ── 1. Base ────────────────────────────────────────────────────────────────
# Se escribe a un .parcial y se renombra solo si todo cierra: un dump cortado
# (base caída, disco lleno, contenedor reiniciado) nunca queda con nombre de
# backup bueno, ni lo cuenta la rotación, ni lo elige nadie para restaurar.
PASO="pg_dump"
echo "[$(date -Is)] Backup -> $ARCHIVO"
PARCIALES+=("$ARCHIVO.parcial")
# pg_dump corre DENTRO del contenedor (la base no está expuesta afuera).
docker compose --env-file "$ENV_FILE" -f "$COMPOSE" exec -T db \
    pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists \
    | gzip > "$ARCHIVO.parcial"

PASO="validar dump"
gzip -t "$ARCHIVO.parcial" 2>/dev/null || fallar "el dump está cortado o corrupto"
# pg_dump escribe esta línea al FINAL de un dump completo. Si falta, el dump
# se cortó aunque el gzip esté sano (pasa si el proceso muere a mitad).
# (Se guarda en una variable y no con `| grep -q`: con pipefail, el SIGPIPE
# de cortar la tubería antes de tiempo se leería como una falla.)
FINAL_DUMP="$(gunzip -c "$ARCHIVO.parcial" | tail -n 20)"
case "$FINAL_DUMP" in
    *"PostgreSQL database dump complete"*) ;;
    *) fallar "el dump no termina con la marca de pg_dump: está incompleto" ;;
esac
TAMANO=$(stat -c%s "$ARCHIVO.parcial")
[ "$TAMANO" -ge 1024 ] || fallar "el dump pesa $TAMANO bytes: está vacío"
mv "$ARCHIVO.parcial" "$ARCHIVO"
echo "[$(date -Is)] Base OK — $(du -h "$ARCHIVO" | cut -f1)"

# ── 2. Fotos y comprobantes (volumen `uploads`) ──────────────────────────
# No están en la base: sin esto, perder el disco es perder todos los logos,
# portadas, galerías y comprobantes de pago.
PASO="uploads"
PARCIALES+=("$FOTOS.parcial")
docker compose --env-file "$ENV_FILE" -f "$COMPOSE" exec -T backend \
    tar czf - -C /app uploads > "$FOTOS.parcial"
PASO="validar uploads"
# tar -t recorre el archivo entero: detecta cortes que gzip -t no ve.
tar -tzf "$FOTOS.parcial" > /dev/null 2>&1 || fallar "el tar de uploads está cortado o corrupto"
mv "$FOTOS.parcial" "$FOTOS"
echo "[$(date -Is)] Uploads OK — $(du -h "$FOTOS" | cut -f1)"

# ── 3. Copia FUERA del servidor ──────────────────────────────────────────
# Un backup que vive en el mismo disco se pierde con el servidor.
# BACKUP_REMOTO en formato rsync (usuario@host:/ruta/). Si la copia falla, el
# backup se da por FALLIDO aunque el local esté bien: lo que protege contra
# perder el VPS es la copia de afuera.
if [ -n "$BACKUP_REMOTO" ]; then
    PASO="copia remota"
    echo "[$(date -Is)] Copiando a $BACKUP_REMOTO ..."
    rsync -a --timeout=120 "$ARCHIVO" "$FOTOS" "$BACKUP_REMOTO" \
        || fallar "no se pudo copiar el backup fuera del servidor ($BACKUP_REMOTO)"
    echo "[$(date -Is)] Copia remota OK"
elif [ -n "$BACKUP_PING_URL" ]; then
    # El backup programado (el que avisa al monitor) TIENE que salir afuera.
    PASO="copia remota"
    fallar "BACKUP_REMOTO vacío: el backup quedó solo en este servidor"
else
    # Corrida manual (ej. antes de un deploy): alcanza con lo local.
    echo "[$(date -Is)] AVISO: BACKUP_REMOTO vacío. El backup quedó SOLO en este servidor." >&2
fi

# ── 4. Rotación local ────────────────────────────────────────────────────
# Solo se borra lo viejo DESPUÉS de tener uno nuevo y bueno. La retención del
# lado remoto la maneja el destino (ver DEPLOY_PRODUCCION.md).
PASO="rotación"
find "$DESTINO" -name 'uploads-*.tar.gz' -mtime +"$RETENCION_DIAS" -delete
BORRADOS=$(find "$DESTINO" -name 'turnos360-*.sql.gz' -mtime +"$RETENCION_DIAS" -print -delete | wc -l)
echo "[$(date -Is)] Rotación: $BORRADOS archivo(s) viejo(s) borrado(s). Quedan $(ls -1 "$DESTINO"/turnos360-*.sql.gz 2>/dev/null | wc -l)."
PASO="fin"
