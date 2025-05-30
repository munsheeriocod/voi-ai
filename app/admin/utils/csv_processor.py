import csv
import io
import logging
from typing import Dict, List, Tuple, Optional
from .validators import normalize_header, validate_csv_headers, REQUIRED_HEADERS

logger = logging.getLogger(__name__)

class CSVProcessor:
    def __init__(self, file_content: bytes):
        self.stream = io.StringIO(file_content.decode("UTF8"), newline=None)
        self.headers = None
        self.normalized_headers = None
        self.header_map = None
        
    def process_headers(self) -> Tuple[bool, List[str], Dict[str, str]]:
        """Process and validate CSV headers"""
        # Read headers
        csv_reader = csv.reader(self.stream)
        self.headers = next(csv_reader, None)
        
        if not self.headers:
            logger.error("No headers found in CSV file")
            return False, ["No headers found in CSV file"], {}
            
        # Log raw headers
        logger.info(f"CSV Headers: {self.headers}")
        
        # Normalize headers for validation
        self.normalized_headers = [normalize_header(h) for h in self.headers]
        self.header_map = {h: n for h, n in zip(self.headers, self.normalized_headers)}
        
        # Validate headers
        is_valid, errors = validate_csv_headers(self.headers)
        if not is_valid:
            logger.error(f"Header validation failed: {errors}")
        return is_valid, errors, self.header_map
        
    def get_dict_reader(self) -> csv.DictReader:
        """Get DictReader with original headers"""
        self.stream.seek(0)  # Reset stream
        next(csv.reader(self.stream))  # Skip original headers
        
        # Create DictReader with original headers
        reader = csv.DictReader(
            self.stream,
            fieldnames=self.headers,
            skipinitialspace=True,  # Skip spaces after delimiter
            strict=True  # Raise error on bad CSV
        )
        
        # Log first row to verify data
        first_row = next(reader, None)
        if first_row:
            logger.info(f"First row data: {first_row}")
            
        # Reset stream for actual processing
        self.stream.seek(0)
        next(csv.reader(self.stream))  # Skip headers again
        
        # Create a new DictReader with proper settings
        return csv.DictReader(
            self.stream,
            fieldnames=self.headers,
            skipinitialspace=True,  # Skip spaces after delimiter
            strict=True  # Raise error on bad CSV
        )
        
    def get_error_response(self, errors: List[str]) -> Dict:
        """Get standardized error response"""
        return {
            'error': 'Invalid CSV headers',
            'header_errors': errors,
            'expected_headers': list(REQUIRED_HEADERS),
            'received_headers': self.headers,
            'normalized_headers': self.normalized_headers
        } 