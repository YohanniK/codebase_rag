import os
from dotenv import load_dotenv
from openai import OpenAI
from pinecone import Index, Pinecone
from langchain.schema import Document
from langchain_pinecone import PineconeVectorStore
from langchain_community.embeddings import HuggingFaceEmbeddings
from sentence_transformers import SentenceTransformer

load_dotenv()

PINECONE_AIP_KEY = os.getenv("PINECONE_AIP_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

pc = Pinecone(api_key=PINECONE_AIP_KEY)

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=GROQ_API_KEY
)


def get_huggingface_embeddings(text, model_name="sentence-transformers/all-mpnet-base-v2"):
    model = SentenceTransformer(model_name)
    return model.encode(text)

def create_pinecone_index(codebase_path: str):
    pinecone_index = pc.Index(codebase_path)
    return pinecone_index

def store_embeddings(repo_url: str, codebase_path: str, references: dict, class_data: list, method_data: list):
    documents = []
    for row in class_data:
        references = row.get("references", [])
        references_str = "; ".join([f"{ref['file']}:{ref['line']}:{ref['column']}" for ref in references])
        metadata = {
            "file_path": row["file_path"],
            "class_name": row["class_name"],
            "constructor_declaration": row["constructor_declaration"],
            "method_declarations": row["method_declarations"],
            "references": references_str,
        }
        content = f"{row['class_name']}\n{row['source_code']}"
        doc = Document(
            page_content=content,
            metadata=metadata
        )
        documents.append(doc)

    # Create a Pinecone VectorStore and add documents
    vectorstore = PineconeVectorStore.from_documents(
        documents=documents,
        embedding=HuggingFaceEmbeddings(),
        index_name=codebase_path,
        namespace=repo_url
    )

    return vectorstore

def perform_rag(query: str, repo_url: str, pinecone_index: Index):
    raw_query_embedding = get_huggingface_embeddings(query)
    # Feel free to change the "top_k" parameter to be a higher or lower number
    top_matches = pinecone_index.query(vector=raw_query_embedding.tolist(), top_k=5, include_metadata=True, namespace=repo_url)
    contexts = [item['metadata']['text'] for item in top_matches['matches']]

    augmented_query = "<CONTEXT>\n" + "\n\n-------\n\n".join(contexts[ : 10]) + "\n-------\n</CONTEXT>\n\n\n\nMY QUESTION:\n" + query

    # Modify the prompt below as need to improve the response quality
    system_prompt = """You are a Senior Software Engineer, specializing in TypeScript.

    Answer any questions I have about the codebase, based on the code provided. Always consider all of the context provided when forming a response.
    """

    llm_response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": augmented_query}
        ]
    )

    return llm_response.choices[0].message.content
