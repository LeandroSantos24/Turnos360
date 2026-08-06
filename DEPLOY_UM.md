# Turnos360 — Deploy en UM-Cloud (OpenStack) · Runbook v2

**Qué es esto:** el procedimiento para levantar Turnos360 en la nube de la UM. Es un **ensayo general**: el mismo runbook, cambiando dos archivos, es el de producción en un VPS.

**Por qué la UM es staging y no producción:** el acceso va por la VPN ZeroTier (`a84ac5c10a1a8ff2`). Sin IP pública no hay Let's Encrypt, los clientes de la barbería no pueden entrar a reservar, y **los webhooks de Mercado Pago nunca llegan** (MP tiene que poder hacerte un POST desde internet). Sirve para validar el deploy y para mostrarlo, no para operar.

**Dos caminos según dónde estés parado:**

| Situación | Andá a |
| --- | --- |
| La instancia ya existe y corre una versión anterior | **Parte A — Redeploy** (30–40 min) |
| Instancia nueva desde cero | **Parte B — Instalación completa** (60–90 min) |

---

# PARTE A — Redeploy de una versión nueva

Para la instancia `turnos360` que ya está `Activo` en `10.201.3.78`. **No hace falta destruirla**: borrarla cuesta 40 minutos de reinstalar Docker para no ganar nada. El sistema operativo, el swap y el firewall ya están.

## A.0 — Antes de tocar el servidor: subir el código

> **Este paso es el que más deploys rompe.** El servidor clona desde GitHub. Si el trabajo nuevo está solo en tu máquina, el `git pull` trae la versión vieja y el deploy "sale bien" pero despliega lo de antes.

En tu Kali, **antes** de conectarte:

```bash
cd ~/Documentos/Turnos360
git status --short          # tiene que estar vacío
git log --oneline -1        # anotá el hash: es el que tiene que aparecer en el server
git push origin main
```

Si `git status` muestra archivos, todavía no commiteaste. Frená acá y commiteá primero.

## A.1 — Conectarte

```bash
sudo zerotier-cli listnetworks     # tiene que decir OK
ping -c 3 10.201.3.78
ssh ubuntu@10.201.3.78
```

## A.2 — Backup antes de cualquier cosa

Aunque sean datos de prueba: es la práctica que después salva un cliente real.

```bash
sudo /usr/local/bin/turnos360-backup
ls -lh /var/backups/turnos360/
```

## A.3 — Traer el código

```bash
cd /opt/turnos360
git pull
git log --oneline -1        # tiene que coincidir con el hash de A.0
```

**Si los hashes no coinciden, no sigas.** Estás por deployar otra cosa.

## A.4 — Actualizar el `.env.prod`

La v2 suma variables nuevas. Compará tu archivo contra la plantilla:

```bash
diff <(grep -oE '^[A-Z_]+=' .env.prod.example | sort) \
     <(grep -oE '^[A-Z_]+=' .env.prod | sort)
```

Lo que aparezca con `<` está en la plantilla y falta en tu archivo. Agregalo con `nano .env.prod`. En esta versión son:

```
ZONA_HORARIA=America/Argentina/Buenos_Aires
COBRO_CBU=
COBRO_ALIAS=
COBRO_TITULAR=
COBRO_CUIT=
COBRO_BANCO=
COBRO_MP_LINK=
COBRO_WHATSAPP=
```

Los `COBRO_*` son **tus** datos de cobro: los ve el dueño del negocio en "Mi suscripción" para transferirte. Si los dejás vacíos, esa pantalla sale en blanco.

> `NEXT_PUBLIC_SITE_URL` no se carga a mano: el compose se la pasa al frontend tomando el valor de `PUBLIC_BASE_URL`.

## A.5 — Decidir: ¿base limpia o conservar?

**Conservar los datos** (upgrade en caliente — el camino de producción):

```bash
D="docker compose --env-file .env.prod -f infra/docker-compose.prod.yml"
$D up -d --build
$D exec backend alembic upgrade head
```

Las migraciones nuevas agregan solo columnas opcionales o con valor por defecto, así que los datos existentes sobreviven intactos.

**Empezar de cero** (recomendado para esta demo: pantallas con datos frescos en vez de turnos de prueba viejos):

