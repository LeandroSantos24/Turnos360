"""Una empresa recién dada de alta puede trabajar el mismo día.

EL PROBLEMA
───────────
El alta dejaba el negocio con la aplicación bien nombrada —«paciente» en vez de
«cliente», «sesión» en vez de «turno»— y absolutamente vacía: sin métodos de
cobro y sin servicios. Sin servicios no hay nada que agendar, la página pública
no muestra nada para reservar y la agenda tiene una sola columna. El primer
paso real era una pantalla en blanco con un botón «Nuevo», que es donde la
gente abandona: no porque sea difícil, sino porque es trabajo antes de haber
visto que la cosa sirve.
"""

import uuid

import pytest
from sqlalchemy import select

from app.models import Empresa, Rubro
from app.models.agenda import Servicio
from app.models.finanzas import MetodoPago
from app.presets import PRESET_BARBERIA, PRESET_MEDICO, PRESET_NUTRICION
from app.services import catalogo_inicial, metodos_pago, sucursal as sucursal_svc


@pytest.fixture
def empresa_de(db):
    """Una empresa con el rubro que se le pida, como la deja el alta."""

    def _hacer(preset: dict, codigo: str = "rubro") -> Empresa:
        s = uuid.uuid4().hex[:8]
        rubro = Rubro(codigo=f"{codigo}-{s}", nombre="Rubro", preset=preset)
        db.add(rubro)
        db.flush()
        emp = Empresa(nombre=f"Negocio {s}", slug=f"n-{s}", rubro_id=rubro.id)
        db.add(emp)
        db.flush()
        sucursal_svc.crear_principal(db, emp)
        return emp

    return _hacer


def _servicios(db, empresa_id):
    return list(
        db.scalars(select(Servicio).where(Servicio.empresa_id == empresa_id))
    )


# ── El catálogo ──────────────────────────────────────────────────────────

def test_una_barberia_nueva_ya_tiene_sus_servicios(db, empresa_de):
    emp = empresa_de(PRESET_BARBERIA, "barberia")
    catalogo_inicial.sembrar(db, emp.id)

    nombres = {s.nombre for s in _servicios(db, emp.id)}
    assert "Corte" in nombres
    assert len(nombres) == len(PRESET_BARBERIA["servicios"])


def test_los_servicios_traen_carril_para_que_la_agenda_sirva(db, empresa_de):
    """Sin `grupo_agenda` la agenda tiene una sola columna y se pierde lo que
    diferencia al producto: corte, barba y color conviviendo en la misma hora."""
    emp = empresa_de(PRESET_BARBERIA, "barberia")
    catalogo_inicial.sembrar(db, emp.id)

    carriles = {s.grupo_agenda for s in _servicios(db, emp.id)}
    assert carriles == {"corte", "barba", "tintura"}


def test_una_consulta_medica_ocupa_al_profesional_entero(db, empresa_de):
    """En salud NO hay carriles paralelos: dos turnos a la misma hora con el
    mismo médico serían un sobreturno encubierto."""
    emp = empresa_de(PRESET_MEDICO, "medico")
    catalogo_inicial.sembrar(db, emp.id)

    assert all(s.grupo_agenda is None for s in _servicios(db, emp.id))


def test_los_servicios_nacen_ofrecidos_en_el_local(db, empresa_de):
    """El invariante de multisucursal: un servicio que no está en ningún local
    no da error, da un servicio INVISIBLE — y eso no se descubre hasta que un
    cliente no lo encuentra en la página."""
    from app.models.agenda import ServicioSucursal

    emp = empresa_de(PRESET_NUTRICION, "nutricion")
    catalogo_inicial.sembrar(db, emp.id)
    db.flush()

    for s in _servicios(db, emp.id):
        filas = db.scalars(
            select(ServicioSucursal).where(ServicioSucursal.servicio_id == s.id)
        ).all()
        assert filas, f"«{s.nombre}» no se ofrece en ningún local: es invisible"


