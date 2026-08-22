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

from app.core.reloj import ahora_de_pared
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
        "portada_url": empresa.portada_url,
        # Reglas que el wizard necesita para no ofrecer horarios que el
        # backend va a rechazar (y para saber qué campos pedir).
        "reserva_anticipacion_min": int(empresa.reserva_anticipacion_min or 0),
        "reserva_pide_telefono": bool(empresa.reserva_pide_telefono),
        "reserva_pide_nacimiento": bool(empresa.reserva_pide_nacimiento),
        "reserva_permite_cancelar": bool(empresa.reserva_permite_cancelar),
        "meta_pixel_id": empresa.meta_pixel_id,
        "google_tag_id": empresa.google_tag_id,
        "google_conversion_label": empresa.google_conversion_label,
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


# Ventana de la reserva PÚBLICA. Solo aplica acá: desde el panel el negocio sí
# puede cargar un turno de ayer (el que se olvidó de anotar) o de dentro de un
# año, porque el que carga es el dueño y sabe lo que hace.
DIAS_MAXIMOS_A_FUTURO = 180
MARGEN_MINUTOS_PASADO = 5  # tolerancia por relojes desfasados del celular


# La definición vive en app/core/reloj.py: es la convención de TODO el
# sistema, no de este módulo. Mientras era privada de acá, las tareas de fondo
# no la podían importar y terminaron usando datetime.now(UTC) — con las tres
# horas de corrimiento puestas. Se mantiene el nombre para no tocar el resto
# del archivo.
_ahora_de_pared = ahora_de_pared


def _texto_anticipacion(minutos: int) -> str:
    """"90" -> "1 hora y 30 minutos". Para que el error se lea como lo diría
    el dueño, no como lo guarda la base."""
    if minutos < 60:
        return f"{minutos} minutos"
    horas, resto = divmod(minutos, 60)
    if horas < 24:
        txt = "1 hora" if horas == 1 else f"{horas} horas"
        return txt if resto == 0 else f"{txt} y {resto} minutos"
    dias, h = divmod(horas, 24)
    txt = "1 día" if dias == 1 else f"{dias} días"
    return txt if h == 0 else f"{txt} y {h} horas"


def _validar_ventana(inicio: dt.datetime, empresa: Empresa) -> None:
    """La reserva web tiene que caer dentro de la ventana QUE DEFINE EL NEGOCIO.

    El motor de disponibilidad solo mira horarios del recurso y solapamientos:
    nunca compara contra "ahora". Sin este control, la vidriera acepta un turno
    para hace 40 días (ensucia caja y estadísticas con turnos retroactivos) o
    para el año 2099 (basura en la agenda que nadie va a limpiar).

    Los tres límites salen de la empresa (antes eran constantes iguales para
    todos): anticipación mínima, días hacia adelante y fecha fija de cierre.
    """
    ahora = _ahora_de_pared()

    # 1. Nunca en el pasado. El margen cubre relojes de celular desfasados.
    if inicio < ahora - dt.timedelta(minutes=MARGEN_MINUTOS_PASADO):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Ese horario ya pasó. Elegí uno disponible.",
        )

    # 2. Anticipación mínima: el negocio no quiere que le entren turnos para
    #    dentro de diez minutos cuando ya está con alguien en la silla.
    anticipacion = int(empresa.reserva_anticipacion_min or 0)
    if anticipacion > 0 and inicio < ahora + dt.timedelta(minutes=anticipacion):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Las reservas se toman con al menos {_texto_anticipacion(anticipacion)} "
            "de anticipación. Elegí un horario más adelante.",
        )

    # 3. Hasta dónde se puede reservar. Manda la MÁS restrictiva entre los días
    #    hacia adelante y la fecha fija de cierre, si el negocio cargó una.
    dias_max = int(empresa.reserva_dias_max or DIAS_MAXIMOS_A_FUTURO)
    tope = (ahora + dt.timedelta(days=dias_max)).date()
    if empresa.reserva_fecha_limite and empresa.reserva_fecha_limite < tope:
        tope = empresa.reserva_fecha_limite

    if inicio.date() > tope:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"La agenda está abierta hasta el {tope.strftime('%d/%m/%Y')} inclusive.",
        )


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

    dias = max(1, min(dias, 31))

    # La ventana que definió el negocio manda también acá.
    #
    # Antes este listado ignoraba las reglas de reserva y _validar_ventana las
    # aplicaba recién al confirmar: la vidriera ofrecía días que el backend
    # después rechazaba. El cliente elegía un horario visible, completaba todos
    # sus datos y ahí comía el error. Es la misma fricción que ya se había
    # sacado con la anticipación mínima, pero del otro extremo de la ventana.
    tope = (_ahora_de_pared() + dt.timedelta(days=int(empresa.reserva_dias_max or 180))).date()
    if empresa.reserva_fecha_limite and empresa.reserva_fecha_limite < tope:
        tope = empresa.reserva_fecha_limite

    # Anticipación mínima: no ofrecer horarios que caen antes del corte.
    corte = _ahora_de_pared() + dt.timedelta(
        minutes=int(empresa.reserva_anticipacion_min or 0)
    )

    # Toda la ventana de una sola vez: 3 consultas en lugar de 3 por cada
    # combinación de día y profesional. Con 31 días y 8 profesionales eran 744
    # idas y vueltas a Postgres para pintar la primera pantalla que ve un
    # cliente. El cálculo es exactamente el mismo, sobre los mismos datos.
    ultimo = min(desde + dt.timedelta(days=dias - 1), tope)
    agenda = disp.precargar(db, empresa.id, [r.id for r in elegibles], desde, ultimo)

    resultado: list[dict] = []
    for i in range(dias):
        fecha = desde + dt.timedelta(days=i)
        if fecha > tope:
            break
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
                    agenda=agenda,
                )
            )
        # Se descartan los horarios anteriores al corte de anticipación. El
        # frontend ya filtra por su cuenta, pero el motor es la fuente de
        # verdad: un cliente con el reloj del celular atrasado veía huecos que
        # el servidor iba a rechazar.
        libres = sorted(h for h in horas if h >= corte)
        if libres:
            resultado.append({"fecha": fecha, "horas": libres})
    return resultado


