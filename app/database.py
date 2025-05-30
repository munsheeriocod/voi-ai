from pymongo import MongoClient
from datetime import datetime
import os
import logging
from bson.objectid import ObjectId
from pymongo.results import DeleteResult

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
    calls_collection = db['calls']
    
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
        logger.info(f"Contacts collection access successful. Current document count: {count}")
        
        # Test calls collection access
        calls_count = calls_collection.count_documents({})
        logger.info(f"Calls collection access successful. Current document count: {calls_count}")
        
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
        logger.info(f"Contacts Collection name: {contacts_collection.name}")
        logger.info(f"Calls Collection name: {calls_collection.name}")
        
        # Get document count for contacts
        contacts_count = contacts_collection.count_documents({})
        logger.info(f"Total documents in contacts collection: {contacts_count}")
        
        # Get document count for calls
        calls_count = calls_collection.count_documents({})
        logger.info(f"Total documents in calls collection: {calls_count}")
        
        # Get a sample document from contacts if any exist
        sample_contact = contacts_collection.find_one()
        if sample_contact:
            logger.info(f"Sample contact document: {sample_contact}")
        else:
            logger.info("No documents found in contacts collection")
            
        # Get a sample document from calls if any exist
        sample_call = calls_collection.find_one()
        if sample_call:
            logger.info(f"Sample call document: {sample_call}")
        else:
            logger.info("No documents found in calls collection")
            
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

def get_contact_by_id(contact_id_str):
    """Get contact by ObjectId string"""
    try:
        # Validate the ObjectId string
        if not ObjectId.is_valid(contact_id_str):
            logger.error(f"Invalid ObjectId format: {contact_id_str}")
            return None
            
        # Convert string to ObjectId
        object_id = ObjectId(contact_id_str)
        
        # Find the document by ObjectId
        contact = contacts_collection.find_one({'_id': object_id})
        
        if contact:
            logger.info(f"Fetched contact with ID: {contact_id_str}")
            # Convert ObjectId to string for JSON serialization
            contact['_id'] = str(contact['_id'])
            return contact
        else:
            logger.info(f"Contact not found with ID: {contact_id_str}")
            return None
            
    except Exception as e:
        logger.error(f"Error fetching contact by ID: {str(e)}")
        return None

def get_contact_by_phone(phone_number):
    """Get contact by phone number"""
    try:
        contact = contacts_collection.find_one({'phone_number': phone_number})
        return contact
    except Exception as e:
        logger.error(f"Error fetching contact: {str(e)}")
        return None

def get_all_contacts(page=1, per_page=10, sort_by='_id', sort_order='asc', search=None, filters=None):
    """Get all contacts from the database with pagination, sorting, and filtering"""
    try:
        logger.info(f"Fetching contacts - Page: {page}, Per Page: {per_page}, Sort By: {sort_by}, Sort Order: {sort_order}, Search: {search}, Filters: {filters}")
        
        # Build query filter
        query = {}
        if search:
            # Basic text search across relevant fields (adjust fields as needed)
            query['$or'] = [
                {'name': {'$regex': search, '$options': 'i'}},
                {'email': {'$regex': search, '$options': 'i'}},
                {'phone_number': {'$regex': search, '$options': 'i'}},
                {'country': {'$regex': search, '$options': 'i'}},
                {'user_type': {'$regex': search, '$options': 'i'}},
                {'plan': {'$regex': search, '$options': 'i'}},
                {'registration_status': {'$regex': search, '$options': 'i'}},
                {'customer_care': {'$regex': search, '$options': 'i'}}
            ]
            
        if filters:
            # TODO: Implement specific field filtering based on filters dictionary
            pass # Placeholder for now
            
        # Build sort order
        sort_direction = 1 if sort_order == 'asc' else -1
        sort = [(sort_by, sort_direction)]
        
        # Calculate skip and limit for pagination
        skip = (page - 1) * per_page
        limit = per_page
        
        # Perform the query with sorting, skip, and limit
        contacts_cursor = contacts_collection.find(query).sort(sort).skip(skip).limit(limit)
        
        # Convert ObjectId to string for JSON serialization and collect results
        contacts_list = []
        for contact in contacts_cursor:
            if '_id' in contact:
                contact['_id'] = str(contact['_id'])
            contacts_list.append(contact)
            
        logger.info(f"Fetched {len(contacts_list)} contacts from database with criteria")
        
        # Get total count for pagination info (without skip and limit)
        total_count = contacts_collection.count_documents(query)
        logger.info(f"Total contacts matching query: {total_count}")
        
        return contacts_list, total_count
        
    except Exception as e:
        logger.error(f"Error fetching contacts with criteria: {str(e)}")
        return [], 0

def count_active_calls():
    """Count the number of active calls in the calls collection"""
    try:
        # Assuming a 'status' field exists and 'active' indicates an active call
        active_count = calls_collection.count_documents({'status': 'active'})
        logger.info(f"Counted {active_count} active calls")
        return active_count
    except Exception as e:
        logger.error(f"Error counting active calls: {str(e)}")
        return 0

