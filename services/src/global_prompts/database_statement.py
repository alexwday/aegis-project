# services/src/global_prompts/database_statement.py
"""
Database Statement Utility

Provides centralized descriptions of available databases to be included in agent prompts.
This module serves as the single source of truth for database information across the system.
"""

import logging

logger = logging.getLogger(__name__)

# Complete database configuration for all available databases
AVAILABLE_DATABASES = {
    "earnings_transcripts": {
        "name": "Earnings Call Transcripts",
        "description": "Complete transcripts of quarterly earnings calls including management presentations, Q&A sessions, investor discussions, and forward-looking guidance. Contains management commentary on financial highlights, market conditions, and strategic initiatives.",
        "query_type": "semantic search",
        "content_type": "earnings call transcripts",
        "use_when": "PRIMARY Source for Earnings Context & Management Discussion: Official management commentary and discussion. SECONDARY Source for Line Items: When financial metrics are not found in Peer Benchmarking. **Strategy:** Query FIRST for management guidance, outlook, strategic initiatives, market discussion. Query SECOND for financial metrics if not found in Peer Benchmarking. **Query:** Use bank name, quarter, year, and specific topics.",
    },
    "quarterly_reports": {
        "name": "Quarterly Report to Shareholders",
        "description": "Official quarterly financial reports containing comprehensive financial statements, segment breakdowns, and key performance metrics for all covered banks.",
        "query_type": "semantic search",
        "content_type": "quarterly financial reports",
        "use_when": "SECONDARY Source for Both Context & Line Items: When information is not found in primary sources (Peer Benchmarking for line items, Earnings Call Transcripts for context). **Strategy:** Query THIRD for financial metrics if not found in Peer Benchmarking or Earnings Call Transcripts. Query SECOND for context/management discussion if not found in Earnings Call Transcripts. **Query:** Use precise metric names, bank identifiers, and time periods.",
    },
    "supplementary_packages": {
        "name": "Peer Benchmarking",
        "description": "Primary source for financial line items, figures, and amounts for all banks and peers. Contains comprehensive financial metrics, ratios, and comparative data across institutions.",
        "query_type": "semantic search",
        "content_type": "peer benchmarking data",
        "use_when": "PRIMARY Source for Line Items & Financial Figures: All financial metrics, amounts, and figures. **Strategy:** Always query FIRST for any request involving specific financial numbers, ratios, or amounts. **Query:** Use precise metric names, bank identifiers, and time periods. This is the authoritative source for all quantitative financial data.",
    },
    "ir_call_summaries": {
        "name": "Investor Relations Call Summaries ETL",
        "description": "Structured summaries of earnings calls prepared through ETL processing, highlighting key points, metrics discussed, and management commentary in a standardized format.",
        "query_type": "semantic search",
        "content_type": "structured call summaries",
        "use_when": "Quick Overview & Key Highlights: Pre-processed summaries of earnings calls. **Strategy:** Query for quick overviews of earnings calls or when users need highlighted key points without full transcript detail. **Query:** Use bank name, quarter, year, and summary-oriented terms.",
    },
}


def get_database_statement() -> str:
    """
    Generate the database availability statement with XML-style delimiters.
    This function provides the complete database configuration for system prompts.

    Returns:
        str: Formatted database statement
    """
    try:
        from datetime import datetime

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Build the database listing
        db_list = []
        for db_key, db_info in AVAILABLE_DATABASES.items():
            db_entry = f"""
<DATABASE id="{db_key}">
<NAME>{db_info['name']}</NAME>
<DESCRIPTION>{db_info['description']}</DESCRIPTION>
<QUERY_TYPE>{db_info['query_type']}</QUERY_TYPE>
<CONTENT_TYPE>{db_info['content_type']}</CONTENT_TYPE>
<USE_WHEN>{db_info['use_when']}</USE_WHEN>
</DATABASE>"""
            db_list.append(db_entry)

        statement = f"""<AVAILABLE_DATABASES timestamp="{current_time}">
The following databases are available for research:
{"".join(db_list)}

<QUERY_STRATEGY>
For optimal results:
1. ALWAYS include specific bank names (e.g., "Royal Bank of Canada", "TD Bank", "Bank of Montreal")
2. ALWAYS include specific time periods (e.g., "Q3 2024", "fiscal year 2023")
3. Use precise financial metric names (e.g., "net income", "operating margin", "return on equity")
4. For comparisons, specify all entities and time periods being compared
5. For management commentary, reference specific topics or themes discussed
</QUERY_STRATEGY>
</AVAILABLE_DATABASES>"""

        return statement
    except Exception as e:
        logger.debug(f"Error generating database statement: {str(e)}")
        # Fallback basic statement in case of errors
        return """<AVAILABLE_DATABASES>Financial databases available: earnings_transcripts, quarterly_reports, supplementary_packages, ir_call_summaries</AVAILABLE_DATABASES>"""


def get_available_databases() -> dict:
    """
    Return the AVAILABLE_DATABASES dictionary for use by other modules.
    
    Returns:
        dict: The complete AVAILABLE_DATABASES configuration
    """
    return AVAILABLE_DATABASES


def get_filtered_database_statement(available_databases: dict) -> str:
    """
    Generate a filtered database statement based on the databases available to the current user.
    This is used by the Planner agent which receives a filtered list of databases.

    Args:
        available_databases: Dict of database keys and info available to the user

    Returns:
        str: Formatted filtered database statement
    """
    try:
        from datetime import datetime

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Build the filtered database listing
        db_list = []
        for db_key, db_info in available_databases.items():
            if db_key in AVAILABLE_DATABASES:
                full_info = AVAILABLE_DATABASES[db_key]
                db_entry = f"""
<DATABASE id="{db_key}">
<NAME>{full_info['name']}</NAME>
<DESCRIPTION>{full_info['description']}</DESCRIPTION>
<QUERY_TYPE>{full_info['query_type']}</QUERY_TYPE>
<CONTENT_TYPE>{full_info['content_type']}</CONTENT_TYPE>
<USE_WHEN>{full_info['use_when']}</USE_WHEN>
</DATABASE>"""
                db_list.append(db_entry)

        statement = f"""<AVAILABLE_DATABASES timestamp="{current_time}" filtered="true">
The following databases are available for your research based on your access permissions:
{"".join(db_list)}

<QUERY_STRATEGY>
For optimal results:
1. ALWAYS include specific bank names (e.g., "Royal Bank of Canada", "TD Bank", "Bank of Montreal")
2. ALWAYS include specific time periods (e.g., "Q3 2024", "fiscal year 2023")
3. Use precise financial metric names (e.g., "net income", "operating margin", "return on equity")
4. For comparisons, specify all entities and time periods being compared
5. For management commentary, reference specific topics or themes discussed
</QUERY_STRATEGY>
</AVAILABLE_DATABASES>"""

        return statement
    except Exception as e:
        logger.debug(f"Error generating filtered database statement: {str(e)}")
        # Fallback to full statement if filtering fails
        return get_database_statement()