"""Emails transaccionales y campañas (Celery). Regla 6: por cola y registrados.

Workflow del turno (siempre activos):
- Confirmación al cliente al reservar online (con seña y botón Google Calendar).
- Aviso al negocio de cada reserva nueva.
- Aviso al cliente si su turno se cancela o se reprograma desde el panel.

Campañas (switches por empresa en la pantalla Campañas):
- Recordatorio 24 h antes  ·  Recordatorio 2 h antes (doble recordatorio).
- Saludo de cumpleaños con beneficio (X días antes, una vez por año).
- Pedido de reseña en Google al finalizar el turno.
- Recuperación de clientes inactivos (X días sin venir).

Si SMTP no está configurado, el mensaje queda FALLIDO con el motivo — nada
explota y ninguna operación del negocio depende del email.
"""

import datetime as dt
import urllib.parse

from sqlalchemy import extract, func, or_ as sa_or, select

from app.celery_app import celery_app
from app.core import mailer
from app.db.session import SessionLocal
from app.models import Cliente, Empresa, Mensaje, Recurso, Servicio, Turno
from app.models.enums import CanalMensaje, EstadoMensaje, EstadoTurno
from app.services.empresa import automs_de

TEAL = "#17a08a"
TINTA = "#0c1015"


# ============================================================
# Helpers de armado
# ============================================================

def _plantilla(
    titulo: str,
    lineas: list[str],
    pie: str,
    boton: tuple[str, str] | None = None,
    marca: str | None = None,
) -> str:
    """Email premium: card blanca con banda de marca, botón pill, footer sobrio.

    Armado con tablas (los clientes de correo no soportan bien flex/grid).
    `marca` = nombre del negocio: él es el protagonista; Turnos360 firma abajo.
    """
    cuerpo = "".join(
        f'<p style="margin:0 0 10px;font-size:15px;line-height:1.65;color:#2a3140;">{linea}</p>'
        for linea in lineas
        if linea
    )
    html_boton = ""
    if boton:
        texto, url = boton
        html_boton = f"""
      <table role="presentation" cellpadding="0" cellspacing="0" style="margin:22px auto 6px;">
        <tr><td style="border-radius:28px;background:{TEAL};">
          <a href="{url}" style="display:inline-block;padding:13px 30px;font-size:14px;
             font-weight:bold;color:#ffffff;text-decoration:none;border-radius:28px;">
            {texto}
          </a>
        </td></tr>
      </table>"""
    encabezado = marca or "Turnos360"
    return f"""
<body style="margin:0;padding:0;background:#eef1f5;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#eef1f5;padding:32px 14px;">
    <tr><td align="center">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
             style="max-width:540px;background:#ffffff;border-radius:18px;overflow:hidden;
                    border:1px solid #e4e8ee;font-family:Arial,Helvetica,sans-serif;">
        <tr><td style="height:5px;background:{TEAL};font-size:0;">&nbsp;</td></tr>
        <tr><td style="padding:30px 34px 8px;">
          <p style="margin:0;font-size:19px;font-weight:bold;color:{TINTA};letter-spacing:0.2px;">
            {encabezado}
          </p>
        </td></tr>
        <tr><td style="padding:6px 34px 0;">
          <h2 style="margin:0 0 14px;font-size:22px;line-height:1.3;color:{TINTA};">{titulo}</h2>
          {cuerpo}
          {html_boton}
        </td></tr>
        <tr><td style="padding:18px 34px 26px;">
          <hr style="border:none;border-top:1px solid #edf0f4;margin:0 0 14px;" />
          <p style="margin:0;font-size:12px;line-height:1.6;color:#8a92a0;">{pie}</p>
        </td></tr>
      </table>
      <p style="margin:16px 0 0;font-size:11px;color:#9aa3b2;font-family:Arial,Helvetica,sans-serif;">
        Enviado con <b style="color:#7c8694;">Turnos360</b> · gestión de turnos para tu negocio
      </p>
    </td></tr>
  </table>
</body>"""


def _fecha_legible(f: dt.datetime) -> str:
    return f.strftime("%d/%m/%Y a las %H:%M")


def _contacto_negocio(empresa: Empresa) -> str:
    """Cómo contactar al negocio (Turnos360 no es parte de la conversación)."""
    partes = []
    if empresa.telefono_publico:
        partes.append(f"WhatsApp {empresa.telefono_publico}")
    if empresa.email_publico:
        partes.append(empresa.email_publico)
    return " · ".join(partes) if partes else "contactá al negocio"


