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
    "subagent_transcripts": {
        "name": "Earnings Call Transcripts",
        "description": "Complete earnings call transcripts from all global banks and insurance companies in scope. Contains management discussion, guidance, context, logic/reasoning/explanation around financial results. Includes some key line items but primarily focused on capturing management commentary and providing context around the numbers.",
        "query_type": "semantic search and RAG retrieval",
        "content_type": "earnings call transcripts",
        "use_when": "PRIMARY Source for Management Discussion & Context: Official management commentary, guidance, outlook, strategic initiatives, market discussion, reasoning behind financial results. Use when you need management's perspective or explanation of financial performance. **Query:** Use bank name, quarter, year, and specific topics or themes.",
        "priority": "primary",
    },
    "subagent_rts": {
        "name": "Report to Shareholders (RTS) / 10-Q/10-K",
        "description": "Report to shareholders for Canadian banks and 10-Q/10-K filings from US banks in scope. Used as secondary source for either raw numbers (benchmarking) or context when primary sources don't have the information needed.",
        "query_type": "semantic search and RAG retrieval",
        "content_type": "official regulatory filings",
        "use_when": "SECONDARY Source for Both Context & Line Items: When information is not found in primary sources (Benchmarking for line items, Transcripts for context). **Strategy:** Query when primary databases don't contain the needed information. **Query:** Use precise metric names, bank identifiers, and time periods.",
    },
    "subagent_benchmarking": {
        "name": "Financial Benchmarking Data",
        "description": "Income statement, balance sheet, and business-specific line items from all major Canadian and US banks in scope. This is the primary source for financial line items, amounts, and historical data. Contains comprehensive financial metrics, ratios, and comparative data across institutions.",
        "query_type": "structured data query and RAG retrieval",
        "content_type": "financial line items and metrics",
        "use_when": "PRIMARY Source for Line Items & Financial Figures: Always use when any line item is questioned. All financial metrics, amounts, figures, and historical data. **Strategy:** Always query FIRST for any request involving specific financial numbers, ratios, or amounts. **Query:** Use precise metric names, bank identifiers, and time periods.",
    },
    "report_transcript_summaries": {
        "name": "Report - Transcript Summaries",
        "description": "Pre-generated summarized versions of earnings call transcripts, created based on investor relations team requirements. These are specific reports that users can request by name. Contains structured summaries of transcript content formatted for reporting purposes.",
        "query_type": "report retrieval",
        "content_type": "pre-generated transcript summary reports",
        "use_when": "SPECIFIC REPORT REQUEST: When users specifically ask for transcript summary reports by name. This subagent pulls already generated data from Postgres and formats it for response. **Query:** Use report name, bank, quarter, year, or specific summary requirements.",
    },
    "report_transcript_key_themes": {
        "name": "Report - Transcript Key Themes",
        "description": "Pre-generated reports highlighting key themes from earnings call transcripts, created based on investor relations team requirements. These are specific reports that users can request by name. Contains thematic analysis and key topic extraction from transcript data.",
        "query_type": "report retrieval",
        "content_type": "pre-generated key themes reports",
        "use_when": "SPECIFIC REPORT REQUEST: When users specifically ask for key themes or thematic analysis reports by name. This subagent pulls already generated data from Postgres and formats it for response. **Query:** Use report name, bank, quarter, year, or specific theme requirements.",
    },
    "report_wm_readthrough": {
        "name": "Report - WM Readthrough",
        "description": "Pre-generated report highlighting key topics and themes from all US Wealth Management (WM) related entities' transcripts. Combines all WM banks into one comprehensive report rather than per-bank analysis. Created based on investor relations team requirements.",
        "query_type": "report retrieval",
        "content_type": "pre-generated WM readthrough reports",
        "use_when": "SPECIFIC REPORT REQUEST: When users specifically ask for WM (Wealth Management) readthrough reports by name. This subagent pulls already generated data from Postgres and formats it for response. **Query:** Use report name, quarter, year, or WM-specific requirements.",
    },
    "report_cm_readthrough": {
        "name": "Report - CM Readthrough",
        "description": "Pre-generated report highlighting key topics and themes from all US Capital Markets (CM) related entities' transcripts. Combines all CM banks into one comprehensive report rather than per-bank analysis. Created based on investor relations team requirements.",
        "query_type": "report retrieval",
        "content_type": "pre-generated CM readthrough reports",
        "use_when": "SPECIFIC REPORT REQUEST: When users specifically ask for CM (Capital Markets) readthrough reports by name. This subagent pulls already generated data from Postgres and formats it for response. **Query:** Use report name, quarter, year, or CM-specific requirements.",
    },
    "report_ir_quarterly_newsletter": {
        "name": "Investor Relations Quarterly Newsletter",
        "description": "Pre-generated quarterly newsletter highlighting key topics and themes across all global banks. Distributed across all of finance as a comprehensive quarterly summary. Created based on investor relations team requirements and combines insights from all institutions.",
        "query_type": "report retrieval",
        "content_type": "pre-generated quarterly newsletter",
        "use_when": "SPECIFIC REPORT REQUEST: When users specifically ask for the quarterly newsletter or quarterly summary report by name. This subagent pulls already generated data from Postgres and formats it for response. **Query:** Use report name, quarter, year, or newsletter-specific requirements.",
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
        from datetime import datetime, timezone

        current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

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
        logger.debug("Error generating database statement")
        # Fallback basic statement in case of errors
        return """<AVAILABLE_DATABASES>Financial databases available: transcripts, rts, benchmarking, report_transcript_summaries, report_transcript_key_themes, report_wm_readthrough, report_cm_readthrough, ir_quarterly_newsletter</AVAILABLE_DATABASES>"""


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
    # Input validation
    if not isinstance(available_databases, dict):
        logger.warning("Invalid input: available_databases must be a dictionary")
        return get_database_statement()
    
    try:
        from datetime import datetime, timezone

        current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

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
        logger.debug("Error generating filtered database statement")
        # Fallback to full statement if filtering fails
        return get_database_statement()