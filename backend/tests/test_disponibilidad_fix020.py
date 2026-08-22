"""Regresión del fix-020: la precarga tiene que dar EXACTAMENTE lo mismo.

La vidriera pública pedía hasta 31 días × todos los profesionales del
servicio. Cada combinación eran 3 consultas: 744 idas y vueltas a Postgres
para pintar la primera pantalla que ve un cliente.

Ahora se trae la ventana entera de una vez. El riesgo obvio de ese cambio es
que el motor deje de mirar la base y empiece a mirar un diccionario que no
dice lo mismo — y que la diferencia aparezca recién con un sobreturno.

Por eso el test central de este archivo no comprueba una lista esperada: corre
los DOS caminos sobre los mismos datos y exige que den el mismo resultado,
día por día y recurso por recurso. Si alguna vez dejan de coincidir, no hay
forma de que pase desapercibido.
"""

import datetime as dt

import pytest
from sqlalchemy import event

from app.models import ExcepcionAgenda, Recurso, Servicio, Turno
from app.models.agenda import HorarioRecurso
from app.models.enums import EstadoTurno, TipoExcepcion, TipoRecurso
from app.services import disponibilidad as disp

HOY = dt.date(2026, 9, 7)          # un lunes
VENTANA = 14


class Contador:
    """Cuenta las consultas SQL que salen de verdad hacia Postgres."""

    def __init__(self, sesion):
        self.conexion = sesion.connection()
        self.n = 0

    def _sumar(self, *_a, **_k):
        self.n += 1

    def __enter__(self):
        event.listen(self.conexion, "before_cursor_execute", self._sumar)
        return self

    def __exit__(self, *_):
        event.remove(self.conexion, "before_cursor_execute", self._sumar)


@pytest.fixture()
def agenda_cargada(db, armar_empresa):
    """Una agenda con de todo: dos profesionales, turnos en varios estados y
    carriles, un feriado de la empresa, una licencia de uno solo y un horario
    con vigencia acotada. La idea es que ningún camino del motor quede sin
    ejercitar."""
    ctx = armar_empresa()
    emp = ctx.empresa

    otro = Recurso(empresa_id=emp.id, nombre="Sofía Ríos", tipo=TipoRecurso.PERSONA)
    db.add(otro)
    db.flush()

    servicio = ctx.servicio          # "Corte", que ya trae el fixture
    servicio.grupo_agenda = "silla"
    tintura = Servicio(
        empresa_id=emp.id, nombre="Tintura", duracion_min=60, precio=20000,
        grupo_agenda="color",
    )
    db.add(tintura)
    db.flush()
    for r in (ctx.lucas, otro):
        tintura.recursos.append(r)

    # Horarios: el nuevo trabaja media jornada, y solo a partir del miércoles.
    for dia in range(7):
        db.add(HorarioRecurso(
            empresa_id=emp.id, recurso_id=otro.id, dia_semana=dia,
            hora_desde=dt.time(9, 0), hora_hasta=dt.time(13, 0),
            vigencia_desde=HOY + dt.timedelta(days=2),
        ))

    # Un feriado de toda la empresa y una licencia de uno solo.
    db.add(ExcepcionAgenda(
        empresa_id=emp.id, recurso_id=None, tipo=TipoExcepcion.FERIADO,
        fecha_desde=HOY + dt.timedelta(days=4),
        fecha_hasta=HOY + dt.timedelta(days=4),
    ))
    db.add(ExcepcionAgenda(
        empresa_id=emp.id, recurso_id=otro.id, tipo=TipoExcepcion.LICENCIA,
        fecha_desde=HOY + dt.timedelta(days=7),
        fecha_hasta=HOY + dt.timedelta(days=9),
    ))

    # Turnos repartidos: distintos días, distintos carriles, distintos estados.
    estados = [
        EstadoTurno.CONFIRMADO, EstadoTurno.PENDIENTE, EstadoTurno.CANCELADO,
        EstadoTurno.FINALIZADO, EstadoTurno.AUSENTE, EstadoTurno.EN_CURSO,
    ]
    for i, estado in enumerate(estados):
        for recurso, serv, hora in (
            (ctx.lucas, servicio, 10), (otro, tintura, 11),
        ):
            ini = dt.datetime.combine(
                HOY + dt.timedelta(days=i), dt.time(hora, 0), tzinfo=dt.timezone.utc
            )
            db.add(Turno(
                empresa_id=emp.id, recurso_id=recurso.id, cliente_id=ctx.cliente.id,
                servicio_id=serv.id, estado=estado,
                fecha_inicio=ini,
                fecha_fin=ini + dt.timedelta(minutes=serv.duracion_min),
            ))
    db.flush()

    ctx.otro = otro
    ctx.servicio_corte = servicio
    ctx.servicio_tintura = tintura
    return ctx


