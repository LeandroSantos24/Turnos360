#!/usr/bin/env bash
# Pruebas de infra/scripts/backup.sh sin Docker ni servidor.
#
#   bash infra/scripts/tests/test_backup.sh
#
# `docker` y `curl` se reemplazan por imitaciones en el PATH: la de docker
# devuelve un dump (entero, cortado o con error) y un tar de uploads; la de
# curl anota a qué URL se avisó. gzip, tar y rsync son los reales.
#
# Qué protege: que un backup que falla NUNCA se dé por bueno (código de
# salida, aviso /fail al monitor, ningún archivo a medias en DESTINO), que los
# dumps no queden legibles para otros usuarios, que una copia remota fallida
# cuente como falla y que la rotación borre solo lo viejo.

set -uo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$AQUI/../backup.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
FALLAS=0
CASOS=0

mkdir -p "$TMP/bin" "$TMP/uploads/uploads/logos"
echo "logo" > "$TMP/uploads/uploads/logos/a.webp"
printf 'POSTGRES_USER=t360\nPOSTGRES_DB=t360\n' > "$TMP/env"

cat > "$TMP/bin/docker" <<'EOF'
#!/usr/bin/env bash
case "$*" in
  *pg_dump*)
    case "${FAKE_PG:-ok}" in
      ok)
        echo "-- PostgreSQL database dump"
        for i in $(seq 1 "${FAKE_FILAS:-400}"); do echo "INSERT INTO turno VALUES ($i, '$RANDOM$RANDOM$RANDOM');"; done
        echo "-- PostgreSQL database dump complete"
        ;;
      cortado)
        echo "-- PostgreSQL database dump"
        for i in $(seq 1 400); do echo "INSERT INTO turno VALUES ($i);"; done
        ;;
      caida)
        echo 'pg_dump: error: connection to server failed' >&2
        exit 1
        ;;
    esac
    ;;
  *tar*)
    tar czf - -C "$FAKE_UPLOADS" uploads
    ;;
  *) exit 1 ;;
esac
EOF
cat > "$TMP/bin/curl" <<'EOF'
#!/usr/bin/env bash
for a in "$@"; do case "$a" in http*) echo "$a" >> "$FAKE_PINGS";; esac; done
exit 0
EOF
chmod +x "$TMP/bin/docker" "$TMP/bin/curl"

correr() {   # correr <nombre> [VAR=valor ...] -> deja $CODIGO, $DEST, $SALIDA
  local nombre="$1"; shift
  DEST="$TMP/$nombre/backups"
  mkdir -p "$TMP/$nombre"
  : > "$TMP/$nombre/pings"
  SALIDA="$(env PATH="$TMP/bin:$PATH" ENV_FILE="$TMP/env" COMPOSE=/dev/null \
      DESTINO="$DEST" FAKE_UPLOADS="$TMP/uploads" FAKE_PINGS="$TMP/$nombre/pings" \
      BACKUP_PING_URL="https://hc.example/abc" "$@" bash "$SCRIPT" 2>&1)"
  CODIGO=$?
  PINGS="$(cat "$TMP/$nombre/pings")"
}

