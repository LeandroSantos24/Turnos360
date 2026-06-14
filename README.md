# Turnos360

SaaS multiempresa de gestión de turnos · CRM · WhatsApp · Finanzas · Fidelización.

> Documentación completa: `docs/Turnos360_Documentacion_Maestra_v4.docx` · Seguimiento: `Turnos360_Tablero_de_Estado.xlsx` · ER: `docs/turnos360.dbml` (pegar en [dbdiagram.io](https://dbdiagram.io)).

## Stack

| Capa | Tecnología |
| --- | --- |
| Backend | Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic |
| Base de datos | PostgreSQL 16 (JSONB, RLS) |
| Cola / tareas | Redis · Celery (workers + beat) |
| Frontend | Next.js · React · TypeScript · Tailwind CSS |
| Mensajería | WhatsApp Cloud API · Resend/SendGrid + Jinja2 |
| Infra | Docker Compose · Nginx + Certbot · GitHub Actions |

## Reglas innegociables (resumen — detalle en la doc §9)

1. **Multi-tenant por fila:** toda tabla lleva `empresa_id`, toda query filtra por él vía `get_current_empresa()`.
2. Lo reservable es un **Recurso** (persona / box / equipo).
3. `Turno.tipo` con sus **5 formas** desde el día uno.
4. Lo específico de cada rubro vive en **configuración** (`config_pack` / `campos_rubro`). Prohibido `if rubro == "X"`.
5. **Datos de salud:** acceso restringido + auditoría de cada lectura. Nunca viajan por WhatsApp/email.
6. **Mensajería siempre asíncrona** por Celery, registrada en `Mensaje`.
7. Credenciales de WhatsApp/email **por empresa y encriptadas**.

## Setup (una sola vez)

```bash
# Dependencias del sistema (Kali / Debian)
sudo apt update && sudo apt install -y docker.io docker-compose-v2 git
sudo usermod -aG docker $USER   # cerrar sesión y volver a entrar

# Node LTS para el frontend (vía nvm)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
nvm install --lts

# Variables de entorno
cp .env.example .env
```

## Desarrollo diario

```bash
make up        # levanta PostgreSQL + Redis + API (http://localhost:8000/docs)
make logs      # logs en vivo
make test      # tests del backend
make down      # apagar todo

# Frontend (en otra terminal)
cd frontend && npm install && npm run dev   # http://localhost:3000
```

## Estructura

```
backend/    FastAPI: app/ (core, models, routers, services), tests/
frontend/   Next.js: app/ (panel del negocio + landing pública)
infra/      docker-compose.yml, nginx, scripts de backup/deploy
docs/       Documentación maestra + ER (turnos360.dbml)
```

## Etapas (estado)

MVP = **E0 → E8** con el rubro barbería. No se avanza de etapa sin pasar su VERIFICACIÓN (doc §8).

- [x] Diseño del producto y documentación maestra
- [ ] **E0** Análisis y diseño final ← _en curso_
- [ ] E1 Base de datos completa · E2 API núcleo · E3 Panel · E4 Landing · E5 Super-admin · E6 WhatsApp · E7 Email · E8 Automatizaciones → **LANZAR**
- [ ] E9–E16 (seguridad, finanzas, fidelización, packs, estadísticas, SaaS)


# 1. Pararte en el proyecto (ya estás ahí)
cd ~/Documentos/Turnos360

# 2. Levantar los 3 servicios (Postgres + Redis + API)
make up

# 3. Verificar que están vivos
make ps        # los 3 deben decir "Up" / "healthy"

# 4. Prueba rápida de que la API responde
curl http://localhost:8000/health    # {"status":"ok"}

# 5. Entrar al contenedor 
make sh

# 6 Ver la base 
make psql
salir \q

# 7 Guardar trabajo 
git add . && git commit -m "..." && git push

# 8 Apagar 
make down

{
  "email": "dueno@lacueva.com",
  "clave": "demo1234"
}