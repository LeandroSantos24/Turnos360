"""Regresión de la auditoría de seguridad previa al deploy (julio 2026).

Cada bloque acá abajo corresponde a un agujero que ESTUVO abierto y se cerró.
Los tests son la garantía de que no vuelvan: si alguien saca un gate de rol o
mueve una validación de lugar, la suite se pone en rojo antes del deploy.

Se prueba el comportamiento por la API, no la implementación: si mañana el
candado se resuelve de otra forma, estos tests siguen valiendo.
"""

import datetime as dt
import time

import pytest
from sqlalchemy import select

from app.core.seguridad import crear_token_superadmin
from app.models import Turno
from app.models.cupon import CuponDescuento
from tests.conftest import token_de


def _mañana_a_las(hora: int = 10, dias: int = 2) -> dt.datetime:
    """Un horario válido a futuro, en la convención del motor (pared + UTC)."""
    base = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=dias)
    return base.replace(hour=hora, minute=0, second=0, microsecond=0)


# ══════════════════════════════════════════════════════════════════════
# 1. El token del super-admin NO entra al panel de un negocio
# ══════════════════════════════════════════════════════════════════════

def test_token_superadmin_no_sirve_en_el_panel(client, armar_empresa):
    """Los dos tokens llevan un id en 'sub'. Sin el claim de ámbito, el token
    del super-admin con sub=7 entraba como el Usuario 7 de un negocio: acceso
    al panel de un cliente sin dejar rastro."""
    ctx = armar_empresa()
    token = crear_token_superadmin(ctx.dueno.id)
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_token_de_empresa_no_sirve_en_el_panel_de_admin(client, armar_empresa):
    """El camino inverso, por simetría."""
    ctx = armar_empresa()
    r = client.get("/admin/empresas", headers=token_de(ctx.dueno))
    assert r.status_code == 401


def test_el_dueno_si_entra_con_su_token(client, armar_empresa):
    """Control positivo: el arreglo no rompió el login normal."""
    ctx = armar_empresa()
    r = client.get("/auth/me", headers=token_de(ctx.dueno))
    assert r.status_code == 200
    assert r.json()["email"] == ctx.dueno.email


# ══════════════════════════════════════════════════════════════════════
# 2. El profesional no ve la plata del negocio
# ══════════════════════════════════════════════════════════════════════

RUTAS_DE_PLATA = [
    "/movimientos",
    "/cajas",
    "/caja/actual",
    "/metodos-pago",
    "/categorias-financieras",
]


@pytest.mark.parametrize("ruta", RUTAS_DE_PLATA)
def test_profesional_no_lee_finanzas(client, armar_empresa, ruta):
    """El manual promete que el profesional "no ve la facturación del negocio".
    Antes eso lo cumplía solo el menú del panel: la API contestaba 200."""
    ctx = armar_empresa()
    r = client.get(ruta, headers=token_de(ctx.profesional))
    assert r.status_code == 403, f"{ruta} respondió {r.status_code}"


def test_profesional_no_ve_cuanto_gasto_un_cliente(client, armar_empresa):
    ctx = armar_empresa()
    r = client.get(
        f"/clientes/{ctx.cliente.id}/cobrado", headers=token_de(ctx.profesional)
    )
    assert r.status_code == 403


@pytest.mark.parametrize("ruta", RUTAS_DE_PLATA)
def test_el_dueno_si_lee_finanzas(client, armar_empresa, ruta):
    """Control positivo: cerrar la puerta al profesional no cerró la del dueño."""
    ctx = armar_empresa()
    r = client.get(ruta, headers=token_de(ctx.dueno))
    assert r.status_code == 200, f"{ruta} respondió {r.status_code}"


# ══════════════════════════════════════════════════════════════════════
# 3. La historia clínica tiene control de rol
# ══════════════════════════════════════════════════════════════════════

def test_recepcion_no_escribe_la_ficha_clinica(client, db, armar_empresa):
    """Dato sensible (Ley 25.326). Recepción administra turnos y cobros, no
    antecedentes médicos. Antes el módulo entero no tenía ningún gate."""
    from app.models.enums import RolUsuario
    from app.models import Usuario
    from app.core.crypto import hash_clave

    ctx = armar_empresa()
    recepcion = Usuario(
        empresa_id=ctx.empresa.id,
        nombre="Recepción Test",
        email=f"recep-{ctx.empresa.id}@example.com",
        hash_clave=hash_clave("clave1234"),
        rol=RolUsuario.RECEPCION,
    )
    db.add(recepcion)
    db.flush()

    r = client.put(
        f"/pacientes/{ctx.cliente.id}/ficha",
        json={"antecedentes": "no deberia poder"},
        headers=token_de(recepcion),
    )
    assert r.status_code == 403


