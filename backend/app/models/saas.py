"""Cobranza del SaaS: lo que cada negocio le paga a Turnos360.

OJO con no confundirlo con app/models/finanzas.py: eso es la caja DEL NEGOCIO
(lo que un cliente le paga a la barbería). Esto es la caja de Leandro: la
cuota mensual que la barbería le paga a Turnos360. Por eso vive fuera del
TenantMixin — no lo ve ningún negocio, solo el super-admin.
"""

import datetime as dt
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PagoSuscripcion(Base):
    """Un pago de cuota registrado a mano por el super-admin.

    Registrar un pago normalmente EMPUJA suscripcion_vence 30 días (lo hace el
    servicio), pero el registro y el vencimiento son cosas separadas a
    propósito: se puede anotar un pago parcial sin renovar, o renovar sin
    cobrar (una cortesía).
    """

    __tablename__ = "pago_suscripcion"
    __table_args__ = (
        Index("ix_pago_suscripcion_fecha", "fecha"),
        Index("ix_pago_suscripcion_empresa_fecha", "empresa_id", "fecha"),
        Index(
            "uq_pago_suscripcion_mp",
            "mp_payment_id",
            unique=True,
            postgresql_where=text("mp_payment_id is not null"),
        ),
        # Idempotencia del registro MANUAL: el diálogo del super-admin manda
        # una clave por apertura. Un doble click o un reintento de red con la
        # misma clave no puede anotar dos cuotas ni correr el vencimiento dos
        # veces.
        Index(
            "uq_pago_suscripcion_idem",
            "clave_idempotencia",
            unique=True,
            postgresql_where=text("clave_idempotencia is not null"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id"), index=True)

    fecha: Mapped[dt.date] = mapped_column(Date)
    monto: Mapped[float] = mapped_column(Numeric(12, 2))
    # Texto libre y no un enum: los métodos de cobro del SaaS cambian solos
    # (transferencia, efectivo, MP, dólares) y no vale una migración por cada uno.
    metodo: Mapped[str] = mapped_column(
        String(40), default="transferencia", server_default=text("'transferencia'")
    )

    # Período que cubre el pago (para el historial: "esto es el mes de julio").
    periodo_desde: Mapped[dt.date | None] = mapped_column(Date)
    periodo_hasta: Mapped[dt.date | None] = mapped_column(Date)

    notas: Mapped[str | None] = mapped_column(Text)
    registrado_por: Mapped[str | None] = mapped_column(String(160))
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # QUÉ fue este pago: "alta" (primer pago), "renovacion", "cambio_plan",
    # "reactivacion" o "manual". Y el plan que pagó. Antes había que deducirlo
    # de las notas.
    tipo: Mapped[str | None] = mapped_column(String(20))
    plan: Mapped[str | None] = mapped_column(String(20))
    intento_id: Mapped[int | None] = mapped_column(ForeignKey("intento_pago.id"))
    clave_idempotencia: Mapped[str | None] = mapped_column(String(64))

    # Id del pago en Mercado Pago, cuando la cuota entró por ahí. Único: es la
    # idempotencia del webhook. Mercado Pago reintenta la misma notificación
    # varias veces y sin esto cada reintento renovaba otros 30 días.
    mp_payment_id: Mapped[str | None] = mapped_column(String(40))

    # Anulación: una cuota anotada por error deja de contar para el historial
    # y para el MRR, pero la fila queda (es plata, tiene que dejar rastro).
    anulado: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    anulado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    anulado_por: Mapped[str | None] = mapped_column(String(160))

    empresa: Mapped["Empresa"] = relationship()  # noqa: F821


class AjusteSuscripcion(Base):
    """Toda vez que se movió el vencimiento de una empresa, y por qué.

    POR QUÉ EXISTE
    ──────────────
    Antes, mover el vencimiento no dejaba ningún rastro. El botón "Renovar 30
    días" regalaba un mes con un click, sin cartel de confirmación y sin
    registrar nada: si se apretaba por error no había forma de enterarse
    después, ni de saber cuál era la fecha anterior para volver atrás. Lo mismo
    con las prórrogas, que además son acumulativas.

    Acá queda la película: quién, cuándo, de qué fecha a qué fecha y por qué.
    Con `vence_antes` guardado, revertir es restaurar un dato, no adivinarlo.

    Ojo con la diferencia con PagoSuscripcion: eso es "cobré una cuota" (plata).
    Esto es "moví la fecha" (efecto). Un pago genera un ajuste, pero hay ajustes
    sin pago —una cortesía, una prórroga— y por eso son dos tablas.
    """

    __tablename__ = "ajuste_suscripcion"
    __table_args__ = (
        Index("ix_ajuste_suscripcion_empresa", "empresa_id", "creado_en"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id"), index=True)

    # Es el REGISTRO DE EVENTOS de la suscripción, no solo de fechas:
    # "pago" | "renovacion" | "prorroga" | "manual" | "reversion" | "plan" |
    # "cancelacion" | "reactivacion" | "cancelada" | "suspension" |
    # "reanudacion" | "aviso" | "aviso_rechazado" | "info_solicitada" |
    # "pago_rechazado" | "pago_devuelto" | "baja_postergada" | "precio"
    tipo: Mapped[str] = mapped_column(String(30))
    vence_antes: Mapped[dt.date | None] = mapped_column(Date)
    vence_despues: Mapped[dt.date | None] = mapped_column(Date)
    dias: Mapped[int | None] = mapped_column(Integer)
    detalle: Mapped[str | None] = mapped_column(Text)

    # El pago que originó el ajuste, si lo hubo. Revertir el ajuste anula el
    # pago: si no, quedaría una cuota cobrada que no cubre ningún período.
    pago_id: Mapped[int | None] = mapped_column(ForeignKey("pago_suscripcion.id"))

    hecho_por: Mapped[str | None] = mapped_column(String(160))
    # Quién lo hizo, por tipo: "dueno" | "admin" | "sistema" | "mercadopago".
    actor_tipo: Mapped[str | None] = mapped_column(String(20))
    # El antes y el después de lo que cambió además de la fecha.
    estado_antes: Mapped[str | None] = mapped_column(String(30))
    estado_despues: Mapped[str | None] = mapped_column(String(30))
    plan_antes: Mapped[str | None] = mapped_column(String(20))
    plan_despues: Mapped[str | None] = mapped_column(String(20))
    monto: Mapped[float | None] = mapped_column(Numeric(12, 2))
    aviso_id: Mapped[int | None] = mapped_column(ForeignKey("aviso_pago.id"))
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Un ajuste revertido no se borra ni se puede revertir dos veces.
    revertido: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    revertido_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revertido_por: Mapped[str | None] = mapped_column(String(160))


class AvisoPago(Base):
    """El negocio avisa "ya te pagué". No es plata todavía: es un aviso.

    POR QUÉ NO ES UN PagoSuscripcion
    ────────────────────────────────
    Una transferencia tarda en verse en la cuenta. Anotar la cuota en el
    momento en que el dueño dice que pagó sería registrar plata que quizá no
    llegó, y el MRR pasaría a ser un número de buena fe.

    Así que el aviso vive aparte: le da al dueño la respuesta que necesita
    ("tu pago está en proceso, en 24 h vas a verlo reflejado") y a Leandro una
    bandeja de entrada con lo que tiene que ir a confirmar contra el banco.
    Cuando confirma, ahí sí nace el PagoSuscripcion y se mueve el vencimiento.

    Los pagos por Mercado Pago NO pasan por acá: los confirma el webhook con la
    respuesta de la API de MP, que es una fuente de verdad y no una promesa.
    """

    __tablename__ = "aviso_pago"
    __table_args__ = (
        Index(
            "ix_aviso_pago_pendiente",
            "creado_en",
            postgresql_where=text("estado = 'pendiente'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id"), index=True)

    metodo: Mapped[str] = mapped_column(String(40), default="transferencia")
    monto: Mapped[float | None] = mapped_column(Numeric(12, 2))
    # Lo que el dueño escriba: número de operación, banco, "lo mandó mi socia".
    referencia: Mapped[str | None] = mapped_column(Text)
    avisado_por: Mapped[str | None] = mapped_column(String(160))
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # EN QUÉ QUEDÓ, en una sola columna.
    #
    # Antes había un `resuelto` booleano y el resto se deducía: resuelto con
    # pago = confirmada, resuelto sin pago = descartada. Deducir el estado de
    # la AUSENCIA de otro dato es frágil —cualquier camino que resuelva sin
    # registrar la cuota queda indistinguible de un rechazo— y sobre todo no
    # dejaba lugar para el POR QUÉ. Un aviso descartado desaparecía de la
    # bandeja sin explicación, así que si el negocio reclamaba a la semana no
    # había nada que mirar.
    #
    #   pendiente        → hay que ir a buscarla al banco
    #   info_solicitada  → falta un dato; el negocio lo ve y puede responder
    #   confirmada       → la plata está y se registró la cuota (pago_id la señala)
    #   rechazada        → no apareció, o no era lo que decía (motivo lo explica)
    estado: Mapped[str] = mapped_column(
        String(20), default="pendiente", server_default=text("'pendiente'")
    )
    # Por qué se rechazó, en las palabras de quien lo rechazó. Es lo que se le
    # contesta al negocio cuando pregunta.
    motivo: Mapped[str | None] = mapped_column(String(200))
    resuelto_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resuelto_por: Mapped[str | None] = mapped_column(String(160))
    # Si se confirmó, la cuota que se registró a partir de este aviso.
    pago_id: Mapped[int | None] = mapped_column(ForeignKey("pago_suscripcion.id"))

    # LO QUE SE ESTÁ PAGANDO, decidido por el servidor al recibir el aviso.
    # Antes el aviso no sabía de qué plan era: al confirmarlo había que
    # adivinar por el monto si era una renovación o una subida a Pro.
    plan: Mapped[str | None] = mapped_column(String(20))
    tipo: Mapped[str | None] = mapped_column(String(20))
    monto_esperado: Mapped[float | None] = mapped_column(Numeric(12, 2))
    # Comprobante: ruta PRIVADA (no se sirve por /uploads). Solo el
    # super-admin lo descarga, por un endpoint autenticado.
    comprobante: Mapped[str | None] = mapped_column(String(200))
    # Cuando el super-admin pide más información, el texto que ve el negocio.
    mensaje_admin: Mapped[str | None] = mapped_column(String(300))

    @property
    def resuelto(self) -> bool:
        """Ya no está esperando. Se deriva: no es una columna."""
        return self.estado not in ("pendiente", "info_solicitada")

    empresa: Mapped["Empresa"] = relationship()  # noqa: F821


class VisitaVidriera(Base):
    """Cuántas veces se abrió la página pública de un negocio, por día.

    QUÉ GUARDA Y QUÉ NO
    ───────────────────
    Un número por empresa y por día. NADA del visitante: ni IP, ni cookie, ni
    user-agent, ni de dónde vino. No hace falta para responder la única
    pregunta que importa —«¿a esta vidriera la mira alguien?»— y todo lo que se
    guarda de más es algo que después hay que cuidar, explicar y borrar.

    Por eso tampoco distingue visitantes únicos: para eso habría que
    identificarlos, que es exactamente lo que no queremos hacer. Dos aperturas
    de la misma persona cuentan dos, y está bien: la tendencia sirve igual.

    POR QUÉ UNA FILA POR DÍA Y NO UN CONTADOR SUELTO
    ───────────────────────────────────────────────
    Un total acumulado no dice nada: 400 visitas puede ser un negocio que
    arranca fuerte o uno que arrancó bien hace un año y hoy no lo abre nadie.
    Con una fila por día se ve la tendencia, que es lo que permite darse cuenta
    de que un cliente se está por ir antes de que lo diga.
    """

    __tablename__ = "visita_vidriera"
    __table_args__ = (
        # Una sola fila por empresa y día: el contador se incrementa con un
        # UPSERT sobre este único. Sin él, dos visitas simultáneas crean dos
        # filas del mismo día y el total queda dividido.
        UniqueConstraint("empresa_id", "dia", name="uq_visita_empresa_dia"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id"), index=True)
    dia: Mapped[dt.date] = mapped_column(Date, index=True)
    visitas: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))


class DebitoAutomatico(Base):
    """La suscripción con débito automático de una empresa en Mercado Pago.

    QUÉ ES, EN CRIOLLO
    ──────────────────
    El negocio pone la tarjeta UNA vez y Mercado Pago le cobra la cuota todos
    los meses solo. Es el modelo de Netflix y Spotify, y es lo que pidió
    Leandro: «pagás suscripción y listo».

    En la API de Mercado Pago esto es un `preapproval` (ellos lo llaman
    "suscripción"). No confundirlo con una `preference` de Checkout Pro, que
    es un pago suelto: la preferencia cobra una vez y se termina, el
    preapproval queda vivo cobrando todos los meses hasta que alguien lo corte.

    POR QUÉ UNA TABLA Y NO COLUMNAS EN `empresa`
    ────────────────────────────────────────────
    Porque los preapprovals viejos siguen hablando. Cuando alguien cancela y
    vuelve a suscribirse, Mercado Pago puede seguir mandando notificaciones
    del anterior durante días —reintentos que ya estaban en vuelo—. Con el id
    guardado en una columna de `empresa`, esa notificación tardía se resolvería
    por empresa y se acreditaría contra la suscripción NUEVA: un cobro del
    ciclo viejo corriendo el vencimiento del ciclo nuevo.

    Con una fila por preapproval, la notificación se resuelve por
    `preapproval_id` y la vieja cae en su propia fila cancelada, donde no hace
    daño. La historia de los cobros vive en `pago_suscripcion`, como siempre.

    QUÉ NO GUARDA
    ─────────────
    Nada de la tarjeta. Ni los últimos cuatro dígitos, ni el emisor, ni el
    token. La tarjeta vive en Mercado Pago y ahí se queda: no la necesitamos
    para nada y guardarla es asumir un riesgo a cambio de cero.
    """

    __tablename__ = "debito_automatico"
    __table_args__ = (
        # El id de Mercado Pago es la identidad de la fila. Único porque es
        # con lo que se resuelven las notificaciones: dos filas con el mismo
        # id serían dos respuestas posibles a "¿de quién es este cobro?".
        UniqueConstraint("preapproval_id", name="uq_debito_preapproval"),
        # UNA SOLA suscripción viva por empresa. Es un índice único PARCIAL:
        # las canceladas no cuentan, así que una empresa puede tener diez
        # canceladas y una viva, pero nunca dos vivas. Sin esto, tocar dos
        # veces "activar débito automático" —o un doble click, o el doble
        # render de React en desarrollo— deja al negocio con dos suscripciones
        # y le cobran la cuota dos veces. Lo frena la base y no el código
        # porque es plata ajena: una condición de carrera acá se ve como un
        # cargo duplicado en el resumen de alguien.
        Index(
            "uq_debito_vivo_por_empresa",
            "empresa_id",
            unique=True,
            postgresql_where=text("estado <> 'cancelled'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id"), index=True)

    # El id del preapproval en Mercado Pago.
    preapproval_id: Mapped[str] = mapped_column(String(64))

    # El estado TAL CUAL lo dice Mercado Pago, sin traducir:
    #   pending    → creada, falta que el dueño ponga la tarjeta
    #   authorized → andando, cobra sola todos los meses
    #   paused     → en pausa (no cobra, se puede reanudar)
    #   cancelled  → terminada, no vuelve
    # Se guarda el string crudo a propósito. Traducirlo a un enum nuestro
    # obligaría a decidir qué hacer con un estado que MP agregue mañana, y la
    # respuesta correcta —guardarlo y mostrarlo tal cual— es esta.
    estado: Mapped[str] = mapped_column(
        String(20), default="pending", server_default=text("'pending'")
    )

    # Qué plan paga esta suscripción y por cuánto. Se guarda acá y no se
    # deduce de la empresa porque son cosas distintas: el débito puede estar
    # autorizado por el monto de Inicial mientras la empresa ya está en Pro
    # (subió de plan y todavía no se re-autorizó). Esa diferencia es
    # exactamente lo que el panel tiene que poder mostrar.
    plan: Mapped[str | None] = mapped_column(String(20))
    monto: Mapped[float | None] = mapped_column(Numeric(12, 2))

    # Cuándo cobra la próxima, según Mercado Pago. Es informativo: la fecha
    # que manda para el servicio es `empresa.suscripcion_vence`.
    proximo_cobro: Mapped[dt.date | None] = mapped_column(Date)

    # Cuántos cobros seguidos vienen fallando. Mercado Pago reintenta solo
    # (cuatro intentos por ciclo) y da de baja la suscripción después de tres
    # ciclos rechazados; esto es para poder AVISARLE al dueño antes de que eso
    # pase, que es lo único que puede evitarlo.
    cobros_fallidos: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0")
    )
    # El motivo del último rechazo, en las palabras de Mercado Pago. Va al
    # cartel del panel: "tu tarjeta venció" se arregla, "no se pudo cobrar" no.
    ultimo_error: Mapped[str | None] = mapped_column(String(200))

    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    actualizada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Quién la cortó: el dueño desde el panel, el super-admin, o Mercado Pago
    # (que la da de baja sola tras tres ciclos rechazados).
    cancelada_por: Mapped[str | None] = mapped_column(String(160))

    empresa: Mapped["Empresa"] = relationship()  # noqa: F821


class AjusteGlobal(Base):
    """Ajustes de Turnos360 que se cambian SIN un deploy.

    QUÉ ENTRA ACÁ Y QUÉ NO
    ──────────────────────
    Entra lo que es de Turnos360 (no de un negocio), que cambia solo, y de lo
    que NO depende ninguna cuenta ni ninguna plata. El caso que la trajo: el
    logo de la marca. Leandro quiere ponerle un gorrito en Navidad y huevos en
    Pascua sin tocar el repo, y tiene razón — eso hoy es reemplazar un archivo
    y desplegar.

    NO entra la configuración del entorno (esa va en variables: los secretos
    no se guardan en la base) NI los precios de los planes. Los precios
    parecen el mismo pedido y no lo son: viven en cinco lugares —la grilla, el
    backend, el compose, precios.ts y la landing—, dos de ellos se COMPILAN
    adentro del bundle, y hay tests que obligan a que los cinco digan lo
    mismo. Una fila en la base sería una sexta fuente que la landing no puede
    leer sin un rebuild: exactamente el «$14.990» que costó esta auditoría
    encontrar. El logo no tiene ese problema porque no hay ninguna lógica que
    dependa de su valor: si está mal, se ve mal, y se arregla en diez segundos.

    Es una tabla clave/valor y no una fila con columnas a propósito: agregar un
    ajuste no puede costar una migración, o dejan de agregarse.
    """

    __tablename__ = "ajuste_global"

    # La clave es la PK: no hace falta un id, y así la base garantiza sola que
    # no haya dos filas peleando por el mismo ajuste.
    clave: Mapped[str] = mapped_column(String(60), primary_key=True)
    # Texto libre. Lo que significa cada valor lo define quien lo lee, y ahí
    # es donde tiene que estar la validación (ver schemas/admin.py::MarcaIn).
    valor: Mapped[str] = mapped_column(Text, default="", server_default=text("''"))

    actualizado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actualizado_por: Mapped[str | None] = mapped_column(String(160))


class IntentoPago(Base):
    """Cada vez que un negocio arranca un pago por Mercado Pago.

    Es lo que faltaba para la conciliación: antes un checkout abandonado o un
    pago rechazado no dejaban rastro, así que el negocio decía «pagué» y no
    había nada que mirar. Ahora cada intento queda con su estado
    (iniciado → aprobado | rechazado | pendiente | cancelado), el monto que el
    SERVIDOR decidió cobrar y el pago que generó si se aprobó.

    El id del intento viaja en el external_reference (`sus:<empresa>:<plan>:i<id>`)
    y vuelve en el webhook: con eso se compara lo que MP cobró contra lo que se
    pidió, y un monto distinto no activa el plan.
    """

    __tablename__ = "intento_pago"
    __table_args__ = (Index("ix_intento_pago_empresa", "empresa_id", "creado_en"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id"), index=True)
    # "alta" | "renovacion" | "cambio_plan" | "reactivacion"
    tipo: Mapped[str] = mapped_column(String(20))
    plan: Mapped[str | None] = mapped_column(String(20))
    monto: Mapped[float] = mapped_column(Numeric(12, 2))
    metodo: Mapped[str] = mapped_column(String(20), default="mercadopago")
    # "iniciado" | "pendiente" | "aprobado" | "rechazado" | "cancelado"
    estado: Mapped[str] = mapped_column(
        String(20), default="iniciado", server_default=text("'iniciado'")
    )
    detalle: Mapped[str | None] = mapped_column(String(200))
    mp_payment_id: Mapped[str | None] = mapped_column(String(40))
    pago_id: Mapped[int | None] = mapped_column(Integer)
    iniciado_por: Mapped[str | None] = mapped_column(String(160))
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    actualizado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditoriaAdmin(Base):
    """Qué hizo cada super-admin, sobre qué empresa, y qué cambió.

    Toda acción administrativa que toca plata, acceso o una suscripción deja
    acá una fila con el estado ANTES y DESPUÉS. Es append-only: no hay
    endpoint que la modifique ni la borre.
    """

    __tablename__ = "auditoria_admin"
    __table_args__ = (
        Index("ix_auditoria_admin_empresa", "empresa_id", "creado_en"),
        Index("ix_auditoria_admin_fecha", "creado_en"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    admin_id: Mapped[int | None] = mapped_column(Integer)
    admin_email: Mapped[str] = mapped_column(String(160))
    accion: Mapped[str] = mapped_column(String(40))
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresa.id"))
    descripcion: Mapped[str | None] = mapped_column(String(300))
    antes: Mapped[dict | None] = mapped_column(JSONB)
    despues: Mapped[dict | None] = mapped_column(JSONB)
    ip: Mapped[str | None] = mapped_column(String(45))
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
