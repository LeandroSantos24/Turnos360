"""Cambiar de plan sin que intervenga nadie de Turnos360.

EL TRÁMITE QUE ESTO SACA
────────────────────────
El cobro por Mercado Pago ya funcionaba de punta a punta —preferencia,
checkout, webhook, acreditación, 30 días— pero le faltaba lo único que
importaba: NO SABÍA QUÉ PLAN SE ESTABA COMPRANDO. Cobraba siempre el mismo
monto y siempre aterrizaba en el plan de entrada. Un negocio que quería pasar a
Pro tenía que escribir y esperar a que alguien le tocara el plan a mano.

LAS DOS REGLAS
──────────────
SUBIR SE PAGA Y SE ACTIVA AL TOQUE. El endpoint NO activa nada: devuelve el
link de pago. El plan se activa cuando la plata entra de verdad, por el
webhook. Si activara al pedirlo, cualquiera subiría a Multi, cerraría el
checkout y se quedaría con el plan gratis.

BAJAR SE ANOTA Y SE APLICA AL VENCER. El mes en curso ya está pagado y se usa
entero. Quitarle Multi a alguien que lo pagó hasta fin de mes es el tipo de
cosa por la que uno deja de bajar de plan y da de baja la cuenta.
"""

import datetime as dt


from app.core import planes
from app.services import cobranza
from app.services import mp_suscripcion as mp_sus

from .conftest import token_de


# ══════════════════════════════════════════════════════════════════════
#  La grilla
# ══════════════════════════════════════════════════════════════════════

def test_la_prueba_no_incluye_multisucursal():
    """EL cambio de esta tanda.

    Si multisucursal se probara gratis, el plan más caro perdería su único
    argumento: el que ya lo usó catorce días no ve por qué pagarlo.
    """
    assert planes.GRILLA[planes.Plan.GRATUITO].sucursales == 1
    assert not planes.incluye("gratuito", planes.Funcion.MULTISUCURSAL)


def test_la_prueba_si_deja_probar_todo_lo_demas():
    """Lo que hace que se quede —membresías, gift cards, cupones— tiene que
    poder probarlo. Si para verlo hay que pagar primero, nunca lo ve.

    Son las FUNCIONES las que van completas. Los CUPOS son los de Inicial, y
    eso es a propósito: la prueba no puede dejar crear más gente de la que el
    plan de entrada soporta, porque después habría que quitársela. La regla
    vive en test_planes_limites_fix031.py.
    """
    prueba = planes.GRILLA[planes.Plan.GRATUITO]
    assert prueba.funciones == planes.GRILLA[planes.Plan.PRO].funciones
    assert prueba.profesionales == planes.GRILLA[planes.Plan.INICIAL].profesionales


def test_enterprise_no_se_vende_solo():
    """No tiene precio de lista. Un link de pago para Enterprise cobraría el
    precio de entrada y activaría cupos ilimitados."""
    assert not planes.se_vende_solo(planes.Plan.ENTERPRISE)
    assert planes.se_vende_solo(planes.Plan.PRO)

    fila = next(p for p in planes.para_mostrar() if p["codigo"] == "enterprise")
    assert fila["a_convenir"] is True
    assert all(
        p["a_convenir"] is False
        for p in planes.para_mostrar()
        if p["codigo"] != "enterprise"
    )


# ══════════════════════════════════════════════════════════════════════
#  La referencia que viaja con el pago
# ══════════════════════════════════════════════════════════════════════

def test_el_plan_viaja_en_la_referencia_y_vuelve_entero():
    """Es el único dato que sobrevive al viaje de ida y vuelta por Mercado
    Pago. Sin él, el webhook no sabe qué acaba de comprar la persona."""
    ref = mp_sus.referencia_de(42, "pro")
    assert mp_sus.empresa_de_referencia(ref) == 42
    assert mp_sus.plan_de_referencia(ref) == "pro"


def test_las_referencias_viejas_se_siguen_acreditando():
    """Mercado Pago reintenta una notificación durante días. Un pago hecho
    antes de este cambio no puede quedar sin acreditar porque le falte el
    plan."""
    assert mp_sus.empresa_de_referencia("sus:42") == 42
    assert mp_sus.plan_de_referencia("sus:42") is None


def test_una_referencia_ajena_no_se_confunde_con_una_cuota():
    """El external_reference de una SEÑA es un id de turno pelado. Si algún día
    las dos cuentas de Mercado Pago fueran la misma, el prefijo es lo único que
    separa «me pagaron una cuota» de «le pagaron una seña a un negocio»."""
    assert mp_sus.empresa_de_referencia("42") is None
    assert mp_sus.empresa_de_referencia("turno:42") is None


# ══════════════════════════════════════════════════════════════════════
#  El precio que se cobra
# ══════════════════════════════════════════════════════════════════════

