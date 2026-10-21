import calendar
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from sqlalchemy import select
from .models import Transaction, Category

def monthly_report(db, month: str, user_id: int):
    start = date.fromisoformat(month + '-01')
    end = date(start.year, start.month, calendar.monthrange(start.year, start.month)[1])
    balance_as_of = min(end, datetime.now(timezone(timedelta(hours=1))).date())
    cumulative = db.scalars(select(Transaction).where(Transaction.user_id == user_id, Transaction.transaction_date <= balance_as_of)).all()
    total_net = sum((r.amount if r.type == 'income' else -r.amount for r in cumulative), Decimal('0.00'))
    rows = db.scalars(select(Transaction).where(Transaction.user_id == user_id, Transaction.transaction_date.between(start, end))).all()
    income = sum((r.amount for r in rows if r.type == 'income'), Decimal('0.00'))
    expense = sum((r.amount for r in rows if r.type == 'expense'), Decimal('0.00'))
    categories = db.scalars(select(Category).where(Category.user_id == user_id)).all()
    return {'total_net': str(total_net), 'balance_as_of': balance_as_of.isoformat(), 'month': month, 'income': str(income), 'expenses': str(expense), 'net_cash_flow': str(income-expense), 'transaction_count': len(rows), 'categories': [{'id': c.id, 'name': c.name, 'total': str(sum((r.amount for r in rows if r.category_id == c.id), Decimal('0.00')))} for c in categories]}


