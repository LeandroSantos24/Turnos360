#!/usr/bin/env bash
#
# Turnos360 · Verificación de un backup — SIN TOCAR LA BASE REAL
#
#   ./verificar-backup.sh /var/backups/turnos360/turnos360-20260821-0330.sql.gz
#
# Por qué existe, si ya está restore.sh
# --------------------------------------
# `restore.sh` es DESTRUCTIVO: pisa la base actual. Es la herramienta correcta
# el día que se te cayó todo, y la peor posible para *probar* si un backup
# sirve — porque para probarlo tendrías que borrar tus datos.
#
# Y esa es, exactamente, la razón por la que casi nadie prueba sus backups: el
# único procedimiento disponible da miedo. Así se llega al día del incendio
# con un archivo de 40 MB que nadie abrió nunca.
#
# Este script restaura el dump en una base TEMPORAL al lado de la real, la
# revisa, la compara contra la que está viva, y después la borra. No para
# ningún servicio, no toca un solo dato de producción, y se puede correr un
# martes a las 3 de la tarde sin avisarle a nadie.
#
# Sale con código != 0 si algo no cierra, así que sirve en cron:
#   0 4 * * 1  /usr/local/bin/turnos360-verificar-backup $(ls -1t /var/backups/turnos360/*.sql.gz | head -1)
#
set -uo pipefail

VERDE=$'\033[0;32m'; ROJO=$'\033[0;31m'; AMAR=$'\033[0;33m'; AZUL=$'\033[0;36m'; N=$'\033[0m'
ok()    { echo "${VERDE}  ✔${N} $1"; }
error() { echo "${ROJO}  ✘${N} $1"; ERRORES=$((ERRORES + 1)); }
aviso() { echo "${AMAR}  !${N} $1"; AVISOS=$((AVISOS + 1)); }
info()  { echo "${AZUL}  ·${N} $1"; }

ERRORES=0
AVISOS=0

ARCHIVO="${1:-}"
CONSERVAR="${2:-}"

REPO="${REPO:-/opt/turnos360}"
COMPOSE="${COMPOSE:-$REPO/infra/docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-$REPO/.env.prod}"
BASE_TMP="${BASE_TMP:-turnos360_verificacion}"

# Tablas que en una base con negocios reales NO pueden estar vacías.
TABLAS_VIVAS="empresa usuario cliente turno"
# Tablas que tienen que EXISTIR aunque estén vacías (si falta una, el dump
# está incompleto o es de una versión vieja del esquema).
TABLAS_ESPERADAS="empresa usuario cliente turno pago mensaje recurso servicio alembic_version"