def test_cada_plan_cobra_lo_suyo(db, armar_empresa):
    ctx = armar_empresa()
    ctx.empresa.precio_mensual = None
    db.flush()

    # Contra la GRILLA y no contra números escritos acá: lo que este test
    # protege es que cada plan cobre LO SUYO, no cuánto sale hoy cada uno.
    for codigo, plan in (
        ("inicial", planes.Plan.INICIAL),
        ("pro", planes.Plan.PRO),
        ("multi", planes.Plan.MULTI),
    ):
        assert mp_sus.precio_de(ctx.empresa, codigo) == planes.GRILLA[plan].precio


def test_el_precio_pactado_le_gana_a_la_grilla(db, armar_empresa):
    """`precio_mensual` es lo que el super-admin le puso en la ficha: un precio
    especial, una cuenta bonificada, o el precio a medida de un Enterprise.
    Existe justamente para pisar la grilla."""
    ctx = armar_empresa()
    ctx.empresa.precio_mensual = 25000
    db.flush()

    assert mp_sus.precio_de(ctx.empresa, "pro") == 25000
    assert mp_sus.precio_de(ctx.empresa, "multi") == 25000


# ══════════════════════════════════════════════════════════════════════
#  El pago activa el plan
# ══════════════════════════════════════════════════════════════════════

def test_pagar_pro_deja_a_la_empresa_en_pro(db, armar_empresa):
    """EL test de todo esto. Antes el pago entraba, el vencimiento se corría y
    el plan quedaba como estaba: se cobraba Pro y el negocio seguía en
    Inicial."""
    ctx = armar_empresa()
    ctx.empresa.plan = "inicial"
    db.flush()

    cobranza.registrar_pago(
        db, ctx.empresa, monto=19900, metodo="mercadopago", plan="pro"
    )
    db.flush()

    assert ctx.empresa.plan == "pro"


def test_pagar_saca_de_la_prueba_aunque_no_se_elija_plan(db, armar_empresa):
    """El camino viejo (botón «renovar», o una transferencia registrada sin
    indicar el plan) tiene que seguir funcionando y caer en el de ENTRADA, no
    en el del medio."""
    ctx = armar_empresa()
    ctx.empresa.plan = "gratuito"
    db.flush()

    cobranza.registrar_pago(db, ctx.empresa, monto=11900, metodo="transferencia")
    db.flush()

    assert ctx.empresa.plan == planes.PLAN_DE_ENTRADA.value


def test_quien_sube_de_plan_no_pierde_los_dias_que_ya_pago(db, armar_empresa):
    """El único caso feo de «30 días desde hoy»: alguien pagó ayer, hoy sube a
    Pro, y perdería 29 días pagos. Paga Pro completo —eso está decidido— pero
    no puede salir con MENOS vencimiento del que entró."""
    ctx = armar_empresa()
    ctx.empresa.plan = "inicial"
    lejos = dt.date.today() + dt.timedelta(days=29)
    ctx.empresa.suscripcion_vence = lejos
    db.flush()

    cobranza.registrar_pago(
        db, ctx.empresa, monto=19900, metodo="mercadopago", plan="pro"
    )
    db.flush()

    assert ctx.empresa.plan == "pro"
    assert ctx.empresa.suscripcion_vence >= lejos


def test_el_que_vencio_hace_meses_cuenta_desde_hoy(db, armar_empresa):
    """Estuvo cortado: no se le regalan las semanas que no pagó."""
    ctx = armar_empresa()
    ctx.empresa.suscripcion_vence = dt.date.today() - dt.timedelta(days=90)
    db.flush()

    cobranza.registrar_pago(
        db, ctx.empresa, monto=11900, metodo="mercadopago", plan="inicial"
    )
    db.flush()

    esperado = dt.date.today() + dt.timedelta(days=cobranza.DIAS_CICLO)
    assert ctx.empresa.suscripcion_vence == esperado


# ══════════════════════════════════════════════════════════════════════
#  Subir y bajar
# ══════════════════════════════════════════════════════════════════════

def test_se_distingue_subir_de_bajar_por_precio(db, armar_empresa):
    """Por PRECIO y no por el orden del enum: es la única definición que no se
    rompe el día que se agregue un plan en el medio de la grilla."""
    ctx = armar_empresa()
    ctx.empresa.plan = "pro"
    db.flush()

    assert cobranza.cambio_de_plan(ctx.empresa, "multi") == "sube"
    assert cobranza.cambio_de_plan(ctx.empresa, "inicial") == "baja"
    assert cobranza.cambio_de_plan(ctx.empresa, "pro") == "mismo"


