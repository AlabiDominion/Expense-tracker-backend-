"""Local-only owner setup. Legacy records are never claimed by public signup."""
import argparse
from pathlib import Path
from secrets import token_urlsafe
from datetime import timedelta
from sqlalchemy import select, update, delete
from .database import SessionLocal
from .models import User, Category, Transaction, AccountToken
from .security import hash_token, now
from .config import settings

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--email',required=True)
    parser.add_argument('--name',required=True)
    parser.add_argument('--frontend-url',default=settings.frontend_url)
    args=parser.parse_args()
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.email==args.email.lower().strip()))
        if user is None:
            user=User(email=args.email.lower().strip(),name=args.name,password_hash=None)
            db.add(user)
            db.flush()
        # Match legacy categories to defaults if the owner already registered.
        for category in db.scalars(select(Category).where(Category.user_id.is_(None))).all():
            match=db.scalar(select(Category).where(Category.user_id==user.id,Category.name==category.name,Category.type==category.type))
            if match:
                db.execute(update(Transaction).where(Transaction.category_id==category.id,Transaction.user_id.is_(None)).values(category_id=match.id,user_id=user.id))
                db.delete(category)
            else:
                category.user_id=user.id
        db.execute(update(Transaction).where(Transaction.user_id.is_(None)).values(user_id=user.id))
        link=None
        if not user.password_hash:
            token=token_urlsafe(48)
            db.execute(delete(AccountToken).where(AccountToken.user_id==user.id))
            db.add(AccountToken(token_hash=hash_token(token),user_id=user.id,expires_at=now()+timedelta(hours=24)))
            link=args.frontend_url.rstrip('/')+'/reset-password?token='+token
        db.commit()
        if link:
            folder=Path(__file__).resolve().parents[1]/'.local'
            folder.mkdir(exist_ok=True)
            (folder/'owner-setup-url.txt').write_text(link,encoding='utf-8')
            print('Owner account reserved and records assigned. Private setup link saved in .local/owner-setup-url.txt (24 hours).')
        else:
            print('Existing records assigned to the owner account. Existing password unchanged.')
