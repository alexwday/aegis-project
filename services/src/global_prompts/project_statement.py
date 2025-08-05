# services/src/global_prompts/project_statement.py
"""
Project Statement Utility

Generates a project context statement that can be prefixed to any system prompt.
Provides essential context about the project's purpose and scope.
"""

import logging

logger = logging.getLogger(__name__)


def get_project_statement() -> str:
    """
    Generate the project context statement with XML-style delimiters.

    Returns:
        str: Formatted project statement
    """
    try:
        from datetime import datetime, timezone

        current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        statement = f"""<PROJECT_CONTEXT timestamp="{current_time}">
This project serves financial analysts and investors by implementing an intelligent research and response system for financial market data inquiries. The system combines comprehensive financial data sources with an autonomous agent-based RAG (Retrieval-Augmented Generation) process. Users can engage in natural conversations about company performance, financial metrics, and market comparisons, and the system will independently research and generate responses as needed.

<KNOWLEDGE_SOURCES>
<PRIMARY_DATA_SOURCES>
The system accesses three primary data sources:
- Transcripts: Earnings call transcripts with management discussion and guidance from global banks and insurance companies
- RTS: Report to Shareholders for Canadian banks and 10-Q/10-K filings from US banks
- Benchmarking: Income statement, balance sheet, and business-specific line items (PRIMARY source for financial metrics)
</PRIMARY_DATA_SOURCES>

<REPORT_SOURCES>
The system provides access to five pre-generated report types:
- Transcript Summaries: Summarized versions of earnings calls based on IR team requirements
- Transcript Key Themes: Thematic analysis and key topic extraction from transcript data
- WM Readthrough: Combined US Wealth Management entities analysis reports
- CM Readthrough: Combined US Capital Markets entities analysis reports  
- IR Quarterly Newsletter: Global banks quarterly summary distributed across finance
</REPORT_SOURCES>
</KNOWLEDGE_SOURCES>

<SYSTEM_PURPOSE>
The system analyzes each inquiry to determine whether to respond based on conversation context 
or perform targeted research across available financial data sources to provide accurate, 
data-driven insights. The system ensures queries include specific banks, quarters, and years for precise analysis.
For financial metrics and line items, the system prioritizes the Benchmarking database as the authoritative source.
</SYSTEM_PURPOSE>
</PROJECT_CONTEXT>"""

        return statement
    except (ImportError, ValueError) as e:
        logger.debug("Error generating project statement")
        # Fallback basic statement in case of errors
        return """<PROJECT_CONTEXT>This project serves financial analysts and investors by implementing an intelligent research and response system for financial market data inquiries using RAG (Retrieval-Augmented Generation) across transcripts, regulatory filings, benchmarking data, and pre-generated reports.</PROJECT_CONTEXT>"""