def _pie_negocio(empresa: Empresa) -> str:
    return (
        f"Este aviso lo envió Turnos360 en nombre de {empresa.nombre}. "
        f"Para cambios o cancelaciones: {_contacto_negocio(empresa)}."
    )


def _link_gcal(titulo: str, inicio: dt.datetime, fin: dt.datetime | None, lugar: str) -> str:
    """Link 'Agregar a Google Calendar' (estático, sin API ni permisos).

    OJO con las zonas horarias: guardamos la hora DE PARED marcada como UTC
    (09:00Z = las 9 del reloj del local). Si le mandamos la Z a Google, la toma
    como UTC real y la convierte a -03 → agendaría a las 6. Por eso mandamos la
    hora SIN Z (Google la lee como local) y declaramos la zona con ctz.
    """
    if fin is None:
        fin = inicio + dt.timedelta(minutes=30)
    fmt = "%Y%m%dT%H%M%S"  # sin Z: hora local, no UTC
    params = urllib.parse.urlencode(
        {
            "action": "TEMPLATE",
            "text": titulo,
            "dates": f"{inicio.strftime(fmt)}/{fin.strftime(fmt)}",
            "ctz": "America/Argentina/Buenos_Aires",
            "location": lugar,
            "details": "Reservado con Turnos360",
        }
    )
    return f"https://calendar.google.com/calendar/render?{params}"


def _cargar(db, turno_id: int):
    turno = db.get(Turno, turno_id)
    if turno is None:
        return None
    return {
        "turno": turno,
        "empresa": db.get(Empresa, turno.empresa_id),
        "cliente": db.get(Cliente, turno.cliente_id),
        "servicio": db.get(Servicio, turno.servicio_id) if turno.servicio_id else None,
        "recurso": db.get(Recurso, turno.recurso_id) if turno.recurso_id else None,
    }


def _registrar(db, *, empresa_id, cliente_id, turno_id, contenido, ok, error=None):
    db.add(
        Mensaje(
            empresa_id=empresa_id,
            cliente_id=cliente_id,
            turno_id=turno_id,
            canal=CanalMensaje.EMAIL,
            contenido=contenido,
            estado=EstadoMensaje.ENVIADO if ok else EstadoMensaje.FALLIDO,
            error=(error or "")[:300] or None,
        )
    )
    db.commit()


def _mandar(db, empresa, destino: str, asunto: str, html: str, contenido_log: str,
            cliente_id=None, turno_id=None):
    """Envía + registra en Mensaje. Nunca propaga la excepción."""
    try:
        mailer.enviar(destino, asunto, html, reply_to=empresa.email_publico or None)
        ok, error = True, None
    except Exception as e:
        ok, error = False, str(e)
    _registrar(
        db, empresa_id=empresa.id, cliente_id=cliente_id, turno_id=turno_id,
        contenido=contenido_log, ok=ok, error=error,
    )


# ============================================================
# Workflow del turno
# ============================================================

@celery_app.task(name="app.tasks.emails.enviar_confirmacion_reserva")
def enviar_confirmacion_reserva(turno_id: int) -> None:
    """Al cliente, apenas reserva online (con seña si aplica + Google Calendar)."""
    with SessionLocal() as db:
        ctx = _cargar(db, turno_id)
        if not ctx or not ctx["cliente"] or not ctx["cliente"].email:
            return
        turno, empresa = ctx["turno"], ctx["empresa"]
        servicio = ctx["servicio"].nombre if ctx["servicio"] else "Turno"
        profesional = ctx["recurso"].nombre if ctx["recurso"] else ""

        lineas = [
            f"<b>{servicio}</b>" + (f" con {profesional}" if profesional else ""),
            f"📅 {_fecha_legible(turno.fecha_inicio)}",
            f"📍 {empresa.nombre}" + (f" · {empresa.direccion}" if empresa.direccion else ""),
        ]
        if turno.sena_estado == "pendiente" and turno.sena_monto:
            lineas.append(
                f"⚠️ Para confirmar el turno falta abonar la seña de "
                f"<b>${turno.sena_monto:,.0f}</b> con Mercado Pago (el link te lo "
                "mostró la página al reservar)."
            )
        gcal = _link_gcal(
            f"{servicio} · {empresa.nombre}",
            turno.fecha_inicio,
            turno.fecha_fin,
            empresa.direccion or empresa.nombre,
        )
        html = _plantilla(
            "¡Tu reserva está tomada!",
            lineas,
            _pie_negocio(empresa),
            boton=("Agregar a Google Calendar", gcal),
            marca=empresa.nombre,
        )
        _mandar(
            db, empresa, ctx["cliente"].email,
            f"Reserva en {empresa.nombre} · {_fecha_legible(turno.fecha_inicio)}",
            html, f"confirmacion_reserva turno={turno.id}",
            cliente_id=ctx["cliente"].id, turno_id=turno.id,
        )


