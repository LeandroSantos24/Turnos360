"""Super-admin: resumen, cobros y pagos, devoluciones, caja y cierres,
estadísticas, integraciones, planes y usuarios.

Todo requiere sesión de super-admin (SuperAdminActual). Las acciones que
tocan plata o accesos quedan en `auditoria_admin` dentro de la misma
transacción (ver services/admin_finanzas.py y services/admin_usuarios.py).
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.api.deps import DB, SuperAdminActual
from app.core.rate_limit import limiter
from app.core.reloj import hoy_de_pared
from app.services import admin_finanzas as fin
from app.services import admin_usuarios as usuarios_svc
from app.services import auditoria_admin as audit

router = APIRouter(prefix="/admin", tags=["admin"])


def _periodo(desde: dt.date | None, hasta: dt.date | None) -> tuple[dt.date, dt.date]:
    hoy = hoy_de_pared()
    return desde or hoy.replace(day=1), hasta or hoy


# ── Resumen ───────────────────────────────────────────────────────────────

@router.get("/resumen")
def resumen(admin: SuperAdminActual, db: DB, desde: dt.date | None = None, hasta: dt.date | None = None) -> dict:
    d, h = _periodo(desde, hasta)
    return fin.resumen_general(db, d, h)


# ── Cobros y pagos ────────────────────────────────────────────────────────

def _filtros(desde, hasta, empresa_id, metodo, estado, monto_min, monto_max, buscar) -> dict:
    return dict(
        desde=desde, hasta=hasta, empresa_id=empresa_id, metodo=metodo or None, estado=estado or None,
        monto_min=monto_min, monto_max=monto_max, buscar=buscar or None,
    )


@router.get("/cobros")
def cobros(
    admin: SuperAdminActual,
    db: DB,
    desde: dt.date | None = None,
    hasta: dt.date | None = None,
    empresa_id: int | None = None,
    metodo: str | None = None,
    estado: str | None = None,
    monto_min: float | None = None,
    monto_max: float | None = None,
    buscar: str | None = Query(default=None, max_length=80),
    pagina: int = Query(default=1, ge=1),
    limite: int = Query(default=50, ge=1, le=200),
) -> dict:
    return fin.operaciones(
        db, **_filtros(desde, hasta, empresa_id, metodo, estado, monto_min, monto_max, buscar),
        pagina=pagina, limite=limite,
    )


@router.get("/cobros/exportar")
@limiter.limit("20/minute")
def exportar_cobros(
    request: Request,
    admin: SuperAdminActual,
    db: DB,
    desde: dt.date | None = None,
    hasta: dt.date | None = None,
    empresa_id: int | None = None,
    metodo: str | None = None,
    estado: str | None = None,
    monto_min: float | None = None,
    monto_max: float | None = None,
    buscar: str | None = Query(default=None, max_length=80),
) -> Response:
    datos = fin.operaciones(
        db, **_filtros(desde, hasta, empresa_id, metodo, estado, monto_min, monto_max, buscar), limite=200, pagina=1,
    )
    filas = datos["filas"]
    # Todas las páginas, no solo la primera.
    pagina = 2
    while len(filas) < datos["total"]:
        filas += fin.operaciones(
            db, **_filtros(desde, hasta, empresa_id, metodo, estado, monto_min, monto_max, buscar),
            limite=200, pagina=pagina,
        )["filas"]
        pagina += 1
    audit.auditar(db, admin, "exportar", descripcion=f"Exportó {len(filas)} cobros a CSV", request=request)
    db.commit()
    return Response(
        fin.a_csv(filas, fin.COLUMNAS_OPERACIONES),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="turnos360-cobros.csv"'},
    )


@router.get("/pagos/{pago_id}")
def ver_pago(pago_id: int, admin: SuperAdminActual, db: DB) -> dict:
    return fin.detalle_pago(db, pago_id)


class DevolverIn(BaseModel):
    monto: float = Field(gt=0)
    motivo: str = Field(min_length=4, max_length=300)
    referencia: str | None = Field(default=None, max_length=120)
    confirmada: bool = False
    clave: str | None = Field(default=None, max_length=64)


@router.post("/pagos/{pago_id}/devolver")
@limiter.limit("10/minute")
def devolver(request: Request, pago_id: int, datos: DevolverIn, admin: SuperAdminActual, db: DB) -> dict:
    return fin.devolver(
        db, pago_id, monto=datos.monto, motivo=datos.motivo, admin=admin, referencia=datos.referencia,
        confirmada=datos.confirmada, clave=datos.clave, request=request,
    )


class ReferenciaIn(BaseModel):
    referencia: str = Field(min_length=1, max_length=120)


@router.post("/devoluciones/{devolucion_id}/confirmar")
def confirmar_devolucion(request: Request, devolucion_id: int, datos: ReferenciaIn, admin: SuperAdminActual, db: DB) -> dict:
    return fin.confirmar_devolucion_manual(db, devolucion_id, datos.referencia, admin, request=request)


@router.post("/devoluciones/{devolucion_id}/refrescar")
@limiter.limit("30/minute")
def refrescar_devolucion(request: Request, devolucion_id: int, admin: SuperAdminActual, db: DB) -> dict:
    return fin.refrescar_devolucion(db, devolucion_id)


class ConciliarIn(BaseModel):
    conciliado: bool
    referencia: str | None = Field(default=None, max_length=120)


@router.post("/pagos/{pago_id}/conciliar")
def conciliar(request: Request, pago_id: int, datos: ConciliarIn, admin: SuperAdminActual, db: DB) -> dict:
    return fin.conciliar(db, pago_id, conciliado=datos.conciliado, referencia=datos.referencia, admin=admin, request=request)


class MotivoIn(BaseModel):
    motivo: str = Field(min_length=4, max_length=300)


@router.post("/pagos/{pago_id}/anular")
def anular_pago(request: Request, pago_id: int, datos: MotivoIn, admin: SuperAdminActual, db: DB) -> dict:
    return fin.anular_pago(db, pago_id, motivo=datos.motivo, admin=admin, request=request)


@router.post("/intentos/{intento_id}/anular")
def anular_intento(request: Request, intento_id: int, datos: MotivoIn, admin: SuperAdminActual, db: DB) -> dict:
    return fin.cancelar_intento(db, intento_id, motivo=datos.motivo, admin=admin, request=request)


# ── Caja y cierres ────────────────────────────────────────────────────────

@router.get("/caja")
def caja(admin: SuperAdminActual, db: DB, desde: dt.date | None = None, hasta: dt.date | None = None) -> dict:
    d, h = _periodo(desde, hasta)
    return fin.caja(db, d, h)


@router.get("/cierres")
def cierres(admin: SuperAdminActual, db: DB) -> list[dict]:
    return fin.listar_cierres(db)


class CierreIn(BaseModel):
    desde: dt.date
    hasta: dt.date
    observaciones: str | None = Field(default=None, max_length=2000)


@router.post("/cierres")
def preparar_cierre(request: Request, datos: CierreIn, admin: SuperAdminActual, db: DB) -> dict:
    return fin.preparar_cierre(db, datos.desde, datos.hasta, datos.observaciones, admin, request=request)


class ObservacionesIn(BaseModel):
    observaciones: str | None = Field(default=None, max_length=2000)


@router.post("/cierres/{cierre_id}/confirmar")
def confirmar_cierre(request: Request, cierre_id: int, datos: ObservacionesIn, admin: SuperAdminActual, db: DB) -> dict:
    return fin.confirmar_cierre(db, cierre_id, datos.observaciones, admin, request=request)


@router.post("/cierres/{cierre_id}/reabrir")
def reabrir_cierre(request: Request, cierre_id: int, datos: MotivoIn, admin: SuperAdminActual, db: DB) -> dict:
    return fin.reabrir_cierre(db, cierre_id, datos.motivo, admin, request=request)


@router.post("/cierres/{cierre_id}/descartar")
def descartar_cierre(request: Request, cierre_id: int, admin: SuperAdminActual, db: DB) -> dict:
    return fin.anular_borrador(db, cierre_id, admin, request=request)


# ── Estadísticas ──────────────────────────────────────────────────────────

@router.get("/estadisticas")
def estadisticas(
    admin: SuperAdminActual,
    db: DB,
    granularidad: str = "mes",
    desde: dt.date | None = None,
    hasta: dt.date | None = None,
) -> dict:
    from app.services import ajustes_admin

    hoy = hoy_de_pared()
    h = hasta or hoy
    d = desde or (h.replace(day=1) - dt.timedelta(days=150)).replace(day=1)
    salida = fin.estadisticas(db, granularidad, d, h)
    # Indicador comercial aparte: días regalados. No toca ninguna suma de plata.
    salida["beneficios"] = ajustes_admin.beneficios(db, d, h, granularidad)
    return salida


# ── Suscripciones: evolución y ajustes administrativos ──────────────────────

@router.get("/suscripciones/evolucion")
def evolucion_suscripciones(
    admin: SuperAdminActual,
    db: DB,
    granularidad: str = "dia",
    desde: dt.date | None = None,
    hasta: dt.date | None = None,
) -> dict:
    from app.services import historial_suscripciones

    h = hasta or hoy_de_pared()
    d = desde or h - dt.timedelta(days=29)
    return historial_suscripciones.evolucion(db, granularidad, d, h)


@router.post("/suscripciones/foto")
@limiter.limit("10/hour")
def tomar_foto_suscripciones(request: Request, admin: SuperAdminActual, db: DB) -> dict:
    """Toma ahora la foto del día (la misma que corre a la noche). Idempotente."""
    from app.services import historial_suscripciones

    return historial_suscripciones.tomar_fotos(db)


@router.get("/ajustes")
def ajustes_administrativos(
    admin: SuperAdminActual,
    db: DB,
    empresa_id: int | None = None,
    admin_email: str | None = Query(default=None, max_length=160),
    categoria: str | None = None,
    desde: dt.date | None = None,
    hasta: dt.date | None = None,
    incluir_automaticos: bool = False,
    pagina: int = Query(default=1, ge=1),
    limite: int = Query(default=50, ge=1, le=200),
) -> dict:
    from app.services import ajustes_admin

    return ajustes_admin.listar(
        db, empresa_id=empresa_id, admin_email=admin_email, categoria=categoria, desde=desde, hasta=hasta,
        incluir_automaticos=incluir_automaticos, pagina=pagina, limite=limite,
    )


@router.get("/estadisticas/exportar")
@limiter.limit("20/minute")
def exportar_estadisticas(
    request: Request,
    admin: SuperAdminActual,
    db: DB,
    granularidad: str = "mes",
    desde: dt.date | None = None,
    hasta: dt.date | None = None,
) -> Response:
    hoy = hoy_de_pared()
    h = hasta or hoy
    d = desde or (h.replace(day=1) - dt.timedelta(days=150)).replace(day=1)
    datos = fin.estadisticas(db, granularidad, d, h)
    audit.auditar(db, admin, "exportar", descripcion=f"Exportó estadísticas ({granularidad}) a CSV", request=request)
    db.commit()
    return Response(
        fin.a_csv(datos["serie"], fin.COLUMNAS_ESTADISTICAS),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="turnos360-estadisticas-{granularidad}.csv"'},
    )


# ── Integraciones y planes ────────────────────────────────────────────────

@router.get("/integraciones/mercadopago")
def estado_mercadopago(admin: SuperAdminActual, db: DB) -> dict:
    return fin.estado_mp(db)


@router.get("/planes")
def planes(admin: SuperAdminActual, db: DB) -> list[dict]:
    return fin.planes(db)


# ── Usuarios y accesos ────────────────────────────────────────────────────

@router.get("/usuarios")
def usuarios(
    admin: SuperAdminActual,
    db: DB,
    buscar: str | None = Query(default=None, max_length=80),
    empresa_id: int | None = None,
    rol: str | None = None,
    activo: bool | None = None,
    pagina: int = Query(default=1, ge=1),
    limite: int = Query(default=50, ge=1, le=200),
) -> dict:
    return usuarios_svc.listar(
        db, buscar=buscar, empresa_id=empresa_id, rol=rol, activo=activo, limite=limite, pagina=pagina,
    )


class AccesoIn(BaseModel):
    activo: bool
    motivo: str | None = Field(default=None, max_length=200)


@router.post("/usuarios/{usuario_id}/acceso")
def cambiar_acceso(request: Request, usuario_id: int, datos: AccesoIn, admin: SuperAdminActual, db: DB) -> dict:
    return usuarios_svc.cambiar_acceso(db, usuario_id, activo=datos.activo, motivo=datos.motivo, admin=admin, request=request)


class MotivoSesionIn(BaseModel):
    motivo: str = Field(min_length=4, max_length=200)


@router.get("/usuarios/{usuario_id}/sesiones")
def sesiones_usuario(usuario_id: int, admin: SuperAdminActual, db: DB) -> dict:
    return usuarios_svc.sesiones_de(db, usuario_id)


@router.post("/usuarios/{usuario_id}/sesiones/{sesion_id}/revocar")
@limiter.limit("60/hour")
def revocar_sesion(request: Request, usuario_id: int, sesion_id: int, datos: MotivoSesionIn, admin: SuperAdminActual, db: DB) -> dict:
    return usuarios_svc.revocar_sesion(db, usuario_id, sesion_id, datos.motivo, admin, request)


@router.post("/usuarios/{usuario_id}/cerrar-sesiones")
@limiter.limit("30/hour")
def cerrar_sesiones(request: Request, usuario_id: int, datos: MotivoSesionIn, admin: SuperAdminActual, db: DB) -> dict:
    return usuarios_svc.cerrar_todas(db, usuario_id, datos.motivo, admin, request)


@router.post("/usuarios/{usuario_id}/invitacion/reenviar")
@limiter.limit("10/hour")
def reenviar_invitacion(request: Request, usuario_id: int, admin: SuperAdminActual, db: DB) -> dict:
    from app.services import invitaciones

    return invitaciones.reenviar(db, usuario_id, admin, request)


@router.post("/usuarios/{usuario_id}/invitacion/revocar")
@limiter.limit("30/hour")
def revocar_invitacion(request: Request, usuario_id: int, admin: SuperAdminActual, db: DB) -> dict:
    from app.services import invitaciones

    return invitaciones.revocar(db, usuario_id, admin, request)


class RestablecerIn(BaseModel):
    cerrar_sesiones: bool = True


@router.post("/usuarios/{usuario_id}/restablecer")
@limiter.limit("10/hour")
def restablecer(request: Request, usuario_id: int, datos: RestablecerIn, admin: SuperAdminActual, db: DB) -> dict:
    return usuarios_svc.iniciar_restablecimiento(
        db, usuario_id, cerrar_sesiones=datos.cerrar_sesiones, admin=admin, request=request,
    )
