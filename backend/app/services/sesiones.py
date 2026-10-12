"""Sesiones de los usuarios del panel: alta, validación, renovación y cierre.

Cómo encaja con lo que ya había
───────────────────────────────
- `usuario.token_version` sigue siendo el «cerrar todo»: subirlo invalida
  cualquier token emitido antes, tenga o no sesión. Las funciones de acá que
  cierran todo además marcan las filas, para que la lista diga la verdad.
- Los tokens emitidos ANTES de este cambio no traen `sid`. Se aceptan como
  siempre (firma + token_version) hasta que el panel los renueve: el refresh
  de un token viejo crea una sesión nueva, así que en minutos (lo que dura un
  access) toda pestaña abierta queda con sesión. No hace falta echar a nadie.

Estados que se muestran (`estado_de`):
- «activa»: no revocada, no vencida y con la token_version vigente.
- «revocada»: alguien la cerró (el usuario, un admin, el sistema). Con motivo.
- «invalidada»: un cambio de clave o un «cerrar todo» la dejó sin efecto
  antes de que existiera la marca (o sin pasar por acá).
- «vencida»: pasó la vida del refresh sin renovarse.
"""

from __future__ import annotations

import datetime as dt
import re
import secrets

from fastapi import HTTPException, Request, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.seguridad import crear_access_token, crear_refresh_token
from app.models import SesionUsuario, Usuario

# Cada cuánto se escribe el «último uso». Escribir en cada request sería una
# escritura por clic; con un minuto alcanza para saber si alguien está usando
# la cuenta.
TOQUE_CADA = dt.timedelta(seconds=60)
# Margen para el refresh anterior: dos pestañas que renuevan a la vez con el
# mismo refresh no deben echar al usuario.
GRACIA_REFRESH = dt.timedelta(seconds=30)


def _ahora() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


# ── Dispositivo ────────────────────────────────────────────────────────────

_NAVEGADORES = (
    (r"Edg(?:e|A|iOS)?/", "Edge"),
    (r"OPR/|Opera", "Opera"),
    (r"SamsungBrowser/", "Samsung Internet"),
    (r"Firefox/|FxiOS/", "Firefox"),
    (r"Chrome/|CriOS/", "Chrome"),
    (r"Safari/", "Safari"),
)
_SISTEMAS = (
    (r"iPhone|iPad|iPod", "iOS"),
    (r"Android", "Android"),
    (r"Windows", "Windows"),
    (r"Mac OS X|Macintosh", "macOS"),
    (r"CrOS", "ChromeOS"),
    (r"Linux", "Linux"),
)


def dispositivo_de(user_agent: str | None) -> str | None:
    """«Chrome en Android». Solo la etiqueta: el user-agent completo no se guarda."""
    ua = (user_agent or "")[:400]
    if not ua:
        return None
    nav = next((n for p, n in _NAVEGADORES if re.search(p, ua)), None)
    so = next((n for p, n in _SISTEMAS if re.search(p, ua)), None)
    if nav and so:
        return f"{nav} en {so}"
    return nav or so or "Otro dispositivo"


# ── Alta y emisión ────────────────────────────────────────────────────────

def crear(db: Session, usuario: Usuario, request: Request | None) -> SesionUsuario:
    """Sesión nueva para un ingreso. No hace commit."""
    ahora = _ahora()
    sesion = SesionUsuario(
        usuario_id=usuario.id,
        empresa_id=usuario.empresa_id,
        sid=secrets.token_hex(16),
        creada_en=ahora,
        ultimo_uso_en=ahora,
        expira_en=ahora + dt.timedelta(days=settings.refresh_token_dias),
        dispositivo=dispositivo_de(request.headers.get("user-agent") if request else None),
        token_version=int(usuario.token_version or 0),
    )
    db.add(sesion)
    db.flush()
    return sesion


def tokens(usuario: Usuario, sesion: SesionUsuario) -> tuple[str, str]:
    """Par access + refresh para la sesión. Rota el jti del refresh. No hace commit."""
    jti = secrets.token_hex(16)
    if sesion.refresh_jti:
        sesion.refresh_jti_anterior = sesion.refresh_jti
        sesion.rotado_en = _ahora()
    sesion.refresh_jti = jti
    tv = int(usuario.token_version or 0)
    access = crear_access_token(usuario.id, usuario.empresa_id, usuario.rol.value, tv, sid=sesion.sid)
    refresh = crear_refresh_token(
        usuario.id, usuario.empresa_id, usuario.rol.value, tv, sid=sesion.sid, jti=jti
    )
    return access, refresh


def ingresar(db: Session, usuario: Usuario, request: Request | None) -> tuple[str, str]:
    """Login exitoso: sesión nueva + último ingreso. Hace commit."""
    sesion = crear(db, usuario, request)
    usuario.ultimo_ingreso_en = sesion.creada_en
    par = tokens(usuario, sesion)
    db.commit()
    return par


# ── Validación ────────────────────────────────────────────────────────────

def _viva(sesion: SesionUsuario | None, usuario: Usuario, ahora: dt.datetime) -> bool:
    return (
        sesion is not None
        and sesion.usuario_id == usuario.id
        and sesion.revocada_en is None
        and sesion.expira_en > ahora
        and int(sesion.token_version or 0) == int(usuario.token_version or 0)
    )