@celery_app.task(name="app.tasks.emails.enviar_aviso_negocio")
def enviar_aviso_negocio(turno_id: int) -> None:
    """Al email público del negocio: le cayó una reserva online."""
    with SessionLocal() as db:
        ctx = _cargar(db, turno_id)
        if not ctx or not ctx["empresa"].email_publico:
            return
        turno, empresa, cliente = ctx["turno"], ctx["empresa"], ctx["cliente"]
        servicio = ctx["servicio"].nombre if ctx["servicio"] else "Turno"
        profesional = ctx["recurso"].nombre if ctx["recurso"] else "—"

        lineas = [
            f"<b>{cliente.nombre} {cliente.apellido or ''}</b>"
            + (f" · {cliente.telefono}" if cliente.telefono else ""),
            f"{servicio} con {profesional}",
            f"📅 {_fecha_legible(turno.fecha_inicio)}",
        ]
        if turno.sena_estado:
            lineas.append(
                "Seña: <b>pendiente de pago</b>"
                if turno.sena_estado == "pendiente"
                else f"Seña: <b>pagada</b> (${turno.sena_monto:,.0f})"
            )
        html = _plantilla("Nueva reserva online 🎉", lineas,
                          "Podés gestionarla desde tu agenda en Turnos360.",
                          marca=empresa.nombre)
        _mandar(
            db, empresa, empresa.email_publico,
            f"Nueva reserva · {_fecha_legible(turno.fecha_inicio)}",
            html, f"aviso_negocio turno={turno.id}",
            cliente_id=cliente.id if cliente else None, turno_id=turno.id,
        )


@celery_app.task(name="app.tasks.emails.enviar_cancelacion")
def enviar_cancelacion(turno_id: int) -> None:
    """Al cliente: su turno fue cancelado."""
    with SessionLocal() as db:
        ctx = _cargar(db, turno_id)
        if not ctx or not ctx["cliente"] or not ctx["cliente"].email:
            return
        turno, empresa = ctx["turno"], ctx["empresa"]
        servicio = ctx["servicio"].nombre if ctx["servicio"] else "tu turno"
        lineas = [
            f"Tu turno de <b>{servicio}</b> del {_fecha_legible(turno.fecha_inicio)} "
            f"en <b>{empresa.nombre}</b> fue cancelado.",
            (f"Motivo: {turno.motivo_cancelacion}" if turno.motivo_cancelacion else ""),
            "Si querés reprogramarlo, contactá al negocio o reservá de nuevo online.",
        ]
        html = _plantilla("Tu turno fue cancelado", lineas, _pie_negocio(empresa),
                          marca=empresa.nombre)
        _mandar(
            db, empresa, ctx["cliente"].email,
            f"Turno cancelado · {empresa.nombre}",
            html, f"cancelacion turno={turno.id}",
            cliente_id=ctx["cliente"].id, turno_id=turno.id,
        )


@celery_app.task(name="app.tasks.emails.enviar_reprogramacion")
def enviar_reprogramacion(turno_id: int) -> None:
    """Al cliente: su turno cambió de fecha/hora o de profesional."""
    with SessionLocal() as db:
        ctx = _cargar(db, turno_id)
        if not ctx or not ctx["cliente"] or not ctx["cliente"].email:
            return
        turno, empresa = ctx["turno"], ctx["empresa"]
        servicio = ctx["servicio"].nombre if ctx["servicio"] else "Turno"
        profesional = ctx["recurso"].nombre if ctx["recurso"] else ""
        gcal = _link_gcal(
            f"{servicio} · {empresa.nombre}",
            turno.fecha_inicio, turno.fecha_fin,
            empresa.direccion or empresa.nombre,
        )
        html = _plantilla(
            "Tu turno cambió de horario",
            [
                f"<b>{servicio}</b>" + (f" con {profesional}" if profesional else ""),
                f"🗓 Nueva fecha: <b>{_fecha_legible(turno.fecha_inicio)}</b>",
                f"📍 {empresa.nombre}" + (f" · {empresa.direccion}" if empresa.direccion else ""),
            ],
            _pie_negocio(empresa),
            boton=("Agregar a Google Calendar", gcal),
            marca=empresa.nombre,
        )
        _mandar(
            db, empresa, ctx["cliente"].email,
            f"Tu turno cambió · {empresa.nombre} · {_fecha_legible(turno.fecha_inicio)}",
            html, f"reprogramacion turno={turno.id}",
            cliente_id=ctx["cliente"].id, turno_id=turno.id,
        )


