"""Registro público: un negocio se da de alta solo, sin pasar por Leandro.

CÓMO ERA HASTA ACÁ
──────────────────
El alta la hacía el super-admin a mano, y la landing lo vendía como propuesta
de valor: *"No hay que crear cuentas ni configurar nada solo. El alta la
hacemos con vos, paso a paso."* Funciona con diez clientes y no escala a cien.

EL RIESGO QUE ABRE, Y CÓMO SE CIERRA
────────────────────────────────────
Un registro abierto es, para quien lo quiera usar mal, una fábrica de páginas
web gratis con el dominio de Turnos360. El freno no es pedir un email y
creerle: es que **la vidriera pública no se muestra hasta que el email esté
verificado**. Sin eso, publicar spam sale gratis; con eso, hay que sostener una
casilla real.

El panel, en cambio, se puede usar desde el segundo cero. Quien se registró de
verdad no queda esperando un email para poder probar el producto — que es el
momento exacto en el que la gente abandona.

Los otros dos frenos:
  · rate limit por IP en el endpoint (está en el router);
  · el email es único en todo el sistema, así que una casilla = un negocio.
"""

import datetime as dt
import hashlib
import logging
import secrets

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import hash_clave
from app.models import Empresa, Rubro, Usuario
from app.models.enums import RolUsuario

log = logging.getLogger("turnos360.registro")

# Cuánto vive el link de verificación. Largo a propósito: quien se registra un
# viernes a la noche tiene que poder confirmar el lunes sin volver a pedirlo.
HORAS_VERIFICACION = 72


def _nuevo_token(usuario: Usuario) -> str:
    """Genera el token y guarda SOLO su hash, igual que el de contraseña.

    Si la base se filtrara, los hashes no sirven para verificar nada.
    """
    token = secrets.token_urlsafe(32)
    usuario.verif_token_hash = hashlib.sha256(token.encode()).hexdigest()
    usuario.verif_token_expira = dt.datetime.now(dt.timezone.utc) + dt.timedelta(
        hours=HORAS_VERIFICACION
    )
    return token


def registrar(db: Session, datos) -> tuple[Empresa, Usuario, str]:
    """Crea la empresa, su dueño y el token de verificación, todo junto.

    Devuelve (empresa, dueño, token) — el token lo manda por email el llamador.

    El orden de validación importa y es el mismo que usa el alta del
    super-admin: se chequea TODO antes de escribir nada. Si el email estuviera
    repetido y lo validáramos después, quedaría una empresa creada y sin dueño,
    que es un registro huérfano para limpiar a mano.
    """
    if db.scalar(select(Empresa.id).where(Empresa.slug == datos.slug)):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f'La dirección "{datos.slug}" ya está ocupada. Probá con otra.',
        )

    rubro = db.scalar(select(Rubro).where(Rubro.codigo == datos.rubro_codigo))
    if rubro is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ese rubro no existe.")

    if db.scalar(
        select(Usuario.id).where(func.lower(Usuario.email) == datos.email.lower())
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Ya hay una cuenta con ese email. Si es tuya, iniciá sesión.",
        )

    hoy = dt.date.today()
    empresa = Empresa(
        nombre=datos.nombre_negocio.strip(),
        slug=datos.slug,
        rubro_id=rubro.id,
        config_pack={},
        prueba_hasta=hoy + dt.timedelta(days=settings.dias_prueba_registro),
        precio_mensual=settings.precio_vigente,
        de_registro_publico=True,
    )
    db.add(empresa)
    db.flush()

    dueno = Usuario(
        empresa_id=empresa.id,
        nombre=datos.nombre.strip(),
        email=datos.email,
        hash_clave=hash_clave(datos.clave),
        rol=RolUsuario.DUENO,
    )
    db.add(dueno)
    db.flush()

    token = _nuevo_token(dueno)
    db.commit()
    db.refresh(empresa)
    db.refresh(dueno)
    log.info(
        "registro público",
        extra={"empresa_id": empresa.id, "slug": empresa.slug},
    )
    return empresa, dueno, token


def verificar(db: Session, token: str) -> Usuario:
    """Marca el email como verificado. El token sirve una sola vez."""
    token_hash = hashlib.sha256((token or "").encode()).hexdigest()
    usuario = db.scalar(
        select(Usuario).where(Usuario.verif_token_hash == token_hash)
    )
    ahora = dt.datetime.now(dt.timezone.utc)
    if usuario is None or (
        usuario.verif_token_expira is not None and usuario.verif_token_expira < ahora
    ):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Ese link no sirve o ya venció. Pedí uno nuevo desde tu panel.",
        )

    usuario.email_verificado = True
    usuario.verif_token_hash = None
    usuario.verif_token_expira = None
    db.commit()
    db.refresh(usuario)
    return usuario


def reenviar(db: Session, usuario: Usuario) -> str | None:
    """Token nuevo para quien no recibió el primero. None si ya está verificado."""
    if usuario.email_verificado:
        return None
    token = _nuevo_token(usuario)
    db.commit()
    return token


def empresa_verificada(db: Session, empresa_id: int) -> bool:
    """¿Esta empresa puede mostrar su vidriera pública?

    Se pregunta por el dueño y no por una bandera en la empresa: la
    verificación es de una persona y de una casilla, no de un negocio. Un
    negocio con dos dueños queda habilitado si al menos uno confirmó.
    """
    return (
        db.scalar(
            select(Usuario.id).where(
                Usuario.empresa_id == empresa_id,
                Usuario.rol == RolUsuario.DUENO,
                Usuario.email_verificado.is_(True),
            )
        )
        is not None
    )
