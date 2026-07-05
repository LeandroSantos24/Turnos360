"""Capa pública (landing): vidriera, huecos y reserva SIN login, por slug.

Regla de aislamiento: acá no hay token, así que el tenant se resuelve por el
slug de la URL. resolver_empresa() es el único punto de entrada y exige que la
empresa exista y esté activa; todas las queries filtran por esa empresa.

No reinventa nada: la reserva reusa turno_service.crear() (valida el hueco con
el motor, tira 409 si choca, crea en estado PENDIENTE) y los horarios libres
salen de disponibilidad.calcular_huecos().
"""

import datetime as dt

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Cliente, Empresa, Recurso, Servicio
from app.models.enums import TipoRecurso
from app.schemas.publico import ReservaPublicaCrear
from app.schemas.turno import TurnoCrear
from app.services import disponibilidad as disp
from app.services import turno as turno_svc


def resolver_empresa(db: Session, slug: str) -> Empresa:
    """Empresa activa por slug, o 404. Punto único de entrada del tenant público."""
    empresa = db.scalar(
        select(Empresa).where(Empresa.slug == slug, Empresa.activa.is_(True))
    )
    if empresa is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Negocio no encontrado")
    return empresa


def _servicio_publico(db: Session, empresa_id: int, servicio_id: int) -> Servicio:
    """Servicio activo y agendable de la empresa, o 404."""
    servicio = db.scalar(
        select(Servicio).where(
            Servicio.id == servicio_id,
            Servicio.empresa_id == empresa_id,
            Servicio.activo.is_(True),
            Servicio.agendable.is_(True),
        )
    )
    if servicio is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Servicio no disponible")
    return servicio


def vidriera(db: Session, slug: str) -> dict:
    """Datos para pintar la página del negocio: info + servicios + equipo."""
    empresa = resolver_empresa(db, slug)

    servicios = db.scalars(
        select(Servicio)
        .where(
            Servicio.empresa_id == empresa.id,
            Servicio.activo.is_(True),
            Servicio.agendable.is_(True),
        )
        .order_by(Servicio.nombre)
    ).all()

    recursos = db.scalars(
        select(Recurso)
        .where(
            Recurso.empresa_id == empresa.id,
            Recurso.activo.is_(True),
            Recurso.tipo == TipoRecurso.PERSONA,
        )
        .order_by(Recurso.nombre)
    ).all()

    return {
        "nombre": empresa.nombre,
        "slug": empresa.slug,
        "descripcion": empresa.descripcion,
        "direccion": empresa.direccion,
        "telefono_publico": empresa.telefono_publico,
        "email_publico": empresa.email_publico,
        "logo_url": empresa.logo_url,
        "color_marca": empresa.color_marca,
        "horarios_atencion": empresa.horarios_atencion,
        "redes": empresa.redes or {},
        "galeria": empresa.galeria or [],
        "servicios": [
            {
                "id": s.id,
                "nombre": s.nombre,
                "precio": float(s.precio) if s.precio is not None else None,
                "duracion_min": s.duracion_min,
            }
            for s in servicios
        ],
        "recursos": [
            {"id": r.id, "nombre": r.nombre, "foto_url": r.foto_url} for r in recursos
        ],
    }


def _elegibles(servicio: Servicio) -> list[Recurso]:
    """Recursos activos que hacen este servicio (para 'cualquiera' y validación)."""
    return [r for r in servicio.recursos if r.activo]