espero() {   # espero <descripción> <condición...>
  CASOS=$((CASOS + 1))
  if "${@:2}"; then echo "  ✔ $1"; else echo "  ✘ $1"; FALLAS=$((FALLAS + 1)); fi
}
sin_parciales() { ! ls "$DEST"/*.parcial >/dev/null 2>&1; }
hay() { ls "$DEST"/$1 >/dev/null 2>&1; }
no_hay() { ! hay "$1"; }
ping_ok() { grep -qx "https://hc.example/abc" <<<"$PINGS"; }
ping_fail() { grep -qx "https://hc.example/abc/fail" <<<"$PINGS"; }

echo "· Backup bueno con copia remota"
mkdir -p "$TMP/remoto"
correr bueno BACKUP_REMOTO="$TMP/remoto/"
espero "sale con 0" test "$CODIGO" -eq 0
espero "deja el dump y los uploads" hay 'turnos360-*.sql.gz'
espero "y el tar de uploads" hay 'uploads-*.tar.gz'
espero "copia los dos afuera" test "$(ls "$TMP/remoto" | wc -l)" -eq 2
espero "avisa start y OK al monitor" bash -c "grep -q '/abc/start' <<<\"$PINGS\" && grep -qx 'https://hc.example/abc' <<<\"$PINGS\""
espero "nada a medias" sin_parciales
espero "dumps legibles solo por el dueño (600)" test "$(stat -c %a "$DEST"/turnos360-*.sql.gz)" = 600
espero "carpeta de backups cerrada (700)" test "$(stat -c %a "$DEST")" = 700

echo "· Postgres caído"
correr caida FAKE_PG=caida BACKUP_REMOTO="$TMP/remoto/"
espero "sale con error" test "$CODIGO" -ne 0
espero "avisa /fail" ping_fail
espero "no avisa OK" bash -c "! grep -qx 'https://hc.example/abc' <<<\"$PINGS\""
espero "no deja ningún dump" no_hay 'turnos360-*'
espero "nada a medias" sin_parciales
espero "dice en qué paso falló" grep -q "pg_dump" <<<"$SALIDA"

echo "· Dump cortado (gzip sano, sin la marca final de pg_dump)"
correr cortado FAKE_PG=cortado BACKUP_REMOTO="$TMP/remoto/"
espero "sale con error" test "$CODIGO" -ne 0
espero "avisa /fail" ping_fail
espero "no lo deja con nombre de backup bueno" no_hay 'turnos360-*'
espero "nada a medias" sin_parciales

echo "· Copia remota que falla"
correr remoto BACKUP_REMOTO="$TMP/no/existe/esta/carpeta/"
espero "sale con error" test "$CODIGO" -ne 0
espero "avisa /fail" ping_fail
espero "el backup local bueno se conserva" hay 'turnos360-*.sql.gz'

echo "· Programado sin BACKUP_REMOTO (con monitor)"
correr sin_remoto
espero "cuenta como falla: no salió del servidor" test "$CODIGO" -ne 0
espero "avisa /fail" ping_fail

echo "· Corrida manual sin BACKUP_REMOTO ni monitor (antes de un deploy)"
correr manual BACKUP_PING_URL=
espero "sale con 0 y avisa que quedó solo local" bash -c "[ $CODIGO -eq 0 ] && grep -q 'SOLO en este servidor' <<<\"\$1\"" _ "$SALIDA"

echo "· Disco sin lugar (límite de tamaño de archivo)"
CODIGO=0
(
  ulimit -f 16   # 16 KB: un dump de 20.000 filas no entra
  correr lleno FAKE_FILAS=20000 BACKUP_REMOTO="$TMP/remoto/"
  exit "$CODIGO"
)
CODIGO=$?
DEST="$TMP/lleno/backups"
PINGS="$(cat "$TMP/lleno/pings")"
espero "sale con error" test "$CODIGO" -ne 0
espero "no deja un dump truncado" no_hay 'turnos360-*'
espero "nada a medias" sin_parciales

echo "· Rotación"
mkdir -p "$TMP/rota/backups"
touch -d '20 days ago' "$TMP/rota/backups/turnos360-20200101-0330.sql.gz" "$TMP/rota/backups/uploads-20200101-0330.tar.gz"
touch -d '2 days ago' "$TMP/rota/backups/turnos360-20200102-0330.sql.gz"
correr rota BACKUP_REMOTO="$TMP/remoto/"
espero "borra lo de más de 14 días" no_hay 'turnos360-20200101-0330.sql.gz'
espero "y los uploads viejos" no_hay 'uploads-20200101-0330.tar.gz'
espero "conserva lo reciente" hay 'turnos360-20200102-0330.sql.gz'

correr rota_falla FAKE_PG=caida BACKUP_REMOTO="$TMP/remoto/"
mkdir -p "$TMP/rota_falla/backups"
touch -d '20 days ago' "$TMP/rota_falla/backups/turnos360-20200101-0330.sql.gz"
correr rota_falla FAKE_PG=caida BACKUP_REMOTO="$TMP/remoto/"
espero "si el backup de hoy falla, NO borra los viejos" hay 'turnos360-20200101-0330.sql.gz'

echo
if [ "$FALLAS" -gt 0 ]; then
  echo "backup.sh: $FALLAS de $CASOS comprobaciones fallaron."
  exit 1
fi
echo "backup.sh: $CASOS comprobaciones OK."
