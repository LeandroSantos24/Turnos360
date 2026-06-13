"""Seeds de desarrollo (E1): una barbería y un consultorio ficticios.

Uso:
    make seed   (o python -m app.seeds dentro del contenedor)

Es idempotente: si los rubros ya existen, no duplica nada.
"""

import datetime as dt
import random

from faker import Faker

from app.core.crypto import encriptar_credenciales, hash_clave
from app.db.session import SessionLocal
from app.models import (
    CategoriaFinanciera,
    Cliente,
    Empresa,
    Especialidad,
    HorarioRecurso,
    MetodoPago,
    Recurso,
    Rubro,
    Servicio,
    SuperAdmin,
    Turno,
    Usuario,
)
from app.models.enums import (
    EstadoTurno,
    RolUsuario,
    TipoMovimiento,
    TipoRecurso,
    TipoTurno,
)

fake = Faker("es_AR")
random.seed(360)
Faker.seed(360)

CANALES = ["instagram", "tiktok", "referido", "google", "paso_por_la_puerta"]

PRESET_BARBERIA = {
    "terminologia": {"turno": "turno", "recurso": "barbero", "cliente": "cliente"},
    "tipo_turno_default": "simple",
    "modulos": {"gift_cards": True, "ficha_clinica": False, "ordenes_trabajo": False},
    "campos_cliente": [
        {"clave": "preferencias_corte", "etiqueta": "Preferencias de corte", "tipo": "texto"},
        {"clave": "productos", "etiqueta": "Productos utilizados", "tipo": "texto"},
    ],
    "datos_sensibles": False,
}

PRESET_MEDICO = {
    "terminologia": {"turno": "turno", "recurso": "médico", "cliente": "paciente"},
    "tipo_turno_default": "simple",
    "modulos": {"gift_cards": False, "ficha_clinica": True, "ordenes_trabajo": False},
    "campos_cliente": [
        {"clave": "obra_social", "etiqueta": "Obra social", "tipo": "texto"},
        {"clave": "nro_afiliado", "etiqueta": "N.º de afiliado", "tipo": "texto"},
    ],
    "datos_sensibles": True,
}

CATEGORIAS = {
    TipoMovimiento.INGRESO: ["Turnos", "Venta de productos", "Membresías", "Gift cards", "Paquetes"],
    TipoMovimiento.EGRESO: [
        "Sueldos", "Comisiones", "Alquiler", "Servicios", "Marketing",
        "Insumos", "Equipamiento", "Impuestos", "Mantenimiento",
    ],
}

METODOS = [("Efectivo", 0), ("Débito", 1.5), ("Crédito", 4.5),
           ("Transferencia", 0), ("Mercado Pago", 6.0), ("MODO", 2.0)]


def _base_empresa(db, empresa: Empresa) -> None:
    """Catálogos financieros por empresa (D-14)."""
    for tipo, nombres in CATEGORIAS.items():
        for n in nombres:
            db.add(CategoriaFinanciera(empresa_id=empresa.id, nombre=n, tipo=tipo))
    for nombre, pct in METODOS:
        db.add(MetodoPago(empresa_id=empresa.id, nombre=nombre, comision_pct=pct))


def _clientes(db, empresa: Empresa, n: int, campos) -> list[Cliente]:
    out = []
    for _ in range(n):
        c = Cliente(
            empresa_id=empresa.id,
            nombre=fake.first_name(),
            apellido=fake.last_name(),
            dni=str(fake.random_int(20_000_000, 45_000_000)),
            email=fake.email(),
            telefono=fake.phone_number(),
            fecha_nacimiento=fake.date_of_birth(minimum_age=18, maximum_age=75),
            canal_adquisicion=random.choice(CANALES),
            campos_rubro=campos(),
        )
        db.add(c)
        out.append(c)
    return out


def _turnos(db, empresa, clientes, recursos, servicios, n: int) -> None:
    hoy = dt.datetime.now(dt.timezone.utc).replace(minute=0, second=0, microsecond=0)
    for _ in range(n):
        serv = random.choice(servicios)
        inicio = hoy + dt.timedelta(days=random.randint(-3, 7), hours=random.randint(9, 18) - 12)
        db.add(Turno(
            empresa_id=empresa.id,
            cliente_id=random.choice(clientes).id,
            recurso_id=random.choice(recursos).id,
            servicio_id=serv.id,
            tipo=TipoTurno.SIMPLE,
            estado=random.choice(list(EstadoTurno)),
            fecha_inicio=inicio,
            fecha_fin=inicio + dt.timedelta(minutes=serv.duracion_min),
            importe_previsto=serv.precio,
        ))


