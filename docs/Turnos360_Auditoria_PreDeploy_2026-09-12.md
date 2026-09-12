# Turnos360 — Auditoría pre-deploy (parte 1: seguridad e infraestructura)

Fecha: 2026-09-12 · Commit auditado: `e15e6c9` · Alcance de esta parte: autenticación,
autorización multi-tenant, secretos, Docker/infra, dependencias.

Pendiente para la parte 2: base de datos y rendimiento, código muerto, N+1,
índices, bundle del frontend.

---

## 🔴 CRÍTICO — resolver antes del deploy

### C1. El volumen `uploads` está declarado pero no montado

`infra/docker-compose.prod.yml` declara el volumen al final:

```yaml
volumes:
  pgdata:
  uploads:
```

pero **ningún servicio lo monta**. Verificado servicio por servicio: sólo `db`
(`pgdata`) y `nginx` (el `.conf`) tienen `volumes:`. El backend no tiene ninguno.

`UPLOADS_DIR` vale `/app/uploads` (default de `core/config.py`), así que las fotos
viven **dentro del contenedor**. El primer `docker compose up -d --build backend`
borra el logo, la portada, las fotos del equipo y la galería de **todos** los
clientes, sin aviso y sin recuperación.

Es exactamente el desastre que el propio comentario del `config.py` advierte
("Tiene que ser un VOLUMEN en producción") y que el comentario del volumen
repite al pie. La declaración quedó huérfana.

**Solución** — montar en `backend` y en `worker` (el worker también escribe si
alguna tarea toca imágenes):

```yaml
  backend:
    volumes:
      - uploads:/app/uploads
```

Ojo con los permisos: el contenedor corre como `app` (uid 10001) y `/app/uploads`
no existe en la imagen, así que Docker crea el volumen vacío y **root-owned**, y
el primer `mkdir` del backend falla con `PermissionError`. Hay que crear la
carpeta con dueño correcto en el `Dockerfile.prod`, antes del `USER app`:

```dockerfile
RUN mkdir -p /app/uploads && chown app:app /app/uploads
```

Docker copia dueño y permisos de la carpeta de la imagen al inicializar el
volumen, así que con eso queda como `app:app`.

**Verificación:** subir una foto, `docker compose ... up -d --build backend`,
confirmar que la foto sigue estando.

---

## 🟠 IMPORTANTE — recomendable antes del deploy

### I1. Los headers de seguridad no cubren el frontend, y no hay CSP

El middleware de `app/main.py` agrega `X-Content-Type-Options`, `X-Frame-Options: DENY`,
`Referrer-Policy` y `HSTS`, pero **sólo a las respuestas de la API**. Las páginas HTML
del panel las sirve Next.js, y nginx las pasa tal cual: no llevan ninguno de esos
headers. El panel entero es embebible en un iframe → clickjacking.

Además **no hay `Content-Security-Policy` en ningún lado** (grep en todo el repo:
un solo `X-Frame-Options`, ninguna CSP).

**Solución simple** (preferible a tocar Next): agregar los headers en el bloque
`location /` de nginx, que cubre todo el frontend de una vez.

```nginx
add_header X-Frame-Options        "DENY"                          always;
add_header X-Content-Type-Options "nosniff"                       always;
add_header Referrer-Policy        "strict-origin-when-cross-origin" always;
```

La CSP conviene arrancarla en `Content-Security-Policy-Report-Only` y mirar qué
rompe antes de enforzarla — Next inyecta scripts inline y una CSP estricta sin
nonce tira el panel abajo.

### I2. Los tokens viven en `localStorage`

`src/lib/auth.ts` y `src/lib/admin-api.ts` guardan access y refresh en `localStorage`.
Cualquier XSS lee el token del super-admin y del dueño; `httpOnly` no aplica.

No hay XSS conocido en el código (React escapa por default, no vi `dangerouslySetInnerHTML`),
así que **no es crítico hoy** — pero es el multiplicador que convierte cualquier XSS
futuro en toma de cuenta completa. Combinado con I1 (sin CSP), no hay segunda línea.

Pasarlo a cookie `httpOnly` + `SameSite=Strict` es trabajo real (afecta login, refresh,
el interceptor de `api.ts` y el panel admin). **Recomiendo hacer I1 ahora y tratar I2
como tarea aparte post-deploy**, no meterlo en el mismo empujón.

### I3. `next build` ignora errores de tipos y de lint

```js
typescript: { ignoreBuildErrors: true },
eslint:     { ignoreDuringBuilds: true },
```

Los ~28 errores están documentados como deuda conocida (firma de `@base-ui`), y el
`typecheck-baseline.txt` es una buena mitigación. Pero con el flag en `true` un error
**nuevo** entra a producción sin que nadie se entere. La red la pone el baseline; hay
que asegurarse de que `npm run typecheck` corra en CI y frene el merge.

### I4. Las dependencias de Python no están fijadas

`pyproject.toml` usa `>=` en las 15 dependencias y no hay lock. `pip install .` en el
build de Docker puede traer una versión distinta de la que probaste — y el build de
producción es el que menos querés que sea irreproducible.

**Solución:** generar un `requirements.txt` con `pip freeze` desde el entorno que
funciona y que `Dockerfile.prod` instale de ahí.

---

## 🟡 MEJORA — no bloquea el deploy

### M1. Bomba de descompresión en la subida de imágenes

`routers/subidas.py` está muy bien resuelto (re-codifica en vez de validar, nombre
por uuid, tamaño decidido por el servidor, tope de 8 MB, EXIF descartado). Dos huecos
menores:

