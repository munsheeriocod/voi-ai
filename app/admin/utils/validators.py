from datetime import datetime
import logging
from .date_utils import parse_date, is_valid_date
import re
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

# Required headers in original format
REQUIRED_HEADERS = {
    'Phone'  # Only require phone number
}

# Optional headers that will be handled automatically
OPTIONAL_HEADERS = {
    'Name',
    'Email',
    'Created At',
    'Last Logged In At',
    'Last Recharged At',
    'Updated At'  # Will be set automatically on create/update
}

# Header mapping rules for common variations
HEADER_MAPPINGS = {
    # Phone number variations
    'Phone': 'Phone',
    'Phone Number': 'Phone',
    'Mobile': 'Phone',
    'Mobile Number': 'Phone',
    'Contact': 'Phone',
    'Contact Number': 'Phone',
    
    # Date variations
    'Created At': 'Created At',
    'Created': 'Created At',
    'Registration Date': 'Created At',
    'Signup Date': 'Created At',
    
    'Updated At': 'Updated At',
    'Last Updated': 'Updated At',
    'Modified': 'Updated At',
    'Modified At': 'Updated At',
    
    'Last Logged In': 'Last Logged In At',
    'Last Login': 'Last Logged In At',
    'Last Login At': 'Last Logged In At',
    'Last Logged In At': 'Last Logged In At',
    
    'Last Recharged': 'Last Recharged At',
    'Last Recharge': 'Last Recharged At',
    'Last Recharge At': 'Last Recharged At',
    'Last Recharged At': 'Last Recharged At',
    
    # Name variations
    'Full Name': 'Name',
    'User Name': 'Name',
    'Customer Name': 'Name',
    
    # Email variations
    'Email Address': 'Email',
    'E-mail': 'Email',
    'E-mail Address': 'Email'
}

def normalize_header(header: str) -> str:
    """Normalize header name for comparison"""
    if not header:
        return ''
    # Convert to lowercase and remove special characters
    normalized = header.lower().strip()
    # Remove any special characters
    normalized = ''.join(c for c in normalized if c.isalnum() or c.isspace())
    # Map to standard header if exists
    return HEADER_MAPPINGS.get(header, header)

def validate_csv_headers(headers: List[str]) -> Tuple[bool, List[str]]:
    """Validate CSV headers"""
    if not headers:
        return False, ["No headers found"]
        
    # Log the validation process
    logger.info(f"Validating headers: {headers}")
    
    # Check for required headers
    missing_headers = []
    for required in REQUIRED_HEADERS:
        if not any(normalize_header(h) == required for h in headers):
            missing_headers.append(required)
            
    if missing_headers:
        logger.error(f"Missing required headers: {missing_headers}")
        return False, [f"Missing required header: {h}" for h in missing_headers]
        
    logger.info("Header validation successful")
    return True, []

def get_header_mapping(headers: List[str]) -> Dict[str, str]:
    """
    Create a mapping between original headers and normalized headers
    Returns: dict mapping original headers to normalized headers
    """
    return {h: normalize_header(h) for h in headers}

def parse_date(date_str):
    """Parse date string in various formats"""
    if not date_str:
        return None
        
    # Clean the input string
    date_str = date_str.strip()
    
    # Try to handle common variations in date formats
    date_str = date_str.replace('  ', ' ')  # Remove double spaces
    date_str = date_str.replace('a.m.', 'AM').replace('p.m.', 'PM')  # Standardize AM/PM
    date_str = date_str.replace('a.m', 'AM').replace('p.m', 'PM')
    date_str = date_str.replace('am', 'AM').replace('pm', 'PM')
    
    # Try the exact format first (most common case)
    try:
        return datetime.strptime(date_str, '%m-%d-%Y %I:%M:%S %p')
    except ValueError:
        pass
    
    # If exact format fails, try other formats
    date_formats = [
        # Full datetime formats
        '%m-%d-%Y %H:%M:%S',     # 24-hour
        '%Y-%m-%d %I:%M:%S %p',  # 12-hour with AM/PM
        '%Y-%m-%d %H:%M:%S',     # 24-hour
        '%d-%m-%Y %I:%M:%S %p',  # 12-hour with AM/PM
        '%d-%m-%Y %H:%M:%S',     # 24-hour
        
        # Date with microseconds
        '%Y-%m-%d %H:%M:%S.%f',
        '%m-%d-%Y %H:%M:%S.%f',
        '%d-%m-%Y %H:%M:%S.%f',
        
        # Date only formats
        '%Y-%m-%d',
        '%m-%d-%Y',
        '%d-%m-%Y',
        '%Y/%m/%d',
        '%m/%d/%Y',
        '%d/%m/%Y',
        
        # Additional formats
        '%b %d %Y %I:%M:%S %p',  # Jan 01 2024 01:30:45 PM
        '%B %d %Y %I:%M:%S %p',  # January 01 2024 01:30:45 PM
        '%d %b %Y %I:%M:%S %p',  # 01 Jan 2024 01:30:45 PM
        '%d %B %Y %I:%M:%S %p',  # 01 January 2024 01:30:45 PM
    ]
    
    for fmt in date_formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
            
    # If all formats fail, log the problematic date string
    logger.warning(f"Could not parse date string: {date_str}")
    return None
