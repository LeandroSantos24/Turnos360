"""Regresión de los hallazgos de la auditoría pre-deploy del 2026-09-27."""

import datetime as dt
import io

import pytest
from PIL import Image
from sqlalchemy import select

from app.core.config import Settings
from app.models import VisitaVidriera
from tests.conftest import token_de


def _inicio(dias=3, hora=15):
    return dt.datetime.combine(dt.date.today() + dt.timedelta(days=dias), dt.time(hora, 0))


# ── Reabrir un turno cancelado no puede crear la silla doble ─────────────

def test_reabrir_cancelado_sobre_hueco_vendido_es_409(client, armar_empresa):
    ctx = armar_empresa()
    h = token_de(ctx.dueno)
    ini = _inicio().isoformat() + "Z"
    base = {"recurso_id": ctx.lucas.id, "servicio_id": ctx.servicio.id, "fecha_inicio": ini}

    t1 = client.post("/turnos", headers=h, json={**base, "cliente_id": ctx.cliente.id}).json()
    assert client.patch(f"/turnos/{t1['id']}/estado", headers=h,
                        json={"estado": "cancelado"}).status_code == 200
    # el hueco se vendió de nuevo
    assert client.post("/turnos", headers=h,
                       json={**base, "cliente_id": ctx.cliente.id}).status_code == 201

    r = client.patch(f"/turnos/{t1['id']}/estado", headers=h, json={"estado": "confirmado"})
    assert r.status_code == 409, r.text


def test_reabrir_cancelado_con_hueco_libre_sigue_andando(client, armar_empresa):
    ctx = armar_empresa()
    h = token_de(ctx.dueno)
    t = client.post("/turnos", headers=h, json={
        "cliente_id": ctx.cliente.id, "recurso_id": ctx.lucas.id,
        "servicio_id": ctx.servicio.id, "fecha_inicio": _inicio().isoformat() + "Z"}).json()
    client.patch(f"/turnos/{t['id']}/estado", headers=h, json={"estado": "cancelado"})
    r = client.patch(f"/turnos/{t['id']}/estado", headers=h, json={"estado": "confirmado"})
    assert r.status_code == 200, r.text


# ── Validación de entrada del panel ──────────────────────────────────────

def test_turno_con_fecha_sin_zona_no_es_500(client, armar_empresa):
    ctx = armar_empresa()
    r = client.post("/turnos", headers=token_de(ctx.dueno), json={
        "cliente_id": ctx.cliente.id, "recurso_id": ctx.lucas.id,
        "servicio_id": ctx.servicio.id, "fecha_inicio": _inicio(hora=11).isoformat()})
    assert r.status_code == 201, r.text
    assert r.json()["fecha_inicio"].startswith(_inicio(hora=11).isoformat()[:16])


def test_importe_previsto_negativo_se_rechaza(client, armar_empresa):
    ctx = armar_empresa()
    r = client.post("/turnos", headers=token_de(ctx.dueno), json={
        "cliente_id": ctx.cliente.id, "recurso_id": ctx.lucas.id,
        "servicio_id": ctx.servicio.id, "fecha_inicio": _inicio().isoformat() + "Z",
        "importe_previsto": -5000})
    assert r.status_code == 422


# ── Referencias por body a otra empresa ──────────────────────────────────

def test_historia_clinica_no_acepta_turno_ni_entrada_ajenos(client, armar_empresa):
    a, b = armar_empresa("A"), armar_empresa("B")
    hb = token_de(b.dueno)
    tb = client.post("/turnos", headers=hb, json={
        "cliente_id": b.cliente.id, "recurso_id": b.lucas.id,
        "servicio_id": b.servicio.id, "fecha_inicio": _inicio().isoformat() + "Z"}).json()
    eb = client.post(f"/pacientes/{b.cliente.id}/entradas", headers=hb,
                     json={"fecha": str(dt.date.today())}).json()

    ha = token_de(a.dueno)
    url = f"/pacientes/{a.cliente.id}"
    hoy = str(dt.date.today())
    assert client.post(f"{url}/entradas", headers=ha,
                       json={"fecha": hoy, "turno_id": tb["id"]}).status_code == 404
    assert client.post(f"{url}/mediciones", headers=ha,
                       json={"fecha": hoy, "entrada_id": eb["id"]}).status_code == 404
    assert client.post(f"{url}/adjuntos", headers=ha, json={
        "nombre_archivo": "x", "ruta": "https://ejemplo.com/x",
        "entrada_clinica_id": eb["id"]}).status_code == 404
    # y con lo propio sigue andando
    assert client.post(f"{url}/entradas", headers=ha, json={"fecha": hoy}).status_code == 201


