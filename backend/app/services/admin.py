"""Lógica del panel de super-administración: empresas, usuarios y rubros."""

import datetime as dt

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import hash_clave, hash_senuelo, verificar_clave
from app.models import Empresa, Rubro, SuperAdmin, Usuario
from app.models.enums import RolUsuario


def autenticar_admin(db: Session, email: str, clave: str) -> SuperAdmin | None:
    """Valida las credenciales del super-admin (tiempo constante ante email inexistente)."""
    sa = db.scalar(select(SuperAdmin).where(SuperAdmin.email == email))
    # El señuelo tiene que costar lo MISMO que un hash real. El anterior
    # usaba 1 iteración contra las 390.000 reales, así que un email
    # inexistente respondía en microsegundos y uno real en ~230 ms: con una
    # sola muestra de curl se descubría cuál es la cuenta de super-admin.
    hash_guardado = sa.hash_clave if sa else hash_senuelo()
    ok = verificar_clave(clave, hash_guardado)
    if sa is None or not sa.activo or not ok:
        return None
    return sa


def listar_rubros(db: Session) -> list[Rubro]:
    return list(db.scalars(select(Rubro).order_by(Rubro.nombre)))


def listar_empresas(db: Session) -> list[Empresa]:
    """Empresas con su rubro y la cantidad de usuarios."""
    filas = db.execute(
        select(Empresa, Rubro.nombre, func.count(Usuario.id))
        .join(Rubro, Empresa.rubro_id == Rubro.id, isouter=True)
        .join(Usuario, Usuario.empresa_id == Empresa.id, isouter=True)
        .group_by(Empresa.id, Rubro.nombre)
        .order_by(Empresa.nombre)
    ).all()
    salida = []
    for empresa, rubro_nombre, cant in filas:
        empresa.rubro_nombre = rubro_nombre
        empresa.cantidad_usuarios = int(cant)
        from app.services.suscripcion import estado_suscripcion

        est = estado_suscripcion(empresa)
        empresa.estado_suscripcion = est["estado"]
        empresa.suscripcion_vence = est["vence"]
        empresa.prueba_hasta = (
            str(empresa.prueba_hasta) if empresa.prueba_hasta else None
        )
        salida.append(empresa)
    return salida


def setear_suscripcion(
    db: Session, empresa_id: int, plan, vence, renovar_30: bool
) -> Empresa:
    """Setea plan y/o vencimiento. renovar_30 = vence hoy + 30 días (atajo)."""
    import datetime as _dt

    empresa = _empresa_o_404(db, empresa_id)
    if plan is not None:
        empresa.plan = plan
    if renovar_30:
        empresa.suscripcion_vence = _dt.date.today() + _dt.timedelta(days=30)
        if empresa.plan == "gratuito":
            empresa.plan = "pro"
    elif vence is not None:
        empresa.suscripcion_vence = vence
    db.commit()
    db.refresh(empresa)
    # recalcular para la respuesta
    from app.services.suscripcion import estado_suscripcion

    est = estado_suscripcion(empresa)
    empresa.estado_suscripcion = est["estado"]
    empresa.prueba_hasta = str(empresa.prueba_hasta) if empresa.prueba_hasta else None
    empresa.suscripcion_vence = est["vence"]
    empresa.cantidad_usuarios = 0
    return empresa


def _empresa_o_404(db: Session, empresa_id: int) -> Empresa:
    empresa = db.get(Empresa, empresa_id)
    if empresa is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Empresa no encontrada")
    return empresa


