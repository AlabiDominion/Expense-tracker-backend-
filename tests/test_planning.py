from test_api import client, payload
from test_auth import accounts, signup

DEBT=dict(name='Family loan',balance='1000.00',apr='0',minimum_payment='100.00',due_date='2026-11-01')

PLAN=dict(month='2026-10',income='400000.00',savings='0.00',emergency='0.00',annual_rent='1000000.00',household_size=2)

def test_budget_upsert_validation_and_category_protection(client):
    assert client.put('/monthly-plan',json=PLAN).status_code==200
    body=dict(month='2026-10',category_id=2,amount='25000.00')
    row=client.post('/budgets',json=body)
    assert row.status_code==201
    changed=client.post('/budgets',json={**body,'amount':'30000.00'})
    assert changed.json()['id']==row.json()['id']
    assert len(client.get('/planning').json()['budgets'])==1
    assert client.post('/budgets',json={**body,'category_id':1}).status_code==422
    assert client.post('/budgets',json={**body,'month':'2026-13'}).status_code==422
    assert client.post('/budgets',json={**body,'amount':'0'}).status_code==422
    assert client.delete('/categories/2').status_code==409
    assert client.delete('/budgets/'+str(row.json()['id'])).status_code==204


def test_repayments_link_existing_expense_without_double_counting(client):
    debt=client.post('/debts',json=DEBT).json()
    expense=client.post('/transactions',json=payload('110.00')).json()
    body=dict(transaction_id=expense['id'],principal='100.00')
    response=client.post(f"/debts/{debt['id']}/payments",json=body)
    assert response.status_code==201,response.text
    assert client.get('/planning').json()['debts'][0]['balance']=='900.00'
    assert len(client.get('/transactions').json())==1
    assert client.get('/reports/2026-02').json()['expenses']=='110.00'
    assert client.post(f"/debts/{debt['id']}/payments",json=body).status_code==409
    assert client.delete(f"/transactions/{expense['id']}").status_code==409
    assert client.put(f"/transactions/{expense['id']}",json=payload()).status_code==409
    assert client.delete(f"/debts/{debt['id']}").status_code==409
    assert client.put(f"/debts/{debt['id']}",json={**DEBT,'balance':'50.00'}).status_code==409
    assert client.delete('/debt-payments/'+str(response.json()['id'])).status_code==204
    assert client.get('/planning').json()['debts'][0]['balance']=='1000.00'
    assert len(client.get('/transactions').json())==1


def test_payment_principal_limits_and_debt_validation(client):
    debt=client.post('/debts',json=DEBT).json()
    expense=client.post('/transactions',json=payload('110.00')).json()
    assert client.post(f"/debts/{debt['id']}/payments",json=dict(transaction_id=expense['id'],principal='111.00')).status_code==422
    assert client.post('/debts',json={**DEBT,'apr':-1}).status_code==422
    assert client.post('/debts',json={**DEBT,'name':'  '}).status_code==422
    assert client.post('/debts',json={**DEBT,'balance':'1.001'}).status_code==422


def test_planning_is_private_exportable_and_account_deletion_works(accounts):
    first,second,_=accounts
    assert first.get('/planning').status_code==401
    signup(first);signup(second,'two@example.com')
    category=next(c for c in first.get('/categories').json() if c['type']=='expense')
    first.put('/monthly-plan',json=PLAN)
    budget=first.post('/budgets',json=dict(month='2026-10',category_id=category['id'],amount='100')).json()
    debt=first.post('/debts',json=DEBT).json()
    expense=first.post('/transactions',json={**payload('100.00'), 'category_id':category['id']}).json()
    payment=first.post(f"/debts/{debt['id']}/payments",json=dict(transaction_id=expense['id'],principal='100.00')).json()
    assert second.get('/planning').json()==dict(budgets=[],debts=[],payments=[],plans=[])
    assert second.delete(f"/budgets/{budget['id']}").status_code==404
    assert second.put(f"/debts/{debt['id']}",json=DEBT).status_code==404
    assert second.post(f"/debts/{debt['id']}/payments",json=dict(transaction_id=expense['id'],principal='1')).status_code==404
    assert second.delete(f"/debt-payments/{payment['id']}").status_code==404
    exported=first.get('/auth/export').json()
    assert len(exported['budgets'])==len(exported['debts'])==len(exported['payments'])==1
    assert first.request('DELETE','/auth/account',json={'password':'A-long-test-password-123'}).status_code==204


def test_income_ceiling_applies_to_creates_edits_reserves_and_income_changes(client):
    body=dict(month='2026-10',category_id=2,amount='100.00')
    assert client.post('/budgets',json=body).status_code==422
    assert client.put('/monthly-plan',json={**PLAN,'income':'100.00','savings':'10.00','emergency':'10.00'}).status_code==200
    assert client.post('/budgets',json=body).status_code==422
    assert client.post('/budgets',json={**body,'amount':'80.00'}).status_code==201
    assert client.post('/budgets',json={**body,'amount':'80.01'}).status_code==422
    assert client.put('/monthly-plan',json={**PLAN,'income':'79.99'}).status_code==422
    assert client.get('/planning').json()['plans'][0]['income']=='100.00'
    assert client.get('/planning').json()['budgets'][0]['amount']=='80.00'
    assert client.post('/budgets',json={**body,'amount':'70.00'}).status_code==201
    assert client.put('/monthly-plan',json={**PLAN,'month':'2026-11','income':'200.00'}).status_code==200


def test_template_replacement_is_atomic_and_keeps_transactions(client):
    template={**PLAN,'savings':'45000.00','emergency':'20000.00','allocations':[dict(name='Rent',amount='83333.33'),dict(name='Food',amount='105000.00')]}
    expense=client.post('/transactions',json=payload()).json()
    assert client.post('/budget-template',json=template).status_code==200
    assert len(client.get('/planning').json()['budgets'])==2
    assert client.post('/budget-template',json=template).status_code==200
    assert len(client.get('/planning').json()['budgets'])==2
    assert len([c for c in client.get('/categories').json() if c['name']=='Rent'])==1
    invalid={**template,'allocations':[dict(name='Rent',amount='400000.00')]}
    assert client.post('/budget-template',json=invalid).status_code==422
    assert len(client.get('/planning').json()['budgets'])==2
    assert client.get('/transactions').json()[0]['id']==expense['id']
    assert client.post('/budget-template',json={**template,'allocations':[dict(name='Rent',amount='1'),dict(name='rent',amount='1')]}).status_code==422
