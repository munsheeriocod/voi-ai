import logging
from typing import Dict, List, Optional
from datetime import datetime
from ...database import get_contact_by_phone, create_contact, update_contact
from .date_utils import parse_date

logger = logging.getLogger(__name__)

class ContactProcessor:
    def __init__(self):
        self.contacts = []
        self.errors = []
        self.skipped = []
        self.duplicates = []
        self.updated = []
        self.current_import_phones = set()
        self.row_number = 2  # Start from 2 since row 1 is headers
        
    def process_row(self, row: Dict[str, str]) -> None:
        """Process a single contact row"""
        try:
            # Skip if no phone number
            phone = row.get('Phone', '').strip()
            logger.info(f"Row {self.row_number} - Phone: '{phone}'")
            
            if not phone:
                logger.info(f"Row {self.row_number} - Skipping: No phone number")
                self.skipped.append({
                    'row': self.row_number,
                    'reason': 'No phone number provided'
                })
                self.row_number += 1
                return
                
            # Check for duplicates within current import
            if phone in self.current_import_phones:
                logger.info(f"Row {self.row_number} - Skipping: Duplicate phone")
                self.duplicates.append({
                    'row': self.row_number,
                    'phone': phone
                })
                self.row_number += 1
                return
                
            # Check for existing contact
            existing_contact = get_contact_by_phone(phone)
            
            # Create contact object
            contact = self._create_contact_object(row)
            
            if existing_contact:
                # Update existing contact
                success = update_contact(phone, contact)
                if success:
                    self.updated.append({
                        'row': self.row_number,
                        'phone': phone
                    })
            else:
                # Create new contact
                contact_id = create_contact(contact)
                if contact_id:
                    self.contacts.append({
                        'row': self.row_number,
                        'phone': phone
                    })
                
            self.current_import_phones.add(phone)
            self.row_number += 1
            
        except Exception as e:
            logger.error(f"Row {self.row_number} - Error: {str(e)}")
            self.errors.append({
                'row': self.row_number,
                'error': str(e)
            })
            self.row_number += 1
            
    def _create_contact_object(self, row: Dict[str, str]) -> Dict:
        """Create a contact object from row data"""
        try:
            # Strip whitespace from all fields
            row = {k: v.strip() if isinstance(v, str) else v for k, v in row.items()}
            
            # Parse dates
            created_at = parse_date(row.get('Created At', ''))
            last_logged_in_at = parse_date(row.get('Last Logged In At', ''))
            last_recharged_at = parse_date(row.get('Last Recharged At', ''))
            
            # Create contact object with database field names
            contact = {
                'phone_number': row.get('Phone', ''),  # Use phone_number for database
                'name': row.get('Name', ''),
                'email': row.get('Email', ''),
                'created_at': created_at,
                'last_logged_in_at': last_logged_in_at,
                'last_recharged_at': last_recharged_at,
                'updated_at': datetime.utcnow()
            }
            
            # Add any additional fields from the CSV
            for key, value in row.items():
                if value and key not in ['Phone', 'Name', 'Email', 'Created At', 'Last Logged In At', 'Last Recharged At']:
                    # Convert header to snake_case for database
                    db_key = key.lower().replace(' ', '_')
                    contact[db_key] = value
                    
            return contact
            
        except Exception as e:
            raise
            
    def get_response(self) -> Dict:
        """Get standardized response"""
        total_created = len(self.contacts)
        total_updated = len(self.updated)
        total_contacts = total_created + total_updated
        
        response = {
            'message': 'Import completed',
            'total_contacts': total_contacts,
            'contacts_created': total_created,
            'contacts_updated': total_updated,
            'rows_skipped': len(self.skipped),
            'duplicates_found': len(self.duplicates),
            'errors': self.errors,
            'skipped_rows': self.skipped,
            'duplicate_rows': self.duplicates
        }
        return response 