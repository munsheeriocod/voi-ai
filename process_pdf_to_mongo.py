import os
import logging
from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer
import numpy as np
from datetime import datetime
from pymongo import MongoClient
from pymongo.collection import Collection
from dotenv import load_dotenv
import gc
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class PDFProcessor:
    def __init__(self):
        # Initialize MongoDB connection
        self.client = MongoClient(os.getenv('MONGODB_URI', 'mongodb://localhost:27017'))
        self.db = self.client[os.getenv('MONGODB_DB_NAME', 'voi_ai')]
        self.collection = self.db.pdf_knowledge_base
        
        # Initialize sentence transformer
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Chunk settings
        self.chunk_size = 4000  # Further increased chunk size for larger text segments
        self.chunk_overlap = 800  # Increased overlap to maintain better context
        self.batch_size = 1  # Process 1 chunk at a time
        
        # Create vector search index if it doesn't exist
        self._create_vector_index()

    def _create_vector_index(self):
        """Create a vector search index for embeddings"""
        try:
            # Check if index exists
            indexes = self.collection.list_indexes()
            index_exists = any(index.get('name') == 'vector_search' for index in indexes)
            
            if not index_exists:
                # Create vector search index
                self.collection.create_index(
                    [("embedding", "vector")],
                    name="vector_search",
                    vectorOptions={
                        "dimensions": 384,  # all-MiniLM-L6-v2 dimension
                        "similarity": "cosine"
                    }
                )
                logger.info("Created vector search index")
        except Exception as e:
            logger.error(f"Error creating vector index: {str(e)}")
            raise

    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)
        return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

    def semantic_search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Perform semantic search using cosine similarity"""
        try:
            # Create query embedding
            query_embedding = self.model.encode(query).tolist()
            
            # Get all chunks with their embeddings
            chunks = list(self.collection.find({}, {'chunk_text': 1, 'embedding': 1, 'metadata': 1}))
            
            # Calculate similarity scores
            results = []
            for chunk in chunks:
                similarity = self.cosine_similarity(query_embedding, chunk['embedding'])
                results.append({
                    'chunk_text': chunk['chunk_text'],
                    'metadata': chunk['metadata'],
                    'score': float(similarity)
                })
            
            # Sort by similarity score and return top results
            results.sort(key=lambda x: x['score'], reverse=True)
            return results[:limit]
            
        except Exception as e:
            logger.error(f"Error performing semantic search: {str(e)}")
            raise

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text from PDF file"""
        try:
            logger.info(f"Extracting text from PDF: {pdf_path}")
            reader = PdfReader(pdf_path)
            text = ""
            for page_num, page in enumerate(reader.pages):
                text += page.extract_text() + "\n"
                logger.info(f"Extracted text from page {page_num + 1}")
            return text
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {str(e)}")
            raise

    def create_chunks(self, text: str):
        """Split text into overlapping chunks and yield them one by one"""
        start = 0
        text_length = len(text)

        while start < text_length:
            end = start + self.chunk_size
            if end > text_length:
                end = text_length
            
            chunk = text[start:end]
            yield chunk
            
            # Move start position, accounting for overlap
            start = end - self.chunk_overlap

    def create_embedding(self, text: str) -> list:
        """Create embedding for text using sentence transformer"""
        try:
            embedding = self.model.encode(text)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Error creating embedding: {str(e)}")
            raise

    def store_chunks(self, chunks, metadata: dict) -> list:
        """Store chunks with embeddings in MongoDB"""
        try:
            chunk_ids = []
            total_chunks = 0
            processed_texts = set()  # Keep track of processed texts
            
            for chunk in chunks:
                # Skip if this exact text has been processed before
                if chunk in processed_texts:
                    logger.warning(f"Skipping duplicate chunk: {chunk[:100]}...")
                    continue
                    
                total_chunks += 1
                logger.info(f"Processing chunk {total_chunks}")
                
                # Create embedding
                embedding = self.create_embedding(chunk)
                
                # Prepare document
                document = {
                    'chunk_text': chunk,
                    'chunk_index': total_chunks - 1,
                    'embedding': embedding,
                    'metadata': metadata,
                    'created_at': datetime.utcnow()
                }
                
                # Insert into MongoDB
                result = self.collection.insert_one(document)
                chunk_ids.append(str(result.inserted_id))
                
                # Add to processed texts
                processed_texts.add(chunk)
                
                # Clear memory after each chunk
                del embedding
                gc.collect()
                
            logger.info(f"Stored {total_chunks} chunks in MongoDB")
            return chunk_ids
        except Exception as e:
            logger.error(f"Error storing chunks: {str(e)}")
            raise

    def process_pdf(self, pdf_path: str) -> list:
        """Process PDF and store chunks in MongoDB"""
        try:
            # Extract text
            text = self.extract_text_from_pdf(pdf_path)
            
            # Create chunks as a generator
            chunks = self.create_chunks(text)
            
            # Prepare metadata
            metadata = {
                'filename': os.path.basename(pdf_path),
                'file_path': pdf_path,
                'file_size': os.path.getsize(pdf_path),
                'processed_at': datetime.utcnow().isoformat()
            }
            
            # Store chunks
            chunk_ids = self.store_chunks(chunks, metadata)
            
            return chunk_ids
            
        except Exception as e:
            logger.error(f"Error processing PDF: {str(e)}")
            raise

def main():
    try:
        # Initialize processor
        processor = PDFProcessor()
        
        # Process PDF
        pdf_path = "Easify_SMS_Application_Features.pdf"
        if not os.path.exists(pdf_path):
            logger.error(f"PDF file not found: {pdf_path}")
            return
            
        chunk_ids = processor.process_pdf(pdf_path)
        logger.info(f"Successfully processed PDF. Stored {len(chunk_ids)} chunks.")
        
        # Verify storage
        total_chunks = processor.collection.count_documents({})
        logger.info(f"Total chunks in database: {total_chunks}")
        
        # Test semantic search
        test_query = "What are the main features of the SMS application?"
        results = processor.semantic_search(test_query)
        logger.info(f"\nSemantic search results for: {test_query}")
        for i, result in enumerate(results, 1):
            logger.info(f"\nResult {i} (Score: {result['score']:.4f}):")
            logger.info(f"Text: {result['chunk_text'][:200]}...")
        
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        raise

if __name__ == "__main__":
    main() 