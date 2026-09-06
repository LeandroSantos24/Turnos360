"""La ficha completa de un negocio: todo lo que hace falta para decidir.

QUÉ PROBLEMA RESUELVE
─────────────────────
El panel de admin listaba nombre, rubro, slug, usuarios y vencimiento. Con eso
se puede saber que una empresa existe, y nada más. Para cualquier pregunta real
—¿está pagando?, ¿le está yendo bien?, ¿lo usa?, ¿le queda chico el plan?—
había que cruzar tres pantallas o entrar a la base.

Esto junta en una sola respuesta las cuatro cosas que contestan esas preguntas:

  IDENTIDAD   quién es, desde cuándo, en qué plan
  COBRANZA    si pagó, cuándo vence, cuánto lleva pagado, si avisó algo
  USO         cuánto de lo que compró está usando, y si se le está quedando chico
  ACTIVIDAD   si el sistema lo usa alguien: turnos, clientes, visitas

POR QUÉ TODO JUNTO Y NO CUATRO LLAMADAS
───────────────────────────────────────
Porque la pregunta es una sola —«¿cómo está este cliente?»— y las respuestas
parciales invitan a sacar conclusiones con la mitad de los datos. Un negocio al
día que hace tres meses no carga un turno no es un buen cliente: es uno que se
va a ir, y eso solo se ve mirando la cobranza y el uso al mismo tiempo.
"""

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import planes
from app.core.reloj import hoy_de_pared
from app.models import (
    Cliente,
    Empresa,
    PagoSuscripcion,
    Recurso,
    Rubro,
    Sucursal,
    Usuario,
)
from app.models.agenda import Servicio
from app.models.turno import Turno
from app.services import cobranza, visitas
from app.services.suscripcion import cuota_de, estado_suscripcion


def _contar(db: Session, modelo, empresa_id: int, *extra) -> int:
    return int(
        db.scalar(
            select(func.count(modelo.id)).where(modelo.empresa_id == empresa_id, *extra)
        )
        or 0
    )


def ficha(db: Session, empresa: Empresa) -> dict:
    hoy = hoy_de_pared()
    lim = planes.limites_de(empresa.plan)
    est = estado_suscripcion(empresa)
    sem = cobranza.semaforo_de(empresa, hoy)

    # ── Uso: lo que compró contra lo que usa ──────────────────────────
    profesionales = _contar(
        db, Recurso, empresa.id, Recurso.activo.is_(True), Recurso.tipo == "persona"
    )
    usuarios = _contar(db, Usuario, empresa.id, Usuario.activo.is_(True))
    sucursales = _contar(db, Sucursal, empresa.id)

    # Los topes de la ficha comercial PISAN a los del plan: es como se arma un
    # Enterprise a medida. Mostrar el del plan cuando hay un override haría que
    # el panel diga «8» sobre un cliente al que le vendimos 40.
    tope_prof = empresa.limite_recursos if empresa.limite_recursos else lim.profesionales
    tope_suc = empresa.limite_sucursales if empresa.limite_sucursales else lim.sucursales
    tope_usu = planes.tope_usuarios(planes.plan_de(empresa.plan))

    # ── Actividad: ¿lo usa alguien? ───────────────────────────────────
    hace_30 = hoy - dt.timedelta(days=30)
    turnos_mes = int(
        db.scalar(
            select(func.count(Turno.id)).where(
                Turno.empresa_id == empresa.id,
                func.date(Turno.fecha_inicio) >= hace_30,
            )
        )
        or 0
    )
    ultimo_turno = db.scalar(
        select(func.max(Turno.fecha_inicio)).where(Turno.empresa_id == empresa.id)
    )

    # ── Cobranza ──────────────────────────────────────────────────────
    pagos = list(
        db.scalars(
            select(PagoSuscripcion)
            .where(
                PagoSuscripcion.empresa_id == empresa.id,
                PagoSuscripcion.anulado.is_(False),
            )
            .order_by(PagoSuscripcion.fecha.desc())
        ).all()
    )
    aviso = cobranza.aviso_pendiente(db, empresa.id)
    rubro = db.get(Rubro, empresa.rubro_id) if empresa.rubro_id else None

    cuota, origen = cuota_de(empresa)


    return {
        "id": empresa.id,
        "nombre": empresa.nombre,
        "slug": empresa.slug,
        "rubro": rubro.nombre if rubro else None,
        "activa": bool(empresa.activa),
        "creada_en": empresa.creada_en.isoformat() if empresa.creada_en else None,
        # Cuántos días lleva con nosotros. Es el número que convierte «se dio de
        # alta el 3/9» en «lleva 2 días»: distinto trato merece uno de 2 días
        # que uno de 8 meses.
        "antiguedad_dias": (
            (hoy - empresa.creada_en.date()).days if empresa.creada_en else None
        ),
        "plan": {
            "codigo": planes.plan_de(empresa.plan).value,
            "etiqueta": lim.etiqueta,
            "resumen": lim.resumen,
            # El pactado manda: para eso existe la columna. Y si no hay
            # pactado sale de la grilla — nunca de una foto guardada en la
            # fila, que es lo que envejecía solo. Ver suscripcion.cuota_de.
            "precio": cuota,
            "precio_pactado": origen == "pactada",
        },
        "suscripcion": {
            "estado": est["estado"],
            "vence": est["vence"],
            "prueba_hasta": str(empresa.prueba_hasta) if empresa.prueba_hasta else None,
            "color": sem["color"],
            "detalle": sem["detalle"],
            "dias_restantes": sem["dias_restantes"],
            "en_prorroga": sem["en_prorroga"],
        },
        "cobranza": {
            "pagos": len(pagos),
            "total_cobrado": sum(float(p.monto) for p in pagos),
            "ultimo_pago": (
                {
                    "fecha": str(pagos[0].fecha),
                    "monto": float(pagos[0].monto),
                    "metodo": pagos[0].metodo,
                }
                if pagos
                else None
            ),
            # Un aviso pendiente es lo primero que hay que ver: significa que
            # el negocio ya hizo su parte y está esperando.
            "aviso_pendiente": (
                {
                    "id": aviso.id,
                    "monto": float(aviso.monto) if aviso.monto is not None else None,
                    "referencia": aviso.referencia,
                    "creado_en": aviso.creado_en.isoformat() if aviso.creado_en else None,
                }
                if aviso
                else None
            ),
        },
        "uso": {
            "profesionales": {"usados": profesionales, "tope": tope_prof},
            "usuarios": {"usados": usuarios, "tope": tope_usu},
            "sucursales": {"usados": sucursales, "tope": tope_suc},
            "clientes": _contar(db, Cliente, empresa.id),
            "servicios": _contar(db, Servicio, empresa.id, Servicio.activo.is_(True)),
        },
        "actividad": {
            "turnos_30d": turnos_mes,
            "ultimo_turno": ultimo_turno.isoformat() if ultimo_turno else None,
            # Visitas a la vidriera: si nadie la abre, el problema del negocio
            # no es Turnos360 y conviene saberlo antes de que nos lo diga.
            "visitas_30d": visitas.total(db, empresa.id, 30),
            "visitas_por_dia": visitas.por_dia(db, empresa.id, 30),
        },
        "contacto": {
            "nombre": empresa.contacto_nombre,
            "email": empresa.contacto_email,
            "telefono": empresa.contacto_telefono,
            "razon_social": empresa.razon_social,
            "cuit": empresa.cuit,
        },
        "notas_admin": empresa.notas_admin,
    }
