import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Date format constants
DEFAULT_DATE_FORMAT = '%m-%d-%Y %I:%M:%S %p'  # Default format: 05-21-2025 07:18:07 AM

# Supported date formats
DATE_FORMATS = [
    # Full datetime formats
    '%m-%d-%Y %I:%M:%S %p',  # 05-21-2025 07:18:07 AM (Default)
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

def clean_date_string(date_str: str) -> str:
    """Clean and standardize date string"""
    if not date_str:
        return ''
        
    # Clean the input string
    date_str = date_str.strip()
    
    # Try to handle common variations in date formats
    date_str = date_str.replace('  ', ' ')  # Remove double spaces
    date_str = date_str.replace('a.m.', 'AM').replace('p.m.', 'PM')  # Standardize AM/PM
    date_str = date_str.replace('a.m', 'AM').replace('p.m', 'PM')
    date_str = date_str.replace('am', 'AM').replace('pm', 'PM')
    
    return date_str

def parse_date(date_str: str) -> datetime:
    """Parse date string in various formats"""
    if not date_str:
        return None
        
    # Clean the input string
    date_str = clean_date_string(date_str)
    
    # Try the default format first (most common case)
    try:
        return datetime.strptime(date_str, DEFAULT_DATE_FORMAT)
    except ValueError:
        pass
    
    # If default format fails, try other formats
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
            
    # If all formats fail, log the problematic date string
    logger.warning(f"Could not parse date string: {date_str}")
    return None

def format_date(date_obj: datetime, format_str: str = None) -> str:
    """Format datetime object to string"""
    if not date_obj:
        return None
        
    if not format_str:
        format_str = DEFAULT_DATE_FORMAT
        
    try:
        return date_obj.strftime(format_str)
    except Exception as e:
        logger.error(f"Error formatting date: {str(e)}")
        return None

def is_valid_date(date_str: str) -> bool:
    """Check if string is a valid date in any supported format"""
    return parse_date(date_str) is not None 