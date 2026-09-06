"""Fase 1: los planes dejan de ser decorativos.

Hasta acá el "plan" era un string libre y el tope de profesionales se pintaba
en ámbar en el panel del super-admin sin bloquear absolutamente nada: una
empresa del plan de tres podía cargar cuarenta. Y pagar la cuota no cambiaba el
plan, así que se podía pagar por Mercado Pago un año entero y seguir figurando
en "gratuito", con los límites de la prueba.

La grilla acordada (revisada probando el alta como un cliente real):

    Prueba   gratis  →  3 profesionales ·  3 usuarios · 1 local
    Inicial  $13.900 →  3 profesionales ·  3 usuarios · 1 local
    Pro      $19.900 → 10 profesionales · 10 usuarios · 1 local
    Multi    $33.900 → ilimitados       · ilimitados  · 3 locales

La prueba comparte los CUPOS con Inicial y no con Pro. El motivo está en el
test de más abajo, y es lo único de esta grilla que no es una decisión de
precio sino una de diseño.

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

    Inicial da la agenda completa: página de reservas, señas y recordatorios.
    El salto a Pro se paga por el equipo más grande y por lo que hace ganar
    plata; el de Multi, por varios locales de verdad.

    Multi da TRES locales y no cinco: con cinco al precio que tiene,
    Enterprise se queda sin razón de ser salvo para cadenas muy grandes, y el
    salto de precio entre uno y otro deja de tener sentido comercial.

    EL DUEÑO CUENTA COMO PROFESIONAL. Los cupos de acá son personas en la
    agenda, dueño incluido: «1 dueño + 3 que atienden» son 4, no 3. Los
    números y las frases del `resumen` se verifican juntos más abajo.
    """
    g = planes.GRILLA
    assert g[planes.Plan.INICIAL].precio == 13900
    assert g[planes.Plan.INICIAL].profesionales == 4
    assert g[planes.Plan.INICIAL].usuarios == 4
    assert g[planes.Plan.INICIAL].sucursales == 1

    assert g[planes.Plan.PRO].precio == 19990
    assert g[planes.Plan.PRO].profesionales == 11
    assert g[planes.Plan.PRO].usuarios == 11
    assert g[planes.Plan.PRO].sucursales == 1

    assert g[planes.Plan.MULTI].precio == 34990
    assert g[planes.Plan.MULTI].profesionales is None, "Multi = ilimitados"
    assert g[planes.Plan.MULTI].usuarios is None
    assert g[planes.Plan.MULTI].sucursales == 3

    # Cada escalón cuesta más y da más: una grilla donde un plan más caro da
    # menos de algo es una grilla mal armada, y se descubre vendiendo.
    escalones = [planes.Plan.INICIAL, planes.Plan.PRO, planes.Plan.MULTI]
    precios = [g[p].precio for p in escalones]
    assert precios == sorted(precios)


def test_la_prueba_da_exactamente_los_cupos_del_plan_de_entrada():
    """Ni más ni menos que Inicial.

    MÁS es el problema que hizo Leandro visible probando el alta: quien carga
    ocho profesionales en la prueba y después paga el plan de cuatro queda con
    cuatro personas sobrantes, y las dos salidas son malas —borrárselas o
    dejar que el tope no exista—.

    MENOS es el problema simétrico y más silencioso: la prueba mostraría menos
    de lo que el cliente va a comprar, y decide sobre un producto más chico
    que el real. Los dos se evitan con la misma igualdad.
    """
    prueba = planes.GRILLA[planes.Plan.GRATUITO]
    entrada = planes.GRILLA[planes.PLAN_DE_ENTRADA]

    assert prueba.profesionales == entrada.profesionales
    assert prueba.usuarios == entrada.usuarios
    assert prueba.sucursales == entrada.sucursales


