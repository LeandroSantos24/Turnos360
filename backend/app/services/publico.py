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
from app.services import mercadopago as mp
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

    # Busca-o-crea el cliente por teléfono + nombre (dentro de la empresa).
    # Solo por teléfono no alcanza: un mismo número puede usarlo un padre que
    # reserva para su hijo, y quedarían pegados en una sola ficha. Matcheamos
    # también el nombre (normalizado: sin distinguir mayúsculas ni espacios de
    # más) para que el cliente habitual sume a su ficha y una persona distinta
    # con el mismo número quede en la suya.
    def _norm(s: str) -> str:
        return " ".join((s or "").lower().split())

    nombre_norm = _norm(datos.cliente.nombre)
    candidatos = db.scalars(
        select(Cliente).where(
            Cliente.empresa_id == empresa.id,
            Cliente.telefono == datos.cliente.telefono,
        )
    ).all()
    cliente = next(
        (c for c in candidatos if _norm(c.nombre) == nombre_norm), None
    )
    if cliente is None:
        cliente = Cliente(
            empresa_id=empresa.id,
            nombre=datos.cliente.nombre,
            telefono=datos.cliente.telefono,
            email=datos.cliente.email,
            acepta_marketing=datos.cliente.acepta_marketing,
            canal_adquisicion="web",
        )
        db.add(cliente)
        db.flush()  # para tener cliente.id sin cerrar la transacción
    # Si ya existía (mismo tel + mismo nombre), lo reusamos tal cual.

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

    # Si el cliente ya existía y ahora acepta marketing, lo registramos.
    if datos.cliente.acepta_marketing and not cliente.acepta_marketing:
        cliente.acepta_marketing = True
        db.commit()

    # --- Cupón de descuento (si el cliente cargó un código) ---
    # Se revalida acá SIEMPRE (server-side): entre que el wizard lo validó y
    # confirmó, pudo vencer o agotarse. Si no corre, la reserva se rechaza con
    # el motivo — jamás se reserva "creyendo" tener un descuento que no corrió.
    descuento_pesos = 0.0
    if datos.cupon_codigo:
        from app.services import cupones as svc_cupones

        cupon, descuento_pesos, mensaje_cupon = svc_cupones.validar_cupon(
            db, empresa.id, datos.cupon_codigo, servicio.id
        )
        if cupon is None:
            raise HTTPException(status_code=400, detail=mensaje_cupon)
        precio_serv = float(servicio.precio or 0)
        turno.descuento_pct = svc_cupones.pct_equivalente(descuento_pesos, precio_serv)
        cupon.usos = (cupon.usos or 0) + 1
        db.commit()

    # --- Cobro anticipado con Mercado Pago (lo que el negocio haya elegido) ---
    # cobro_modo: "ninguno" (no se cobra nada) | "sena" (monto fijo) | "total"
    # (el precio del servicio).
    pago_url: str | None = None
    monto_a_cobrar: float | None = None
    concepto = ""
    if empresa.cobro_modo == "sena" and empresa.sena_monto:
        monto_a_cobrar = float(empresa.sena_monto)
        concepto = f"Seña · {servicio.nombre} · {empresa.nombre}"
    elif empresa.cobro_modo == "total" and servicio.precio:
        # Si hubo cupón, se cobra el precio CON el descuento aplicado.
        monto_a_cobrar = round(float(servicio.precio) - descuento_pesos, 2)
        concepto = f"{servicio.nombre} · {empresa.nombre}"

    if monto_a_cobrar:
        turno.sena_estado = "pendiente"
        turno.sena_monto = monto_a_cobrar
        db.commit()
        pago_url = mp.crear_preferencia(empresa, turno, concepto)

    # --- Emails por cola (Regla 6). La reserva jamás depende del email. ---
    try:
        from app.tasks.emails import enviar_aviso_negocio, enviar_confirmacion_reserva

        enviar_confirmacion_reserva.delay(turno.id)
        enviar_aviso_negocio.delay(turno.id)
    except Exception:
        # Redis caído o worker apagado: se pierde el aviso, no la reserva.
        pass

    if pago_url:
        mensaje = (
            "Tu turno quedó reservado. Aboná la seña para confirmarlo: "
            "si no se abona, el negocio puede liberar el horario."
        )
    else:
        mensaje = "Tu turno quedó solicitado. El negocio te lo va a confirmar."

    return {
        "turno_id": turno.id,
        "servicio": servicio.nombre,
        "recurso": recurso.nombre,
        "inicio": datos.inicio,
        "estado": "pendiente",
        "mensaje": mensaje,
        "pago_url": pago_url,
        "sena_monto": float(turno.sena_monto) if turno.sena_monto else None,
    }

def slugs_activos(db: Session) -> list[str]:
    """Slugs de las empresas activas. Alimenta el sitemap de la landing."""
    return list(
        db.scalars(
            select(Empresa.slug)
            .where(Empresa.activa.is_(True), Empresa.slug.is_not(None))
            .order_by(Empresa.slug)
        )
    )
