import pytest
from app.statement_parser import parse_statement, StatementError

class FakePage:
    def __init__(self, words, text=''):
        self.words, self.text = words, text
    def extract_text(self):
        return self.text
    def extract_words(self, **kwargs):
        return self.words

class FakePdf:
    def __init__(self,pages): self.pages=pages
    def __enter__(self): return self
    def __exit__(self,*args): pass

def word(text,x,y):
    return dict(text=text,x0=x,top=y,bottom=y+6)

def statement(monkeypatch, *, expected='13.09'):
    headers=[word(name,x,100) for name,x in zip(['Date','Narration','Reference','Debit','Credit','Balance'],[46,114,463,747,793,835])]
    row1=[word('2026-10-01T09:',46,130),word('Test income',114,130),word('REF_CREDIT_0',463,130),word('0.00',747,130),word('100.00',793,130),word('99999.99',835,130)]
    # The second transaction begins on page one and continues on page two.
    first=FakePage(headers+row1+[word('2026-10-02T10:',46,800)],f'Moniepoint Account Statement\nCurrency NGN\nAccount Number 0000000000\nTotal Debits {expected}\nTotal Credits 100.00')
    second=FakePage([word('30:00',46,10),word('TEST SHOP',114,10),word('REF_DEBIT_0',463,10),word('12.34',747,10),word('0.00',793,10),word('98765.43',835,10),word('2026-10-02T10:',46,80),word('Value Added Tax',114,80),word('REF_DEBIT_1',463,80),word('0.75',747,80),word('0.00',793,80),word('98764.68',835,80)])
    monkeypatch.setattr('app.statement_parser.pdfplumber.open',lambda _:FakePdf([first,second]))

def test_columns_cross_page_and_balances_are_not_transactions(monkeypatch):
    statement(monkeypatch)
    result=parse_statement(b'%PDF-test')
    assert len(result['rows'])==3
    assert result['debit_total']=='13.09'
    assert result['credit_total']=='100.00'
    assert result['rows'][1]['description']=='TEST SHOP'
    assert result['rows'][1]['amount']=='12.34'
    assert result['reconciled'] is True
    assert result['warnings']==[]
    assert len(result['scope'])==64

def test_summary_mismatch_warns(monkeypatch):
    statement(monkeypatch,expected='99.00')
    result=parse_statement(b'%PDF-test')
    assert not result['reconciled']
    assert result['warnings']

def test_rejects_invalid_file():
    with pytest.raises(StatementError,match='valid PDF'):
        parse_statement(b'not a PDF')

def test_rejects_scanned_pdf(monkeypatch):
    monkeypatch.setattr('app.statement_parser.pdfplumber.open',lambda _:FakePdf([FakePage([])]))
    with pytest.raises(StatementError,match='selectable text'):
        parse_statement(b'%PDF-test')
