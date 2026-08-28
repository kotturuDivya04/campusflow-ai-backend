import argparse
import sys
from pathlib import Path
from utils.logger import logger
from services.importer import TimetableImporter
from config import DEFAULT_OUTPUT_DIR

def main():
    """Main CLI entrypoint for running the CampusFlow AI timetable parser."""
    parser = argparse.ArgumentParser(
        description="CampusFlow AI Timetable Ingestion and Parser CLI Tool"
    )
    parser.add_argument(
        "file_path",
        type=str,
        help="Path to the timetable spreadsheet (.xlsx, .csv) or PDF (.pdf) file to import"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory where the JSON and TXT import reports will be written"
    )
    
    args = parser.parse_args()
    
    file_path = Path(args.file_path)
    output_dir = Path(args.output_dir)
    
    if not file_path.exists():
        logger.error(f"Target file does not exist: {file_path}")
        sys.exit(1)
        
    logger.info("Initializing TimetableImporter...")
    importer = TimetableImporter()
    
    try:
        # Run import and output dual reports
        json_report, txt_report = importer.import_timetable(
            file_path=str(file_path.resolve()),
            output_dir=output_dir
        )
        
        # Display the human-readable text report directly in the console
        print(txt_report)
        
        if json_report["summary"]["status"] == "Failed":
            sys.exit(2)
            
    except Exception as e:
        logger.error(f"Critical execution error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
