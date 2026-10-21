from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db
from .models import Category
from .auth import router as auth_router
from .workspace import router as workspace_router
from .statements import router as statement_router
from .planning import router as planning_router

app=FastAPI(title='CloudBerth Expense Tracker',version='2.0.0',description='Free personal finance workspaces by CloudBerth Technologies.')
app.add_middleware(CORSMiddleware,allow_origins=settings.cors_origins,allow_credentials=True,allow_methods=['GET','POST','PUT','PATCH','DELETE'],allow_headers=['Content-Type','X-Requested-With'])

@app.middleware('http')
async def protect_requests(request: Request, call_next):
    if request.method not in ('GET','HEAD','OPTIONS'):
        origin=request.headers.get('origin')
        if (origin and origin not in settings.cors_origins) or request.headers.get('x-requested-with')!='CloudBerth':
            return JSONResponse(status_code=403,content={'detail':'This request could not be verified. Refresh the page and try again.'})
    response=await call_next(request)
    response.headers['Cache-Control']='no-store'
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='no-referrer'
    return response

@app.get('/health')
def health(db: Session = Depends(get_db)):
    try:
        db.execute(select(Category.id).limit(1))
    except SQLAlchemyError:
        raise HTTPException(503,'Database unavailable or migrations not applied')
    return {'status':'ok','database':db.get_bind().dialect.name}

app.include_router(auth_router)
app.include_router(workspace_router)
app.include_router(statement_router)
app.include_router(planning_router)

