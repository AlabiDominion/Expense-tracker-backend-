$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
& .\.venv\Scripts\python.exe -m app.setup_db
if ($LASTEXITCODE -ne 0) { throw 'Database setup failed. Check DATABASE_URL in .env.' }
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
