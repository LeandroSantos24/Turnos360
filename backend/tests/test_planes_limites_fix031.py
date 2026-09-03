"""Fase 1: los planes dejan de ser decorativos.

Hasta acá el "plan" era un string libre y el tope de profesionales se pintaba
en ámbar en el panel del super-admin sin bloquear absolutamente nada: una
empresa del plan de tres podía cargar cuarenta. Y pagar la cuota no cambiaba el
plan, así que se podía pagar por Mercado Pago un año entero y seguir figurando
en "gratuito", con los límites de la prueba.

La grilla acordada (revisada antes del deploy, para entrar por debajo de la
competencia directa: Ágora cobra $11.900 con plan único):

    Inicial  $11.900 →  2 profesionales ·  3 usuarios · 1 local
    Pro      $19.900 →  8 profesionales · 10 usuarios · 1 local
    Multi    $32.900 → ilimitados       · ilimitados  · 5 locales

Los tres ejes van separados a propósito. PROFESIONAL es quien ocupa una columna
de la agenda —lo que de verdad escala con el tamaño del negocio y lo que se
cobra—; USUARIO es quien entra con su clave, y se limita con la mano floja
porque cobrar por asiento a una peluquería de barrio es la forma más rápida de
que compartan una clave entre cuatro, que arruina la trazabilidad de la caja.

La prueba (GRATUITO) da TODO desbloqueado: una prueba recortada no deja probar
lo que uno querría vender. Al vencer cae a Inicial y ahí recién aprietan los
cupos.

El nombre viejo "basico" sigue entrando como Inicial: hay empresas con ese
string escrito en la base y no se tienen que enterar del cambio.
"""

import uuid

import pytest

from app.core import planes
from app.core.crypto import hash_clave
from app.core.seguridad import crear_token_superadmin
from app.models import Empresa, Recurso, SuperAdmin
from app.models.enums import TipoRecurso

from .conftest import token_de


@pytest.fixture()
def admin(db) -> dict:
    sa = SuperAdmin(
        nombre="Admin Test",
        email=f"sa-{uuid.uuid4().hex}@turnos360.test",
        hash_clave=hash_clave("clave1234"),
    )
    db.add(sa)
    db.flush()
    return {"Authorization": f"Bearer {crear_token_superadmin(sa.id)}"}


def _plan(db, ctx, plan: str, *, override=None):
    ctx.empresa.plan = plan
    ctx.empresa.limite_recursos = override
    db.commit()


def _profesionales(db, empresa_id) -> int:
    return (
        db.query(Recurso)
        .filter_by(empresa_id=empresa_id, activo=True, tipo=TipoRecurso.PERSONA)
        .count()
    )


def _crear_prof(client, ctx, nombre="Nuevo"):
    return client.post(
        "/recursos", headers=token_de(ctx.dueno), json={"nombre": nombre, "tipo": "persona"}
    )


# ══════════════════════════════════════════════════════════════════════
#  La grilla
# ══════════════════════════════════════════════════════════════════════

def test_la_grilla_es_la_acordada():
    """La grilla comercial, fijada acá para que no se mueva sin querer.

    Inicial entra a $11.900 —lo mismo que cobra Ágora con plan único— y da la
    agenda completa: página de reservas, señas y recordatorios. El salto a Pro
    se paga por el equipo más grande y por lo que hace ganar plata; el de Multi,
    por varios locales de verdad.
    """
    g = planes.GRILLA
    assert g[planes.Plan.INICIAL].precio == 11900
    assert g[planes.Plan.INICIAL].profesionales == 2
    assert g[planes.Plan.INICIAL].usuarios == 3
    assert g[planes.Plan.INICIAL].sucursales == 1

    assert g[planes.Plan.PRO].precio == 19900
    assert g[planes.Plan.PRO].profesionales == 8
    assert g[planes.Plan.PRO].usuarios == 10
    assert g[planes.Plan.PRO].sucursales == 1

    assert g[planes.Plan.MULTI].precio == 32900
    assert g[planes.Plan.MULTI].profesionales is None, "Multi = ilimitados"
    assert g[planes.Plan.MULTI].usuarios is None
    assert g[planes.Plan.MULTI].sucursales == 5

    # Cada escalón cuesta más y da más: una grilla donde un plan más caro da
    # menos de algo es una grilla mal armada, y se descubre vendiendo.
    escalones = [planes.Plan.INICIAL, planes.Plan.PRO, planes.Plan.MULTI]
    precios = [g[p].precio for p in escalones]
    assert precios == sorted(precios)


