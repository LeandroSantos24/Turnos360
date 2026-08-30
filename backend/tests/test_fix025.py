"""Regresión del fix-025.

Tres cosas que aparecieron probando en vivo:

1. Crear una empresa desde el panel devolvía 500. La fila SÍ se creaba (por eso
   al reintentar decía «ya existe»): lo que se caía era la respuesta, porque la
   fecha de fin de prueba viajaba como `date` y el esquema la espera como texto.
2. La pantalla de horarios dejaba apilar la MISMA franja infinitas veces.
3. Faltaban rubros: sin «uñas» no había forma de cargar un centro de uñas.
"""

import datetime as dt
import uuid

from app.core.crypto import hash_clave
from app.core.seguridad import crear_token_superadmin
from app.models import Rubro, SuperAdmin

from .conftest import token_de


def _cab_superadmin(db) -> dict:
    """Un super-admin real en la base + su token."""
    sa = SuperAdmin(
        nombre="Admin Test",
        email=f"sa-{uuid.uuid4().hex}@turnos360.test",
        hash_clave=hash_clave("clave1234"),
    )
    db.add(sa)
    db.flush()
    return {"Authorization": f"Bearer {crear_token_superadmin(sa.id)}"}


def _rubro(db) -> Rubro:
    r = Rubro(codigo=f"r-{uuid.uuid4().hex[:8]}", nombre="Barbería Test", preset={})
    db.add(r)
    db.flush()
    return r


# ══════════════════════════════════════════════════════════════════════
# 1. Crear empresa ya no tira 500
# ══════════════════════════════════════════════════════════════════════

def test_crear_empresa_no_tira_500_y_devuelve_la_prueba_como_texto(client, db):
    """El caso exacto que rompía: con prueba, la fecha tiene que volver como
    texto y el estado tiene que decir «prueba», sin caerse al serializar."""
    cab = _cab_superadmin(db)
    rubro = _rubro(db)
    db.commit()
    s = uuid.uuid4().hex[:8]

    r = client.post(
        "/admin/empresas",
        headers=cab,
        json={
            "nombre": "Barbería Nueva",
            "slug": f"barberia-nueva-{s}",
            "rubro_id": rubro.id,
            "dueno": {
                "nombre": "Leo",
                "email": f"leo-nueva-{s}@example.com",
                "clave": "clave1234",
            },
            "dias_prueba": 14,
        },
    )
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert isinstance(cuerpo["prueba_hasta"], str), (
        "prueba_hasta tiene que volver como texto; si vuelve como date, "
        "Pydantic se cae y el panel ve un 500 con la empresa ya creada."
    )
    assert cuerpo["estado_suscripcion"] == "prueba"
    assert cuerpo["prueba_hasta"] == str(dt.date.today() + dt.timedelta(days=14))


def test_crear_empresa_sin_prueba_no_se_cae(client, db):
    """dias_prueba=0: prueba_hasta es None y el estado, sin_vencimiento.
    Guarda la rama del None (que también pasa por la serialización)."""
    cab = _cab_superadmin(db)
    rubro = _rubro(db)
    db.commit()
    s = uuid.uuid4().hex[:8]

    r = client.post(
        "/admin/empresas",
        headers=cab,
        json={
            "nombre": "Sin Prueba",
            "slug": f"sin-prueba-{s}",
            "rubro_id": rubro.id,
            "dueno": {
                "nombre": "Leo",
                "email": f"leo-sinprueba-{s}@example.com",
                "clave": "clave1234",
            },
            "dias_prueba": 0,
        },
    )
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["prueba_hasta"] is None
    assert cuerpo["estado_suscripcion"] == "sin_vencimiento"


# ══════════════════════════════════════════════════════════════════════
# 2. No se puede duplicar la misma franja
# ══════════════════════════════════════════════════════════════════════

def test_franja_duplicada_exacta_se_rechaza(client, db, armar_empresa):
    ctx = armar_empresa()
    db.commit()
    cab = token_de(ctx.dueno)
    payload = {"dia_semana": 2, "hora_desde": "09:00", "hora_hasta": "13:00"}

    r1 = client.post(f"/recursos/{ctx.lucas.id}/horarios", headers=cab, json=payload)
    assert r1.status_code == 201, r1.text

    r2 = client.post(f"/recursos/{ctx.lucas.id}/horarios", headers=cab, json=payload)
    assert r2.status_code == 409, (
        "Se dejó cargar la misma franja dos veces. Antes se podía apilar "
        "infinitas veces la misma."
    )
    assert "ya está cargada" in r2.json()["detail"].lower()


def test_dos_franjas_distintas_del_mismo_dia_se_permiten(client, db, armar_empresa):
    """Un turno partido (mañana y tarde) tiene que seguir siendo válido: el
    candado es contra el duplicado EXACTO, no contra dos franjas del mismo día."""
    ctx = armar_empresa()
    db.commit()
    cab = token_de(ctx.dueno)

    r1 = client.post(
        f"/recursos/{ctx.pablo.id}/horarios",
        headers=cab,
        json={"dia_semana": 3, "hora_desde": "09:00", "hora_hasta": "13:00"},
    )
    r2 = client.post(
        f"/recursos/{ctx.pablo.id}/horarios",
        headers=cab,
        json={"dia_semana": 3, "hora_desde": "16:00", "hora_hasta": "20:00"},
    )
    assert r1.status_code == 201, r1.text
    assert r2.status_code == 201, r2.text


def test_misma_franja_con_distinta_vigencia_se_permite(client, db, armar_empresa):
    """La vigencia forma parte de la identidad de la franja: dos tramos con la
    misma hora pero distinta vigencia son válidos; repetir la vigencia, no."""
    ctx = armar_empresa()
    db.commit()
    cab = token_de(ctx.dueno)
    base = {"dia_semana": 4, "hora_desde": "10:00", "hora_hasta": "12:00"}

    r1 = client.post(
        f"/recursos/{ctx.lucas.id}/horarios",
        headers=cab,
        json={**base, "vigencia_desde": "2026-01-01", "vigencia_hasta": "2026-06-30"},
    )
    r2 = client.post(
        f"/recursos/{ctx.lucas.id}/horarios",
        headers=cab,
        json={**base, "vigencia_desde": "2026-07-01", "vigencia_hasta": "2026-12-31"},
    )
    r3 = client.post(
        f"/recursos/{ctx.lucas.id}/horarios",
        headers=cab,
        json={**base, "vigencia_desde": "2026-01-01", "vigencia_hasta": "2026-06-30"},
    )
    assert r1.status_code == 201, r1.text
    assert r2.status_code == 201, r2.text  # distinta vigencia → pasa
    assert r3.status_code == 409, r3.text  # idéntica a r1 → rechazada


# ══════════════════════════════════════════════════════════════════════
# 3. Los rubros nuevos
# ══════════════════════════════════════════════════════════════════════

def test_seed_minimo_incluye_los_rubros_nuevos():
    from app.seeds_minimo import RUBROS

    codigos = {c for c, _n, _p in RUBROS}
    assert {"unas", "estetica", "spa"} <= codigos, (
        "Faltan rubros nuevos. Sin «unas» no se puede cargar un centro de uñas."
    )
    for _codigo, nombre, preset in RUBROS:
        assert isinstance(nombre, str) and nombre
        assert "terminologia" in preset and "recurso" in preset["terminologia"]
