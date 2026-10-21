"""Income-backed monthly budget plans."""
from alembic import op
import sqlalchemy as sa
revision='005'
down_revision='004'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('monthly_plans',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('user_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),sa.Column('month',sa.String(7),nullable=False),sa.Column('income',sa.Numeric(12,2),nullable=False),sa.Column('savings',sa.Numeric(12,2),nullable=False),sa.Column('emergency',sa.Numeric(12,2),nullable=False),sa.Column('annual_rent',sa.Numeric(12,2),nullable=False),sa.Column('household_size',sa.Integer(),nullable=False),sa.UniqueConstraint('user_id','month',name='uq_monthly_plan'))
    op.create_index('ix_monthly_plans_user_id','monthly_plans',['user_id'])

def downgrade():
    op.drop_table('monthly_plans')
