from datetime import date
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class CategoryInput(BaseModel):
    name: str = Field(min_length=1, max_length=60, pattern=r'.*\S.*')
    type: Literal['income', 'expense']
    color: str = Field(default='#788fa0', pattern=r'^#[0-9a-fA-F]{6}$')
    icon: str = Field(default='◇', max_length=8)

class CategoryOutput(CategoryInput):
    id: int
    model_config = ConfigDict(from_attributes=True)

class TransactionInput(BaseModel):
    description: str = Field(min_length=1, max_length=200, pattern=r'.*\S.*')
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    type: Literal['income', 'expense']
    category_id: int
    transaction_date: date

class TransactionOutput(TransactionInput):
    source: str = 'manual'
    id: int
    model_config = ConfigDict(from_attributes=True)

