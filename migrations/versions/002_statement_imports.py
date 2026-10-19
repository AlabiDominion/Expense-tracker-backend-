"""Track statement provenance and enforce idempotent imports."""
from alembic import op
import sqlalchemy as sa
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('transactions', sa.Column('source', sa.String(30), nullable=False, server_default='manual'))
    op.add_column('transactions', sa.Column('import_key', sa.String(64), nullable=True))
    op.create_index('uq_transactions_import_key', 'transactions', ['import_key'], unique=True)

def downgrade():
    op.drop_index('uq_transactions_import_key', table_name='transactions')
    op.drop_column('transactions', 'import_key')
    op.drop_column('transactions', 'source')