def test_el_resumen_de_cada_plan_dice_el_mismo_numero_que_el_cupo():
    """La frase que lee el cliente y el tope que aplica el backend.

    «1 dueño + 3 que atienden» tiene que ser exactamente `profesionales=4`.
    Es el error más caro de la grilla porque no rompe nada: el cliente lee la
    landing, contrata, carga el equipo que le prometieron y el último le
    rebota con un error de límite. Se entera él, no nosotros.

    Se cuenta sumando los números de la frase: si dice «1 dueño + 3», son 4.
    """
    import re

    for plan, lim in planes.GRILLA.items():
        if lim.profesionales is None:
            # Ilimitado: la frase no debería prometer un número.
            assert not re.search(r"\d+\s+que atienden", lim.resumen), (
                f"{plan.value}: el cupo es ilimitado pero el resumen promete "
                f"un número — {lim.resumen!r}"
            )
            continue

        numeros = [int(n) for n in re.findall(r"(\d+)\s*(?:dueño|que atienden)", lim.resumen)]
        if not numeros:
            continue  # la prueba describe el plazo, no el equipo
        assert sum(numeros) == lim.profesionales, (
            f"{plan.value}: el resumen dice {lim.resumen!r} (suma {sum(numeros)}) "
            f"pero el cupo es {lim.profesionales}. El cliente contrata leyendo "
            "la frase y el backend aplica el número."
        )


def test_el_plan_viejo_basico_sigue_entrando_como_inicial():
    """Las empresas que tienen "basico" escrito en la base no se enteran del
    cambio de nombre. Sin esto, `plan_de` no lo reconocería y las mandaría a
    GRATUITO — que ahora da MÁS, así que serían un plan regalado."""
    assert planes.plan_de("basico") is planes.Plan.INICIAL
    assert planes.plan_de("  BASICO ") is planes.Plan.INICIAL


def test_la_prueba_da_todas_las_funciones_con_los_cupos_de_inicial():
    """LA regla que evita el cliente enojado el día que paga.

    Antes la prueba daba los cupos de Pro. Quien cargaba ocho profesionales
    durante los catorce días y después pagaba Inicial —que da tres— quedaba
    con cinco personas sobrantes, y las dos salidas posibles eran malas:
    borrárselas (perder datos que él cargó) o dejarlas pasar (y entonces el
    tope no existe, y nadie sube de plan nunca). Lo planteó Leandro probando
    el alta: «si crea 8 usuarios y después solo paga el plan de 2, ¿qué
    hacemos con los que sobran?».

    La prueba no puede dejar crear más de lo que el plan de entrada soporta.
    Así el día que elige plan no pierde absolutamente nada.

    Las FUNCIONES sí van todas: membresías, gift cards, cupones y campañas son
    lo que hace que se quede, y si para verlas hay que pagar primero, nunca
    las ve. Lo que se acota son los CUPOS, que es lo único que genera el
    problema de arriba.
    """
    prueba = planes.GRILLA[planes.Plan.GRATUITO]
    inicial = planes.GRILLA[planes.Plan.INICIAL]
    pro = planes.GRILLA[planes.Plan.PRO]

    # Cupos: los de Inicial, para que nada sobre al pagar.
    assert prueba.profesionales == inicial.profesionales
    assert prueba.usuarios == inicial.usuarios
    assert prueba.sucursales == inicial.sucursales

    # Funciones: las de Pro, para que vea lo que compra.
    assert prueba.funciones == pro.funciones

    # Multisucursal no se regala: es el único argumento del plan más caro.
    assert prueba.sucursales == 1
    assert not planes.incluye("gratuito", planes.Funcion.MULTISUCURSAL)


