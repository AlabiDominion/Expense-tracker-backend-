import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.main import app
from app.database import Base,get_db
from app.models import User,Transaction,AccountToken,AuthSession
from app.security import hash_token,now
from app import auth
from datetime import timedelta

@pytest.fixture()
def accounts():
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    def override():
        with Session(engine) as db: yield db
    app.dependency_overrides[get_db]=override
    auth._attempts.clear()
    first=TestClient(app,headers={'X-Requested-With':'CloudBerth'})
    second=TestClient(app,headers={'X-Requested-With':'CloudBerth'})
    yield first,second,engine
    first.close();second.close();app.dependency_overrides.clear();engine.dispose();auth._attempts.clear()

def signup(client,email='one@example.com'):
    response=client.post('/auth/register',json={'name':'Example User','email':email,'password':'A-long-test-password-123'})
    assert response.status_code==201,response.text
    return response.json()

def test_unauthenticated_api_and_csrf(accounts):
    first,_,_=accounts
    assert first.get('/transactions').status_code==401
    assert first.get('/categories').status_code==401
    assert first.get('/reports/2026-10').status_code==401
    assert first.post('/statements/preview',files={'file':('test.pdf',b'%PDF-test')}).status_code==401
    with TestClient(app) as browser:
        assert browser.post('/auth/login',json={'email':'one@example.com','password':'password'}).status_code==403
    assert first.post('/auth/login',json={'email':'one@example.com','password':'password'},headers={'Origin':'https://untrusted.example'}).status_code==403

def test_register_session_logout_password_hash(accounts):
    first,_,engine=accounts
    user=signup(first)
    assert first.get('/auth/me').json()['email']=='one@example.com'
    assert first.get('/transactions').json()==[]
    assert len(first.get('/categories').json())==7
    assert 'HttpOnly' in first.cookies.__repr__() or first.cookies.get('cloudberth_session')
    with Session(engine) as db:
        saved=db.get(User,user['id'])
        assert saved.password_hash.startswith('$argon2')
        assert db.scalar(select(AuthSession)).token_hash != first.cookies.get('cloudberth_session')
    assert first.post('/auth/logout').status_code==204
    assert first.get('/auth/me').status_code==401
    assert first.post('/auth/login',json={'email':'one@example.com','password':'incorrect'}).status_code==401
    assert first.post('/auth/login',json={'email':'one@example.com','password':'A-long-test-password-123'}).status_code==200

def test_private_transactions_categories_reports_and_imports(accounts):
    first,second,_=accounts
    signup(first);signup(second,'two@example.com')
    a=next(c for c in first.get('/categories').json() if c['type']=='expense')
    b=next(c for c in second.get('/categories').json() if c['type']=='expense')
    transaction={'description':'Private spending','type':'expense','amount':'9.99','category_id':a['id'],'transaction_date':'2026-10-01'}
    row=first.post('/transactions',json=transaction).json()
    assert second.get('/transactions').json()==[]
    assert second.get('/reports/2026-10').json()['expenses']=='0.00'
    assert second.put(f"/transactions/{row['id']}",json={**transaction,'category_id':b['id']}).status_code==404
    assert second.delete(f"/transactions/{row['id']}").status_code==404
    assert second.delete(f"/categories/{a['id']}").status_code==404
    assert second.post('/transactions',json=transaction).status_code==422
    assert first.delete(f"/categories/{a['id']}?replacement_id={b['id']}").status_code==422
    imported={'description':'From statement','amount':'5.00','type':'expense','transaction_date':'2026-10-01','reference':'BANK_REFERENCE'}
    batch={'scope':'a'*64,'rows':[imported]}
    assert first.post('/statements/import',json=batch).json()['imported']==1
    assert second.post('/statements/import',json=batch).json()['imported']==1
    assert first.post('/statements/import',json=batch).json()['skipped']==1
    assert len(second.get('/transactions').json())==1
    assert first.get('/auth/export').json()['profile']['email']=='one@example.com'
    assert len(first.get('/auth/export').json()['transactions'])==2

def test_reset_is_single_use_and_revokes_sessions(accounts):
    first,_,engine=accounts
    user=signup(first)
    token='a-private-single-use-test-token'
    with Session(engine) as db:
        db.add(AccountToken(token_hash=hash_token(token),user_id=user['id'],expires_at=now()+timedelta(minutes=30)));db.commit()
    response=first.post('/auth/reset-password',json={'token':token,'password':'My-new-long-password-123'})
    assert response.status_code==200
    assert first.get('/auth/me').status_code==401
    assert first.post('/auth/reset-password',json={'token':token,'password':'My-new-long-password-123'}).status_code==400
    assert first.post('/auth/login',json={'email':'one@example.com','password':'My-new-long-password-123'}).status_code==200

def test_delete_account_only_removes_current_users_data(accounts):
    first,second,_=accounts
    signup(first);signup(second,'two@example.com')
    assert first.request('DELETE','/auth/account',json={'password':'wrong'}).status_code==401
    assert first.request('DELETE','/auth/account',json={'password':'A-long-test-password-123'}).status_code==204
    assert first.get('/auth/me').status_code==401
    assert second.get('/auth/me').status_code==200
    assert len(second.get('/categories').json())==7


def test_expired_session_is_rejected(accounts):
    first,_,engine=accounts
    user=signup(first)
    with Session(engine) as db:
        session=db.scalar(select(AuthSession).where(AuthSession.user_id==user['id']))
        session.expires_at=now()-timedelta(seconds=1)
        db.commit()
    assert first.get('/auth/me').status_code==401

def test_reset_email_uses_configured_sender_and_does_not_enumerate(accounts,monkeypatch):
    first,_,engine=accounts
    signup(first)
    messages=[]
    class FakeSMTP:
        def __init__(self,*args,**kwargs): pass
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def starttls(self,**kwargs): pass
        def login(self,*args): pass
        def send_message(self,message): messages.append(message)
    monkeypatch.setattr(auth.settings,'smtp_host','smtp.test.invalid')
    monkeypatch.setattr(auth.settings,'smtp_from','CloudBerth <test@cloudberth.com>')
    monkeypatch.setattr(auth.settings,'smtp_username','test@cloudberth.com')
    monkeypatch.setattr(auth.settings,'smtp_password','test-only')
    monkeypatch.setattr(auth.smtplib,'SMTP',FakeSMTP)
    exists=first.post('/auth/forgot-password',json={'email':'one@example.com'})
    missing=first.post('/auth/forgot-password',json={'email':'absent@example.com'})
    assert exists.status_code==200 and exists.json()==missing.json()
    assert len(messages)==1
    assert '/reset-password?token=' in messages[0].get_content()
    with Session(engine) as db:
        assert db.scalar(select(AccountToken)) is not None