def test_el_profesional_si_ve_la_ficha_de_su_paciente(client, armar_empresa):
    """Control positivo: el que atiende necesita la ficha (nutrición, kinesio)."""
    ctx = armar_empresa()
    r = client.put(
        f"/pacientes/{ctx.cliente.id}/ficha",
        json={"antecedentes": "control anual"},
        headers=token_de(ctx.profesional),
    )
    assert r.status_code in (200, 201)


# ══════════════════════════════════════════════════════════════════════
# 4. Un cupón inválido no deja turnos fantasma
# ══════════════════════════════════════════════════════════════════════

def test_cupon_invalido_no_crea_el_turno(client, db, armar_empresa):
    """turno_svc.crear() hace commit. Validar el cupón después dejaba el turno
    guardado aunque el cliente recibiera un 400 y creyera que no reservó."""
    ctx = armar_empresa()
    r = client.post(
        f"/publico/{ctx.empresa.slug}/reservar",
        json={
            "servicio_id": ctx.servicio.id,
            "inicio": _mañana_a_las().isoformat(),
            "cliente": {
                "nombre": "Cliente Fantasma",
                "telefono": "2610000000",
                "email": "fantasma@example.com",
            },
            "cupon_codigo": "NOEXISTE99",
        },
    )
    assert r.status_code == 400
    turnos = db.scalars(
        select(Turno).where(Turno.empresa_id == ctx.empresa.id)
    ).all()
    assert len(turnos) == 0, "el cupón inválido dejó un turno en la agenda"


def test_cupon_valido_si_reserva_y_descuenta(client, db, armar_empresa):
    """Control positivo: mover la validación de lugar no rompió el descuento."""
    ctx = armar_empresa()
    cupon = CuponDescuento(
        empresa_id=ctx.empresa.id,
        codigo="PROMO10",
        tipo="porcentaje",
        valor=10,
        activo=True,
    )
    db.add(cupon)
    db.flush()

    r = client.post(
        f"/publico/{ctx.empresa.slug}/reservar",
        json={
            "servicio_id": ctx.servicio.id,
            "inicio": _mañana_a_las(hora=11).isoformat(),
            "cliente": {
                "nombre": "Cliente Con Cupon",
                "telefono": "2610000001",
                "email": "cupon@example.com",
            },
            "cupon_codigo": "PROMO10",
        },
    )
    assert r.status_code == 200
    turno = db.scalar(select(Turno).where(Turno.empresa_id == ctx.empresa.id))
    assert turno is not None
    assert float(turno.descuento_pct or 0) > 0


# ══════════════════════════════════════════════════════════════════════
# 5. La reserva pública vive en una ventana razonable de tiempo
# ══════════════════════════════════════════════════════════════════════

def _reservar(client, ctx, inicio, tel="2619999999"):
    return client.post(
        f"/publico/{ctx.empresa.slug}/reservar",
        json={
            "servicio_id": ctx.servicio.id,
            "inicio": inicio.isoformat() if hasattr(inicio, "isoformat") else inicio,
            "cliente": {"nombre": "Test", "telefono": tel, "email": "t@ex.com"},
        },
    )


def test_no_se_reserva_en_el_pasado(client, db, armar_empresa):
    """El motor solo mira horarios y solapamientos: nunca compara contra "ahora".
    Sin este control entraban turnos retroactivos que ensucian caja y stats."""
    ctx = armar_empresa()
    hace_40_dias = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=40)
    r = _reservar(client, ctx, hace_40_dias.replace(hour=10, minute=0, second=0, microsecond=0))
    assert r.status_code == 400
    assert db.scalar(select(Turno).where(Turno.empresa_id == ctx.empresa.id)) is None


def test_no_se_reserva_en_el_ano_2099(client, db, armar_empresa):
    ctx = armar_empresa()
    r = _reservar(client, ctx, dt.datetime(2099, 6, 15, 10, 0, tzinfo=dt.timezone.utc))
    assert r.status_code == 400
    assert db.scalar(select(Turno).where(Turno.empresa_id == ctx.empresa.id)) is None


def test_una_fecha_sin_zona_horaria_no_rompe_el_endpoint(client, armar_empresa):
    """El schema aceptaba datetimes sin zona y el motor asumía que la tenían:
    el primer '<' reventaba con TypeError y el endpoint público daba 500."""
    ctx = armar_empresa()
    naive = (dt.datetime.now() + dt.timedelta(days=3)).replace(
        hour=11, minute=0, second=0, microsecond=0
    )
    r = _reservar(client, ctx, naive.isoformat(), tel="2618888888")
    assert r.status_code == 200


# ══════════════════════════════════════════════════════════════════════
# 6. El login no delata qué emails están registrados
# ══════════════════════════════════════════════════════════════════════