# ============================================================
# Campañas (switches por empresa)
# ============================================================

@celery_app.task(name="app.tasks.emails.enviar_recordatorio")
def enviar_recordatorio(turno_id: int) -> None:
    """24 h antes."""
    with SessionLocal() as db:
        ctx = _cargar(db, turno_id)
        if not ctx or not ctx["cliente"] or not ctx["cliente"].email:
            return
        turno, empresa = ctx["turno"], ctx["empresa"]
        servicio = ctx["servicio"].nombre if ctx["servicio"] else "tu turno"
        html = _plantilla(
            "Recordatorio de tu turno ⏰",
            [
                f"Mañana tenés <b>{servicio}</b> en <b>{empresa.nombre}</b>.",
                f"📅 {_fecha_legible(turno.fecha_inicio)}",
                (f"📍 {empresa.direccion}" if empresa.direccion else ""),
                f"Si no podés asistir, avisá así liberan el horario: {_contacto_negocio(empresa)}.",
            ],
            _pie_negocio(empresa),
            marca=empresa.nombre,
        )
        _mandar(
            db, empresa, ctx["cliente"].email,
            f"Recordatorio: {servicio} mañana en {empresa.nombre}",
            html, f"recordatorio_24h turno={turno.id}",
            cliente_id=ctx["cliente"].id, turno_id=turno.id,
        )


@celery_app.task(name="app.tasks.emails.enviar_recordatorio_2h")
def enviar_recordatorio_2h(turno_id: int) -> None:
    """2 h antes (el segundo del doble recordatorio)."""
    with SessionLocal() as db:
        ctx = _cargar(db, turno_id)
        if not ctx or not ctx["cliente"] or not ctx["cliente"].email:
            return
        turno, empresa = ctx["turno"], ctx["empresa"]
        servicio = ctx["servicio"].nombre if ctx["servicio"] else "tu turno"
        html = _plantilla(
            "¡Es hoy! Tu turno se acerca ⏰",
            [
                f"En un rato: <b>{servicio}</b> a las "
                f"<b>{turno.fecha_inicio.strftime('%H:%M')}</b> en <b>{empresa.nombre}</b>.",
                (f"📍 {empresa.direccion}" if empresa.direccion else ""),
            ],
            _pie_negocio(empresa),
            marca=empresa.nombre,
        )
        _mandar(
            db, empresa, ctx["cliente"].email,
            f"¡Hoy a las {turno.fecha_inicio.strftime('%H:%M')}! · {empresa.nombre}",
            html, f"recordatorio_2h turno={turno.id}",
            cliente_id=ctx["cliente"].id, turno_id=turno.id,
        )


@celery_app.task(name="app.tasks.emails.pedir_resena")
def pedir_resena(turno_id: int, manual: bool = False) -> None:
    """Pedido de reseña en Google.

    Sale solo al finalizar el turno cuando la campaña está activa, y también
    a pedido desde la agenda (`manual=True`). En el caso manual se saltea el
    switch de la campaña —el dueño ya decidió mandarlo apretando el botón—
    pero el link sigue siendo obligatorio: sin él el mail no tiene a dónde
    llevar al cliente.
    """
    with SessionLocal() as db:
        ctx = _cargar(db, turno_id)
        if not ctx or not ctx["cliente"] or not ctx["cliente"].email:
            return
        empresa = ctx["empresa"]
        cfg = automs_de(empresa).get("resena_google", {})
        if not cfg.get("link"):
            return
        if not manual and not cfg.get("activa"):
            return
        html = _plantilla(
            "¿Cómo estuvo tu visita? ⭐",
            [
                f"Gracias por venir a <b>{empresa.nombre}</b>.",
                "Si te gustó la atención, una reseña en Google nos ayuda muchísimo "
                "(te toma 30 segundos).",
            ],
            _pie_negocio(empresa),
            boton=("Dejar mi reseña", cfg["link"]),
            marca=empresa.nombre,
        )
        _mandar(
            db, empresa, ctx["cliente"].email,
            f"¿Cómo estuvo tu visita a {empresa.nombre}?",
            html, f"pedido_resena turno={ctx['turno'].id}",
            cliente_id=ctx["cliente"].id, turno_id=ctx["turno"].id,
        )


