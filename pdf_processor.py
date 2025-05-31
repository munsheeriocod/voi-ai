import os
import logging
from PyPDF2 import PdfReader
from typing import List, Dict
from datetime import datetime
from bson import ObjectId
from app.database import get_db
from semantic_search import SemanticSearch

# Configure logging
logger = logging.getLogger(__name__)

class PDFProcessor:
    def __init__(self):
        self.db = get_db()
        self.collection = self.db.pdf_knowledge_base
        self.chunk_size = 1000  # Number of characters per chunk
        self.chunk_overlap = 200  # Number of characters to overlap between chunks
        self.semantic_search = SemanticSearch()

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """
        Extract text from a PDF file.
        
        Args:
            pdf_path (str): Path to the PDF file
            
        Returns:
            str: Extracted text from the PDF
        """
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

    def create_text_chunks(self, text: str) -> List[str]:
        """
        Split text into overlapping chunks.
        
        Args:
            text (str): Text to split into chunks
            
        Returns:
            List[str]: List of text chunks
        """
        chunks = []
        start = 0
        text_length = len(text)

        while start < text_length:
            end = start + self.chunk_size
            if end > text_length:
                end = text_length
            
            chunk = text[start:end]
            chunks.append(chunk)
            
            # Move start position, accounting for overlap
            start = end - self.chunk_overlap

        logger.info(f"Created {len(chunks)} text chunks")
        return chunks

    def process_pdf(self, pdf_path: str, metadata: Dict = None) -> List[str]:
        """
        Process a PDF file: extract text, create chunks, and store in MongoDB with embeddings.
        
        Args:
            pdf_path (str): Path to the PDF file
            metadata (Dict, optional): Additional metadata about the PDF
            
        Returns:
            List[str]: List of inserted document IDs
        """
        try:
            # Extract text from PDF
            text = self.extract_text_from_pdf(pdf_path)
            
            # Create text chunks
            chunks = self.create_text_chunks(text)
            
            # Prepare metadata
            if metadata is None:
                metadata = {}
            
            # Add PDF-specific metadata
            metadata.update({
                "filename": os.path.basename(pdf_path),
                "file_path": pdf_path,
                "file_size": os.path.getsize(pdf_path),
                "total_chunks": len(chunks),
                "processed_at": datetime.utcnow().isoformat()
            })
            
            # Process chunks and store with embeddings
            chunk_ids = self.semantic_search.process_and_store_chunks(chunks, metadata)
            
            logger.info(f"Successfully processed PDF and stored {len(chunk_ids)} chunks with embeddings")
            return chunk_ids
            
        except Exception as e:
            logger.error(f"Error processing PDF: {str(e)}")
            raise

    def get_relevant_chunks(self, query: str, limit: int = 3) -> List[Dict]:
        """
        Get relevant chunks for a query using semantic search.
        
        Args:
            query (str): The user's question
            limit (int): Maximum number of chunks to return
            
        Returns:
            List[Dict]: List of relevant chunks
        """
        try:
            return self.semantic_search.find_similar_chunks(query, limit)
        except Exception as e:
            logger.error(f"Error getting relevant chunks: {str(e)}")
            raise 