def test_pasar_de_la_prueba_a_inicial_no_deja_nada_afuera():
    """La propiedad de fondo, escrita como invariante y no como números.

    Mientras esto valga, el paso de la prueba al plan de entrada no puede
    obligar a borrarle nada a nadie. Si alguien sube los cupos de la prueba
    sin subir los de Inicial, este test es el que avisa.
    """
    prueba = planes.GRILLA[planes.Plan.GRATUITO]
    entrada = planes.GRILLA[planes.PLAN_DE_ENTRADA]

    assert prueba.profesionales is not None
    assert entrada.profesionales is not None
    assert prueba.profesionales <= entrada.profesionales
    assert prueba.usuarios <= entrada.usuarios
    assert prueba.sucursales <= entrada.sucursales


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
    # Enterprise SÍ se ofrece —es una columna más de la grilla— pero sin
    # precio: `a_convenir` es lo que hace que la pantalla muestre «Hablemos»
    # en vez de un botón de pago.
    assert codigos == ["inicial", "pro", "multi", "enterprise"]
    porcodigo = {p["codigo"]: p for p in planes.para_mostrar()}
    assert porcodigo["enterprise"]["a_convenir"] is True
    assert porcodigo["pro"]["a_convenir"] is False


# ══════════════════════════════════════════════════════════════════════
#  El tope BLOQUEA
# ══════════════════════════════════════════════════════════════════════

def test_el_plan_inicial_frena_al_pasarse_del_cupo(client, db, armar_empresa):
    """El tope se lee de la GRILLA y no está escrito acá a mano: así el test
    sigue protegiendo la regla cuando el número cambie, que ya pasó una vez."""
    tope = planes.GRILLA[planes.Plan.INICIAL].profesionales
    ctx = armar_empresa()
    _plan(db, ctx, "inicial")

    while _profesionales(db, ctx.empresa.id) < tope:
        assert _crear_prof(client, ctx, f"P{uuid.uuid4().hex[:5]}").status_code == 201
        db.expire_all()
    assert _profesionales(db, ctx.empresa.id) == tope

    r = _crear_prof(client, ctx, "Uno de más")
    assert r.status_code == 409, f"El plan de {tope} tiene que frenar en el siguiente."
    assert "Inicial" in r.json()["detail"]
    assert "Mi suscripción" in r.json()["detail"], (
        "El mensaje tiene que decir a dónde ir, no solo que no se puede."
    )


def test_el_plan_pro_deja_llegar_a_su_cupo(client, db, armar_empresa):
    tope = planes.GRILLA[planes.Plan.PRO].profesionales
    ctx = armar_empresa()
    _plan(db, ctx, "pro")
    while _profesionales(db, ctx.empresa.id) < tope:
        r = _crear_prof(client, ctx, f"P{uuid.uuid4().hex[:5]}")
        assert r.status_code == 201, r.text
        db.expire_all()
    assert _crear_prof(client, ctx, "Uno de más").status_code == 409


def test_el_plan_multi_no_tiene_tope_de_profesionales(client, db, armar_empresa):
    ctx = armar_empresa()
    _plan(db, ctx, "multi")
    for i in range(12):
        assert _crear_prof(client, ctx, f"Multi{i}").status_code == 201


def _llenar_cupo(client, db, ctx, plan="inicial"):
    """Deja la empresa JUSTO en el tope de profesionales de su plan.

    Antes varios tests se apoyaban en que `armar_empresa` creaba exactamente
    los que Inicial permitía. Eso ató los tests a un número de la grilla por
    la puerta de atrás: el día que Inicial pasó de 2 a 3 profesionales,
    fallaron cuatro tests que no hablaban de precios. Ahora se llena hasta el
    tope, sea cual sea.
    """
    tope = planes.GRILLA[planes.plan_de(plan)].profesionales
    while _profesionales(db, ctx.empresa.id) < tope:
        assert _crear_prof(client, ctx, f"P{uuid.uuid4().hex[:5]}").status_code == 201
        db.expire_all()