@celery_app.task(name="app.tasks.emails.encolar_recordatorios")
def encolar_recordatorios() -> int:
    """Beat cada 15 min: encola los recordatorios de 24 h y de 2 h que tocan.

    Ventanas con solapamiento (23-25 h y 1h45-2h30) + flags de dedup: ningún
    turno se escapa aunque un ciclo se pierda, y jamás se manda dos veces.
    Cada envío respeta el switch de SU empresa.
    """
    ahora = dt.datetime.now(dt.timezone.utc)
    encolados = 0
    with SessionLocal() as db:
        empresas_cfg: dict[int, dict] = {}

        def cfg_de(empresa_id: int) -> dict:
            if empresa_id not in empresas_cfg:
                empresas_cfg[empresa_id] = automs_de(db.get(Empresa, empresa_id))
            return empresas_cfg[empresa_id]

        # --- 24 h ---
        turnos = db.scalars(
            select(Turno).where(
                Turno.fecha_inicio >= ahora + dt.timedelta(hours=23),
                Turno.fecha_inicio <= ahora + dt.timedelta(hours=25),
                Turno.recordatorio_enviado.is_(False),
                Turno.estado.in_([EstadoTurno.PENDIENTE, EstadoTurno.CONFIRMADO]),
            )
        ).all()
        for turno in turnos:
            turno.recordatorio_enviado = True
            db.commit()
            if cfg_de(turno.empresa_id).get("recordatorio_24h", {}).get("activa"):
                enviar_recordatorio.delay(turno.id)
                encolados += 1

        # --- 2 h ---
        turnos2 = db.scalars(
            select(Turno).where(
                Turno.fecha_inicio >= ahora + dt.timedelta(minutes=105),
                Turno.fecha_inicio <= ahora + dt.timedelta(minutes=150),
                Turno.recordatorio_2h_enviado.is_(False),
                Turno.estado.in_([EstadoTurno.PENDIENTE, EstadoTurno.CONFIRMADO]),
            )
        ).all()
        for turno in turnos2:
            turno.recordatorio_2h_enviado = True
            db.commit()
            if cfg_de(turno.empresa_id).get("recordatorio_2h", {}).get("activa"):
                enviar_recordatorio_2h.delay(turno.id)
                encolados += 1
    return encolados


@celery_app.task(name="app.tasks.emails.enviar_cumpleanios")
def enviar_cumpleanios() -> int:
    """Beat diario: saluda a los que cumplen años en `dias_antes` días.

    Dedup anual con cliente.ultimo_cumple_enviado (una sola vez por año).
    """
    hoy = dt.date.today()
    enviados = 0
    with SessionLocal() as db:
        empresas = db.scalars(select(Empresa).where(Empresa.activa.is_(True))).all()
        for empresa in empresas:
            cfg = automs_de(empresa).get("cumple", {})
            if not cfg.get("activa"):
                continue
            objetivo = hoy + dt.timedelta(days=int(cfg.get("dias_antes", 7)))
            clientes = db.scalars(
                select(Cliente).where(
                    Cliente.empresa_id == empresa.id,
                    Cliente.email.is_not(None),
                    # Consentimiento: es una campaña promocional (Ley 25.326).
                    Cliente.acepta_marketing.is_(True),
                    Cliente.fecha_nacimiento.is_not(None),
                    extract("month", Cliente.fecha_nacimiento) == objetivo.month,
                    extract("day", Cliente.fecha_nacimiento) == objetivo.day,
                )
            ).all()
            for cliente in clientes:
                if (
                    cliente.ultimo_cumple_enviado
                    and cliente.ultimo_cumple_enviado.year == hoy.year
                ):
                    continue  # ya lo saludamos este año
                cliente.ultimo_cumple_enviado = hoy
                db.commit()
                mensaje = (cfg.get("mensaje") or "").strip()
                lineas = [
                    f"¡Se viene tu cumpleaños! 🎉 En <b>{empresa.nombre}</b> lo "
                    "queremos festejar con vos.",
                ]
                if mensaje:
                    lineas.append(f"🎁 <b>{mensaje}</b>")
                lineas.append(
                    f"Reservá tu turno: {_contacto_negocio(empresa)}."
                )
                html = _plantilla(
                    f"¡Feliz cumple, {cliente.nombre}! 🎂", lineas,
                    _pie_negocio(empresa), marca=empresa.nombre,
                )
                _mandar(
                    db, empresa, cliente.email,
                    f"🎂 ¡{empresa.nombre} te quiere saludar!",
                    html, f"cumple cliente={cliente.id}",
                    cliente_id=cliente.id,
                )
                enviados += 1
    return enviados


