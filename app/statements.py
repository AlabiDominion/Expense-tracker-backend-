from datetime import date
from decimal import Decimal
from hashlib import sha256
from typing import Literal
import re
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from .database import get_db
from .models import Category, Transaction
from .statement_parser import parse_statement, StatementError

router = APIRouter(prefix='/statements', tags=['Statement imports'])
MAX_BYTES = 10 * 1024 * 1024

class ImportRow(BaseModel):
    description: str = Field(min_length=1, max_length=200, pattern=r'.*\S.*')
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    transaction_date: date
    type: Literal['income','expense']
    category_id: int | None = None
    reference: str = Field(min_length=1, max_length=300)

class ImportRequest(BaseModel):
    scope: str = Field(pattern=r'^[a-f0-9]{64}$')
    rows: list[ImportRow] = Field(min_length=1, max_length=2000)

def import_key(scope, reference):
    return sha256(f'moniepoint|{scope}|{reference}'.encode()).hexdigest()

def signature(day, kind, amount, description):
    return (str(day),kind,Decimal(str(amount)).quantize(Decimal('.01')),re.sub(r'\s+',' ',description).strip().casefold())

def suggest_category(description, kind, categories):
    rules = [('salary','Salary'),('freelance','Freelance')] if kind=='income' else [('data purchase','Bills & utilities'),('airtime','Bills & utilities'),('tax','Bills & utilities'),('electric','Bills & utilities'),('fuel','Transport'),('uber','Transport'),('bolt','Transport'),('restaurant','Food & dining'),('chicken republic','Food & dining')]
    for keyword,name in rules:
        if keyword in description.lower():
            match = next((c for c in categories if c.type==kind and c.name==name),None)
            if match:
                return match.id
    return None

@router.post('/preview')
async def preview(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        content = await file.read(MAX_BYTES+1)
    finally:
        await file.close()
    if len(content)>MAX_BYTES:
        raise HTTPException(413,'Please upload a PDF smaller than 10 MB.')
    try:
        result = await run_in_threadpool(parse_statement, content)
    except StatementError as error:
        raise HTTPException(422,str(error))
    scope = result['scope']
    categories = db.scalars(select(Category)).all()
    saved = db.scalars(select(Transaction)).all()
    known = {t.import_key for t in saved if t.import_key}
    signatures = {signature(t.transaction_date,t.type,t.amount,t.description) for t in saved}
    seen = set()
    for index,row in enumerate(result['rows']):
        key = import_key(scope,row['reference'])
        row['row_id']=index
        row['duplicate']=key in known or key in seen
        row['possible_duplicate']=not row['duplicate'] and signature(row['transaction_date'],row['type'],row['amount'],row['description']) in signatures
        row['category_id']=suggest_category(row['description'],row['type'],categories)
        seen.add(key)
    return result

@router.post('/import')
def commit_import(body: ImportRequest, db: Session = Depends(get_db)):
    known = set(db.scalars(select(Transaction.import_key).where(Transaction.import_key.is_not(None))).all())
    categories = {c.id:c for c in db.scalars(select(Category)).all()}
    imported,skipped = 0,0
    ids = []
    for row in body.rows:
        key = import_key(body.scope,row.reference)
        if key in known:
            skipped += 1
            continue
        category_id = row.category_id
        if category_id is not None:
            category = categories.get(category_id)
            if not category or category.type != row.type:
                raise HTTPException(422,'Each category must match its transaction type.')
        else:
            category = next((c for c in categories.values() if c.type==row.type and c.name=='Uncategorized'),None)
            if category is None:
                category=Category(name='Uncategorized',type=row.type,color='#788fa0',icon='◇')
                db.add(category)
                db.flush()
                categories[category.id]=category
            category_id=category.id
        transaction=Transaction(**row.model_dump(exclude={'reference','category_id'}),category_id=category_id,source='moniepoint_pdf',import_key=key)
        db.add(transaction)
        known.add(key)
        imported += 1
        ids.append(transaction)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409,'A matching import was saved at the same time. Preview the statement again.')
    return {'imported':imported,'skipped':skipped,'transaction_ids':[row.id for row in ids]}
