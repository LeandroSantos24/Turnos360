"""Sucursales (E16, paso 1 de multisucursal).

La decisión de diseño que ordena todo este módulo: **ninguna empresa tiene
cero sucursales**. Se le crea una en el alta, llamada como el negocio, y los
datos históricos se migraron a ella.

El motivo es evitar dos caminos de código. Si `sucursal_id` pudiera ser NULL,
cada consulta de agenda, caja y disponibilidad necesitaría un
`OR sucursal_id IS NULL` para no perder los datos viejos — y esa segunda rama,
la que casi nunca se ejecuta, es donde se esconden los bugs. Con la regla de
"nunca cero", todo filtra por sucursal siempre, sin ramas.

Lo que protege al plan de entrada no está acá sino en la interfaz: el menú de
sucursales y los selectores solo aparecen cuando la empresa tiene más de una.
Un negocio de un solo local nunca ve la palabra "sucursal", aunque por debajo
el código ya sea multisucursal.
"""

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import planes
from app.models import Empresa, Recurso, Sucursal
from app.models.enums import TipoRecurso


def crear_principal(db: Session, empresa: Empresa) -> Sucursal:
    """La sucursal que nace con la empresa. Hace flush para que quede el id.

    Se llama como el negocio y no "Principal" a secas: el día que el dueño
    agregue un segundo local, el selector va a decir "Barbería El Faro" y
    "Centro", que se entiende sin explicación. El nombre es editable.

    Hereda la dirección y el teléfono público de la empresa cuando están
    cargados, así el primer local no nace vacío.
    """
    sucursal = Sucursal(
        empresa_id=empresa.id,
        nombre=(empresa.nombre or "Principal")[:120],
        direccion=empresa.direccion,
        activa=True,
    )
    db.add(sucursal)
    db.flush()
    return sucursal


def principal_de(db: Session, empresa_id: int) -> Sucursal | None:
    """La sucursal por defecto: la más vieja que siga activa.

    Es la que se usa cuando algo se crea sin decir en qué local va. Para una
    empresa de un solo local es "la" sucursal; para una de varios es la
    original, que es la respuesta menos sorpresiva.
    """
    return db.scalars(
        select(Sucursal)
        .where(Sucursal.empresa_id == empresa_id, Sucursal.activa.is_(True))
        .order_by(Sucursal.id)
        .limit(1)
    ).first()


def id_principal(db: Session, empresa_id: int) -> int:
    """El id de la sucursal por defecto, creándola si la empresa no tiene.

    El fallback no debería hacer falta nunca (la migración dejó una por
    empresa y el alta crea la suya). Está igual porque la alternativa es que
    un alta explote con un IntegrityError de NOT NULL, y eso le rompe el día
    a alguien por un invariante que este módulo puede reparar solo.
    """
    sucursal = principal_de(db, empresa_id)
    if sucursal is not None:
        return sucursal.id

    empresa = db.get(Empresa, empresa_id)
    if empresa is None:
        # Que falle donde corresponde: el problema es la empresa, no la sucursal.
        raise ValueError(f"No existe la empresa {empresa_id}")
    return crear_principal(db, empresa).id


def cuantas(db: Session, empresa_id: int) -> int:
    """Cuántos locales activos tiene. La interfaz lo usa para decidir si
    muestra o esconde todo lo de sucursales."""
    return len(
        list(
            db.scalars(
                select(Sucursal.id).where(
                    Sucursal.empresa_id == empresa_id, Sucursal.activa.is_(True)
                )
            )
        )
    )


# ══════════════════════════════════════════════════════════════════════
#  ABM (paso 2). Todo esto solo se ve cuando el plan permite más de un local.
# ══════════════════════════════════════════════════════════════════════


def _fila(db: Session, sucursal: Sucursal, principal_id: int | None) -> dict:
    """Una sucursal con lo que la pantalla necesita para decidir qué ofrecer."""
    cuantos = db.scalar(
        select(func.count(Recurso.id)).where(
            Recurso.sucursal_id == sucursal.id,
            Recurso.tipo == TipoRecurso.PERSONA,
            Recurso.activo.is_(True),
        )
    )
    return {
        "id": sucursal.id,
        "nombre": sucursal.nombre,
        "direccion": sucursal.direccion,
        "telefono": sucursal.telefono,
        "activa": sucursal.activa,
        "profesionales": int(cuantos or 0),
        "es_principal": sucursal.id == principal_id,
    }


