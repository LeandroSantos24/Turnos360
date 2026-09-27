"""Barrido automático de aislamiento entre empresas (auditoría 2026-09-27).

No confía en la lista de endpoints de nadie: recorre TODAS las rutas
autenticadas de la app y, en cada una con un id en la ruta, prueba el id de
OTRA empresa con el token del dueño de A. Después compara una foto de todas
las filas de B antes y después: si algún endpoint escribió en B, falla.

Además prueba las referencias por BODY (cliente_id, plan_id, metodo_pago_id,
recurso_id...), que es donde suele esconderse el IDOR que el barrido por
ruta no ve.
"""

import datetime as dt
import hashlib
import re

from fastapi.routing import APIRoute
from sqlalchemy import text

from app.main import app
from tests.conftest import token_de


def _rutas():
    def walk(rs):
        for r in rs:
            if isinstance(r, APIRoute):
                yield r
            elif hasattr(r, "original_router"):
                yield from walk(r.original_router.routes)
    return list(walk(app.routes))


def _foto_empresa(db, empresa_id: int) -> str:
    """Hash de todas las filas con empresa_id=B en todas las tablas."""
    tablas = db.execute(text(
        "SELECT table_name FROM information_schema.columns "
        "WHERE column_name='empresa_id' AND table_schema='public' ORDER BY 1"
    )).scalars().all()
    h = hashlib.sha256()
    for t in tablas:
        filas = db.execute(
            text(f'SELECT * FROM "{t}" WHERE empresa_id=:e ORDER BY 1'), {"e": empresa_id}
        ).all()
        h.update(f"{t}:{filas!r}".encode())
    # la propia fila de empresa también
    h.update(repr(db.execute(text("SELECT * FROM empresa WHERE id=:e"), {"e": empresa_id}).all()).encode())
    return h.hexdigest()


def _poblar_b(client, db, ctx):
    """Crea en B una entidad de cada tipo, usando la API de B."""
    h = token_de(ctx.dueno)
    manana = (dt.date.today() + dt.timedelta(days=2))
    inicio = dt.datetime.combine(manana, dt.time(11, 0)).isoformat() + "Z"
    t = client.post("/turnos", headers=h, json={
        "cliente_id": ctx.cliente.id, "recurso_id": ctx.lucas.id,
        "servicio_id": ctx.servicio.id, "fecha_inicio": inicio}).json()
    client.post(f"/turnos/{t['id']}/items", headers=h,
                json={"descripcion": "Cera", "precio": 100, "cantidad": 1, "tipo": "producto"})
    client.post("/caja/abrir", headers=h, json={"saldo_inicial": 0})
    client.post(f"/turnos/{t['id']}/cobro", headers=h,
                json={"pagos": [{"metodo_pago_id": ctx.metodo.id, "monto": 10100}]})
    client.post("/gastos", headers=h, json={"concepto": "Luz", "monto": 50})
    client.post("/categorias-financieras", headers=h, json={"nombre": "Varios", "tipo": "egreso"})
    plan = client.post("/planes-abono", headers=h, json={
        "nombre": "Plan B", "precio": 1000, "ilimitado": True,
        "servicios_cubiertos": [ctx.servicio.id]}).json()
    client.post("/membresias", headers=h, json={
        "cliente_id": ctx.cliente.id, "plan_id": plan.get("id"),
        "fecha_desde": str(dt.date.today()),
        "fecha_hasta": str(dt.date.today() + dt.timedelta(days=30))})
    client.post("/cupones", headers=h, json={"codigo": "BONOB", "tipo": "porcentaje", "valor": 10})
    client.post("/gift-cards", headers=h, json={"monto": 500})
    client.post("/excepciones", headers=h, json={
        "tipo": "feriado", "fecha_desde": str(manana), "fecha_hasta": str(manana)})
    client.post("/pacientes/%d/entradas" % ctx.cliente.id, headers=h, json={"fecha": str(manana)})
    client.post("/pacientes/%d/mediciones" % ctx.cliente.id, headers=h, json={"fecha": str(manana)})
    client.post("/pacientes/%d/adjuntos" % ctx.cliente.id, headers=h,
                json={"nombre_archivo": "x.pdf", "ruta": "https://ejemplo.com/x.pdf"})
    db.flush()


PARAM_TABLA = {
    "cliente_id": "cliente", "turno_id": "turno", "recurso_id": "recurso",
    "servicio_id": "servicio", "cupon_id": "cupon_descuento", "excepcion_id": "excepcion_agenda",
    "gift_id": "gift_card", "membresia_id": "membresia", "metodo_id": "metodo_pago",
    "plan_id": "plan_abono", "sucursal_id": "sucursal", "usuario_id": "usuario",
    "caja_id": "caja", "movimiento_id": "movimiento_financiero", "item_id": "item_turno",
    "horario_id": "horario_recurso", "entrada_id": "entrada_clinica",
    "medicion_id": "medicion_antropometrica", "adjunto_id": "adjunto",
}