def _llenar_cupo_de_cuentas(client, db, ctx, plan="inicial"):
    """Lo mismo que `_llenar_cupo`, pero con las cuentas con clave.

    Estos tests tenían el número escrito a mano (`while _usuarios(...) < 3`) y
    volvieron a romperse exactamente igual el día que Inicial pasó de 3 a 4
    cuentas. Tres tests en rojo que no hablan de cupos es ruido: se lee el
    fallo, se descubre que el producto cambió a propósito, y se pierde la
    confianza en que un rojo significa algo.
    """
    tope = planes.GRILLA[planes.plan_de(plan)].usuarios
    while _usuarios(db, ctx.empresa.id) < tope:
        assert _crear_usuario(client, ctx).status_code in (200, 201)
        db.expire_all()
    return tope
    return tope


def test_un_box_no_ocupa_asiento_del_plan(client, db, armar_empresa):
    """El cupo es de PROFESIONALES. Un box o un equipo no paga asiento."""
    ctx = armar_empresa()
    _plan(db, ctx, "inicial")
    _llenar_cupo(client, db, ctx)

    r = client.post(
        "/recursos", headers=token_de(ctx.dueno), json={"nombre": "Box 1", "tipo": "box"}
    )
    assert r.status_code == 201, r.text


def test_desactivar_a_alguien_libera_su_lugar(client, db, armar_empresa):
    """El que se fue del negocio no tiene que seguir ocupando un asiento."""
    ctx = armar_empresa()
    _plan(db, ctx, "inicial")
    _llenar_cupo(client, db, ctx)
    assert _crear_prof(client, ctx, "Sobra").status_code == 409

    client.patch(
        f"/recursos/{ctx.lucas.id}", headers=token_de(ctx.dueno), json={"activo": False}
    )
    db.expire_all()
    assert _crear_prof(client, ctx, "Ahora si").status_code == 201


def test_no_se_puede_esquivar_el_cupo_reactivando(client, db, armar_empresa):
    """Desactivar a uno, crear al cuarto, y volver a activar al primero."""
    ctx = armar_empresa()
    _plan(db, ctx, "inicial")
    _llenar_cupo(client, db, ctx)

    client.patch(
        f"/recursos/{ctx.lucas.id}", headers=token_de(ctx.dueno), json={"activo": False}
    )
    _crear_prof(client, ctx, "El que entra en el lugar liberado")
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
    assert d["profesionales_tope"] == planes.GRILLA[planes.Plan.INICIAL].profesionales
    assert d["profesionales_usados"] == _profesionales(db, ctx.empresa.id)
    assert len(d["grilla"]) == 4  # inicial, pro, multi y enterprise


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


def test_el_plan_inicial_frena_al_pasarse_del_cupo_de_cuentas(client, db, armar_empresa):
    """Antes no había tope de usuarios: el plan más chico podía tener
    cuarenta cuentas con clave."""
    ctx = armar_empresa()
    _plan(db, ctx, "inicial")
    _llenar_cupo_de_cuentas(client, db, ctx)

    r = _crear_usuario(client, ctx, "La que sobra")
    assert r.status_code == 409
    assert "Inicial" in r.json()["detail"]
    assert "Mi suscripción" in r.json()["detail"], (
        "El error tiene que decir a dónde ir, no solo que no se puede."
    )


def test_desactivar_una_cuenta_libera_su_asiento(client, db, armar_empresa):
    """El empleado que se fue no sigue ocupando lugar."""
    ctx = armar_empresa()
    _plan(db, ctx, "inicial")
    _llenar_cupo_de_cuentas(client, db, ctx)
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
    _llenar_cupo_de_cuentas(client, db, ctx)

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
        f"PRECIO_LISTA_MENSUAL vale {settings.precio_lista_mensual:.0f} y el "
        f"plan de entrada cuesta "
        f"{planes.GRILLA[planes.PLAN_DE_ENTRADA].precio:.0f}. La landing y la "
        "factura van a decir cosas distintas.\n"
        "\n"
        "DÓNDE MIRAR, en este orden: el `.env` de tu máquina (gana sobre todo "
        "lo demás y no está en el repo, así que es el que nadie revisa), "
        "después el default del compose, y por último la grilla de planes.py."
    )


