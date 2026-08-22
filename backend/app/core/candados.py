"""Candados de agenda: que dos personas no se queden con la misma silla.

EL PROBLEMA
-----------
Crear un turno son dos pasos: preguntarle al motor si el hueco está libre y,
si lo está, insertar la fila. Entre esos dos pasos no había NADA.

    Ana (15:00:00.000)  ¿está libre las 15:00?  -> sí
    Beto (15:00:00.040) ¿está libre las 15:00?  -> sí   (Ana todavía no insertó)
    Ana                 INSERT                  -> ok
    Beto                INSERT                  -> ok

Las dos reciben "tu turno quedó reservado". El barbero abre la agenda y tiene
dos personas a la misma hora. No hay error, no hay log, no hay forma de
enterarse hasta que las dos aparecen.

No es una carrera improbable: la vidriera es pública, un negocio que publica
"a las 20:00 abrimos los turnos del sábado" tiene a diez personas apretando el
botón en el mismo segundo, y basta con que dos caigan en la misma ranura.

POR QUÉ UN CANDADO Y NO UNA RESTRICCIÓN EN LA BASE
---------------------------------------------------
La respuesta obvia sería una restricción de exclusión de Postgres sobre
(recurso, rango horario). No sirve acá: la regla de carriles dice que dos
turnos SÍ pueden pisarse en el tiempo si son de grupos distintos —corte y
tintura conviven en la misma silla— y que un servicio sin grupo bloquea con
cualquiera. Eso no se puede escribir como una restricción de exclusión sin
mentir en alguno de los dos lados.

El candado deja la regla donde está —en el motor, que ya la tiene bien— y
solo se asegura de que dos reservas para el mismo recurso no se evalúen a la
vez. Es la solución más chica que resuelve el problema entero.

POR QUÉ UN ADVISORY LOCK Y NO UN SELECT ... FOR UPDATE
--------------------------------------------------------
No hay una fila que trabar. El conflicto es por un hueco que TODAVÍA NO
EXISTE: los dos quieren insertar. `FOR UPDATE` sobre la fila del recurso
también funcionaría, pero traba una fila de datos por un motivo que no tiene
nada que ver con esa fila, y cualquiera que después edite el recurso se
llevaría una sorpresa. El advisory lock dice lo que es: "estoy tocando la
agenda de este recurso, esperá".
"""

from sqlalchemy import text
from sqlalchemy.orm import Session


def bloquear_agenda(db: Session, empresa_id: int, recurso_id: int) -> None:
    """Serializa las reservas de UN recurso hasta el fin de la transacción.

    Se llama ANTES de preguntar si el hueco está libre. El candado se suelta
    solo, en el commit o en el rollback: no hay forma de olvidarse de
    liberarlo, que es el modo clásico de que un candado se convierta en un
    problema peor que el que resolvía.

    Dos reservas para recursos distintos —o para empresas distintas— no se
    esperan entre sí: la clave incluye las dos cosas. Una peluquería con seis
    sillas sigue atendiendo seis reservas simultáneas.
    """
    db.execute(
        text("SELECT pg_advisory_xact_lock(:empresa, :recurso)"),
        {"empresa": empresa_id, "recurso": recurso_id},
    )
