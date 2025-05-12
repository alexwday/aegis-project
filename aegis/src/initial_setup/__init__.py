"""
Initial setup module for AEGIS project.
Contains configuration for database, logging, OAuth and SSL.
"""

from aegis.src.initial_setup.db_config import check_tables_exist, connect_to_db
from aegis.src.initial_setup.logging_config import configure_logging

__all__ = ["configure_logging", "connect_to_db", "check_tables_exist"]
