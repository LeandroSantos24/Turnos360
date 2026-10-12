"""Historia de suscripciones (fotos diarias) y ajustes administrativos."""

import datetime as dt
import uuid

import pytest

from app.core.crypto import hash_clave
from app.core.reloj import hoy_de_pared
from app.core.seguridad import crear_token_superadmin
from app.models import AjusteSuscripcion, AuditoriaAdmin, Empresa, SuperAdmin, SuscripcionDiaria
from app.services import historial_suscripciones as hist

HOY = hoy_de_pared()


@pytest.fixture()
def admin(db) -> dict:
    sa = SuperAdmin(nombre="Admin Test", email=f"sa-{uuid.uuid4().hex}@turnos360.test", hash_clave=hash_clave("clave1234"))
    db.add(sa)
    db.flush()
    return {"Authorization": f"Bearer {crear_token_superadmin(sa.id)}"}


def _empresa(armar_empresa, db, vence_hace=3):
    ctx = armar_empresa()
    ctx.empresa.plan = "pro"
    ctx.empresa.suscripcion_vence = HOY - dt.timedelta(days=vence_hace)
    ctx.empresa.creada_en = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=30)
    db.commit()
    return ctx


def _filas(db, empresa_id):
    return {
        f.fecha: (f.estado, f.origen)
        for f in db.query(SuscripcionDiaria).filter_by(empresa_id=empresa_id).order_by(SuscripcionDiaria.fecha)
    }


def _sin_fotos_previas(db):
    # La base de desarrollo puede tener fotos de otras corridas: los tests
    # parten de cero dentro de su transacción.
    db.query(SuscripcionDiaria).delete()
    db.commit()


# ── Fotos diarias ─────────────────────────────────────────────────────────

def test_la_foto_es_idempotente(db, armar_empresa):
    _sin_fotos_previas(db)
    ctx = _empresa(armar_empresa, db, vence_hace=-10)
    r1 = hist.tomar_fotos(db, HOY)
    antes = db.query(SuscripcionDiaria).count()
    r2 = hist.tomar_fotos(db, HOY)
    assert r1["fotos"] >= 1 and r2["fotos"] == 0
    assert db.query(SuscripcionDiaria).count() == antes
    assert _filas(db, ctx.empresa.id) == {HOY: ("activa", "foto")}


def test_completa_los_dias_que_faltan_y_anota_lo_que_paso_solo(db, armar_empresa):
    _sin_fotos_previas(db)
    ctx = _empresa(armar_empresa, db, vence_hace=3)
    hist.tomar_fotos(db, HOY - dt.timedelta(days=5))  # primera foto
    r = hist.tomar_fotos(db, HOY)  # 4 días sin correr
    filas = _filas(db, ctx.empresa.id)
    assert filas[HOY - dt.timedelta(days=5)] == ("activa", "foto")
    assert filas[HOY - dt.timedelta(days=3)] == ("activa", "reconstruido")
    assert filas[HOY - dt.timedelta(days=2)] == ("prorroga", "reconstruido")
    assert filas[HOY] == ("prorroga", "foto")
    assert len(filas) == 6 and r["reconstruidas"] >= 4
    ev = db.query(AjusteSuscripcion).filter_by(empresa_id=ctx.empresa.id, tipo="estado").all()
    assert len(ev) == 1
    assert (ev[0].estado_antes, ev[0].estado_despues, ev[0].actor_tipo) == ("activa", "prorroga", "sistema")
    # Correr de nuevo no duplica ni el evento.
    hist.tomar_fotos(db, HOY)
    assert db.query(AjusteSuscripcion).filter_by(empresa_id=ctx.empresa.id, tipo="estado").count() == 1


def test_la_reconstruccion_deshace_los_ajustes_posteriores(client, db, armar_empresa, admin):
    _sin_fotos_previas(db)
    ctx = _empresa(armar_empresa, db, vence_hace=3)
    hist.tomar_fotos(db, HOY - dt.timedelta(days=5))
    # Hoy se le da una prórroga: el vencimiento queda en el futuro.
    r = client.post(
        f"/admin/empresas/{ctx.empresa.id}/prorroga", headers=admin,
        json={"dias": 10, "motivo": "Corte de luz en el local", "categoria": "incidencia"},
    )
    assert r.status_code == 200, r.text
    hist.tomar_fotos(db, HOY)
    filas = _filas(db, ctx.empresa.id)
    # Ayer todavía estaba en gracia (con el vencimiento de ANTES de la prórroga)…
    assert filas[HOY - dt.timedelta(days=1)] == ("prorroga", "reconstruido")
    # …y hoy, con la prórroga, está activa.
    assert filas[HOY] == ("activa", "foto")


