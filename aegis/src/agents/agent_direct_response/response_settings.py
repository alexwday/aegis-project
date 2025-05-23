# python/aegis/src/agents/agent_direct_response/response_settings.py
"""
Direct Response Agent Settings

This module defines the settings and configuration for the direct response agent,
including model capabilities and streaming settings.

This version implements advanced prompt engineering techniques:
1. CO-STAR framework (Context, Objective, Style, Tone, Audience, Response)
2. Sectioning with XML-style delimiters
3. Enhanced LLM guardrails
4. Pattern recognition instructions

Attributes:
    MODEL_CAPABILITY (str): The model capability to use ('small' or 'large')
    MAX_TOKENS (int): Maximum tokens for model response
    TEMPERATURE (float): Randomness parameter (0-1)
    SYSTEM_PROMPT (str): System prompt template defining the response agent role
"""

import logging

from ...global_prompts.project_statement import get_project_statement
from ...global_prompts.database_statement import get_database_statement
from ...global_prompts.fiscal_calendar import get_fiscal_statement
from ...global_prompts.restrictions_statement import get_restrictions_statement
from ...global_prompts.error_handling import get_error_handling_statement

# Get module logger (no configuration here - using centralized config)
logger = logging.getLogger(__name__)

# Model capability - used to get specific model based on environment
MODEL_CAPABILITY = "large"

# Model settings
MAX_TOKENS = 4096
TEMPERATURE = 0.7

# Define the direct response agent role and task
RESPONSE_ROLE = "an expert direct response agent in the IRIS workflow"

# CO-STAR Framework Components
RESPONSE_OBJECTIVE = """
Generate answers using ONLY information from the conversation history.
No external knowledge or database research.
"""

RESPONSE_STYLE = "Clear, professional, and concise."

RESPONSE_TONE = "Professional and helpful."

RESPONSE_AUDIENCE = "Financial professionals needing synthesized information from conversation history."

# Define the direct response agent task
RESPONSE_TASK = """<TASK>
Answer user queries using ONLY information from the conversation history.

<CORE_RULES>
1. Use ONLY information explicitly in the conversation - no external knowledge
2. For financial data: Must come from prior research results with citations
3. If information is insufficient: Recommend database research instead
4. Structure responses clearly with headings, bullets, or tables as needed
</CORE_RULES>

<ACCEPTABLE_RESPONSES>
- Reformatting/simplifying already-researched information
- Explaining what a previously-researched metric means  
- Combining multiple pieces of already-researched data
- Answering non-financial general questions
- Basic financial concepts IF explicitly discussed in conversation
</ACCEPTABLE_RESPONSES>

<NEVER_DO>
- Use training data for finance/accounting definitions
- Make up or approximate financial figures
- Extrapolate beyond explicit conversation content
- Answer finance questions without prior research in conversation
</NEVER_DO>

<RESPONSE_QUALITY>
Your response should:
- Directly answer the question asked
- Use clear structure and formatting
- Acknowledge limitations when information is incomplete
- Cite sources from prior research (e.g., "per Q2 2024 earnings transcript")
</RESPONSE_QUALITY>
</TASK>"""


# Construct the complete system prompt by combining the necessary statements
def construct_system_prompt():
    # Get all the required statements
    # Direct response doesn't need database details since it only uses conversation history
    project_statement = get_project_statement(level='minimal')
    fiscal_statement = get_fiscal_statement()
    database_statement = get_database_statement(level='minimal')
    restrictions_statement = get_restrictions_statement("direct_response")
    error_handling = get_error_handling_statement("default")

    # Combine into a formatted system prompt using CO-STAR framework
    prompt_parts = [
        "<CONTEXT>",
        project_statement,
        fiscal_statement,
        database_statement,
        restrictions_statement,
        "</CONTEXT>",
        "<OBJECTIVE>",
        RESPONSE_OBJECTIVE,
        "</OBJECTIVE>",
        "<STYLE>",
        RESPONSE_STYLE,
        "</STYLE>",
        "<TONE>",
        RESPONSE_TONE,
        "</TONE>",
        "<AUDIENCE>",
        RESPONSE_AUDIENCE,
        "</AUDIENCE>",
        f"You are {RESPONSE_ROLE}.",
        RESPONSE_TASK,
        error_handling,
    ]

    # Join with double newlines for readability
    return "\n\n".join(prompt_parts)


# Generate the complete system prompt
SYSTEM_PROMPT = construct_system_prompt()

logger.debug("Direct response agent settings initialized")
