import pandas as pd
from typing import Any
from parsers.base_parser import BaseParser
from utils.constants import HEADER_SYNONYMS
from utils.logger import logger

class CSVParser(BaseParser):
    """Concrete parser implementation for reading CSV (.csv) files."""
    
    def parse(self, file_path: str) -> list[dict[str, Any]]:
        """Parses a CSV file, automatically detecting the header row if leading rows exist."""
        logger.info(f"Starting CSV parsing for file: {file_path}")
        
        try:
            # Load raw file without assuming header position
            df_raw = pd.read_csv(file_path, header=None)
        except Exception as e:
            logger.error(f"Failed to read CSV file structure: {e}")
            raise ValueError(f"Invalid CSV format or file corrupted: {e}")
            
        if df_raw.empty:
            logger.warning(f"CSV file is empty: {file_path}")
            return []
            
        header_idx = self._detect_header_row(df_raw)
        logger.info(f"Detected header row index: {header_idx}")
        
        # Reload the sheet using detected header row
        try:
            df = pd.read_csv(file_path, header=header_idx)
        except Exception as e:
            logger.error(f"Failed to reload CSV file with header at row {header_idx}: {e}")
            raise ValueError(f"Error parsing CSV rows: {e}")
            
        # Clean columns and convert records to list of dicts
        df = df.dropna(how='all') # Drop completely empty rows
        
        # Replace NaN values with None
        df = df.where(pd.notnull(df), None)
        
        records = df.to_dict(orient="records")
        logger.info(f"Extracted {len(records)} raw records from CSV.")
        return records
        
    def _detect_header_row(self, df: pd.DataFrame) -> int:
        """Inspects the first 10 rows to find which row matches the highest number of column synonyms."""
        best_row_idx = 0
        max_matches = 0
        
        # Scan up to 10 rows or total rows
        scan_limit = min(10, len(df))
        
        for idx in range(scan_limit):
            row = df.iloc[idx].dropna().astype(str).tolist()
            matches = 0
            
            for cell in row:
                cell_clean = cell.strip().lower()
                # Check if cell matches any synonym list in HEADER_SYNONYMS
                for synonyms in HEADER_SYNONYMS.values():
                    if cell_clean in synonyms:
                        matches += 1
                        break
            
            if matches > max_matches:
                max_matches = matches
                best_row_idx = idx
                
        # If no synonyms match, default to first row (index 0)
        if max_matches < 2:
            logger.warning("Could not reliably identify header row using synonyms. Defaulting to first row.")
            return 0
            
        return best_row_idx