def test_bajar_no_toca_el_plan_hasta_que_venza(db, armar_empresa):
    """El mes ya está pagado y se usa entero."""
    ctx = armar_empresa()
    ctx.empresa.plan = "multi"
    ctx.empresa.suscripcion_vence = dt.date.today() + dt.timedelta(days=12)
    db.flush()

    cuando = cobranza.programar_baja(db, ctx.empresa, "pro")
    db.flush()

    assert ctx.empresa.plan == "multi", "le quitaron algo que ya había pagado"
    assert ctx.empresa.plan_programado == "pro"
    assert cuando == ctx.empresa.suscripcion_vence


def test_la_baja_se_aplica_sola_cuando_vence(db, armar_empresa):
    ctx = armar_empresa()
    ctx.empresa.plan = "multi"
    ctx.empresa.plan_programado = "pro"
    ctx.empresa.suscripcion_vence = dt.date.today() - dt.timedelta(days=1)
    db.flush()

    cobranza.aplicar_bajas_programadas(db)
    db.refresh(ctx.empresa)

    assert ctx.empresa.plan == "pro"
    assert ctx.empresa.plan_programado is None


def test_la_baja_no_se_adelanta(db, armar_empresa):
    """Si el ciclo sigue vigente, el barrido no la toca."""
    ctx = armar_empresa()
    ctx.empresa.plan = "multi"
    ctx.empresa.plan_programado = "pro"
    ctx.empresa.suscripcion_vence = dt.date.today() + dt.timedelta(days=5)
    db.flush()

    cobranza.aplicar_bajas_programadas(db)
    db.refresh(ctx.empresa)

    assert ctx.empresa.plan == "multi"
    assert ctx.empresa.plan_programado == "pro"


def test_aplicar_bajas_dos_veces_no_hace_nada_la_segunda(db, armar_empresa):
    """El barrido corre todos los días. Sin idempotencia, una baja podría
    encadenarse hacia abajo día tras día."""
    ctx = armar_empresa()
    ctx.empresa.plan = "multi"
    ctx.empresa.plan_programado = "pro"
    ctx.empresa.suscripcion_vence = dt.date.today() - dt.timedelta(days=1)
    db.flush()

    assert cobranza.aplicar_bajas_programadas(db) >= 1
    assert cobranza.aplicar_bajas_programadas(db) == 0
    db.refresh(ctx.empresa)
    assert ctx.empresa.plan == "pro"


def test_pagar_cancela_la_baja_programada(db, armar_empresa):
    """Si pagó, volvió a elegir. Lo que eligió ahora gana sobre lo que había
    anotado antes — si no, pagaría Multi y caería a Pro igual."""
    ctx = armar_empresa()
    ctx.empresa.plan = "multi"
    ctx.empresa.plan_programado = "pro"
    db.flush()

    cobranza.registrar_pago(
        db, ctx.empresa, monto=32900, metodo="mercadopago", plan="multi"
    )
    db.flush()

    assert ctx.empresa.plan == "multi"
    assert ctx.empresa.plan_programado is None


def test_bajar_sin_vencimiento_se_aplica_al_toque(db, armar_empresa):
    """Está en prueba o es una cuenta bonificada: no hay ciclo pago que
    respetar, así que esperar no protegería nada."""
    ctx = armar_empresa()
    ctx.empresa.plan = "multi"
    ctx.empresa.suscripcion_vence = None
    db.flush()

    assert cobranza.programar_baja(db, ctx.empresa, "inicial") is None
    assert ctx.empresa.plan == "inicial"


# ══════════════════════════════════════════════════════════════════════
#  Los endpoints
# ══════════════════════════════════════════════════════════════════════

def test_subir_de_plan_NO_activa_nada_sin_pagar(client, db, armar_empresa):
    """El candado del autoservicio.

    Si el endpoint activara el plan al pedirlo, cualquiera subiría a Multi,
    cerraría el checkout y se quedaría con el plan sin haber pagado un peso.
    """
    ctx = armar_empresa()
    ctx.empresa.plan = "inicial"
    db.commit()

    r = client.post(
        "/empresa/suscripcion/cambiar-plan",
        headers=token_de(ctx.dueno),
        json={"plan": "multi"},
    )

    assert r.status_code == 200, r.text
    assert r.json()["accion"] in ("pagar", "pagar_transferencia")
    db.refresh(ctx.empresa)
    assert ctx.empresa.plan == "inicial", "activó un plan que nadie pagó"


def test_bajar_de_plan_contesta_cuando_se_aplica(client, db, armar_empresa):
    ctx = armar_empresa()
    ctx.empresa.plan = "multi"
    ctx.empresa.suscripcion_vence = dt.date.today() + dt.timedelta(days=10)
    db.commit()

    r = client.post(
        "/empresa/suscripcion/cambiar-plan",
        headers=token_de(ctx.dueno),
        json={"plan": "inicial"},
    )

    assert r.status_code == 200, r.text
    assert r.json()["accion"] == "programada"
    db.refresh(ctx.empresa)
    assert ctx.empresa.plan == "multi"
    assert ctx.empresa.plan_programado == "inicial"