@celery_app.task(name="app.tasks.emails.enviar_inactivos")
def enviar_inactivos() -> int:
    """Beat diario: 'te extrañamos' a quien lleva N días o más sin venir.

    Antes buscaba la última visita EXACTAMENTE hace N días (ventana de 1 día):
    frágil y casi imposible de probar. Ahora: cualquiera que lleve N días o más
    sin venir, y al que no le avisamos en los últimos N días (dedup con
    ultimo_inactivo_enviado). Solo a quien aceptó recibir promociones.
    """
    hoy = dt.date.today()
    enviados = 0
    with SessionLocal() as db:
        empresas = db.scalars(select(Empresa).where(Empresa.activa.is_(True))).all()
        for empresa in empresas:
            cfg = automs_de(empresa).get("inactivos", {})
            if not cfg.get("activa"):
                continue
            dias = int(cfg.get("dias", 60))
            corte = hoy - dt.timedelta(days=dias)

            # Última visita FINALIZADA de cada cliente.
            sub = (
                select(
                    Turno.cliente_id,
                    func.max(Turno.fecha_inicio).label("ultima"),
                )
                .where(
                    Turno.empresa_id == empresa.id,
                    Turno.estado == EstadoTurno.FINALIZADO,
                )
                .group_by(Turno.cliente_id)
                .subquery()
            )
            filas = db.execute(
                select(Cliente, sub.c.ultima)
                .join(sub, sub.c.cliente_id == Cliente.id)
                .where(
                    Cliente.empresa_id == empresa.id,
                    Cliente.email.is_not(None),
                    Cliente.acepta_marketing.is_(True),
                    # Hace N días o MÁS que no viene.
                    func.date(sub.c.ultima) <= corte,
                    # Y no le avisamos hace poco (o nunca).
                    sa_or(
                        Cliente.ultimo_inactivo_enviado.is_(None),
                        Cliente.ultimo_inactivo_enviado <= corte,
                    ),
                )
            ).all()

            for cliente, _ultima in filas:
                cliente.ultimo_inactivo_enviado = hoy
                db.commit()
                mensaje = (cfg.get("mensaje") or "").strip()
                lineas = [
                    f"Hace un tiempo que no te vemos por <b>{empresa.nombre}</b> "
                    "y te extrañamos 💈",
                ]
                if mensaje:
                    lineas.append(f"🎁 <b>{mensaje}</b>")
                lineas.append(f"Reservá tu turno: {_contacto_negocio(empresa)}.")
                html = _plantilla(
                    f"¡Volvé, {cliente.nombre}!", lineas,
                    _pie_negocio(empresa), marca=empresa.nombre,
                )
                _mandar(
                    db, empresa, cliente.email,
                    f"Te extrañamos en {empresa.nombre}",
                    html, f"inactivo cliente={cliente.id}",
                    cliente_id=cliente.id,
                )
                enviados += 1
    return enviados


