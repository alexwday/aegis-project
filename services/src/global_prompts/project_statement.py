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
This project serves financial analysts and investors by implementing an intelligent research and response system for financial market data inquiries. The system combines comprehensive earnings transcripts, quarterly reports, supplementary packages, and peer benchmarking data with an autonomous agent-based RAG (Retrieval-Augmented Generation) process. Users can engage in natural conversations about company performance, financial metrics, and market comparisons, and the system will independently research and generate responses as needed.

<KNOWLEDGE_SOURCES>
<EARNINGS_DATA>
The system accesses earnings call transcripts, investor relations call summaries, 
and management guidance statements from various time periods.
</EARNINGS_DATA>

<FINANCIAL_REPORTS>
The system accesses quarterly reports, annual reports, supplementary financial packages, 
and peer benchmarking data to provide comprehensive financial analysis.
</FINANCIAL_REPORTS>
</KNOWLEDGE_SOURCES>

<SYSTEM_PURPOSE>
The system analyzes each inquiry to determine whether to respond based on conversation context 
or perform targeted research across available financial data sources to provide accurate, 
data-driven insights. The system ensures queries include specific banks, quarters, and years for precise analysis.
</SYSTEM_PURPOSE>
</PROJECT_CONTEXT>"""

        return statement
    except (ImportError, ValueError) as e:
        logger.debug("Error generating project statement")
        # Fallback basic statement in case of errors
        return """<PROJECT_CONTEXT>This project serves financial analysts and investors by implementing an intelligent research and response system for financial market data inquiries using RAG (Retrieval-Augmented Generation).</PROJECT_CONTEXT>"""