def test_elegir_el_plan_que_ya_tengo_cancela_la_baja(client, db, armar_empresa):
    """La forma más natural de arrepentirse, sin un botón aparte."""
    ctx = armar_empresa()
    ctx.empresa.plan = "multi"
    ctx.empresa.plan_programado = "inicial"
    ctx.empresa.suscripcion_vence = dt.date.today() + dt.timedelta(days=10)
    db.commit()

    r = client.post(
        "/empresa/suscripcion/cambiar-plan",
        headers=token_de(ctx.dueno),
        json={"plan": "multi"},
    )

    assert r.json()["accion"] == "cancelada"
    db.refresh(ctx.empresa)
    assert ctx.empresa.plan_programado is None


def test_nadie_puede_contratar_enterprise_online(client, db, armar_empresa):
    """No tiene precio de lista: el link cobraría el de entrada y activaría
    cupos ilimitados. Es la única forma de que este endpoint regale un plan."""
    ctx = armar_empresa()
    db.commit()

    r = client.post(
        "/empresa/suscripcion/cambiar-plan",
        headers=token_de(ctx.dueno),
        json={"plan": "enterprise"},
    )

    assert r.status_code == 400
    db.refresh(ctx.empresa)
    assert ctx.empresa.plan != "enterprise"


def test_un_plan_inventado_no_pasa(client, db, armar_empresa):
    ctx = armar_empresa()
    db.commit()

    r = client.post(
        "/empresa/suscripcion/cambiar-plan",
        headers=token_de(ctx.dueno),
        json={"plan": "ilimitado-gratis"},
    )
    assert r.status_code == 400


def test_solo_el_dueno_cambia_el_plan(client, db, armar_empresa):
    """Es una decisión comercial: la recepcionista no contrata planes."""
    ctx = armar_empresa()
    db.commit()

    r = client.post(
        "/empresa/suscripcion/cambiar-plan",
        headers=token_de(ctx.profesional),
        json={"plan": "pro"},
    )
    assert r.status_code == 403


def test_mi_suscripcion_dice_el_plan_y_la_baja_anotada(client, db, armar_empresa):
    """La pantalla necesita las dos cosas: cuál es su columna, y si hay una
    baja pendiente que ofrecerle cancelar."""
    ctx = armar_empresa()
    ctx.empresa.plan = "multi"
    ctx.empresa.plan_programado = "pro"
    db.commit()

    d = client.get("/empresa/mi-suscripcion", headers=token_de(ctx.dueno)).json()

    assert d["plan_codigo"] == "multi"
    assert d["plan_programado"] == "pro"
    assert d["plan_programado_etiqueta"] == "Pro"
    assert any(p["codigo"] == "enterprise" for p in d["grilla"])


# ══════════════════════════════════════════════════════════════════════
#  El barrido diario
# ══════════════════════════════════════════════════════════════════════

def test_el_barrido_diario_aplica_las_bajas_sin_reventar(db, armar_empresa, monkeypatch):
    """El barrido de cobranza corre una vez por día y no lo mira nadie.

    EL BUG QUE FIJA ESTE TEST
    Dentro de `avisar_vencimientos` había una variable local llamada `log`
    —una clave de deduplicación, no un logger— que SOMBREABA al logger del
    módulo en toda la función. Cualquier `log.info(...)` agregado ahí adentro,
    aunque estuviera cien líneas más arriba, reventaba con UnboundLocalError:
    Python decide que un nombre es local si se le asigna en cualquier parte del
    cuerpo, no a partir de donde se asigna.

    Como el barrido corre en Celery y su excepción se traga en el log, el
    síntoma habría sido que un día los avisos de vencimiento dejan de salir y
    las bajas de plan dejan de aplicarse, sin que nada avise.
    """
    from app.tasks import emails

    ctx = armar_empresa()
    ctx.empresa.plan = "multi"
    ctx.empresa.plan_programado = "pro"
    ctx.empresa.suscripcion_vence = dt.date.today() - dt.timedelta(days=1)
    db.commit()

    class SesionDelTest:
        def __enter__(self):
            return db

        def __exit__(self, *_):
            db.flush()
            return False

    monkeypatch.setattr(emails, "SessionLocal", SesionDelTest)
    # Sin SMTP los avisos se registran como fallidos y siguen: lo que se
    # verifica acá es que el barrido LLEGA hasta el final.
    emails.avisar_vencimientos()

    db.refresh(ctx.empresa)
    assert ctx.empresa.plan == "pro", "el barrido no aplicó la baja"
    assert ctx.empresa.plan_programado is None