def _recursos(ctx):
    return [ctx.lucas, ctx.pablo, ctx.otro]


# ══════════════════════════════════════════════════════════════════════════
#  1. EL test: los dos caminos dan lo mismo
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("servicio_attr", ["servicio_corte", "servicio_tintura"])
def test_precargar_da_exactamente_los_mismos_huecos_que_consultar(
    db, agenda_cargada, servicio_attr
):
    ctx = agenda_cargada
    serv = getattr(ctx, servicio_attr)
    recursos = _recursos(ctx)
    hasta = HOY + dt.timedelta(days=VENTANA - 1)

    agenda = disp.precargar(db, ctx.empresa.id, [r.id for r in recursos], HOY, hasta)

    comparados = 0
    for i in range(VENTANA):
        fecha = HOY + dt.timedelta(days=i)
        for r in recursos:
            def huecos(usando):
                return disp.calcular_huecos(
                    db, ctx.empresa.id, r.id, fecha, serv.duracion_min,
                    buffer_min=serv.buffer_min, paso_min=serv.paso_turno_min,
                    grupo_agenda=serv.grupo_agenda, agenda=usando,
                )

            assert huecos(agenda) == huecos(None), (
                f"El {fecha} para {r.nombre} los dos caminos difieren"
            )
            comparados += 1

    # Que el test no se declare verde por no haber comparado nada.
    assert comparados == VENTANA * len(recursos)


def test_hay_dias_con_huecos_y_dias_sin_huecos(db, agenda_cargada):
    """Sin esto, el test de arriba pasaría con dos listas vacías siempre."""
    ctx = agenda_cargada
    serv = ctx.servicio_corte
    hasta = HOY + dt.timedelta(days=VENTANA - 1)
    agenda = disp.precargar(db, ctx.empresa.id, [ctx.otro.id], HOY, hasta)

    con, sin = 0, 0
    for i in range(VENTANA):
        fecha = HOY + dt.timedelta(days=i)
        h = disp.calcular_huecos(
            db, ctx.empresa.id, ctx.otro.id, fecha, serv.duracion_min,
            grupo_agenda=serv.grupo_agenda, agenda=agenda,
        )
        con += bool(h)
        sin += not h

    assert con > 0, "ningún día tuvo huecos: el fixture no está midiendo nada"
    assert sin > 0, "ningún día quedó sin huecos: faltan feriados o vigencias"


# ══════════════════════════════════════════════════════════════════════════
#  2. Que efectivamente sean 3 consultas y no 744
# ══════════════════════════════════════════════════════════════════════════


def test_precargar_son_tres_consultas_sin_importar_el_tamano(db, agenda_cargada):
    ctx = agenda_cargada
    recursos = [r.id for r in _recursos(ctx)]

    with Contador(db) as c:
        disp.precargar(db, ctx.empresa.id, recursos, HOY, HOY)
    chico = c.n

    with Contador(db) as c:
        disp.precargar(db, ctx.empresa.id, recursos, HOY, HOY + dt.timedelta(days=364))
    grande = c.n

    assert chico == 3, f"la precarga de un día hizo {chico} consultas"
    assert grande == 3, f"la de un año hizo {grande}: el costo depende del tamaño"


def test_calcular_con_precarga_no_toca_la_base(db, agenda_cargada):
    """Es el punto de todo el fix: 248 combinaciones, cero consultas nuevas."""
    ctx = agenda_cargada
    serv = ctx.servicio_corte
    recursos = _recursos(ctx)
    hasta = HOY + dt.timedelta(days=VENTANA - 1)
    agenda = disp.precargar(db, ctx.empresa.id, [r.id for r in recursos], HOY, hasta)

    with Contador(db) as c:
        for i in range(VENTANA):
            for r in recursos:
                disp.calcular_huecos(
                    db, ctx.empresa.id, r.id, HOY + dt.timedelta(days=i),
                    serv.duracion_min, grupo_agenda=serv.grupo_agenda, agenda=agenda,
                )

    assert c.n == 0, f"con la agenda precargada igual hizo {c.n} consultas"