@celery_app.task(name="app.tasks.emails.enviar_prueba_campana")
def enviar_prueba_campana(empresa_id: int, tipo: str, destino: str) -> None:
    """Manda al dueño una MUESTRA de la campaña, para que la vea sin esperar.

    Usa datos de ejemplo. No toca ningún cliente ni ningún flag.
    """
    with SessionLocal() as db:
        empresa = db.get(Empresa, empresa_id)
        if empresa is None:
            return
        cfg = automs_de(empresa)
        contacto = _contacto_negocio(empresa)
        pie = _pie_negocio(empresa)
        maniana = dt.datetime.now() + dt.timedelta(days=1)

        if tipo == "cumple":
            m = (cfg["cumple"].get("mensaje") or "").strip()
            lineas = [
                f"¡Se viene tu cumpleaños! 🎉 En <b>{empresa.nombre}</b> lo queremos "
                "festejar con vos.",
            ]
            if m:
                lineas.append(f"🎁 <b>{m}</b>")
            lineas.append(f"Reservá tu turno: {contacto}.")
            asunto = f"🎂 ¡{empresa.nombre} te quiere saludar!"
            html = _plantilla("¡Feliz cumple, Juan! 🎂", lineas, pie, marca=empresa.nombre)

        elif tipo == "inactivos":
            m = (cfg["inactivos"].get("mensaje") or "").strip()
            lineas = [
                f"Hace un tiempo que no te vemos por <b>{empresa.nombre}</b> y te "
                "extrañamos 💈",
            ]
            if m:
                lineas.append(f"🎁 <b>{m}</b>")
            lineas.append(f"Reservá tu turno: {contacto}.")
            asunto = f"Te extrañamos en {empresa.nombre}"
            html = _plantilla("¡Volvé, Juan!", lineas, pie, marca=empresa.nombre)

        elif tipo == "resena_google":
            link = cfg["resena_google"].get("link") or "#"
            asunto = f"¿Cómo estuvo tu visita a {empresa.nombre}?"
            html = _plantilla(
                "¿Cómo estuvo tu visita? ⭐",
                [
                    f"Gracias por venir a <b>{empresa.nombre}</b>.",
                    "Si te gustó la atención, una reseña en Google nos ayuda muchísimo "
                    "(te toma 30 segundos).",
                ],
                pie,
                boton=("Dejar mi reseña", link),
                marca=empresa.nombre,
            )

        elif tipo == "recordatorio_2h":
            asunto = f"¡Hoy a las {maniana.strftime('%H:%M')}! · {empresa.nombre}"
            html = _plantilla(
                "¡Es hoy! Tu turno se acerca ⏰",
                [
                    f"En un rato: <b>Corte</b> a las <b>{maniana.strftime('%H:%M')}</b> "
                    f"en <b>{empresa.nombre}</b>.",
                    (f"📍 {empresa.direccion}" if empresa.direccion else ""),
                ],
                pie,
                marca=empresa.nombre,
            )

        else:  # recordatorio_24h
            asunto = f"Recordatorio: Corte mañana en {empresa.nombre}"
            html = _plantilla(
                "Recordatorio de tu turno ⏰",
                [
                    f"Mañana tenés <b>Corte</b> en <b>{empresa.nombre}</b>.",
                    f"📅 {_fecha_legible(maniana)}",
                    (f"📍 {empresa.direccion}" if empresa.direccion else ""),
                    f"Si no podés asistir, avisá así liberan el horario: {contacto}.",
                ],
                pie,
                marca=empresa.nombre,
            )

        _mandar(
            db, empresa, destino,
            f"[PRUEBA] {asunto}",
            html, f"prueba_campana tipo={tipo}",
        )


# ============================================================
# Cobranza del SaaS: avisos de vencimiento al negocio
# ============================================================

# Hitos del ciclo, en días respecto de suscripcion_vence.
# Negativo = después del vencimiento (dentro de la prórroga).
_HITOS_VENCIMIENTO = {
    10: ("aviso", "Tu suscripción vence en 10 días"),
    3: ("aviso", "Tu suscripción vence en 3 días"),
    0: ("vence", "Tu suscripción vence hoy"),
    -3: ("gracia", "Tu suscripción venció · te quedan 7 días"),
    -8: ("ultimo", "Últimos 2 días antes de que se corte el servicio"),
}


def _email_del_dueno(db, empresa) -> str | None:
    """A quién le escribimos. Primero el dueño; si no hay, el mail público.

    Se busca el usuario con rol dueño y no el email_publico a secas porque el
    público suele ser el del local (lo atiende recepción) y esto es plata: va
    a quien decide.
    """
    from app.models import Usuario
    from app.models.enums import RolUsuario

    duenio = db.scalar(
        select(Usuario).where(
            Usuario.empresa_id == empresa.id,
            Usuario.rol == RolUsuario.DUENO,
            Usuario.activo.is_(True),
        )
    )
    if duenio and (duenio.email or "").strip():
        return duenio.email.strip()
    return (empresa.email_publico or "").strip() or None


