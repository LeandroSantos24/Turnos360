# Turnos360 — Deploy a producción (VPS con IP pública)

Base: el mismo stack del runbook de la UM (`DEPLOY_UM.md`, Parte B para instalar Docker, swap y firewall). Acá solo lo que cambia en producción.

## 0. Antes (una sola vez)

1. DNS: `turnos360.com.ar` y `www` → IP del VPS.
2. Firewall: abiertos solo 22, 80 y 443.
3. `.env.prod` NUEVO desde la plantilla actual (`cp .env.prod.example .env.prod`), no el de la UM: aquel tiene URLs `http://localhost` y comentarios en la misma línea que la variable. Comentarios siempre en su propia línea. Obligatorias: `POSTGRES_*`, `REDIS_PASSWORD` (solo alfanumérico), `SECRET_KEY`, `FERNET_KEY` (distintas, ≥32), `NEXT_PUBLIC_API_URL`, `PUBLIC_BASE_URL`, `API_BASE_URL`, `CORS_ORIGINS` (https y con `/api` donde corresponde, ver la plantilla).
4. Super-admin: crearlo con `SUPERADMIN_EMAIL`/`SUPERADMIN_PASS` (clave nueva, larga). Una clave de super-admin estuvo escrita en `seeds.py` en commits viejos de este repo público: si algún entorno la usa, cambiala.
5. **Guardar `.env.prod` fuera del servidor** (gestor de contraseñas). Sin `FERNET_KEY` las credenciales de MP/WhatsApp guardadas en la base no se pueden descifrar aunque tengas el backup.
6. Certificado (con el puerto 80 libre, antes del primer `up`):

```
sudo apt install -y certbot
sudo certbot certonly --standalone -d turnos360.com.ar -d www.turnos360.com.ar
sudo mkdir -p /var/www/certbot
cp infra/nginx/produccion.conf.ejemplo infra/nginx/produccion.conf
```

7. Backups fuera del servidor y alertas (detalle en la sección 3): clave SSH de root hacia la máquina de backup, los scripts instalados y en `sudo crontab -e`:

```
30 3 * * * BACKUP_REMOTO=usuario@host:/backups/turnos360/ BACKUP_PING_URL=https://hc-ping.com/<uuid-backup> /usr/local/bin/turnos360-backup >> /var/log/turnos360-backup.log 2>&1
0 5 * * 1 VERIFICAR_PING_URL=https://hc-ping.com/<uuid-verificacion> /usr/local/bin/turnos360-verificar-backup $(ls -1t /var/backups/turnos360/turnos360-*.sql.gz | head -1) >> /var/log/turnos360-backup.log 2>&1
0 4 * * 1 certbot renew --webroot -w /var/www/certbot --quiet && docker exec turnos360-prod-nginx-1 nginx -s reload
```

## 1. Deploy

```
cd /opt/turnos360
sudo /usr/local/bin/turnos360-backup
git log --oneline -1
git pull
git log --oneline -1
D="docker compose --env-file .env.prod -f infra/docker-compose.prod.yml -f infra/docker-compose.https.yml"
$D up -d --build
$D exec backend alembic upgrade head
$D exec backend python -m app.seeds_minimo
$D ps
curl -fsS https://turnos360.com.ar/api/ready
curl -s https://turnos360.com.ar/api/estado
```

`/api/estado` puede decir `"tareas": "esperando"` los primeros 15 minutos después de un deploy (beat manda el primer latido a los 5): es normal.

Anotá el hash ANTERIOR (primer `git log`): es el de rollback.

Verificar: login de un negocio, «Mi suscripción», `/admin/cobranza`, una reserva de prueba en la vidriera.

Mercado Pago (cuenta Turnos360): webhook `https://turnos360.com.ar/api/publico/mp/webhook-suscripcion` con eventos de **pagos**. Arrancar con `MP_FIRMA_MODO=log`; cuando los logs muestren que la firma valida, pasar a `enforce` y `$D up -d`.

## 2. Rollback