def _body_valido(path: str, metodo: str) -> dict:
    """Un body que PASA la validación, para que el chequeo de pertenencia
    sea lo que decide y no el 422 del schema."""
    manana = dt.date.today() + dt.timedelta(days=5)
    ini = dt.datetime.combine(manana, dt.time(16, 0)).isoformat() + "Z"
    tabla = {
        "/turnos/{turno_id}/mover": {"fecha_inicio": ini},
        "/turnos/{turno_id}/estado": {"estado": "cancelado"},
        "/turnos/{turno_id}/descuento": {"descuento_pct": 50},
        "/turnos/{turno_id}/cobro": {"pagos": [{"monto": 1}]},
        "/turnos/{turno_id}/items": {"descripcion": "x", "precio": 1, "cantidad": 1, "tipo": "producto"},
        "/recursos/{recurso_id}/horarios": {"dia_semana": 1, "hora_desde": "09:00", "hora_hasta": "10:00"},
        "/pacientes/{cliente_id}/entradas": {"fecha": str(manana)},
        "/pacientes/{cliente_id}/mediciones": {"fecha": str(manana)},
        "/pacientes/{cliente_id}/adjuntos": {"nombre_archivo": "x", "ruta": "https://ejemplo.com/x"},
        "/cupones/{cupon_id}": {"codigo": "HACK1", "tipo": "monto", "valor": 1},
    }
    if metodo in ("GET", "DELETE"):
        return {}
    return tabla.get(path, {})


def _ids_de(db, tabla: str, empresa_id: int) -> list[int]:
    existe = db.execute(text(
        "SELECT 1 FROM information_schema.tables WHERE table_name=:t"), {"t": tabla}).first()
    if not existe:
        return []
    return list(db.execute(text(f'SELECT id FROM "{tabla}" WHERE empresa_id=:e'),
                           {"e": empresa_id}).scalars())


def test_ningun_endpoint_con_id_en_la_ruta_toca_otra_empresa(client, db, armar_empresa):
    a = armar_empresa("A")
    b = armar_empresa("B")
    _poblar_b(client, db, b)

    ids_b = {p: _ids_de(db, t, b.empresa.id) for p, t in PARAM_TABLA.items()}
    faltan = [p for p, v in ids_b.items() if not v]
    antes = _foto_empresa(db, b.empresa.id)

    fugas, probados = [], 0
    for r in _rutas():
        params = re.findall(r"{(\w+)}", r.path)
        if not params or r.path.startswith("/admin") or r.path.startswith("/publico"):
            continue
        for metodo in r.methods:
            valores = {p: (ids_b.get(p) or [999999])[0] for p in params}
            url = r.path.format(**valores)
            resp = client.request(metodo, url, headers=token_de(a.dueno),
                                  json=_body_valido(r.path, metodo))
            probados += 1
            vacio = resp.status_code == 200 and resp.json() in (None, [], {"total_cobrado": 0.0, "cantidad_pagos": 0})
            if resp.status_code == 422:
                fugas.append(f"(422, body no valido: revisar) {metodo} {url} {resp.text[:100]}")
            elif resp.status_code < 300 and not vacio:
                fugas.append(f"{metodo} {url} -> {resp.status_code} {resp.text[:120]}")

    despues = _foto_empresa(db, b.empresa.id)
    print(f"\nrutas probadas: {probados} · ids de B sin crear: {faltan}")
    assert not faltan, f"no se pudo poblar B: {faltan}"
    assert not fugas, "IDOR:\n" + "\n".join(fugas)
    assert antes == despues, "un endpoint de A MODIFICÓ datos de B"


