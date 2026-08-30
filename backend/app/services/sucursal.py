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

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Empresa, Sucursal


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