**Código (lo normal, sin tocar la base).** Las migraciones 0007 y 0008 solo agregan; el código anterior funciona con el esquema nuevo (probado).

```
cd /opt/turnos360
git checkout <hash-anterior>
$D up -d --build
```

**Base (solo si hay datos dañados).** Restaurar el backup que se tomó antes del deploy:

```
sudo /usr/local/bin/turnos360-restore /var/backups/turnos360/turnos360-<fecha>.sql.gz
```

No usar `alembic downgrade` en producción: borra las tablas de eventos y auditoría.

**Fotos y comprobantes** (si se perdió el volumen):

```
$D exec -T backend tar xzf - -C /app < /var/backups/turnos360/uploads-<fecha>.tar.gz
```

## 3. Observabilidad y alertas

Tres avisos externos cubren todo; ninguno corre en el VPS (si el VPS muere, igual avisan).

### Sentry (errores de la API, el worker y beat)

1. En sentry.io: proyecto **Python → FastAPI**. Copiar el DSN a `SENTRY_DSN` en `.env.prod` y `$D up -d` (no hace falta rebuild).
2. Alertas: la regla por defecto («nuevo issue» por email) alcanza para arrancar.
3. Probar que llega (manda un mensaje, no rompe nada):

```
$D exec backend python -c "import sentry_sdk; from app.core.observabilidad import iniciar_sentry; iniciar_sentry('prueba'); sentry_sdk.capture_message('Prueba de Sentry desde producción'); sentry_sdk.flush(5)"
```

No viajan cuerpos de pedidos, variables locales, cookies, IPs, emails, tokens ni CBU/CUIT (ver `app/core/observabilidad.py`). Sin `SENTRY_DSN`, o con Sentry caído, todo sigue funcionando.

### Monitor externo (UptimeRobot, Better Stack o similar)

| Monitor | URL | Condición | Intervalo |
|---|---|---|---|
| API + base + Redis + worker/beat | `https://turnos360.com.ar/api/estado` | HTTP 200 | 5 min, alertar tras 2 fallas |
| Web (Nginx + TLS + Next) | `https://turnos360.com.ar/` | HTTP 200 y la palabra `Turnos360` | 5 min |
| Certificado | `turnos360.com.ar` | vence en menos de 14 días | diario (casi todos lo traen incluido) |

No usar `/api/health` (solo dice que el proceso existe) ni `/api/ready` (no mira el worker). `/api/estado` devuelve solo ok/falla por componente.

### Backups (Healthchecks.io, plan gratis)

1. Crear dos checks: **backup** (período 1 día, gracia 2 h) y **verificación** (período 7 días, gracia 1 día). Cada uno da una URL `https://hc-ping.com/<uuid>`.
2. Ponerlas en el crontab de arriba (`BACKUP_PING_URL` y `VERIFICAR_PING_URL`).
3. Instalar el verificador: `sudo cp infra/scripts/verificar-backup.sh /usr/local/bin/turnos360-verificar-backup && sudo chmod +x /usr/local/bin/turnos360-verificar-backup`.
4. Probar: `sudo BACKUP_REMOTO=usuario@host:/backups/turnos360/ BACKUP_PING_URL=https://hc-ping.com/<uuid-backup> /usr/local/bin/turnos360-backup` y ver el check en verde.

Avisa si el backup falla (base caída, disco lleno, dump incompleto, copia remota fallida) y también si **no corre** (cron roto, VPS apagado). Los dumps quedan con permisos 600. La retención del lado remoto la maneja esa máquina (por ejemplo `find /backups/turnos360 -mtime +30 -delete` en su cron).

### Después de un reinicio del VPS

```
sudo systemctl is-enabled docker
$D ps
curl -s https://turnos360.com.ar/api/estado
```

`docker` tiene que decir `enabled`; los servicios vuelven solos (`restart: unless-stopped`) y en ~1 minuto `ps` muestra `healthy` en db, redis, backend y frontend. Si no vuelve, el monitor externo avisa.