```bash
D="docker compose --env-file .env.prod -f infra/docker-compose.prod.yml"
$D down -v                    # el -v borra el volumen de la base. Es a propósito acá.
$D up -d --build
$D exec backend alembic upgrade head
$D exec backend python -m app.seeds_minimo
```

> El `-v` **solo** en staging. En el servidor de producción con clientes reales, ese comando es el fin del negocio.

El build tarda 5–15 minutos (compila el frontend).

## A.6 — Cargar datos de demostración

Esto es lo que hace que la demo se vea como un negocio real y no como un sistema recién instalado. Primero creá la empresa desde `/admin` (rubro Barbería, con sus servicios, recursos y horarios), anotá su ID, y después:

```bash
$D exec backend python -m app.seeds_demo --empresa 1
```

Genera ~2 meses de operación hacia atrás: clientes, turnos, cobros y movimientos de caja con las fechas repartidas. Sin esto, "Mes pasado" queda vacío y la curva de facturación es una línea recta — que es exactamente lo que se nota en una demo.

Para rehacerlo: `... python -m app.seeds_demo --empresa 1 --limpiar`.

## A.7 — Verificar

```bash
$D ps                                          # 7 servicios Up, tres healthy
$D exec backend alembic current                # 27 migraciones, termina en (head)
curl -s http://localhost/api/health            # {"status":"ok"}
sudo ss -tlnp | grep -E '5432|6379'            # NO debe devolver NADA
```

Y desde el navegador de tu Kali: `http://10.201.3.78` → landing. `http://10.201.3.78/admin` → panel de super-admin.

**Las tres pantallas que hay que abrir sí o sí después de este redeploy**, porque son las que tocó esta versión:

1. **Mi página** → subir una portada y ver que el hero de la vidriera la tome.
2. **Reglas de reserva** → cambiar la anticipación mínima y confirmar que la vidriera respeta el límite.
3. **Caja** → anular un movimiento y verificar que sigue en el listado pero no suma al total.

Salta a la sección **Operación diaria** al final.

---

# PARTE B — Instalación completa (instancia nueva)

## Fase 0 — Preparar tu máquina (Kali)

### 0.1 Credenciales de OpenStack

En My-UM-Cloud, botón naranja **Cloud_Credentials**. Si es la primera vez sale "Credential creation in progress"; volvé a clickear y aparecen usuario, contraseña y el link al Dashboard (Horizon).

### 0.2 ZeroTier

```bash
curl -s https://install.zerotier.com | sudo bash
sudo zerotier-cli join a84ac5c10a1a8ff2      # esperás: 200 join OK
sudo zerotier-cli info                        # anotá el address (10 caracteres)
```

Con ese address, botón azul **ZeroTier_Config** → pegarlo → **Create_ZT**. Volvé a entrar: tenés que ver tu usuario, tu dirección y un **botón VERDE**. Sin el botón verde no vas a poder llegar a la instancia.

```bash
sudo zerotier-cli listnetworks   # debe decir OK y mostrarte una IP asignada
```

### 0.3 Clave SSH

Si ya tenés una (la que usás con GitHub), reusala. Si no:

```bash
ssh-keygen -t ed25519 -C "turnos360-um"
cat ~/.ssh/id_ed25519.pub
```

## Fase 1 — Crear la instancia en Horizon

**1.1 Subir la clave SSH** · Compute → Pares de claves → Importar clave pública. Nombre `leandro-kali`, tipo SSH Key, y pegás el contenido de tu `.pub`.

**1.2 Security Group** · Red → Grupos de seguridad → Crear, nombre `turnos360-sg`. Reglas de **Ingress**:

| Regla | Puerto | Remote |
| --- | --- | --- |
| SSH | 22 | CIDR de la red ZeroTier (o `0.0.0.0/0`: igual solo se llega por la VPN) |
| HTTP | 80 | igual que arriba |

**No abras 5432 ni 6379.** El compose de producción ya no los publica, pero que tampoco estén en el grupo es la segunda muralla.

**1.3 Lanzar la instancia** · Compute → Instancias → Lanzar instancia:

- **Source:** Ubuntu 24.04 LTS. Boot desde imagen, creando volumen nuevo.
- **Flavor:** `m1.medium` o mayor. Mínimo 2 vCPU / 4 GB / 20 GB.
- **Networks:** la red interna del proyecto.
- **Security Groups:** `turnos360-sg`.
- **Key Pair:** `leandro-kali`.

