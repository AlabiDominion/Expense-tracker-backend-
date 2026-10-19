import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.database import Base, get_db
from app.main import app
from app.models import Category

@pytest.fixture()
def client():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([Category(id=1,name='Salary',type='income',color='#188c68',icon='+'),Category(id=2,name='Food',type='expense',color='#e9a24b',icon='-')])
        db.commit()
    def override():
        with Session(engine) as db:
            yield db
    app.dependency_overrides[get_db] = override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()

def payload(amount='10.10', day='2026-02-28', category=2, kind='expense'):
    return dict(description='Test entry',amount=amount,transaction_date=day,category_id=category,type=kind)

def test_month_boundaries_and_decimal_totals(client):
    for body in [payload('0.10'),payload('0.20'),payload('99.00','2026-03-01'),payload('10.00',category=1,kind='income')]:
        assert client.post('/transactions',json=body).status_code == 201
    report=client.get('/reports/2026-02').json()
    assert report['expenses']=='0.30'
    assert report['income']=='10.00'
    assert report['net_cash_flow']=='9.70'
    assert report['transaction_count']==3

def test_category_type_and_amount_validation(client):
    assert client.post('/transactions',json=payload(category=1)).status_code==422
    assert client.post('/transactions',json=payload('0')).status_code==422
    assert client.post('/transactions',json=payload('1.001')).status_code==422
    assert client.post('/transactions',json=payload(day='2026-02-30')).status_code==422

def test_update_delete_changes_report(client):
    row=client.post('/transactions',json=payload()).json()
    assert client.put(f"/transactions/{row['id']}",json=payload('25.55')).status_code==200
    assert client.get('/reports/2026-02').json()['expenses']=='25.55'
    assert client.delete(f"/transactions/{row['id']}").status_code==204
    assert client.get('/reports/2026-02').json()['expenses']=='0.00'
    assert client.delete(f"/transactions/{row['id']}").status_code==404

def test_duplicate_categories(client):
    body=dict(name='Travel',type='expense')
    assert client.post('/categories',json=body).status_code==201
    assert client.post('/categories',json=body).status_code==409


def test_health_checks_database(client):
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json()['status'] == 'ok'
    assert response.json()['database'] == 'sqlite'

def test_statement_import_is_idempotent_and_keeps_source(client):
    body={'scope':'a'*64,'rows':[dict(description='Imported lunch',amount='15.25',type='expense',transaction_date='2026-02-02',category_id=2,reference='TEST_DEBIT_0')]}
    first=client.post('/statements/import',json=body)
    assert first.status_code==200
    assert first.json()['imported']==1
    second=client.post('/statements/import',json=body)
    assert second.json()['imported']==0
    assert second.json()['skipped']==1
    saved=client.get('/transactions').json()
    assert len(saved)==1
    assert saved[0]['source']=='moniepoint_pdf'
    assert saved[0]['amount']=='15.25'

def test_import_creates_uncategorized_and_rejects_wrong_category(client):
    row=dict(description='Unknown merchant',amount='10.10',type='expense',transaction_date='2026-02-02',reference='OTHER_DEBIT_0')
    assert client.post('/statements/import',json={'scope':'b'*64,'rows':[row]}).json()['imported']==1
    categories=client.get('/categories').json()
    assert any(c['name']=='Uncategorized' and c['type']=='expense' for c in categories)
    row['reference']='OTHER_DEBIT_1'
    row['category_id']=1
    assert client.post('/statements/import',json={'scope':'b'*64,'rows':[row]}).status_code==422
    assert len(client.get('/transactions').json())==1

def test_preview_never_writes_and_flags_duplicates(client,monkeypatch):
    row=dict(description='Coffee',amount='0.25',type='expense',transaction_date='2026-02-02',reference='REF_DEBIT_0')
    monkeypatch.setattr('app.statements.parse_statement',lambda _:dict(scope='c'*64,bank='Moniepoint',currency='NGN',pages=1,rows=[row.copy()],warnings=[],reconciled=True))
    first=client.post('/statements/preview',files={'file':('statement.pdf',b'%PDF-test','application/pdf')})
    assert first.status_code==200
    assert not first.json()['rows'][0]['duplicate']
    assert client.get('/transactions').json()==[]
    client.post('/statements/import',json={'scope':'c'*64,'rows':[row]})
    second=client.post('/statements/preview',files={'file':('statement.pdf',b'%PDF-test','application/pdf')})
    assert second.json()['rows'][0]['duplicate']

def test_preview_rejects_invalid_pdf(client):
    result=client.post('/statements/preview',files={'file':('bad.pdf',b'not a PDF','application/pdf')})
    assert result.status_code==422

def test_delete_unused_category(client):
    row=client.post('/categories',json={'name':'Temporary','type':'expense'}).json()
    assert client.delete(f"/categories/{row['id']}").status_code==204
    assert client.delete(f"/categories/{row['id']}").status_code==404

def test_used_category_requires_same_type_replacement(client):
    transaction=client.post('/transactions',json=payload()).json()
    assert client.delete('/categories/2').status_code==409
    assert client.delete('/categories/2?replacement_id=1').status_code==422
    assert client.delete('/categories/2?replacement_id=2').status_code==422
    replacement=client.post('/categories',json={'name':'Other spending','type':'expense'}).json()
    assert client.delete(f"/categories/2?replacement_id={replacement['id']}").status_code==204
    saved=client.get('/transactions').json()
    assert saved[0]['id']==transaction['id']
    assert saved[0]['category_id']==replacement['id']
    assert saved[0]['amount']==transaction['amount']