def test_el_plan_viejo_basico_sigue_entrando_como_inicial():
    """Las empresas que tienen "basico" escrito en la base no se enteran del
    cambio de nombre. Sin esto, `plan_de` no lo reconocería y las mandaría a
    GRATUITO — que ahora da MÁS, así que serían un plan regalado."""
    assert planes.plan_de("basico") is planes.Plan.INICIAL
    assert planes.plan_de("  BASICO ") is planes.Plan.INICIAL


def test_la_prueba_da_todo_desbloqueado():
    """Una prueba recortada no deja probar lo que uno querría vender.

    Que el negocio cargue su equipo entero y vea el producto andando con sus
    datos de verdad; al vencer cae a Inicial y ahí recién aprietan los cupos.
    """
    prueba = planes.GRILLA[planes.Plan.GRATUITO]
    assert prueba.profesionales is None
    assert prueba.usuarios is None
    assert prueba.funciones == planes.GRILLA[planes.Plan.MULTI].funciones


def test_cada_plan_incluye_todo_lo_del_anterior():
    """Un escalón que quita algo del anterior es una trampa para el que sube.

    Se verifica con subconjuntos y no a ojo: es exactamente el error que se
    cuela agregando una función nueva y olvidándose de sumarla al plan de
    arriba.
    """
    g = planes.GRILLA
    assert g[planes.Plan.INICIAL].funciones <= g[planes.Plan.PRO].funciones
    assert g[planes.Plan.PRO].funciones <= g[planes.Plan.MULTI].funciones


def test_los_recordatorios_estan_desde_el_plan_mas_barato():
    """Son el corazón anti-ausencias: es LO que se vende. Cobrarlos aparte
    dejaría al plan de entrada sin la razón por la que alguien lo contrata."""
    assert planes.incluye("inicial", planes.Funcion.CAMPANAS)


def test_multisucursal_es_exclusivo_de_multi():
    assert not planes.incluye("inicial", planes.Funcion.MULTISUCURSAL)
    assert not planes.incluye("pro", planes.Funcion.MULTISUCURSAL)
    assert planes.incluye("multi", planes.Funcion.MULTISUCURSAL)


def test_un_plan_desconocido_cae_al_mas_restrictivo():
    """La columna estuvo meses aceptando texto libre: puede haber cualquier cosa.

    Equivocarse hacia arriba sería regalar un plan que nadie pagó.
    """
    assert planes.plan_de("cualquier-cosa") is planes.Plan.GRATUITO
    assert planes.plan_de(None) is planes.Plan.GRATUITO
    assert planes.plan_de("") is planes.Plan.GRATUITO
    assert planes.plan_de("  PRO  ") is planes.Plan.PRO


def test_la_prueba_no_se_ofrece_como_plan_a_la_venta():
    codigos = [p["codigo"] for p in planes.para_mostrar()]
    assert "gratuito" not in codigos
    assert codigos == ["inicial", "pro", "multi"]


# ══════════════════════════════════════════════════════════════════════
#  El tope BLOQUEA
# ══════════════════════════════════════════════════════════════════════

