# Turnos360 — Deploy en UM-Cloud (OpenStack) · Runbook de staging

**Qué es esto:** el procedimiento completo para levantar Turnos360 en la nube de la UM, de punta a punta. Es un **ensayo general**: el mismo runbook, cambiando dos archivos, es el de producción en un VPS.

**Por qué la UM es staging y no producción:** el acceso va por la VPN ZeroTier (`a84ac5c10a1a8ff2`). Sin IP pública no hay Let's Encrypt, los clientes de la barbería no pueden entrar a reservar, y **los webhooks de Mercado Pago nunca llegan** (MP tiene que poder hacerte un POST desde internet). Sirve para validar el deploy, no para operar.

**Tiempo estimado:** 60–90 minutos la primera vez.

---

## Fase 0 — Preparar tu máquina (Kali)

### 0.1 Credenciales de OpenStack

En My-UM-Cloud, botón naranja **Cloud_Credentials**. Si es la primera vez sale "Credential creation in progress"; volvé a clickear y aparecen usuario, contraseña y el link al Dashboard (Horizon). Anotalas.

### 0.2 ZeroTier

```bash
curl -s https://install.zerotier.com | sudo bash
sudo zerotier-cli join a84ac5c10a1a8ff2      # esperás: 200 join OK
sudo zerotier-cli info                        # anotá el address (10 caracteres)
```

Con ese address, botón azul **ZeroTier_Config** → pegarlo → **Create_ZT**. Volvé a entrar a ZeroTier_Config: tenés que ver tu usuario, tu dirección y un **botón VERDE**. Sin el botón verde no vas a poder llegar a la instancia, así que no sigas hasta verlo.

```bash
sudo zerotier-cli listnetworks   # debe decir OK y mostrarte una IP asignada
```

### 0.3 Clave SSH

Si ya tenés `~/.ssh/id_ed25519.pub` (la que usás con GitHub), reusala. Si no:

```bash
ssh-keygen -t ed25519 -C "turnos360-um"
cat ~/.ssh/id_ed25519.pub
```

---

## Fase 1 — Crear la instancia en Horizon

Entrá al Dashboard con las credenciales del paso 0.1.

**1.1 Subir la clave SSH** · Compute → Key Pairs → Import Public Key. Nombre `leandro-kali`, tipo SSH Key, y pegás el contenido de tu `.pub`.

**1.2 Security Group** · Network → Security Groups → Create Security Group, nombre `turnos360-sg`. Agregá reglas de **Ingress**:

| Regla | Puerto | Remote |
| --- | --- | --- |
| SSH | 22 | CIDR de la red ZeroTier (o `0.0.0.0/0` si no lo sabés: igual solo se llega por la VPN) |
| HTTP | 80 | igual que arriba |

**No abras 5432 ni 6379.** El compose de producción ya no los publica, pero que tampoco estén en el grupo es la segunda muralla.

**1.3 Lanzar la instancia** · Compute → Instances → Launch Instance:

- **Source:** Ubuntu 24.04 LTS (o 22.04). Boot desde imagen, creando volumen nuevo.
- **Flavor:** el más grande que te permita la cuota. Mínimo 2 vCPU / 4 GB / 20 GB. Con 2 GB también anda, pero el build del frontend va justo (ver 2.2).
- **Networks:** la red interna del proyecto.
- **Security Groups:** `turnos360-sg`.
- **Key Pair:** `leandro-kali`.

**1.4 Anotar la IP.** En la lista de instancias vas a ver su IP (algo tipo `10.x.x.x` o `172.16.x.x`). **Esa IP es la que usás para todo de acá en adelante.** Vamos a llamarla `<IP>`.

> Si en Network → Floating IPs el pool ofreciera un rango **público** (no 10.x, no 172.16-31.x, no 192.168.x), avisame: cambiaría el panorama y podríamos ir a producción acá.

**1.5 Probar el acceso**

```bash
ping -c 3 <IP>
ssh ubuntu@<IP>
```

Si el ping falla: revisá el botón verde de ZeroTier (0.2) y que la instancia esté ACTIVE en Horizon.

---

## Fase 2 — Preparar el servidor

Todo lo que sigue es **dentro de la instancia** (después del `ssh`).

### 2.1 Sistema y Docker

```bash
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y ca-certificates curl git

# Docker (repo oficial)
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

sudo usermod -aG docker $USER
newgrp docker          # o cerrás sesión y volvés a entrar
docker run --rm hello-world
```