def test_no_se_inventa_historia_antes_de_la_primera_foto(db, armar_empresa):
    _sin_fotos_previas(db)
    ctx = _empresa(armar_empresa, db)
    hist.tomar_fotos(db, HOY)
    assert min(_filas(db, ctx.empresa.id)) == HOY
    assert hist.primera_foto(db) == HOY


def test_metricas_de_transiciones():
    d = lambda n: HOY - dt.timedelta(days=n)  # noqa: E731
    filas = [
        # empresa 1: prueba → activa (nueva) → vencida
        (d(6), 1, "prueba", "foto"), (d(5), 1, "activa", "foto"), (d(2), 1, "vencida", "foto"),
        # empresa 2: activa → cancelada
        (d(6), 2, "activa", "foto"), (d(3), 2, "cancelada", "foto"),
        # empresa 3: activa → vencida → activa (reactivada)
        (d(6), 3, "activa", "foto"), (d(4), 3, "vencida", "foto"), (d(1), 3, "activa", "foto"),
        # empresa 4: aparece después de la primera foto ya activa (alta)
        (d(1), 4, "activa", "foto"),
    ]
    filas.sort(key=lambda f: (f[1], f[0]))
    m = hist._metricas(filas, d(5), HOY, [(d(1), "inicial", "pro")], d(6))
    assert m == {"nuevas": 2, "reactivadas": 1, "vencimientos": 2, "cancelaciones": 1, "pruebas_vencidas": 0, "cambios_de_plan": 1}


def test_evolucion_endpoint(client, db, armar_empresa, admin):
    _sin_fotos_previas(db)
    _empresa(armar_empresa, db, vence_hace=-10)
    r = client.get("/admin/suscripciones/evolucion?granularidad=dia", headers=admin)
    assert r.status_code == 200
    assert r.json()["confiable_desde"] is None  # todavía no hay fotos
    assert client.post("/admin/suscripciones/foto", headers=admin).status_code == 200
    d = client.get("/admin/suscripciones/evolucion?granularidad=semana", headers=admin).json()
    assert d["confiable_desde"] == HOY.isoformat()
    assert d["serie"][-1]["activas_al_cierre"] >= 1
    assert {"activas_al_cierre", "nuevas", "vencimientos", "cancelaciones"} <= set(d["variacion"])
    assert "confiable_desde" in d["definiciones"]
    assert client.get("/admin/suscripciones/evolucion?granularidad=anio", headers=admin).status_code == 400


def test_evolucion_solo_super_admin(client, db, armar_empresa):
    from .conftest import token_de

    ctx = armar_empresa()
    assert client.get("/admin/suscripciones/evolucion", headers=token_de(ctx.dueno)).status_code == 401


# ── Ajustes administrativos ───────────────────────────────────────────────

def test_motivo_obligatorio_en_los_ajustes(client, db, armar_empresa, admin):
    ctx = _empresa(armar_empresa, db)
    base = f"/admin/empresas/{ctx.empresa.id}"
    assert client.post(f"{base}/prorroga", headers=admin, json={"dias": 5}).status_code == 422
    assert client.patch(f"{base}/suscripcion", headers=admin, json={"renovar_30": True, "motivo": "Promo de lanzamiento"}).status_code == 422
    assert client.patch(f"{base}/suscripcion", headers=admin, json={"plan": "inicial"}).status_code == 422
    assert client.post(f"{base}/prorroga", headers=admin, json={"dias": 5, "motivo": "ok", "categoria": "cortesia"}).status_code == 422
    assert db.query(AjusteSuscripcion).filter_by(empresa_id=ctx.empresa.id).count() == 0


