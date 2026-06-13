"""Turnos360 — API principal.

Punto de entrada de FastAPI. En E2 se montan acá los routers
(auth, clientes, recursos, servicios, turnos) y la dependencia
get_current_empresa() que inyecta empresa_id en toda query.
"""

from fastapi import FastAPI

from app.core.config import settings

app = FastAPI(
    title="Turnos360 API",
    version="0.1.0",
    description="SaaS multiempresa de gestión de turnos · CRM · WhatsApp · Finanzas · Fidelización",
)


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