def test_planes_y_cupones_descartan_servicios_ajenos(client, armar_empresa):
    a, b = armar_empresa("A"), armar_empresa("B")
    h = token_de(a.dueno)
    plan = client.post("/planes-abono", headers=h, json={
        "nombre": "x", "precio": 1,
        "servicios_cubiertos": [a.servicio.id, b.servicio.id]}).json()
    assert plan["servicios_cubiertos"] == [a.servicio.id]

    cup = client.post("/cupones", headers=h, json={
        "codigo": "AUD27", "tipo": "monto", "valor": 1,
        "servicios_ids": [b.servicio.id, a.servicio.id]}).json()
    assert cup["servicios_ids"] == [a.servicio.id]


# ── Subida de imágenes: bomba de descompresión ───────────────────────────

def test_imagen_con_demasiados_pixeles_es_400_no_500(client, db, armar_empresa, tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "uploads_dir", str(tmp_path))
    ctx = armar_empresa()
    db.commit()
    buf = io.BytesIO()
    Image.new("1", (9000, 9000)).save(buf, "PNG")  # 81 M píxeles, pocos KB
    assert len(buf.getvalue()) < 2_000_000
    r = client.post("/subidas/imagen", headers=token_de(ctx.dueno),
                    files={"archivo": ("bomba.png", buf.getvalue(), "image/png")})
    assert r.status_code == 400, r.text


# ── CORS ─────────────────────────────────────────────────────────────────

_PROD = dict(env="prod", secret_key="s" * 40, fernet_key="f" * 40)


def test_produccion_no_levanta_con_cors_comodin():
    with pytest.raises(ValueError, match="CORS_ORIGINS"):
        Settings(_env_file=None, cors_origins="*", **_PROD)
    with pytest.raises(ValueError, match="CORS_ORIGINS"):
        Settings(_env_file=None, cors_origins="", **_PROD)
    assert Settings(_env_file=None, cors_origins="https://turnos360.com.ar", **_PROD)


def test_cors_no_refleja_origen_ajeno_ni_manda_credenciales(client):
    r = client.options("/auth/me", headers={
        "Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") is None
    r = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert r.headers.get("access-control-allow-credentials") is None


# ── El pedido del servidor de Next (SEO) no cuenta como visita ───────────

def test_pedido_ssr_de_la_vidriera_no_cuenta_visita(client, db, armar_empresa):
    ctx = armar_empresa()
    ctx.dueno.email_verificado = True
    db.flush()
    r = client.get(f"/publico/{ctx.empresa.slug}", headers={"x-turnos360-ssr": "1"})
    assert r.status_code == 200, r.text
    assert db.scalar(select(VisitaVidriera).where(
        VisitaVidriera.empresa_id == ctx.empresa.id)) is None


def test_slugs_de_rutas_del_panel_estan_reservados():
    """Toda carpeta de página del frontend tiene que estar reservada como slug:
    si no, la vidriera de ese negocio queda tapada por la ruta del panel."""
    from pathlib import Path

    from app.schemas.admin import SLUGS_RESERVADOS

    app_dir = Path(__file__).resolve().parents[2] / "frontend" / "src" / "app"
    if not app_dir.exists():
        pytest.skip("sin el frontend al lado")
    rutas = set()
    for d in app_dir.iterdir():
        if not d.is_dir():
            continue
        if d.name.startswith("("):
            rutas |= {x.name for x in d.iterdir() if x.is_dir() and not x.name.startswith("[")}
        elif d.name not in ("fonts",):
            rutas.add(d.name)
    faltan = sorted(rutas - SLUGS_RESERVADOS)
    assert not faltan, f"rutas sin reservar como slug: {faltan}"


def test_sitemap_no_lista_vidrieras_sin_verificar(client, db, armar_empresa):
    ctx = armar_empresa()
    ctx.empresa.de_registro_publico = True
    ctx.dueno.email_verificado = False
    db.flush()
    assert ctx.empresa.slug not in client.get("/publico/slugs").json()
    ctx.dueno.email_verificado = True
    db.flush()
    assert ctx.empresa.slug in client.get("/publico/slugs").json()