def test_el_plan_inicial_frena_en_el_tercer_profesional(client, db, armar_empresa):
    ctx = armar_empresa()
    _plan(db, ctx, "inicial")
    # armar_empresa ya deja los 2 profesionales que Inicial permite.
    assert _profesionales(db, ctx.empresa.id) == 2

    r = _crear_prof(client, ctx, "El tercero")
    assert r.status_code == 409, "El plan de 2 tiene que frenar en el tercero."
    assert "Inicial" in r.json()["detail"]
    assert "Mi suscripción" in r.json()["detail"], (
        "El mensaje tiene que decir a dónde ir, no solo que no se puede."
    )


def test_el_plan_pro_deja_llegar_a_ocho(client, db, armar_empresa):
    ctx = armar_empresa()
    _plan(db, ctx, "pro")
    while _profesionales(db, ctx.empresa.id) < 8:
        r = _crear_prof(client, ctx, f"P{uuid.uuid4().hex[:5]}")
        assert r.status_code == 201, r.text
        db.expire_all()
    assert _crear_prof(client, ctx, "El noveno").status_code == 409


def test_el_plan_multi_no_tiene_tope_de_profesionales(client, db, armar_empresa):
    ctx = armar_empresa()
    _plan(db, ctx, "multi")
    for i in range(12):
        assert _crear_prof(client, ctx, f"Multi{i}").status_code == 201


def test_un_box_no_ocupa_asiento_del_plan(client, db, armar_empresa):
    """El cupo es de PROFESIONALES. Un box o un equipo no paga asiento."""
    ctx = armar_empresa()
    _plan(db, ctx, "inicial")  # ya está en su tope de 2 profesionales

    r = client.post(
        "/recursos", headers=token_de(ctx.dueno), json={"nombre": "Box 1", "tipo": "box"}
    )
    assert r.status_code == 201, r.text


def test_desactivar_a_alguien_libera_su_lugar(client, db, armar_empresa):
    """El que se fue del negocio no tiene que seguir ocupando un asiento."""
    ctx = armar_empresa()
    _plan(db, ctx, "inicial")  # ya está en su tope de 2 profesionales
    assert _crear_prof(client, ctx, "Sobra").status_code == 409

    client.patch(
        f"/recursos/{ctx.lucas.id}", headers=token_de(ctx.dueno), json={"activo": False}
    )
    db.expire_all()
    assert _crear_prof(client, ctx, "Ahora si").status_code == 201


def test_no_se_puede_esquivar_el_cupo_reactivando(client, db, armar_empresa):
    """Desactivar a uno, crear al cuarto, y volver a activar al primero."""
    ctx = armar_empresa()
    _plan(db, ctx, "inicial")  # ya está en su tope de 2 profesionales

    client.patch(
        f"/recursos/{ctx.lucas.id}", headers=token_de(ctx.dueno), json={"activo": False}
    )
    _crear_prof(client, ctx, "El tercero")
    db.expire_all()

    r = client.patch(
        f"/recursos/{ctx.lucas.id}", headers=token_de(ctx.dueno), json={"activo": True}
    )
    assert r.status_code == 409, "Reactivar ocupa un asiento igual que dar de alta."


def test_el_override_del_super_admin_pisa_al_plan(client, db, armar_empresa):
    """Para hacerle un cupo especial a un cliente sin inventar un plan."""
    ctx = armar_empresa()
    _plan(db, ctx, "inicial", override=6)
    while _profesionales(db, ctx.empresa.id) < 6:
        r = _crear_prof(client, ctx, f"P{uuid.uuid4().hex[:5]}")
        assert r.status_code == 201, r.text
        db.expire_all()
    assert _crear_prof(client, ctx, "El septimo").status_code == 409


