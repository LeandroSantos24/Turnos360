"""Finanzas del super-admin: cobros, devoluciones, conciliación, caja,
cierres, estadísticas y estado de Mercado Pago.

TODO ESTO ES LA CAJA DE TURNOS360 (lo que los negocios le pagan por la
cuota), no la caja de un negocio (models/finanzas.py). Son dos mundos que no
se cruzan.

CRITERIOS (los mismos en todas las pantallas)
─────────────────────────────────────────────
- Ingreso = pago acreditado (`pago_suscripcion`), por su fecha de
  acreditación (`fecha`), no por cuándo se creó el registro.
- Un pago anulado por CORRECCIÓN (se cargó mal) no es ingreso. Un pago
  anulado porque se DEVOLVIÓ sí fue ingreso, y la devolución resta aparte en
  la fecha en que se confirmó. Así el mismo dinero nunca se cuenta dos veces
  ni se resta dos veces.
- Devolución = solo las «aprobadas». Una solicitada o en proceso se muestra
  como pendiente, nunca como plata devuelta.
- Comisión = la que informó Mercado Pago al acreditar. Si no se conoce, no se
  inventa: se muestra como «sin dato».
- Pendiente / en revisión / rechazado son OPERACIONES (avisos de
  transferencia e intentos de pago), no ingresos.
- Saldo = calculado con los registros del sistema. No es el saldo del banco:
  lo que está conciliado y lo que no se muestra por separado.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import uuid
from collections import defaultdict

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    AjusteSuscripcion,
    AvisoPago,
    CierreCajaSaas,
    DevolucionSuscripcion,
    Empresa,
    EventoMP,
    IntentoPago,
    PagoSuscripcion,
)
from app.services import auditoria_admin as audit
from app.services import mp_suscripcion as mp

# ── Estados ───────────────────────────────────────────────────────────────

ETIQUETA_ESTADO = {
    "pendiente": "Pendiente",
    "en_revision": "En revisión",
    "acreditado": "Acreditado",
    "rechazado": "Rechazado",
    "cancelado": "Cancelado",
    "anulado": "Anulado (corrección)",
    "reembolso_solicitado": "Reembolso solicitado",
    "reembolso_parcial": "Reembolso parcial",
    "reembolso_total": "Reembolso total",
}


def _f(x) -> float:
    return float(x or 0)


def _hoy() -> dt.date:
    from app.core.reloj import hoy_de_pared

    return hoy_de_pared()


def _dia(ts: dt.datetime | None) -> dt.date | None:
    """Fecha de negocio (Argentina) de un instante guardado en UTC."""
    if ts is None:
        return None
    from zoneinfo import ZoneInfo

    return ts.astimezone(ZoneInfo(settings.zona_horaria)).date()


def _devoluciones_por_pago(db: Session, pago_ids: list[int]) -> dict[int, dict]:
    """{pago_id: {aprobado, pendiente, rechazado}} en pesos."""
    res: dict[int, dict] = defaultdict(lambda: {"aprobado": 0.0, "pendiente": 0.0, "rechazado": 0.0})
    if not pago_ids:
        return res
    for d in db.scalars(select(DevolucionSuscripcion).where(DevolucionSuscripcion.pago_id.in_(pago_ids))):
        clave = "aprobado" if d.estado == "aprobada" else "rechazado" if d.estado == "rechazada" else "pendiente"
        res[d.pago_id][clave] += _f(d.monto)
    return res


def estado_de_pago(pago: PagoSuscripcion, dev: dict) -> str:
    aprobado, pendiente = dev.get("aprobado", 0.0), dev.get("pendiente", 0.0)
    if aprobado >= _f(pago.monto) - 0.009 and aprobado > 0:
        return "reembolso_total"
    if aprobado > 0:
        return "reembolso_parcial"
    if pago.anulado:
        return "anulado"
    if pendiente > 0:
        return "reembolso_solicitado"
    return "acreditado"


def cuenta_como_ingreso(pago: PagoSuscripcion, dev: dict) -> bool:
    """Anulado por corrección no; anulado porque se devolvió, sí (la
    devolución resta aparte)."""
    return (not pago.anulado) or dev.get("aprobado", 0.0) > 0


def _concepto(tipo: str | None, plan: str | None) -> str:
    base = {
        "alta": "Alta",
        "renovacion": "Renovación",
        "cambio_plan": "Cambio de plan",
        "reactivacion": "Reactivación",
        "manual": "Pago",
    }.get(tipo or "", "Cuota")
    return f"{base} · plan {plan}" if plan else base


# ── Operaciones (cobros y pagos) ──────────────────────────────────────────

def operaciones(
    db: Session,
    *,
    desde: dt.date | None = None,
    hasta: dt.date | None = None,
    empresa_id: int | None = None,
    metodo: str | None = None,
    estado: str | None = None,
    monto_min: float | None = None,
    monto_max: float | None = None,
    buscar: str | None = None,
    limite: int = 50,
    pagina: int = 1,
) -> dict:
    """Todo lo que es o fue un cobro de cuota, en una sola lista.

    Une tres fuentes sin duplicar: pagos acreditados, transferencias
    informadas que todavía no son pago (en revisión / rechazadas) e intentos
    de Mercado Pago que no terminaron en pago (pendientes / rechazados /
    cancelados). Las que sí terminaron en pago aparecen una sola vez: como
    pago.
    """
    nombres = dict(db.execute(select(Empresa.id, Empresa.nombre)).all())
    filas: list[dict] = []

    q = select(PagoSuscripcion)
    if empresa_id:
        q = q.where(PagoSuscripcion.empresa_id == empresa_id)
    pagos = list(db.scalars(q))
    devs = _devoluciones_por_pago(db, [p.id for p in pagos])
    for p in pagos:
        e = estado_de_pago(p, devs[p.id])
        filas.append({
            "clave": f"P-{p.id}", "tipo": "pago", "id": p.id,
            "empresa_id": p.empresa_id, "empresa": nombres.get(p.empresa_id, "—"),
            "concepto": _concepto(p.tipo, p.plan), "monto": _f(p.monto), "moneda": "ARS",
            "creado_en": p.creado_en.isoformat() if p.creado_en else None,
            "fecha": p.fecha.isoformat() if p.fecha else None,
            "acreditado_en": p.fecha.isoformat() if p.fecha else None,
            "metodo": p.metodo, "estado": e, "estado_etiqueta": ETIQUETA_ESTADO[e],
            "id_proveedor": p.mp_payment_id, "referencia": p.referencia_banco,
            "devuelto": devs[p.id]["aprobado"], "conciliado": bool(p.conciliado),
            "comision": _f(p.comision) if p.comision is not None else None,
        })

    q = select(AvisoPago).where(AvisoPago.estado.in_(("pendiente", "info_solicitada", "rechazada")))
    if empresa_id:
        q = q.where(AvisoPago.empresa_id == empresa_id)
    for a in db.scalars(q):
        e = "rechazado" if a.estado == "rechazada" else "en_revision"
        monto = _f(a.monto if a.monto is not None else a.monto_esperado)
        filas.append({
            "clave": f"A-{a.id}", "tipo": "transferencia_informada", "id": a.id,
            "empresa_id": a.empresa_id, "empresa": nombres.get(a.empresa_id, "—"),
            "concepto": _concepto(a.tipo, a.plan) + " · transferencia informada",
            "monto": monto, "moneda": "ARS",
            "creado_en": a.creado_en.isoformat() if a.creado_en else None,
            "fecha": (_dia(a.creado_en) or _hoy()).isoformat(), "acreditado_en": None,
            "metodo": a.metodo or "transferencia", "estado": e,
            "estado_etiqueta": "Información pedida" if a.estado == "info_solicitada" else ETIQUETA_ESTADO[e],
            "id_proveedor": None, "referencia": a.referencia, "devuelto": 0.0,
            "conciliado": False, "comision": None, "motivo": a.motivo,
        })

    q = select(IntentoPago).where(IntentoPago.estado.in_(("iniciado", "pendiente", "rechazado", "cancelado")))
    if empresa_id:
        q = q.where(IntentoPago.empresa_id == empresa_id)
    for i in db.scalars(q):
        e = {"iniciado": "pendiente", "pendiente": "pendiente"}.get(i.estado, i.estado)
        filas.append({
            "clave": f"I-{i.id}", "tipo": "intento_mp", "id": i.id,
            "empresa_id": i.empresa_id, "empresa": nombres.get(i.empresa_id, "—"),
            "concepto": _concepto(i.tipo, i.plan) + " · Mercado Pago",
            "monto": _f(i.monto), "moneda": "ARS",
            "creado_en": i.creado_en.isoformat() if i.creado_en else None,
            "fecha": (_dia(i.creado_en) or _hoy()).isoformat(), "acreditado_en": None,
            "metodo": i.metodo, "estado": e, "estado_etiqueta": ETIQUETA_ESTADO.get(e, e),
            "id_proveedor": i.mp_payment_id, "referencia": i.detalle, "devuelto": 0.0,
            "conciliado": False, "comision": None,
        })

    def pasa(f: dict) -> bool:
        fecha = dt.date.fromisoformat(f["fecha"]) if f["fecha"] else None
        if desde and (fecha is None or fecha < desde):
            return False
        if hasta and (fecha is None or fecha > hasta):
            return False
        if metodo and f["metodo"] != metodo:
            return False
        if estado and f["estado"] != estado:
            return False
        if monto_min is not None and f["monto"] < monto_min:
            return False
        if monto_max is not None and f["monto"] > monto_max:
            return False
        if buscar:
            b = buscar.strip().lower()
            campos = (f["clave"], str(f["id"]), f["empresa"], f["id_proveedor"] or "", f["referencia"] or "")
            if not any(b in str(c).lower() for c in campos):
                return False
        return True

    filas = [f for f in filas if pasa(f)]
    filas.sort(key=lambda f: (f["fecha"] or "", f["creado_en"] or ""), reverse=True)
    total = len(filas)
    limite = max(1, min(limite, 200))
    pagina = max(1, pagina)
    return {
        "total": total,
        "pagina": pagina,
        "limite": limite,
        "filas": filas[(pagina - 1) * limite: pagina * limite],
        "sumas": {
            "acreditado": round(sum(f["monto"] for f in filas if f["tipo"] == "pago" and f["estado"] != "anulado"), 2),
            "en_revision": round(sum(f["monto"] for f in filas if f["estado"] == "en_revision"), 2),
            "pendiente": round(sum(f["monto"] for f in filas if f["estado"] == "pendiente"), 2),
            "rechazado": round(sum(f["monto"] for f in filas if f["estado"] == "rechazado"), 2),
            "devuelto": round(sum(f["devuelto"] for f in filas), 2),
        },
    }


def _pago_bloqueado(db: Session, pago_id: int) -> PagoSuscripcion:
    pago = db.scalar(
        select(PagoSuscripcion)
        .where(PagoSuscripcion.id == pago_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if pago is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ese pago no existe.")
    return pago


def _devolvible(pago: PagoSuscripcion, dev: dict) -> float:
    return round(max(0.0, _f(pago.monto) - dev.get("aprobado", 0.0) - dev.get("pendiente", 0.0)), 2)


def detalle_pago(db: Session, pago_id: int) -> dict:
    pago = db.get(PagoSuscripcion, pago_id)
    if pago is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ese pago no existe.")
    empresa = db.get(Empresa, pago.empresa_id)
    dev = _devoluciones_por_pago(db, [pago.id])[pago.id]
    e = estado_de_pago(pago, dev)
    devoluciones = [
        {
            "id": d.id, "monto": _f(d.monto), "metodo": d.metodo, "estado": d.estado,
            "motivo": d.motivo, "referencia": d.referencia, "mp_refund_id": d.mp_refund_id,
            "error": d.error, "origen": d.origen, "solicitada_por": d.solicitada_por,
            "solicitada_en": d.solicitada_en.isoformat() if d.solicitada_en else None,
            "confirmada_en": d.confirmada_en.isoformat() if d.confirmada_en else None,
        }
        for d in db.scalars(
            select(DevolucionSuscripcion)
            .where(DevolucionSuscripcion.pago_id == pago.id)
            .order_by(DevolucionSuscripcion.solicitada_en)
        )
    ]
    historial = [
        {
            "fecha": a.creado_en.isoformat() if a.creado_en else None, "tipo": a.tipo,
            "detalle": a.detalle, "hecho_por": a.hecho_por, "revertido": bool(a.revertido),
        }
        for a in db.scalars(
            select(AjusteSuscripcion)
            .where(AjusteSuscripcion.pago_id == pago.id)
            .order_by(AjusteSuscripcion.creado_en)
        )
    ]
    aviso = db.scalar(select(AvisoPago).where(AvisoPago.pago_id == pago.id))
    ajuste_pago = db.scalar(
        select(AjusteSuscripcion).where(
            AjusteSuscripcion.pago_id == pago.id,
            AjusteSuscripcion.tipo.in_(("pago", "renovacion", "manual")),
            AjusteSuscripcion.revertido.is_(False),
        )
    )
    devolvible = _devolvible(pago, dev)
    es_mp = pago.metodo == "mercadopago" and bool(pago.mp_payment_id)
    return {
        "id": pago.id,
        "empresa_id": pago.empresa_id,
        "empresa": empresa.nombre if empresa else "—",
        "concepto": _concepto(pago.tipo, pago.plan),
        "monto": _f(pago.monto),
        "moneda": "ARS",
        "metodo": pago.metodo,
        "fecha": pago.fecha.isoformat() if pago.fecha else None,
        "creado_en": pago.creado_en.isoformat() if pago.creado_en else None,
        "registrado_por": pago.registrado_por,
        "periodo_desde": pago.periodo_desde.isoformat() if pago.periodo_desde else None,
        "periodo_hasta": pago.periodo_hasta.isoformat() if pago.periodo_hasta else None,
        "notas": pago.notas,
        "mp_payment_id": pago.mp_payment_id,
        "comision": _f(pago.comision) if pago.comision is not None else None,
        "neto": _f(pago.neto) if pago.neto is not None else None,
        "estado": e,
        "estado_etiqueta": ETIQUETA_ESTADO[e],
        "anulado": bool(pago.anulado),
        "anulado_en": pago.anulado_en.isoformat() if pago.anulado_en else None,
        "anulado_por": pago.anulado_por,
        "anulado_motivo": pago.anulado_motivo,
        "conciliado": bool(pago.conciliado),
        "conciliado_en": pago.conciliado_en.isoformat() if pago.conciliado_en else None,
        "conciliado_por": pago.conciliado_por,
        "referencia_banco": pago.referencia_banco,
        "devuelto": dev["aprobado"],
        "devolucion_pendiente": dev["pendiente"],
        "devolvible": devolvible,
        "devoluciones": devoluciones,
        "historial": historial,
        "aviso": (
            {"id": aviso.id, "referencia": aviso.referencia, "resuelto_por": aviso.resuelto_por,
             "resuelto_en": aviso.resuelto_en.isoformat() if aviso.resuelto_en else None,
             "tiene_comprobante": bool(aviso.comprobante)}
            if aviso else None
        ),
        "acciones": {
            "devolver_mp": es_mp and devolvible > 0 and mp.esta_activo() and not (pago.anulado and dev["aprobado"] == 0),
            "devolver_manual": (not es_mp) and devolvible > 0 and not pago.anulado,
            "conciliar": not pago.anulado or dev["aprobado"] > 0,
            # Corregir una carga: solo pagos manuales sin devoluciones, y por el
            # mismo camino que «Deshacer» (revierte también el vencimiento).
            "anular": (not pago.anulado) and (not es_mp) and dev["aprobado"] == 0 and dev["pendiente"] == 0
            and ajuste_pago is not None,
        },
        "ajuste_id": ajuste_pago.id if ajuste_pago else None,
    }


# ── Devoluciones ──────────────────────────────────────────────────────────

def devolver(
    db: Session,
    pago_id: int,
    *,
    monto: float,
    motivo: str,
    admin,
    referencia: str | None = None,
    confirmada: bool = False,
    clave: str | None = None,
    request=None,
) -> dict:
    """Pide (MP) o registra (manual) la devolución de un pago.

    - Mercado Pago: se pide por la API. La devolución queda con el estado que
      informa MP; solo «aprobada» cuenta como plata devuelta.
    - Manual (transferencia / efectivo): `confirmada=True` exige la referencia
      de la transferencia de vuelta; sin confirmar, queda «solicitada».
    Nunca toca el pago original salvo marcarlo devuelto si se devolvió todo.
    """
    from app.services import cobranza

    motivo = (motivo or "").strip()
    if len(motivo) < 4:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Escribí el motivo de la devolución.")
    if monto is None or monto <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El monto tiene que ser mayor a cero.")
    if clave:
        previa = db.scalar(select(DevolucionSuscripcion).where(DevolucionSuscripcion.clave_idempotencia == clave))
        if previa is not None:
            return detalle_pago(db, previa.pago_id)

    pago = _pago_bloqueado(db, pago_id)
    dev = _devoluciones_por_pago(db, [pago.id])[pago.id]
    if pago.anulado and dev["aprobado"] == 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ese pago está anulado: no hay nada que devolver.")
    devolvible = _devolvible(pago, dev)
    monto = round(float(monto), 2)
    if monto > devolvible + 0.001:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Se puede devolver hasta {cobranza.pesos(devolvible)} (lo acreditado menos lo ya devuelto o pedido).",
        )
    empresa = db.get(Empresa, pago.empresa_id)
    quien = getattr(admin, "email", None) or str(admin)
    es_mp = pago.metodo == "mercadopago" and bool(pago.mp_payment_id)

    d = DevolucionSuscripcion(
        pago_id=pago.id, empresa_id=pago.empresa_id, monto=monto,
        metodo="mercadopago" if es_mp else "manual", estado="solicitada",
        motivo=motivo[:300], referencia=(referencia or "").strip()[:120] or None,
        clave_idempotencia=clave or uuid.uuid4().hex, solicitada_por=quien,
    )
    db.add(d)
    db.flush()

    if es_mp:
        total = dev["aprobado"] == 0 and dev["pendiente"] == 0 and abs(monto - _f(pago.monto)) < 0.01
        try:
            r = mp.devolver(pago.mp_payment_id, None if total else monto, d.clave_idempotencia)
        except mp.ErrorMP as e:
            d.estado = "rechazada"
            d.error = str(e)[:300]
            audit.auditar(db, admin, "devolucion", empresa_id=pago.empresa_id,
                          descripcion=f"Devolución de {cobranza.pesos(monto)} del pago #{pago.id} rechazada: {d.error}",
                          request=request)
            db.commit()
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from e
        d.mp_refund_id = str(r.get("id") or "") or None
        d.estado = mp._ESTADO_DEVOLUCION.get(str(r.get("status") or ""), "en_proceso")
    else:
        if confirmada:
            if not d.referencia:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    "Para darla por hecha, cargá la referencia de la transferencia de vuelta.",
                )
            d.estado = "aprobada"

    if d.estado == "aprobada":
        d.confirmada_en = dt.datetime.now(dt.timezone.utc)
    _marcar_si_devuelto_todo(db, pago, quien)
    cobranza.evento(
        db, empresa, "devolucion",
        f"Devolución de {cobranza.pesos(monto)} del pago #{pago.id} ({d.estado}): {motivo[:120]}",
        hecho_por=quien, actor_tipo="admin", monto=monto, pago_id=pago.id,
    )
    audit.auditar(db, admin, "devolucion", empresa_id=pago.empresa_id,
                  descripcion=f"Devolución de {cobranza.pesos(monto)} del pago #{pago.id} · {d.metodo} · {d.estado}",
                  request=request)
    db.commit()
    return detalle_pago(db, pago.id)


def _marcar_si_devuelto_todo(db: Session, pago: PagoSuscripcion, quien: str) -> None:
    db.flush()
    dev = _devoluciones_por_pago(db, [pago.id])[pago.id]
    if not pago.anulado and dev["aprobado"] >= _f(pago.monto) - 0.009:
        pago.anulado = True
        pago.anulado_en = dt.datetime.now(dt.timezone.utc)
        pago.anulado_por = quien
        pago.anulado_motivo = "Devuelto en su totalidad"


def confirmar_devolucion_manual(db: Session, devolucion_id: int, referencia: str, admin, request=None) -> dict:
    d = db.get(DevolucionSuscripcion, devolucion_id)
    if d is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Esa devolución no existe.")
    if d.metodo != "manual":
        raise HTTPException(status.HTTP_409_CONFLICT, "Las devoluciones de Mercado Pago las confirma Mercado Pago.")
    if d.estado != "solicitada":
        raise HTTPException(status.HTTP_409_CONFLICT, "Esa devolución ya no está pendiente.")
    referencia = (referencia or "").strip()
    if not referencia:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cargá la referencia de la transferencia de vuelta.")
    pago = _pago_bloqueado(db, d.pago_id)
    d.referencia = referencia[:120]
    d.estado = "aprobada"
    d.confirmada_en = dt.datetime.now(dt.timezone.utc)
    quien = getattr(admin, "email", None) or str(admin)
    _marcar_si_devuelto_todo(db, pago, quien)
    audit.auditar(db, admin, "devolucion", empresa_id=d.empresa_id,
                  descripcion=f"Confirmó la devolución #{d.id} ({referencia[:60]})", request=request)
    db.commit()
    return detalle_pago(db, pago.id)


def refrescar_devolucion(db: Session, devolucion_id: int) -> dict:
    """Le pregunta a MP cómo está una devolución pedida desde el panel."""
    d = db.get(DevolucionSuscripcion, devolucion_id)
    if d is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Esa devolución no existe.")
    if d.metodo != "mercadopago" or not d.mp_refund_id:
        return detalle_pago(db, d.pago_id)
    pago = _pago_bloqueado(db, d.pago_id)
    try:
        r = mp.consultar_devolucion(pago.mp_payment_id, d.mp_refund_id)
    except mp.ErrorMP as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from e
    nuevo = mp._ESTADO_DEVOLUCION.get(str(r.get("status") or ""), d.estado)
    if nuevo != d.estado:
        d.estado = nuevo
        if nuevo == "aprobada":
            d.confirmada_en = dt.datetime.now(dt.timezone.utc)
        _marcar_si_devuelto_todo(db, pago, "mercadopago")
    db.commit()
    return detalle_pago(db, pago.id)


# ── Conciliación y corrección ─────────────────────────────────────────────

def conciliar(db: Session, pago_id: int, *, conciliado: bool, referencia: str | None, admin, request=None) -> dict:
    pago = _pago_bloqueado(db, pago_id)
    quien = getattr(admin, "email", None) or str(admin)
    pago.conciliado = conciliado
    pago.conciliado_en = dt.datetime.now(dt.timezone.utc) if conciliado else None
    pago.conciliado_por = quien if conciliado else None
    if referencia is not None:
        pago.referencia_banco = referencia.strip()[:120] or None
    audit.auditar(db, admin, "conciliar" if conciliado else "desconciliar", empresa_id=pago.empresa_id,
                  descripcion=f"Pago #{pago.id} {'conciliado' if conciliado else 'vuelto a sin conciliar'}"
                  + (f" · ref. {pago.referencia_banco}" if pago.referencia_banco else ""),
                  request=request)
    db.commit()
    return detalle_pago(db, pago.id)


def anular_pago(db: Session, pago_id: int, *, motivo: str, admin, request=None) -> dict:
    """Corrección de una carga equivocada. No borra nada: usa el mismo camino
    que «Deshacer» (anula el pago y devuelve el vencimiento a como estaba)."""
    from app.services import cobranza

    motivo = (motivo or "").strip()
    if len(motivo) < 4:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Escribí por qué se anula.")
    info = detalle_pago(db, pago_id)
    if not info["acciones"]["anular"]:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Este pago no se puede anular desde acá. Si es de Mercado Pago o ya tiene devoluciones, usá «Devolver».",
        )
    empresa = db.get(Empresa, info["empresa_id"])
    antes = audit.foto(db, empresa)
    quien = getattr(admin, "email", None) or str(admin)
    cobranza.revertir_ajuste(db, info["empresa_id"], info["ajuste_id"], hecho_por=quien)
    pago = db.get(PagoSuscripcion, pago_id)
    pago.anulado_motivo = motivo[:300]
    audit.auditar(db, admin, "anular_pago", empresa_id=info["empresa_id"],
                  descripcion=f"Anuló el pago #{pago_id}: {motivo[:200]}",
                  antes=antes, despues=audit.foto(db, empresa), request=request)
    db.commit()
    return detalle_pago(db, pago_id)


def cancelar_intento(db: Session, intento_id: int, *, motivo: str, admin, request=None) -> dict:
    """Anulación de un cobro de MP que todavía no se acreditó.

    Si ya hay un pago en MP pendiente, se le pide a MP que lo cancele; si el
    checkout ni se abrió, se cierra el intento acá. Un pago aprobado NO se
    anula: se devuelve.
    """
    i = db.scalar(select(IntentoPago).where(IntentoPago.id == intento_id).with_for_update())
    if i is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Esa operación no existe.")
    if i.estado == "aprobado":
        raise HTTPException(status.HTTP_409_CONFLICT, "Ese pago ya se acreditó: no se anula, se devuelve desde el pago.")
    if i.estado not in ("iniciado", "pendiente"):
        raise HTTPException(status.HTTP_409_CONFLICT, "Esa operación ya está cerrada.")
    if i.mp_payment_id:
        try:
            r = mp.cancelar_pago(i.mp_payment_id)
        except mp.ErrorMP as e:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from e
        if str(r.get("status") or "") != "cancelled":
            raise HTTPException(status.HTTP_409_CONFLICT, "Mercado Pago no confirmó la cancelación. Revisá el pago en MP.")
    i.estado = "cancelado"
    i.detalle = f"Anulado desde el panel: {(motivo or '').strip()[:150]}"
    i.actualizado_en = dt.datetime.now(dt.timezone.utc)
    audit.auditar(db, admin, "anular_intento", empresa_id=i.empresa_id,
                  descripcion=f"Anuló el intento de pago #{i.id}" + (f" (MP {i.mp_payment_id})" if i.mp_payment_id else ""),
                  request=request)
    db.commit()
    return {"id": i.id, "estado": i.estado}


# ── Caja ──────────────────────────────────────────────────────────────────

def _movimientos(db: Session, desde: dt.date | None, hasta: dt.date) -> tuple[list[dict], list[dict]]:
    """(ingresos, devoluciones) del período, según los criterios de arriba."""
    q = select(PagoSuscripcion).where(PagoSuscripcion.fecha <= hasta)
    if desde:
        q = q.where(PagoSuscripcion.fecha >= desde)
    pagos = list(db.scalars(q))
    devs = _devoluciones_por_pago(db, [p.id for p in pagos])
    nombres = dict(db.execute(select(Empresa.id, Empresa.nombre)).all())
    ingresos = [
        {
            "pago_id": p.id, "fecha": p.fecha.isoformat(), "empresa": nombres.get(p.empresa_id, "—"),
            "concepto": _concepto(p.tipo, p.plan), "metodo": p.metodo, "monto": _f(p.monto),
            "comision": _f(p.comision) if p.comision is not None else None,
            "conciliado": bool(p.conciliado), "referencia": p.referencia_banco,
        }
        for p in pagos
        if cuenta_como_ingreso(p, devs[p.id])
    ]
    salidas = []
    for d in db.scalars(select(DevolucionSuscripcion).where(DevolucionSuscripcion.estado == "aprobada")):
        dia = _dia(d.confirmada_en) or _dia(d.solicitada_en)
        if dia is None or dia > hasta or (desde and dia < desde):
            continue
        salidas.append({
            "devolucion_id": d.id, "pago_id": d.pago_id, "fecha": dia.isoformat(),
            "empresa": nombres.get(d.empresa_id, "—"), "metodo": d.metodo, "monto": _f(d.monto),
            "referencia": d.referencia or d.mp_refund_id,
        })
    return ingresos, salidas


def _totales(ingresos: list[dict], salidas: list[dict]) -> dict:
    por_metodo: dict[str, dict] = defaultdict(lambda: {"cobros": 0.0, "devoluciones": 0.0})
    for m in ingresos:
        por_metodo[m["metodo"]]["cobros"] += m["monto"]
    for s in salidas:
        clave = "mercadopago" if s["metodo"] == "mercadopago" else "manual"
        por_metodo[clave]["devoluciones"] += s["monto"]
    cobros = sum(m["monto"] for m in ingresos)
    devoluciones = sum(s["monto"] for s in salidas)
    comisiones = sum(m["comision"] or 0 for m in ingresos)
    sin_comision = sum(1 for m in ingresos if m["metodo"] == "mercadopago" and m["comision"] is None)
    no_conc = [m for m in ingresos if not m["conciliado"]]
    return {
        "cobros": round(cobros, 2),
        "transferencias_verificadas": round(sum(m["monto"] for m in ingresos if m["metodo"] == "transferencia"), 2),
        "mercadopago": round(sum(m["monto"] for m in ingresos if m["metodo"] == "mercadopago"), 2),
        "devoluciones": round(devoluciones, 2),
        "comisiones": round(comisiones, 2),
        "pagos_mp_sin_comision": sin_comision,
        "neto": round(cobros - devoluciones - comisiones, 2),
        "sin_conciliar": {"cantidad": len(no_conc), "monto": round(sum(m["monto"] for m in no_conc), 2)},
        "conciliado": round(sum(m["monto"] for m in ingresos if m["conciliado"]), 2),
        "por_metodo": {k: {kk: round(vv, 2) for kk, vv in v.items()} for k, v in por_metodo.items()},
        "cantidad_cobros": len(ingresos),
        "cantidad_devoluciones": len(salidas),
    }


def caja(db: Session, desde: dt.date, hasta: dt.date) -> dict:
    if hasta < desde:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La fecha de fin es anterior a la de inicio.")
    previos_in, previos_out = _movimientos(db, None, desde - dt.timedelta(days=1))
    inicial = _totales(previos_in, previos_out)["neto"]
    ingresos, salidas = _movimientos(db, desde, hasta)
    tot = _totales(ingresos, salidas)
    cierre = db.scalar(
        select(CierreCajaSaas).where(
            CierreCajaSaas.desde == desde, CierreCajaSaas.hasta == hasta, CierreCajaSaas.estado != "anulado"
        )
    )
    diferencias = None
    if cierre is not None and cierre.estado == "cerrado":
        guardado = cierre.totales or {}
        diferencias = {
            k: round(tot[k] - _f(guardado.get(k)), 2)
            for k in ("cobros", "devoluciones", "comisiones", "neto")
            if abs(tot[k] - _f(guardado.get(k))) > 0.009
        } or None
    return {
        "desde": desde.isoformat(),
        "hasta": hasta.isoformat(),
        "saldo_inicial": round(inicial, 2),
        "totales": tot,
        "saldo_final": round(inicial + tot["neto"], 2),
        "es_calculado": True,
        "ingresos": sorted(ingresos, key=lambda m: m["fecha"]),
        "devoluciones": sorted(salidas, key=lambda m: m["fecha"]),
        "cierre": _cierre_dict(cierre) if cierre else None,
        "diferencias_con_cierre": diferencias,
    }


# ── Cierres ───────────────────────────────────────────────────────────────

def _cierre_dict(c: CierreCajaSaas) -> dict:
    return {
        "id": c.id, "desde": c.desde.isoformat(), "hasta": c.hasta.isoformat(), "estado": c.estado,
        "totales": c.totales, "observaciones": c.observaciones,
        "preparado_por": c.preparado_por, "preparado_en": c.preparado_en.isoformat() if c.preparado_en else None,
        "cerrado_por": c.cerrado_por, "cerrado_en": c.cerrado_en.isoformat() if c.cerrado_en else None,
        "reabierto_por": c.reabierto_por, "reabierto_en": c.reabierto_en.isoformat() if c.reabierto_en else None,
        "motivo_reapertura": c.motivo_reapertura,
    }


def listar_cierres(db: Session) -> list[dict]:
    return [_cierre_dict(c) for c in db.scalars(select(CierreCajaSaas).order_by(CierreCajaSaas.desde.desc()))]


def _snapshot(db: Session, desde: dt.date, hasta: dt.date) -> dict:
    datos = caja(db, desde, hasta)
    return {**datos["totales"], "saldo_inicial": datos["saldo_inicial"], "saldo_final": datos["saldo_final"]}


def preparar_cierre(db: Session, desde: dt.date, hasta: dt.date, observaciones: str | None, admin, request=None) -> dict:
    if hasta < desde:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La fecha de fin es anterior a la de inicio.")
    if hasta >= _hoy():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Solo se cierran períodos que ya terminaron.")
    vigente = db.scalar(
        select(CierreCajaSaas).where(
            CierreCajaSaas.estado.in_(("borrador", "cerrado", "reabierto")),
            CierreCajaSaas.desde <= hasta, CierreCajaSaas.hasta >= desde,
        )
    )
    if vigente is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Ya hay un cierre ({vigente.estado}) del {vigente.desde:%d/%m} al {vigente.hasta:%d/%m} que se superpone.",
        )
    quien = getattr(admin, "email", None) or str(admin)
    c = CierreCajaSaas(
        desde=desde, hasta=hasta, estado="borrador", totales=_snapshot(db, desde, hasta),
        observaciones=(observaciones or "").strip() or None, preparado_por=quien,
    )
    db.add(c)
    audit.auditar(db, admin, "cierre_preparado", descripcion=f"Preparó el cierre {desde:%d/%m/%Y}–{hasta:%d/%m/%Y}",
                  request=request)
    db.commit()
    return _cierre_dict(c)


def confirmar_cierre(db: Session, cierre_id: int, observaciones: str | None, admin, request=None) -> dict:
    c = db.scalar(select(CierreCajaSaas).where(CierreCajaSaas.id == cierre_id).with_for_update())
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ese cierre no existe.")
    if c.estado not in ("borrador", "reabierto"):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ese cierre ya está cerrado o anulado.")
    quien = getattr(admin, "email", None) or str(admin)
    c.totales = _snapshot(db, c.desde, c.hasta)  # lo que hay al momento de cerrar
    if observaciones is not None:
        c.observaciones = observaciones.strip() or None
    c.estado = "cerrado"
    c.cerrado_por = quien
    c.cerrado_en = dt.datetime.now(dt.timezone.utc)
    audit.auditar(db, admin, "cierre_confirmado",
                  descripcion=f"Cerró la caja {c.desde:%d/%m/%Y}–{c.hasta:%d/%m/%Y}: neto {c.totales.get('neto')}",
                  request=request)
    db.commit()
    return _cierre_dict(c)


def reabrir_cierre(db: Session, cierre_id: int, motivo: str, admin, request=None) -> dict:
    motivo = (motivo or "").strip()
    if len(motivo) < 4:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Escribí por qué se reabre el cierre.")
    c = db.scalar(select(CierreCajaSaas).where(CierreCajaSaas.id == cierre_id).with_for_update())
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ese cierre no existe.")
    if c.estado != "cerrado":
        raise HTTPException(status.HTTP_409_CONFLICT, "Solo se reabre un cierre cerrado.")
    quien = getattr(admin, "email", None) or str(admin)
    c.estado = "reabierto"
    c.reabierto_por = quien
    c.reabierto_en = dt.datetime.now(dt.timezone.utc)
    c.motivo_reapertura = motivo[:300]
    audit.auditar(db, admin, "cierre_reabierto",
                  descripcion=f"Reabrió el cierre {c.desde:%d/%m/%Y}–{c.hasta:%d/%m/%Y}: {motivo[:150]}",
                  antes={"totales": c.totales}, request=request)
    db.commit()
    return _cierre_dict(c)


def anular_borrador(db: Session, cierre_id: int, admin, request=None) -> dict:
    c = db.get(CierreCajaSaas, cierre_id)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ese cierre no existe.")
    if c.estado != "borrador":
        raise HTTPException(status.HTTP_409_CONFLICT, "Solo se descarta un borrador. Un cierre cerrado se reabre.")
    c.estado = "anulado"
    audit.auditar(db, admin, "cierre_descartado", descripcion=f"Descartó el borrador {c.desde:%d/%m}–{c.hasta:%d/%m}",
                  request=request)
    db.commit()
    return _cierre_dict(c)


# ── Estadísticas ──────────────────────────────────────────────────────────

def _inicio_bucket(d: dt.date, granularidad: str) -> dt.date:
    if granularidad == "semana":
        return d - dt.timedelta(days=d.weekday())
    return d.replace(day=1)


def _siguiente(d: dt.date, granularidad: str) -> dt.date:
    if granularidad == "semana":
        return d + dt.timedelta(days=7)
    return (d.replace(day=28) + dt.timedelta(days=4)).replace(day=1)


def estadisticas(db: Session, granularidad: str, desde: dt.date, hasta: dt.date) -> dict:
    if granularidad not in ("semana", "mes"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La granularidad es «semana» o «mes».")
    if hasta < desde:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La fecha de fin es anterior a la de inicio.")

    def vacio():
        return {"bruto": 0.0, "devoluciones": 0.0, "comisiones": 0.0, "neto": 0.0, "cobros": 0,
                "renovaciones": 0, "altas": 0, "pendientes": 0, "rechazados": 0, "cancelaciones": 0}

    def serie(d0: dt.date, d1: dt.date) -> tuple[dict[dt.date, dict], dict]:
        buckets: dict[dt.date, dict] = {}
        b = _inicio_bucket(d0, granularidad)
        while b <= d1:
            buckets[b] = vacio()
            b = _siguiente(b, granularidad)

        def poner(fecha: dt.date | None, clave: str, valor: float = 1):
            if fecha is None or fecha < d0 or fecha > d1:
                return
            buckets[_inicio_bucket(fecha, granularidad)][clave] += valor

        ingresos, salidas = _movimientos(db, d0, d1)
        pagos = {p.id: p for p in db.scalars(select(PagoSuscripcion).where(
            PagoSuscripcion.id.in_([m["pago_id"] for m in ingresos] or [0])))}
        for m in ingresos:
            f = dt.date.fromisoformat(m["fecha"])
            poner(f, "bruto", m["monto"])
            poner(f, "comisiones", m["comision"] or 0)
            poner(f, "cobros")
            tipo = pagos[m["pago_id"]].tipo
            if tipo == "renovacion":
                poner(f, "renovaciones")
            elif tipo == "alta":
                poner(f, "altas")
        for s in salidas:
            poner(dt.date.fromisoformat(s["fecha"]), "devoluciones", s["monto"])
        for a in db.scalars(select(AvisoPago)):
            dia = _dia(a.creado_en)
            if a.estado in ("pendiente", "info_solicitada"):
                poner(dia, "pendientes")
            elif a.estado == "rechazada":
                poner(dia, "rechazados")
        for i in db.scalars(select(IntentoPago)):
            dia = _dia(i.creado_en)
            if i.estado in ("iniciado", "pendiente"):
                poner(dia, "pendientes")
            elif i.estado == "rechazado":
                poner(dia, "rechazados")
        for aj in db.scalars(select(AjusteSuscripcion).where(AjusteSuscripcion.tipo == "cancelada")):
            poner(_dia(aj.creado_en), "cancelaciones")
        tot = vacio()
        for v in buckets.values():
            v["neto"] = round(v["bruto"] - v["devoluciones"] - v["comisiones"], 2)
            for k in v:
                tot[k] += v[k]
        tot = {k: round(v, 2) if isinstance(v, float) else v for k, v in tot.items()}
        return buckets, tot

    buckets, total = serie(desde, hasta)
    largo = (hasta - desde).days + 1
    _, anterior = serie(desde - dt.timedelta(days=largo), desde - dt.timedelta(days=1))

    def variacion(a: float, b: float) -> float | None:
        return None if not b else round((a - b) / abs(b) * 100, 1)

    activas = _contar_activas(db)
    return {
        "granularidad": granularidad,
        "desde": desde.isoformat(),
        "hasta": hasta.isoformat(),
        "serie": [
            {"periodo": k.isoformat(), **{kk: round(vv, 2) if isinstance(vv, float) else vv for kk, vv in v.items()}}
            for k, v in sorted(buckets.items())
        ],
        "total": total,
        "anterior": anterior,
        "variacion": {k: variacion(total[k], anterior[k]) for k in ("bruto", "neto", "devoluciones", "cobros")},
        "suscripciones_activas_hoy": activas,
        "definiciones": DEFINICIONES,
    }


DEFINICIONES = {
    "bruto": "Pagos acreditados, por fecha de acreditación. No incluye los anulados por corrección.",
    "devoluciones": "Devoluciones aprobadas, por la fecha en que se confirmaron. Las pedidas o en proceso no restan.",
    "comisiones": "Comisión que informó Mercado Pago al acreditar. Las transferencias no tienen.",
    "neto": "Bruto − devoluciones − comisiones. Es un cálculo con los registros del sistema, no el saldo del banco.",
    "pendientes": "Transferencias informadas en revisión e intentos de Mercado Pago sin terminar, por fecha de creación. No es plata cobrada.",
    "rechazados": "Transferencias rechazadas y pagos de Mercado Pago rechazados, por fecha de creación.",
    "renovaciones": "Pagos acreditados de tipo renovación.",
    "altas": "Primer pago de un negocio.",
    "cancelaciones": "Suscripciones cuya cancelación se hizo efectiva en el período.",
    "suscripciones_activas_hoy": "Foto de hoy (no hay historia día por día del estado).",
}


def _contar_activas(db: Session) -> int:
    from app.services.suscripcion import estado_suscripcion

    # Las que hoy están pagas o en un estado que todavía da servicio por un
    # pago (gracia, revisión, cancelación programada). La prueba no cuenta.
    activos = ("activa", "sin_vencimiento", "pendiente_pago", "en_revision", "prorroga", "cancelacion_programada")
    n = 0
    for e in db.scalars(select(Empresa).where(Empresa.activa.is_(True))):
        try:
            if estado_suscripcion(e, db)["estado"] in activos:
                n += 1
        except Exception:
            continue
    return n


# ── CSV ───────────────────────────────────────────────────────────────────

def _celda(v) -> str:
    """Neutraliza fórmulas: una celda que empieza con = + - @ (o tab/CR) la
    ejecuta Excel. Se antepone un apóstrofo."""
    s = "" if v is None else str(v)
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
        # Los números negativos sí quedan como números.
        try:
            float(s)
            return s
        except ValueError:
            return "'" + s
    return s


def a_csv(filas: list[dict], columnas: list[tuple[str, str]]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow([t for _, t in columnas])
    for f in filas:
        w.writerow([_celda(f.get(k)) for k, _ in columnas])
    return "﻿" + buf.getvalue()  # BOM: Excel abre bien los acentos


COLUMNAS_OPERACIONES = [
    ("clave", "Id interno"), ("fecha", "Fecha"), ("acreditado_en", "Acreditado"), ("empresa", "Empresa"),
    ("concepto", "Concepto"), ("metodo", "Método"), ("estado_etiqueta", "Estado"), ("monto", "Importe"),
    ("moneda", "Moneda"), ("devuelto", "Devuelto"), ("comision", "Comisión"), ("id_proveedor", "Id proveedor"),
    ("referencia", "Referencia"), ("conciliado", "Conciliado"),
]
COLUMNAS_ESTADISTICAS = [
    ("periodo", "Período"), ("bruto", "Bruto"), ("devoluciones", "Devoluciones"), ("comisiones", "Comisiones"),
    ("neto", "Neto"), ("cobros", "Cobros"), ("renovaciones", "Renovaciones"), ("altas", "Altas"),
    ("pendientes", "Pendientes"), ("rechazados", "Rechazados"), ("cancelaciones", "Cancelaciones"),
]


# ── Mercado Pago: estado de la integración ────────────────────────────────

def estado_mp(db: Session) -> dict:
    """Lo que se puede afirmar con datos, y lo que falta comprobar."""
    from app.core.config import settings as s

    token = s.mp_saas_access_token or ""
    if not token:
        entorno = None
    elif token.startswith("TEST-"):
        entorno = "pruebas"
    else:
        # APP_USR- lo usan tanto producción como los usuarios de prueba: no
        # se puede saber solo mirando el token.
        entorno = "produccion_o_usuario_de_prueba"
    ultimo = db.scalar(select(EventoMP).order_by(EventoMP.recibido_en.desc()).limit(1))
    ultimo_ok = db.scalar(
        select(EventoMP).where(EventoMP.resultado == "procesado").order_by(EventoMP.recibido_en.desc()).limit(1)
    )
    hace7 = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=7)
    errores = list(db.scalars(
        select(EventoMP).where(EventoMP.resultado.in_(("error", "firma_invalida")), EventoMP.recibido_en >= hace7)
        .order_by(EventoMP.recibido_en.desc()).limit(10)
    ))
    hace1 = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=24)
    pendientes = db.scalar(
        select(func.count(IntentoPago.id)).where(
            IntentoPago.estado.in_(("iniciado", "pendiente")), IntentoPago.creado_en < hace1
        )
    ) or 0
    sin_conciliar = db.scalar(
        select(func.count(PagoSuscripcion.id)).where(
            PagoSuscripcion.metodo == "mercadopago", PagoSuscripcion.anulado.is_(False),
            PagoSuscripcion.conciliado.is_(False),
        )
    ) or 0
    devs_abiertas = db.scalar(
        select(func.count(DevolucionSuscripcion.id)).where(
            DevolucionSuscripcion.metodo == "mercadopago",
            DevolucionSuscripcion.estado.in_(("solicitada", "en_proceso")),
        )
    ) or 0

    def ev(e: EventoMP | None):
        return None if e is None else {
            "recibido_en": e.recibido_en.isoformat(), "tipo": e.tipo, "accion": e.accion,
            "resultado": e.resultado, "detalle": e.detalle,
        }

    falta = []
    if not token:
        falta.append("Cargar MP_SAAS_ACCESS_TOKEN (cuenta de Turnos360).")
    if not s.mp_saas_webhook_secret:
        falta.append("Cargar MP_SAAS_WEBHOOK_SECRET para validar la firma de los avisos.")
    if token and ultimo is None:
        falta.append("Todavía no llegó ningún aviso al webhook: hacer un pago de prueba y ver que aparezca acá.")
    if token and ultimo_ok is None:
        falta.append("Ningún aviso se procesó todavía: no está comprobado de punta a punta.")
    if s.mp_firma_modo != "enforce":
        falta.append(f"La firma está en modo «{s.mp_firma_modo}»: pasar a «enforce» después de verla cerrar con tráfico real.")
    return {
        "configurado": bool(token),
        "entorno": entorno,
        "webhook_secreto": bool(s.mp_saas_webhook_secret),
        "firma_modo": s.mp_firma_modo,
        "webhook_url": f"{s.api_base_url.rstrip('/')}/publico/mp/webhook-suscripcion",
        "ultimo_evento": ev(ultimo),
        "ultimo_procesado": ev(ultimo_ok),
        "errores_recientes": [ev(e) for e in errores],
        "intentos_pendientes_24h": int(pendientes),
        "pagos_mp_sin_conciliar": int(sin_conciliar),
        "devoluciones_abiertas": int(devs_abiertas),
        "comprobado": bool(token and ultimo_ok is not None),
        "falta_comprobar": falta,
    }


# ── Resumen general ───────────────────────────────────────────────────────

def resumen_general(db: Session, desde: dt.date, hasta: dt.date) -> dict:
    from app.services.suscripcion import estado_suscripcion

    empresas = list(db.scalars(select(Empresa)))
    estados: dict[str, int] = defaultdict(int)
    por_vencer = 0
    hoy = _hoy()
    for e in empresas:
        if not e.activa:
            continue
        try:
            est = estado_suscripcion(e, db)["estado"]
        except Exception:
            est = "desconocido"
        estados[est] += 1
        if e.suscripcion_vence and hoy <= e.suscripcion_vence <= hoy + dt.timedelta(days=7):
            por_vencer += 1
    datos = caja(db, desde, hasta)
    t = datos["totales"]
    ops = operaciones(db, desde=desde, hasta=hasta, limite=1)
    en_revision = db.scalar(select(func.count(AvisoPago.id)).where(AvisoPago.estado.in_(("pendiente", "info_solicitada")))) or 0
    devs_pend = db.scalars(select(DevolucionSuscripcion).where(DevolucionSuscripcion.estado.in_(("solicitada", "en_proceso"))))
    devs_pend = list(devs_pend)
    stats = estadisticas(db, "semana", max(desde, hasta - dt.timedelta(days=7 * 12 - 1)), hasta)
    alertas = []
    if en_revision:
        alertas.append({"tipo": "aviso", "texto": f"{en_revision} transferencia(s) esperando revisión", "href": "/admin/cobranza"})
    if devs_pend:
        alertas.append({"tipo": "aviso", "texto": f"{len(devs_pend)} devolución(es) sin confirmar", "href": "/admin/cobros?estado=reembolso_solicitado"})
    if t["sin_conciliar"]["cantidad"]:
        alertas.append({"tipo": "info", "texto": f"{t['sin_conciliar']['cantidad']} cobro(s) del período sin conciliar", "href": "/admin/caja"})
    mp_estado = estado_mp(db)
    if mp_estado["errores_recientes"]:
        alertas.append({"tipo": "error", "texto": "Errores recientes en el webhook de Mercado Pago", "href": "/admin/integraciones"})
    if por_vencer:
        alertas.append({"tipo": "info", "texto": f"{por_vencer} suscripción(es) vencen en los próximos 7 días", "href": "/admin/cobranza"})
    return {
        "desde": desde.isoformat(),
        "hasta": hasta.isoformat(),
        "empresas": {
            "total": len(empresas),
            "activas": sum(1 for e in empresas if e.activa),
            "inactivas": sum(1 for e in empresas if not e.activa),
        },
        "suscripciones": {"por_estado": dict(estados), "activas": _contar_activas(db), "por_vencer_7d": por_vencer},
        "periodo": {
            "acreditado": t["cobros"], "cantidad_cobros": t["cantidad_cobros"],
            "devoluciones": t["devoluciones"], "comisiones": t["comisiones"], "neto": t["neto"],
            "en_revision": ops["sumas"]["en_revision"], "pendiente": ops["sumas"]["pendiente"],
            "rechazado": ops["sumas"]["rechazado"],
        },
        "transferencias_en_revision": int(en_revision),
        "devoluciones_pendientes": {"cantidad": len(devs_pend), "monto": round(sum(_f(d.monto) for d in devs_pend), 2)},
        "serie_semanal": stats["serie"],
        "alertas": alertas,
    }


# ── Planes ────────────────────────────────────────────────────────────────

def planes(db: Session) -> list[dict]:
    from app.core import planes as cp
    from app.services.suscripcion import estado_suscripcion

    conteo: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for e in db.scalars(select(Empresa).where(Empresa.activa.is_(True))):
        try:
            est = estado_suscripcion(e, db)["estado"]
        except Exception:
            est = "desconocido"
        conteo[e.plan or "sin_plan"][est] += 1
    salida = []
    for p in cp.Plan:
        lim = cp.limites_de(p.value)
        salida.append({
            "codigo": p.value,
            "etiqueta": lim.etiqueta,
            "precio": float(lim.precio) if lim.precio is not None else None,
            "profesionales": lim.profesionales,
            "usuarios": lim.usuarios,
            "sucursales": lim.sucursales,
            "se_vende_solo": cp.se_vende_solo(p),
            "funciones": sorted(f.value for f in lim.funciones),
            "empresas": sum(conteo[p.value].values()),
            "por_estado": dict(conteo[p.value]),
        })
    return salida
