"""Budgets and personal debt planning."""
from alembic import op
import sqlalchemy as sa
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('budgets',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('user_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),sa.Column('month',sa.String(7),nullable=False),sa.Column('category_id',sa.Integer(),sa.ForeignKey('categories.id'),nullable=False),sa.Column('amount',sa.Numeric(12,2),nullable=False),sa.UniqueConstraint('user_id','month','category_id',name='uq_budget_month_category'),sa.CheckConstraint('amount > 0'))
    op.create_table('debts',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('user_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),sa.Column('name',sa.String(100),nullable=False),sa.Column('balance',sa.Numeric(12,2),nullable=False),sa.Column('apr',sa.Numeric(7,3),nullable=False),sa.Column('minimum_payment',sa.Numeric(12,2),nullable=False),sa.Column('due_date',sa.Date(),nullable=False),sa.CheckConstraint('balance >= 0'),sa.CheckConstraint('apr >= 0'),sa.CheckConstraint('minimum_payment >= 0'))
    op.create_table('debt_payments',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('user_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),sa.Column('debt_id',sa.Integer(),sa.ForeignKey('debts.id'),nullable=False),sa.Column('transaction_id',sa.Integer(),sa.ForeignKey('transactions.id'),nullable=False,unique=True),sa.Column('principal',sa.Numeric(12,2),nullable=False))
    for table in ['budgets','debts','debt_payments']:
        op.create_index('ix_'+table+'_user_id',table,['user_id'])

def downgrade():
    for table in ['debt_payments','debts','budgets']:
        op.drop_table(table)
