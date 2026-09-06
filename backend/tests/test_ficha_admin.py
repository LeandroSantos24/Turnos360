"""La ficha del negocio en el panel de admin, y el contador de visitas.

«Dale un 360 al panel admin»: el listado mostraba nombre, rubro, slug, usuarios
y vencimiento. Con eso se sabe que una empresa existe y nada más. Para cualquier
pregunta real —¿está pagando?, ¿lo usa?, ¿le queda chico el plan?— había que
cruzar tres pantallas o entrar a la base.

El contador de visitas se agrega ahora aunque no se mire por un mes: recién
dice algo cuando acumuló semanas, así que cada día sin contar es un día que
después no se recupera.
"""

import datetime as dt
import uuid

import pytest

from app.core.crypto import hash_clave
from app.core.seguridad import crear_token_superadmin
from app.models import SuperAdmin, VisitaVidriera
from app.services import visitas


@pytest.fixture()
def admin(db) -> dict:
    sa = SuperAdmin(
        nombre="Admin Ficha",
        email=f"sa-{uuid.uuid4().hex}@turnos360.test",
        hash_clave=hash_clave("clave1234"),
    )
    db.add(sa)
    db.flush()
    return {"Authorization": f"Bearer {crear_token_superadmin(sa.id)}"}


def _ficha(client, admin, empresa_id):
    r = client.get(f"/admin/empresas/{empresa_id}/ficha", headers=admin)
    assert r.status_code == 200, r.text
    return r.json()


# ══════════════════════════════════════════════════════════════════════
#  La ficha
# ══════════════════════════════════════════════════════════════════════

def test_la_ficha_trae_las_cuatro_cosas(client, db, armar_empresa, admin):
    """Identidad, cobranza, uso y actividad. Juntas y no en cuatro llamadas:
    un negocio al día que hace tres meses no carga un turno no es un buen
    cliente, y eso solo se ve mirando las dos cosas al mismo tiempo."""
    ctx = armar_empresa("Con ficha")
    db.commit()

    f = _ficha(client, admin, ctx.empresa.id)
    for clave in ("plan", "suscripcion", "cobranza", "uso", "actividad"):
        assert clave in f, f"Falta {clave}"
    assert f["nombre"] == "Con ficha"


def test_el_uso_dice_usados_y_tope(client, db, armar_empresa, admin):
    """«2 de 3» contesta sola la pregunta de si le queda chico el plan.
    Solo el usado obligaría a recordar de memoria el tope de cada plan."""
    ctx = armar_empresa()
    db.commit()

    uso = _ficha(client, admin, ctx.empresa.id)["uso"]
    assert uso["profesionales"]["usados"] >= 1
    assert uso["profesionales"]["tope"] is not None
    assert uso["sucursales"]["usados"] >= 1


def test_el_tope_pactado_le_gana_al_del_plan(client, db, armar_empresa, admin):
    """Es como se arma un Enterprise a medida. Si la ficha mostrara el del
    plan, diría «10» sobre un cliente al que le vendimos 40."""
    ctx = armar_empresa()
    ctx.empresa.limite_recursos = 40
    db.commit()

    uso = _ficha(client, admin, ctx.empresa.id)["uso"]
    assert uso["profesionales"]["tope"] == 40


def test_el_precio_pactado_le_gana_al_de_la_grilla(client, db, armar_empresa, admin):
    ctx = armar_empresa()
    ctx.empresa.precio_mensual = 25000
    db.commit()

    plan = _ficha(client, admin, ctx.empresa.id)["plan"]
    assert plan["precio"] == 25000
    assert plan["precio_pactado"] is True


def test_un_aviso_pendiente_aparece_en_la_ficha(client, db, armar_empresa, admin):
    """Es lo primero que hay que ver: el negocio ya hizo su parte y espera."""
    from app.services import cobranza

    ctx = armar_empresa()
    cobranza.registrar_aviso(
        db, ctx.empresa, metodo="transferencia", monto=19900, referencia="OP-7"
    )
    db.commit()

    aviso = _ficha(client, admin, ctx.empresa.id)["cobranza"]["aviso_pendiente"]
    assert aviso is not None
    assert aviso["monto"] == 19900
    assert aviso["referencia"] == "OP-7"


def test_sin_aviso_pendiente_viene_en_null(client, db, armar_empresa, admin):
    ctx = armar_empresa()
    db.commit()
    assert _ficha(client, admin, ctx.empresa.id)["cobranza"]["aviso_pendiente"] is None


def test_una_empresa_que_no_existe_da_404(client, admin):
    assert client.get("/admin/empresas/999999/ficha", headers=admin).status_code == 404


def test_sin_ser_superadmin_no_se_ve_la_ficha(client, db, armar_empresa):
    """Tiene datos comerciales: precio pactado, CUIT, contacto."""
    ctx = armar_empresa()
    db.commit()
    assert client.get(f"/admin/empresas/{ctx.empresa.id}/ficha").status_code in (401, 403)


