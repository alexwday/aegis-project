# financial_transcripts/content_synthesis_prompt.py
"""
Content Synthesis Prompt for Financial Transcripts

This module provides prompt templates for synthesizing information
from earnings call transcript content.
"""

import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_content_synthesis_prompt(query: str, content: str) -> str:
    """
    Generate a prompt for synthesizing content from financial transcripts.

    Args:
        query: The original user query
        content: Formatted transcript sections to synthesize

    Returns:
        str: Formatted prompt for content synthesis
    """
    prompt = f"""Your task is to synthesize information from financial earnings call transcripts to answer a user's question. 

User Question: {query}

Transcript Content:
{content}

SYNTHESIS INSTRUCTIONS:
1. Create a detailed, well-structured response that directly addresses the user's question
2. Cite specific sections with bank name, date, quarter, and speaker when relevant
3. Include any relevant quotes from executives, using exact wording when possible
4. Analyze the information to provide insights beyond simple extraction
5. For financial figures, clearly indicate the time period and context
6. Include proper attribution for all information
7. Note any limitations in the available transcript data
8. Structure your response with clear sections and headers as appropriate

Provide two outputs:
1. STATUS_SUMMARY: A one-sentence status indicating the relevance of findings (e.g., "✅ Found detailed discussion of capital allocation in RBC Q2 2023 call" or "📄 Limited information found on specific topic").
2. DETAILED_RESEARCH: Your comprehensive synthesis structured with proper formatting and citations.

Respond using the provided function."""

    return prompt