def test_los_defaults_de_docker_compose_coinciden_con_la_grilla():
    """El tercer lugar donde vive el precio, y el que nadie mira.

    EL CASO REAL: los compose traían `${PRECIO_LISTA_MENSUAL:-14990}` en seis
    lugares mientras la grilla decía $11.900. El `.env` de desarrollo lo
    pisaba, así que en la máquina de Leandro todo se veía bien — pero
    cualquier despliegue que no definiera esa variable arrancaba con un precio
    que no existía en ninguna grilla, y no había forma de enterarse salvo
    mirando una factura.

    El primer intento de arreglo fue sacar los defaults. Fue peor: con
    `${VAR}` a secas, docker compose sustituye una CADENA VACÍA cuando la
    variable no está, y pydantic no puede convertirla a float — el backend
    dejaba de levantar. El default tiene que existir; lo que faltaba no era
    quitarlo sino que algo verificara que dice lo mismo que la grilla.

    Esto lee los YAML como texto a propósito: sin parsear, sin importar
    docker, y falla con el archivo y el número que no coinciden.
    """
    import pathlib
    import re

    raiz = pathlib.Path(__file__).resolve().parents[2]
    esperado = {
        "PRECIO_LISTA_MENSUAL": float(planes.GRILLA[planes.PLAN_DE_ENTRADA].precio),
        # La promo no está en la grilla: es un precio de campaña. Lo único que
        # se exige es que no supere al de lista, porque una "promo" más cara
        # que el precio normal es un error de tipeo con cara de descuento.
        "PRECIO_PROMO_MENSUAL": None,
    }

    revisados = 0
    encontrados = 0
    for nombre in ("docker-compose.yml", "docker-compose.prod.yml"):
        ruta = raiz / "infra" / nombre
        if not ruta.exists():
            continue
        encontrados += 1
        texto = ruta.read_text(encoding="utf-8")
        for var, valor in esperado.items():
            # `${VAR}` a secas, SIN `:-`: es la forma que sustituye una cadena
            # vacía y voltea el backend. Se busca aparte porque el patrón de
            # abajo no la matchea, y un test que no ve el bug no protege nada.
            assert not re.search(rf"\$\{{{var}\}}", texto), (
                f"{nombre}: {var} quedó sin default (`${{{var}}}`). Docker "
                "compose sustituye una cadena vacía cuando la variable no "
                "está y pydantic no puede convertirla a float: el backend no "
                "arranca. Poné un default que coincida con la grilla."
            )
            for hallado in re.finditer(
                rf"\$\{{{var}:-([0-9.]*)\}}", texto
            ):
                crudo = hallado.group(1)
                revisados += 1
                assert crudo != "", (
                    f"{nombre}: {var} quedó con default vacío. Docker compose "
                    "sustituye una cadena vacía y el backend no arranca."
                )
                if valor is not None:
                    assert float(crudo) == valor, (
                        f"{nombre}: el default de {var} es {crudo} y la grilla "
                        f"dice {valor:.0f}. Un despliegue sin esa variable "
                        "cobraría un precio que no existe en ninguna grilla."
                    )
                else:
                    assert float(crudo) <= esperado["PRECIO_LISTA_MENSUAL"], (
                        f"{nombre}: la promo ({crudo}) es más cara que el "
                        "precio de lista. Eso es un typo con cara de descuento."
                    )

    # LOS DOS MOTIVOS POR LOS QUE ACÁ NO SE REVISÓ NADA SON DISTINTOS, Y
    # CONFUNDIRLOS ES LO QUE HIZO QUE ESTE TEST NO SIRVIERA ADENTRO DEL
    # CONTENEDOR DURANTE SEMANAS.
    #
    #  · No están los archivos → no hay nada que comparar. Antes esto pasaba
    #    en el contenedor (donde `parents[2]` da `/`) y el test terminaba en
    #    verde sin haber mirado un solo número. Ahora infra/ va montada, así
    #    que si igual faltan es que algo se movió: se SALTEA con el motivo a
    #    la vista, que es distinto de aprobar.
    #  · Están los archivos pero no tienen ningún default → los defaults se
    #    borraron o cambiaron de forma. Eso SÍ es una falla.
    if encontrados == 0:
        pytest.skip(
            f"No encuentro los compose desde {raiz}. En el contenedor tienen "
            "que estar montados (ver el volumen ../infra:/infra en "
            "infra/docker-compose.yml). Este chequeo no corrió."
        )

    assert revisados > 0, (
        "Los compose están pero no tienen ningún default de precio. Si se "
        "cambiaron de forma, este test dejó de proteger nada."
    )


