"""Seed base: super-admin + catálogo de rubros (bootstrap del sistema).

Crea SOLO lo que no se puede crear desde la app: el super-administrador (para
entrar al panel /admin) y los rubros disponibles con sus presets. Las EMPRESAS
y los USUARIOS se crean desde el panel de administración. Idempotente.

Credenciales del super-admin: SUPERADMIN_EMAIL / SUPERADMIN_PASS por variable
de entorno. En desarrollo, si faltan, queda admin@turnos360.com / superadmin360.
En PRODUCCIÓN, SUPERADMIN_PASS es obligatoria: este usuario controla el alta de
empresas, la pausa de tenants y las suscripciones de todo el SaaS — no puede
nacer con una clave conocida.

Uso (dentro del contenedor):
    docker compose -f infra/docker-compose.yml exec backend python -m app.seeds_minimo
"""

import argparse
import os

from app.core.claves import ClaveDebil, revisar_clave_superadmin
from app.core.config import settings
from app.core.crypto import hash_clave
from app.db.session import SessionLocal
from app.models import Rubro, SuperAdmin
from app.seeds import (
    PRESET_BARBERIA,
    PRESET_ESTETICA,
    PRESET_MEDICO,
    PRESET_NUTRICION,
    PRESET_SPA,
    PRESET_UNAS,
)

RUBROS = [
    ("barberia", "Barbería / Peluquería", PRESET_BARBERIA),
    ("medico", "Consultorio médico", PRESET_MEDICO),
    ("nutricion", "Nutrición", PRESET_NUTRICION),
    ("unas", "Centro de uñas / Manicura", PRESET_UNAS),
    ("estetica", "Centro de estética", PRESET_ESTETICA),
    ("spa", "Spa & Masajes", PRESET_SPA),
]

EMAIL_DEV = "admin@turnos360.com"
CLAVE_DEV = "superadmin360"


def run(rotar_clave: bool = False) -> None:
    """Crea el super-admin y los rubros. Idempotente.

    rotar_clave: cambia la clave del super-admin que YA existe. Es explícito a
    propósito —una bandera, no el comportamiento por defecto— porque el resto
    del tiempo este seed tiene que poder correrse sin miedo a pisar nada.

    Existe porque no había NINGUNA forma de cambiar esa clave: el panel no
    tiene pantalla para eso y el seed solo creaba el usuario si no existía. Una
    clave que no se puede rotar es una clave que, el día que se filtre, hay
    que arreglar a mano contra la base de producción.
    """
    email = (os.environ.get("SUPERADMIN_EMAIL") or EMAIL_DEV).strip() or EMAIL_DEV
    clave = (os.environ.get("SUPERADMIN_PASS") or "").strip()
    clave_es_dev = not clave

    if clave_es_dev:
        if settings.es_produccion:
            raise SystemExit(
                "SUPERADMIN_PASS sin configurar en producción. Este usuario "
                "controla todo el SaaS: seteá SUPERADMIN_EMAIL y SUPERADMIN_PASS "
                "(clave fuerte) antes de correr el seed."
            )
        clave = CLAVE_DEV  # SOLO desarrollo

    # En producción la clave se revisa de verdad. Antes alcanzaba con que no
    # estuviera vacía: SUPERADMIN_PASS=1234 pasaba sin chistar, y este usuario
    # controla el alta de TODAS las empresas, la pausa de cualquier negocio y
    # las suscripciones del SaaS entero.
    #
    # Se revisa en producción y también cuando se rota a mano, que son los dos
    # momentos en que alguien elige esta clave. En desarrollo no molesta.
    if settings.es_produccion or rotar_clave:
        try:
            revisar_clave_superadmin(clave, email)
        except ClaveDebil as e:
            raise SystemExit(f"SUPERADMIN_PASS: {e}") from e

    db = SessionLocal()
    try:
        # Super-administrador (para entrar al panel /admin)
        existente = db.query(SuperAdmin).filter_by(email=email).first()
        if existente is None:
            db.add(
                SuperAdmin(
                    nombre="Leandro",
                    email=email,
                    hash_clave=hash_clave(clave),
                )
            )
            rotada = False
        elif rotar_clave:
            existente.hash_clave = hash_clave(clave)
            rotada = True
        else:
            rotada = False

        # Catálogo de rubros (con sus presets de terminología/módulos)
        for codigo, nombre, preset in RUBROS:
            if db.query(Rubro).filter_by(codigo=codigo).first() is None:
                db.add(Rubro(codigo=codigo, nombre=nombre, preset=preset))

        db.commit()
        print("Seed base OK.")
        if rotada:
            print(f"  Clave de {email} ROTADA. La anterior ya no sirve.")
        elif rotar_clave:
            print(f"  No existía {email}: se creó con la clave de SUPERADMIN_PASS.")
        if clave_es_dev:
            print(f"  Super-admin: {email} / {CLAVE_DEV}  (clave de DESARROLLO)")
        else:
            print(f"  Super-admin: {email}  (con la clave de SUPERADMIN_PASS)")
        print(
            "  Rubros disponibles: barbería, médico, nutrición, uñas, "
            "estética, spa"
        )
        print("  Entrá al panel /admin para crear tus empresas y usuarios.")
    finally:
        db.close()


if __name__ == "__main__":
    _p = argparse.ArgumentParser(description="Seed base de Turnos360.")
    _p.add_argument(
        "--rotar-clave",
        action="store_true",
        help=(
            "Cambia la clave del super-admin que ya existe por la de "
            "SUPERADMIN_PASS. Sin esto, un super-admin existente no se toca."
        ),
    )
    run(rotar_clave=_p.parse_args().rotar_clave)