**1.4 Anotar la IP.** Es la que usás para todo de acá en adelante. La llamamos `<IP>`.

> Si en Red → IPs flotantes el pool ofreciera un rango **público** (no 10.x, no 172.16-31.x, no 192.168.x), avisame: cambiaría el panorama y podríamos ir a producción acá.

**1.5 Probar el acceso**

```bash
ping -c 3 <IP>
ssh ubuntu@<IP>
```

## Fase 2 — Preparar el servidor

Todo lo que sigue es **dentro de la instancia**.

### 2.1 Sistema y Docker

```bash
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y ca-certificates curl git

sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

sudo usermod -aG docker $USER
newgrp docker
docker run --rm hello-world
```

> **Si `apt-get update` falla o Docker no descarga:** la instancia no tiene salida a internet. Es la falla más común en nubes universitarias. Verificá con `curl -I https://download.docker.com`. Sin salida no se puede deployar nada: hay que pedirle NAT saliente al admin de la cátedra.

### 2.2 Swap

El `next build` pide ~1,5–2 GB de RAM. Sin swap, el build muere con un error de memoria críptico.

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
free -h
```

### 2.3 Firewall

```bash
sudo apt-get install -y ufw
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw --force enable
```

## Fase 3 — Traer el código y configurar

### 3.1 Clonar

```bash
sudo mkdir -p /opt/turnos360 && sudo chown $USER:$USER /opt/turnos360
git clone https://github.com/LeandroSantos24/Turnos360.git /opt/turnos360
cd /opt/turnos360
git log --oneline -1        # verificá que sea el commit que pusheaste
```

### 3.2 Generar los secretos

```bash
for n in POSTGRES_PASSWORD SECRET_KEY FERNET_KEY SUPERADMIN_PASS; do
  echo "$n=$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
done
echo "REDIS_PASSWORD=$(python3 -c 'import secrets,string; print("".join(secrets.choice(string.ascii_letters+string.digits) for _ in range(40)))')"
```

**`REDIS_PASSWORD` se genera aparte a propósito**: va dentro de una URL (`redis://:PASS@redis:6379/0`) y los caracteres especiales la romperían.

### 3.3 Armar el `.env.prod`

```bash
cp .env.prod.example .env.prod
nano .env.prod
chmod 600 .env.prod
```

Completá los secretos y, en las URLs, reemplazá `<IP>` por la real:

```
NEXT_PUBLIC_API_URL=http://<IP>/api
PUBLIC_BASE_URL=http://<IP>
API_BASE_URL=http://<IP>/api
CORS_ORIGINS=http://<IP>
UVICORN_WORKERS=2
ZONA_HORARIA=America/Argentina/Buenos_Aires
```

Email: podés dejar `SMTP_*` vacío en staging (los envíos fallan y quedan logueados, no rompen nada). Si querés probarlos, usá una **contraseña de aplicación nueva** de Gmail.

## Fase 4 — Levantar el stack

```bash
cd /opt/turnos360
D="docker compose --env-file .env.prod -f infra/docker-compose.prod.yml"
$D up -d --build            # 5-15 min la primera vez
$D ps
```

Los 7 servicios (`db`, `redis`, `backend`, `worker`, `beat`, `frontend`, `nginx`) tienen que estar `Up`, y `db`/`redis`/`backend` además `healthy`.

```bash
$D exec backend alembic upgrade head
$D exec backend alembic current      # tiene que terminar en (head)
$D exec backend python -m app.seeds_minimo
```

Son **27 migraciones** y crean **38 tablas**.

El seed tiene que decir *"con la clave de SUPERADMIN_PASS"*. **Si dice "clave de DESARROLLO", pará**: `SUPERADMIN_PASS` quedó vacía y el super-admin nació con clave conocida.

## Fase 5 — Verificación

### 5.1 Desde el servidor

```bash
curl -s http://localhost/api/health                            # {"status":"ok"}
curl -s -o /dev/null -w "%{http_code}\n" http://localhost/     # 200
```

### 5.2 Desde tu Kali (por la VPN)

`http://<IP>` → landing. `http://<IP>/admin` → super-admin con `SUPERADMIN_EMAIL` / `SUPERADMIN_PASS`.

### 5.3 Las cuatro pruebas que importan

**a) Que db y redis NO estén expuestos** (el P0 más grave):

