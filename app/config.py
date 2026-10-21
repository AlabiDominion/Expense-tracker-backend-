from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = 'mysql+pymysql://root:password@127.0.0.1:3306/expense_tracker?charset=utf8mb4'
    cors_origins: list[str] = ['http://localhost:5173', 'http://127.0.0.1:5173', 'http://localhost:5174', 'http://127.0.0.1:5174', 'http://localhost:5175', 'http://127.0.0.1:5175']
    cookie_secure: bool = False
    session_days: int = 7
    frontend_url: str = 'http://localhost:5173'
    smtp_host: str = ''
    smtp_port: int = 587
    smtp_username: str = ''
    smtp_password: str = ''
    smtp_from: str = ''
    smtp_ssl: bool = False
    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[1] / '.env', extra='ignore')

settings = Settings()

