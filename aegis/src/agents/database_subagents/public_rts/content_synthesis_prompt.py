# shareholder_reports/content_synthesis_prompt.py
"""
Content Synthesis Prompt for Shareholder Reports

This module provides prompt templates for synthesizing information
from shareholder report content.
"""

import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_content_synthesis_prompt(query: str, content: str) -> str:
    """
    Generate a prompt for synthesizing content from shareholder reports.

    Args:
        query: The original user query
        content: Formatted shareholder report sections to synthesize

    Returns:
        str: Formatted prompt for content synthesis
    """
    prompt = f"""Your task is to synthesize information from quarterly shareholder reports of major banks to answer a user's question. 

User Question: {query}

Shareholder Report Content:
{content}

SYNTHESIS INSTRUCTIONS:
1. Create a detailed, well-structured response that directly addresses the user's question
2. Cite specific sections with bank name, date, quarter, and report section when relevant
3. For financial figures, clearly indicate the currency, time period, and any relevant accounting standards
4. Include exact financial metrics with proper attribution
5. Analyze the information to provide insights beyond simple extraction
6. Include proper citations for all information
7. Note any limitations or inconsistencies in the available report data
8. Structure your response with clear sections and headers as appropriate
9. For historical data, be explicit about the timeframes being discussed

Provide two outputs:
1. STATUS_SUMMARY: A one-sentence status indicating the relevance of findings (e.g., "✅ Found detailed financial metrics in RBC Q2 2023 report" or "📄 Limited information found on specific metric").
2. DETAILED_RESEARCH: Your comprehensive synthesis structured with proper formatting and citations.

Respond using the provided function."""

    return prompt
