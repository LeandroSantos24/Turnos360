"""Seed mínimo: solo la empresa La Cueva y su usuario dueño.

Pensado para arrancar una instancia VACÍA y cargar todo a mano (servicios,
recursos, clientes, membresías, turnos) como un negocio real. No crea datos
de relleno. Es idempotente: si ya existe, no duplica.

Uso (dentro del contenedor):
    docker compose -f infra/docker-compose.yml exec backend python -m app.seeds_minimo
"""

from app.core.crypto import encriptar_credenciales, hash_clave
from app.db.session import SessionLocal
from app.models import Empresa, Rubro, SuperAdmin, Usuario
from app.models.enums import RolUsuario
from app.seeds import PRESET_BARBERIA


def run() -> None:
    db = SessionLocal()
    try:
        # --- Rubro barbería (trae el preset de terminología y módulos) ---
        rubro = db.query(Rubro).filter_by(codigo="barberia").first()
        if rubro is None:
            rubro = Rubro(
                codigo="barberia",
                nombre="Barbería / Peluquería",
                preset=PRESET_BARBERIA,
            )
            db.add(rubro)
            db.flush()

        # --- Super admin (para el futuro panel de administración) ---
        if db.query(SuperAdmin).filter_by(email="admin@turnos360.com").first() is None:
            db.add(
                SuperAdmin(
                    nombre="Leandro",
                    email="admin@turnos360.com",
                    hash_clave=hash_clave("superadmin360"),
                )
            )

        # --- Empresa La Cueva ---
        empresa = db.query(Empresa).filter_by(slug="la-cueva").first()
        if empresa is None:
            empresa = Empresa(
                rubro_id=rubro.id,
                nombre="Barbería La Cueva",
                slug="la-cueva",
                config_pack={},
                wa_credenciales=encriptar_credenciales(
                    {"waba_id": "demo", "phone_number_id": "demo", "token": "demo"}
                ),
            )
            db.add(empresa)
            db.flush()

        # --- Usuario dueño ---
        if db.query(Usuario).filter_by(email="dueno@lacueva.com").first() is None:
            db.add(
                Usuario(
                    empresa_id=empresa.id,
                    nombre="Dueño Barbería",
                    email="dueno@lacueva.com",
                    hash_clave=hash_clave("demo1234"),
                    rol=RolUsuario.DUENO,
                )
            )

        db.commit()
        print("Seed mínimo OK.")
        print("  Empresa: Barbería La Cueva")
        print("  Login:   dueno@lacueva.com / demo1234")
        print("  App vacía: cargá servicios, recursos, clientes y turnos a mano.")
    finally:
        db.close()


if __name__ == "__main__":
    run()