# services/src/global_prompts/restrictions_statement.py
"""
Restrictions Statement Utility

Provides statements about output restrictions and guidelines that should
be applied across all agent responses for compliance and quality control.
"""

import logging

logger = logging.getLogger(__name__)


def get_compliance_restrictions() -> str:
    """
    Generate a statement about compliance restrictions for outputs.
    Uses XML-style delimiters for better sectioning.

    Returns:
        str: Formatted compliance restrictions statement
    """
    try:
        statement = """<COMPLIANCE_RESTRICTIONS>
<INVESTMENT_DISCLAIMER>No investment advice; provide market data and analysis only.</INVESTMENT_DISCLAIMER>

<VERIFICATION_REQUIREMENT>Include disclaimer: Information is based on available financial data. Users should verify current data and consult financial advisors for investment decisions.</VERIFICATION_REQUIREMENT>

<DATA_ACCURACY>Emphasize that data is from specific time periods and may not reflect current market conditions.</DATA_ACCURACY>

<PUBLIC_INFORMATION>All data is from public sources (earnings calls, quarterly reports, etc.).</PUBLIC_INFORMATION>

<OUT_OF_SCOPE>
If a query falls outside available financial data (e.g., private company data, future predictions, investment recommendations):
- Clearly state inability to provide such information
- Explain the system's focus on historical financial data analysis
- Suggest what data is available instead
- Do not attempt to answer out-of-scope questions
</OUT_OF_SCOPE>

<CRITICAL_DATA_SOURCING>
Base responses **EXCLUSIVELY** on information from:
- The current user query
- Retrieved financial database documents from this system
- Conversation history *if that history itself contains information clearly sourced from the above*

**ABSOLUTELY NO speculation, predictions, or assumptions beyond the provided financial data.**

This applies to ALL agents, including Direct Response.
</CRITICAL_DATA_SOURCING>
</COMPLIANCE_RESTRICTIONS>"""

        return statement
    except Exception as e:
        logger.debug("Error generating compliance restrictions")
        # Fallback statement in case of errors
        return "Responses must include appropriate disclaimers and should not provide investment advice."


def get_quality_guidelines() -> str:
    """
    Generate a statement about output quality guidelines.
    Uses XML-style delimiters for better sectioning.

    Returns:
        str: Formatted quality guidelines statement
    """
    try:
        statement = """<QUALITY_GUIDELINES>
<STRUCTURE>Structure responses clearly with sections for different metrics/time periods.</STRUCTURE>

<CITATIONS>Cite specific sources (e.g., "RBC Q3 2024 Earnings Call, Page 5") when referencing data.</CITATIONS>

<COMPARISONS>For comparative analysis: Present data side-by-side with clear time period labels.</COMPARISONS>

<METRICS>Use standard financial metrics and define any specialized terms.</METRICS>

<TIME_CONTEXT>Always specify the time period (quarter/year) for any data point.</TIME_CONTEXT>

<MULTIPLE_SOURCES>When data comes from multiple sources, clearly distinguish between them.</MULTIPLE_SOURCES>

<SOURCE_ATTRIBUTION>Always note which database/document type provided the information.</SOURCE_ATTRIBUTION>
</QUALITY_GUIDELINES>"""

        return statement
    except Exception as e:
        logger.debug("Error generating quality guidelines")
        # Fallback statement in case of errors
        return "Responses should be well-structured, include source citations, and specify time periods."


def get_confidence_signaling() -> str:
    """
    Generate guidelines for confidence signaling in responses.

    Returns:
        str: Formatted confidence signaling guidelines
    """
    try:
        statement = """<CONFIDENCE_SIGNALING>
When presenting financial data, indicate your level of confidence based on the sources:

<HIGH_CONFIDENCE>
Use when: Data comes directly from official reports or transcripts with clear attribution
Signal with: Direct, unqualified statements
Example: "Royal Bank of Canada reported net income of $4.1 billion in Q3 2024."
</HIGH_CONFIDENCE>

<MEDIUM_CONFIDENCE>
Use when: Data requires interpretation or comes from supplementary sources
Signal with: Measured language with mild qualifiers
Example: "Based on the supplementary package data, peer comparisons indicate..."
</MEDIUM_CONFIDENCE>

<LOW_CONFIDENCE>
Use when: Data is incomplete or requires significant interpretation
Signal with: Explicit uncertainty markers
Example: "Available data suggests, though complete information was not found..."
</LOW_CONFIDENCE>

<NO_CONFIDENCE>
Use when: No relevant data is found for the specific query
Signal with: Clear statements of data unavailability
Example: "The available databases do not contain data for this specific metric/time period."
</NO_CONFIDENCE>
</CONFIDENCE_SIGNALING>"""

        return statement
    except Exception as e:
        logger.debug("Error generating confidence signaling guidelines")
        # Fallback statement in case of errors
        return "<CONFIDENCE_SIGNALING>Indicate your level of confidence in responses based on data availability and quality.</CONFIDENCE_SIGNALING>"


def get_restrictions_statement() -> str:
    """
    Generate a combined restrictions and guidelines statement for use in prompts.
    Includes confidence signaling guidelines.

    Returns:
        str: Formatted restrictions statement combining compliance, quality, and confidence guidelines
    """
    try:
        compliance = get_compliance_restrictions()
        quality = get_quality_guidelines()
        confidence = get_confidence_signaling()

        combined_statement = f"""<RESTRICTIONS_AND_GUIDELINES>
{compliance}

{quality}

{confidence}
</RESTRICTIONS_AND_GUIDELINES>"""
        return combined_statement
    except Exception as e:
        logger.debug("Error generating combined restrictions statement")
        # Fallback combined statement
        return """<RESTRICTIONS_AND_GUIDELINES>
Responses must include appropriate disclaimers and should not provide investment advice. 
All outputs should be well-structured, reference data sources, and specify time periods.
</RESTRICTIONS_AND_GUIDELINES>"""