def validar_acceso(db: Session, usuario: Usuario, payload: dict) -> SesionUsuario | None:
    """Comprueba la sesión del access token. Lanza 401 si está cerrada.

    Devuelve None para los tokens viejos sin `sid` (ver el docstring del módulo).
    """
    sid = payload.get("sid")
    if not sid:
        return None
    ahora = _ahora()
    sesion = db.scalar(select(SesionUsuario).where(SesionUsuario.sid == str(sid)))
    if not _viva(sesion, usuario, ahora):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Credenciales inválidas",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if sesion.ultimo_uso_en is None or ahora - sesion.ultimo_uso_en > TOQUE_CADA:
        # UPDATE condicionado: dos requests en paralelo no se pisan ni piden
        # un lock sobre la fila.
        db.execute(
            update(SesionUsuario)
            .where(SesionUsuario.id == sesion.id)
            .values(ultimo_uso_en=ahora)
        )
        db.commit()
    return sesion


def renovar(db: Session, usuario: Usuario, payload: dict, request: Request | None) -> tuple[str, str]:
    """Refresh. Con sesión: la sesión tiene que seguir viva y el refresh ser
    el último emitido. Sin sesión (token viejo): se le crea una. Hace commit."""
    ahora = _ahora()
    sid = payload.get("sid")
    if not sid:
        sesion = crear(db, usuario, request)
        par = tokens(usuario, sesion)
        db.commit()
        return par

    no = HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token inválido o vencido")
    sesion = db.scalar(select(SesionUsuario).where(SesionUsuario.sid == str(sid)))
    if not _viva(sesion, usuario, ahora):
        raise no
    jti = payload.get("jti")
    vigente = jti is not None and jti == sesion.refresh_jti
    reciente = (
        jti is not None
        and jti == sesion.refresh_jti_anterior
        and sesion.rotado_en is not None
        and ahora - sesion.rotado_en <= GRACIA_REFRESH
    )
    if not (vigente or reciente):
        # Un refresh viejo que vuelve a aparecer después de rotar es la señal
        # típica de un token robado: se cierra la sesión entera.
        revocar(db, sesion, "Se reutilizó un refresh anterior", "sistema")
        db.commit()
        raise no
    sesion.ultimo_uso_en = ahora
    sesion.expira_en = ahora + dt.timedelta(days=settings.refresh_token_dias)
    par = tokens(usuario, sesion)
    db.commit()
    return par


# ── Cierre ────────────────────────────────────────────────────────────────

def revocar(db: Session, sesion: SesionUsuario, motivo: str, por: str) -> bool:
    """Cierra una sesión. Devuelve False si ya estaba cerrada. No hace commit."""
    if sesion.revocada_en is not None:
        return False
    sesion.revocada_en = _ahora()
    sesion.motivo_revocacion = (motivo or "")[:160] or None
    sesion.revocada_por = (por or "")[:160] or None
    db.flush()
    return True


def revocar_todas(
    db: Session, usuario: Usuario, motivo: str, por: str, *, subir_version: bool = True
) -> int:
    """Cierra todas las sesiones del usuario. Con `subir_version`, además
    invalida los tokens viejos sin sesión. No hace commit."""
    ahora = _ahora()
    n = db.execute(
        update(SesionUsuario)
        .where(SesionUsuario.usuario_id == usuario.id, SesionUsuario.revocada_en.is_(None))
        .values(revocada_en=ahora, motivo_revocacion=motivo[:160], revocada_por=por[:160])
    ).rowcount
    if subir_version:
        usuario.token_version = int(usuario.token_version or 0) + 1
    db.flush()
    return int(n or 0)


def cerrar_actual(db: Session, usuario: Usuario, payload: dict) -> None:
    """Logout: cierra la sesión del token con el que se llamó. Hace commit."""
    sid = payload.get("sid")
    if not sid:
        return
    sesion = db.scalar(
        select(SesionUsuario).where(
            SesionUsuario.sid == str(sid), SesionUsuario.usuario_id == usuario.id
        )
    )
    if sesion is not None and revocar(db, sesion, "Cerró sesión", "usuario"):
        db.commit()


# ── Lectura ───────────────────────────────────────────────────────────────

def estado_de(sesion: SesionUsuario, usuario: Usuario, ahora: dt.datetime | None = None) -> str:
    ahora = ahora or _ahora()
    if sesion.revocada_en is not None:
        return "revocada"
    if int(sesion.token_version or 0) != int(usuario.token_version or 0):
        return "invalidada"
    if sesion.expira_en <= ahora:
        return "vencida"
    if not usuario.activo:
        return "invalidada"
    return "activa"


def a_dict(sesion: SesionUsuario, usuario: Usuario, ahora: dt.datetime | None = None) -> dict:
    return {
        "id": sesion.id,
        "creada_en": sesion.creada_en.isoformat() if sesion.creada_en else None,
        "ultimo_uso_en": sesion.ultimo_uso_en.isoformat() if sesion.ultimo_uso_en else None,
        "expira_en": sesion.expira_en.isoformat() if sesion.expira_en else None,
        "dispositivo": sesion.dispositivo,
        "estado": estado_de(sesion, usuario, ahora),
        "revocada_en": sesion.revocada_en.isoformat() if sesion.revocada_en else None,
        "motivo": sesion.motivo_revocacion,
        "revocada_por": sesion.revocada_por,
    }


def de_usuario(db: Session, usuario: Usuario, limite: int = 50) -> list[SesionUsuario]:
    return list(
        db.scalars(
            select(SesionUsuario)
            .where(SesionUsuario.usuario_id == usuario.id)
            .order_by(SesionUsuario.creada_en.desc(), SesionUsuario.id.desc())
            .limit(limite)
        )
    )
