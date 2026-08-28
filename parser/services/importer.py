import time
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from utils.logger import logger
from utils.helpers import detect_file_type
from parsers.excel_parser import ExcelParser
from parsers.csv_parser import CSVParser
from parsers.pdf_parser import PDFParser
from mappers.header_mapper import HeaderMapper
from mappers.timetable_mapper import TimetableMapper
from validators.schema_validator import SchemaValidator
from validators.business_validator import BusinessValidator
from services.database_service import DatabaseService

class TimetableImporter:
    """ETL orchestrator coordinating modular parsing, validation, mapping, and loading pipelines."""

    def __init__(self, db_service: Optional[DatabaseService] = None):
        self.db_service = db_service or DatabaseService()

    def import_timetable(self, file_path: str, output_dir: Optional[Path] = None) -> tuple[dict[str, Any], str]:
        """Runs the complete import pipeline on a timetable file and generates reports.
        
        Args:
            file_path: Absolute path to the source file.
            output_dir: Optional path to save the TXT and JSON reports.
            
        Returns:
            A tuple (json_report_dict, txt_report_string).
        """
        start_time = time.time()
        file_path_obj = Path(file_path)
        file_name = file_path_obj.name
        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"Starting ingestion process for file: {file_name}")

        # Ingestion metrics counters
        metrics = {
            "file_name": file_name,
            "file_type": "",
            "total_records_read": 0,
            "successfully_imported_records": 0,
            "failed_records": 0,
            "duplicate_records": 0,
            "validation_errors": 0,
            "unknown_faculty": 0,
            "unknown_subjects": 0,
            "unknown_departments": 0,
            "unknown_sections": 0,
            "unknown_classrooms": 0,
            "processing_time_seconds": 0.0,
            "import_timestamp": timestamp_str
        }

        row_logs = []  # Detailed log of events for each row

        # 1. Detect file type and instantiate modular parser
        file_type = detect_file_type(file_path)
        if not file_type:
            err = f"Unsupported file extension: {file_path_obj.suffix}"
            logger.error(err)
            metrics["failed_records"] = 1
            metrics["validation_errors"] = 1
            row_logs.append({"row": 0, "errors": [err]})
            return self._generate_final_reports(metrics, row_logs, start_time, output_dir, file_path_obj)
            
        metrics["file_type"] = file_type.upper()
        
        parser_map = {
            "excel": ExcelParser,
            "csv": CSVParser,
            "pdf": PDFParser
        }
        parser = parser_map[file_type]()

        # 2. Extract raw data (Parsers only handle raw extraction)
        try:
            raw_records = parser.parse(file_path)
            metrics["total_records_read"] = len(raw_records)
            if not raw_records:
                logger.warning(f"File {file_name} was empty or contained no tables.")
                return self._generate_final_reports(metrics, row_logs, start_time, output_dir, file_path_obj)
        except Exception as e:
            err = f"File reading failed: {e}"
            logger.error(err)
            metrics["failed_records"] = 1
            metrics["validation_errors"] = 1
            row_logs.append({"row": 0, "errors": [err]})
            return self._generate_final_reports(metrics, row_logs, start_time, output_dir, file_path_obj)

        # 3. Establish DB Connection & Load caches
        try:
            self.db_service.connect()
            
            logger.info("Caching lookup tables for database mapping...")
            departments = self.db_service.fetch_departments()
            faculty = self.db_service.fetch_faculty()
            classrooms = self.db_service.fetch_classrooms()
            subjects = self.db_service.fetch_subjects()
            slots = self.db_service.fetch_slots()
            sections = self.db_service.fetch_sections()
            
            # Fetch existing bookings to prevent database double bookings in-memory
            db_fac, db_room, db_sec = self.db_service.fetch_existing_timetable_bookings()
            logger.info(f"Cached lookups successfully. (Found {len(db_fac)} existing faculty slots in DB)")
            
        except Exception as e:
            err = f"Database initialization or lookup loading failed: {e}"
            logger.error(err)
            self.db_service.close()
            metrics["failed_records"] = len(raw_records)
            metrics["validation_errors"] = 1
            row_logs.append({"row": 0, "errors": [err]})
            return self._generate_final_reports(metrics, row_logs, start_time, output_dir, file_path_obj)

        # 4. Instantiate shared pipeline components
        mapper = TimetableMapper(
            departments=departments,
            faculty=faculty,
            classrooms=classrooms,
            subjects=subjects,
            slots=slots,
            sections=sections
        )
        
        business_validator = BusinessValidator(
            departments=departments,
            faculty=faculty,
            classrooms=classrooms,
            subjects=subjects,
            slots=slots,
            sections=sections,
            db_faculty_bookings=db_fac,
            db_classroom_bookings=db_room,
            db_section_bookings=db_sec
        )

        # 5. Process records through the pipeline
        successful_inserts = 0
        failed_records = 0

        for idx, raw_row in enumerate(raw_records, start=1):
            row_errors = []
            is_row_duplicate = False
            is_val_error = False
            
            try:
                # A. Header Mapping
                mapped_row = HeaderMapper.map_headers(raw_row)
                
                missing_cols = HeaderMapper.verify_required_headers(mapped_row)
                if missing_cols:
                    is_val_error = True
                    row_errors.append(f"Missing required columns/values: {missing_cols}")
                    metrics["validation_errors"] += 1
                    raise ValueError("Column mapping failed")

                # B. Schema Validation & Type Coercion (Data Cleaning & Normalization)
                validated_row, schema_errors = SchemaValidator.validate_row(mapped_row)
                if schema_errors:
                    is_val_error = True
                    row_errors.extend(schema_errors)
                    metrics["validation_errors"] += len(schema_errors)
                    raise ValueError("Schema validation failed")

                # C. Business Validation - Part 1: Referential Integrity
                is_valid_ref, ref_errors = business_validator.validate_referential_integrity(validated_row)
                if not is_valid_ref:
                    row_errors.extend(ref_errors)
                    for err_msg in ref_errors:
                        if "Unknown Faculty" in err_msg:
                            metrics["unknown_faculty"] += 1
                        elif "Unknown Subject" in err_msg:
                            metrics["unknown_subjects"] += 1
                        elif "Unknown Department" in err_msg:
                            metrics["unknown_departments"] += 1
                        elif "Unknown Section" in err_msg:
                            metrics["unknown_sections"] += 1
                        elif "Unknown Classroom" in err_msg:
                            metrics["unknown_classrooms"] += 1
                        else:
                            metrics["validation_errors"] += 1
                    raise ValueError("Referential integrity check failed")

                # D. Business Validation - Part 2: File duplicates checking
                is_valid_dup, dup_errors = business_validator.validate_file_duplicates(validated_row)
                if not is_valid_dup:
                    is_row_duplicate = True
                    row_errors.extend(dup_errors)
                    metrics["duplicate_records"] += len(dup_errors)
                    raise ValueError("File double-booking detected")

                # E. Database ID Resolution
                db_record = mapper.map_to_db_record(validated_row)
                if not db_record:
                    is_val_error = True
                    row_errors.append("Mapping error: unable to resolve database primary key IDs.")
                    metrics["validation_errors"] += 1
                    raise ValueError("ID resolution failed")

                # F. Duplicate Detection (checks against existing DB records cached in-memory)
                db_dup_errors = business_validator.detect_db_duplicates(db_record)
                if db_dup_errors:
                    is_row_duplicate = True
                    row_errors.extend(db_dup_errors)
                    metrics["duplicate_records"] += len(db_dup_errors)
                    raise ValueError("Database duplicate check failed")

                # G. PostgreSQL savepoint-contained Insertion
                success, insert_msg = self.db_service.insert_timetable_record(db_record)
                if not success:
                    if "Duplicate" in insert_msg:
                        is_row_duplicate = True
                        metrics["duplicate_records"] += 1
                    else:
                        is_val_error = True
                        metrics["validation_errors"] += 1
                    row_errors.append(insert_msg)
                    raise ValueError("PostgreSQL insertion failed")

                # H. Register booking in-memory if successfully written to the session
                business_validator.register_successful_booking(db_record)
                successful_inserts += 1

            except Exception:
                failed_records += 1
                row_logs.append({
                    "row": idx,
                    "original_data": raw_row,
                    "is_duplicate": is_row_duplicate,
                    "is_validation_error": is_val_error,
                    "errors": row_errors
                })

        # 6. Finalize transaction blocks
        try:
            if successful_inserts > 0:
                self.db_service.commit()
            else:
                self.db_service.rollback()
        except Exception as e:
            err = f"Transaction commit failed: {e}"
            logger.error(err)
            self.db_service.rollback()
            row_logs.append({"row": 0, "errors": [err]})
            failed_records = len(raw_records)
            successful_inserts = 0
        finally:
            self.db_service.close()

        # Update metrics
        metrics["successfully_imported_records"] = successful_inserts
        metrics["failed_records"] = failed_records

        return self._generate_final_reports(metrics, row_logs, start_time, output_dir, file_path_obj)

    def _generate_final_reports(
        self, 
        metrics: dict[str, Any], 
        row_logs: list[dict[str, Any]], 
        start_time: float, 
        output_dir: Optional[Path], 
        file_path_obj: Path
    ) -> tuple[dict[str, Any], str]:
        """Generates JSON and human-readable text reports, saving them to disk if requested."""
        metrics["processing_time_seconds"] = round(time.time() - start_time, 3)

        # JSON Report Object
        json_report = {
            "summary": metrics,
            "failed_rows_details": row_logs
        }

        # Human-Readable Text Report String
        txt_report = self._build_txt_report_string(metrics, row_logs)

        # Save to file if output directory is defined
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            timestamp_suffix = int(time.time())
            stem = file_path_obj.stem
            
            # Save JSON report
            json_file = output_dir / f"import_report_{stem}_{timestamp_suffix}.json"
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(json_report, f, indent=4)
                
            # Save TXT report
            txt_file = output_dir / f"import_report_{stem}_{timestamp_suffix}.txt"
            with open(txt_file, "w", encoding="utf-8") as f:
                f.write(txt_report)
                
            logger.info(f"Import reports written to disk: JSON={json_file.name}, TXT={txt_file.name}")

        return json_report, txt_report

    def _build_txt_report_string(self, metrics: dict[str, Any], row_logs: list[dict[str, Any]]) -> str:
        """Constructs a clean human-readable textual report."""
        divider = "=" * 65
        sub_divider = "-" * 65
        
        txt = []
        txt.append(divider)
        txt.append("CAMPUSFLOW AI - TIMETABLE IMPORT SUMMARY REPORT")
        txt.append(divider)
        txt.append(f"File Name:                      {metrics['file_name']}")
        txt.append(f"File Type:                      {metrics['file_type']}")
        txt.append(f"Import Timestamp:               {metrics['import_timestamp']}")
        txt.append(f"Total Records Read:             {metrics['total_records_read']}")
        txt.append(f"Successfully Imported:          {metrics['successfully_imported_records']}")
        txt.append(f"Failed/Skipped Records:         {metrics['failed_records']}")
        txt.append(f"Processing Time (seconds):      {metrics['processing_time_seconds']}")
        txt.append(sub_divider)
        txt.append("DETAILED METRIC BREAKDOWN:")
        txt.append(f"  - Duplicate Records:          {metrics['duplicate_records']}")
        txt.append(f"  - Validation Errors:          {metrics['validation_errors']}")
        txt.append(f"  - Unknown Faculty:            {metrics['unknown_faculty']}")
        txt.append(f"  - Unknown Subjects:           {metrics['unknown_subjects']}")
        txt.append(f"  - Unknown Departments:        {metrics['unknown_departments']}")
        txt.append(f"  - Unknown Sections:           {metrics['unknown_sections']}")
        txt.append(f"  - Unknown Classrooms:         {metrics['unknown_classrooms']}")
        txt.append(divider)
        
        if row_logs:
            txt.append("\nFAILED ROWS DETAILS AND AUDIT LOGS:")
            txt.append(sub_divider)
            for log in row_logs:
                row_num = log.get("row", "System")
                err_list = log.get("errors", [])
                orig = log.get("original_data", {})
                
                txt.append(f"Row {row_num}:")
                txt.append(f"  Original Data: {orig}")
                txt.append(f"  Errors Details:")
                for err in err_list:
                    txt.append(f"    * {err}")
                txt.append(sub_divider)
        else:
            txt.append("\nClean Import: No validation or database insertion failures recorded.")
            txt.append(sub_divider)
            
        return "\n".join(txt)
