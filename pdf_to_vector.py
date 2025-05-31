import os
from typing import List, Dict, Any, Generator
from PyPDF2 import PdfReader
from openai import OpenAI
from pinecone import Pinecone
from dotenv import load_dotenv
import logging
from tqdm import tqdm
import hashlib
import json
import time

# Configure logging with more detailed format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class PDFToVector:
    def __init__(self):
        """Initialize the PDF to vector converter with OpenAI and Pinecone clients."""
        logger.info("Initializing PDFToVector...")
        start_time = time.time()
        
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
        self.index = self.pc.Index(os.getenv("PINECONE_INDEX"))
        self.batch_size = 5  # Reduced batch size for faster processing
        self.cache_dir = "embedding_cache"
        
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
            logger.info(f"Created cache directory: {self.cache_dir}")
            
        logger.info(f"Initialization completed in {time.time() - start_time:.2f} seconds")
        
    def _get_cache_path(self, text: str) -> str:
        """Get cache file path for a text."""
        text_hash = hashlib.md5(text.encode()).hexdigest()
        return os.path.join(self.cache_dir, f"{text_hash}.json")
        
    def _get_cached_embedding(self, text: str) -> List[float]:
        """Get cached embedding if it exists."""
        cache_path = self._get_cache_path(text)
        if os.path.exists(cache_path):
            logger.debug(f"Cache hit for text hash: {os.path.basename(cache_path)}")
            with open(cache_path, 'r') as f:
                return json.load(f)
        return None
        
    def _cache_embedding(self, text: str, embedding: List[float]):
        """Cache an embedding."""
        cache_path = self._get_cache_path(text)
        with open(cache_path, 'w') as f:
            json.dump(embedding, f)
        logger.debug(f"Cached embedding for text hash: {os.path.basename(cache_path)}")
        
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text from a PDF file."""
        logger.info(f"Starting text extraction from: {pdf_path}")
        start_time = time.time()
        
        try:
            reader = PdfReader(pdf_path)
            total_pages = len(reader.pages)
            logger.info(f"PDF has {total_pages} pages")
            
            text = ""
            for i, page in enumerate(reader.pages, 1):
                page_text = page.extract_text()
                text += page_text + "\n"
                logger.debug(f"Extracted text from page {i}/{total_pages}")
            
            text = text.strip()
            logger.info(f"Text extraction completed in {time.time() - start_time:.2f} seconds")
            logger.info(f"Extracted text length: {len(text)} characters")
            
            return text
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {str(e)}")
            raise

    def chunk_text(self, text: str, chunk_size: int = 500, chunk_overlap: int = 100) -> List[str]:
        """Split text into overlapping chunks."""
        logger.info("Starting text chunking...")
        start_time = time.time()
        
        if not text.strip():
            logger.warning("Empty text provided for chunking")
            return []
            
        # Split text into sentences first
        sentences = text.replace('\n', ' ').split('. ')
        logger.info(f"Split text into {len(sentences)} sentences")
        
        chunks = []
        current_chunk = []
        current_length = 0
        
        for sentence in sentences:
            sentence = sentence.strip() + '. '
            sentence_length = len(sentence)
            
            if current_length + sentence_length > chunk_size and current_chunk:
                # Join current chunk and add to chunks
                chunk_text = ''.join(current_chunk).strip()
                if chunk_text:
                    chunks.append(chunk_text)
                
                # Start new chunk with overlap
                overlap_start = max(0, len(current_chunk) - chunk_overlap)
                current_chunk = current_chunk[overlap_start:]
                current_length = sum(len(s) for s in current_chunk)
            
            current_chunk.append(sentence)
            current_length += sentence_length
        
        # Add the last chunk if it exists
        if current_chunk:
            chunk_text = ''.join(current_chunk).strip()
            if chunk_text:
                chunks.append(chunk_text)
        
        logger.info(f"Chunking completed in {time.time() - start_time:.2f} seconds")
        logger.info(f"Created {len(chunks)} chunks")
        
        # Log chunk sizes for debugging
        chunk_sizes = [len(chunk) for chunk in chunks]
        logger.info(f"Chunk size statistics - Min: {min(chunk_sizes)}, Max: {max(chunk_sizes)}, Avg: {sum(chunk_sizes)/len(chunk_sizes):.2f}")
        
        return chunks

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for a list of texts using OpenAI's text-embedding-3-small model."""
        logger.info(f"Getting embeddings for {len(texts)} texts...")
        start_time = time.time()
        
        try:
            # Filter out empty texts
            texts = [t for t in texts if t.strip()]
            if not texts:
                logger.warning("No valid texts to embed")
                return []
                
            # Check cache first
            embeddings = []
            texts_to_fetch = []
            
            for text in texts:
                cached = self._get_cached_embedding(text)
                if cached:
                    embeddings.append(cached)
                else:
                    texts_to_fetch.append(text)
            
            logger.info(f"Cache hits: {len(embeddings)}, Cache misses: {len(texts_to_fetch)}")
            
            # Get embeddings for uncached texts
            if texts_to_fetch:
                logger.info(f"Fetching {len(texts_to_fetch)} embeddings from API...")
                api_start_time = time.time()
                
                response = self.openai_client.embeddings.create(
                    input=texts_to_fetch,
                    model="text-embedding-3-small"  # Using OpenAI's embedding model
                )
                
                logger.info(f"API call completed in {time.time() - api_start_time:.2f} seconds")
                
                # Cache new embeddings
                for text, embedding in zip(texts_to_fetch, response.data):
                    self._cache_embedding(text, embedding.embedding)
                    embeddings.append(embedding.embedding)
            
            logger.info(f"Embedding generation completed in {time.time() - start_time:.2f} seconds")
            return embeddings
            
        except Exception as e:
            logger.error(f"Error getting embeddings: {str(e)}")
            raise

    def process_chunks_in_batches(self, chunks: List[str], metadata: Dict[str, Any]) -> Generator[Dict[str, Any], None, None]:
        """Process chunks in batches and yield progress updates."""
        logger.info("Starting batch processing...")
        start_time = time.time()
        
        total_chunks = len(chunks)
        if total_chunks == 0:
            logger.warning("No chunks to process")
            yield {
                "status": "error",
                "message": "No text content found in PDF",
                "progress": 100
            }
            return
            
        processed_chunks = 0
        
        for i in range(0, total_chunks, self.batch_size):
            batch_start_time = time.time()
            batch = chunks[i:i + self.batch_size]
            logger.info(f"Processing batch {i//self.batch_size + 1}/{(total_chunks + self.batch_size - 1)//self.batch_size}")
            
            try:
                embeddings = self.get_embeddings(batch)
                vectors = []
                
                for j, (chunk, embedding) in enumerate(zip(batch, embeddings)):
                    vector_id = f"{metadata['filename']}-{i+j}"
                    vectors.append((vector_id, embedding, {"text": chunk, **metadata}))
                
                if vectors:
                    logger.info(f"Upserting {len(vectors)} vectors to Pinecone...")
                    upsert_start_time = time.time()
                    self.index.upsert(vectors=vectors)
                    logger.info(f"Pinecone upsert completed in {time.time() - upsert_start_time:.2f} seconds")
                
                processed_chunks += len(batch)
                batch_time = time.time() - batch_start_time
                logger.info(f"Batch processed in {batch_time:.2f} seconds")
                
                yield {
                    "status": "processing",
                    "progress": (processed_chunks / total_chunks) * 100,
                    "processed_chunks": processed_chunks,
                    "total_chunks": total_chunks,
                    "batch_time": batch_time
                }
                
            except Exception as e:
                logger.error(f"Error processing batch: {str(e)}")
                raise
        
        total_time = time.time() - start_time
        logger.info(f"Batch processing completed in {total_time:.2f} seconds")

    def process_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """Process a PDF file and store its vectors in Pinecone."""
        logger.info(f"Starting PDF processing: {pdf_path}")
        start_time = time.time()
        
        try:
            # Extract text from PDF
            text = self.extract_text_from_pdf(pdf_path)
            if not text.strip():
                logger.warning("No text content found in PDF")
                return {
                    "status": "error",
                    "message": "No text content found in PDF"
                }
            
            # Split text into chunks
            chunks = self.chunk_text(text)
            if not chunks:
                logger.warning("No valid chunks generated from PDF")
                return {
                    "status": "error",
                    "message": "No valid chunks generated from PDF"
                }
            
            # Prepare metadata
            metadata = {
                "filename": os.path.basename(pdf_path),
                "source": "pdf",
                "total_chunks": len(chunks)
            }
            
            # Process chunks in batches
            for progress in self.process_chunks_in_batches(chunks, metadata):
                logger.info(f"Processing progress: {progress['progress']:.2f}%")
            
            total_time = time.time() - start_time
            logger.info(f"PDF processing completed in {total_time:.2f} seconds")
            
            return {
                "status": "success",
                "message": f"Successfully processed PDF: {metadata['filename']}",
                "total_chunks": len(chunks),
                "processing_time": total_time
            }
            
        except Exception as e:
            logger.error(f"Error processing PDF: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }

def main():
    """Example usage of the PDFToVector class."""
    # Initialize the converter
    converter = PDFToVector()
    
    # Process a PDF file
    pdf_path = "example.pdf"  # Replace with your PDF path
    result = converter.process_pdf(pdf_path)
    
    print(result)

if __name__ == "__main__":
    main() 