def get_dashboard_metrics():
    """Get key metrics for the dashboard"""
    try:
        logger.info("Fetching dashboard metrics")
        
        # Get total number of contacts
        total_contacts = contacts_collection.count_documents({})
        
        # Get active calls count
        active_calls = count_active_calls()
        
        metrics = {
            "active_calls": active_calls,
            "customer_retention": 0.0, # Placeholder
            "churn_risk_alerts": 0, # Placeholder
            "ai_success_rate": 0.0, # Placeholder
            "total_contacts": total_contacts # Actual count
        }
        
        logger.info(f"Dashboard metrics: {metrics}")
        return metrics
    except Exception as e:
        logger.error(f"Error fetching dashboard metrics: {str(e)}")
        return {}

def create_contact(contact_data):
    """Create a new contact from mapped data"""
    try:
        logger.info("Attempting to create contact...")
        
        # Validate required fields (only phone_number is strictly required for creation)
        phone_number = contact_data.get('phone_number')
        if not phone_number:
            logger.error("Cannot create contact: phone_number is required")
            return None
            
        # Check if document already exists using phone_number (unique index)
        existing = contacts_collection.find_one({'phone_number': phone_number})
        if existing:
            logger.info(f"Contact with phone {phone_number} already exists")
            # Optionally return existing contact ID or a specific indicator
            return None # Or return existing['_id']
        
        # Add timestamps
        now = datetime.utcnow()
        contact_data['created_at'] = contact_data.get('created_at', now) # Allow overriding for imports if needed
        contact_data['updated_at'] = now
        
        # Clean up any potential _id passed in the input data to avoid issues
        contact_data.pop('_id', None)
        
        logger.info(f"Inserting document into MongoDB: {contact_data}")
        result = contacts_collection.insert_one(contact_data)
        
        if result.inserted_id:
            logger.info(f"Contact created successfully with ID: {result.inserted_id}")
            # Verify the document was actually inserted (optional but good for debugging)
            inserted_doc = contacts_collection.find_one({'_id': result.inserted_id})
            if inserted_doc:
                 logger.info(f"Verified document insertion for ID: {result.inserted_id}")
                 # Convert ObjectId to string before returning
                 inserted_doc['_id'] = str(inserted_doc['_id'])
                 return inserted_doc # Return the created document with string _id
            else:
                logger.error("Document insertion verification failed")
                return None
        else:
            logger.error("No document ID returned from insert operation")
            return None
            
    except Exception as insert_error:
        logger.error(f"Error during document insertion: {str(insert_error)}")
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

def update_contact_by_id(contact_id_str, contact_data):
    """Update an existing contact by ObjectId string"""
    try:
        logger.info(f"Attempting to update contact with ID: {contact_id_str} with data: {contact_data}")
        # Validate the ObjectId string
        if not ObjectId.is_valid(contact_id_str):
            logger.error(f"Invalid ObjectId format for update: {contact_id_str}")
            return False, "Invalid contact ID format"
            
        # Convert string to ObjectId
        object_id = ObjectId(contact_id_str)
        
        # Prepare update data - remove _id if present and add updated_at
        update_data = contact_data.copy() # Use a copy to not modify original dict
        update_data.pop('_id', None)
        update_data['updated_at'] = datetime.utcnow()
        
        result = contacts_collection.update_one(
            {'_id': object_id},
            {'$set': update_data}
        )
        
        if result.matched_count == 0:
            logger.warning(f"No contact found with ID {contact_id_str} for update.")
            return False, "Contact not found"
            
        success = result.modified_count > 0
        logger.info(f"Contact update by ID {contact_id_str} {'successful' if success else 'failed'}. Matched: {result.matched_count}, Modified: {result.modified_count}")
        
        return success, None # Return success status and no error message on success
        
    except Exception as e:
        logger.error(f"Error updating contact by ID {contact_id_str}: {str(e)}")
        return False, str(e)

def delete_contact_by_id(contact_id_str):
    """Delete a contact by ObjectId string"""
    try:
        logger.info(f"Attempting to delete contact with ID: {contact_id_str}")
        # Validate the ObjectId string
        if not ObjectId.is_valid(contact_id_str):
            logger.error(f"Invalid ObjectId format for delete: {contact_id_str}")
            return False, "Invalid contact ID format"
            
        # Convert string to ObjectId
        object_id = ObjectId(contact_id_str)
        
        # Perform the delete operation
        result: DeleteResult = contacts_collection.delete_one({'_id': object_id})
        
        if result.deleted_count == 0:
            logger.warning(f"No contact found with ID {contact_id_str} for deletion.")
            return False, "Contact not found"
            
        logger.info(f"Contact with ID {contact_id_str} deleted successfully.")
        return True, None # Return success status and no error message on success
        
    except Exception as e:
        logger.error(f"Error deleting contact by ID {contact_id_str}: {str(e)}")
        return False, str(e) 