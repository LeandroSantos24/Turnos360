"""Actividad de campañas: envíos reales de los últimos 30 días y alcance."""

import datetime as dt

from app.models.enums import CanalMensaje, EstadoMensaje
from app.models.mensajeria import Mensaje
from tests.conftest import token_de


# ── Actividad de campañas ─────────────────────────────────────────────

def test_actividad_cuenta_envios_reales_y_no_las_pruebas(client, db, armar_empresa):
    ctx = armar_empresa()
    otra = armar_empresa("Otro negocio")
    ahora = dt.datetime.now(dt.timezone.utc)

    def msj(emp_id, contenido, estado=EstadoMensaje.ENVIADO, hace=0):
        db.add(Mensaje(
            empresa_id=emp_id, canal=CanalMensaje.EMAIL, contenido=contenido,
            estado=estado, fecha=ahora - dt.timedelta(days=hace),
        ))

    msj(ctx.empresa.id, "recordatorio_24h turno=1")
    msj(ctx.empresa.id, "recordatorio_24h turno=2")
    msj(ctx.empresa.id, "recordatorio_24h turno=3", EstadoMensaje.FALLIDO)
    msj(ctx.empresa.id, "recordatorio_24h turno=4", hace=45)   # fuera de los 30 días
    msj(ctx.empresa.id, "prueba_campana tipo=recordatorio_24h")  # prueba: no cuenta
    msj(ctx.empresa.id, "inactivo cliente=9")
    msj(otra.empresa.id, "recordatorio_24h turno=5")            # otro negocio
    ctx.cliente.email = "cli@example.com"
    ctx.cliente.acepta_marketing = True
    ctx.cliente.fecha_nacimiento = dt.date(1990, 5, 4)
    db.commit()

    r = client.get("/empresa/automatizaciones/actividad", headers=token_de(ctx.dueno))
    assert r.status_code == 200
    d = r.json()
    assert d["dias"] == 30
    assert d["campanas"]["recordatorio_24h"]["enviados"] == 2
    assert d["campanas"]["recordatorio_24h"]["fallidos"] == 1
    assert d["campanas"]["recordatorio_24h"]["ultimo"]
    assert d["campanas"]["inactivos"]["enviados"] == 1
    assert d["campanas"]["cumple"] == {"enviados": 0, "fallidos": 0, "ultimo": None}
    assert d["alcance"] == {"clientes": 1, "con_email": 1, "aceptan_promos": 1, "con_cumple": 1}


def test_actividad_es_solo_del_dueno(client, armar_empresa):
    ctx = armar_empresa()
    r = client.get("/empresa/automatizaciones/actividad", headers=token_de(ctx.profesional))
    assert r.status_code == 403
