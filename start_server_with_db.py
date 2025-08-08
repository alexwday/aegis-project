#!/usr/bin/env python3
"""
Enhanced AEGIS server starter with embedded PostgreSQL support.
This script starts a local PostgreSQL instance and the FastAPI server.
"""

import uvicorn
import sys
import os
import time
import signal
import atexit
import subprocess
from pathlib import Path
from typing import Optional
import psutil
import pg_embedded

# Add the services package to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class EmbeddedPostgresManager:
    """Manages embedded PostgreSQL instance for development."""
    
    def __init__(self, 
                 version: str = "15.3",
                 port: int = 5432,
                 data_dir: str = "./postgres-data",
                 database: str = "aegis_dev",
                 user: str = "aegis_user",
                 password: str = "aegis_dev_password"):
        self.version = version
        self.port = port
        self.data_dir = Path(data_dir)
        self.database = database
        self.user = user
        self.password = password
        self.pg = None
        self.initialized_flag = self.data_dir / ".initialized"
        
    def check_port_available(self) -> bool:
        """Check if the PostgreSQL port is available."""
        for conn in psutil.net_connections():
            if conn.laddr.port == self.port and conn.status == 'LISTEN':
                return False
        return True
        
    def start(self) -> bool:
        """Start the embedded PostgreSQL instance."""
        print(f"🐘 Starting embedded PostgreSQL {self.version}...")
        
        # Check if port is available
        if not self.check_port_available():
            print(f"❌ Port {self.port} is already in use. Please stop any existing PostgreSQL instances.")
            return False
        
        # Ensure data directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Initialize PostgreSQL instance
            self.pg = pg_embedded.PostgreSQL(
                version=self.version,
                port=self.port,
                data_dir=str(self.data_dir),
                log_file=str(self.data_dir / "postgresql.log"),
                user=self.user,
                password=self.password,
                configuration={
                    "shared_buffers": "128MB",
                    "max_connections": "100",
                    "log_statement": "all",
                    "log_destination": "stderr",
                    "logging_collector": "on",
                    "log_directory": "log",
                    "log_filename": "postgresql-%Y-%m-%d_%H%M%S.log"
                }
            )
            
            # Start PostgreSQL
            self.pg.start()
            print(f"✅ PostgreSQL started on port {self.port}")
            
            # Initialize database if needed
            if not self.initialized_flag.exists():
                self._initialize_database()
            else:
                print("📊 Using existing database")
                self._check_and_import_new_dumps()
            
            # Set environment variables for the application
            self._set_environment_variables()
            
            # Register cleanup on exit
            atexit.register(self.stop)
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to start PostgreSQL: {e}")
            if self.data_dir.exists() and not any(self.data_dir.iterdir()):
                print("💡 Hint: Try removing the empty postgres-data directory and retry")
            return False
    
    def _initialize_database(self):
        """Initialize the database with schema and optional data."""
        print("🔄 Initializing database...")
        
        try:
            # Create the main database
            self.pg.create_database(self.database)
            print(f"✅ Created database '{self.database}'")
            
            # Look for SQL initialization files
            sql_dir = Path("data/sql")
            if sql_dir.exists():
                # Import schema first
                schema_file = sql_dir / "schema.sql"
                if schema_file.exists():
                    print(f"📝 Importing schema from {schema_file}...")
                    self._execute_sql_file(schema_file)
                    print("✅ Schema imported")
                
                # Import initial data
                for data_file in ["initial_data.sql", "sample_data.sql", "import.sql"]:
                    data_path = sql_dir / data_file
                    if data_path.exists():
                        print(f"📥 Importing data from {data_file}...")
                        self._execute_sql_file(data_path)
                        print(f"✅ Data imported from {data_file}")
                        break
            
            # Mark as initialized
            self.initialized_flag.touch()
            print("✅ Database initialization complete")
            
        except Exception as e:
            print(f"❌ Database initialization failed: {e}")
            raise
    
    def _check_and_import_new_dumps(self):
        """Check for new SQL dumps to import."""
        sql_dir = Path("data/sql")
        pending_import = sql_dir / "pending_import.sql"
        
        if pending_import.exists():
            response = input("📦 Found pending_import.sql. Import it now? (y/n): ")
            if response.lower() == 'y':
                print("📥 Importing pending data...")
                self._execute_sql_file(pending_import)
                # Rename file after successful import
                pending_import.rename(sql_dir / f"imported_{time.strftime('%Y%m%d_%H%M%S')}.sql")
                print("✅ Data imported successfully")
    
    def _execute_sql_file(self, file_path: Path):
        """Execute SQL commands from a file."""
        import psycopg2
        
        conn_string = f"postgresql://{self.user}:{self.password}@localhost:{self.port}/{self.database}"
        conn = psycopg2.connect(conn_string)
        conn.autocommit = True
        
        with open(file_path, 'r') as f:
            sql = f.read()
            
        with conn.cursor() as cursor:
            cursor.execute(sql)
        
        conn.close()
    
    def _set_environment_variables(self):
        """Set environment variables for the application to use."""
        os.environ["VECTOR_POSTGRES_DB_HOST"] = "localhost"
        os.environ["VECTOR_POSTGRES_DB_PORT"] = str(self.port)
        os.environ["VECTOR_POSTGRES_DB_NAME"] = self.database
        os.environ["DB_USERNAME"] = self.user
        os.environ["DB_PASSWORD"] = self.password
        
        # Also set a DATABASE_URL for convenience
        os.environ["DATABASE_URL"] = f"postgresql://{self.user}:{self.password}@localhost:{self.port}/{self.database}"
        
        print("🔧 Environment variables set for database connection")
    
    def stop(self):
        """Stop the embedded PostgreSQL instance."""
        if self.pg:
            print("\n🛑 Stopping PostgreSQL...")
            try:
                self.pg.stop()
                print("✅ PostgreSQL stopped")
            except Exception as e:
                print(f"⚠️  Error stopping PostgreSQL: {e}")
    
    def export_database(self, output_file: str = None):
        """Export the current database to SQL dump."""
        if output_file is None:
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            output_file = f"data/sql/export_{timestamp}.sql"
        
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        print(f"📤 Exporting database to {output_file}...")
        
        pg_dump = self.pg.get_bin_path() / "pg_dump"
        cmd = [
            str(pg_dump),
            f"-h", "localhost",
            f"-p", str(self.port),
            f"-U", self.user,
            f"-d", self.database,
            f"-f", str(output_path),
            "--no-password"
        ]
        
        env = os.environ.copy()
        env["PGPASSWORD"] = self.password
        
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Database exported to {output_file}")
            return True
        else:
            print(f"❌ Export failed: {result.stderr}")
            return False


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    print("\n\n👋 Shutting down...")
    sys.exit(0)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Start AEGIS server with embedded PostgreSQL")
    parser.add_argument("--port", type=int, default=5432, help="PostgreSQL port (default: 5432)")
    parser.add_argument("--api-port", type=int, default=8000, help="FastAPI port (default: 8000)")
    parser.add_argument("--no-db", action="store_true", help="Start without PostgreSQL")
    parser.add_argument("--export", action="store_true", help="Export database and exit")
    parser.add_argument("--reset", action="store_true", help="Reset database (delete all data)")
    
    args = parser.parse_args()
    
    # Setup signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    
    # Handle database reset
    if args.reset:
        data_dir = Path("./postgres-data")
        if data_dir.exists():
            response = input("⚠️  This will delete all database data. Are you sure? (yes/no): ")
            if response.lower() == 'yes':
                import shutil
                shutil.rmtree(data_dir)
                print("✅ Database reset complete")
            else:
                print("❌ Reset cancelled")
        else:
            print("ℹ️  No database data to reset")
        return
    
    # Start PostgreSQL if not disabled
    pg_manager = None
    if not args.no_db:
        pg_manager = EmbeddedPostgresManager(port=args.port)
        
        # Handle export
        if args.export:
            if pg_manager.initialized_flag.exists():
                pg_manager.start()
                pg_manager.export_database()
                pg_manager.stop()
            else:
                print("❌ No database to export")
            return
        
        # Start PostgreSQL
        if not pg_manager.start():
            print("❌ Failed to start PostgreSQL. Exiting.")
            return
        
        print("\n" + "="*60)
    
    # Start FastAPI server
    print("🚀 Starting AEGIS FastAPI Server...")
    print(f"📱 Chat Interface: Open chat_interface.html in your browser")
    print(f"📋 API Docs: http://localhost:{args.api_port}/docs")
    print(f"🔍 Health Check: http://localhost:{args.api_port}/health")
    
    if pg_manager:
        print(f"\n📊 PostgreSQL Details:")
        print(f"   Host: localhost")
        print(f"   Port: {args.port}")
        print(f"   Database: aegis_dev")
        print(f"   User: aegis_user")
        print(f"   Password: aegis_dev_password")
    
    print("\n🛑 Press Ctrl+C to stop both servers\n")
    print("="*60 + "\n")
    
    try:
        uvicorn.run(
            "services.src.api:app",
            host="0.0.0.0",
            port=args.api_port,
            reload=True,
            log_level="info"
        )
    finally:
        if pg_manager:
            pg_manager.stop()


if __name__ == "__main__":
    main()