def reservar(db: Session, slug: str, datos: ReservaPublicaCrear) -> dict:
    """Crea una reserva pública. Resuelve el profesional (o el primero libre si
    'cualquiera'), busca-o-crea el cliente por teléfono (canal 'web') y delega la
    creación al motor de turnos (que revalida el hueco y crea en PENDIENTE)."""
    empresa = resolver_empresa(db, slug)
    servicio = _servicio_publico(db, empresa.id, servicio_id=datos.servicio_id)

    _validar_ventana(datos.inicio, empresa)

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

    # --- Cupón de descuento: se VALIDA ANTES de crear el turno ---
    # El orden importa. turno_svc.crear() hace commit, así que validar el cupón
    # después dejaba el turno guardado en la agenda del negocio aunque el
    # cliente recibiera un 400 y creyera que no había reservado nada: turnos
    # fantasma que el barbero ve y nadie va a ocupar.
    # Se revalida server-side igual que antes (entre que el wizard lo mostró y
    # el cliente confirmó, el cupón pudo vencerse o agotarse). El consumo del
    # uso queda para después de crear el turno: si el horario se ocupó justo y
    # sale 409, el cupón no se gasta.
    from app.services import cupones as svc_cupones

    cupon = None
    descuento_pesos = 0.0
    if datos.cupon_codigo:
        cupon, descuento_pesos, mensaje_cupon = svc_cupones.validar_cupon(
            db, empresa.id, datos.cupon_codigo, servicio.id
        )
        if cupon is None:
            raise HTTPException(status_code=400, detail=mensaje_cupon)

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

    # Turno creado: recién ahora se aplica el descuento y se consume el uso.
    if cupon is not None:
        precio_serv = float(servicio.precio or 0)
        turno.descuento_pct = svc_cupones.pct_equivalente(descuento_pesos, precio_serv)
        # Se guarda QUÉ cupón fue, no solo el porcentaje. Con el contador de
        # usos solo se sabía "este código se usó 12 veces"; con esto se puede
        # responder cuánta gente distinta lo usó, cuánto facturaron esos
        # turnos y cuánto se regaló en descuento — que es lo que decide si la
        # promoción funcionó o fue plata tirada.
        turno.cupon_id = cupon.id
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
