import logging
from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List, Dict
from app.database import get_db

# Configure logging
logger = logging.getLogger(__name__)

class SemanticSearch:
    def __init__(self):
        # Initialize the sentence transformer model
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.db = get_db()
        self.collection = self.db.pdf_knowledge_base
        
    def create_embedding(self, text: str) -> List[float]:
        """Create embedding for a text"""
        try:
            embedding = self.model.encode(text)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Error creating embedding: {str(e)}")
            raise
            
    def store_embedding(self, chunk_id: str, embedding: List[float]):
        """Store embedding in MongoDB"""
        try:
            self.collection.update_one(
                {'_id': chunk_id},
                {'$set': {'embedding': embedding}}
            )
        except Exception as e:
            logger.error(f"Error storing embedding: {str(e)}")
            raise
            
    def find_similar_chunks(self, query: str, limit: int = 3) -> List[Dict]:
        """Find similar chunks using cosine similarity"""
        try:
            # Create embedding for the query
            query_embedding = self.model.encode(query)
            
            # Get all chunks with embeddings
            chunks = list(self.collection.find({'embedding': {'$exists': True}}))
            
            if not chunks:
                return []
                
            # Calculate cosine similarity
            similarities = []
            for chunk in chunks:
                chunk_embedding = np.array(chunk['embedding'])
                similarity = np.dot(query_embedding, chunk_embedding) / (
                    np.linalg.norm(query_embedding) * np.linalg.norm(chunk_embedding)
                )
                similarities.append((chunk, similarity))
                
            # Sort by similarity and get top results
            similarities.sort(key=lambda x: x[1], reverse=True)
            top_chunks = [chunk for chunk, _ in similarities[:limit]]
            
            return top_chunks
            
        except Exception as e:
            logger.error(f"Error finding similar chunks: {str(e)}")
            raise
            
    def process_and_store_chunks(self, chunks: List[str], metadata: Dict) -> List[str]:
        """Process chunks and store with embeddings"""
        try:
            chunk_ids = []
            for chunk in chunks:
                # Create embedding
                embedding = self.create_embedding(chunk)
                
                # Store in database
                result = self.collection.insert_one({
                    'chunk_text': chunk,
                    'embedding': embedding,
                    'metadata': metadata
                })
                
                chunk_ids.append(str(result.inserted_id))
                
            return chunk_ids
            
        except Exception as e:
            logger.error(f"Error processing and storing chunks: {str(e)}")
            raise 