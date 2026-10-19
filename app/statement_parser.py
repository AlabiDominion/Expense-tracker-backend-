"""Moniepoint selectable-text statements: parse columns, never running balances."""
from io import BytesIO
from decimal import Decimal, InvalidOperation
from datetime import date
import re
from hashlib import sha256
import pdfplumber

class StatementError(ValueError):
    pass

AMOUNT = re.compile(r'^-?[\d,]+\.\d{2}$')
DATE = re.compile(r'^\d{4}-\d{2}-\d{2}T')

def parse_statement(content: bytes):
    if not content.startswith(b'%PDF-'):
        raise StatementError('Please upload a valid PDF file.')
    try:
        with pdfplumber.open(BytesIO(content)) as pdf:
            if len(pdf.pages) > 100:
                raise StatementError('Please use a statement of 100 pages or fewer.')
            first = pdf.pages[0].extract_text() or ''
            if not first.strip():
                raise StatementError('This PDF has no selectable text. Scanned statements are not supported yet.')
            if 'Moniepoint' not in first or not re.search(r'Currency\s+NGN', first):
                raise StatementError('This version supports NGN Moniepoint statements with selectable text.')
            names = ['Date', 'Narration', 'Reference', 'Debit', 'Credit', 'Balance']
            headers = {w['text']: w for w in pdf.pages[0].extract_words() if w['text'] in names}
            if any(key not in headers for key in names) or headers['Date']['top'] != headers['Debit']['top']:
                raise StatementError('The transaction columns could not be identified.')
            boundaries = [headers['Narration']['x0']-8, headers['Reference']['x0']-10, headers['Debit']['x0']-15, headers['Credit']['x0']-15, headers['Balance']['x0']-15]
            records, current = [], None
            for page_index, page in enumerate(pdf.pages):
                lines = []
                for word in sorted(page.extract_words(x_tolerance=1, y_tolerance=2), key=lambda w:(w['top'],w['x0'])):
                    if page_index == 0 and word['top'] < headers['Debit']['bottom']+5:
                        continue
                    if not lines or abs(word['top']-lines[-1][0]) > 2:
                        lines.append((word['top'], [word]))
                    else:
                        lines[-1][1].append(word)
                for _, line in lines:
                    columns = [[] for _ in range(6)]
                    for word in sorted(line, key=lambda w:w['x0']):
                        columns[sum(word['x0'] >= edge for edge in boundaries)].append(word['text'])
                    values = [' '.join(parts) for parts in columns]
                    if DATE.match(values[0]):
                        if current:
                            records.append(current)
                        current = {'date': values[0][:10], 'columns': [[] for _ in range(6)]}
                    if current:
                        for index, value in enumerate(values):
                            if value:
                                current['columns'][index].append(value)
            if current:
                records.append(current)
            rows, skipped = [], 0
            for record in records:
                cells = [' '.join(parts).strip() for parts in record['columns']]
                amounts = [[Decimal(v.replace(',', '')) for v in cells[i].split() if AMOUNT.fullmatch(v)] for i in (3,4)]
                if any(len(values)!=1 for values in amounts) or not cells[1] or not cells[2]:
                    skipped += 1
                    continue
                debit, credit = amounts[0][0], amounts[1][0]
                if (debit>0)==(credit>0) or debit<0 or credit<0:
                    skipped += 1
                    continue
                date.fromisoformat(record['date'])
                rows.append({'transaction_date':record['date'], 'description':cells[1][:200], 'reference':cells[2][:300], 'type':'expense' if debit>0 else 'income', 'amount':str(max(debit,credit))})
            if not rows:
                raise StatementError('No valid transaction rows were found in this statement.')
            def summary(label):
                match = re.search(label+r'\s+([\d,]+\.\d{2})', first)
                return Decimal(match.group(1).replace(',','')) if match else None
            debit_total = sum((Decimal(r['amount']) for r in rows if r['type']=='expense'), Decimal('0.00'))
            credit_total = sum((Decimal(r['amount']) for r in rows if r['type']=='income'), Decimal('0.00'))
            expected_debit, expected_credit = summary('Total Debits'), summary('Total Credits')
            reconciled = expected_debit == debit_total and expected_credit == credit_total
            warnings = []
            if skipped:
                warnings.append(f'{skipped} rows could not be safely extracted. Review against your original statement.')
            if not reconciled:
                warnings.append('Extracted totals do not match the statement summary. Review all rows before importing.')
            account = re.search(r'Account Number\s+(\d+)', first)
            if not account:
                raise StatementError('The statement account could not be identified.')
            scope = sha256(account.group(1).encode()).hexdigest()
            return {'scope':scope, 'bank':'Moniepoint', 'currency':'NGN', 'pages':len(pdf.pages), 'rows':rows, 'warnings':warnings, 'reconciled':reconciled, 'debit_total':str(debit_total), 'credit_total':str(credit_total), 'statement_debits':str(expected_debit) if expected_debit is not None else None, 'statement_credits':str(expected_credit) if expected_credit is not None else None}
    except StatementError:
        raise
    except Exception as exc:
        raise StatementError('This PDF could not be read. Use an unencrypted Moniepoint statement with selectable text.') from exc

