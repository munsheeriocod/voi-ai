from pymongo import MongoClient
from datetime import datetime
import os
import logging

# Configure logging
logger = logging.getLogger(__name__)

# MongoDB connection variables
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017')
DB_NAME = os.getenv('MONGODB_DATABASE', 'voice_assistant')

# MongoDB connection
try:
    logger.info("=== Initializing MongoDB Connection ===")
    logger.info(f"Attempting to connect to MongoDB at: {MONGO_URI}")
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    contacts_collection = db['contacts']
    
    # Test connection
    client.admin.command('ping')
    logger.info("MongoDB connection successful")
    
    # Log database and collection details
    logger.info(f"Connected to database: {db.name}")
    logger.info(f"Using collection: {contacts_collection.name}")
    logger.info(f"Current document count: {contacts_collection.count_documents({})}")
    
except Exception as e:
    logger.error(f"Error connecting to MongoDB: {str(e)}")
    raise
finally:
    logger.info("=== Finished MongoDB Connection Setup ===")

def test_connection():
    """Test MongoDB connection and database access"""
    try:
        # Test connection
        client.admin.command('ping')
        logger.info("MongoDB connection successful")
        
        # Test database access
        db.command('ping')
        logger.info(f"Database access successful: {DB_NAME}")
        
        # Test collection access
        count = contacts_collection.count_documents({})
        logger.info(f"Collection access successful. Current document count: {count}")
        
        return True
    except Exception as e:
        logger.error(f"Database connection test failed: {str(e)}")
        return False

def check_database_state():
    """Check the current state of the database"""
    try:
        logger.info("=== Checking Database State ===")
        
        # Test connection
        client.admin.command('ping')
        logger.info("MongoDB connection successful")
        
        # Get database info
        logger.info(f"Database name: {db.name}")
        logger.info(f"Collection name: {contacts_collection.name}")
        
        # Get document count
        count = contacts_collection.count_documents({})
        logger.info(f"Total documents in contacts collection: {count}")
        
        # Get a sample document if any exist
        sample = contacts_collection.find_one()
        if sample:
            logger.info(f"Sample document: {sample}")
        else:
            logger.info("No documents found in collection")
            
        # List all documents
        all_docs = list(contacts_collection.find())
        logger.info(f"Total documents found: {len(all_docs)}")
        if all_docs:
            logger.info("First few documents:")
            for doc in all_docs[:3]:
                logger.info(f"Document: {doc}")
                
        return True
    except Exception as e:
        logger.error(f"Error checking database state: {str(e)}")
        return False
    finally:
        logger.info("=== Finished Database State Check ===")

def ensure_collection_exists():
    """Ensure the contacts collection exists and has proper indexes"""
    try:
        # Check if collection exists
        collections = db.list_collection_names()
        if 'contacts' not in collections:
            logger.info("Creating contacts collection...")
            # Create collection by inserting and removing a dummy document
            db.contacts.insert_one({"dummy": True})
            db.contacts.delete_one({"dummy": True})
            logger.info("Contacts collection created")
        
        # Ensure indexes exist
        contacts_collection.create_index('phone_number', unique=True)
        logger.info("Collection indexes verified")
        
        return True
    except Exception as e:
        logger.error(f"Error ensuring collection exists: {str(e)}")
        return False

def init_db():
    """Initialize database with indexes"""
    try:
        # Test connection first
        if not test_connection():
            raise Exception("Database connection test failed")
            
        # Create unique index on phone_number
        contacts_collection.create_index('phone_number', unique=True)
        logger.info(f"Database initialized successfully: {DB_NAME}")
        
        # Check initial database state
        check_database_state()
    except Exception as e:
        logger.error(f"Database initialization error: {str(e)}")
        raise

def get_contact_by_phone(phone_number):
    """Get contact by phone number"""
    try:
        contact = contacts_collection.find_one({'phone_number': phone_number})
        return contact
    except Exception as e:
        logger.error(f"Error fetching contact: {str(e)}")
        return None

def create_contact(contact_data):
    """Create a new contact"""
    try:
        
        # Map CSV fields to database fields using exact header names
        try:
            mapped_data = {
                'name': contact_data.get('name', ''),
                'email': contact_data.get('email', ''),
                'phone_number': contact_data.get('phone_number', ''),  # Using exact 'Phone' header
                'country': contact_data.get('country', ''),
                'user_type': contact_data.get('user_type', ''),
                'plan': contact_data.get('plan', ''),
                'registration_status': contact_data.get('registration_status', ''),
                'customer_care': contact_data.get('customer_care', ''),
                'opt_out_ratio': float(contact_data.get('opt_out_ratio', 0) or 0),
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow(),
                'last_logged_in': contact_data.get('last_logged_in_at', ''),
                'last_recharged': contact_data.get('last_recharged_at', '')
            }
        except KeyError as ke:
            logger.error(f"Missing key in contact data: {str(ke)}")
            return None
        except ValueError as ve:
            logger.error(f"Error converting data: {str(ve)}")
            return None
        
        # Validate required fields
        if not mapped_data['phone_number']:
            logger.error("Cannot create contact: Phone is required")
            return None
            
        # Try to insert the document
        try:
            logger.info("Attempting to insert document into MongoDB...")
            # Check if document already exists
            existing = contacts_collection.find_one({'phone_number': mapped_data['phone_number']})
            if existing:
                logger.info(f"Contact with phone {mapped_data['phone_number']} already exists")
                return None
                
            # Log the collection details before insert
            logger.info(f"Collection name: {contacts_collection.name}")
            logger.info(f"Database name: {db.name}")
            logger.info(f"Current document count: {contacts_collection.count_documents({})}")
            
            result = contacts_collection.insert_one(mapped_data)
            if result.inserted_id:
                logger.info(f"Contact created successfully with ID: {result.inserted_id}")
                # Verify the document was actually inserted
                inserted_doc = contacts_collection.find_one({'_id': result.inserted_id})
                if inserted_doc:
                    logger.info(f"Verified document insertion: {inserted_doc}")
                    # Double check the document count
                    new_count = contacts_collection.count_documents({})
                    logger.info(f"New document count: {new_count}")
                    return result.inserted_id
                else:
                    logger.error("Document insertion verification failed")
                    return None
            else:
                logger.error("No document ID returned from insert operation")
                return None
        except Exception as insert_error:
            logger.error(f"Error during document insertion: {str(insert_error)}")
            return None
            
    except Exception as e:
        logger.error(f"Error creating contact: {str(e)}")
        return None

def update_contact(phone_number, contact_data):
    """Update an existing contact"""
    try:
        
        # Update timestamp
        contact_data['updated_at'] = datetime.utcnow()
        
        result = contacts_collection.update_one(
            {'phone_number': phone_number},
            {'$set': contact_data}
        )
        success = result.modified_count > 0
        logger.info(f"Contact update {'successful' if success else 'failed'}")
        return success
    except Exception as e:
        logger.error(f"Error updating contact: {str(e)}")
        return False 