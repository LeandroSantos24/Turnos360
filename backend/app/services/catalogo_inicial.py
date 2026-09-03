"""Los servicios con los que nace una empresa, según su rubro.

EL PROBLEMA
───────────
El alta dejaba el negocio con la aplicación bien nombrada —"paciente" en vez de
"cliente", "sesión" en vez de "turno"— y absolutamente vacía. Sin servicios no
hay nada que agendar, la página pública no muestra nada para reservar y la
agenda tiene una sola columna. El primer paso real seguía siendo una pantalla
en blanco con un botón «Nuevo servicio», y ahí es donde la gente abandona: no
porque sea difícil, sino porque es trabajo antes de haber visto que la cosa
sirve.

LO QUE SE SIEMBRA
─────────────────
Los tres a cinco servicios que ese rubro usa siempre, con duración, precio de
referencia y carril de agenda (ver `app/presets.py`). El dueño entra, ve su
agenda con los carriles ya armados, corrige los precios mirando su lista y en
cinco minutos está reservando.

SON UN PUNTO DE PARTIDA, NO UNA IMPOSICIÓN
──────────────────────────────────────────
Se editan, se borran y se agregan los propios desde Servicios como cualquier
otro. No quedan marcados de ninguna forma ni tienen un trato especial: una vez
creados son servicios comunes.

QUÉ NO HACE
───────────
No pisa nada. Si la empresa ya tiene aunque sea un servicio cargado, no toca
nada — ni siquiera para completar los que falten. Un negocio que ya empezó a
cargar su catálogo no quiere que le aparezcan cuatro servicios ajenos entre los
suyos; el sembrado es para el alta y solo para el alta.
"""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Empresa, Rubro
from app.models.agenda import Servicio

log = logging.getLogger("turnos360.catalogo")


def sembrar(db: Session, empresa_id: int) -> list[Servicio]:
    """Crea los servicios del preset del rubro. NO hace commit.

    Devuelve los creados (vacío si la empresa ya tenía catálogo o si el rubro
    no define servicios).

    No commitea porque se llama desde el alta, que commitea una sola vez al
    final: si esto commiteara por su cuenta, un error posterior dejaría una
    empresa a medio crear pero con su catálogo, que es exactamente el registro
    huérfano que el resto del alta se cuida de no dejar.
    """
    ya_tiene = db.scalar(
        select(Servicio.id).where(Servicio.empresa_id == empresa_id).limit(1)
    )
    if ya_tiene is not None:
        return []

    empresa = db.get(Empresa, empresa_id)
    if empresa is None:
        return []

    rubro = db.get(Rubro, empresa.rubro_id) if empresa.rubro_id else None
    preset = dict(rubro.preset) if rubro and rubro.preset else {}
    # El config_pack de la empresa pisa al preset del rubro, igual que en
    # obtener_config: si el super-admin le armó un catálogo a medida en el
    # alta, manda el suyo.
    if empresa.config_pack:
        preset.update(empresa.config_pack)

    plantillas = preset.get("servicios") or []
    if not plantillas:
        return []

    creados: list[Servicio] = []
    for p in plantillas:
        nombre = str(p.get("nombre") or "").strip()
        if not nombre:
            continue
        servicio = Servicio(
            empresa_id=empresa_id,
            nombre=nombre[:120],
            duracion_min=int(p.get("duracion_min") or 30),
            precio=p.get("precio"),
            grupo_agenda=p.get("grupo") or None,
            paso_turno_min=int(p.get("paso_turno_min") or 15),
            activo=True,
            agendable=True,
        )
        db.add(servicio)
        creados.append(servicio)

    if creados:
        # El flush dispara el listener de ServicioSucursal, que es el que deja
        # cada servicio ofrecido en todos los locales abiertos. Sin él, los
        # servicios quedarían creados pero INVISIBLES en la página pública —y
        # un servicio invisible no da un error ruidoso, no se descubre hasta
        # que un cliente no lo encuentra.
        db.flush()
        log.info(
            "catálogo inicial sembrado",
            extra={"empresa_id": empresa_id, "servicios": len(creados)},
        )
    return creados
