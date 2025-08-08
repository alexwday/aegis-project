#!/usr/bin/env python3
"""
Start AEGIS server using local PostgreSQL installation.
For users who have PostgreSQL already installed and running.
"""

import uvicorn
import sys
import os
import subprocess
from pathlib import Path
import psycopg2
from psycopg2 import sql

# Add the services package to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class LocalPostgresSetup:
    """Setup local PostgreSQL database (requires PostgreSQL to be installed)."""
    
    def __init__(self, 
                 host: str = "localhost",
                 port: int = 5432,
                 database: str = "aegis_dev",
                 user: str = None,
                 password: str = None):
        self.host = host
        self.port = port
        self.database = database
        # Use current system user if not specified
        self.user = user or os.environ.get("USER", "postgres")
        self.password = password or ""
        self.sql_dir = Path("./data/sql")
        
    def setup(self) -> bool:
        """Setup the database, creating it if needed."""
        print(f"🐘 Setting up local PostgreSQL database '{self.database}'...")
        
        # First try to connect to the target database
        if self._test_connection():
            print(f"✅ Connected to existing database '{self.database}'")
            self._check_and_initialize()
            self._set_environment_variables()
            return True
            
        # If that fails, try to create the database
        if self._create_database():
            print(f"✅ Created new database '{self.database}'")
            self._initialize_database()
            self._set_environment_variables()
            return True
            
        print("❌ Could not connect to PostgreSQL. Please ensure:")
        print("   1. PostgreSQL is installed and running")
        print("   2. You have the correct permissions")
        print(f"   3. Connection details are correct (host={self.host}, port={self.port})")
        return False
        
    def _test_connection(self) -> bool:
        """Test if we can connect to the database."""
        try:
            conn_string = self._get_connection_string(self.database)
            conn = psycopg2.connect(conn_string)
            conn.close()
            return True
        except:
            return False
            
    def _create_database(self) -> bool:
        """Create the database if it doesn't exist."""
        try:
            # Connect to default postgres database to create our database
            conn_string = self._get_connection_string("postgres")
            conn = psycopg2.connect(conn_string)
            conn.autocommit = True
            cursor = conn.cursor()
            
            # Check if database exists
            cursor.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (self.database,)
            )
            
            if cursor.fetchone():
                cursor.close()
                conn.close()
                return True  # Database already exists
                
            # Create database
            cursor.execute(
                sql.SQL("CREATE DATABASE {}").format(
                    sql.Identifier(self.database)
                )
            )
            
            cursor.close()
            conn.close()
            print(f"✅ Created database '{self.database}'")
            return True
            
        except Exception as e:
            print(f"⚠️  Could not create database: {e}")
            return False
            
    def _check_and_initialize(self):
        """Check if database needs initialization."""
        try:
            conn_string = self._get_connection_string(self.database)
            conn = psycopg2.connect(conn_string)
            cursor = conn.cursor()
            
            # Check if we have any tables
            cursor.execute("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            
            table_count = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            
            if table_count == 0:
                print("📝 Empty database detected, initializing...")
                self._initialize_database()
            else:
                print(f"📊 Found {table_count} existing tables")
                self._check_for_imports()
                
        except Exception as e:
            print(f"⚠️  Could not check database: {e}")
            
    def _initialize_database(self):
        """Initialize database with schema and sample data."""
        if not self.sql_dir.exists():
            print("⚠️  No SQL directory found at data/sql/")
            return
            
        # Import schema
        schema_file = self.sql_dir / "schema.sql"
        if schema_file.exists():
            print("📝 Importing schema...")
            if self._import_sql_file(schema_file):
                print("✅ Schema imported")
                
        # Import sample data
        for data_file in ["sample_data.sql", "initial_data.sql"]:
            data_path = self.sql_dir / data_file
            if data_path.exists():
                print(f"📥 Importing {data_file}...")
                if self._import_sql_file(data_path):
                    print(f"✅ {data_file} imported")
                break
                
    def _check_for_imports(self):
        """Check for pending imports."""
        if not self.sql_dir.exists():
            return
            
        pending = self.sql_dir / "pending_import.sql"
        if pending.exists():
            response = input("📦 Found pending_import.sql. Import now? (y/n): ")
            if response.lower() == 'y':
                if self._import_sql_file(pending):
                    import time
                    pending.rename(self.sql_dir / f"imported_{time.strftime('%Y%m%d_%H%M%S')}.sql")
                    print("✅ Import complete")
                    
    def _import_sql_file(self, file_path: Path) -> bool:
        """Import SQL file into database."""
        try:
            conn_string = self._get_connection_string(self.database)
            conn = psycopg2.connect(conn_string)
            conn.autocommit = True
            cursor = conn.cursor()
            
            with open(file_path, 'r') as f:
                sql_content = f.read()
                
            cursor.execute(sql_content)
            cursor.close()
            conn.close()
            return True
            
        except Exception as e:
            print(f"⚠️  Error importing SQL: {e}")
            return False
            
    def _get_connection_string(self, database: str) -> str:
        """Get connection string for psycopg2."""
        parts = [
            f"host={self.host}",
            f"port={self.port}",
            f"dbname={database}",
            f"user={self.user}"
        ]
        if self.password:
            parts.append(f"password={self.password}")
        return " ".join(parts)
        
    def _set_environment_variables(self):
        """Set environment variables for the application."""
        os.environ["VECTOR_POSTGRES_DB_HOST"] = self.host
        os.environ["VECTOR_POSTGRES_DB_PORT"] = str(self.port)
        os.environ["VECTOR_POSTGRES_DB_NAME"] = self.database
        os.environ["DB_USERNAME"] = self.user
        os.environ["DB_PASSWORD"] = self.password
        
        # SQLAlchemy connection string
        if self.password:
            os.environ["DATABASE_URL"] = f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
        else:
            os.environ["DATABASE_URL"] = f"postgresql://{self.user}@{self.host}:{self.port}/{self.database}"
            
        print("🔧 Environment variables configured")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Start AEGIS server with local PostgreSQL")
    parser.add_argument("--host", default="localhost", help="PostgreSQL host")
    parser.add_argument("--port", type=int, default=5432, help="PostgreSQL port")
    parser.add_argument("--user", help="PostgreSQL user (default: current system user)")
    parser.add_argument("--password", help="PostgreSQL password")
    parser.add_argument("--database", default="aegis_dev", help="Database name")
    parser.add_argument("--api-port", type=int, default=8000, help="FastAPI port")
    parser.add_argument("--no-db", action="store_true", help="Skip database setup")
    
    args = parser.parse_args()
    
    # Setup database if not disabled
    if not args.no_db:
        pg_setup = LocalPostgresSetup(
            host=args.host,
            port=args.port,
            database=args.database,
            user=args.user,
            password=args.password
        )
        
        if not pg_setup.setup():
            print("\n💡 Tips:")
            print("   - If PostgreSQL is not installed: Use 'python start_server_postgres.py' (requires Docker)")
            print("   - If using different credentials: Add --user and --password flags")
            print("   - If PostgreSQL is on different port: Add --port flag")
            return
            
        print("\n" + "="*60)
        
    # Start FastAPI server
    print("🚀 Starting AEGIS FastAPI Server...")
    print(f"📱 Chat Interface: Open chat_interface.html in your browser")
    print(f"📋 API Docs: http://localhost:{args.api_port}/docs")
    print(f"🔍 Health Check: http://localhost:{args.api_port}/health")
    
    if not args.no_db:
        print(f"\n📊 Using PostgreSQL at {args.host}:{args.port}/{args.database}")
        
    print("\n🛑 Press Ctrl+C to stop the server\n")
    print("="*60 + "\n")
    
    uvicorn.run(
        "services.src.api:app",
        host="0.0.0.0",
        port=args.api_port,
        reload=True,
        log_level="info"
    )


if __name__ == "__main__":
    main()