if [[ -z "$ARCHIVO" || ! -f "$ARCHIVO" ]]; then
  echo "Uso: $0 <archivo.sql.gz> [--conservar]" >&2
  echo >&2
  echo "Backups disponibles:" >&2
  ls -1t /var/backups/turnos360/*.sql.gz 2>/dev/null | head -10 >&2 || echo "  (ninguno)" >&2
  exit 1
fi

# ── Cómo hablarle a Postgres ────────────────────────────────────────────────
# Por defecto, adentro del contenedor (la base no está expuesta afuera). Se
# puede sobreescribir con PSQL_BASE para correr el script contra un Postgres
# local — que es, además, cómo se lo probó.
if [[ -z "${PSQL_BASE:-}" ]]; then
  POSTGRES_USER="$(grep -E '^POSTGRES_USER=' "$ENV_FILE" | cut -d= -f2-)"
  POSTGRES_DB="$(grep -E '^POSTGRES_DB=' "$ENV_FILE" | cut -d= -f2-)"
  PSQL_BASE="docker compose --env-file $ENV_FILE -f $COMPOSE exec -T db psql -U $POSTGRES_USER"
else
  POSTGRES_DB="${POSTGRES_DB:-turnos360}"
fi

psql_en() {           # psql_en <base> <sql>
  $PSQL_BASE -d "$1" -tAc "$2" 2>/dev/null
}

echo
echo "${AZUL}═══════════════════════════════════════════════════════════${N}"
echo "${AZUL}  Verificación de backup — no toca la base real${N}"
echo "${AZUL}═══════════════════════════════════════════════════════════${N}"
echo
info "Archivo:     $ARCHIVO"
info "Tamaño:      $(du -h "$ARCHIVO" | cut -f1)"
info "Fecha:       $(date -r "$ARCHIVO" '+%Y-%m-%d %H:%M')"
EDAD_H=$(( ( $(date +%s) - $(date -r "$ARCHIVO" +%s) ) / 3600 ))
info "Antigüedad:  ${EDAD_H} h"
echo

# ── 1. ¿El archivo está entero? ─────────────────────────────────────────────
# Un gzip truncado se ve igual que uno bueno en un `ls`. Esta es la falla más
# común y la más silenciosa: el disco se llenó a mitad del dump.
if gzip -t "$ARCHIVO" 2>/dev/null; then
  ok "El gzip está íntegro"
else
  error "EL ARCHIVO ESTÁ CORTADO O CORRUPTO. Este backup no sirve."
  exit 1
fi

LINEAS=$(gunzip -c "$ARCHIVO" | wc -l)
if [[ "$LINEAS" -lt 50 ]]; then
  error "El dump tiene $LINEAS líneas: está prácticamente vacío."
  exit 1
fi
ok "El dump tiene $LINEAS líneas"

# ── 2. Restaurar en una base temporal ───────────────────────────────────────
echo
info "Restaurando en la base temporal «$BASE_TMP»…"
psql_en postgres "DROP DATABASE IF EXISTS $BASE_TMP" >/dev/null
if ! psql_en postgres "CREATE DATABASE $BASE_TMP" >/dev/null; then
  error "No pude crear la base temporal."
  exit 1
fi

SALIDA_RESTORE=$(gunzip -c "$ARCHIVO" | $PSQL_BASE -d "$BASE_TMP" -v ON_ERROR_STOP=1 --quiet 2>&1)
CODIGO=$?
if [[ $CODIGO -ne 0 ]]; then
  error "La restauración falló:"
  echo "$SALIDA_RESTORE" | tail -10 | sed 's/^/      /'
  psql_en postgres "DROP DATABASE IF EXISTS $BASE_TMP" >/dev/null
  exit 1
fi
ok "Restauró sin errores"

# ── 3. ¿Está el esquema completo? ───────────────────────────────────────────
echo
info "Revisando el esquema…"
FALTAN=""
for t in $TABLAS_ESPERADAS; do
  existe=$(psql_en "$BASE_TMP" "SELECT to_regclass('public.$t') IS NOT NULL")
  [[ "$existe" == "t" ]] || FALTAN="$FALTAN $t"
done
if [[ -n "$FALTAN" ]]; then
  error "Faltan tablas:$FALTAN"
else
  ok "Están las $(echo $TABLAS_ESPERADAS | wc -w) tablas esperadas"
fi

TOTAL_TABLAS=$(psql_en "$BASE_TMP" "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
ok "Total de tablas restauradas: $TOTAL_TABLAS"

REVISION=$(psql_en "$BASE_TMP" "SELECT version_num FROM alembic_version")
if [[ -z "$REVISION" ]]; then
  error "alembic_version está vacía: el backup no sabe en qué versión del esquema quedó."
else
  ok "Versión del esquema: $REVISION"
fi

# ── 4. ¿Hay datos, y cuántos? ───────────────────────────────────────────────
echo
info "Contando filas…"
printf "      %-22s %10s %10s\n" "TABLA" "BACKUP" "EN VIVO"
HAY_VIVA=$(psql_en "$POSTGRES_DB" "SELECT 1" || echo "")
for t in $TABLAS_ESPERADAS; do
  [[ "$t" == "alembic_version" ]] && continue
  n=$(psql_en "$BASE_TMP" "SELECT count(*) FROM $t" || echo "?")
  if [[ -n "$HAY_VIVA" ]]; then
    v=$(psql_en "$POSTGRES_DB" "SELECT count(*) FROM $t" 2>/dev/null || echo "?")
  else
    v="—"
  fi
  printf "      %-22s %10s %10s\n" "$t" "$n" "$v"

  if echo "$TABLAS_VIVAS" | grep -qw "$t" && [[ "$n" == "0" ]]; then
    aviso "«$t» quedó en cero. Si el negocio ya tiene datos, este backup está mal."
  fi
  # Una diferencia enorme entre el backup y la base viva no es normal ni
  # siquiera con un dump de anoche: son datos que se perderían.
  if [[ "$v" =~ ^[0-9]+$ && "$n" =~ ^[0-9]+$ && "$v" -gt 0 ]]; then
    perdidas=$(( v - n ))
    if [[ $perdidas -gt 0 ]]; then
      pct=$(( perdidas * 100 / v ))
      if [[ $pct -ge 20 ]]; then
        aviso "«$t»: el backup tiene $perdidas filas menos que la base viva (${pct}%)."
      fi
    fi
  fi
done

# ── 5. ¿Qué tan fresco es? ──────────────────────────────────────────────────
echo
ULTIMO=$(psql_en "$BASE_TMP" "SELECT COALESCE(max(creado_en)::text, '') FROM turno" 2>/dev/null)
[[ -z "$ULTIMO" ]] && ULTIMO=$(psql_en "$BASE_TMP" "SELECT COALESCE(max(fecha_inicio)::text, '') FROM turno" 2>/dev/null)
if [[ -n "$ULTIMO" ]]; then
  info "Turno más reciente en el backup: $ULTIMO"
else
  aviso "No pude leer la fecha del último turno."
fi

if [[ "$EDAD_H" -gt 48 ]]; then
  aviso "El backup tiene ${EDAD_H} horas. ¿Está corriendo el cron diario?"
fi

# ── 6. Limpieza ─────────────────────────────────────────────────────────────
echo
if [[ "$CONSERVAR" == "--conservar" ]]; then
  aviso "Base temporal «$BASE_TMP» CONSERVADA para que la mires a mano."
  echo "      Cuando termines:  DROP DATABASE $BASE_TMP;"
else
  psql_en postgres "DROP DATABASE IF EXISTS $BASE_TMP" >/dev/null
  ok "Base temporal borrada. La base real no se tocó en ningún momento."
fi

# ── 7. Veredicto ────────────────────────────────────────────────────────────
echo
if [[ $ERRORES -gt 0 ]]; then
  echo "${ROJO}═══════════════════════════════════════════════════════════${N}"
  echo "${ROJO}  ESTE BACKUP NO SIRVE — $ERRORES problema(s)${N}"
  echo "${ROJO}═══════════════════════════════════════════════════════════${N}"
  exit 1
fi
if [[ $AVISOS -gt 0 ]]; then
  echo "${AMAR}═══════════════════════════════════════════════════════════${N}"
  echo "${AMAR}  Restauró bien, pero hay $AVISOS cosa(s) para mirar${N}"
  echo "${AMAR}═══════════════════════════════════════════════════════════${N}"
  exit 2
fi
echo "${VERDE}═══════════════════════════════════════════════════════════${N}"
echo "${VERDE}  BACKUP VERIFICADO — restaura y tiene los datos${N}"
echo "${VERDE}═══════════════════════════════════════════════════════════${N}"
echo
echo "  Esto es lo que convierte un archivo en un backup. Corrélo una vez"
echo "  por semana, o dejalo en cron y que te grite solo cuando falle."
echo
