#!/usr/bin/env python3
"""
Export the embedded PostgreSQL database to SQL dump file.
Can be run while the server is running.
"""

import os
import sys
import subprocess
import psycopg2
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def export_database():
    """Export the database using pg_dump."""
    
    # Database connection parameters
    host = os.getenv("VECTOR_POSTGRES_DB_HOST", "localhost")
    port = os.getenv("VECTOR_POSTGRES_DB_PORT", "5432")
    database = os.getenv("VECTOR_POSTGRES_DB_NAME", "aegis_dev")
    user = os.getenv("DB_USERNAME", "aegis_user")
    password = os.getenv("DB_PASSWORD", "aegis_dev_password")
    
    # Test connection first
    try:
        conn_string = f"postgresql://{user}:{password}@{host}:{port}/{database}"
        conn = psycopg2.connect(conn_string)
        conn.close()
        print(f"✅ Connected to database '{database}'")
    except Exception as e:
        print(f"❌ Cannot connect to database: {e}")
        print("💡 Make sure the server is running with: python start_server_with_db.py")
        return False
    
    # Create output directory
    output_dir = Path("data/sql")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"export_{timestamp}.sql"
    
    # Also create a 'latest' symlink for convenience
    latest_file = output_dir / "export_latest.sql"
    
    print(f"📤 Exporting database to {output_file}...")
    
    # Use pg_dump command
    # First try to find pg_dump in common locations
    pg_dump_paths = [
        "pg_dump",  # System PATH
        "./.pg_embedded/bin/pg_dump",  # Embedded PostgreSQL
        "./postgres-data/../.pg_embedded/bin/pg_dump",  # Alternative location
        "/usr/local/bin/pg_dump",  # macOS Homebrew
        "/usr/bin/pg_dump",  # Linux
    ]
    
    pg_dump = None
    for path in pg_dump_paths:
        if Path(path).exists() or subprocess.run(["which", path], capture_output=True).returncode == 0:
            pg_dump = path
            break
    
    if not pg_dump:
        print("❌ pg_dump not found. Please install PostgreSQL client tools.")
        return False
    
    # Run pg_dump
    cmd = [
        pg_dump,
        "-h", host,
        "-p", port,
        "-U", user,
        "-d", database,
        "-f", str(output_file),
        "--no-password",
        "--verbose",
        "--clean",  # Add DROP statements
        "--if-exists",  # Don't error if objects don't exist
        "--create",  # Include CREATE DATABASE
    ]
    
    env = os.environ.copy()
    env["PGPASSWORD"] = password
    
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"✅ Database exported successfully to {output_file}")
        
        # Create/update latest symlink
        if latest_file.exists():
            latest_file.unlink()
        latest_file.write_text(output_file.read_text())
        print(f"📎 Also saved as {latest_file}")
        
        # Show file size
        size = output_file.stat().st_size
        if size > 1024 * 1024:
            print(f"📊 Export size: {size / (1024*1024):.2f} MB")
        else:
            print(f"📊 Export size: {size / 1024:.2f} KB")
        
        return True
    else:
        print(f"❌ Export failed: {result.stderr}")
        return False


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Export embedded PostgreSQL database")
    parser.add_argument("--tables-only", action="store_true", help="Export only table data, not schema")
    parser.add_argument("--schema-only", action="store_true", help="Export only schema, not data")
    
    args = parser.parse_args()
    
    print("🐘 PostgreSQL Database Exporter")
    print("="*40)
    
    if export_database():
        print("\n✨ Export complete!")
        print("💡 To import this data on another machine:")
        print("   1. Start the server: python start_server_with_db.py")
        print("   2. Import the data: python scripts/db_import.py data/sql/export_latest.sql")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()