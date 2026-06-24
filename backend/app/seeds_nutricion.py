"""Seed del pack nutrición: rubro 'nutricion' + empresa de Giuliana (E13).

Es idempotente y NO toca a La Cueva: si el rubro o la empresa ya existen,
no duplica nada. Crea la empresa real de Giuliana con credenciales de PRUEBA
(cambialas cuando deployes).

Uso (dentro del contenedor):
    docker compose -f infra/docker-compose.yml exec backend python -m app.seeds_nutricion
"""

import datetime as dt

from app.core.crypto import hash_clave
from app.db.session import SessionLocal
from app.seeds import _base_empresa  # reusa los catálogos financieros por empresa
from app.models import (
    Cliente,
    Empresa,
    HorarioRecurso,
    Recurso,
    Rubro,
    Servicio,
    Usuario,
)
from app.models.enums import RolUsuario, TipoRecurso

# Preset del rubro: terminología, módulos y campos propios de nutrición.
# El módulo ficha_clinica = True es lo que "enciende" el pack salud para este rubro.
PRESET_NUTRICION = {
    "terminologia": {"turno": "consulta", "recurso": "profesional", "cliente": "paciente"},
    "tipo_turno_default": "simple",
    "modulos": {"gift_cards": False, "ficha_clinica": True, "ordenes_trabajo": False},
    "campos_cliente": [
        {"clave": "obra_social", "etiqueta": "Obra social", "tipo": "texto"},
        {"clave": "plan_obra_social", "etiqueta": "Plan", "tipo": "texto"},
        {"clave": "nro_afiliado", "etiqueta": "N.º de afiliado", "tipo": "texto"},
    ],
    "datos_sensibles": True,
}

# Tipos de consulta de Giuliana. (nombre, duracion_min, buffer_min, paso_turno_min, precio)
# Los precios van en 0: que ella los complete desde el panel.
SERVICIOS_NUTRICION = [
    ("Primera consulta", 60, 0, 60, 0),
    ("Antropometría", 30, 0, 30, 0),
    ("Control", 20, 0, 20, 0),
    ("Control + antropometría", 30, 0, 30, 0),
]


def run() -> None:
    db = SessionLocal()
    try:
        # 1) Rubro nutrición (lo crea solo si no existe)
        rubro = db.query(Rubro).filter_by(codigo="nutricion").first()
        if rubro is None:
            rubro = Rubro(codigo="nutricion", nombre="Nutrición", preset=PRESET_NUTRICION)
            db.add(rubro)
            db.flush()
            print("Rubro 'nutricion' creado.")
        else:
            print("Rubro 'nutricion' ya existía — lo reuso.")

        # 2) Empresa de Giuliana (idempotente por slug)
        if db.query(Empresa).filter_by(slug="giuliana").first():
            print("La empresa 'giuliana' ya existe — nada que hacer.")
            return

        empresa = Empresa(rubro_id=rubro.id, nombre="Giuliana Nutrición",
                          slug="giuliana", config_pack={})
        db.add(empresa)
        db.flush()

        # Usuario dueño — credenciales de PRUEBA (cambiar en producción)
        db.add(Usuario(empresa_id=empresa.id, nombre="Giuliana",
                       email="giuliana@nutricion.com", hash_clave=hash_clave("demo1234"),
                       rol=RolUsuario.DUENO))

        # La profesional, como recurso de la agenda
        giuliana = Recurso(empresa_id=empresa.id, tipo=TipoRecurso.PERSONA,
                           nombre="Lic. Giuliana", color="#0d9488")
        db.add(giuliana)
        db.flush()

        # Horario de atención: lunes a viernes 9-17 (ajustable desde el panel)
        for dia in range(5):
            db.add(HorarioRecurso(empresa_id=empresa.id, recurso_id=giuliana.id,
                                  dia_semana=dia, hora_desde=dt.time(9), hora_hasta=dt.time(17)))

        # Tipos de consulta
        for nombre, dur, buf, paso, precio in SERVICIOS_NUTRICION:
            db.add(Servicio(empresa_id=empresa.id, nombre=nombre, duracion_min=dur,
                            buffer_min=buf, paso_turno_min=paso, precio=precio))

        # Un paciente de prueba (Julieta, la de las antropometrías) para tener
        # con qué probar la ficha y los gráficos más adelante.
        db.add(Cliente(empresa_id=empresa.id, nombre="Julieta", apellido="Sarandón",
                       fecha_nacimiento=dt.date(1999, 1, 1), canal_adquisicion="referido",
                       campos_rubro={"obra_social": "OSDE", "plan_obra_social": "210",
                                     "nro_afiliado": "12345"}))

        db.commit()
        print("Seed nutrición OK: empresa Giuliana + profesional + servicios + paciente de prueba.")
    finally:
        db.close()


if __name__ == "__main__":
    run()