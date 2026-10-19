import calendar
from datetime import date
from decimal import Decimal
from sqlalchemy import select
from .models import Transaction, Category

def monthly_report(db, month: str):
    start = date.fromisoformat(month + '-01')
    end = date(start.year, start.month, calendar.monthrange(start.year, start.month)[1])
    rows = db.scalars(select(Transaction).where(Transaction.transaction_date.between(start, end))).all()
    income = sum((r.amount for r in rows if r.type == 'income'), Decimal('0.00'))
    expense = sum((r.amount for r in rows if r.type == 'expense'), Decimal('0.00'))
    categories = db.scalars(select(Category)).all()
    return {'month': month, 'income': str(income), 'expenses': str(expense), 'net_cash_flow': str(income-expense), 'transaction_count': len(rows), 'categories': [{'id': c.id, 'name': c.name, 'total': str(sum((r.amount for r in rows if r.category_id == c.id), Decimal('0.00')))} for c in categories]}