def test_sin_precarga_sigue_consultando_como_siempre(db, agenda_cargada):
    """El camino viejo no se tocó: el panel lo sigue usando para una pregunta
    suelta, donde precargar sería trabajo de más."""
    ctx = agenda_cargada
    with Contador(db) as c:
        disp.calcular_huecos(
            db, ctx.empresa.id, ctx.lucas.id, HOY, 30, grupo_agenda="silla"
        )
    assert c.n == 3


# ══════════════════════════════════════════════════════════════════════════
#  3. Preguntar fuera de la ventana revienta (no miente)
# ══════════════════════════════════════════════════════════════════════════


def test_un_dia_fuera_de_la_ventana_es_un_error_y_no_un_dia_libre(db, agenda_cargada):
    """El modo de fallar peligroso: el diccionario contesta "no hay nada
    reservado" y el sistema ofrece un horario que ya está tomado."""
    ctx = agenda_cargada
    agenda = disp.precargar(db, ctx.empresa.id, [ctx.lucas.id], HOY, HOY)

    with pytest.raises(ValueError, match="precargada cubre"):
        disp.calcular_huecos(
            db, ctx.empresa.id, ctx.lucas.id,
            HOY + dt.timedelta(days=1), 30, agenda=agenda,
        )


def test_un_recurso_fuera_de_la_precarga_tambien_es_un_error(db, agenda_cargada):
    ctx = agenda_cargada
    agenda = disp.precargar(db, ctx.empresa.id, [ctx.lucas.id], HOY, HOY)

    with pytest.raises(ValueError, match="no está en la agenda"):
        disp.calcular_huecos(db, ctx.empresa.id, ctx.otro.id, HOY, 30, agenda=agenda)


def test_una_precarga_vacia_no_consulta_nada(db, agenda_cargada):
    """Un servicio sin profesionales asignados no tiene por qué pegarle a la
    base tres veces para descubrir que no hay nada."""
    ctx = agenda_cargada
    with Contador(db) as c:
        agenda = disp.precargar(db, ctx.empresa.id, [], HOY, HOY)
    assert c.n == 0
    assert agenda.turnos == {}


# ══════════════════════════════════════════════════════════════════════════
#  4. Por la vidriera pública, que es quien lo usa
# ══════════════════════════════════════════════════════════════════════════


def test_la_vidriera_devuelve_lo_mismo_que_antes(client, db, agenda_cargada):
    """La prueba de que el cliente ve exactamente los mismos horarios."""
    ctx = agenda_cargada
    ctx.empresa.activa = True
    db.flush()

    r = client.get(
        f"/publico/{ctx.empresa.slug}/horarios",
        params={
            "servicio_id": ctx.servicio_corte.id,
            "desde": HOY.isoformat(),
            "dias": VENTANA,
        },
    )
    assert r.status_code == 200
    dias = r.json()

    # Y lo mismo que sale de calcular a mano, sin precarga, día por día.
    esperado = {}
    for i in range(VENTANA):
        fecha = HOY + dt.timedelta(days=i)
        horas = set()
        for rec in _recursos(ctx):
            horas.update(disp.calcular_huecos(
                db, ctx.empresa.id, rec.id, fecha, ctx.servicio_corte.duracion_min,
                buffer_min=ctx.servicio_corte.buffer_min,
                paso_min=ctx.servicio_corte.paso_turno_min,
                grupo_agenda=ctx.servicio_corte.grupo_agenda,
            ))
        if horas:
            esperado[fecha.isoformat()] = len(horas)

    devuelto = {d["fecha"]: len(d["horas"]) for d in dias}
    # El endpoint recorta por anticipación mínima y ventana; lo que devuelve
    # tiene que ser un subconjunto exacto de lo calculado a mano.
    for fecha, cuantos in devuelto.items():
        assert fecha in esperado
        assert cuantos <= esperado[fecha]


