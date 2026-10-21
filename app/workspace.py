from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .database import get_db
from .models import Category, Transaction, User
from .schemas import CategoryInput, CategoryOutput, TransactionInput, TransactionOutput
from .reports import monthly_report
from .security import get_current_user

router = APIRouter(tags=['Private workspace'])

@router.get('/categories', response_model=list[CategoryOutput])
def categories(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.scalars(select(Category).where(Category.user_id == user.id).order_by(Category.id)).all()

@router.post('/categories', response_model=CategoryOutput, status_code=201)
def add_category(body: CategoryInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = Category(**body.model_dump(), user_id=user.id)
    row.name = row.name.strip()
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'A category with this name and type already exists')
    db.refresh(row)
    return row

@router.get('/transactions', response_model=list[TransactionOutput])
def transactions(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.scalars(select(Transaction).where(Transaction.user_id == user.id).order_by(Transaction.transaction_date.desc(), Transaction.id.desc())).all()

def validate_category(body, db, user_id):
    category = db.scalar(select(Category).where(Category.id == body.category_id, Category.user_id == user_id))
    if not category or category.type != body.type:
        raise HTTPException(422, 'Select a category matching the transaction type')

@router.post('/transactions', response_model=TransactionOutput, status_code=201)
def add_transaction(body: TransactionInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    validate_category(body, db, user.id)
    row = Transaction(**body.model_dump(), user_id=user.id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row

@router.put('/transactions/{transaction_id}', response_model=TransactionOutput)
def update_transaction(transaction_id: int, body: TransactionInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.scalar(select(Transaction).where(Transaction.id == transaction_id, Transaction.user_id == user.id))
    if not row:
        raise HTTPException(404, 'Transaction not found')
    validate_category(body, db, user.id)
    for key, value in body.model_dump().items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row

@router.delete('/transactions/{transaction_id}', status_code=204)
def delete_transaction(transaction_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.scalar(select(Transaction).where(Transaction.id == transaction_id, Transaction.user_id == user.id))
    if not row:
        raise HTTPException(404, 'Transaction not found')
    db.delete(row)
    db.commit()
    return Response(status_code=204)

@router.get('/reports/{month}')
def report(month: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        return monthly_report(db, month, user.id)
    except ValueError:
        raise HTTPException(422, 'Month must be YYYY-MM')




@router.delete('/categories/{category_id}', status_code=204)
def delete_category(category_id: int, replacement_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    category = db.scalar(select(Category).where(Category.id == category_id, Category.user_id == user.id))
    if not category:
        raise HTTPException(404, 'Category not found')
    used = db.scalar(select(Transaction.id).where(Transaction.category_id == category_id, Transaction.user_id == user.id).limit(1)) is not None
    if replacement_id is not None:
        replacement = db.scalar(select(Category).where(Category.id == replacement_id, Category.user_id == user.id))
        if replacement_id == category_id or not replacement or replacement.type != category.type:
            raise HTTPException(422, 'Choose a different category with the same transaction type')
    if used and replacement_id is None:
        raise HTTPException(409, 'This category has transactions. Choose a replacement category before deleting it.')
    if used:
        db.execute(update(Transaction).where(Transaction.category_id == category_id, Transaction.user_id == user.id).values(category_id=replacement_id))
    db.delete(category)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'This category is still in use. Refresh and choose a replacement category.')
    return Response(status_code=204)