def test_ajustes_clasificados_auditados_y_revertibles(client, db, armar_empresa, admin):
    ctx = _empresa(armar_empresa, db, vence_hace=-5)
    base = f"/admin/empresas/{ctx.empresa.id}"
    vence_antes = ctx.empresa.suscripcion_vence
    r = client.post(f"{base}/prorroga", headers=admin, json={"dias": 7, "motivo": "Caída del sistema el lunes", "categoria": "incidencia"})
    assert r.status_code == 200
    r = client.patch(f"{base}/suscripcion", headers=admin, json={"plan": "inicial", "motivo": "Pidió bajar de plan"})
    assert r.status_code == 200, r.text
    lista = client.get(f"/admin/ajustes?empresa_id={ctx.empresa.id}", headers=admin).json()["filas"]
    pr = next(a for a in lista if a["tipo"] == "prorroga")
    assert (pr["categoria"], pr["motivo"], pr["dias"], pr["estado"]) == ("incidencia", "Caída del sistema el lunes", 7, "vigente")
    assert pr["vence_antes"] == vence_antes.isoformat()
    pl = next(a for a in lista if a["tipo"] == "plan")
    assert pl["categoria"] == "plan" and pl["motivo"] == "Pidió bajar de plan"
    assert db.query(AuditoriaAdmin).filter(
        AuditoriaAdmin.empresa_id == ctx.empresa.id, AuditoriaAdmin.descripcion.contains("Caída del sistema")
    ).count() == 1

    rv = client.post(f"{base}/ajustes/{pr['id']}/revertir", headers=admin, json={"motivo": "Se cargó dos veces"})
    assert rv.status_code == 200
    lista = client.get(f"/admin/ajustes?empresa_id={ctx.empresa.id}", headers=admin).json()["filas"]
    assert next(a for a in lista if a["id"] == pr["id"])["estado"] == "revertido"
    rev = next(a for a in lista if a["tipo"] == "reversion")
    assert rev["categoria"] == "correccion" and rev["motivo"] == "Se cargó dos veces"
    # Filtros.
    assert all(a["categoria"] == "incidencia" for a in client.get("/admin/ajustes?categoria=incidencia", headers=admin).json()["filas"])
    assert client.get("/admin/ajustes?categoria=inventada", headers=admin).status_code == 400
    manana = (HOY + dt.timedelta(days=1)).isoformat()
    assert client.get(f"/admin/ajustes?empresa_id={ctx.empresa.id}&desde={manana}", headers=admin).json()["total"] == 0


def test_los_dias_regalados_no_tocan_la_caja_y_van_aparte(client, db, armar_empresa, admin):
    ctx = _empresa(armar_empresa, db, vence_hace=-5)
    q = f"desde={HOY.isoformat()}&hasta={HOY.isoformat()}"
    caja_antes = client.get(f"/admin/caja?{q}", headers=admin).json()
    est_antes = client.get(f"/admin/estadisticas?granularidad=mes&{q}", headers=admin).json()
    client.post(f"/admin/empresas/{ctx.empresa.id}/prorroga", headers=admin, json={"dias": 10, "motivo": "Cliente nuevo, cortesía", "categoria": "cortesia"})
    client.patch(f"/admin/empresas/{ctx.empresa.id}/suscripcion", headers=admin, json={"renovar_30": True, "motivo": "Error al cargar", "categoria": "correccion"})
    caja = client.get(f"/admin/caja?{q}", headers=admin).json()
    est = client.get(f"/admin/estadisticas?granularidad=mes&{q}", headers=admin).json()
    assert caja["totales"] == caja_antes["totales"] and caja["saldo_final"] == caja_antes["saldo_final"]
    assert est["total"] == est_antes["total"]
    b = est["beneficios"]["total"]
    assert b["dias_cortesia"] - est_antes["beneficios"]["total"]["dias_cortesia"] == 10
    # La corrección no es un beneficio.
    assert b["dias_sin_clasificar"] == est_antes["beneficios"]["total"]["dias_sin_clasificar"]
    assert "No es plata" in est["beneficios"]["nota"]


def test_la_categoria_solo_admite_valores_validos(db, armar_empresa):
    from sqlalchemy.exc import IntegrityError

    ctx = _empresa(armar_empresa, db)
    db.add(AjusteSuscripcion(empresa_id=ctx.empresa.id, tipo="manual", categoria="regalito"))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_ajustes_solo_super_admin(client, db, armar_empresa):
    from .conftest import token_de

    ctx = armar_empresa()
    assert client.get("/admin/ajustes", headers=token_de(ctx.dueno)).status_code == 401
    assert db.get(Empresa, ctx.empresa.id) is not None