def huecos(
    db: Session,
    slug: str,
    servicio_id: int,
    recurso_id: int | None,
    desde: dt.date,
    dias: int,
) -> list[dict]:
    """Horarios de inicio libres, por día, para un servicio (y opcionalmente un
    profesional). Con 'cualquiera', un horario está libre si ALGÚN profesional
    elegible lo tiene libre. Nunca ofrece sobreturnos.

    Nota: no filtra horas pasadas del día de hoy; eso lo resuelve el frontend con
    la hora local del cliente (el motor trabaja en hora local etiquetada UTC).
    """
    empresa = resolver_empresa(db, slug)
    servicio = _servicio_publico(db, empresa.id, servicio_id)

    elegibles = _elegibles(servicio)
    if recurso_id is not None:
        elegibles = [r for r in elegibles if r.id == recurso_id]
        if not elegibles:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Ese profesional no hace ese servicio"
            )

    dias = max(1, min(dias, 60))
    resultado: list[dict] = []
    for i in range(dias):
        fecha = desde + dt.timedelta(days=i)
        horas: set[dt.datetime] = set()
        for r in elegibles:
            horas.update(
                disp.calcular_huecos(
                    db,
                    empresa.id,
                    r.id,
                    fecha,
                    servicio.duracion_min,
                    buffer_min=servicio.buffer_min,
                    paso_min=servicio.paso_turno_min,
                    grupo_agenda=servicio.grupo_agenda,
                )
            )
        if horas:
            resultado.append({"fecha": fecha, "horas": sorted(horas)})
    return resultado


def reservar(db: Session, slug: str, datos: ReservaPublicaCrear) -> dict:
    """Crea una reserva pública. Resuelve el profesional (o el primero libre si
    'cualquiera'), busca-o-crea el cliente por teléfono (canal 'web') y delega la
    creación al motor de turnos (que revalida el hueco y crea en PENDIENTE)."""
    empresa = resolver_empresa(db, slug)
    servicio = _servicio_publico(db, empresa.id, servicio_id=datos.servicio_id)

    elegibles = _elegibles(servicio)
    if not elegibles:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "No hay profesionales disponibles para ese servicio",
        )

    fin = datos.inicio + dt.timedelta(minutes=servicio.duracion_min)

    # Resolver el profesional que va a atender.
    if datos.recurso_id is not None:
        recurso = next((r for r in elegibles if r.id == datos.recurso_id), None)
        if recurso is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Ese profesional no hace ese servicio"
            )
        if not disp.esta_disponible(
            db, empresa.id, recurso.id, datos.inicio, fin,
            grupo_agenda=servicio.grupo_agenda,
        ):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Ese horario ya no está disponible. Elegí otro.",
            )
    else:
        # "Sin preferencia": el primer profesional libre en ese hueco.
        recurso = next(
            (
                r
                for r in elegibles
                if disp.esta_disponible(
                    db, empresa.id, r.id, datos.inicio, fin,
                    grupo_agenda=servicio.grupo_agenda,
                )
            ),
            None,
        )
        if recurso is None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Ese horario ya no está disponible. Elegí otro.",
            )

    # Busca-o-crea el cliente por teléfono (dentro de la empresa).
    cliente = db.scalar(
        select(Cliente).where(
            Cliente.empresa_id == empresa.id,
            Cliente.telefono == datos.cliente.telefono,
        )
    )
    if cliente is None:
        cliente = Cliente(
            empresa_id=empresa.id,
            nombre=datos.cliente.nombre,
            telefono=datos.cliente.telefono,
            email=datos.cliente.email,
            canal_adquisicion="web",
        )
        db.add(cliente)
        db.flush()  # para tener cliente.id sin cerrar la transacción
    # Si ya existía, lo reusamos tal cual (no le pisamos el nombre cargado).

    # Delegar al motor de turnos: revalida el hueco (409 si se ocupó) y crea
    # el turno en estado PENDIENTE. Un solo lugar que sabe crear turnos.
    turno = turno_svc.crear(
        db,
        empresa.id,
        TurnoCrear(
            cliente_id=cliente.id,
            recurso_id=recurso.id,
            servicio_id=servicio.id,
            fecha_inicio=datos.inicio,
            notas="Reserva web",
        ),
    )

    return {
        "turno_id": turno.id,
        "servicio": servicio.nombre,
        "recurso": recurso.nombre,
        "inicio": datos.inicio,
        "estado": "pendiente",
        "mensaje": "Tu turno quedó solicitado. El negocio te lo va a confirmar.",
    }