def test_la_grilla_del_frontend_dice_lo_mismo_que_la_del_backend():
    """El cuarto lugar donde vive el precio, y el que ve el cliente primero.

    EL CASO REAL, EL QUE ORIGINÓ ESTE TEST
    ──────────────────────────────────────
    Leandro entró a su panel y vio «$14.990» donde la grilla decía otra cosa:
    «esto es muy mal, no sale 14990, habíamos quedado en 13900». El número
    estaba escrito a mano en cuatro lugares —planes.py, config.py,
    precios.ts y la landing— y arreglar tres de cuatro se ve exactamente
    igual que arreglar los cuatro, hasta que un cliente mira la pantalla que
    quedó vieja.

    Los dos archivos del frontend se leen como TEXTO. No hay forma de
    importar TypeScript desde pytest, y un test que compare contra una copia
    del número acá adentro sería un quinto lugar donde escribirlo — es decir,
    parte del problema.
    """
    import pathlib
    import re

    raiz = pathlib.Path(__file__).resolve().parents[2]
    esperado = {
        p.value: float(planes.GRILLA[p].precio) for p in planes.PLANES_A_LA_VENTA
    }

    # (archivo, cómo se llama el código del plan en ese archivo)
    fuentes = [
        ("frontend/src/lib/precios.ts", "codigo"),
        ("frontend/src/app/page.tsx", "codigo"),
    ]

    revisados = 0
    for nombre, clave in fuentes:
        ruta = raiz / nombre
        if not ruta.exists():
            continue  # en la imagen del backend el frontend no está montado
        texto = ruta.read_text(encoding="utf-8")

        # Cada entrada de la grilla: `codigo: "pro",` … `precio: 19990,`
        # El `.*?` no cruza a la entrada siguiente porque `precio` aparece
        # una sola vez por objeto y siempre después del código.
        encontrados = {
            m.group(1): float(m.group(2))
            for m in re.finditer(
                rf'{clave}:\s*"([a-z]+)",.*?precio:\s*([0-9.]+),', texto, re.S
            )
        }

        for codigo, precio in esperado.items():
            assert codigo in encontrados, (
                f"{nombre} no tiene el plan «{codigo}» de la grilla del backend."
            )
            assert encontrados[codigo] == precio, (
                f"{nombre}: el plan «{codigo}» sale ${encontrados[codigo]:,.0f} "
                f"y la grilla del backend dice ${precio:,.0f}. El cliente lee "
                "el del frontend y le cobramos el del backend."
            )
        revisados += 1

    # Igual que arriba: no es lo mismo «el frontend no está montado» que «el
    # frontend está y le falta un archivo».
    if not (raiz / "frontend/src").exists():
        pytest.skip(
            f"El frontend no está montado en {raiz} (es lo normal adentro del "
            "contenedor del backend). Este chequeo corre en tu máquina con "
            "`pytest` desde la raíz del repo."
        )

    assert revisados == len(fuentes), (
        "Falta alguno de los archivos de precios del frontend: "
        f"revisé {revisados} de {len(fuentes)}. Si se movieron, actualizá "
        "las rutas acá — si no, este test deja de proteger nada."
    )
