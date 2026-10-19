from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base

class Category(Base):
    __tablename__ = 'categories'
    __table_args__ = (UniqueConstraint('name', 'type'), CheckConstraint("type IN ('income', 'expense')"))
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60))
    type: Mapped[str] = mapped_column(String(7))
    color: Mapped[str] = mapped_column(String(7), default='#788fa0')
    icon: Mapped[str] = mapped_column(String(8), default='◇')

class Transaction(Base):
    __tablename__ = 'transactions'
    __table_args__ = (CheckConstraint('amount > 0'), CheckConstraint("type IN ('income', 'expense')"), Index('ix_transactions_date_type', 'transaction_date', 'type'))
    id: Mapped[int] = mapped_column(primary_key=True)
    description: Mapped[str] = mapped_column(String(200))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    type: Mapped[str] = mapped_column(String(7))
    category_id: Mapped[int] = mapped_column(ForeignKey('categories.id'))
    transaction_date: Mapped[date] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(30), default='manual', server_default='manual')
    import_key: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

