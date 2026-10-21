"""Default categories are copied separately into every new account."""
from .models import Category

DEFAULTS=[('Salary','income','#188c68','↗'),('Freelance','income','#4785d6','⌘'),('Food & dining','expense','#e9a24b','♨'),('Shopping','expense','#9b83cf','◇'),('Transport','expense','#5c9fba','↔'),('Bills & utilities','expense','#dc7d7e','⌂'),('Entertainment','expense','#86a878','♫')]

def create_user_categories(db,user_id):
    db.add_all([Category(user_id=user_id,name=name,type=kind,color=color,icon=icon) for name,kind,color,icon in DEFAULTS])