# ══════════════════════════════════════════════════════════════════════════
#  5. Los bordes de la ventana
# ══════════════════════════════════════════════════════════════════════════


def test_un_turno_en_el_ultimo_dia_de_la_ventana_tambien_se_precarga(
    db, agenda_cargada
):
    """El borde de arriba es el que se rompe callado.

    Si la consulta de turnos termina en la medianoche del último día en vez de
    la del siguiente, los turnos de ESE día no entran en la precarga. El motor
    lo ve libre, lo ofrece, y el negocio se come un sobreturno el último día
    del calendario — el más difícil de notar mirando.
    """
    ctx = agenda_cargada
    ultimo = HOY + dt.timedelta(days=VENTANA - 1)
    ini = dt.datetime.combine(ultimo, dt.time(15, 0), tzinfo=dt.timezone.utc)
    db.add(Turno(
        empresa_id=ctx.empresa.id, recurso_id=ctx.lucas.id,
        cliente_id=ctx.cliente.id, servicio_id=ctx.servicio_corte.id,
        estado=EstadoTurno.CONFIRMADO,
        fecha_inicio=ini, fecha_fin=ini + dt.timedelta(minutes=30),
    ))
    db.flush()

    agenda = disp.precargar(db, ctx.empresa.id, [ctx.lucas.id], HOY, ultimo)

    assert agenda.turnos.get((ctx.lucas.id, ultimo)), (
        "el turno del último día de la ventana no quedó precargado"
    )
    con_precarga = disp.calcular_huecos(
        db, ctx.empresa.id, ctx.lucas.id, ultimo, 30,
        grupo_agenda="silla", agenda=agenda,
    )
    consultando = disp.calcular_huecos(
        db, ctx.empresa.id, ctx.lucas.id, ultimo, 30, grupo_agenda="silla"
    )
    assert con_precarga == consultando
    assert ini not in con_precarga, "ofreció un horario que ya está tomado"


def test_un_turno_del_primer_dia_de_la_ventana_tambien_se_precarga(db, agenda_cargada):
    """El borde de abajo, por simetría."""
    ctx = agenda_cargada
    ini = dt.datetime.combine(HOY, dt.time(16, 0), tzinfo=dt.timezone.utc)
    db.add(Turno(
        empresa_id=ctx.empresa.id, recurso_id=ctx.pablo.id,
        cliente_id=ctx.cliente.id, servicio_id=ctx.servicio_corte.id,
        estado=EstadoTurno.CONFIRMADO,
        fecha_inicio=ini, fecha_fin=ini + dt.timedelta(minutes=30),
    ))
    db.flush()

    agenda = disp.precargar(db, ctx.empresa.id, [ctx.pablo.id], HOY, HOY)
    assert agenda.turnos.get((ctx.pablo.id, HOY))
    assert ini not in disp.calcular_huecos(
        db, ctx.empresa.id, ctx.pablo.id, HOY, 30, grupo_agenda="silla", agenda=agenda
    )


# ══════════════════════════════════════════════════════════════════════════
#  6. Que el endpoint sea barato de verdad, no solo el motor
# ══════════════════════════════════════════════════════════════════════════


def test_la_vidriera_no_consulta_una_vez_por_dia(db, agenda_cargada):
    """El fix vive en el llamador, no en el motor: si alguien saca el
    `agenda=agenda` de publico.py, el motor sigue perfecto y la pantalla vuelve
    a costar cientos de consultas. Lo que se fija acá es la FORMA del costo:
    pedir 31 días no puede salir más caro que pedir 7.
    """
    from app.services import publico as svc

    ctx = agenda_cargada
    ctx.empresa.activa = True
    ctx.empresa.reserva_dias_max = 365
    db.flush()

    def consultas(dias):
        with Contador(db) as c:
            svc.huecos(db, ctx.empresa.slug, ctx.servicio_corte.id, None, HOY, dias)
        return c.n

    pocos, muchos = consultas(7), consultas(31)

    assert pocos == muchos, (
        f"7 días costaron {pocos} consultas y 31 costaron {muchos}: "
        "el costo volvió a crecer con el tamaño del pedido"
    )
    assert muchos <= 10, f"{muchos} consultas para una pantalla es demasiado"