def _datos_de_pago_html() -> list[str]:
    """Líneas con el CBU y el alias, si están configurados.

    Van DENTRO del mail a propósito: si el negocio tiene que entrar al panel
    para buscar el CBU, el aviso pierde la mitad de su efecto.
    """
    from app.core.config import settings

    lineas = []
    if settings.cobro_alias or settings.cobro_cbu:
        partes = []
        if settings.cobro_alias:
            partes.append(f"<b>Alias:</b> {settings.cobro_alias}")
        if settings.cobro_cbu:
            partes.append(f"<b>CBU:</b> {settings.cobro_cbu}")
        if settings.cobro_titular:
            partes.append(f"<b>Titular:</b> {settings.cobro_titular}")
        lineas.append(" &nbsp;·&nbsp; ".join(partes))
    return lineas


@celery_app.task(name="app.tasks.emails.avisar_vencimientos")
def avisar_vencimientos() -> None:
    """Avisa a cada negocio que su suscripción está por vencer o venció.

    Corre una vez por día. No es una campaña del negocio: es la cobranza de
    Turnos360, así que NO tiene switch en el panel del cliente.

    Se manda a lo sumo un mail por hito y por ciclo de vencimiento. La clave
    de deduplicación incluye la fecha de vencimiento, así que cuando el
    negocio paga y la fecha se corre, el ciclo siguiente vuelve a avisar.
    """
    from app.core.config import settings
    from app.services.suscripcion import DIAS_PRORROGA

    hoy = dt.date.today()
    with SessionLocal() as db:
        empresas = db.scalars(select(Empresa).where(Empresa.activa.is_(True))).all()
        for empresa in empresas:
            vence = empresa.suscripcion_vence
            if vence is None:
                continue
            # En período de prueba no se cobra: avisarle de un vencimiento que
            # no existe es la mejor forma de que no convierta.
            if empresa.prueba_hasta is not None and hoy <= empresa.prueba_hasta:
                continue

            dias = (vence - hoy).days
            hito = _HITOS_VENCIMIENTO.get(dias)
            if hito is None:
                continue
            clave, asunto = hito

            # Una sola vez por hito y por ciclo.
            log = f"aviso_vencimiento {clave} vence={vence}"
            ya = db.scalar(
                select(Mensaje).where(
                    Mensaje.empresa_id == empresa.id,
                    Mensaje.contenido == log,
                    Mensaje.estado == EstadoMensaje.ENVIADO,
                )
            )
            if ya is not None:
                continue

            destino = _email_del_dueno(db, empresa)
            if not destino:
                continue

            corte = vence + dt.timedelta(days=DIAS_PRORROGA)
            monto = (
                f"${float(empresa.precio_mensual):,.0f}".replace(",", ".")
                if empresa.precio_mensual is not None
                else None
            )

            if dias > 0:
                lineas = [
                    f"Hola! Te escribimos para avisarte que tu suscripción a "
                    f"Turnos360 vence el <b>{vence.strftime('%d/%m/%Y')}</b>.",
                ]
            elif dias == 0:
                lineas = [
                    "Hola! Tu suscripción a Turnos360 vence <b>hoy</b>.",
                ]
            else:
                lineas = [
                    f"Hola! Tu suscripción venció el "
                    f"<b>{vence.strftime('%d/%m/%Y')}</b>.",
                ]

            if monto:
                lineas.append(f"El importe es de <b>{monto}</b>.")

            lineas.append(
                f"Tu cuenta sigue funcionando con normalidad hasta el "
                f"<b>{corte.strftime('%d/%m/%Y')}</b>. Después de esa fecha, la "
                "agenda y tu página dejan de estar disponibles."
            )
            lineas += _datos_de_pago_html()
            lineas.append(
                "Cuando transfieras, mandanos el comprobante y registramos el "
                "pago: tu vencimiento se corre 30 días."
            )

            boton = None
            if settings.cobro_whatsapp:
                url = (
                    f"https://wa.me/{settings.cobro_whatsapp}"
                    "?text=Hola!%20Te%20paso%20el%20comprobante%20de%20Turnos360."
                )
                boton = ("Mandar el comprobante", url)

            html = _plantilla(
                titulo=asunto,
                lineas=lineas,
                pie="Turnos360 · Gestión de turnos para tu negocio",
                boton=boton,
                marca="Turnos360",
            )
            _mandar(db, empresa, destino, asunto, html, log)
