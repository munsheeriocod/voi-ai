import os
from pinecone import Pinecone
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Initialize Pinecone
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index(os.getenv("PINECONE_INDEX"))

def embed_texts(texts):
    """Get OpenAI embeddings for a list of texts."""
    response = client.embeddings.create(
        input=texts,
        model="llama-text-embed-v2"
    )
    return [d.embedding for d in response.data]

def upsert_chunks(chunks, metadata):
    """Embed and upsert chunks into Pinecone."""
    embeddings = embed_texts(chunks)
    vectors = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        vector_id = f"{metadata['filename']}-{i}"
        vectors.append((vector_id, embedding, {"text": chunk, **metadata}))
    index.upsert(vectors=vectors)

def query_vector_store(query, top_k=3):
    """
    Query the vector store (e.g., Pinecone) for relevant context.
    """
    # Embed the query
    embedding = client.embeddings.create(
        input=query,
        model="text-embedding-3-large"
    )["data"][0]["embedding"]

    # Query Pinecone
    results = index.query(vector=embedding, top_k=top_k, include_metadata=True)

    # Return concatenated context
    context = " ".join([m['metadata']['text'] for m in results['matches']])
    return context