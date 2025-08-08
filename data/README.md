# AEGIS Database Setup

This directory contains database-related files for the AEGIS project.

## Directory Structure

```
data/
├── sql/
│   ├── schema.sql         # Core database schema
│   ├── sample_data.sql    # Sample data for development
│   ├── export_*.sql       # Database exports (timestamped)
│   └── export_latest.sql  # Most recent export
└── README.md
```

## Quick Start

### 1. Start Server with Embedded PostgreSQL

```bash
# Install dependencies
pip install -r requirements.txt

# Start server with database
python start_server_with_db.py
```

This will:
- Download and start PostgreSQL locally (no installation needed)
- Create the database if it doesn't exist
- Import `schema.sql` and `sample_data.sql` on first run
- Start the FastAPI server

### 2. Database Management

#### Export Database
```bash
# While server is running, in another terminal:
python scripts/db_export.py
```

#### Import Database
```bash
# Start server first, then:
python scripts/db_import.py data/sql/export_latest.sql
```

#### Reset Database
```bash
python start_server_with_db.py --reset
```

## Sharing Your Project

### To Share (with data):

1. Export your database:
   ```bash
   python scripts/db_export.py
   ```

2. Zip the project:
   ```bash
   zip -r aegis-project.zip . -x "postgres-data/*" ".pg_embedded/*" "venv/*" "*.pyc"
   ```

3. Send the zip file

### To Use Shared Project:

1. Unzip the project
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Start the server:
   ```bash
   python start_server_with_db.py
   ```
   
   The server will automatically:
   - Download PostgreSQL if needed
   - Create the database
   - Import any SQL files found in `data/sql/`

## Connection Details

When the server is running, these environment variables are set:
- `VECTOR_POSTGRES_DB_HOST`: localhost
- `VECTOR_POSTGRES_DB_PORT`: 5432
- `VECTOR_POSTGRES_DB_NAME`: aegis_dev
- `DB_USERNAME`: aegis_user
- `DB_PASSWORD`: aegis_dev_password

Your existing `db_config.py` will automatically use these.

## SQL Files

- **schema.sql**: Database structure (tables, indexes, triggers)
- **sample_data.sql**: Example data for testing
- **export_*.sql**: Your exported data (timestamped)
- **pending_import.sql**: Place here for auto-import prompt

## Troubleshooting

### Port Already in Use
If port 5432 is busy, use a different port:
```bash
python start_server_with_db.py --port 5433
```

### Database Won't Start
Try resetting:
```bash
python start_server_with_db.py --reset
```

### Can't Find pg_dump/psql
The scripts will use the embedded PostgreSQL tools automatically. If issues persist, the tools are located in `.pg_embedded/bin/`