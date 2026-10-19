from datetime import date
from decimal import Decimal
from sqlalchemy import select
from .database import SessionLocal
from .models import Category, Transaction

def seed(categories_only=False):
    with SessionLocal() as db:
        if db.scalar(select(Category.id).limit(1)):
            print('Database already contains categories; seed skipped.')
            return
        specs=[('Salary','income','#188c68','↗'),('Freelance','income','#4785d6','⌘'),('Food & dining','expense','#e9a24b','♨'),('Shopping','expense','#9b83cf','◇'),('Transport','expense','#5c9fba','↔'),('Bills & utilities','expense','#dc7d7e','⌂'),('Entertainment','expense','#86a878','♫')]
        cats=[Category(name=n,type=t,color=c,icon=i) for n,t,c,i in specs]
        db.add_all(cats)
        db.flush()
        if categories_only:
            db.commit()
            print('Default categories created.')
            return
        today=date.today()
        for offset in range(6):
            ordinal=today.year*12+today.month-1-offset
            year, month0=divmod(ordinal,12)
            entries=[('Monthly salary',0,650000,1),('Website design project',1,125000+offset*7000,8),('Weekly groceries',2,32500+offset*1100,3),('Electricity bill',5,24000,5),('Ride to the office',4,8500,7),('New headphones',3,45000,10),('Lunch with the team',2,18200,12),('Internet subscription',5,25000,14),('Movie night',6,12000,16),('Market essentials',2,28500,18),('Fuel refill',4,30000,19)]
            for description, index, amount, day in entries:
                db.add(Transaction(description=description, category_id=cats[index].id, type=cats[index].type, amount=Decimal(amount), transaction_date=date(year,month0+1,day)))
        db.commit()
        print('Seeded seven categories and 66 transactions.')

if __name__ == '__main__':
    seed()

