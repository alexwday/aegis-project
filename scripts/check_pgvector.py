#!/usr/bin/env python3
"""
Check pgvector installation, version, and capabilities.
Tests for halfvec support and maximum dimensions.
"""

import os
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def check_pgvector():
    """Check pgvector installation and capabilities."""
    
    # Database connection parameters
    host = os.getenv("VECTOR_POSTGRES_DB_HOST", "localhost")
    port = os.getenv("VECTOR_POSTGRES_DB_PORT", "5432")
    database = os.getenv("VECTOR_POSTGRES_DB_NAME", "aegis_dev")
    user = os.getenv("DB_USERNAME", "aegis_user")
    password = os.getenv("DB_PASSWORD", "aegis_dev_password")
    
    print("🔍 Checking pgvector installation and capabilities...")
    print("="*60)
    
    try:
        # Connect to database
        conn_string = f"postgresql://{user}:{password}@{host}:{port}/{database}"
        conn = psycopg2.connect(conn_string)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Check if pgvector extension exists
        print("\n1️⃣  Checking pgvector extension availability...")
        cursor.execute("""
            SELECT * FROM pg_available_extensions 
            WHERE name = 'vector'
        """)
        result = cursor.fetchone()
        
        if result:
            print(f"✅ pgvector is available")
            print(f"   Default version: {result[1]}")
            print(f"   Installed version: {result[2] if result[2] else 'Not installed'}")
            
            if not result[2]:
                print("\n📦 Installing pgvector extension...")
                try:
                    cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
                    print("✅ pgvector extension installed")
                except Exception as e:
                    print(f"❌ Failed to install pgvector: {e}")
                    print("   You may need to install pgvector in your PostgreSQL first:")
                    print("   - Docker: Use postgres image with pgvector")
                    print("   - Local: Install pgvector from https://github.com/pgvector/pgvector")
                    return
        else:
            print("❌ pgvector is not available in this PostgreSQL installation")
            print("\n💡 To add pgvector to Docker PostgreSQL:")
            print("   Use image: ankane/pgvector:latest or pgvector/pgvector:pg15")
            print("\n💡 To add pgvector to local PostgreSQL:")
            print("   Follow: https://github.com/pgvector/pgvector#installation")
            return
        
        # Get detailed version info
        print("\n2️⃣  Getting pgvector version details...")
        cursor.execute("""
            SELECT extversion FROM pg_extension 
            WHERE extname = 'vector'
        """)
        version = cursor.fetchone()
        if version:
            version_str = version[0]
            print(f"✅ pgvector version: {version_str}")
            
            # Parse version
            major, minor = version_str.split('.')[:2]
            version_float = float(f"{major}.{minor}")
            
            # Check for halfvec support (added in v0.5.0)
            if version_float >= 0.5:
                print(f"✅ halfvec type supported (16-bit precision)")
            else:
                print(f"❌ halfvec not supported (requires v0.5.0+, you have v{version_str})")
        
        # Test vector dimensions
        print("\n3️⃣  Testing vector dimension limits...")
        
        # Create test table
        cursor.execute("DROP TABLE IF EXISTS vector_test")
        
        # Test standard vector with 3072 dimensions
        try:
            cursor.execute("""
                CREATE TABLE vector_test (
                    id serial PRIMARY KEY,
                    embedding_standard vector(3072)
                )
            """)
            print("✅ Standard vector(3072) supported")
            cursor.execute("DROP TABLE vector_test")
        except Exception as e:
            print(f"❌ Standard vector(3072) failed: {e}")
        
        # Test halfvec with 3072 dimensions (if version supports it)
        if version_float >= 0.5:
            try:
                cursor.execute("""
                    CREATE TABLE vector_test (
                        id serial PRIMARY KEY,
                        embedding_half halfvec(3072)
                    )
                """)
                print("✅ halfvec(3072) supported (50% storage savings)")
                cursor.execute("DROP TABLE vector_test")
            except Exception as e:
                print(f"❌ halfvec(3072) failed: {e}")
        
        # Show available vector types
        print("\n4️⃣  Available vector data types:")
        cursor.execute("""
            SELECT typname, typlen, typcategory 
            FROM pg_type 
            WHERE typname IN ('vector', 'halfvec', 'sparsevec')
            ORDER BY typname
        """)
        
        types = cursor.fetchall()
        if types:
            for typ in types:
                print(f"   • {typ[0]}: {'variable' if typ[1] == -1 else f'{typ[1]} bytes'}")
        
        # Show recommended configurations
        print("\n5️⃣  Recommended configurations for OpenAI embeddings:")
        print("   • text-embedding-3-small: 1536 dimensions → vector(1536)")
        print("   • text-embedding-3-large: 3072 dimensions → vector(3072)")
        if version_float >= 0.5:
            print("   • For storage optimization: use halfvec(3072) - 50% smaller")
        
        # Check index methods
        print("\n6️⃣  Available index methods for vector similarity:")
        cursor.execute("""
            SELECT amname, amhandler::text 
            FROM pg_am 
            WHERE amname IN ('ivfflat', 'hnsw')
        """)
        
        indexes = cursor.fetchall()
        if indexes:
            for idx in indexes:
                print(f"   • {idx[0]} index available")
        else:
            print("   • Basic indexes only (consider upgrading pgvector for better performance)")
        
        # Example table creation
        print("\n📝 Example table with 3072-dimension embeddings:")
        print("```sql")
        if version_float >= 0.5:
            print("-- With halfvec (recommended for storage efficiency):")
            print("CREATE TABLE document_embeddings (")
            print("    id SERIAL PRIMARY KEY,")
            print("    content TEXT,")
            print("    embedding halfvec(3072)  -- 50% storage savings")
            print(");")
            print()
        print("-- With standard vector:")
        print("CREATE TABLE document_embeddings (")
        print("    id SERIAL PRIMARY KEY,")
        print("    content TEXT,")
        print("    embedding vector(3072)")
        print(");")
        print()
        print("-- Create index for similarity search:")
        print("CREATE INDEX ON document_embeddings")
        print("USING ivfflat (embedding vector_cosine_ops)")
        print("WITH (lists = 100);  -- Adjust 'lists' based on data size")
        print("```")
        
        cursor.close()
        conn.close()
        
        print("\n✅ pgvector check complete!")
        
    except psycopg2.OperationalError as e:
        print(f"❌ Cannot connect to database: {e}")
        print("\n💡 Make sure PostgreSQL is running:")
        print("   python start_server_postgres.py")
    except Exception as e:
        print(f"❌ Error: {e}")


def main():
    """Main entry point."""
    print("🐘 PostgreSQL pgvector Capability Checker")
    print("="*60)
    check_pgvector()


if __name__ == "__main__":
    main()