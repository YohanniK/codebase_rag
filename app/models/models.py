from pydantic import BaseModel

class RepoInput(BaseModel):
    github_url: str

class QueryInput(BaseModel):
    query: str
    repo_id: str
