# financial_benchmarking/catalog_selection_prompt.py
"""
Catalog Selection Prompt for Financial Benchmarking

This module provides prompt templates for selecting relevant
benchmarking datasets from the catalog.
"""

import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_catalog_selection_prompt(query: str, catalog: str) -> str:
    """
    Generate a prompt for selecting relevant benchmarking datasets from the catalog.

    Args:
        query: The original user query
        catalog: Formatted catalog of available benchmarking datasets

    Returns:
        str: Formatted prompt for document selection
    """
    prompt = f"""Your task is to select the most relevant financial benchmarking datasets based on a user query. 

User Query: {query}

Available Benchmarking Datasets:
{catalog}

INSTRUCTIONS:
1. Select the benchmarking datasets that are most likely to contain information relevant to the query
2. Consider specific financial metrics, fiscal quarters/years, and bank names mentioned in the query
3. For ratio-specific queries, prioritize datasets containing those specific metrics
4. For time-period specific analysis, select datasets from relevant reporting periods
5. For bank comparisons, select benchmarking datasets that enable direct comparison
6. Return only Document IDs of the selected datasets

Provide your answer as a JSON array of document IDs only, like this: ["12345", "67890"]

If no relevant datasets can be identified, return an empty array: []"""

    return prompt
