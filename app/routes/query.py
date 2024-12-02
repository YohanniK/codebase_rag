from fastapi import APIRouter, HTTPException
from app.models.models import QueryInput


router = APIRouter()

@router.get('/')
async def query_repo(input: QueryInput):
    return {'message': ''}