def test_referencias_por_body_de_otra_empresa(client, db, armar_empresa):
    a = armar_empresa("A")
    b = armar_empresa("B")
    _poblar_b(client, db, b)
    h = token_de(a.dueno)
    plan_b = _ids_de(db, "plan_abono", b.empresa.id)[0]
    cat_b = _ids_de(db, "categoria_financiera", b.empresa.id) or [999999]
    manana = dt.date.today() + dt.timedelta(days=3)
    inicio = dt.datetime.combine(manana, dt.time(15, 0)).isoformat() + "Z"

    # turno propio de A para usar de ancla
    t_a = client.post("/turnos", headers=h, json={
        "cliente_id": a.cliente.id, "recurso_id": a.lucas.id,
        "servicio_id": a.servicio.id, "fecha_inicio": inicio}).json()["id"]
    client.post("/caja/abrir", headers=h, json={"saldo_inicial": 0})

    antes = _foto_empresa(db, b.empresa.id)
    casos = [
        ("POST", "/turnos", {"cliente_id": b.cliente.id, "recurso_id": a.lucas.id,
                             "servicio_id": a.servicio.id, "fecha_inicio": inicio}),
        ("POST", "/turnos", {"cliente_id": a.cliente.id, "recurso_id": b.lucas.id,
                             "servicio_id": a.servicio.id, "fecha_inicio": inicio}),
        ("POST", "/turnos", {"cliente_id": a.cliente.id, "recurso_id": a.lucas.id,
                             "servicio_id": b.servicio.id, "fecha_inicio": inicio}),
        ("PATCH", f"/turnos/{t_a}/mover", {"fecha_inicio": inicio, "recurso_id": b.lucas.id}),
        ("POST", f"/turnos/{t_a}/cobro", {"pagos": [{"metodo_pago_id": b.metodo.id, "monto": 1}]}),
        ("POST", "/membresias", {"cliente_id": b.cliente.id, "plan_id": plan_b,
                                 "fecha_desde": str(dt.date.today()),
                                 "fecha_hasta": str(manana)}),
        ("POST", "/membresias", {"cliente_id": a.cliente.id, "plan_id": plan_b,
                                 "fecha_desde": str(dt.date.today()),
                                 "fecha_hasta": str(manana)}),
        ("POST", "/planes-abono", {"nombre": "x", "precio": 1, "servicios_cubiertos": [b.servicio.id]}),
        ("POST", "/cupones", {"codigo": "XA1", "tipo": "monto", "valor": 1,
                              "servicios_ids": [b.servicio.id]}),
        ("POST", "/gastos", {"concepto": "x", "monto": 1, "categoria_id": cat_b[0]}),
        ("POST", "/gastos", {"concepto": "x", "monto": 1, "metodo_pago_id": b.metodo.id}),
        ("POST", "/gift-cards", {"monto": 1, "metodo_pago_id": b.metodo.id}),
        ("POST", "/recursos", {"nombre": "x", "sucursal_id": b.sede.id}),
        ("POST", "/recursos", {"nombre": "x", "usuario_id": b.profesional.id}),
        ("PATCH", f"/recursos/{a.pablo.id}", {"usuario_id": b.profesional.id}),
        ("PATCH", f"/recursos/{a.pablo.id}", {"sucursal_id": b.sede.id}),
        ("POST", "/excepciones", {"tipo": "feriado", "fecha_desde": str(manana),
                                  "fecha_hasta": str(manana), "recurso_id": b.lucas.id}),
        ("POST", "/servicios", {"nombre": "x", "recurso_ids": [b.lucas.id]}),
        ("POST", "/servicios", {"nombre": "x", "sucursales": [{"sucursal_id": b.sede.id}]}),
        ("PATCH", f"/servicios/{a.servicio.id}", {"recurso_ids": [b.lucas.id]}),
        ("POST", f"/pacientes/{a.cliente.id}/entradas",
         {"fecha": str(manana), "turno_id": _ids_de(db, "turno", b.empresa.id)[0]}),
        ("POST", f"/pacientes/{a.cliente.id}/mediciones",
         {"fecha": str(manana), "entrada_id": (_ids_de(db, "entrada_clinica", b.empresa.id) or [999999])[0]}),
        ("POST", f"/pacientes/{a.cliente.id}/adjuntos",
         {"nombre_archivo": "x", "ruta": "/uploads/x",
          "entrada_clinica_id": (_ids_de(db, "entrada_clinica", b.empresa.id) or [999999])[0]}),
        ("POST", "/equipo/usuarios", {"nombre": "x", "email": "x-cross@example.com",
                                      "clave": "clave-larga-123", "rol": "recepcion",
                                      "sucursal_id": b.sede.id}),
    ]
    # Estos tres filtran el id ajeno en silencio (mismo criterio que
    # servicio.recursos): 2xx es correcto si el id de B NO quedó guardado.
    def _filtrado(url, body, datos):
        ajenos = {b.servicio.id, b.lucas.id}
        for campo in ("servicios_cubiertos", "servicios_ids", "recurso_ids"):
            if campo in body and not (set(datos.get(campo) or []) & ajenos):
                return True
        return False

    aceptados = []
    for metodo, url, body in casos:
        resp = client.request(metodo, url, headers=h, json=body)
        if resp.status_code < 300 and _filtrado(url, body, resp.json()):
            continue
        if resp.status_code < 300:
            aceptados.append(f"{metodo} {url} {body} -> {resp.status_code} {resp.text[:160]}")
    for x in aceptados:
        print("ACEPTADO:", x)
    assert antes == _foto_empresa(db, b.empresa.id), "A modificó datos de B vía body"
    assert not aceptados, "Referencias ajenas aceptadas:\n" + "\n".join(aceptados)


def test_reserva_publica_no_mezcla_empresas(client, db, armar_empresa):
    a = armar_empresa("A")
    b = armar_empresa("B")
    manana = dt.date.today() + dt.timedelta(days=4)
    inicio = dt.datetime.combine(manana, dt.time(12, 0)).isoformat()
    cli = {"nombre": "Ana", "telefono": "2615550000", "email": "ana@example.com"}
    casos = [
        {"servicio_id": b.servicio.id, "inicio": inicio, "cliente": cli},
        {"servicio_id": a.servicio.id, "recurso_id": b.lucas.id, "inicio": inicio, "cliente": cli},
        {"servicio_id": a.servicio.id, "sucursal_id": b.sede.id, "inicio": inicio, "cliente": cli},
    ]
    antes = _foto_empresa(db, b.empresa.id)
    for body in casos:
        r = client.post(f"/publico/{a.empresa.slug}/reservar", json=body)
        assert r.status_code >= 400, (body, r.status_code, r.text[:200])
    assert antes == _foto_empresa(db, b.empresa.id)
