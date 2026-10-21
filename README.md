# CloudBerth backend

See [the workspace guide](../README.md) for MySQL, migrations, seed data, tests and presentation steps.



## Free financial planning

- Budgets: category limits per month; matching expense transactions drive usage automatically.
- Debts: outstanding principal, explicit fixed APR (0 for interest-free), minimum monthly payment and next due date.
- Repayments link an existing expense transaction. Principal reduces the debt, the remaining expense amount is interest/fees, and no second expense is created. Unlink before editing or deleting a linked transaction. Update due dates manually after repayment.
- Planner: compare highest-interest-first and smallest-balance-first, with minimum payments, monthly compounding rounded to cents, final partial payments and a 600-month limit. Estimates assume first payment next month, fixed APR and no new borrowing/fees; they do not model flat-rate/daily-interest loans.
- All records are private to the signed-in account; JSON export and account deletion include planning data. Guest demo planning uses separate local browser storage.

Apply migration `004` with `python -m alembic upgrade head`, then restart the API. Deploy backend before frontend. Production has not been migrated by local development commands.

### Income-backed budgets
Set take-home income for each month before adding category limits. Total allocated includes expense limits, savings and emergency reserves; API validation prevents over-allocation, including when editing limits or reducing income. Recorded income is displayed separately and planning never creates transactions. Apply migration 005 locally before restarting the API.

Household essentials (annual rent / 12 and household-size-adjusted food weighting) and Flexible starter are editable illustrative templates. Preview shows the full allocation before replacement; applying atomically replaces only that month's budgets and reserves, reuses matching expense categories and creates missing ones. Existing transactions remain unchanged. Template suggestions are heuristics, not estimates of actual local living costs.
