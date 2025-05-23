# global_prompts/shared_examples.py
"""
Shared Examples Module

Provides common example queries and references used across multiple agents
to reduce redundancy and ensure consistency.
"""

import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_bank_references() -> str:
    """
    Get standardized bank references used across agents.
    
    Returns:
        str: Formatted bank reference list
    """
    return """<BANK_REFERENCE>
Major Canadian Banks:
- Royal Bank of Canada (RBC)
- Toronto-Dominion Bank (TD)
- Bank of Montreal (BMO)
- Canadian Imperial Bank of Commerce (CIBC)
- Bank of Nova Scotia (Scotiabank, BNS)
- National Bank of Canada (NBC, NA)

Major US Banks:
- JPMorgan Chase (JPM)
- Bank of America (BAC)
- Citigroup (C)
- Wells Fargo (WFC)
- Goldman Sachs (GS)
- Morgan Stanley (MS)
</BANK_REFERENCE>"""


def get_metric_references() -> str:
    """
    Get standardized financial metric references.
    
    Returns:
        str: Formatted metric reference list
    """
    return """<METRIC_REFERENCE>
Common Financial Metrics:
- Revenue (Total Revenue, Income)
- Net Income (Profit, Earnings)
- Earnings Per Share (EPS)
- Return on Equity (ROE)
- Return on Assets (ROA)
- Net Interest Margin (NIM)
- Efficiency Ratio
- Capital Ratio (CET1)
- Provision for Credit Losses (PCL)
</METRIC_REFERENCE>"""


def get_query_examples() -> dict:
    """
    Get categorized query examples for routing and clarification.
    
    Returns:
        dict: Dictionary of query categories with examples
    """
    return {
        "data_requests": [
            "What was TD's net income in Q2 2024?",
            "Show BMO's efficiency ratio",
            "Compare RBC and CIBC revenue"
        ],
        "management_commentary": [
            "What did the CEO say about digital strategy?",
            "Management guidance for next quarter",
            "Executive comments on market conditions"
        ],
        "trend_analysis": [
            "Revenue growth over 3 quarters",
            "Year-over-year performance",
            "How has ROE changed?"
        ],
        "basic_concepts": [
            "What's the difference between revenue and income?",
            "How is ROE calculated?",
            "What does efficiency ratio measure?"
        ],
        "follow_ups": [
            "Explain that in simpler terms",
            "What does that mean for investors?",
            "Summarize the key points"
        ]
    }


def get_time_reference_examples() -> dict:
    """
    Get examples of time reference interpretations.
    
    Returns:
        dict: Dictionary of time reference patterns and interpretations
    """
    return {
        "simple_relative": {
            "last_quarter": "The quarter immediately before current quarter",
            "same_quarter_last_year": "Same numbered quarter from previous fiscal year",
            "year_over_year": "Compare same quarters between current and previous fiscal year"
        },
        "complex_relative": {
            "last_X_quarters": "The X quarters immediately preceding current quarter (excludes current)",
            "past_X_quarters": "The X most recent quarters (includes current)",
            "quarter_over_quarter": "Comparing consecutive quarters"
        }
    }