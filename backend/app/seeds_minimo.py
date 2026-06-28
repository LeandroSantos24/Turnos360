"""Seed base: super-admin + catálogo de rubros (bootstrap del sistema).

Crea SOLO lo que no se puede crear desde la app: el super-administrador (para
entrar al panel /admin) y los rubros disponibles con sus presets. Las EMPRESAS
y los USUARIOS se crean desde el panel de administración. Idempotente.

Uso (dentro del contenedor):
    docker compose -f infra/docker-compose.yml exec backend python -m app.seeds_minimo
"""

from app.core.crypto import hash_clave
from app.db.session import SessionLocal
from app.models import Rubro, SuperAdmin
from app.seeds import PRESET_BARBERIA, PRESET_MEDICO

RUBROS = [
    ("barberia", "Barbería / Peluquería", PRESET_BARBERIA),
    ("medico", "Consultorio médico", PRESET_MEDICO),
]


def run() -> None:
    db = SessionLocal()
    try:
        # Super-administrador (para entrar al panel /admin)
        if db.query(SuperAdmin).filter_by(email="admin@turnos360.com").first() is None:
            db.add(
                SuperAdmin(
                    nombre="Leandro",
                    email="admin@turnos360.com",
                    hash_clave=hash_clave("superadmin360"),
                )
            )

        # Catálogo de rubros (con sus presets de terminología/módulos)
        for codigo, nombre, preset in RUBROS:
            if db.query(Rubro).filter_by(codigo=codigo).first() is None:
                db.add(Rubro(codigo=codigo, nombre=nombre, preset=preset))

        db.commit()
        print("Seed base OK.")
        print("  Super-admin: admin@turnos360.com / superadmin360")
        print("  Rubros disponibles: barbería, médico")
        print("  Entrá al panel /admin para crear tus empresas y usuarios.")
    finally:
        db.close()


if __name__ == "__main__":
    run()