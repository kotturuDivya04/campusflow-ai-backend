import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_UPLOAD_DIR = BASE_DIR / "uploads"
DEFAULT_OUTPUT_DIR = BASE_DIR / "output"
DEFAULT_LOG_DIR = BASE_DIR / "logs"

# Ensure runtime directories exist
DEFAULT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_LOG_DIR.mkdir(parents=True, exist_ok=True)

# Database Configuration
DB_USER = os.getenv("POSTGRES_USER", "campusflow_admin")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "campusflow_secure_password_2026")
DB_NAME = os.getenv("POSTGRES_DB", "campusflow_db")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_HOST = os.getenv("DB_HOST", "localhost")

# Build connection string for psycopg2
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# App Configuration
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE_PATH = DEFAULT_LOG_DIR / "parser.log"

# Define validation settings
MAX_VALIDATION_ERRORS_RETAINED = 500
