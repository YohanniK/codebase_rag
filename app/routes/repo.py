from fastapi import APIRouter, HTTPException
from app.models.models import RepoInput
from app.services.repo_service import process_repository
from app.services.pinecone_service import create_pinecone_index, store_embeddings
router = APIRouter()

@router.post('/upload/')
async def upload_repo(input: RepoInput):
    try:
        repo_url, codebase_path, references, class_data, method_data = process_repository(input.github_url)
        create_pinecone_index(codebase_path)
        store_embeddings(repo_url, codebase_path, references, class_data, method_data)
        return {'message': 'Repository processed and indexed successfully'}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