def test_lo_que_ya_existe_no_se_rompe(client, db, armar_empresa):
    """Enforcement solo al ALTA: nadie pierde lo que ya tenía cargado."""
    ctx = armar_empresa()
    _plan(db, ctx, "multi")
    for i in range(8):
        _crear_prof(client, ctx, f"Viejo{i}")
    _plan(db, ctx, "inicial")  # lo bajan de plan
    db.expire_all()

    # Los 10 siguen ahí y siguen funcionando.
    assert _profesionales(db, ctx.empresa.id) == 10
    r = client.get("/recursos", headers=token_de(ctx.dueno))
    assert r.status_code == 200
    # Pero no puede sumar uno más.
    assert _crear_prof(client, ctx, "Uno mas").status_code == 409


# ══════════════════════════════════════════════════════════════════════
#  Pagar cambia el plan
# ══════════════════════════════════════════════════════════════════════

def test_registrar_un_pago_saca_a_la_empresa_de_la_prueba(client, db, armar_empresa, admin):
    ctx = armar_empresa()
    _plan(db, ctx, "gratuito")

    client.post(
        f"/admin/empresas/{ctx.empresa.id}/pagos",
        headers=admin,
        json={"monto": 11900, "metodo": "transferencia", "renovar": True},
    )
    db.expire_all()
    assert db.get(Empresa, ctx.empresa.id).plan == "inicial"


def test_renovar_30_dias_pasa_al_plan_de_entrada_no_al_del_medio(
    client, db, armar_empresa, admin
):
    """Antes saltaba directo a "pro": una cortesía regalaba el cupo de 10."""
    ctx = armar_empresa()
    _plan(db, ctx, "gratuito")

    client.patch(
        f"/admin/empresas/{ctx.empresa.id}/suscripcion",
        headers=admin,
        json={"renovar_30": True},
    )
    db.expire_all()
    assert db.get(Empresa, ctx.empresa.id).plan == "inicial"


def test_un_pago_no_baja_de_plan_a_quien_ya_tenia_uno_mejor(
    client, db, armar_empresa, admin
):
    ctx = armar_empresa()
    _plan(db, ctx, "multi")
    client.post(
        f"/admin/empresas/{ctx.empresa.id}/pagos",
        headers=admin,
        json={"monto": 35990, "metodo": "transferencia", "renovar": True},
    )
    db.expire_all()
    assert db.get(Empresa, ctx.empresa.id).plan == "multi"


def test_el_plan_ya_no_acepta_texto_libre(client, armar_empresa, admin):
    ctx = armar_empresa()
    r = client.patch(
        f"/admin/empresas/{ctx.empresa.id}/suscripcion",
        headers=admin,
        json={"plan": "plan-inventado"},
    )
    assert r.status_code == 422


# ══════════════════════════════════════════════════════════════════════
#  El dueño ve su cupo antes de chocarse con él
# ══════════════════════════════════════════════════════════════════════

def test_mi_suscripcion_muestra_el_cupo_y_la_grilla(client, db, armar_empresa):
    ctx = armar_empresa()
    _plan(db, ctx, "inicial")

    r = client.get("/empresa/mi-suscripcion", headers=token_de(ctx.dueno))
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["plan_etiqueta"] == "Inicial"
    assert d["profesionales_tope"] == 2
    assert d["profesionales_usados"] == 2
    assert len(d["grilla"]) == 3


# ══════════════════════════════════════════════════════════════════════
#  El dueño administra su propio equipo
# ══════════════════════════════════════════════════════════════════════

