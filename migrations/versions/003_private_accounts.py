"""Private user accounts; retain legacy records unassigned until owner setup."""
from alembic import op
import sqlalchemy as sa
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('users',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('name',sa.String(100),nullable=False),sa.Column('email',sa.String(254),nullable=False),sa.Column('password_hash',sa.String(255),nullable=True),sa.Column('created_at',sa.DateTime(),nullable=False),sa.UniqueConstraint('email'))
    for table in ['auth_sessions','account_tokens']:
        op.create_table(table,sa.Column('token_hash',sa.String(64),primary_key=True),sa.Column('user_id',sa.Integer(),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),sa.Column('expires_at',sa.DateTime(),nullable=False))
        op.create_index(f'ix_{table}_user_id',table,['user_id'])
    connection=op.get_bind()
    for table in ['categories','transactions']:
        op.add_column(table,sa.Column('user_id',sa.Integer(),nullable=True))
        op.create_foreign_key(f'fk_{table}_user',table,'users',['user_id'],['id'])
        op.create_index(f'ix_{table}_user_id',table,['user_id'])
    op.create_unique_constraint('uq_categories_user_name_type','categories',['user_id','name','type'])
    for constraint in sa.inspect(connection).get_unique_constraints('categories'):
        if constraint['column_names']==['name','type']:
            op.drop_constraint(constraint['name'],'categories',type_='unique')
    op.drop_index('uq_transactions_import_key',table_name='transactions')
    op.create_unique_constraint('uq_transactions_user_import','transactions',['user_id','import_key'])

def downgrade():
    # Combining private workspaces could collide or expose data. Restore from backup instead.
    raise RuntimeError('Account migration cannot be downgraded automatically.')