def test_el_login_tarda_lo_mismo_exista_o_no_el_email(client, armar_empresa):
    """El señuelo tenía 1 iteración de PBKDF2 contra las 390.000 de un hash
    real: 3 ms vs 240 ms. Con esa diferencia se enumera la lista de clientes
    con un script de diez líneas."""
    ctx = armar_empresa()

    def mediana(email: str) -> float:
        muestras = []
        for _ in range(5):
            t0 = time.perf_counter()
            client.post("/auth/login", json={"email": email, "clave": "malamala"})
            muestras.append(time.perf_counter() - t0)
        return sorted(muestras)[len(muestras) // 2]

    existe = mediana(ctx.dueno.email)
    no_existe = mediana("noexisteseguro@example.com")
    ratio = max(existe, no_existe) / max(min(existe, no_existe), 1e-9)
    assert ratio < 2.0, (
        f"el tiempo distingue emails registrados: {existe*1000:.0f} ms vs "
        f"{no_existe*1000:.0f} ms (ratio {ratio:.1f}x)"
    )


# ══════════════════════════════════════════════════════════════════════
# 7. Cambiar la contraseña corta las sesiones abiertas
# ══════════════════════════════════════════════════════════════════════

def test_cambiar_la_clave_invalida_los_tokens_viejos(client, db, armar_empresa):
    """Sin revocación, un token robado sobrevivía al cambio de contraseña. Y el
    refresh dura 7 días y se renueva solo: el atacante se quedaba adentro."""
    ctx = armar_empresa()
    headers_viejos = token_de(ctx.dueno)

    assert client.get("/auth/me", headers=headers_viejos).status_code == 200

    r = client.post(
        "/auth/cambiar-password",
        json={"clave_actual": ctx.clave, "clave_nueva": "claveNueva123"},
        headers=headers_viejos,
    )
    assert r.status_code == 200

    # El token de antes del cambio ya no vale.
    assert client.get("/auth/me", headers=headers_viejos).status_code == 401


def test_el_refresh_viejo_no_renueva_despues_del_cambio(client, db, armar_empresa):
    """El punto que más importa: el refresh es el que dura una semana."""
    from tests.conftest import refresh_de

    ctx = armar_empresa()
    refresh_viejo = refresh_de(ctx.dueno)
    headers = token_de(ctx.dueno)

    client.post(
        "/auth/cambiar-password",
        json={"clave_actual": ctx.clave, "clave_nueva": "claveNueva123"},
        headers=headers,
    )

    r = client.post("/auth/refresh", json={"refresh_token": refresh_viejo})
    assert r.status_code == 401


def test_restablecer_por_email_tambien_corta_las_sesiones(client, db, armar_empresa):
    """Es el flujo que usa alguien que sospecha que le entraron a la cuenta:
    tiene que echar al intruso, no solo cambiar la clave."""
    import hashlib
    import secrets as _secrets

    ctx = armar_empresa()
    headers_viejos = token_de(ctx.dueno)

    token = _secrets.token_urlsafe(32)
    ctx.dueno.reset_token_hash = hashlib.sha256(token.encode()).hexdigest()
    ctx.dueno.reset_token_expira = dt.datetime.now(dt.timezone.utc) + dt.timedelta(
        minutes=60
    )
    db.flush()

    r = client.post(
        "/auth/restablecer-password",
        json={"token": token, "clave_nueva": "otraClave456"},
    )
    assert r.status_code == 200
    assert client.get("/auth/me", headers=headers_viejos).status_code == 401


# ══════════════════════════════════════════════════════════════════════
# 8. El endpoint público de horarios no se puede pedir sin techo
# ══════════════════════════════════════════════════════════════════════

def test_el_tope_de_dias_de_horarios_esta_acotado(client, armar_empresa):
    """Cada día recorre a todos los profesionales del servicio. Con 60 días eso
    eran cientos de consultas SQL por request, sin login y sin rate limit."""
    ctx = armar_empresa()
    r = client.get(
        f"/publico/{ctx.empresa.slug}/horarios",
        params={"servicio_id": ctx.servicio.id, "dias": 60},
    )
    assert r.status_code == 422, "60 días debería rechazarse por validación"

    ok = client.get(
        f"/publico/{ctx.empresa.slug}/horarios",
        params={"servicio_id": ctx.servicio.id, "dias": 31},
    )
    assert ok.status_code == 200


def test_horarios_tiene_rate_limit_declarado():
    """El rate limit se apaga en los tests (conftest), así que se verifica la
    CONFIGURACIÓN, igual que en test_rate_limit_config.py."""
    from app.routers import publico

    marcas = getattr(publico.horarios, "_rate_limit_marker", None)
    tiene = marcas is not None or hasattr(publico.horarios, "__wrapped__")
    assert tiene, "el endpoint público de horarios quedó sin rate limit"