def crear_empresa(db: Session, datos) -> Empresa:
    """Crea la empresa y, de una, su usuario dueño."""
    if db.scalar(select(Empresa).where(Empresa.slug == datos.slug)):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Ya existe una empresa con ese identificador (slug)"
        )
    rubro = db.get(Rubro, datos.rubro_id)
    if rubro is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rubro no encontrado")

    # El email del dueño se valida ACÁ, antes de crear nada. Si se validara
    # después, un email repetido dejaría la empresa creada y sin dueño: un
    # registro huérfano para limpiar a mano.
    if db.scalar(
        select(Usuario).where(func.lower(Usuario.email) == datos.dueno.email.lower())
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Ese email ya está en uso por otro usuario del sistema. Cada persona entra con una dirección propia: usá otra para el dueño de este negocio.",
        )

    # La prueba arranca al crear la empresa. Se guarda la fecha de fin, no los
    # días: así "faltan 3 días" se calcula siempre contra el calendario y no
    # depende de cuándo se corra ningún proceso.
    dias = int(getattr(datos, "dias_prueba", 0) or 0)
    prueba_hasta = dt.date.today() + dt.timedelta(days=dias) if dias > 0 else None

    # La cuota arranca en el precio de lista. Antes nacía en NULL y había que
    # acordarse de cargarla a mano: mientras estuviera vacía, el MRR y la deuda
    # del panel de cobranza contaban esa empresa como cero. Si el precio es
    # otro (piloto bonificado, descuento por referido), se edita en la ficha
    # comercial, que es donde corresponde decidirlo.
    empresa = Empresa(
        rubro_id=datos.rubro_id,
        nombre=datos.nombre,
        slug=datos.slug,
        config_pack={},
        prueba_hasta=prueba_hasta,
        precio_mensual=settings.precio_vigente,
    )
    db.add(empresa)
    db.flush()

    db.add(
        Usuario(
            empresa_id=empresa.id,
            nombre=datos.dueno.nombre,
            email=datos.dueno.email,
            hash_clave=hash_clave(datos.dueno.clave),
            rol=RolUsuario.DUENO,
        )
    )
    db.commit()
    db.refresh(empresa)
    empresa.rubro_nombre = rubro.nombre
    empresa.cantidad_usuarios = 1
    return empresa


def pausar_empresa(db: Session, empresa_id: int, activa: bool) -> Empresa:
    empresa = _empresa_o_404(db, empresa_id)
    empresa.activa = activa
    db.commit()
    db.refresh(empresa)
    rubro = db.get(Rubro, empresa.rubro_id)
    empresa.rubro_nombre = rubro.nombre if rubro else None
    empresa.cantidad_usuarios = (
        db.scalar(select(func.count(Usuario.id)).where(Usuario.empresa_id == empresa_id))
        or 0
    )
    return empresa


def listar_usuarios(db: Session, empresa_id: int) -> list[Usuario]:
    _empresa_o_404(db, empresa_id)
    return list(
        db.scalars(
            select(Usuario)
            .where(Usuario.empresa_id == empresa_id)
            .order_by(Usuario.nombre)
        )
    )


def crear_usuario(db: Session, empresa_id: int, datos) -> Usuario:
    _empresa_o_404(db, empresa_id)
    # El chequeo es GLOBAL, no por empresa: el email identifica a la
    # persona en todo el sistema. Antes se miraba solo dentro de la
    # empresa, así que crear un usuario con el email de alguien de OTRO
    # negocio pasaba sin problema... y dejaba a esa persona sin poder
    # entrar a su cuenta, sin ningún error a la vista.
    existe = db.scalar(
        select(Usuario).where(func.lower(Usuario.email) == datos.email.lower())
    )
    if existe:
        propia = existe.empresa_id == empresa_id
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Ya hay un usuario con ese email en este negocio."
            if propia
            else "Ese email ya está en uso en otro negocio del sistema. Cada persona entra con una dirección propia: usá otra.",
        )
    usuario = Usuario(
        empresa_id=empresa_id,
        nombre=datos.nombre,
        email=datos.email,
        hash_clave=hash_clave(datos.clave),
        rol=datos.rol,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def actualizar_usuario(db: Session, usuario_id: int, activo: bool) -> Usuario:
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    usuario.activo = activo
    db.commit()
    db.refresh(usuario)
    return usuario