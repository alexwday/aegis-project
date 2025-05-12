# financial_transcripts/catalog_selection_prompt.py
"""
Catalog Selection Prompt for Financial Transcripts

This module provides prompt templates for selecting relevant
transcript documents from the catalog.
"""

import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_catalog_selection_prompt(query: str, catalog: str) -> str:
    """
    Generate a prompt for selecting relevant transcript documents from the catalog.

    Args:
        query: The original user query
        catalog: Formatted catalog of available transcript documents

    Returns:
        str: Formatted prompt for document selection
    """
    prompt = f"""Your task is to select the most relevant financial earnings call transcript documents based on a user query. 

User Query: {query}

Available Transcript Documents:
{catalog}

INSTRUCTIONS:
1. Select the transcript documents that are most likely to contain information relevant to the query
2. Consider bank names, fiscal quarters/years, and topics mentioned in the query
3. For date-specific queries, prioritize transcripts from the relevant time periods
4. For comparisons across banks, select relevant transcripts from each bank mentioned
5. For topic-specific queries, select transcripts likely to discuss those topics
6. Return only Document IDs of the selected documents

Provide your answer as a JSON array of document IDs only, like this: ["12345", "67890"]

If no relevant documents can be identified, return an empty array: []"""

    return prompt
