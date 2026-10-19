from fastapi import FastAPI, Depends, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db
from .models import Category, Transaction
from .schemas import CategoryInput, CategoryOutput, TransactionInput, TransactionOutput
from .reports import monthly_report

app = FastAPI(title='ECEWS Expense Tracker', version='1.0.0', description='Single-user interview project. All amounts are NGN.')
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=['GET', 'POST', 'PUT', 'DELETE'], allow_headers=['Content-Type'])

@app.get('/health')
def health(db: Session = Depends(get_db)):
    try:
        db.execute(select(Category.id).limit(1))
    except SQLAlchemyError:
        raise HTTPException(503, 'Database unavailable or migrations not applied')
    return {'status': 'ok', 'database': db.get_bind().dialect.name}

@app.get('/categories', response_model=list[CategoryOutput])
def categories(db: Session = Depends(get_db)):
    return db.scalars(select(Category).order_by(Category.id)).all()

@app.post('/categories', response_model=CategoryOutput, status_code=201)
def add_category(body: CategoryInput, db: Session = Depends(get_db)):
    row = Category(**body.model_dump())
    row.name = row.name.strip()
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'A category with this name and type already exists')
    db.refresh(row)
    return row

@app.get('/transactions', response_model=list[TransactionOutput])
def transactions(db: Session = Depends(get_db)):
    return db.scalars(select(Transaction).order_by(Transaction.transaction_date.desc(), Transaction.id.desc())).all()

def validate_category(body, db):
    category = db.get(Category, body.category_id)
    if not category or category.type != body.type:
        raise HTTPException(422, 'Select a category matching the transaction type')

@app.post('/transactions', response_model=TransactionOutput, status_code=201)
def add_transaction(body: TransactionInput, db: Session = Depends(get_db)):
    validate_category(body, db)
    row = Transaction(**body.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row

@app.put('/transactions/{transaction_id}', response_model=TransactionOutput)
def update_transaction(transaction_id: int, body: TransactionInput, db: Session = Depends(get_db)):
    row = db.get(Transaction, transaction_id)
    if not row:
        raise HTTPException(404, 'Transaction not found')
    validate_category(body, db)
    for key, value in body.model_dump().items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row

@app.delete('/transactions/{transaction_id}', status_code=204)
def delete_transaction(transaction_id: int, db: Session = Depends(get_db)):
    row = db.get(Transaction, transaction_id)
    if not row:
        raise HTTPException(404, 'Transaction not found')
    db.delete(row)
    db.commit()
    return Response(status_code=204)

@app.get('/reports/{month}')
def report(month: str, db: Session = Depends(get_db)):
    try:
        return monthly_report(db, month)
    except ValueError:
        raise HTTPException(422, 'Month must be YYYY-MM')




from .statements import router as statement_router
app.include_router(statement_router)


@app.delete('/categories/{category_id}', status_code=204)
def delete_category(category_id: int, replacement_id: int | None = None, db: Session = Depends(get_db)):
    category = db.get(Category, category_id)
    if not category:
        raise HTTPException(404, 'Category not found')
    used = db.scalar(select(Transaction.id).where(Transaction.category_id == category_id).limit(1)) is not None
    if replacement_id is not None:
        replacement = db.get(Category, replacement_id)
        if replacement_id == category_id or not replacement or replacement.type != category.type:
            raise HTTPException(422, 'Choose a different category with the same transaction type')
    if used and replacement_id is None:
        raise HTTPException(409, 'This category has transactions. Choose a replacement category before deleting it.')
    if used:
        db.execute(update(Transaction).where(Transaction.category_id == category_id).values(category_id=replacement_id))
    db.delete(category)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'This category is still in use. Refresh and choose a replacement category.')
    return Response(status_code=204)
