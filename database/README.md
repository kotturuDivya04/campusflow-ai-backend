# CampusFlow AI - Database Module

This is the complete, self-contained database module for **CampusFlow AI**, a campus coordination platform designed to optimize higher education operations. The database is built on **PostgreSQL 15** and fully containerized with **Docker** for quick deployment, local development, and CI/CD integration.

---

## Folder Structure

```text
database/
├── Dockerfile                  # Builds PostgreSQL 15 image with extensions
├── docker-entrypoint-initdb.d/ # Auto-run scripts on container startup
│   ├── init.sql                # Enables extensions & configures system vars (runs 1st)
│   ├── schema.sql              # Complete 3NF-compliant DDL schema (runs 2nd)
│   └── seed.sql                # Comprehensive test seed dataset (runs 3rd)
├── README.md                   # Setup and usage guide (this file)
├── database_design.md          # Architectural and table-level documentation
├── .env.example                # Template for environment configuration
├── diagrams/
│   ├── er_diagram.drawio       # Entity-Relationship diagram in Draw.io format
│   └── er_diagram.png          # High-resolution export of the ER diagram
└── sample_data/                # Raw CSV records for testing future import parsers
    ├── departments.csv
    ├── faculty.csv
    ├── students.csv
    ├── timetable.csv
    ├── requests.csv
    ├── clubs.csv
    └── events.csv
```

---

## Prerequisites

- **Docker** and **Docker Compose** installed on your system.
- A database client (e.g., pgAdmin, DBeaver, or command line `psql`) to connect locally.

---

## Spin Up the Database

1. **Configure Environment Variables:**
   Copy the example environment configuration to create your local `.env` file:
   ```bash
   cp .env.example .env
   ```
   *(On Windows PowerShell: `Copy-Item .env.example .env`)*

2. **Build and Run the Container:**
   You can spin up the container using Docker Compose (if you configure a `docker-compose.yml`) or directly using Docker:
   ```bash
   # Build the custom PostgreSQL image
   docker build -t campusflow-db .
   
   # Run the container mapping port 5432
   docker run -d \
     --name campusflow-postgres-container \
     -p 5432:5432 \
     --env-file .env \
     campusflow-db
   ```

3. **Verify Initialization Logs:**
   PostgreSQL automatically executes the `.sql` scripts inside `docker-entrypoint-initdb.d/` in alphabetical order:
   - `init.sql` runs first to initialize database variables and enable system extensions (`uuid-ossp`, `pg_trgm`, `btree_gist`).
   - `schema.sql` creates all 26 tables, primary keys, foreign keys, unique constraints, and performance-optimizing indexes.
   - `seed.sql` populates the database with realistic test data (faculty members, students, departments, a weekly class timetable, club bookings, approval histories, audit records, and AI chat logs).

   To monitor the execution, run:
   ```bash
   docker logs campusflow-postgres-container
   ```
   Look for the output:
   `Initializing CampusFlow AI Database...`

---

## Connection Settings

To connect to the database from your FastAPI backend, database GUI, or command-line scripts:

- **Host:** `localhost` (or `db_host` if running inside a Docker network)
- **Port:** `5432`
- **Database:** `campusflow_db` (from `.env` - default: `campusflow_db`)
- **Username:** `campusflow_admin` (from `.env` - default: `campusflow_admin`)
- **Password:** `campusflow_secure_password_2026` (from `.env` - default: `campusflow_secure_password_2026`)

### Example: Connect via psql
If you have `psql` installed locally:
```bash
psql -h localhost -U campusflow_admin -d campusflow_db
```

---

## Core Database Safeguards

The database schema utilizes strict relational constraints to enforce operational integrity directly at the storage level:
- **Double-booking Prevention:**
  - Faculty cannot be assigned to two classes in the same slot on the same day (`uq_timetable_faculty`).
  - Classrooms cannot be double-booked for two sessions in the same slot on the same day (`uq_timetable_classroom`).
  - Student sections cannot have two different classes scheduled in the same slot on the same day (`uq_timetable_section`).
- **Orphan Prevention:** Standard cascading policies (`ON DELETE CASCADE`, `ON DELETE RESTRICT`, `ON DELETE SET NULL`) prevent broken links across academic units.
- **Workflow Integrity:** The `approvals` table uses a checksum constraint to guarantee that approvals are mapped exclusively to exactly one source transaction (Department Requests, Events, or Venue Bookings).
