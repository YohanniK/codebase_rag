from fastapi import FastAPI
from app.routes import repo, query

app = FastAPI()

app.include_router(repo.router, prefix='/repos', tags=['Repositories'])
app.include_router(query.router, prefix='/query', tags=['Query'])

@app.get('/')
async def root():
    return {"message": "Welcome to Codebase RAG APP"}
