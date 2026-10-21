from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base

class Category(Base):
    __tablename__ = 'categories'
    __table_args__ = (UniqueConstraint('user_id', 'name', 'type', name='uq_categories_user_name_type'), CheckConstraint("type IN ('income', 'expense')"))
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(60))
    type: Mapped[str] = mapped_column(String(7))
    color: Mapped[str] = mapped_column(String(7), default='#788fa0')
    icon: Mapped[str] = mapped_column(String(8), default='◇')

class Transaction(Base):
    __tablename__ = 'transactions'
    __table_args__ = (CheckConstraint('amount > 0'), CheckConstraint("type IN ('income', 'expense')"), Index('ix_transactions_date_type', 'transaction_date', 'type'), UniqueConstraint('user_id', 'import_key', name='uq_transactions_user_import'))
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True, index=True)
    description: Mapped[str] = mapped_column(String(200))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    type: Mapped[str] = mapped_column(String(7))
    category_id: Mapped[int] = mapped_column(ForeignKey('categories.id'))
    transaction_date: Mapped[date] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(30), default='manual', server_default='manual')
    import_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

class AuthSession(Base):
    __tablename__ = 'auth_sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)

class AccountToken(Base):
    __tablename__ = 'account_tokens'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)

class Budget(Base):
    __tablename__ = 'budgets'
    __table_args__ = (UniqueConstraint('user_id', 'month', 'category_id', name='uq_budget_month_category'), CheckConstraint('amount > 0'))
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    month: Mapped[str] = mapped_column(String(7))
    category_id: Mapped[int] = mapped_column(ForeignKey('categories.id'))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))

class Debt(Base):
    __tablename__ = 'debts'
    __table_args__ = (CheckConstraint('balance >= 0'), CheckConstraint('apr >= 0'), CheckConstraint('minimum_payment >= 0'))
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    name: Mapped[str] = mapped_column(String(100))
    balance: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    apr: Mapped[Decimal] = mapped_column(Numeric(7, 3))
    minimum_payment: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    due_date: Mapped[date] = mapped_column(Date)

class DebtPayment(Base):
    __tablename__ = 'debt_payments'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    debt_id: Mapped[int] = mapped_column(ForeignKey('debts.id'))
    transaction_id: Mapped[int] = mapped_column(ForeignKey('transactions.id'), unique=True)
    principal: Mapped[Decimal] = mapped_column(Numeric(12, 2))

class MonthlyPlan(Base):
    __tablename__ = 'monthly_plans'
    __table_args__ = (UniqueConstraint('user_id', 'month', name='uq_monthly_plan'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    month: Mapped[str] = mapped_column(String(7))
    income: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    savings: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    emergency: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    annual_rent: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    household_size: Mapped[int] = mapped_column(default=1)
