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

import os

from app.core.config import settings
from app.core.crypto import hash_clave
from app.db.session import SessionLocal
from app.models import Rubro, SuperAdmin
from app.seeds import PRESET_BARBERIA, PRESET_MEDICO, PRESET_NUTRICION

RUBROS = [
    ("barberia", "Barbería / Peluquería", PRESET_BARBERIA),
    ("medico", "Consultorio médico", PRESET_MEDICO),
    ("nutricion", "Nutrición", PRESET_NUTRICION),
]

EMAIL_DEV = "admin@turnos360.com"
CLAVE_DEV = "superadmin360"


def run() -> None:
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

    db = SessionLocal()
    try:
        # Super-administrador (para entrar al panel /admin)
        if db.query(SuperAdmin).filter_by(email=email).first() is None:
            db.add(
                SuperAdmin(
                    nombre="Leandro",
                    email=email,
                    hash_clave=hash_clave(clave),
                )
            )

        # Catálogo de rubros (con sus presets de terminología/módulos)
        for codigo, nombre, preset in RUBROS:
            if db.query(Rubro).filter_by(codigo=codigo).first() is None:
                db.add(Rubro(codigo=codigo, nombre=nombre, preset=preset))

        db.commit()
        print("Seed base OK.")
        if clave_es_dev:
            print(f"  Super-admin: {email} / {CLAVE_DEV}  (clave de DESARROLLO)")
        else:
            print(f"  Super-admin: {email}  (con la clave de SUPERADMIN_PASS)")
        print("  Rubros disponibles: barbería, médico, nutrición")
        print("  Entrá al panel /admin para crear tus empresas y usuarios.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