def listar(db: Session, empresa_id: int) -> dict:
    """Los locales del negocio, activos e inactivos, con el cupo del plan.

    Los inactivos siguen apareciendo a propósito: un local cerrado tiene
    historia (turnos, caja, arqueos) y esconderlo haría creer que esa plata
    desapareció.
    """
    todas = list(
        db.scalars(
            select(Sucursal)
            .where(Sucursal.empresa_id == empresa_id)
            .order_by(Sucursal.id)
        )
    )
    principal = principal_de(db, empresa_id)
    empresa = db.get(Empresa, empresa_id)
    return {
        "sucursales": [_fila(db, s, principal.id if principal else None) for s in todas],
        "tope": planes.tope_sucursales(
            empresa.plan if empresa else None,
            empresa.limite_sucursales if empresa else None,
        ),
        "usadas": sum(1 for s in todas if s.activa),
        "plan_etiqueta": planes.limites_de(empresa.plan if empresa else None).etiqueta,
    }


def _validar_cupo(db: Session, empresa_id: int) -> None:
    """El tope de locales del plan, aplicado al crear y al reactivar.

    Se cuentan solo los ACTIVOS: un local cerrado no ocupa lugar, igual que un
    profesional desactivado no ocupa asiento.
    """
    empresa = db.get(Empresa, empresa_id)
    tope = planes.tope_sucursales(
        empresa.plan if empresa else None,
        empresa.limite_sucursales if empresa else None,
    )
    usadas = cuantas(db, empresa_id)
    if usadas < tope:
        return

    lim = planes.limites_de(empresa.plan if empresa else None)
    raise HTTPException(
        status.HTTP_409_CONFLICT,
        f"Tu plan {lim.etiqueta} incluye "
        f"{tope} {'local' if tope == 1 else 'locales'} y ya "
        f"{'lo tenés' if tope == 1 else 'los tenés'} en uso. Para sumar otro, "
        "pasá al plan Multi desde «Mi suscripción».",
    )


def _de_la_empresa(db: Session, empresa_id: int, sucursal_id: int) -> Sucursal:
    sucursal = db.get(Sucursal, sucursal_id)
    if sucursal is None or sucursal.empresa_id != empresa_id:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Ese local no existe en este negocio."
        )
    return sucursal


def crear(db: Session, empresa_id: int, datos) -> dict:
    _validar_cupo(db, empresa_id)
    sucursal = Sucursal(
        empresa_id=empresa_id,
        nombre=datos.nombre,
        direccion=datos.direccion,
        telefono=datos.telefono,
        activa=True,
    )
    db.add(sucursal)
    db.commit()
    db.refresh(sucursal)
    principal = principal_de(db, empresa_id)
    return _fila(db, sucursal, principal.id if principal else None)


def editar(db: Session, empresa_id: int, sucursal_id: int, datos) -> dict:
    sucursal = _de_la_empresa(db, empresa_id, sucursal_id)
    cambios = datos.model_dump(exclude_unset=True)

    if cambios.get("activa") is False and sucursal.activa:
        _validar_baja(db, empresa_id, sucursal)
    if cambios.get("activa") is True and not sucursal.activa:
        _validar_cupo(db, empresa_id)

    for campo, valor in cambios.items():
        # nombre en None sería un local sin nombre: se ignora, como en el resto
        # del sistema. dirección y teléfono SÍ se pueden vaciar.
        if campo == "nombre" and valor is None:
            continue
        setattr(sucursal, campo, valor)

    db.commit()
    db.refresh(sucursal)
    principal = principal_de(db, empresa_id)
    return _fila(db, sucursal, principal.id if principal else None)


def _validar_baja(db: Session, empresa_id: int, sucursal: Sucursal) -> None:
    """Dos candados antes de cerrar un local.

    1. No puede quedar el negocio sin ningún local activo. Es el invariante de
       todo el paso 1: si llega a cero, las altas siguientes no tienen dónde
       caer y empiezan a fallar con un error de base que no explica nada.
    2. No se cierra un local que todavía tiene gente trabajando. El profesional
       no desaparecería de la base, pero sí de la agenda y de la caja, y sus
       turnos futuros quedarían en un local cerrado. Es más honesto pedir que
       los muevan primero que dejar que se enteren la semana que viene.
    """
    if cuantas(db, empresa_id) <= 1:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Es el único local activo del negocio y no se puede cerrar: la "
            "agenda, la caja y las altas necesitan uno. Si te mudaste, "
            "editale el nombre y la dirección en vez de cerrarlo.",
        )

    ocupados = db.scalar(
        select(func.count(Recurso.id)).where(
            Recurso.sucursal_id == sucursal.id,
            Recurso.tipo == TipoRecurso.PERSONA,
            Recurso.activo.is_(True),
        )
    )
    if ocupados:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"«{sucursal.nombre}» todavía tiene "
            f"{ocupados} {'profesional' if ocupados == 1 else 'profesionales'} "
            "en actividad. Movelos a otro local (o desactivalos) antes de "
            "cerrarlo, para que no queden turnos colgados de un local cerrado.",
        )
