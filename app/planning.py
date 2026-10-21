from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, ConfigDict, field_validator
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .database import get_db
from .models import Budget, Debt, DebtPayment, Category, Transaction, User, MonthlyPlan
from .security import get_current_user

router = APIRouter(tags=['Financial planning'])

class BudgetInput(BaseModel):
    month: str = Field(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    category_id: int
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    @field_validator('month')
    @classmethod
    def valid_month(cls, value):
        date.fromisoformat(value+'-01')
        return value

class BudgetOutput(BudgetInput):
    model_config = ConfigDict(from_attributes=True)
    id: int

class PlanInput(BaseModel):
    month: str = Field(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    income: Decimal = Field(gt=0,max_digits=12,decimal_places=2)
    savings: Decimal = Field(ge=0,max_digits=12,decimal_places=2)
    emergency: Decimal = Field(ge=0,max_digits=12,decimal_places=2)
    annual_rent: Decimal = Field(ge=0,max_digits=12,decimal_places=2)
    household_size: int = Field(ge=1,le=30)
    @field_validator('month')
    @classmethod
    def valid_month(cls,value):
        date.fromisoformat(value+'-01')
        return value

class PlanOutput(PlanInput):
    model_config = ConfigDict(from_attributes=True)
    id: int

class TemplateLine(BaseModel):
    name: str = Field(min_length=1,max_length=60)
    amount: Decimal = Field(gt=0,max_digits=12,decimal_places=2)
    @field_validator('name')
    @classmethod
    def clean_name(cls,value):
        if not value.strip():
            raise ValueError('Enter a category name')
        return value.strip()

class TemplateInput(PlanInput):
    allocations: list[TemplateLine] = Field(min_length=1,max_length=30)

def plan_total(db,user_id,month):
    return sum(db.scalars(select(Budget.amount).where(Budget.user_id==user_id,Budget.month==month).with_for_update()).all(),Decimal('0.00'))

def check_allocation(income,savings,emergency,total):
    if total+savings+emergency>income:
        raise HTTPException(422,'Allocations, savings and emergency reserves cannot exceed your planned monthly income.')

def write_plan(db,body,user_id):
    row=db.scalar(select(MonthlyPlan).where(MonthlyPlan.user_id==user_id,MonthlyPlan.month==body.month).with_for_update())
    values=body.model_dump(exclude={'allocations'})
    if row:
        for key,value in values.items():
            setattr(row,key,value)
    else:
        row=MonthlyPlan(**values,user_id=user_id)
        db.add(row)
    return row

@router.put('/monthly-plan',response_model=PlanOutput)
def save_plan(body:PlanInput,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    db.scalar(select(User).where(User.id==user.id).with_for_update())
    check_allocation(body.income,body.savings,body.emergency,plan_total(db,user.id,body.month))
    row=write_plan(db,body,user.id)
    db.commit()
    db.refresh(row)
    return row

@router.post('/budget-template')
def apply_template(body:TemplateInput,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    db.scalar(select(User).where(User.id==user.id).with_for_update())
    names=[line.name.casefold() for line in body.allocations]
    if len(set(names))!=len(names):
        raise HTTPException(422,'Each template category must appear only once.')
    check_allocation(body.income,body.savings,body.emergency,sum((line.amount for line in body.allocations),Decimal('0.00')))
    write_plan(db,body,user.id)
    db.execute(delete(Budget).where(Budget.user_id==user.id,Budget.month==body.month))
    categories=db.scalars(select(Category).where(Category.user_id==user.id,Category.type=='expense').with_for_update()).all()
    for line in body.allocations:
        category=next((c for c in categories if c.name.casefold()==line.name.casefold()),None)
        if category is None:
            category=Category(user_id=user.id,name=line.name,type='expense',color='#087dbd',icon='◇')
            db.add(category)
            db.flush()
        db.add(Budget(user_id=user.id,month=body.month,category_id=category.id,amount=line.amount))
    db.commit()
    return {'saved':True}

class DebtInput(BaseModel):
    name: str = Field(min_length=1,max_length=100)
    balance: Decimal = Field(ge=0,max_digits=12,decimal_places=2)
    apr: Decimal = Field(ge=0,le=1000,max_digits=7,decimal_places=3)
    minimum_payment: Decimal = Field(ge=0,max_digits=12,decimal_places=2)
    due_date: date
    @field_validator('name')
    @classmethod
    def clean_name(cls, value):
        if not value.strip():
            raise ValueError('Enter the lender or debt name')
        return value.strip()

class DebtOutput(DebtInput):
    model_config = ConfigDict(from_attributes=True)
    id: int

class PaymentInput(BaseModel):
    transaction_id: int
    principal: Decimal = Field(gt=0,max_digits=12,decimal_places=2)

class PaymentOutput(PaymentInput):
    model_config = ConfigDict(from_attributes=True)
    id: int
    debt_id: int

def owned(db, model, row_id, user_id):
    row = db.scalar(select(model).where(model.id==row_id,model.user_id==user_id).with_for_update())
    if row is None:
        raise HTTPException(404,'Record not found')
    return row

@router.get('/planning')
def planning(db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    return {key:[schema.model_validate(row).model_dump(mode='json') for row in db.scalars(select(model).where(model.user_id==user.id)).all()] for key,model,schema in [('budgets',Budget,BudgetOutput),('debts',Debt,DebtOutput),('payments',DebtPayment,PaymentOutput),('plans',MonthlyPlan,PlanOutput)]}

@router.post('/budgets',response_model=BudgetOutput,status_code=201)
def save_budget(body: BudgetInput,db: Session=Depends(get_db),user: User=Depends(get_current_user)):
    db.scalar(select(User).where(User.id==user.id).with_for_update())
    plan=db.scalar(select(MonthlyPlan).where(MonthlyPlan.user_id==user.id,MonthlyPlan.month==body.month).with_for_update())
    if plan is None:
        raise HTTPException(422,'Set your planned monthly income before allocating budgets.')
    category=owned(db,Category,body.category_id,user.id)
    if category.type!='expense':
        raise HTTPException(422,'Choose an expense category')
    row=db.scalar(select(Budget).where(Budget.user_id==user.id,Budget.month==body.month,Budget.category_id==body.category_id).with_for_update())
    total=plan_total(db,user.id,body.month)-(row.amount if row else Decimal('0.00'))+body.amount
    check_allocation(plan.income,plan.savings,plan.emergency,total)
    if row:
        row.amount=body.amount
    else:
        row=Budget(**body.model_dump(),user_id=user.id)
        db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409,'Budget changed in another request. Refresh and retry.')
    db.refresh(row)
    return row

@router.delete('/budgets/{row_id}',status_code=204)
def delete_budget(row_id:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    db.delete(owned(db,Budget,row_id,user.id))
    db.commit()
    return Response(status_code=204)

@router.post('/debts',response_model=DebtOutput,status_code=201)
def add_debt(body:DebtInput,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=Debt(**body.model_dump(),user_id=user.id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row

@router.put('/debts/{row_id}',response_model=DebtOutput)
def edit_debt(row_id:int,body:DebtInput,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=owned(db,Debt,row_id,user.id)
    if body.balance!=row.balance and db.scalar(select(DebtPayment.id).where(DebtPayment.debt_id==row.id).limit(1)):
        raise HTTPException(409,'Unlink repayments before correcting the outstanding balance.')
    for key,value in body.model_dump().items():
        setattr(row,key,value)
    db.commit()
    db.refresh(row)
    return row

@router.delete('/debts/{row_id}',status_code=204)
def delete_debt(row_id:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=owned(db,Debt,row_id,user.id)
    if db.scalar(select(DebtPayment.id).where(DebtPayment.debt_id==row.id).limit(1)):
        raise HTTPException(409,'Unlink repayments before removing this debt. Your expense records will remain.')
    db.delete(row)
    db.commit()
    return Response(status_code=204)

@router.post('/debts/{row_id}/payments',response_model=PaymentOutput,status_code=201)
def record_payment(row_id:int,body:PaymentInput,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    debt=owned(db,Debt,row_id,user.id)
    transaction=owned(db,Transaction,body.transaction_id,user.id)
    if transaction.type!='expense' or transaction.transaction_date>datetime.now(timezone(timedelta(hours=1))).date():
        raise HTTPException(422,'Choose an existing expense already paid, not a future transaction')
    if body.principal>transaction.amount or body.principal>debt.balance:
        raise HTTPException(422,'Principal cannot exceed the payment amount or outstanding balance')
    row=DebtPayment(**body.model_dump(),debt_id=debt.id,user_id=user.id)
    debt.balance-=body.principal
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409,'This expense is already linked to a debt repayment')
    db.refresh(row)
    return row

@router.delete('/debt-payments/{row_id}',status_code=204)
def undo_payment(row_id:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    # Lock debts before payment rows, matching the recording lock order.
    payment=db.scalar(select(DebtPayment).where(DebtPayment.id==row_id,DebtPayment.user_id==user.id))
    if not payment:
        raise HTTPException(404,'Record not found')
    debt=owned(db,Debt,payment.debt_id,user.id)
    payment=owned(db,DebtPayment,row_id,user.id)
    debt.balance+=payment.principal
    db.delete(payment)
    db.commit()
    return Response(status_code=204)


