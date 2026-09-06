"""Cuántas veces se abre la página pública de cada negocio.

PARA QUÉ SIRVE
──────────────
Lo preguntó Leandro mirando el panel de admin: «¿se puede medir tráfico de su
landing?». No se medía. Y es de los datos que hay que empezar a juntar ANTES de
necesitarlos: un contador recién dice algo cuando acumuló semanas, así que cada
día sin contar es un día que después no se puede recuperar.

Sirve para dos cosas concretas: saber si a un negocio le está llegando gente
—si su vidriera no la abre nadie, el problema no es Turnos360— y ver la
tendencia antes de que un cliente se vaya. Una vidriera que pasó de 200 visitas
mensuales a 20 avisa con un mes de anticipación.

QUÉ NO GUARDA
─────────────
Nada del visitante. Ni IP, ni cookie, ni user-agent, ni referrer. Un número por
empresa y por día, y listo. Todo lo que se guarde de más es algo que después
hay que cuidar, explicar y borrar — y no hace falta para responder la pregunta.
"""

import logging

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.reloj import hoy_de_pared
from app.models import VisitaVidriera

log = logging.getLogger("turnos360.visitas")


def registrar_por_slug(db: Session, slug: str) -> None:
    """Suma uno al contador de hoy, resolviendo la empresa por su slug.

    UNA sola consulta: el INSERT saca el empresa_id de un SELECT sobre empresa,
    en la misma sentencia. La alternativa —buscar el id y después insertar— son
    dos viajes a la base en el endpoint público MÁS golpeado del sistema, para
    guardar un número. Y si el slug no existe, el SELECT no devuelve filas y el
    INSERT no inserta nada: no hace falta preguntar antes.
    """
    try:
        db.execute(
            text(
                """
                INSERT INTO visita_vidriera (empresa_id, dia, visitas)
                SELECT id, :dia, 1 FROM empresa WHERE slug = :slug
                ON CONFLICT ON CONSTRAINT uq_visita_empresa_dia
                DO UPDATE SET visitas = visita_vidriera.visitas + 1
                """
            ),
            {"dia": hoy_de_pared(), "slug": slug},
        )
        db.commit()
    except Exception:
        db.rollback()
        log.warning("no se pudo contar la visita de %s", slug, exc_info=True)


def registrar(db: Session, empresa_id: int) -> None:
    """Suma uno al contador de hoy. NUNCA levanta.

    Se llama desde la vidriera pública, que es la pantalla que ve el cliente
    del negocio. Si contar una visita fallara y esa excepción subiera, la
    página no cargaría — y estaríamos rompiendo una reserva real por una
    estadística. Un contador es exactamente el tipo de cosa que puede fallar
    en silencio.

    El UPSERT hace el trabajo en UNA consulta y sin condición de carrera. Con
    un SELECT y después un INSERT, dos visitas simultáneas leen «no hay fila»,
    las dos insertan, y una explota contra el único. Con
    `ON CONFLICT DO UPDATE` la base resuelve el empate.
    """
    try:
        db.execute(
            insert(VisitaVidriera)
            .values(empresa_id=empresa_id, dia=hoy_de_pared(), visitas=1)
            .on_conflict_do_update(
                constraint="uq_visita_empresa_dia",
                set_={"visitas": VisitaVidriera.visitas + 1},
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        log.warning("no se pudo contar la visita de %s", empresa_id, exc_info=True)


def por_dia(db: Session, empresa_id: int, dias: int = 30) -> list[dict]:
    """Las visitas de los últimos `dias`, del más viejo al más nuevo.

    Los días SIN visitas no están en la base (no hay fila) y se rellenan en
    cero: un gráfico que saltea los días vacíos miente sobre la tendencia —
    dibuja una línea plana donde hubo una caída.
    """
    import datetime as dt

    hoy = hoy_de_pared()
    desde = hoy - dt.timedelta(days=dias - 1)

    filas = {
        f.dia: f.visitas
        for f in db.scalars(
            select(VisitaVidriera).where(
                VisitaVidriera.empresa_id == empresa_id,
                VisitaVidriera.dia >= desde,
            )
        ).all()
    }
    return [
        {"dia": (desde + dt.timedelta(days=i)).isoformat(),
         "visitas": int(filas.get(desde + dt.timedelta(days=i), 0))}
        for i in range(dias)
    ]


def total(db: Session, empresa_id: int, dias: int = 30) -> int:
    return sum(d["visitas"] for d in por_dia(db, empresa_id, dias))
