import pdfplumber
from typing import Any
from parsers.base_parser import BaseParser
from utils.constants import HEADER_SYNONYMS
from utils.logger import logger
from utils.helpers import clean_string

class PDFParser(BaseParser):
    """Concrete parser implementation for reading and extracting tables from PDF files."""
    
    def parse(self, file_path: str) -> list[dict[str, Any]]:
        """Parses a PDF document, extracting tables and mapping headers dynamically."""
        logger.info(f"Starting PDF parsing for file: {file_path}")
        
        raw_tables = []
        try:
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    tables = page.extract_tables()
                    logger.info(f"Page {page_num}: Found {len(tables)} table(s)")
                    for t in tables:
                        if t:
                            raw_tables.append(t)
        except Exception as e:
            logger.error(f"Failed to read PDF file structures: {e}")
            raise ValueError(f"Invalid PDF layout or file corrupted: {e}")
            
        if not raw_tables:
            logger.warning(f"No tables detected in PDF: {file_path}")
            return []
            
        all_records = []
        
        # Process each extracted table grid
        for table_idx, table in enumerate(raw_tables):
            if len(table) < 2:
                # Need at least a header row and one data row
                continue
                
            header_idx = self._detect_header_row(table)
            logger.info(f"Table {table_idx}: Detected header row index: {header_idx}")
            
            raw_headers = table[header_idx]
            # Replace None headers or duplicate empty headers with placeholder strings
            headers = []
            for col_idx, h in enumerate(raw_headers):
                h_clean = clean_string(h)
                if not h_clean:
                    headers.append(f"column_{col_idx}")
                else:
                    headers.append(h_clean)
                    
            # Parse data rows (everything after the header row)
            # Apply merged cell interpolation (carrying values forward)
            previous_row = [None] * len(headers)
            
            for row_idx in range(header_idx + 1, len(table)):
                row = table[row_idx]
                
                # Ensure row has same length as headers
                if len(row) < len(headers):
                    row = row + [None] * (len(headers) - len(row))
                elif len(row) > len(headers):
                    row = row[:len(headers)]
                    
                record = {}
                cleaned_row = []
                
                for col_idx, cell in enumerate(row):
                    cell_val = clean_string(cell)
                    
                    # Merged cell interpolation:
                    # If cell is empty, and we have a valid value from the previous row in the same column,
                    # AND we believe this column represents grouped variables (like Day or Section), carry it down.
                    # For a timetable, the 'Day' or 'Section' columns are often merged vertically.
                    if not cell_val and previous_row[col_idx]:
                        # Check header to see if it is a commonly merged column (Day, Section, Semester, Year)
                        header_lower = headers[col_idx].lower()
                        is_merged_col = any(
                            syn in header_lower for key in ["day_of_week", "section_name", "academic_year", "semester"] 
                            for syn in HEADER_SYNONYMS[key]
                        )
                        if is_merged_col:
                            cell_val = previous_row[col_idx]
                            
                    cleaned_row.append(cell_val if cell_val else None)
                    record[headers[col_idx]] = cell_val if cell_val else None
                    
                previous_row = cleaned_row
                
                # Filter out completely empty or meta records
                non_empty_count = sum(1 for val in record.values() if val)
                if non_empty_count > 1:
                    all_records.append(record)
                    
        logger.info(f"Extracted {len(all_records)} raw records from PDF tables.")
        return all_records
        
    def _detect_header_row(self, table: list[list[str]]) -> int:
        """Finds which row in the table contains the highest count of header synonyms."""
        best_row_idx = 0
        max_matches = 0
        
        # Scan first 5 rows of the table
        scan_limit = min(5, len(table))
        
        for idx in range(scan_limit):
            row = table[idx]
            matches = 0
            
            for cell in row:
                cell_clean = clean_string(cell).lower()
                for synonyms in HEADER_SYNONYMS.values():
                    if cell_clean in synonyms:
                        matches += 1
                        break
                        
            if matches > max_matches:
                max_matches = matches
                best_row_idx = idx
                
        return best_row_idx