def test_el_dueno_puede_dar_de_alta_a_su_equipo(client, db, armar_empresa):
    """Antes había que escribirle al super-admin para sumar una recepcionista."""
    ctx = armar_empresa()
    r = client.post(
        "/equipo/usuarios",
        headers=token_de(ctx.dueno),
        json={
            "nombre": "Sofía Recepción",
            "email": f"sofi-{uuid.uuid4().hex[:6]}@example.com",
            "clave": "clave1234",
            "rol": "recepcion",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["rol"] == "recepcion"
    assert r.json()["email_recuperable"] is True


def test_el_dueno_puede_corregir_un_nombre(client, armar_empresa):
    ctx = armar_empresa()
    r = client.patch(
        f"/equipo/usuarios/{ctx.profesional.id}",
        headers=token_de(ctx.dueno),
        json={"nombre": "Nombre Corregido"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["nombre"] == "Nombre Corregido"


def test_el_dueno_no_puede_crear_otro_dueno(client, armar_empresa):
    """Un rol que toca la facturación no se regala desde una pantalla."""
    ctx = armar_empresa()
    r = client.post(
        "/equipo/usuarios",
        headers=token_de(ctx.dueno),
        json={
            "nombre": "Otro Dueño",
            "email": f"otro-{uuid.uuid4().hex[:6]}@example.com",
            "clave": "clave1234",
            "rol": "dueno",
        },
    )
    assert r.status_code == 422


def test_el_dueno_no_se_puede_desactivar_a_si_mismo(client, armar_empresa):
    """Quedaría afuera de su panel y nadie podría reactivarlo."""
    ctx = armar_empresa()
    r = client.patch(
        f"/equipo/usuarios/{ctx.dueno.id}",
        headers=token_de(ctx.dueno),
        json={"activo": False},
    )
    assert r.status_code == 409


def test_no_se_puede_pisar_el_email_de_otra_cuenta(client, db, armar_empresa):
    ctx = armar_empresa()
    r = client.patch(
        f"/equipo/usuarios/{ctx.profesional.id}",
        headers=token_de(ctx.dueno),
        json={"email": ctx.dueno.email},
    )
    assert r.status_code == 409


def test_no_se_puede_tocar_al_equipo_de_otra_empresa(client, armar_empresa):
    a = armar_empresa()
    b = armar_empresa()
    r = client.patch(
        f"/equipo/usuarios/{b.profesional.id}",
        headers=token_de(a.dueno),
        json={"nombre": "Hackeado"},
    )
    assert r.status_code == 404


def test_recepcion_no_administra_el_equipo(client, armar_empresa):
    ctx = armar_empresa()
    r = client.post(
        "/equipo/usuarios",
        headers=token_de(ctx.profesional),
        json={
            "nombre": "Colado",
            "email": f"c-{uuid.uuid4().hex[:6]}@example.com",
            "clave": "clave1234",
            "rol": "profesional",
        },
    )
    assert r.status_code in (401, 403)


# ══════════════════════════════════════════════════════════════════════
#  El tope de USUARIOS (cuentas con clave), que antes no existía
# ══════════════════════════════════════════════════════════════════════

def _crear_usuario(client, ctx, nombre="Recepción"):
    return client.post(
        "/equipo/usuarios",
        headers=token_de(ctx.dueno),
        json={
            "nombre": nombre,
            "email": f"{uuid.uuid4().hex[:10]}@example.com",
            "clave": "clave1234",
            "rol": "recepcion",
        },
    )


def _usuarios(db, empresa_id) -> int:
    from app.models import Usuario

    return db.query(Usuario).filter_by(empresa_id=empresa_id, activo=True).count()


def test_el_plan_inicial_frena_en_la_cuarta_cuenta(client, db, armar_empresa):
    """Antes no había tope de usuarios: el plan de dos profesionales podía
    tener cuarenta cuentas con clave."""
    ctx = armar_empresa()
    _plan(db, ctx, "inicial")

    while _usuarios(db, ctx.empresa.id) < 3:
        assert _crear_usuario(client, ctx).status_code in (200, 201)
        db.expire_all()

    r = _crear_usuario(client, ctx, "La cuarta")
    assert r.status_code == 409
    assert "Inicial" in r.json()["detail"]
    assert "Mi suscripción" in r.json()["detail"], (
        "El error tiene que decir a dónde ir, no solo que no se puede."
    )


def test_desactivar_una_cuenta_libera_su_asiento(client, db, armar_empresa):
    """El empleado que se fue no sigue ocupando lugar."""
    ctx = armar_empresa()
    _plan(db, ctx, "inicial")
    while _usuarios(db, ctx.empresa.id) < 3:
        _crear_usuario(client, ctx)
        db.expire_all()
    assert _crear_usuario(client, ctx, "Sobra").status_code == 409

    client.patch(
        f"/equipo/usuarios/{ctx.profesional.id}",
        headers=token_de(ctx.dueno),
        json={"activo": False},
    )
    db.expire_all()
    assert _crear_usuario(client, ctx, "Ahora si").status_code in (200, 201)


def test_no_se_esquiva_el_cupo_de_cuentas_reactivando(client, db, armar_empresa):
    """Desactivo a uno, creo al que faltaba, y reactivo al primero."""
    ctx = armar_empresa()
    _plan(db, ctx, "inicial")
    while _usuarios(db, ctx.empresa.id) < 3:
        _crear_usuario(client, ctx)
        db.expire_all()

    client.patch(
        f"/equipo/usuarios/{ctx.profesional.id}",
        headers=token_de(ctx.dueno),
        json={"activo": False},
    )
    _crear_usuario(client, ctx, "El que faltaba")
    db.expire_all()

    r = client.patch(
        f"/equipo/usuarios/{ctx.profesional.id}",
        headers=token_de(ctx.dueno),
        json={"activo": True},
    )
    assert r.status_code == 409, "Reactivar ocupa asiento igual que dar de alta."


def test_multi_no_tiene_tope_de_cuentas(client, db, armar_empresa):
    ctx = armar_empresa()
    _plan(db, ctx, "multi")
    for i in range(6):
        assert _crear_usuario(client, ctx, f"Cuenta{i}").status_code in (200, 201)


# ══════════════════════════════════════════════════════════════════════
#  El panel se entera de qué incluye el plan
# ══════════════════════════════════════════════════════════════════════

def test_empresa_actual_dice_que_funciones_incluye_el_plan(client, db, armar_empresa):
    """Sin esto el panel no puede poner el candado, y la única forma de
    enterarse de que algo no está incluido es entrar y que falle adentro."""
    ctx = armar_empresa()
    _plan(db, ctx, "inicial")

    d = client.get("/empresa/actual", headers=token_de(ctx.dueno)).json()

    assert d["plan_codigo"] == "inicial"
    assert d["plan_etiqueta"] == "Inicial"
    assert "campanas" in d["funciones"], "los recordatorios van desde el más barato"
    assert "membresias" not in d["funciones"]
    assert "multisucursal" not in d["funciones"]


def test_el_plan_multi_ve_todo_habilitado(client, db, armar_empresa):
    ctx = armar_empresa()
    _plan(db, ctx, "multi")

    d = client.get("/empresa/actual", headers=token_de(ctx.dueno)).json()

    assert set(d["funciones"]) == {f.value for f in planes.Funcion}


# ══════════════════════════════════════════════════════════════════════
#  Los números no se pueden contradecir entre sí
# ══════════════════════════════════════════════════════════════════════

def test_el_precio_de_config_y_el_del_plan_de_entrada_son_el_mismo():
    """El mismo número vive en dos lugares y tiene que decir lo mismo.

    `settings.precio_lista_mensual` es lo que se le carga a una empresa nueva
    como cuota; `GRILLA[INICIAL].precio` es lo que dice la grilla que muestra
    la landing y la pantalla de suscripción. Si se separan, el negocio ve un
    precio en la página de ventas y le aparece otro en su factura — y se
    entera él antes que nosotros.

    No se unifican en una sola variable porque el precio de la grilla es una
    constante del producto y la cuota es configurable por entorno (para poder
    probar sin tocar código). Este test es el puente.
    """
    from app.core.config import settings

    assert float(settings.precio_lista_mensual) == float(
        planes.GRILLA[planes.PLAN_DE_ENTRADA].precio
    ), (
        "PRECIO_LISTA_MENSUAL y el precio del plan de entrada se separaron. "
        "La landing y la factura van a decir cosas distintas."
    )
