# services/src/global_prompts/__init__.py
"""
Global prompts module for AEGIS project.
Contains shared prompt templates and statement generators.
"""

from .project_statement import get_project_statement
from .restrictions_statement import (
    get_compliance_restrictions,
    get_quality_guidelines, 
    get_confidence_signaling,
    get_restrictions_statement
)
from .fiscal_statement import get_fiscal_statement, get_fiscal_period
from .database_statement import (
    get_database_statement,
    get_available_databases,
    get_filtered_database_statement
)

__all__ = [
    "get_project_statement",
    "get_compliance_restrictions",
    "get_quality_guidelines",
    "get_confidence_signaling", 
    "get_restrictions_statement",
    "get_fiscal_statement",
    "get_fiscal_period",
    "get_database_statement",
    "get_available_databases",
    "get_filtered_database_statement"
]
