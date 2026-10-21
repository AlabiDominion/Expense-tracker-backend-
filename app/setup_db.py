import re
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from alembic import command
from alembic.config import Config
from .config import settings


def setup():
    url = make_url(settings.database_url)
    if url.get_backend_name() != 'mysql':
        raise SystemExit('Setup expects a MySQL DATABASE_URL.')
    database = url.database
    if not database or not re.fullmatch(r'[A-Za-z0-9_]+', database):
        raise SystemExit('Database name must contain letters, numbers or underscores.')
    server = create_engine(url._replace(database=None), pool_pre_ping=True)
    try:
        with server.connect() as connection:
            connection.execute(text(f'CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'))
            connection.commit()
        root = Path(__file__).resolve().parents[1]
        config = Config(str(root / 'alembic.ini'))
        config.set_main_option('script_location', str(root / 'migrations'))
        command.upgrade(config, 'head')
        # Categories are created per user at registration; no shared workspace is seeded.
        print('MySQL database initialized. Demo transactions were not imported.')
    finally:
        server.dispose()

if __name__ == '__main__':
    setup()


