"""Autogestión del turno: el cliente lo cambia o lo cancela desde el email.

POR QUÉ
───────
La regla «Permitir que cancelen o reprogramen» existía en Reglas de reserva,
pero no había ninguna pantalla donde el cliente pudiera hacerlo: el email
decía «contactá al negocio». El que no podía ir, simplemente no iba. Con un
link en la confirmación y en el recordatorio, el horario se libera solo y
otro lo puede reservar.

EL LINK
───────
El token es un HMAC (con SECRET_KEY) de «id del turno + versión». Así:

- es impredecible y no expone el id del turno;
- es estable: el email de confirmación y el del recordatorio llevan el MISMO
  link, y el viejo no deja de servir por mandar otro email;
- se revoca sumando 1 a `turno.gestion_version`.

En la base se guarda solo el SHA-256 del token (para encontrar el turno);
nunca el token.

Vigencia:
- ver el turno: hasta 24 h después de que termina;
- cambiar o cancelar: hasta la hora del turno, si la regla del negocio lo
  permite y el turno sigue pendiente o confirmado. Es un link de varios usos
  controlados: después de cancelar sigue mostrando el turno (cancelado), pero
  no deja hacer nada más.

Toda la lógica de reservas es la de siempre: el cambio pasa por
`turno.mover` (disponibilidad, candado de agenda, email al cliente) y la
cancelación por `turno.cambiar_estado`. Acá solo se suman los controles que
corresponden a un cliente sin cuenta.
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import logging

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.reloj import ahora_de_pared
from app.models import Cliente, Empresa, LogAuditoria, Recurso, Servicio
from app.models.enums import EstadoTurno
from app.models.organizacion import Sucursal
from app.models.turno import Turno
from app.services import auditoria
from app.services import disponibilidad as disp

log = logging.getLogger(__name__)

# Cuántas veces puede mover el mismo turno el cliente desde el link. Sin
# tope, un link reenviado podría pasear el turno por toda la agenda.
MAX_CAMBIOS = 3
# Cuánto después de terminado el turno se sigue pudiendo VER.
VER_HASTA_DESPUES = dt.timedelta(hours=24)
ESTADOS_GESTIONABLES = (EstadoTurno.PENDIENTE, EstadoTurno.CONFIRMADO)

_NO_VALIDO = HTTPException(
    status.HTTP_404_NOT_FOUND,
    "Este link no es válido. Revisá que esté completo o pedile uno nuevo al negocio.",
)


# ── El token ──────────────────────────────────────────────────────────────

def _token(turno: Turno) -> str:
    firma = hmac.new(
        settings.secret_key.encode(),
        f"gestion-turno:{turno.id}:{int(turno.gestion_version or 0)}".encode(),
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(firma).decode().rstrip("=")


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def emitir_link(db: Session, turno: Turno) -> str:
    """URL del link de autogestión de este turno. Hace flush, no commit."""
    token = _token(turno)
    h = _hash(token)
    if turno.gestion_token_hash != h:
        turno.gestion_token_hash = h
        db.flush()
    base = settings.public_base_url.rstrip("/")
    return f"{base}/gestionar/{token}"


def revocar_link(db: Session, turno: Turno) -> None:
    """El link que estaba en los emails deja de servir. No hace commit."""
    turno.gestion_version = int(turno.gestion_version or 0) + 1
    turno.gestion_token_hash = None
    db.flush()


def link_si_corresponde(db: Session, turno: Turno, empresa: Empresa) -> str | None:
    """El link para un email, solo si el negocio deja cambiar o cancelar y el
    turno todavía se puede gestionar. Nunca rompe el email."""
    try:
        if not empresa.reserva_permite_cancelar:
            return None
        if turno.estado not in ESTADOS_GESTIONABLES:
            return None
        return emitir_link(db, turno)
    except Exception:
        log.exception("No se pudo emitir el link de autogestión (turno %s)", turno.id)
        return None


def _turno_de(db: Session, token: str, *, para_actuar: bool = False) -> Turno:
    if not token or len(token) > 100:
        raise _NO_VALIDO
    q = select(Turno).where(Turno.gestion_token_hash == _hash(token))
    if para_actuar:
        q = q.with_for_update()
    turno = db.scalar(q)
    # Comparación de tiempo constante contra el token esperado: si el hash
    # coincide pero la versión cambió (link revocado), no sirve.
    if turno is None or not hmac.compare_digest(_token(turno), token):
        raise _NO_VALIDO
    fin = turno.fecha_fin or turno.fecha_inicio
    if fin is None or ahora_de_pared() > fin + VER_HASTA_DESPUES:
        raise HTTPException(
            status.HTTP_410_GONE,
            "Este link ya venció: el turno ya pasó.",
        )
    return turno


# ── Qué se puede hacer ────────────────────────────────────────────────────

def _bloqueo(turno: Turno, empresa: Empresa) -> str | None:
    """Por qué el cliente NO puede tocar el turno (None = puede)."""
    if not empresa.activa:
        return "El negocio no está tomando cambios por este medio. Comunicate con ellos."
    if turno.estado == EstadoTurno.CANCELADO:
        return "Este turno ya está cancelado."
    if turno.estado not in ESTADOS_GESTIONABLES:
        return "Este turno ya no se puede cambiar desde acá."
    if turno.cobrado:
        return "Este turno ya tiene un cobro registrado. Para cambiarlo, comunicate con el negocio."
    if not empresa.reserva_permite_cancelar:
        return "Este negocio no toma cambios ni cancelaciones online. Comunicate con ellos."
    if turno.fecha_inicio is None or ahora_de_pared() >= turno.fecha_inicio:
        return "El turno ya empezó o ya pasó."
    return None


def _cambios_hechos(db: Session, turno: Turno) -> int:
    return int(
        db.scalar(
            select(func.count(LogAuditoria.id)).where(
                LogAuditoria.tabla == "turno",
                LogAuditoria.registro_id == turno.id,
                LogAuditoria.accion == "autogestion_mover",
            )
        )
        or 0
    )


def ver(db: Session, token: str) -> dict:
    turno = _turno_de(db, token)
    empresa = db.get(Empresa, turno.empresa_id)
    servicio = db.get(Servicio, turno.servicio_id) if turno.servicio_id else None
    recurso = db.get(Recurso, turno.recurso_id) if turno.recurso_id else None
    cliente = db.get(Cliente, turno.cliente_id)
    sucursal = db.get(Sucursal, turno.sucursal_id) if turno.sucursal_id else None
    bloqueo = _bloqueo(turno, empresa)
    cambios = _cambios_hechos(db, turno)
    return {
        "negocio": empresa.nombre,
        "slug": empresa.slug,
        "color_marca": empresa.color_marca,
        "logo_url": empresa.logo_url,
        "direccion": (sucursal.direccion if sucursal and sucursal.direccion else None)
        or empresa.direccion,
        "telefono": empresa.telefono_publico,
        # Solo el nombre de pila: quien tenga el link no ve teléfono ni email.
        "cliente": (cliente.nombre or "").split(" ")[0] if cliente else None,
        "servicio": servicio.nombre if servicio else "Turno",
        "profesional": recurso.nombre if recurso else None,
        "inicio": turno.fecha_inicio,
        "fin": turno.fecha_fin,
        "estado": turno.estado.value,
        "sena_estado": turno.sena_estado,
        "sena_monto": float(turno.sena_monto) if turno.sena_monto else None,
        "puede_cancelar": bloqueo is None,
        "puede_reprogramar": bloqueo is None and cambios < MAX_CAMBIOS and turno.servicio_id is not None,
        "motivo_bloqueo": bloqueo
        or (
            "Ya cambiaste este turno varias veces. Para otro cambio, comunicate con el negocio."
            if cambios >= MAX_CAMBIOS
            else None
        ),
    }


def horarios(db: Session, token: str, desde: dt.date, dias: int) -> list[dict]:
    """Los horarios libres para el MISMO servicio en el MISMO local."""
    from app.services import publico

    turno = _turno_de(db, token)
    empresa = db.get(Empresa, turno.empresa_id)
    if _bloqueo(turno, empresa) or not turno.servicio_id:
        return []
    return publico.huecos(
        db, empresa.slug, turno.servicio_id, None, desde, dias, sucursal_id=turno.sucursal_id
    )


def cancelar(db: Session, token: str, motivo: str | None, ip: str | None) -> dict:
    from app.schemas.turno import TurnoCambiarEstado
    from app.services import turno as turno_svc

    turno = _turno_de(db, token, para_actuar=True)
    empresa = db.get(Empresa, turno.empresa_id)
    bloqueo = _bloqueo(turno, empresa)
    if bloqueo:
        raise HTTPException(status.HTTP_409_CONFLICT, bloqueo)

    texto = "Cancelado por el cliente desde el link del email"
    if motivo and motivo.strip():
        texto = f"{texto}: {motivo.strip()}"[:300]
    auditoria.registrar(
        db,
        accion="autogestion_cancelar",
        empresa_id=turno.empresa_id,
        tabla="turno",
        registro_id=turno.id,
        detalle={"inicio": turno.fecha_inicio.isoformat(), "motivo": (motivo or "")[:200] or None},
        ip=ip,
    )
    turno_svc.cambiar_estado(
        db,
        turno.empresa_id,
        turno.id,
        TurnoCambiarEstado(estado=EstadoTurno.CANCELADO, motivo_cancelacion=texto),
    )
    _avisar_negocio(turno.id, "cancelacion", None)
    return ver(db, token)


def reprogramar(
    db: Session, token: str, inicio: dt.datetime, ip: str | None
) -> dict:
    from app.schemas.turno import TurnoMover
    from app.services import publico
    from app.services import turno as turno_svc

    turno = _turno_de(db, token, para_actuar=True)
    empresa = db.get(Empresa, turno.empresa_id)
    bloqueo = _bloqueo(turno, empresa)
    if bloqueo:
        raise HTTPException(status.HTTP_409_CONFLICT, bloqueo)
    if not turno.servicio_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Este turno no se puede cambiar desde acá.")
    if _cambios_hechos(db, turno) >= MAX_CAMBIOS:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Ya cambiaste este turno varias veces. Para otro cambio, comunicate con el negocio.",
        )
    # Si la suscripción del negocio está cortada, tampoco entra un cambio:
    # es lo mismo que una reserva nueva.
    publico.exigir_al_dia(empresa)
    publico._validar_ventana(inicio, empresa)
    if inicio == turno.fecha_inicio:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Elegí un horario distinto al que ya tenés.")

    servicio = db.get(Servicio, turno.servicio_id)
    if servicio is None or not servicio.activo:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ese servicio ya no se ofrece. Comunicate con el negocio.")
    fin = inicio + dt.timedelta(minutes=servicio.duracion_min)

    # Primero el mismo profesional; si no está libre, otro del MISMO local que
    # haga el servicio (es lo que se le ofreció en los horarios).
    elegibles = [
        r for r in publico._elegibles(servicio) if r.sucursal_id == turno.sucursal_id
    ]
    elegibles.sort(key=lambda r: r.id != turno.recurso_id)
    recurso = next(
        (
            r
            for r in elegibles
            if disp.esta_disponible(
                db, empresa.id, r.id, inicio, fin,
                excluir_turno_id=turno.id, grupo_agenda=servicio.grupo_agenda,
            )
        ),
        None,
    )
    if recurso is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ese horario ya no está disponible. Elegí otro.")

    antes = turno.fecha_inicio
    auditoria.registrar(
        db,
        accion="autogestion_mover",
        empresa_id=turno.empresa_id,
        tabla="turno",
        registro_id=turno.id,
        detalle={
            "de": antes.isoformat(),
            "a": inicio.isoformat(),
            "recurso_de": turno.recurso_id,
            "recurso_a": recurso.id,
        },
        ip=ip,
    )
    # mover() revalida el hueco con el candado de agenda, resetea los
    # recordatorios, hace commit y le avisa al cliente por email. Si el hueco
    # se ocupó en el medio, levanta 409 y la auditoría se revierte con todo.
    turno_svc.mover(
        db,
        turno.empresa_id,
        turno.id,
        TurnoMover(
            fecha_inicio=inicio,
            recurso_id=recurso.id if recurso.id != turno.recurso_id else None,
        ),
    )
    _avisar_negocio(turno.id, "reprogramacion", antes.isoformat())
    return ver(db, token)


def _avisar_negocio(turno_id: int, accion: str, antes_iso: str | None) -> None:
    try:
        from app.core.cola import encolar
        from app.tasks.emails import avisar_negocio_autogestion

        encolar(avisar_negocio_autogestion, turno_id, accion, antes_iso)
    except Exception:
        log.exception("No se pudo encolar el aviso al negocio (turno %s)", turno_id)
