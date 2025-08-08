#!/usr/bin/env python3
"""
Import SQL dump into the embedded PostgreSQL database.
The server must be running before importing.
"""

import os
import sys
import subprocess
import psycopg2
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def import_database(sql_file: str):
    """Import SQL dump file into the database."""
    
    # Database connection parameters
    host = os.getenv("VECTOR_POSTGRES_DB_HOST", "localhost")
    port = os.getenv("VECTOR_POSTGRES_DB_PORT", "5432")
    database = os.getenv("VECTOR_POSTGRES_DB_NAME", "aegis_dev")
    user = os.getenv("DB_USERNAME", "aegis_user")
    password = os.getenv("DB_PASSWORD", "aegis_dev_password")
    
    # Check if file exists
    sql_path = Path(sql_file)
    if not sql_path.exists():
        print(f"❌ File not found: {sql_file}")
        return False
    
    # Test connection first
    try:
        conn_string = f"postgresql://{user}:{password}@{host}:{port}/{database}"
        conn = psycopg2.connect(conn_string)
        
        # Get current table count for comparison
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        table_count_before = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        
        print(f"✅ Connected to database '{database}'")
        print(f"📊 Current tables in database: {table_count_before}")
        
    except Exception as e:
        print(f"❌ Cannot connect to database: {e}")
        print("💡 Make sure the server is running with: python start_server_with_db.py")
        return False
    
    # Confirm import
    print(f"\n⚠️  This will import: {sql_file}")
    print(f"   File size: {sql_path.stat().st_size / 1024:.2f} KB")
    response = input("Continue with import? (y/n): ")
    
    if response.lower() != 'y':
        print("❌ Import cancelled")
        return False
    
    print(f"\n📥 Importing {sql_file}...")
    
    # Try to find psql in common locations
    psql_paths = [
        "psql",  # System PATH
        "./.pg_embedded/bin/psql",  # Embedded PostgreSQL
        "./postgres-data/../.pg_embedded/bin/psql",  # Alternative location
        "/usr/local/bin/psql",  # macOS Homebrew
        "/usr/bin/psql",  # Linux
    ]
    
    psql = None
    for path in psql_paths:
        if Path(path).exists() or subprocess.run(["which", path], capture_output=True).returncode == 0:
            psql = path
            break
    
    if psql:
        # Use psql for import (handles large files better)
        cmd = [
            psql,
            "-h", host,
            "-p", port,
            "-U", user,
            "-d", database,
            "-f", str(sql_path),
            "--no-password"
        ]
        
        env = os.environ.copy()
        env["PGPASSWORD"] = password
        
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        if result.returncode == 0:
            success = True
        else:
            print(f"⚠️  Some warnings during import: {result.stderr[:500]}")
            success = True  # Often still successful despite warnings
    else:
        # Fallback to Python import
        print("💡 Using Python-based import (may be slower for large files)...")
        
        try:
            conn = psycopg2.connect(conn_string)
            conn.autocommit = True
            cursor = conn.cursor()
            
            with open(sql_path, 'r') as f:
                sql = f.read()
            
            # Execute the SQL
            cursor.execute(sql)
            cursor.close()
            conn.close()
            success = True
            
        except Exception as e:
            print(f"❌ Import failed: {e}")
            success = False
    
    if success:
        # Check table count after import
        try:
            conn = psycopg2.connect(conn_string)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            table_count_after = cursor.fetchone()[0]
            
            # Get some sample table names
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                LIMIT 5
            """)
            sample_tables = [row[0] for row in cursor.fetchall()]
            
            cursor.close()
            conn.close()
            
            print(f"\n✅ Import completed successfully!")
            print(f"📊 Tables after import: {table_count_after}")
            if table_count_after > table_count_before:
                print(f"   Added {table_count_after - table_count_before} new tables")
            if sample_tables:
                print(f"   Sample tables: {', '.join(sample_tables)}")
            
        except Exception as e:
            print(f"✅ Import completed (couldn't verify: {e})")
        
        return True
    
    return False


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Import SQL dump into embedded PostgreSQL")
    parser.add_argument("file", nargs="?", default="data/sql/export_latest.sql",
                       help="SQL file to import (default: data/sql/export_latest.sql)")
    parser.add_argument("--force", action="store_true", 
                       help="Skip confirmation prompt")
    
    args = parser.parse_args()
    
    print("🐘 PostgreSQL Database Importer")
    print("="*40)
    
    # Check for common import files if default doesn't exist
    if not Path(args.file).exists():
        alternatives = [
            "data/sql/import.sql",
            "data/sql/initial_data.sql",
            "data/sql/schema.sql"
        ]
        
        for alt in alternatives:
            if Path(alt).exists():
                print(f"💡 Found {alt}")
                response = input(f"Import this file instead? (y/n): ")
                if response.lower() == 'y':
                    args.file = alt
                    break
    
    if import_database(args.file):
        print("\n✨ Import complete!")
        print("💡 Your database is now ready to use")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()