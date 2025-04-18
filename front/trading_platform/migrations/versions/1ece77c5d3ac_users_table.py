"""users table

Revision ID: 1ece77c5d3ac
Revises: 
Create Date: 2025-02-27 16:18:25.559682

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1ece77c5d3ac'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('note', schema=None) as batch_op:
        batch_op.drop_index('ix_note_timestamp')

    op.drop_table('note')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('note',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('content', sa.TEXT(), nullable=False),
    sa.Column('timestamp', sa.DATETIME(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('note', schema=None) as batch_op:
        batch_op.create_index('ix_note_timestamp', ['timestamp'], unique=False)

    # ### end Alembic commands ###
