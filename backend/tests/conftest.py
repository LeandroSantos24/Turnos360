"""Fixtures compartidas de la suite de Turnos360.

AISLAMIENTO DE DATOS — el punto más importante de este archivo:
cada test corre dentro de una transacción externa que se REVIERTE al final.
Los commit() que haga el código bajo test se convierten en savepoints
(join_transaction_mode="create_savepoint", SQLAlchemy 2.0), así que al
terminar el test no queda NADA en la base. Esto permite correr la suite
contra la base de desarrollo (la del docker compose) sin ensuciarla:
ni empresas de prueba, ni turnos, ni clientes fantasma.

RATE LIMITING: se apaga en los tests (autouse). Todos los requests del
TestClient comparten la IP "testclient", así que con el limiter prendido
el undécimo login de la suite empezaría a dar 429 y los tests serían
frágiles y dependientes del orden. La CONFIGURACIÓN de los límites se
verifica aparte en test_rate_limit_config.py.
"""

import datetime as dt
import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.crypto import hash_clave
from app.core.rate_limit import limiter
from app.core.seguridad import crear_access_token, crear_refresh_token
from app.db.session import engine, get_db
from app.main import app
from app.models import Cliente, Empresa, Recurso, Rubro, Usuario
from app.models.agenda import HorarioRecurso, Servicio
from app.models.enums import EstadoTurno, RolUsuario, TipoRecurso
from app.models.finanzas import MetodoPago, Pago
from app.models.turno import Turno


@pytest.fixture(autouse=True)
def _limiter_apagado():
    previo = limiter.enabled
    limiter.enabled = False
    yield
    limiter.enabled = previo


@pytest.fixture()
def db():
    """Sesión transaccional: todo lo que el test escriba se revierte al final."""
    conexion = engine.connect()
    trans = conexion.begin()
    sesion = Session(bind=conexion, join_transaction_mode="create_savepoint")
    try:
        yield sesion
    finally:
        sesion.close()
        trans.rollback()
        conexion.close()


@pytest.fixture()
def client(db):
    """TestClient cuya dependencia de DB es la sesión transaccional del test."""
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)


def token_de(usuario: Usuario) -> dict:
    """Headers de Authorization para un usuario (sin pasar por /auth/login)."""
    t = crear_access_token(usuario.id, usuario.empresa_id, usuario.rol.value)
    return {"Authorization": f"Bearer {t}"}


def refresh_de(usuario: Usuario) -> str:
    return crear_refresh_token(usuario.id, usuario.empresa_id, usuario.rol.value)


@pytest.fixture()
def armar_empresa(db):
    """Factory: una empresa completa y funcional, con sufijo único.

    Trae: rubro propio (no depende del seed), dueño, profesional vinculado al
    recurso "Lucas", dos recursos con horario 0-24 todos los días, un servicio
    "Corte" que prestan ambos, un método de pago y un cliente. La clave de
    todos los usuarios es ctx.clave.
    """

    def _armar(nombre: str = "Barbería Test") -> SimpleNamespace:
        s = uuid.uuid4().hex[:8]
        rubro = Rubro(codigo=f"test-{s}", nombre="Rubro de prueba", preset={})
        db.add(rubro)
        db.flush()

        emp = Empresa(nombre=nombre, slug=f"test-{s}", rubro_id=rubro.id)
        db.add(emp)
        db.flush()

        clave = "clave1234"
        dueno = Usuario(
            empresa_id=emp.id,
            nombre="Dueño Test",
            email=f"dueno-{s}@example.com",
            hash_clave=hash_clave(clave),
            rol=RolUsuario.DUENO,
        )
        lucas = Recurso(empresa_id=emp.id, nombre="Lucas Estrella", tipo=TipoRecurso.PERSONA)
        pablo = Recurso(empresa_id=emp.id, nombre="Pablo Vega", tipo=TipoRecurso.PERSONA)
        db.add_all([dueno, lucas, pablo])
        db.flush()

        profesional = Usuario(
            empresa_id=emp.id,
            nombre="Profe Test",
            email=f"profe-{s}@example.com",
            hash_clave=hash_clave(clave),
            rol=RolUsuario.PROFESIONAL,
        )
        db.add(profesional)
        db.flush()
        lucas.usuario_id = profesional.id  # el profesional opera la silla de Lucas

        servicio = Servicio(empresa_id=emp.id, nombre="Corte", duracion_min=30, precio=10000)
        db.add(servicio)
        db.flush()
        servicio.recursos.append(lucas)
        servicio.recursos.append(pablo)

        for r in (lucas, pablo):
            for dia in range(7):
                db.add(
                    HorarioRecurso(
                        empresa_id=emp.id,
                        recurso_id=r.id,
                        dia_semana=dia,
                        hora_desde=dt.time(0, 0),
                        hora_hasta=dt.time(23, 59),
                    )
                )

        metodo = MetodoPago(empresa_id=emp.id, nombre="Efectivo")
        cliente = Cliente(
            empresa_id=emp.id, nombre="Juan Perez", telefono=f"261{s[:7]}"
        )
        db.add_all([metodo, cliente])
        db.flush()

        return SimpleNamespace(
            empresa=emp,
            dueno=dueno,
            profesional=profesional,
            lucas=lucas,
            pablo=pablo,
            servicio=servicio,
            metodo=metodo,
            cliente=cliente,
            clave=clave,
        )

    return _armar


def cargar_pagos(db, ctx, recurso, cantidad: int, monto: float, base: dt.datetime):
    """Crea `cantidad` turnos FINALIZADOS con su pago, para tests de finanzas."""
    for i in range(cantidad):
        inicio = base + dt.timedelta(minutes=40 * i)
        turno = Turno(
            empresa_id=ctx.empresa.id,
            cliente_id=ctx.cliente.id,
            servicio_id=ctx.servicio.id,
            recurso_id=recurso.id,
            fecha_inicio=inicio,
            fecha_fin=inicio + dt.timedelta(minutes=30),
            estado=EstadoTurno.FINALIZADO,
        )
        db.add(turno)
        db.flush()
        db.add(
            Pago(
                empresa_id=ctx.empresa.id,
                turno_id=turno.id,
                cliente_id=ctx.cliente.id,
                metodo_pago_id=ctx.metodo.id,
                monto=monto,
                comision_aplicada=0,
                fecha=inicio,
            )
        )
    db.flush()
