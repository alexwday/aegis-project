#!/usr/bin/env python3
"""
AEGIS server with PostgreSQL via Docker.
Manages a PostgreSQL Docker container and the FastAPI server together.
"""

import uvicorn
import sys
import os
import time
import signal
import atexit
import subprocess
import json
from pathlib import Path
from typing import Optional, Dict, Any

# Add the services package to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class DockerPostgresManager:
    """Manages PostgreSQL Docker container for development."""
    
    def __init__(self, 
                 container_name: str = "aegis-postgres",
                 port: int = 5432,
                 database: str = "aegis_dev",
                 user: str = "aegis_user",
                 password: str = "aegis_dev_password",
                 postgres_version: str = "15"):
        self.container_name = container_name
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.postgres_version = postgres_version
        self.data_dir = Path("./postgres-data")
        self.sql_dir = Path("./data/sql")
        
    def check_docker_installed(self) -> bool:
        """Check if Docker is installed and running."""
        try:
            result = subprocess.run(
                ["docker", "version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                print("❌ Docker is installed but not running. Please start Docker Desktop.")
                return False
            return True
        except FileNotFoundError:
            print("❌ Docker is not installed. Please install Docker Desktop from https://docker.com")
            return False
        except subprocess.TimeoutExpired:
            print("❌ Docker is not responding. Please check Docker Desktop is running.")
            return False
            
    def container_exists(self) -> bool:
        """Check if container exists (running or stopped)."""
        result = subprocess.run(
            ["docker", "ps", "-a", "--filter", f"name={self.container_name}", "--format", "{{.Names}}"],
            capture_output=True,
            text=True
        )
        return self.container_name in result.stdout
        
    def container_running(self) -> bool:
        """Check if container is currently running."""
        result = subprocess.run(
            ["docker", "ps", "--filter", f"name={self.container_name}", "--format", "{{.Names}}"],
            capture_output=True,
            text=True
        )
        return self.container_name in result.stdout
        
    def start(self) -> bool:
        """Start the PostgreSQL Docker container."""
        if not self.check_docker_installed():
            return False
            
        print(f"🐘 Starting PostgreSQL {self.postgres_version} in Docker...")
        
        # Create data directory for persistence
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if container exists
        if self.container_exists():
            if self.container_running():
                print(f"✅ PostgreSQL container '{self.container_name}' is already running")
                self._wait_for_postgres()
                self._set_environment_variables()
                return True
            else:
                # Start existing container
                print(f"🔄 Starting existing container '{self.container_name}'...")
                subprocess.run(["docker", "start", self.container_name])
                self._wait_for_postgres()
                self._set_environment_variables()
                print("✅ PostgreSQL container started")
                return True
        
        # Create new container
        print(f"🚀 Creating new PostgreSQL container '{self.container_name}'...")
        
        # Pull pgvector-enabled PostgreSQL image
        image_name = f"pgvector/pgvector:pg{self.postgres_version}"
        print(f"📥 Pulling {image_name} image (PostgreSQL with pgvector)...")
        subprocess.run(
            ["docker", "pull", image_name],
            stdout=subprocess.DEVNULL
        )
        
        # Run container with mounted data directory
        cmd = [
            "docker", "run",
            "--name", self.container_name,
            "-e", f"POSTGRES_USER={self.user}",
            "-e", f"POSTGRES_PASSWORD={self.password}",
            "-e", f"POSTGRES_DB={self.database}",
            "-p", f"{self.port}:5432",
            "-v", f"{self.data_dir.absolute()}:/var/lib/postgresql/data",
            "-d",  # Run in background
            image_name
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ Failed to create container: {result.stderr}")
            return False
            
        print("⏳ Waiting for PostgreSQL to initialize...")
        self._wait_for_postgres()
        
        # Initialize database if needed
        if self._is_first_run():
            self._initialize_database()
        else:
            print("📊 Using existing database")
            self._check_for_imports()
            
        self._set_environment_variables()
        
        # Register cleanup
        atexit.register(self.cleanup)
        
        print(f"✅ PostgreSQL is ready on port {self.port}")
        return True
        
    def _wait_for_postgres(self, timeout: int = 30):
        """Wait for PostgreSQL to be ready to accept connections."""
        import psycopg2
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                conn_string = f"postgresql://{self.user}:{self.password}@localhost:{self.port}/{self.database}"
                conn = psycopg2.connect(conn_string)
                conn.close()
                return True
            except:
                time.sleep(1)
        
        raise TimeoutError("PostgreSQL failed to start within timeout period")
        
    def _is_first_run(self) -> bool:
        """Check if this is the first run (no tables exist)."""
        import psycopg2
        
        try:
            conn_string = f"postgresql://{self.user}:{self.password}@localhost:{self.port}/{self.database}"
            conn = psycopg2.connect(conn_string)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            count = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            return count == 0
        except:
            return True
            
    def _initialize_database(self):
        """Initialize database with schema and optional sample data."""
        print("🔄 Initializing database...")
        
        if not self.sql_dir.exists():
            print("⚠️  No SQL directory found, skipping initialization")
            return
        
        # First, test vector capabilities
        test_file = self.sql_dir / "test_vector_capabilities.sql"
        if test_file.exists():
            print("🧪 Testing pgvector capabilities...")
            self._import_sql_file(test_file)
            self._show_vector_capabilities()
        
        # Import adaptive schema if it exists, otherwise use standard schema
        adaptive_schema = self.sql_dir / "schema_adaptive.sql"
        standard_schema = self.sql_dir / "schema.sql"
        
        if adaptive_schema.exists():
            print("📝 Importing adaptive schema (adjusts to pgvector capabilities)...")
            self._import_sql_file(adaptive_schema)
            print("✅ Adaptive schema imported")
        elif standard_schema.exists():
            print("📝 Importing standard schema...")
            self._import_sql_file(standard_schema)
            print("✅ Schema imported")
            
        # Import sample data
        for data_file in ["sample_data.sql", "initial_data.sql"]:
            data_path = self.sql_dir / data_file
            if data_path.exists():
                print(f"📥 Importing {data_file}...")
                self._import_sql_file(data_path)
                print(f"✅ {data_file} imported")
                break
                
    def _show_vector_capabilities(self):
        """Display the vector capabilities test results."""
        import psycopg2
        
        try:
            conn_string = f"postgresql://{self.user}:{self.password}@localhost:{self.port}/{self.database}"
            conn = psycopg2.connect(conn_string)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT capability, supported, details
                FROM vector_capabilities
                WHERE capability IN ('vector_3072', 'halfvec_3072', 'vector_1536')
                ORDER BY capability
            """)
            
            results = cursor.fetchall()
            if results:
                print("\n📊 Vector Capabilities:")
                for cap, supported, details in results:
                    status = "✅" if supported else "❌"
                    print(f"   {status} {cap}: {details}")
                print()
            
            cursor.close()
            conn.close()
        except:
            pass  # Silently fail if table doesn't exist
    
    def _check_for_imports(self):
        """Check for pending SQL imports."""
        if not self.sql_dir.exists():
            return
            
        pending = self.sql_dir / "pending_import.sql"
        if pending.exists():
            response = input("📦 Found pending_import.sql. Import now? (y/n): ")
            if response.lower() == 'y':
                self._import_sql_file(pending)
                # Rename after import
                pending.rename(self.sql_dir / f"imported_{time.strftime('%Y%m%d_%H%M%S')}.sql")
                print("✅ Import complete")
                
    def _import_sql_file(self, file_path: Path):
        """Import SQL file into database."""
        import psycopg2
        
        conn_string = f"postgresql://{self.user}:{self.password}@localhost:{self.port}/{self.database}"
        conn = psycopg2.connect(conn_string)
        conn.autocommit = True
        
        with open(file_path, 'r') as f:
            sql = f.read()
            
        cursor = conn.cursor()
        try:
            cursor.execute(sql)
        except psycopg2.Error as e:
            print(f"⚠️  SQL execution warning: {e}")
        finally:
            cursor.close()
            conn.close()
            
    def _set_environment_variables(self):
        """Set environment variables for the application."""
        os.environ["VECTOR_POSTGRES_DB_HOST"] = "localhost"
        os.environ["VECTOR_POSTGRES_DB_PORT"] = str(self.port)
        os.environ["VECTOR_POSTGRES_DB_NAME"] = self.database
        os.environ["DB_USERNAME"] = self.user
        os.environ["DB_PASSWORD"] = self.password
        os.environ["DATABASE_URL"] = f"postgresql://{self.user}:{self.password}@localhost:{self.port}/{self.database}"
        
        print("🔧 Environment variables configured")
        
    def stop(self):
        """Stop the PostgreSQL container."""
        if self.container_running():
            print(f"\n🛑 Stopping PostgreSQL container '{self.container_name}'...")
            subprocess.run(["docker", "stop", self.container_name])
            print("✅ PostgreSQL stopped")
            
    def remove(self):
        """Remove the PostgreSQL container."""
        if self.container_exists():
            print(f"🗑️  Removing container '{self.container_name}'...")
            subprocess.run(["docker", "rm", "-f", self.container_name])
            print("✅ Container removed")
            
    def reset(self):
        """Reset database by removing container and data."""
        self.remove()
        if self.data_dir.exists():
            import shutil
            shutil.rmtree(self.data_dir)
            print("✅ Database data deleted")
            
    def export_database(self, output_file: str = None):
        """Export database to SQL dump."""
        if output_file is None:
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            output_file = f"data/sql/export_{timestamp}.sql"
            
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        print(f"📤 Exporting database to {output_file}...")
        
        # Use docker exec to run pg_dump
        cmd = [
            "docker", "exec", self.container_name,
            "pg_dump",
            "-U", self.user,
            "-d", self.database,
            "--clean",
            "--if-exists",
            "--no-owner"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            output_path.write_text(result.stdout)
            print(f"✅ Database exported to {output_file}")
            
            # Also save as latest
            latest = output_path.parent / "export_latest.sql"
            latest.write_text(result.stdout)
            
            return True
        else:
            print(f"❌ Export failed: {result.stderr}")
            return False
            
    def cleanup(self):
        """Cleanup handler - optionally stop container."""
        pass  # Keep container running by default


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    print("\n\n👋 Shutting down...")
    sys.exit(0)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Start AEGIS server with PostgreSQL in Docker")
    parser.add_argument("--port", type=int, default=5432, help="PostgreSQL port (default: 5432)")
    parser.add_argument("--api-port", type=int, default=8000, help="FastAPI port (default: 8000)")
    parser.add_argument("--no-db", action="store_true", help="Start without PostgreSQL")
    parser.add_argument("--export", action="store_true", help="Export database and exit")
    parser.add_argument("--reset", action="store_true", help="Reset database (delete all data)")
    parser.add_argument("--stop", action="store_true", help="Stop PostgreSQL container")
    
    args = parser.parse_args()
    
    # Setup signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    # Create manager
    pg_manager = DockerPostgresManager(port=args.port)
    
    # Handle special commands
    if args.reset:
        response = input("⚠️  This will delete all database data. Are you sure? (yes/no): ")
        if response.lower() == 'yes':
            pg_manager.reset()
            print("✅ Database reset complete")
        return
        
    if args.stop:
        pg_manager.stop()
        return
        
    if args.export:
        if pg_manager.container_running():
            pg_manager.export_database()
        else:
            print("❌ PostgreSQL is not running. Start it first.")
        return
    
    # Start PostgreSQL if not disabled
    if not args.no_db:
        if not pg_manager.start():
            print("❌ Failed to start PostgreSQL")
            return
            
        print("\n" + "="*60)
        
    # Start FastAPI server
    print("🚀 Starting AEGIS FastAPI Server...")
    print(f"📱 Chat Interface: Open chat_interface.html in your browser")
    print(f"📋 API Docs: http://localhost:{args.api_port}/docs")
    print(f"🔍 Health Check: http://localhost:{args.api_port}/health")
    
    if not args.no_db:
        print(f"\n📊 PostgreSQL Connection Details:")
        print(f"   Host: localhost")
        print(f"   Port: {args.port}")
        print(f"   Database: {pg_manager.database}")
        print(f"   User: {pg_manager.user}")
        print(f"   Password: {pg_manager.password}")
        print(f"\n💡 Container will keep running after server stops")
        print(f"   Stop it with: python {__file__} --stop")
        
    print("\n🛑 Press Ctrl+C to stop the server\n")
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
        # Note: Container keeps running for next session
        pass


if __name__ == "__main__":
    main()