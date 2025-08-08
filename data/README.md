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

### Using Docker (Recommended)

```bash
# Install dependencies
pip install -r requirements.txt

# Start server with PostgreSQL in Docker
python start_server_postgres.py
```

**Alternative using docker-compose:**
```bash
# Start PostgreSQL only
docker-compose up -d postgres

# Then start the API server
python start_server.py
```

### Database Management

#### Export Database
```bash
# While server is running, in another terminal:
python scripts/db_export.py

# Or using the start script:
python start_server_postgres.py --export
```

#### Import Database
```bash
# Start server first, then:
python scripts/db_import.py data/sql/export_latest.sql
```

#### Reset Database
```bash
python start_server_postgres.py --reset
```

#### Stop PostgreSQL Container
```bash
python start_server_postgres.py --stop
```

## Sharing Your Project

### To Share (with data):

1. Export your database:
   ```bash
   python scripts/db_export.py
   ```

2. Zip the project:
   ```bash
   zip -r aegis-project.zip . -x "postgres-data/*" "venv/*" "*.pyc" "__pycache__/*"
   ```

3. Send the zip file

### To Use Shared Project:

1. Unzip the project
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   # Or use the setup script:
   ./setup.sh
   ```

3. Start the server:
   ```bash
   python start_server_postgres.py
   ```
   
   The server will automatically:
   - Start PostgreSQL in Docker
   - Create the database
   - Import SQL files from `data/sql/`

## Connection Details

When the server is running, these environment variables are automatically set:
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
- **export_latest.sql**: Most recent export (auto-created)
- **pending_import.sql**: Place SQL here for import prompt on startup

## Troubleshooting

### Docker Not Running
Make sure Docker Desktop is installed and running.

### Port Already in Use
If port 5432 is busy:
```bash
python start_server_postgres.py --port 5433
```

### Database Won't Start
Reset everything:
```bash
python start_server_postgres.py --reset
```

### Container Still Running
The PostgreSQL container keeps running after the server stops (for convenience).
To stop it:
```bash
python start_server_postgres.py --stop
# Or manually:
docker stop aegis-postgres
```