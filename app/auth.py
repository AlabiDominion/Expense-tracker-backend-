from collections import defaultdict, deque
from datetime import timedelta
from email.message import EmailMessage
import logging
import smtplib
import ssl
from threading import Lock
from time import monotonic
from secrets import token_urlsafe
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from pwdlib import PasswordHash
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .database import get_db
from .models import User, Category, Transaction, AuthSession, AccountToken
from .security import COOKIE, create_session, get_current_user, hash_token, now, public_user
from .config import settings
from .default_categories import create_user_categories

router=APIRouter(prefix='/auth',tags=['Accounts'])
passwords=PasswordHash.recommended()
DUMMY_HASH=passwords.hash(token_urlsafe(24))
_attempts=defaultdict(deque)
_lock=Lock()

def throttle(request,bucket,limit=12):
    key=(request.client.host if request.client else 'unknown',bucket)
    current=monotonic()
    with _lock:
        for old in list(_attempts):
            if not _attempts[old] or _attempts[old][-1]<current-600:
                del _attempts[old]
        attempts=_attempts[key]
        while attempts and attempts[0]<current-600: attempts.popleft()
        if len(attempts)>=limit: raise HTTPException(429,'Too many attempts. Please try again in a few minutes.')
        attempts.append(current)

class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1,max_length=128)
class Registration(Credentials):
    name: str = Field(min_length=2,max_length=100,pattern=r'.*\S.*')
class ResetRequest(BaseModel):
    email: EmailStr
class NewPassword(BaseModel):
    token: str = Field(min_length=20,max_length=200)
    password: str = Field(min_length=10,max_length=128)
class ConfirmPassword(BaseModel):
    password: str = Field(min_length=1,max_length=128)

def email_available():
    return bool(settings.smtp_host and settings.smtp_from and settings.smtp_username and settings.smtp_password)

@router.get('/options')
def options():
    return {'password_reset':email_available()}

@router.get('/me')
def me(user: User = Depends(get_current_user)):
    return public_user(user)

@router.post('/register',status_code=201)
def register(body: Registration,request: Request,response: Response,db: Session=Depends(get_db)):
    throttle(request,'register',8)
    if len(body.password)<10: raise HTTPException(422,'Use a password of at least 10 characters.')
    email=str(body.email).lower().strip()
    user=User(name=body.name.strip(),email=email,password_hash=passwords.hash(body.password))
    db.add(user)
    try:
        db.flush()
        create_user_categories(db,user.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409,'An account already uses this email. Sign in or reset your password.')
    create_session(db,user,response)
    return public_user(user)

@router.post('/login')
def login(body: Credentials,request: Request,response: Response,db: Session=Depends(get_db)):
    throttle(request,'login')
    user=db.scalar(select(User).where(User.email==str(body.email).lower().strip()))
    valid=passwords.verify(body.password,user.password_hash if user and user.password_hash else DUMMY_HASH)
    if not user or not user.password_hash or not valid:
        raise HTTPException(401,'Email or password is incorrect.')
    create_session(db,user,response)
    return public_user(user)

@router.post('/logout',status_code=204)
def logout(request: Request,response: Response,db: Session=Depends(get_db)):
    token=request.cookies.get(COOKIE)
    if token:
        db.execute(delete(AuthSession).where(AuthSession.token_hash==hash_token(token)))
        db.commit()
    response.delete_cookie(COOKIE,path='/',secure=settings.cookie_secure,httponly=True,samesite='lax')
    response.status_code=204
    return response

@router.post('/forgot-password')
def forgot(body: ResetRequest,request: Request,db: Session=Depends(get_db)):
    throttle(request,'reset',5)
    if not email_available():
        raise HTTPException(503,'Password reset is temporarily unavailable. Please contact support@cloudberth.com.')
    user=db.scalar(select(User).where(User.email==str(body.email).lower().strip()))
    if user:
        token=token_urlsafe(48)
        db.execute(delete(AccountToken).where(AccountToken.user_id==user.id))
        db.add(AccountToken(token_hash=hash_token(token),user_id=user.id,expires_at=now()+timedelta(minutes=30)))
        db.commit()
        message=EmailMessage()
        message['Subject']='Reset your CloudBerth password'
        message['From']=settings.smtp_from
        message['To']=user.email
        message.set_content(f'Hello {user.name},\n\nReset your password using this link (valid for 30 minutes):\n{settings.frontend_url.rstrip("/")}/reset-password?token={token}\n\nIf you did not request this, you can ignore this email.\n\nCloudBerth Technologies')
        try:
            cls=smtplib.SMTP_SSL if settings.smtp_ssl else smtplib.SMTP
            kwargs={'context':ssl.create_default_context()} if settings.smtp_ssl else {}
            with cls(settings.smtp_host,settings.smtp_port,timeout=15,**kwargs) as smtp:
                if not settings.smtp_ssl: smtp.starttls(context=ssl.create_default_context())
                smtp.login(settings.smtp_username,settings.smtp_password)
                smtp.send_message(message)
        except Exception:
            logging.getLogger(__name__).warning('Password-reset email delivery failed; check SMTP configuration.')
    return {'message':'If an account exists for this email, a reset link will be sent.'}

@router.post('/reset-password')
def reset(body: NewPassword,request: Request,db: Session=Depends(get_db)):
    throttle(request,'new-password')
    token=db.get(AccountToken,hash_token(body.token))
    if not token or token.expires_at<=now(): raise HTTPException(400,'This link is invalid or expired. Request a new reset link.')
    user=db.get(User,token.user_id)
    if not user: raise HTTPException(400,'This link is invalid or expired.')
    user.password_hash=passwords.hash(body.password)
    db.execute(delete(AccountToken).where(AccountToken.user_id==user.id))
    db.execute(delete(AuthSession).where(AuthSession.user_id==user.id))
    db.commit()
    return {'message':'Password saved. You can now sign in.'}

@router.delete('/account',status_code=204)
def delete_account(body: ConfirmPassword,response: Response,user: User=Depends(get_current_user),db: Session=Depends(get_db)):
    if not user.password_hash or not passwords.verify(body.password,user.password_hash):
        raise HTTPException(401,'Your password is incorrect.')
    for model in [Transaction,Category,AuthSession,AccountToken]:
        db.execute(delete(model).where(model.user_id==user.id))
    db.delete(user)
    db.commit()
    response.delete_cookie(COOKIE,path='/')
    response.status_code=204
    return response

@router.get('/export')
def export_account(user: User=Depends(get_current_user),db: Session=Depends(get_db)):
    from .schemas import CategoryOutput, TransactionOutput
    return {'profile':public_user(user),'categories':[CategoryOutput.model_validate(row).model_dump(mode='json') for row in db.scalars(select(Category).where(Category.user_id==user.id)).all()],'transactions':[TransactionOutput.model_validate(row).model_dump(mode='json') for row in db.scalars(select(Transaction).where(Transaction.user_id==user.id)).all()]}

class ProfileUpdate(BaseModel):
    name: str = Field(min_length=2,max_length=100,pattern=r'.*\S.*')

@router.patch('/profile')
def update_profile(body: ProfileUpdate,user: User=Depends(get_current_user),db: Session=Depends(get_db)):
    user.name=body.name.strip()
    db.commit()
    return public_user(user)
