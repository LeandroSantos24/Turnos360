"""Historial de ajustes de la suscripción y anulación de cuotas.

Revision ID: f86b7eda5fb0
Revises: e9b3c47d1a05

EL PROBLEMA QUE ARREGLA
───────────────────────
Mover el vencimiento de una empresa no dejaba rastro. "Renovar 30 días"
regalaba un mes con un click —sin confirmar y sin registrar— y las prórrogas,
que además son acumulativas, tampoco anotaban nada. Si se apretaba por error,
no había forma de enterarse después ni de saber cuál era la fecha anterior.

`ajuste_suscripcion` guarda cada movimiento con su `vence_antes`, así revertir
es restaurar un dato guardado y no adivinar una fecha.

Las columnas de anulación en `pago_suscripcion` son la otra mitad: revertir un
ajuste que vino de un pago tiene que anular ese pago, o quedaría una cuota
cobrada que no cubre ningún período y el MRR seguiría contándola.

NOTA sobre lo que este archivo NO hace: el autogenerate propuso borrar los
índices parciales `ix_pago_empresa_vigente` e `ix_turno_sena_pendiente`. Es un
falso positivo conocido —no los reconoce en los modelos— y borrarlos habría
degradado las consultas de estadísticas y del barrido de señas. Se sacaron a
mano, y el de pago pasó a estar declarado en el modelo para que no vuelva a
aparecer.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f86b7eda5fb0'
down_revision: Union[str, None] = 'e9b3c47d1a05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('ajuste_suscripcion',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('empresa_id', sa.Integer(), nullable=False),
    sa.Column('tipo', sa.String(length=20), nullable=False),
    sa.Column('vence_antes', sa.Date(), nullable=True),
    sa.Column('vence_despues', sa.Date(), nullable=True),
    sa.Column('dias', sa.Integer(), nullable=True),
    sa.Column('detalle', sa.Text(), nullable=True),
    sa.Column('pago_id', sa.Integer(), nullable=True),
    sa.Column('hecho_por', sa.String(length=160), nullable=True),
    sa.Column('creado_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('revertido', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('revertido_en', sa.DateTime(timezone=True), nullable=True),
    sa.Column('revertido_por', sa.String(length=160), nullable=True),
    sa.ForeignKeyConstraint(['empresa_id'], ['empresa.id'], name=op.f('fk_ajuste_suscripcion_empresa_id_empresa')),
    sa.ForeignKeyConstraint(['pago_id'], ['pago_suscripcion.id'], name=op.f('fk_ajuste_suscripcion_pago_id_pago_suscripcion')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_ajuste_suscripcion'))
    )
    op.create_index('ix_ajuste_suscripcion_empresa', 'ajuste_suscripcion', ['empresa_id', 'creado_en'], unique=False)
    op.create_index(op.f('ix_ajuste_suscripcion_empresa_id'), 'ajuste_suscripcion', ['empresa_id'], unique=False)
    op.add_column('pago_suscripcion', sa.Column('anulado', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    op.add_column('pago_suscripcion', sa.Column('anulado_en', sa.DateTime(timezone=True), nullable=True))
    op.add_column('pago_suscripcion', sa.Column('anulado_por', sa.String(length=160), nullable=True))


def downgrade() -> None:
    op.drop_column('pago_suscripcion', 'anulado_por')
    op.drop_column('pago_suscripcion', 'anulado_en')
    op.drop_column('pago_suscripcion', 'anulado')
    op.drop_index(op.f('ix_ajuste_suscripcion_empresa_id'), table_name='ajuste_suscripcion')
    op.drop_index('ix_ajuste_suscripcion_empresa', table_name='ajuste_suscripcion')
    op.drop_table('ajuste_suscripcion')
    # ### end Alembic commands ###