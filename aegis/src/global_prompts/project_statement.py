# global_prompts/project_statement.py
"""
Project Statement Utility

Generates a project context statement that can be prefixed to any system prompt.
Provides essential context about the project's purpose and scope.
"""

import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_project_statement() -> str:
    """
    Generate the project context statement with XML-style delimiters.

    Returns:
        str: Formatted project statement
    """
    try:
        from datetime import datetime

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        statement = f"""<PROJECT_CONTEXT timestamp="{current_time}">
This project serves RBC's Finance team by implementing an intelligent research and response system for financial data inquiries. The system combines comprehensive public financial data sources with an autonomous agent-based RAG (Retrieval-Augmented Generation) process. Users can engage in natural conversations about financial data from major US and Canadian banks, and the system will independently research and generate responses as needed.

<KNOWLEDGE_SOURCES>
<PUBLIC_FINANCIAL_SOURCES>
The system accesses public financial data sources, including:
1. Transcripts from quarterly earnings calls
2. Reports to shareholders from quarterly earnings
3. Benchmarking data built from supplementary financial information
</PUBLIC_FINANCIAL_SOURCES>
</KNOWLEDGE_SOURCES>

<SYSTEM_PURPOSE>
The system analyzes each inquiry to determine whether to respond based on conversation context
or perform targeted research across available financial data sources to provide accurate,
data-driven insights. The system helps users analyze financial trends, compare performance metrics,
and extract insights from earnings call transcripts and shareholder reports.
</SYSTEM_PURPOSE>

<SYSTEM_CAPABILITIES>
1. Multi-agent workflow with specialized components for routing, clarification, planning, and summarization
2. Parallel database queries for efficient research across multiple sources
3. Semantic search across earnings transcripts, shareholder reports, and benchmarking data
4. Time-aware fiscal calendar handling for Canadian banks (Nov-Oct fiscal year)
5. Source attribution and confidence signaling in responses
6. Streaming responses for real-time user interaction
</SYSTEM_CAPABILITIES>

<SYSTEM_LIMITATIONS>
1. Only accesses public financial data - no internal or proprietary information
2. Cannot provide investment advice or definitive recommendations
3. Limited to historical data - cannot predict future performance
4. Fiscal quarter calculations may require user confirmation for complex time references
5. Research scope limited to available database content (primarily US and Canadian banks)
6. Cannot access real-time market data or live pricing information
</SYSTEM_LIMITATIONS>
</PROJECT_CONTEXT>"""

        return statement
    except Exception as e:
        logger.error(f"Error generating project statement: {str(e)}")
        # Fallback basic statement in case of errors
        return """<PROJECT_CONTEXT>This project serves RBC's Finance team by implementing an intelligent research and response system for public financial data inquiries using RAG (Retrieval-Augmented Generation).</PROJECT_CONTEXT>"""
