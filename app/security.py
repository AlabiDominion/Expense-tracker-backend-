"""Opaque, server-side sessions: only a token hash is persisted."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from secrets import token_urlsafe
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db
from .models import AuthSession, User

COOKIE='cloudberth_session'

def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

def hash_token(token):
    return sha256(token.encode()).hexdigest()

def get_current_user(request: Request, db: Session = Depends(get_db)):
    token=request.cookies.get(COOKIE)
    session=db.get(AuthSession,hash_token(token)) if token else None
    if not session or session.expires_at <= now():
        raise HTTPException(401,'Please sign in to access your workspace.')
    user=db.get(User,session.user_id)
    if not user:
        raise HTTPException(401,'Please sign in again.')
    return user

def create_session(db,user,response):
    token=token_urlsafe(48)
    db.add(AuthSession(token_hash=hash_token(token),user_id=user.id,expires_at=now()+timedelta(days=settings.session_days)))
    db.commit()
    response.set_cookie(COOKIE,token,max_age=settings.session_days*86400,httponly=True,secure=settings.cookie_secure,samesite='lax',path='/')

def public_user(user):
    return {'id':user.id,'name':user.name,'email':user.email}
