"""Turnos360 — API principal.

Punto de entrada de FastAPI. Acá se montan los routers de cada módulo
y los middlewares transversales (CORS, security headers, rate limiting).
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.rate_limit import limiter
from app.routers import agenda, auth, clientes, recursos, servicios, turnos, membresias, salud, empresa, items, finanzas, estadisticas

app = FastAPI(
    title="Turnos360 API",
    version="0.1.0",
    description="SaaS multiempresa de gestión de turnos · CRM · WhatsApp · Finanzas · Fidelización",
)

# Rate limiting: registramos el limiter y el handler que responde 429 al pasarse.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS: orígenes permitidos según el entorno (configurable por CORS_ORIGINS).
# En dev es localhost:3000; en producción se cargan los dominios reales.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_lista,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def agregar_security_headers(request: Request, call_next):
    """Agrega headers de seguridad a TODA respuesta de la API."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if settings.es_produccion:
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


# Routers
app.include_router(auth.router)
app.include_router(clientes.router)
app.include_router(recursos.router)
app.include_router(agenda.horarios_router)
app.include_router(agenda.excepciones_router)
app.include_router(turnos.router)
app.include_router(servicios.router)
app.include_router(membresias.router)
app.include_router(salud.router)
app.include_router(empresa.router)
app.include_router(items.router)
app.include_router(finanzas.router)
app.include_router(estadisticas.router)


@app.get("/", tags=["meta"])
def root() -> dict:
    return {"producto": "Turnos360", "version": app.version, "env": settings.env, "docs": "/docs"}


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}