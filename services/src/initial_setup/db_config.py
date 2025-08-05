# services/src/initial_setup/db_config.py
"""
Database configuration for RBC environment using SQLAlchemy.
All database parameters are loaded from environment variables.
"""

from typing import Any, Dict, Optional, List
import logging
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text, Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from ..initial_setup.env_config import config

# Get logger
logger = logging.getLogger(__name__)


def create_db_engine() -> Engine:
    """
    Create SQLAlchemy engine with secure connection pooling.
    
    Returns:
        SQLAlchemy Engine instance
        
    Raises:
        SQLAlchemyError: If engine creation fails
    """
    try:
        params = config.get_db_params_secure()
        
        # Validate required parameters
        required_params = ['host', 'port', 'dbname', 'user', 'password']
        missing_params = [p for p in required_params if not params.get(p)]
        if missing_params:
            raise ValueError(f"Missing required database parameters: {missing_params}")
        
        # URL-encode password to handle special characters safely
        encoded_password = quote_plus(params["password"])
        encoded_user = quote_plus(params["user"])
        
        connection_string = (
            f"postgresql://{encoded_user}:{encoded_password}@"
            f"{params['host']}:{params['port']}/{params['dbname']}"
        )
        
        logger.debug("Creating database engine with connection pooling")
        
        engine = create_engine(
            connection_string,
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,  # Validates connections before use
            pool_recycle=3600,   # Recycle connections after 1 hour
            echo=False,          # Never log SQL to prevent credential exposure
            connect_args={
                "connect_timeout": 30,
                "application_name": "aegis-project"
            }
        )
        
        logger.debug("Database engine created successfully")
        return engine
        
    except Exception as e:
        logger.error("Failed to create database engine")
        raise SQLAlchemyError("Database engine creation failed") from e


def get_db_session() -> Session:
    """
    Get database session with proper error handling.
    
    Returns:
        SQLAlchemy Session instance
        
    Raises:
        SQLAlchemyError: If session creation fails
    """
    try:
        engine = create_db_engine()
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        logger.debug("Database session created successfully")
        return session
    except Exception as e:
        logger.error("Failed to create database session")
        raise SQLAlchemyError("Database session creation failed") from e


def test_db_connection() -> bool:
    """
    Test database connectivity without exposing credentials.
    
    Returns:
        bool: True if connection successful, False otherwise
    """
    try:
        engine = create_db_engine()
        with engine.connect() as conn:
            # Simple connectivity test
            conn.execute(text("SELECT 1"))
        logger.debug("Database connectivity test successful")
        return True
    except OperationalError:
        logger.error("Database connectivity test failed - connection error")
        return False
    except SQLAlchemyError:
        logger.error("Database connectivity test failed - SQLAlchemy error")
        return False
    except Exception:
        logger.error("Database connectivity test failed - unexpected error")
        return False


def check_tables_exist(session: Optional[Session] = None) -> List[str]:
    """
    Check if the required tables exist in the database using SQLAlchemy.

    Args:
        session: Optional SQLAlchemy session. If None, creates a new session.

    Returns:
        List of existing table names
        
    Raises:
        SQLAlchemyError: If database query fails
    """
    session_created = False
    if session is None:
        session = get_db_session()
        session_created = True
    
    try:
        # Use parameterized query to prevent SQL injection
        result = session.execute(
            text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = ANY(:table_names)
            """),
            {"table_names": ['apg_catalog', 'apg_content']}
        )
        
        tables = [row[0] for row in result.fetchall()]
        logger.debug(f"Found {len(tables)} required tables in database")
        return tables
        
    except SQLAlchemyError as e:
        logger.error("Failed to check table existence")
        raise SQLAlchemyError("Table existence check failed") from e
    finally:
        if session_created:
            session.close()


def get_db_params() -> Dict[str, Any]:
    """
    Get masked database connection parameters for logging/display purposes.
    
    Returns:
        Dictionary with database connection parameters (password masked)
    """
    logger.debug("Getting masked database parameters")
    return config.get_db_params()
