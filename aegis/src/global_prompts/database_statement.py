# global_prompts/database_statement.py
"""
Database Statement Utility

Provides centralized descriptions of available databases to be included in agent prompts.
This module serves as the single source of truth for database information across the system.
"""

import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration version and last update
DATABASE_CONFIG_VERSION = "2.0"
DATABASE_CONFIG_LAST_UPDATED = "2025-01-01"

# Complete database configuration for all available databases
AVAILABLE_DATABASES = {
    "public_transcripts": {
        "name": "Financial Earnings Call Transcripts",
        "description": "Word-for-word transcripts from quarterly earnings calls of major US and Canadian banks, including management presentations and Q&A sessions with analysts.",
        "query_type": "semantic search",
        "content_type": "earnings call transcripts",
        "use_when": "**USE THIS DATABASE WHEN:** (1) Seeking management commentary or explanations about financial results; (2) Looking for forward-looking statements or guidance; (3) Interested in what questions analysts and investors are asking; (4) Wanting strategic context behind the numbers; (5) Exploring management's outlook on market conditions; (6) Needing direct quotes from bank executives; (7) Investigating how banks are addressing challenges or opportunities. **SPECIFIC CONTENT:** Detailed discussions of quarterly performance, strategic initiatives, risk factors, guidance for future quarters, and analyst Q&A sessions. **NOT SUITABLE FOR:** Precise financial figures - use Benchmarking database for those.",
        "example_queries": [
            "What did RBC's CEO say about digital transformation?",
            "How did management explain the decrease in net interest margin?",
            "What guidance did TD provide for next quarter?",
            "What questions did analysts ask about credit losses?"
        ]
    },
    "public_rts": {
        "name": "Reports to Shareholders",
        "description": "Comprehensive quarterly reports to shareholders from major US and Canadian banks, containing detailed financial statements, MD&A sections, and formal disclosures.",
        "query_type": "semantic search",
        "content_type": "official reports and disclosures",
        "use_when": "**USE THIS DATABASE WHEN:** (1) Needing the most detailed and official documentation; (2) Researching specific formal disclosures; (3) Looking for comprehensive Management's Discussion and Analysis (MD&A); (4) Requiring footnotes to financial statements; (5) Seeking in-depth explanation of operations and business segments; (6) Needing contextual narrative for financial changes; (7) Investigating risk factors and detailed explanations of material changes. **SPECIFIC CONTENT:** Balance sheets, income statements, cash flow statements, MD&A sections, risk disclosures, segment reporting, and formal financial notes. **NOT SUITABLE FOR:** Quick financial metrics (use Benchmarking) or interactive discussions (use Transcripts).",
        "example_queries": [
            "What are the details in BMO's MD&A about credit risk?",
            "Show me the segment reporting breakdown for CIBC",
            "What risk factors did Scotia Bank disclose?",
            "Find the footnotes about derivative instruments"
        ]
    },
    "public_benchmarking": {
        "name": "Financial Benchmarking Data",
        "description": "Structured database of financial metrics, ratios, and performance indicators extracted directly from earnings reports, providing standardized figures for accurate comparison across banks and time periods.",
        "query_type": "semantic search",
        "content_type": "financial metrics and benchmarks",
        "use_when": "**USE THIS DATABASE WHEN:** (1) Needing precise financial figures, metrics, or ratios; (2) Comparing performance between banks; (3) Analyzing trends over multiple quarters or years; (4) Seeking exact revenue, income, or asset values; (5) Evaluating efficiency ratios, capital ratios, or ROE/ROA metrics; (6) Requiring hard numbers rather than commentary; (7) Creating quantitative analysis or comparisons. **SPECIFIC CONTENT:** Revenue, net income, EPS, ROE, ROA, efficiency ratios, capital ratios, loan volumes, deposit levels, credit metrics, and all standard banking KPIs in structured format. **PRIMARY SOURCE:** Always use this database first for any financial metrics or figures.",
        "example_queries": [
            "What was BMO's net income in Q2 2024?",
            "Compare efficiency ratios across all Canadian banks",
            "Show revenue trends for RBC over the last 4 quarters",
            "What is TD's current ROE?",
            "How do the CET1 ratios compare between banks?"
        ]
    },
}


def get_database_statement(level: str = 'full') -> str:
    """
    Returns a formatted statement about available databases for use in agent prompts.
    Uses XML-style delimiters for better sectioning.

    Args:
        level: 'full' (default), 'brief', or 'minimal'
            - full: Complete database descriptions with usage guidelines (~1,800 tokens)
            - brief: Database names and one-line descriptions only (~200 tokens)
            - minimal: Just database IDs for reference (~20 tokens)

    Returns:
        str: Formatted statement describing available databases
    """
    current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    statement = f"""<AVAILABLE_DATABASES>
<METADATA>
  <VERSION>{DATABASE_CONFIG_VERSION}</VERSION>
  <LAST_UPDATED>{DATABASE_CONFIG_LAST_UPDATED}</LAST_UPDATED>
  <GENERATED_AT>{current_timestamp}</GENERATED_AT>
</METADATA>

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
  <EXAMPLE_QUERIES>
"""
        for example in db_info.get('example_queries', []):
            statement += f"    - {example}\n"
        statement += """  </EXAMPLE_QUERIES>
</DATABASE>

"""
    statement += "</PUBLIC_FINANCIAL_DATABASES>\n"
    statement += "</AVAILABLE_DATABASES>"
    
    # Return appropriate level
    if level == 'brief':
        return get_database_statement_brief()
    elif level == 'minimal':
        return get_database_statement_minimal()
    else:
        return statement


# Export database configuration for other modules
def get_available_databases():
    """
    Returns the dictionary of available databases.

    Returns:
        dict: Dictionary of available database configurations
    """
    return AVAILABLE_DATABASES


def get_database_statement_brief() -> str:
    """
    Returns a brief database statement with just names and one-line descriptions.
    Reduces token usage by ~90% compared to full version.
    """
    current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    statement = f"""<AVAILABLE_DATABASES timestamp="{current_timestamp}">
The following databases are available for research:

"""
    
    for db_name, db_info in AVAILABLE_DATABASES.items():
        # Extract first sentence of description for brevity
        brief_desc = db_info['description'].split('.')[0] + '.'
        statement += f"- **{db_name}**: {db_info['name']} - {brief_desc}\n"
    
    statement += "\n</AVAILABLE_DATABASES>"
    return statement


def get_database_statement_minimal() -> str:
    """
    Returns minimal database identifiers for agents that only need references.
    Reduces token usage by ~99% compared to full version.
    """
    db_list = ", ".join(AVAILABLE_DATABASES.keys())
    return f"<DATABASES>Available databases: {db_list}</DATABASES>"


logger.debug("Database statement module initialized")