- No se fija `Image.MAX_IMAGE_PIXELS`. El default de Pillow es 89 M píxeles y recién
  corta a 2×. Un PNG de 8 MB muy comprimido puede decodificar a ~400 MB de RAM, contra
  un `mem_limit: 640m` con 2 workers.
- **Verificado:** `Image.DecompressionBombError` hereda directo de `Exception`, no de
  `OSError` ni `ValueError` — el `except (UnidentifiedImageError, OSError, ValueError)`
  **no lo atrapa**. Sale 500 en vez de 400.

```python
Image.MAX_IMAGE_PIXELS = 40_000_000
# y agregar Image.DecompressionBombError al except
```

### M2. `frontend/.dockerignore` es de dos líneas

Sólo `node_modules` y `.next`. El del backend excluye cuidadosamente `.env*`; el del
frontend no. `Dockerfile.prod` hace `COPY . .` en el stage de build, y Next **carga
`.env.local` automáticamente en build time**. Hoy no hay ningún `.env` en `frontend/`,
así que no hay fuga — pero el día que aparezca uno, se hornea en el bundle.

Agregar `.env`, `.env.*`, `!.env.example`.

### M3. Advisories de Next 14.2.35 — la mayoría no aplica

`npm audit` lista 8 vulnerabilidades (7 high, 1 critical) y propone `next@16`, que es
breaking. Revisé cuáles aplican de verdad:

| Advisory | ¿Aplica? |
|---|---|
| RCE en Image Optimization (AVIF) | **No** — `images: { unoptimized: true }` elimina `/_next/image` |
| RCE en servidores Windows | **No** — corre en Alpine |
| Bypass de middleware con i18n | **No** — no hay `middleware.ts` ni i18n |
| SSRF en rewrites | **No** — no hay rewrites |
| DoS / SSRF en Server Actions | **No** — cero `"use server"` en `src/` |
| Cache poisoning en respuestas RSC | **Posible** — App Router con RSC |
| Exposición de Server Function endpoints | **Posible** |
| postcss `<=8.5.22` | Sólo build time, fuente confiable |

O sea: el `unoptimized: true` ya neutralizó la crítica, y eso está bien pensado.
Quedan dos de cache que conviene mirar, pero **no justifican saltar a Next 16 antes
del deploy**. Tratalo como tarea propia.

---

## 🟢 OK — revisado y correcto

- **Aislamiento multi-tenant.** Barrido automático de los 22 routers: todo endpoint con
  `{id}` en la ruta scopea por `empresa_id`. Los únicos sin scope son los públicos por
  `slug` (`/publico/{slug}`), que es correcto — el slug *es* el selector de tenant.
- **Scope de tokens.** `SCOPE_EMPRESA` / `SCOPE_SUPERADMIN` impide que el token del
  panel de super-admin sea aceptado como el usuario con ese mismo id numérico.
- **Revocación de sesiones.** El claim `tv` contra `usuario.token_version` invalida al
  instante todo token emitido antes de un cambio de contraseña, incluido el refresh de
  7 días guardado en otro dispositivo.
- **Empresa pausada.** Se relee de la base en cada request, así que pausar corta también
  los tokens ya emitidos.
- **Endpoints de super-admin de WhatsApp.** `router_admin` usa `SuperAdminActual`, no
  `gate_dueno`: no hay IDOR entre empresas.
- **Historia clínica.** Router con `gate_clinico` (recepción afuera) y auditoría de
  **lectura**, no sólo de escritura. Correcto para Ley 25.326.
- **Rate limiting.** Por IP real: nginx pisa `X-Real-IP` con `$remote_addr` y uvicorn
  corre con `--forwarded-allow-ips=172.16.0.0/12` (no `*`), así que el cliente no elige
  la clave del límite. Límites sensatos en login (10/min), admin login (5/min),
  registro (3/h), olvidé-contraseña (3/min).
- **Fail-fast de producción.** `ENV=prod` sin `SECRET_KEY` o `FERNET_KEY` real no levanta.
  `FERNET_KEY` obligatoriamente distinta de `SECRET_KEY`.
- **Interruptores validados.** `WA_PROVEEDOR`, `MP_FIRMA_MODO` y `ENV` con valores
  cerrados: un typo no levanta el backend en vez de cambiar el comportamiento en silencio.
- **Fortaleza de clave del super-admin.** Criterio NIST SP 800-63B (largo y listas, no
  composición), con las credenciales del propio repo en la lista negra.
- **Secretos fuera de git.** `.env` ignorado, sólo los `.example` versionados. Confirmado
  con `git ls-files`.
- **Variables públicas del frontend.** Sólo `NEXT_PUBLIC_API_URL` y `NEXT_PUBLIC_SITE_URL`;
  ambas son URLs, ninguna es secreto.
- **Docker.** Multi-stage, usuario sin privilegios en backend (uid 10001) y frontend
  (`nextjs`), `db` y `redis` sin puertos publicados, Redis con contraseña y `noeviction`,
  `mem_limit` por servicio, rotación de logs, healthchecks reales (`/ready` mira base y
  Redis; `/health` a propósito no).
- **Docs de la API cerradas en producción** (`docs_url=None` con `ENV=prod`).
- **Subida de imágenes.** Re-codificación con Pillow en vez de validar extensión o
  content-type; nombre por uuid; tamaño decidido por el servidor; EXIF descartado.

---

## Nota sobre `nginx` en el compose de producción

`docker-compose.prod.yml` monta `nginx/staging.conf`, que es HTTP plano, y el puerto 443
está comentado. Está documentado como decisión deliberada para el staging de la UM (sin
IP pública no hay Let's Encrypt). **No es un hallazgo** — pero es el paso que falta
tildar el día del deploy real: cambiar el montaje a `produccion.conf.ejemplo`,
descomentar 443 y los volúmenes de certbot.