> **Si el `apt-get update` falla o Docker no descarga:** la instancia no tiene salida a internet. Es la falla más común en nubes universitarias. Verificá con `curl -I https://download.docker.com`. Si no hay salida, hay que pedirle al admin de la cátedra que habilite NAT saliente o un proxy — sin eso no se puede deployar nada. Avisame y vemos alternativas.

### 2.2 Swap (importante si la instancia tiene 2 GB)

El `next build` pide ~1.5–2 GB de RAM. Sin swap, el build muere con un error de memoria críptico.

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
free -h        # tiene que aparecer la línea Swap
```

### 2.3 Firewall del sistema

```bash
sudo apt-get install -y ufw
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw --force enable
sudo ufw status
```

---

## Fase 3 — Traer el código y configurar

### 3.1 Clonar

```bash
sudo mkdir -p /opt/turnos360 && sudo chown $USER:$USER /opt/turnos360
git clone https://github.com/LeandroSantos24/Turnos360.git /opt/turnos360
cd /opt/turnos360
```

(Repo público, así que HTTPS alcanza. Si lo hacés privado, generá una deploy key.)

### 3.2 Generar los secretos

```bash
for n in POSTGRES_PASSWORD SECRET_KEY FERNET_KEY SUPERADMIN_PASS; do
  echo "$n=$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
done
echo "REDIS_PASSWORD=$(python3 -c 'import secrets,string; print("".join(secrets.choice(string.ascii_letters+string.digits) for _ in range(40)))')"
```

Copiá la salida a un lado. **`REDIS_PASSWORD` se genera aparte a propósito**: va dentro de una URL (`redis://:PASS@redis:6379/0`) y los caracteres especiales la romperían.

### 3.3 Armar el `.env.prod`

```bash
cp .env.prod.example .env.prod
nano .env.prod
```

Completá con los secretos generados y, en las URLs, reemplazá `<IP>` por la IP real de tu instancia:

```
NEXT_PUBLIC_API_URL=http://<IP>/api
PUBLIC_BASE_URL=http://<IP>
API_BASE_URL=http://<IP>/api
CORS_ORIGINS=http://<IP>
UVICORN_WORKERS=2
```

Email: podés dejar `SMTP_*` vacío en staging (los envíos fallan y quedan logueados, no rompen nada). Si querés probar los emails, poné una **contraseña de aplicación nueva** de Gmail — la actual viajó dentro de un zip.

```bash
chmod 600 .env.prod       # que no lo lea cualquiera
```

---

## Fase 4 — Levantar el stack

### 4.1 Build y arranque

```bash
cd /opt/turnos360
docker compose --env-file .env.prod -f infra/docker-compose.prod.yml up -d --build
```

La primera vez tarda **5–15 minutos** (compila el frontend). Después:

```bash
docker compose --env-file .env.prod -f infra/docker-compose.prod.yml ps
```

Los 7 servicios (`db`, `redis`, `backend`, `worker`, `beat`, `frontend`, `nginx`) tienen que estar `Up`, y `db`/`redis`/`backend` además `healthy`.

### 4.2 Migraciones

```bash
docker compose --env-file .env.prod -f infra/docker-compose.prod.yml exec backend alembic upgrade head
docker compose --env-file .env.prod -f infra/docker-compose.prod.yml exec backend alembic current
```

Lo segundo tiene que terminar en `(head)`. Son 19 migraciones y crean 37 tablas.

### 4.3 Seed inicial

```bash
docker compose --env-file .env.prod -f infra/docker-compose.prod.yml exec backend python -m app.seeds_minimo
```

Tiene que decir *"con la clave de SUPERADMIN_PASS"*. **Si dice "clave de DESARROLLO", pará**: significa que `SUPERADMIN_PASS` quedó vacía en el `.env.prod` y el super-admin nació con clave conocida.

---

## Fase 5 — Verificación

### 5.1 Desde el servidor

```bash
curl -s http://localhost/api/health          # {"status":"ok"}
curl -s -o /dev/null -w "%{http_code}\n" http://localhost/    # 200
```

### 5.2 Desde tu Kali (por la VPN)

```bash
curl -s http://<IP>/api/health
```

Y en el navegador: `http://<IP>` → tiene que cargar la landing. `http://<IP>/admin` → panel de super-admin, entrás con `SUPERADMIN_EMAIL` / `SUPERADMIN_PASS`.

### 5.3 Las cuatro pruebas que importan

**a) Que db y redis NO estén expuestos** (el P0 más grave):

```bash
sudo ss -tlnp | grep -E '5432|6379'      # NO debe devolver nada
sudo ss -tlnp | grep ':80'               # solo esto debe aparecer
```

**b) Que el fail-fast funcione.** En el servidor, probá arrancar el backend sin FERNET_KEY:

```bash
docker compose --env-file .env.prod -f infra/docker-compose.prod.yml run --rm -e FERNET_KEY= backend python -c "from app.core.config import settings"
```

Tiene que **fallar** con el mensaje de FERNET_KEY. Si arranca, `ENV` no está en `prod`.

**c) Que el rate limit cuente por IP real.** Once intentos de login fallidos seguidos:

```bash
for i in $(seq 1 11); do
  curl -s -o /dev/null -w "%{http_code} " -X POST http://<IP>/api/auth/login \
    -H "Content-Type: application/json" -d '{"email":"x@x.com","clave":"mala"}'
done; echo
```

Esperado: `401` diez veces y `429` al final. Ese 429 confirma que Nginx pasa la IP real y uvicorn la respeta.

**d) Un día de operación completo.** Desde el panel: creá una empresa de prueba, entrá con su usuario, cargá un servicio y un recurso, sacá un turno desde la agenda, cobralo, cerrá la caja. Es la verificación de tu doc maestra y la única que prueba que el sistema **sirve**, no solo que levanta.

---

## Fase 6 — Backups (no es opcional)

```bash
sudo cp infra/scripts/backup.sh /usr/local/bin/turnos360-backup
sudo cp infra/scripts/restore.sh /usr/local/bin/turnos360-restore
sudo chmod +x /usr/local/bin/turnos360-*

sudo /usr/local/bin/turnos360-backup      # probalo a mano primero
ls -lh /var/backups/turnos360/
```

Cron diario a las 3:30:

```bash
sudo crontab -e
# agregar:
30 3 * * * /usr/local/bin/turnos360-backup >> /var/log/turnos360-backup.log 2>&1
```

**La prueba de restauración — hacela ahora, con datos de prueba:**

```bash
# 1. Anotá cuántos turnos tenés en el panel
# 2. Borrá algo (un cliente de prueba)
# 3. Restaurá:
sudo /usr/local/bin/turnos360-restore /var/backups/turnos360/turnos360-<fecha>.sql.gz
# 4. Verificá en el panel que el cliente borrado volvió
```

Un backup que nunca restauraste no es un backup. Esta es la parte del ejercicio que más vale.

---

## Operación diaria

```bash
cd /opt/turnos360
D="docker compose --env-file .env.prod -f infra/docker-compose.prod.yml"

$D ps                          # estado
$D logs -f backend             # logs en vivo
$D logs --tail 100 worker
$D restart backend             # reiniciar un servicio
$D down                        # bajar todo (los datos sobreviven en el volumen)
```

**Desplegar una versión nueva:**

```bash
cd /opt/turnos360
sudo /usr/local/bin/turnos360-backup          # SIEMPRE backup antes
git pull
$D up -d --build
$D exec backend alembic upgrade head
$D ps
```

> Si cambiaste `NEXT_PUBLIC_API_URL`, el `--build` es obligatorio: esa variable se hornea en el bundle del frontend en build time. Reiniciar no alcanza.

---

## Problemas frecuentes

**El frontend no llega a la API / todo da error de red.** Casi siempre `NEXT_PUBLIC_API_URL` mal. Verificá que sea `http://<IP>/api` (con `/api`, sin barra al final) y rebuildeá el frontend.

**`next build` muere sin explicación clara.** Falta RAM: revisá el swap (2.2).

**El backend reinicia en loop.** `$D logs backend`. Si es el fail-fast de secretos, el mensaje te dice cuál falta. Si es la base, mirá que `db` esté `healthy`.

**Redis: `NOAUTH Authentication required`.** El `REDIS_PASSWORD` del `.env.prod` tiene caracteres que rompen la URL. Regeneralo solo alfanumérico y `$D up -d`.

**429 en todo apenas entrás.** El límite se disparó de una prueba anterior. Esperá un minuto o `$D restart redis` (borra los contadores).

**No puedo llegar a la instancia.** ZeroTier: `sudo zerotier-cli listnetworks` tiene que decir OK, y el botón de ZeroTier_Config tiene que estar verde.

---

## Después de esto

Cuando el ejercicio esté completo (incluida la restauración probada), el paso a producción en Vultr es el **mismo runbook** con tres diferencias: la instancia se crea en Vultr en vez de Horizon, el DNS de `turnos360.com.ar` apunta a la IP pública, y Nginx pasa de `staging.conf` a `produccion.conf.ejemplo` con Let's Encrypt (las instrucciones están comentadas dentro de ese archivo). Todo lo demás —compose, secretos, migraciones, seed, backups— es idéntico.
