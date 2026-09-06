"""`precio_mensual` vuelve a significar PRECIO PACTADO, y nada más.

QUÉ PASÓ
────────
Leandro abrió el panel de un negocio de prueba y vio «$14.990» donde la grilla
decía $13.900: «esto es muy mal, no sale 14990, habíamos quedado en 13900».

El número no estaba mal escrito en ningún lado. Al registrarse, cada empresa
copiaba el precio de lista DEL MOMENTO a `empresa.precio_mensual`. Esa copia es
una foto: sacada el día del alta, de un negocio que todavía no había comprado
nada, y que dejó de parecerse al precio real apenas la lista se movió. Sus
empresas de prueba nacieron cuando el default del compose decía 14990.

QUÉ HACE ESTA MIGRACIÓN
───────────────────────
Borra esas fotos, y SOLO esas. `precio_mensual` pasa a leerse como "precio
pactado, distinto del de lista"; NULL significa "sin trato especial, paga lo
que dice su plan" (services/suscripcion.py · cuota_de).

A QUIÉN LE TOCA — el criterio, que es lo importante acá
────────────────────────────────────────────────────────
Borrar un precio es destruir información, así que la condición es estrecha a
propósito. Se limpia una empresa solo si cumple LAS TRES:

  1. Está en período de prueba (`prueba_hasta >= hoy`). Con la prueba corriendo
     todavía no compró nada.
  2. No tiene NI UN pago registrado. Si alguna vez cobró algo, hubo un acuerdo
     y ese número puede ser el acordado.
  3. Se registró sola por la web (`de_registro_publico`). Nadie habló con ella,
     así que no hay nada que negociar; una empresa cargada por el super-admin
     puede tener un precio puesto a mano y no se toca.

Una empresa con precio pactado de verdad —un piloto bonificado, un descuento
por referido— falla la 1 o la 3 y queda intacta. Si el criterio igual dejara
alguna afuera, el arreglo es cargarle el precio en la ficha comercial, que es
un minuto. Al revés no: un precio borrado de más no se recupera.

NO SE PUEDE DESHACER, y el downgrade lo dice en vez de fingir que sí. Volver a
poner el precio de lista de HOY en esas filas no restauraría nada: pondría una
foto nueva, que es justamente el problema que esto viene a sacar.

Revision ID: 0003_precio_pactado
Revises: 0002_visitas
"""

from alembic import op

revision = "0003_precio_pactado"
down_revision = "0002_visitas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE empresa
           SET precio_mensual = NULL
         WHERE precio_mensual IS NOT NULL
           AND de_registro_publico IS TRUE
           AND prueba_hasta IS NOT NULL
           AND prueba_hasta >= CURRENT_DATE
           AND NOT EXISTS (
                 SELECT 1 FROM pago_suscripcion p
                  WHERE p.empresa_id = empresa.id
               )
        """
    )


def downgrade() -> None:
    # A propósito: no hay vuelta atrás. Ver el docstring.
    pass
