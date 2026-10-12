"""Historia de las suscripciones: foto diaria, transiciones y evolución.

QUÉ HABÍA
─────────
- `ajuste_suscripcion` ya era el registro de EVENTOS: pagos, prórrogas,
  renovaciones, cambios de plan, suspensiones, cancelaciones, con estado y
  plan de antes y después, quién y cuándo. Se reusa tal cual.
- Lo que no quedaba en ningún lado son los cambios que pasan SOLOS con el
  tiempo: una cuota que vence, la gracia que se termina, una prueba que se
  acaba. El estado se calcula con fechas, así que «cuántas activas había el
  15 de agosto» no se podía saber.

QUÉ SE AGREGA
─────────────
1. `suscripcion_diaria`: una fila por empresa y por día con el estado de ese
   día. La toma `tomar_fotos()` (tarea nocturna, 23:50 hora argentina) y es
   idempotente: si ya existe la fila del día, no la toca.
2. Si la tarea no corrió algunos días (worker caído), la siguiente corrida
   completa los días que faltan desde la última foto, reconstruyendo cada día
   con los datos de hoy MENOS los ajustes registrados desde ese día. Esas filas
   quedan marcadas `origen="reconstruido"`. Antes de la primera foto no se
   completa nada: no hay de dónde sacarlo sin inventar.
3. Cuando una foto muestra un cambio que pasó solo (venció, entró o salió de
   la gracia, terminó la prueba, se hizo efectiva una baja programada), se
   anota un evento `tipo="estado"` en `ajuste_suscripcion`, actor «sistema».
   Así el historial de la empresa cuenta también lo que nadie tocó.
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from types import SimpleNamespace

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.reloj import hoy_de_pared
from app.models import AjusteSuscripcion, Empresa, SuscripcionDiaria

# Los estados que cuentan como «suscripción activa»: pagan o todavía tienen el
# servicio por un pago (gracia, revisión, baja programada). Es la misma regla
# que usa el resumen del panel. La prueba gratuita NO cuenta.
ACTIVOS = frozenset({
    "activa", "sin_vencimiento", "pendiente_pago", "en_revision", "prorroga", "cancelacion_programada",
})
# Cambios que suceden solos con el paso del tiempo (los demás tienen evento propio).
TRANSICIONES_DEL_TIEMPO = {
    ("activa", "prorroga"): "Venció la cuota: entró en el período de gracia",
    ("activa", "vencida"): "Venció la cuota",
    ("prorroga", "vencida"): "Terminó el período de gracia sin pago",
    ("prueba", "prueba_vencida"): "Terminó la prueba",
    ("cancelacion_programada", "cancelada"): "Se hizo efectiva la baja programada",
}

DEFINICIONES = {
    "activas_al_cierre": "Empresas con la suscripción activa el último día del período (activa, al día sin vencimiento, en gracia, con un pago en revisión o pendiente, o con la baja programada para más adelante). No cuenta la prueba gratuita.",
    "nuevas": "Empresas que tuvieron su primer día activo dentro del período (según las fotos diarias).",
    "reactivadas": "Empresas que volvieron a estar activas después de haber dejado de estarlo.",
    "vencimientos": "Empresas que pasaron de activas a vencidas en el período.",
    "cancelaciones": "Empresas que pasaron a «cancelada» en el período.",
    "pruebas_vencidas": "Pruebas gratuitas que terminaron sin pasar a un plan pago.",
    "cambios_de_plan": "Cambios de plan registrados en el período (por el negocio, por un pago o por administración).",
    "confiable_desde": "Fecha de la primera foto diaria. Antes de ese día no hay datos históricos y no se estiman.",
    "reconstruido": "Días que la tarea nocturna no tomó en su momento y se completaron después a partir del registro de ajustes.",
}


def _fin_del_dia_utc(d: dt.date) -> dt.datetime:
    """Último instante del día `d` en Argentina, expresado en UTC."""
    from zoneinfo import ZoneInfo

    from app.core.config import settings

    local = dt.datetime.combine(d + dt.timedelta(days=1), dt.time.min, ZoneInfo(settings.zona_horaria))
    return local.astimezone(dt.timezone.utc)


def _campos_al(empresa: Empresa, eventos_posteriores: list[AjusteSuscripcion]) -> SimpleNamespace:
    """Los datos de la empresa como estaban antes de `eventos_posteriores`.

    Se deshacen del más nuevo al más viejo: cada ajuste guarda el vencimiento
    y el plan de antes; las suspensiones y cancelaciones se invierten.
    """
    c = SimpleNamespace(
        id=empresa.id,
        plan=empresa.plan,
        suscripcion_vence=empresa.suscripcion_vence,
        prueba_hasta=empresa.prueba_hasta,
        activa=bool(empresa.activa),
        cancela_al_vencer=bool(empresa.cancela_al_vencer),
        cancelada_en=empresa.cancelada_en,
    )
    for ev in sorted(eventos_posteriores, key=lambda e: (e.creado_en, e.id), reverse=True):
        if ev.vence_antes != ev.vence_despues or ev.tipo in ("prorroga", "renovacion", "manual", "pago", "reversion"):
            c.suscripcion_vence = ev.vence_antes
        if ev.plan_antes:
            c.plan = ev.plan_antes
        if ev.tipo == "suspension":
            c.activa = True
        elif ev.tipo == "reanudacion":
            c.activa = False
        elif ev.tipo == "cancelacion":
            c.cancela_al_vencer = False
        elif ev.tipo == "reactivacion":
            c.cancela_al_vencer = True
        elif ev.tipo == "cancelada":
            c.cancelada_en = None
    return c


def _estado_reconstruido(empresa: Empresa, eventos: list[AjusteSuscripcion], dia: dt.date) -> str:
    from app.services.suscripcion import estado_suscripcion

    corte = _fin_del_dia_utc(dia)
    posteriores = [e for e in eventos if e.creado_en is not None and e.creado_en >= corte]
    return estado_suscripcion(_campos_al(empresa, posteriores), None, dia)["estado"]


def _plan_reconstruido(empresa: Empresa, eventos: list[AjusteSuscripcion], dia: dt.date) -> str | None:
    corte = _fin_del_dia_utc(dia)
    return _campos_al(empresa, [e for e in eventos if e.creado_en and e.creado_en >= corte]).plan


def primera_foto(db: Session) -> dt.date | None:
    return db.scalar(select(func.min(SuscripcionDiaria.fecha)).where(SuscripcionDiaria.origen == "foto"))


def tomar_fotos(db: Session, hoy: dt.date | None = None, *, max_dias: int = 400) -> dict:
    """Foto de hoy para cada empresa y relleno de los días que faltan.

    Idempotente: correrla dos veces el mismo día no duplica nada (clave
    primaria fecha+empresa y ON CONFLICT DO NOTHING). Hace commit.
    """
    from app.services import cobranza
    from app.services.suscripcion import estado_suscripcion

    hoy = hoy or hoy_de_pared()
    inicio_global = primera_foto(db) or hoy
    ultimas = dict(
        db.execute(select(SuscripcionDiaria.empresa_id, func.max(SuscripcionDiaria.fecha)).group_by(SuscripcionDiaria.empresa_id)).all()
    )
    nuevas = reconstruidas = transiciones = 0
    for empresa in db.scalars(select(Empresa).order_by(Empresa.id)):
        alta = (empresa.creada_en.date() if empresa.creada_en else inicio_global)
        desde = max(inicio_global, alta)
        if empresa.id in ultimas:
            desde = max(desde, ultimas[empresa.id] + dt.timedelta(days=1))
        desde = max(desde, hoy - dt.timedelta(days=max_dias))
        if desde > hoy:
            continue
        eventos = list(db.scalars(select(AjusteSuscripcion).where(AjusteSuscripcion.empresa_id == empresa.id)))
        previo = db.scalar(
            select(SuscripcionDiaria.estado)
            .where(SuscripcionDiaria.empresa_id == empresa.id, SuscripcionDiaria.fecha < desde)
            .order_by(SuscripcionDiaria.fecha.desc())
            .limit(1)
        )
        dia = desde
        while dia <= hoy:
            if dia == hoy:
                estado = estado_suscripcion(empresa, db, hoy)["estado"]
                plan, origen = empresa.plan, "foto"
            else:
                estado = _estado_reconstruido(empresa, eventos, dia)
                plan, origen = _plan_reconstruido(empresa, eventos, dia), "reconstruido"
            r = db.execute(
                insert(SuscripcionDiaria)
                .values(fecha=dia, empresa_id=empresa.id, estado=estado, plan=plan, origen=origen)
                .on_conflict_do_nothing(index_elements=["fecha", "empresa_id"])
            )
            if r.rowcount:
                if origen == "foto":
                    nuevas += 1
                else:
                    reconstruidas += 1
                motivo = TRANSICIONES_DEL_TIEMPO.get((previo, estado)) if previo else None
                if motivo:
                    cobranza.evento(
                        db, empresa, "estado", f"{motivo} (el {dia.strftime('%d/%m/%Y')})",
                        hecho_por="sistema", actor_tipo="sistema",
                        estado_antes=previo, estado_despues=estado,
                    )
                    transiciones += 1
            previo = estado
            dia += dt.timedelta(days=1)
    db.commit()
    return {"fecha": hoy.isoformat(), "fotos": nuevas, "reconstruidas": reconstruidas, "transiciones": transiciones}


# ── Evolución ─────────────────────────────────────────────────────────────

def _inicio_bucket(d: dt.date, g: str) -> dt.date:
    if g == "semana":
        return d - dt.timedelta(days=d.weekday())
    if g == "mes":
        return d.replace(day=1)
    return d


def _fin_bucket(inicio: dt.date, g: str) -> dt.date:
    if g == "semana":
        return inicio + dt.timedelta(days=6)
    if g == "mes":
        sig = (inicio.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
        return sig - dt.timedelta(days=1)
    return inicio


def _metricas(filas: list[tuple[dt.date, int, str, str]], desde: dt.date, hasta: dt.date,
              cambios_plan: list[tuple[dt.date, str | None, str | None]],
              inicio_global: dt.date | None) -> dict:
    """Transiciones en [desde, hasta] a partir de las fotos (ordenadas)."""
    por_empresa: dict[int, list[tuple[dt.date, str]]] = defaultdict(list)
    for fecha, emp, estado, _ in filas:
        por_empresa[emp].append((fecha, estado))
    m = {"nuevas": 0, "reactivadas": 0, "vencimientos": 0, "cancelaciones": 0, "pruebas_vencidas": 0}
    for serie in por_empresa.values():
        fue_activa = False
        prev = None
        for fecha, estado in serie:
            activa = estado in ACTIVOS
            dentro = desde <= fecha <= hasta
            if prev is not None and dentro:
                if activa and prev not in ACTIVOS:
                    m["reactivadas" if fue_activa else "nuevas"] += 1
                if prev in ACTIVOS and estado == "vencida":
                    m["vencimientos"] += 1
                if estado == "cancelada" and prev != "cancelada":
                    m["cancelaciones"] += 1
                if prev == "prueba" and estado == "prueba_vencida":
                    m["pruebas_vencidas"] += 1
            elif prev is None and dentro and activa and inicio_global and fecha > inicio_global:
                # Su primera foto es posterior a la primera foto general: la
                # empresa se dio de alta ese día y ya arrancó activa.
                m["nuevas"] += 1
            fue_activa = fue_activa or activa
            prev = estado
    m["cambios_de_plan"] = sum(1 for f, _, _ in cambios_plan if desde <= f <= hasta)
    return m


def evolucion(db: Session, granularidad: str, desde: dt.date, hasta: dt.date) -> dict:
    from fastapi import HTTPException, status

    if granularidad not in ("dia", "semana", "mes"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La granularidad es «dia», «semana» o «mes».")
    if hasta < desde:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La fecha de fin es anterior a la de inicio.")
    if (hasta - desde).days > 800:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El período es demasiado largo (máximo 800 días).")
    hoy = hoy_de_pared()
    confiable = primera_foto(db)
    largo = (hasta - desde).days + 1
    ant_desde, ant_hasta = desde - dt.timedelta(days=largo), desde - dt.timedelta(days=1)

    filas = db.execute(
        select(SuscripcionDiaria.fecha, SuscripcionDiaria.empresa_id, SuscripcionDiaria.estado, SuscripcionDiaria.origen)
        .where(SuscripcionDiaria.fecha <= hasta)
        .order_by(SuscripcionDiaria.empresa_id, SuscripcionDiaria.fecha)
    ).all()
    from zoneinfo import ZoneInfo

    from app.core.config import settings

    zona = ZoneInfo(settings.zona_horaria)
    cambios_plan = [
        (a.creado_en.astimezone(zona).date(), a.plan_antes, a.plan_despues)
        for a in db.scalars(
            select(AjusteSuscripcion).where(
                AjusteSuscripcion.tipo == "plan",
                AjusteSuscripcion.creado_en >= _fin_del_dia_utc(ant_desde - dt.timedelta(days=1)),
                AjusteSuscripcion.creado_en < _fin_del_dia_utc(hasta),
            )
        )
    ]
    activas_por_dia: dict[dt.date, int] = defaultdict(int)
    con_foto: set[dt.date] = set()
    reconstruidos: set[dt.date] = set()
    for fecha, _emp, estado, origen in filas:
        con_foto.add(fecha)
        if origen == "reconstruido":
            reconstruidos.add(fecha)
        if estado in ACTIVOS:
            activas_por_dia[fecha] += 1

    serie = []
    b = _inicio_bucket(desde, granularidad)
    while b <= hasta:
        ini, fin = max(b, desde), min(_fin_bucket(b, granularidad), hasta)
        cierre = min(fin, hoy)
        tiene = cierre in con_foto
        met = _metricas(filas, ini, fin, cambios_plan, confiable)
        dias_con_datos = sum(1 for k in range((fin - ini).days + 1) if ini + dt.timedelta(days=k) in con_foto)
        serie.append({
            "periodo": b.isoformat(),
            "desde": ini.isoformat(),
            "hasta": fin.isoformat(),
            "activas_al_cierre": activas_por_dia.get(cierre, 0) if tiene else None,
            **met,
            "dias_con_datos": dias_con_datos,
            "dias": (fin - ini).days + 1,
            "dias_reconstruidos": sum(1 for k in range((fin - ini).days + 1) if ini + dt.timedelta(days=k) in reconstruidos),
        })
        b = _fin_bucket(b, granularidad) + dt.timedelta(days=1)

    def totales(d0: dt.date, d1: dt.date) -> dict:
        m = _metricas(filas, d0, d1, cambios_plan, confiable)
        cierre = min(d1, hoy)
        m["activas_al_cierre"] = activas_por_dia.get(cierre) if cierre in con_foto else None
        return m

    total, anterior = totales(desde, hasta), totales(ant_desde, ant_hasta)

    def var(a, b):
        if a is None or b in (None, 0):
            return None
        return round((a - b) / b * 100, 1)

    planes = defaultdict(int)
    for f, pa, pd in cambios_plan:
        if desde <= f <= hasta:
            planes[f"{pa or '—'} → {pd or '—'}"] += 1
    return {
        "granularidad": granularidad,
        "desde": desde.isoformat(),
        "hasta": hasta.isoformat(),
        "confiable_desde": confiable.isoformat() if confiable else None,
        "serie": serie,
        "total": total,
        "anterior": anterior,
        "variacion": {k: var(total.get(k), anterior.get(k)) for k in ("activas_al_cierre", "nuevas", "vencimientos", "cancelaciones")},
        "cambios_de_plan": [{"cambio": k, "cantidad": v} for k, v in sorted(planes.items(), key=lambda x: -x[1])],
        "definiciones": DEFINICIONES,
    }
