# global_prompts/database_statement.py
"""
Database Statement Utility

Provides centralized descriptions of available databases to be included in agent prompts.
This module serves as the single source of truth for database information across the system.
"""

import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Complete database configuration for all available databases
AVAILABLE_DATABASES = {
    "public_transcripts": {
        "name": "Financial Earnings Call Transcripts",
        "description": "Transcripts from quarterly earnings calls of major US and Canadian banks.",
        "query_type": "semantic search",
        "content_type": "earnings call transcripts",
        "use_when": "Primary Source: Detailed discussions from earnings calls. **Strategy:** Use to search for management commentary, analyst questions, forward-looking statements, and strategic priorities. **Query:** Use specific bank names, executive titles, topics, quarters (e.g., 'Q2 2023'), or specific financial terms.",
    },
    "public_rts": {
        "name": "Reports to Shareholders",
        "description": "Quarterly reports to shareholders from major US and Canadian banks.",
        "query_type": "semantic search",
        "content_type": "official reports and disclosures",
        "use_when": "Primary Source: Official financial reporting. **Strategy:** Use to search for quarterly financial results, formal disclosures, management discussion and analysis (MD&A), and official financial guidance. **Query:** Use specific bank names, financial metrics, reporting periods, or specific disclosure sections.",
    },
    "public_benchmarking": {
        "name": "Financial Benchmarking Data",
        "description": "Benchmarking dataset built from supplementary financial data provided with quarterly earnings reports, including historical data and comparative metrics.",
        "query_type": "semantic search",
        "content_type": "financial metrics and benchmarks",
        "use_when": "Comparative Analysis: Cross-bank performance comparison. **Strategy:** Use to compare financial metrics across institutions, identify trends, and benchmark performance. Includes YoY and QoQ comparisons. **Query:** Use specific financial metrics (e.g., 'ROE', 'CET1 ratio', 'efficiency ratio'), specific banks for comparison, or time periods for trend analysis.",
    },
}


def get_database_statement() -> str:
    """
    Returns a formatted statement about available databases for use in agent prompts.
    Uses XML-style delimiters for better sectioning.

    Returns:
        str: Formatted statement describing available databases
    """
    statement = """<AVAILABLE_DATABASES>
The following databases are available for research:

"""
    # All of our databases are public financial databases
    statement += "<PUBLIC_FINANCIAL_DATABASES>\n"
    for db_name, db_info in AVAILABLE_DATABASES.items():
        statement += f"""<DATABASE id="{db_name}">
  <NAME>{db_info['name']}</NAME>
  <DESCRIPTION>{db_info['description']}</DESCRIPTION>
  <CONTENT_TYPE>{db_info['content_type']}</CONTENT_TYPE>
  <QUERY_TYPE>{db_info['query_type']}</QUERY_TYPE>
  <USAGE>{db_info['use_when']}</USAGE>
</DATABASE>

"""
    statement += "</PUBLIC_FINANCIAL_DATABASES>\n"
    statement += "</AVAILABLE_DATABASES>"

    return statement


# Export database configuration for other modules
def get_available_databases():
    """
    Returns the dictionary of available databases.

    Returns:
        dict: Dictionary of available database configurations
    """
    return AVAILABLE_DATABASES


logger.debug("Database statement module initialized")
EOF < /dev/null