def run() -> None:
    db = SessionLocal()
    try:
        if db.query(Rubro).count():
            print("Seeds ya cargados — nada que hacer.")
            return

        # --- rubros (presets) ---
        r_barberia = Rubro(codigo="barberia", nombre="Barbería / Peluquería", preset=PRESET_BARBERIA)
        r_medico = Rubro(codigo="medico", nombre="Consultorio médico", preset=PRESET_MEDICO)
        db.add_all([r_barberia, r_medico])
        db.flush()

        # --- super admin ---
        db.add(SuperAdmin(nombre="Leandro", email="admin@turnos360.com",
                          hash_clave=hash_clave("superadmin360")))

        # ================= BARBERÍA =================
        barberia = Empresa(
            rubro_id=r_barberia.id, nombre="Barbería La Cueva", slug="la-cueva",
            config_pack={},
            wa_credenciales=encriptar_credenciales(
                {"waba_id": "demo", "phone_number_id": "demo", "token": "demo"}),
        )
        db.add(barberia)
        db.flush()
        db.add(Usuario(empresa_id=barberia.id, nombre="Dueño Barbería",
                       email="dueno@lacueva.com", hash_clave=hash_clave("demo1234"),
                       rol=RolUsuario.DUENO))
        barberos = [Recurso(empresa_id=barberia.id, tipo=TipoRecurso.PERSONA, nombre=n, color=c)
                    for n, c in [("Juan", "#0d9488"), ("Pedro", "#7c3aed")]]
        db.add_all(barberos)
        db.flush()
        for b in barberos:  # lunes a viernes 9-19
            for dia in range(5):
                db.add(HorarioRecurso(empresa_id=barberia.id, recurso_id=b.id, dia_semana=dia,
                                      hora_desde=dt.time(9), hora_hasta=dt.time(19)))
        servicios_b = [
            Servicio(empresa_id=barberia.id, nombre="Corte", duracion_min=30, precio=9000),
            Servicio(empresa_id=barberia.id, nombre="Corte + barba", duracion_min=45,
                     buffer_min=5, precio=13000),
        ]
        db.add_all(servicios_b)
        db.flush()
        _base_empresa(db, barberia)
        clientes_b = _clientes(
            db, barberia, 12,
            lambda: {"preferencias_corte": random.choice(["fade", "clásico", "rapado"])})
        db.flush()
        _turnos(db, barberia, clientes_b, barberos, servicios_b, 25)

        # ================= CONSULTORIO =================
        consultorio = Empresa(rubro_id=r_medico.id, nombre="Consultorio San Martín",
                              slug="consultorio-san-martin", config_pack={})
        db.add(consultorio)
        db.flush()
        db.add(Usuario(empresa_id=consultorio.id, nombre="Recepción",
                       email="recepcion@csm.com", hash_clave=hash_clave("demo1234"),
                       rol=RolUsuario.RECEPCION))
        esp_clinica = Especialidad(empresa_id=consultorio.id, nombre="Clínica médica")
        esp_pediatria = Especialidad(empresa_id=consultorio.id, nombre="Pediatría")
        db.add_all([esp_clinica, esp_pediatria])
        db.flush()
        medicos = [
            Recurso(empresa_id=consultorio.id, tipo=TipoRecurso.PERSONA,
                    nombre="Dra. Antonella", especialidades=[esp_clinica]),
            Recurso(empresa_id=consultorio.id, tipo=TipoRecurso.PERSONA,
                    nombre="Dr. Ivo", especialidades=[esp_pediatria]),
        ]
        db.add_all(medicos)
        db.flush()
        for m in medicos:
            for dia in range(5):
                db.add(HorarioRecurso(empresa_id=consultorio.id, recurso_id=m.id, dia_semana=dia,
                                      hora_desde=dt.time(8), hora_hasta=dt.time(14)))
        servicios_c = [Servicio(empresa_id=consultorio.id, nombre="Consulta", duracion_min=20,
                                buffer_min=5, precio=15000)]
        db.add_all(servicios_c)
        db.flush()
        _base_empresa(db, consultorio)
        clientes_c = _clientes(
            db, consultorio, 10,
            lambda: {"obra_social": random.choice(["OSDE", "Swiss Medical", "PAMI", "Particular"]),
                     "nro_afiliado": str(fake.random_int(10_000, 99_999))})
        db.flush()
        _turnos(db, consultorio, clientes_c, medicos, servicios_c, 18)

        db.commit()
        print("Seeds OK: Barbería La Cueva + Consultorio San Martín cargados.")
    finally:
        db.close()


if __name__ == "__main__":
    run()