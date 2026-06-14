"""Turnos360 — API principal.

Punto de entrada de FastAPI. Acá se montan los routers de cada módulo.
En E2 arranca con auth; los CRUDs y el motor de turnos se suman después.
"""

from fastapi import FastAPI

from app.core.config import settings
from app.routers import agenda, auth, clientes, recursos, servicios, turnos

app = FastAPI(
    title="Turnos360 API",
    version="0.1.0",
    description="SaaS multiempresa de gestión de turnos · CRM · WhatsApp · Finanzas · Fidelización",
)

# Routers
app.include_router(auth.router)
app.include_router(clientes.router)
app.include_router(recursos.router)
app.include_router(agenda.horarios_router)
app.include_router(agenda.excepciones_router)
app.include_router(turnos.router)
app.include_router(servicios.router)

@app.get("/", tags=["meta"])
def root() -> dict:
    return {
        "producto": "Turnos360",
        "version": app.version,
        "env": settings.env,
        "docs": "/docs",
    }


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}