# ══════════════════════════════════════════════════════════════════════
#  El contador de visitas
# ══════════════════════════════════════════════════════════════════════

def test_abrir_la_vidriera_cuenta_una_visita(client, db, armar_empresa):
    """De punta a punta: el contador se dispara desde el endpoint público real.

    Sin un `if status != 200: return` que lo saltee: un test que se salta a sí
    mismo cuando cambia una precondición deja de proteger sin avisar, y el
    verde sigue apareciendo igual.
    """
    from sqlalchemy import select

    from app.core.reloj import hoy_de_pared

    ctx = armar_empresa()
    ctx.dueno.email_verificado = True
    db.commit()

    r = client.get(f"/publico/{ctx.empresa.slug}")
    assert r.status_code == 200, r.text

    db.expire_all()
    fila = db.scalar(
        select(VisitaVidriera).where(
            VisitaVidriera.empresa_id == ctx.empresa.id,
            VisitaVidriera.dia == hoy_de_pared(),
        )
    )
    assert fila is not None, "Abrir la vidriera no contó la visita."
    assert fila.visitas >= 1


def test_dos_visitas_el_mismo_dia_suman_en_la_misma_fila(db, armar_empresa):
    """El UPSERT resuelve el empate. Con un SELECT y después un INSERT, dos
    visitas simultáneas leen «no hay fila», las dos insertan, y una explota
    contra el único — o peor, quedan dos filas y el total se parte en dos."""
    from sqlalchemy import select

    ctx = armar_empresa()
    db.commit()

    visitas.registrar(db, ctx.empresa.id)
    visitas.registrar(db, ctx.empresa.id)
    visitas.registrar(db, ctx.empresa.id)

    filas = list(
        db.scalars(
            select(VisitaVidriera).where(VisitaVidriera.empresa_id == ctx.empresa.id)
        ).all()
    )
    assert len(filas) == 1, "Tiene que haber UNA fila por día."
    assert filas[0].visitas == 3


def test_contar_una_visita_nunca_levanta(db, armar_empresa):
    """LA regla. Se llama desde la página que ve el cliente del negocio: si
    contar fallara y esa excepción subiera, la vidriera no cargaría. Romper una
    reserva real por una estadística sería el peor intercambio posible."""
    visitas.registrar(db, 999999)  # empresa inexistente: FK inválida
    visitas.registrar_por_slug(db, "no-existe-este-slug")
    # Si llegó acá sin excepción, la propiedad se cumple.


def test_un_slug_que_no_existe_no_crea_nada(db, armar_empresa):
    """El INSERT saca el empresa_id de un SELECT: sin filas, no inserta."""
    from sqlalchemy import func, select

    antes = db.scalar(select(func.count(VisitaVidriera.id))) or 0
    visitas.registrar_por_slug(db, "definitivamente-no-existe")
    assert (db.scalar(select(func.count(VisitaVidriera.id))) or 0) == antes


def test_los_dias_sin_visitas_vienen_en_cero(db, armar_empresa):
    """Un gráfico que saltea los días vacíos MIENTE sobre la tendencia:
    dibuja una línea plana donde hubo una caída a cero."""
    ctx = armar_empresa()
    db.commit()
    visitas.registrar(db, ctx.empresa.id)

    serie = visitas.por_dia(db, ctx.empresa.id, 30)
    assert len(serie) == 30, "Siempre 30 puntos, haya o no filas."
    assert serie[-1]["visitas"] == 1, "El último punto es hoy."
    assert all(d["visitas"] == 0 for d in serie[:-1])


def test_la_serie_va_del_mas_viejo_al_mas_nuevo(db, armar_empresa):
    """El último punto es HOY en la zona del negocio, no la del servidor.

    `date.today()` usa la del servidor, que en producción es UTC: entre las
    21:00 y la medianoche de Argentina ya devuelve mañana, y el gráfico
    mostraría un día que todavía no pasó.
    """
    from app.core.reloj import hoy_de_pared

    ctx = armar_empresa()
    db.commit()
    serie = visitas.por_dia(db, ctx.empresa.id, 7)
    dias = [d["dia"] for d in serie]

    assert dias == sorted(dias), "Del más viejo al más nuevo."
    assert len(dias) == 7
    assert dias[-1] == hoy_de_pared().isoformat()
    assert dias[0] == (hoy_de_pared() - dt.timedelta(days=6)).isoformat()


def test_las_visitas_de_una_empresa_no_se_mezclan_con_otra(db, armar_empresa):
    a = armar_empresa("Una")
    b = armar_empresa("Otra")
    db.commit()

    visitas.registrar(db, a.empresa.id)
    visitas.registrar(db, a.empresa.id)
    visitas.registrar(db, b.empresa.id)

    assert visitas.total(db, a.empresa.id) == 2
    assert visitas.total(db, b.empresa.id) == 1
