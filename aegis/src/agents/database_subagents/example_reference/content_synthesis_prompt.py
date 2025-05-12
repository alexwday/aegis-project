# financial_benchmarking/content_synthesis_prompt.py
"""
Content Synthesis Prompt for Financial Benchmarking

This module provides prompt templates for synthesizing information
from financial benchmarking data.
"""

import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_content_synthesis_prompt(query: str, content: str) -> str:
    """
    Generate a prompt for synthesizing content from financial benchmarking data.

    Args:
        query: The original user query
        content: Formatted benchmarking data to synthesize

    Returns:
        str: Formatted prompt for content synthesis
    """
    prompt = f"""Your task is to synthesize information from financial benchmarking data of major banks to answer a user's question. 

User Question: {query}

Benchmarking Data:
{content}

SYNTHESIS INSTRUCTIONS:
1. Create a detailed, well-structured response that directly addresses the user's question
2. Focus on comparative analysis across banks or time periods as appropriate
3. For financial figures and ratios, provide context on what they mean and how they compare
4. Highlight notable trends, outliers, or patterns in the data
5. When comparing metrics, clearly indicate relative performance (e.g., ranking, percentage differences)
6. For time-series data, note important changes (QoQ, YoY) and potential reasons if indicated
7. Include exact metrics with proper attribution to specific banks and time periods
8. Structure your response with clear sections, potentially suggesting tables or charts where helpful
9. Note any limitations or inconsistencies in the available benchmark data

Provide two outputs:
1. STATUS_SUMMARY: A one-sentence status indicating the relevance of findings (e.g., "✅ Found comparative data for ROE across 5 major banks" or "📄 Limited comparative metrics available for requested ratio").
2. DETAILED_RESEARCH: Your comprehensive synthesis structured with proper formatting, comparisons, and analysis.

Respond using the provided function."""

    return prompt
