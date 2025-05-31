import os
from pinecone import Pinecone
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def check_pinecone_index():
    try:
        # Initialize Pinecone
        pc = Pinecone(api_key=os.getenv('PINECONE_API_KEY'))
        index = pc.Index(os.getenv('PINECONE_INDEX'))
        
        # Get index stats
        stats = index.describe_index_stats()
        logger.info(f"Index stats: {stats}")
        
        # Query a test vector to see if we get any results
        test_query = [0.0] * 1536  # OpenAI embedding dimension
        results = index.query(
            vector=test_query,
            top_k=5,
            include_metadata=True
        )
        
        logger.info(f"Query results: {results}")
        
    except Exception as e:
        logger.error(f"Error checking Pinecone: {str(e)}")

if __name__ == "__main__":
    check_pinecone_index() 