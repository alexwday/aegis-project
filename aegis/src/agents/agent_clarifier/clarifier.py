# python/aegis/src/agents/agent_clarifier/clarifier.py
"""
Clarifier Agent Module

This module handles context assessment to determine if research can proceed or
if essential context is missing and must be requested from the user.

Functions:
    clarify_research_needs: Determines if essential context is needed
                           or if research can proceed

Dependencies:
    - json
    - logging
    - OpenAI connector for LLM calls
"""

import json
import logging
from typing import Tuple, Dict, Optional, Any, List

from ...chat_model.model_settings import get_model_config
from ...llm_connectors.rbc_openai import call_llm
from .clarifier_settings import (
    MAX_TOKENS,
    MODEL_CAPABILITY,
    SYSTEM_PROMPT,
    TEMPERATURE,
    TOOL_DEFINITIONS,
)

# Get module logger (no configuration here - using centralized config)
logger = logging.getLogger(__name__)

# Get model configuration based on capability
model_config = get_model_config(MODEL_CAPABILITY)
MODEL_NAME = model_config["name"]
PROMPT_TOKEN_COST = model_config["prompt_token_cost"]
COMPLETION_TOKEN_COST = model_config["completion_token_cost"]


class ClarifierError(Exception):
    """Base exception class for clarifier-related errors."""

    pass


def clarify_research_needs(
    conversation, token
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    """
    Determine if essential context is needed or create a research statement.

    Analyzes the conversation to identify:
    - User intent (what they are asking for in full context)
    - Years mentioned or inferred
    - Quarters mentioned or inferred
    - Banks mentioned or inferred

    For research statements, formats the output with each bank's parameters
    on its own line for clear presentation.

    Args:
        conversation (dict): Conversation with 'messages' key
        token (str): Authentication token for API access
            - In RBC environment: OAuth token
            - In local environment: API key

    Returns:
        Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
            - Clarifier decision dictionary with fields:
                - action: 'request_essential_context' or 'create_research_statement'
                - output: The formatted output (questions or research statement)
                - intent: The identified user intent (for research statements)
                - years: List of years identified (for research statements)
                - quarters: List of quarters identified (for research statements)
                - banks: List of banks identified (for research statements)
                - metrics: List of metrics identified (for research statements)
                - scope: 'research' for all financial queries (for compatibility)
                - is_continuation: Boolean flag for continuing research (default False)
            - Usage details dictionary for the LLM call, or None if error.

    Raises:
        ClarifierError: If there is an error in the clarification process.
    """
    usage_details = None  # Initialize usage details
    try:
        # Prepare system message with clarifier prompt
        system_message = {"role": "system", "content": SYSTEM_PROMPT}

        # Prepare messages for the API call
        messages = [system_message]
        if conversation and "messages" in conversation:
            messages.extend(conversation["messages"])

        logger.info(f"Clarifying research needs using model: {MODEL_NAME}")
        logger.info("Initiating Clarifier API call")

        # Make the API call with tool calling (non-streaming returns tuple)
        response, usage_details = call_llm(
            oauth_token=token,
            model=MODEL_NAME,
            messages=messages,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            tools=TOOL_DEFINITIONS,
            tool_choice={
                "type": "function",
                "function": {"name": "make_clarifier_decision"},
            },
            stream=False,
            prompt_token_cost=PROMPT_TOKEN_COST,
            completion_token_cost=COMPLETION_TOKEN_COST,
        )

        # Check if response object itself is valid before accessing attributes
        if not response or not hasattr(response, "choices") or not response.choices:
            raise ClarifierError("Invalid or empty response received from LLM")

        # Extract the tool call from the response
        message = response.choices[0].message
        if not message or not message.tool_calls:
            content_returned = (
                message.content if message and message.content else "No content"
            )
            logger.warning(
                f"Expected tool call but received content: {content_returned[:100]}..."
            )
            raise ClarifierError(
                "No tool call received in response, content returned instead."
            )

        tool_call = message.tool_calls[0]

        # Verify that the correct function was called
        if tool_call.function.name != "make_clarifier_decision":
            raise ClarifierError(f"Unexpected function call: {tool_call.function.name}")

        # Parse the arguments
        try:
            arguments = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError:
            raise ClarifierError(
                f"Invalid JSON in tool arguments: {tool_call.function.arguments}"
            )

        # Extract decision fields
        action = arguments.get("action")
        output = arguments.get("output")

        # New fields specific to the research parameters
        intent = arguments.get("intent")
        years = arguments.get("years", [])
        quarters = arguments.get("quarters", [])
        banks = arguments.get("banks", [])
        metrics = arguments.get("metrics", [])

        if not action:
            raise ClarifierError("Missing 'action' in tool arguments")

        if not output:
            raise ClarifierError("Missing 'output' in tool arguments")

        # Validate required fields for create_research_statement
        if action == "create_research_statement":
            if not intent:
                logger.warning("Missing 'intent' in research statement")
                intent = "Unspecified research intent"

            # Log the identified parameters
            logger.info(f"Identified intent: {intent}")
            logger.info(f"Identified years: {years}")
            logger.info(f"Identified quarters: {quarters}")
            logger.info(f"Identified banks: {banks}")
            logger.info(f"Identified metrics: {metrics}")

        # Log the clarifier decision
        logger.info(f"Clarifier decision: {action}")

        # For research statements, format the output to include the structured parameters
        if action == "create_research_statement":
            # Format intent as research statement
            formatted_intent = f"Research intent: {intent}"

            # Format parameters with each bank on its own line
            formatted_parameters = format_research_parameters(
                banks, metrics, years, quarters
            )

            # Combine into final output
            output = f"{formatted_intent}\n\nParameters:\n{formatted_parameters}"

        # Construct the decision dictionary with the new parameter fields
        decision = {
            "action": action,
            "output": output,
            "intent": intent,
            "years": years,
            "quarters": quarters,
            "banks": banks,
            "metrics": metrics,
            "scope": "research",  # Always set to 'research' for financial queries
            "is_continuation": False,  # Default to False as we don't track continuations
        }

        # Return both decision and usage details
        return decision, usage_details

    except Exception as e:
        logger.error(f"Error clarifying research needs: {str(e)}", exc_info=True)
        # Re-raise to signal failure upstream
        raise ClarifierError(f"Failed to clarify research needs: {str(e)}") from e


def format_research_parameters(
    banks: List[str], metrics: List[str], years: List[int], quarters: List[int]
) -> str:
    """
    Format research parameters in the standardized format.
    Each bank gets its own line with associated time periods and metrics.

    Args:
        banks (List[str]): List of bank identifiers
        metrics (List[str]): List of financial metrics
        years (List[int]): List of years
        quarters (List[int]): List of quarters

    Returns:
        str: Formatted parameters string with each bank on its own line
    """
    parameters = []

    for bank in banks:
        for metric in metrics:
            time_periods = []
            for year in years:
                for quarter in quarters:
                    time_periods.append(f"{year}-Q{quarter}")

            time_period_str = ", ".join(time_periods)
            parameters.append(f"{bank}[{time_period_str}]-{metric}")

    return "\n".join(parameters)