def test_no_se_le_meten_servicios_a_quien_ya_empezo_su_catalogo(db, empresa_de):
    """El sembrado es para el alta y solo para el alta. A un negocio que ya
    cargó lo suyo, cuatro servicios ajenos entre los propios son un estorbo."""
    emp = empresa_de(PRESET_BARBERIA, "barberia")
    db.add(Servicio(empresa_id=emp.id, nombre="Lo mío", duracion_min=30, precio=1))
    db.flush()

    assert catalogo_inicial.sembrar(db, emp.id) == []
    assert {s.nombre for s in _servicios(db, emp.id)} == {"Lo mío"}


def test_un_rubro_sin_servicios_en_el_preset_no_rompe_el_alta(db, empresa_de):
    """Los rubros viejos no tienen la clave `servicios`. El alta tiene que
    seguir funcionando: quedarse sin catálogo es molesto, no poder registrarse
    es fatal."""
    emp = empresa_de({"terminologia": {}}, "viejo")
    assert catalogo_inicial.sembrar(db, emp.id) == []


def test_el_catalogo_a_medida_del_super_admin_le_gana_al_rubro(db, empresa_de):
    """config_pack pisa al preset, igual que en toda la configuración."""
    emp = empresa_de(PRESET_BARBERIA, "barberia")
    emp.config_pack = {
        "servicios": [
            {"nombre": "Único", "duracion_min": 45, "precio": 1000, "grupo": None}
        ]
    }
    db.flush()

    catalogo_inicial.sembrar(db, emp.id)

    assert {s.nombre for s in _servicios(db, emp.id)} == {"Único"}


# ── Los presets, como conjunto ───────────────────────────────────────────

def test_todos_los_rubros_ofrecidos_traen_servicios():
    """Un rubro sin servicios sugeridos deja al negocio en la pantalla en
    blanco que este trabajo vino a sacar. Se verifica el catálogo entero para
    que agregar un rubro nuevo y olvidarse de los servicios falle acá."""
    from app.seeds_minimo import RUBROS

    sin_servicios = [nombre for _, nombre, p in RUBROS if not p.get("servicios")]
    assert sin_servicios == [], f"Rubros sin servicios sugeridos: {sin_servicios}"


def test_ningun_servicio_sugerido_dura_cero(db):
    """Una duración en cero rompe el cálculo de huecos: el turno no ocuparía
    lugar y se podrían agendar infinitos a la misma hora."""
    from app.seeds_minimo import RUBROS

    for _, nombre, preset in RUBROS:
        for s in preset.get("servicios", []):
            assert s["duracion_min"] > 0, f"{nombre}: «{s['nombre']}» dura 0"
            assert s.get("paso_turno_min", 15) > 0, f"{nombre}: «{s['nombre']}» sin paso"


def test_los_rubros_sensibles_tienen_ficha_clinica():
    """Nutrición, kinesiología, psicología y médico manejan datos de salud.
    Si `datos_sensibles` está prendido, la ficha clínica tiene que estar
    disponible — y si no, el profesional termina escribiendo lo clínico en el
    campo de notas del turno, que no tiene ninguna de las protecciones."""
    from app.seeds_minimo import RUBROS

    for _, nombre, preset in RUBROS:
        if preset.get("datos_sensibles"):
            assert preset["modulos"]["ficha_clinica"], (
                f"{nombre} marca datos sensibles pero no habilita la ficha"
            )


# ── Los métodos de cobro, en el mismo alta ───────────────────────────────

def test_el_alta_deja_metodos_de_cobro_y_servicios_juntos(db, empresa_de):
    """Las dos mitades de «puedo trabajar hoy»: algo que vender y con qué
    cobrarlo."""
    emp = empresa_de(PRESET_BARBERIA, "barberia")
    metodos_pago.sembrar(db, emp.id)
    catalogo_inicial.sembrar(db, emp.id)
    db.flush()

    assert _servicios(db, emp.id)
    assert db.scalars(
        select(MetodoPago).where(MetodoPago.empresa_id == emp.id)
    ).all()
