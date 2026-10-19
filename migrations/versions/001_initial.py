"""Initial ledger tables."""
from alembic import op
import sqlalchemy as sa
revision = '001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('categories', sa.Column('id',sa.Integer(),primary_key=True),sa.Column('name',sa.String(60),nullable=False),sa.Column('type',sa.String(7),nullable=False),sa.Column('color',sa.String(7),nullable=False),sa.Column('icon',sa.String(8),nullable=False),sa.UniqueConstraint('name','type'),sa.CheckConstraint("type IN ('income', 'expense')"))
    op.create_table('transactions',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('description',sa.String(200),nullable=False),sa.Column('amount',sa.Numeric(12,2),nullable=False),sa.Column('type',sa.String(7),nullable=False),sa.Column('category_id',sa.Integer(),sa.ForeignKey('categories.id'),nullable=False),sa.Column('transaction_date',sa.Date(),nullable=False),sa.Column('created_at',sa.DateTime(),nullable=False),sa.Column('updated_at',sa.DateTime(),nullable=False),sa.CheckConstraint('amount > 0'),sa.CheckConstraint("type IN ('income', 'expense')"))
    op.create_index('ix_transactions_date_type','transactions',['transaction_date','type'])

def downgrade():
    op.drop_table('transactions')
    op.drop_table('categories')