```bash
sudo ss -tlnp | grep -E '5432|6379'      # NO debe devolver nada
sudo ss -tlnp | grep ':80'               # solo esto debe aparecer
```

**b) Que el fail-fast funcione:**

```bash
$D run --rm -e FERNET_KEY= backend python -c "from app.core.config import settings"
```

Tiene que **fallar** con el mensaje de FERNET_KEY. Si arranca, `ENV` no está en `prod`.

**c) Que el rate limit cuente por IP real.** Once intentos de login fallidos:

```bash
for i in $(seq 1 11); do
  curl -s -o /dev/null -w "%{http_code} " -X POST http://<IP>/api/auth/login \
    -H "Content-Type: application/json" -d '{"email":"x@x.com","clave":"mala"}'
done; echo
```

Esperado: `401` diez veces y `429` al final. Ese 429 confirma que Nginx pasa la IP real y uvicorn la respeta.

**d) Un día de operación completo.** Creá una empresa, entrá con su usuario, cargá servicio y recurso, sacá un turno, cobralo, cerrá la caja. Es la única prueba que confirma que el sistema **sirve**, no solo que levanta.

## Fase 6 — Backups (no es opcional)

```bash
sudo cp infra/scripts/backup.sh /usr/local/bin/turnos360-backup
sudo cp infra/scripts/restore.sh /usr/local/bin/turnos360-restore
sudo chmod +x /usr/local/bin/turnos360-*

sudo /usr/local/bin/turnos360-backup
ls -lh /var/backups/turnos360/
```

Cron diario a las 3:30:

```bash
sudo crontab -e
# 30 3 * * * /usr/local/bin/turnos360-backup >> /var/log/turnos360-backup.log 2>&1
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

# Operación diaria

```bash
cd /opt/turnos360
D="docker compose --env-file .env.prod -f infra/docker-compose.prod.yml"

$D ps                          # estado
$D logs -f backend             # logs en vivo
$D logs --tail 100 worker
$D restart backend             # reiniciar un servicio
$D down                        # bajar todo (los datos sobreviven en el volumen)
```

**Desplegar una versión nueva:** ver la Parte A de este documento.

> Si cambiaste `NEXT_PUBLIC_API_URL` o `PUBLIC_BASE_URL`, el `--build` es obligatorio: esas variables se hornean en el bundle del frontend en build time. Reiniciar no alcanza.

---

# Problemas frecuentes

**Deployé y no veo lo nuevo.** El `git pull` no trajo nada porque el trabajo no está pusheado. Verificá que el hash de `git log --oneline -1` en el servidor sea el mismo que en tu máquina.

**El frontend no llega a la API / todo da error de red.** Casi siempre `NEXT_PUBLIC_API_URL` mal. Tiene que ser `http://<IP>/api` (con `/api`, sin barra al final) y hay que rebuildear.

**`next build` muere sin explicación clara.** Falta RAM: revisá el swap (2.2).

**El backend reinicia en loop.** `$D logs backend`. Si es el fail-fast de secretos, el mensaje dice cuál falta. Si es la base, mirá que `db` esté `healthy`.

**Redis: `NOAUTH Authentication required`.** El `REDIS_PASSWORD` tiene caracteres que rompen la URL. Regeneralo solo alfanumérico y `$D up -d`.

**429 en todo apenas entrás.** El límite se disparó de una prueba anterior. Esperá un minuto o `$D restart redis` (borra los contadores).

**"Mi suscripción" muestra el CBU vacío.** Faltan los `COBRO_*` en el `.env.prod` (ver A.4).

**Los horarios de los turnos aparecen corridos 3 horas.** Falta `ZONA_HORARIA` en el `.env.prod`.

**No puedo llegar a la instancia.** ZeroTier: `sudo zerotier-cli listnetworks` tiene que decir OK, y el botón de ZeroTier_Config tiene que estar verde.

---

# Después de esto

Cuando el ejercicio esté completo (incluida la restauración probada), el paso a producción es el **mismo runbook** con tres diferencias: la instancia se crea en un VPS con IP pública (São Paulo: 30-40 ms contra Argentina), el DNS de `turnos360.com.ar` apunta a esa IP, y Nginx pasa de `staging.conf` a `produccion.conf.ejemplo` con Let's Encrypt.

Recién ahí sirven las señas: los webhooks de Mercado Pago necesitan poder hacerte un POST desde internet, y eso por VPN no pasa.
