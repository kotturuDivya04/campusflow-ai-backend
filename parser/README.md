# CampusFlow AI - Parser Module

This is the self-contained Parser Module for **CampusFlow AI**, a campus coordination system. It parses university timetable spreadsheets (`.xlsx`, `.csv`) and PDF schedules (`.pdf`), cleans, validates, and loads them into a PostgreSQL database.

---

## Features

- **Multi-format Support:** Native parsers for Excel, CSV, and PDF timetable grids.
- **Intelligent Header mapping:** Standardizes arbitrary column names (e.g. "Instructor", "Teacher" -> "faculty_name") using synonym matching.
- **Pydantic Validation:** Checks schemas, data types, and enum values.
- **Business Checks:** Flags database referential errors and double-bookings within files.
- **Transaction Safety:** Uses database savepoints to skip invalid entries and import valid ones.
- **Import Summary Report:** Outputs run summaries and error tables to JSON files.

---

## Setup Instructions

### Prerequisites
- Python 3.10+
- Access to the PostgreSQL database container (see [Database Module README](../database/README.md)).

### Local Installation
1. Install the required python packages:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure environment variables. The parser uses the same settings as the database module. Create a `.env` file in the `parser/` folder or export variables:
   ```env
   POSTGRES_USER=campusflow_admin
   POSTGRES_PASSWORD=campusflow_secure_password_2026
   POSTGRES_DB=campusflow_db
   POSTGRES_PORT=5432
   DB_HOST=localhost
   ```

---

## Running the Parser via CLI

Run the parser by passing the path of the timetable file:

```bash
# Run on an Excel timetable
python main.py uploads/timetable_cs_fall.xlsx

# Run on a CSV timetable
python main.py uploads/timetable_ee_fall.csv

# Run on a PDF timetable
python main.py uploads/timetable_me_fall.pdf
```

The script will print a summary to the console and save the detailed JSON validation report in the `output/` directory (e.g., `output/import_report_timetable_cs_fall_1718302821.json`).

---

## Docker Execution

To run the parser inside a Docker container:

1. **Build the Docker Image:**
   ```bash
   docker build -t campusflow-parser .
   ```

2. **Run the Ingestion Command:**
   Mount your local `uploads` and `output` folders and pass the file target:
   ```bash
   docker run --rm \
     --network host \
     -v "$(pwd)/uploads:/app/uploads" \
     -v "$(pwd)/output:/app/output" \
     --env-file .env \
     campusflow-parser uploads/timetable_cs_fall.xlsx
   ```
   *(Note: `--network host` allows the container to talk to a database running on `localhost:5432`)*
