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
                - is_continuation: Boolean flag for continuing research (default False)
            - Usage details dictionary for the LLM call, or None if error.

    Raises:
        ClarifierError: If there is an error in the clarification process.
    """
    # Input validation
    if not isinstance(conversation, dict):
        raise ClarifierError("Conversation must be a dictionary")
    if not isinstance(token, str) or not token.strip():
        raise ClarifierError("Token must be a non-empty string")
    if "messages" in conversation and not isinstance(conversation["messages"], list):
        raise ClarifierError("Conversation messages must be a list")

    usage_details = None  # Initialize usage details
    try:
        # Prepare system message with clarifier prompt
        system_message = {"role": "system", "content": SYSTEM_PROMPT}

        # Prepare messages for the API call
        messages = [system_message]
        if conversation and "messages" in conversation:
            messages.extend(conversation["messages"])

        # Log the current fiscal period for debugging
        from ...global_prompts.fiscal_calendar import get_fiscal_period

        fiscal_year, fiscal_quarter = get_fiscal_period()
        logger.info(
            f"Current fiscal period: Year {fiscal_year}, Quarter {fiscal_quarter}"
        )
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

        # Validate list types and their contents
        for field_name, field_value, expected_type in [
            ("years", years, int),
            ("quarters", quarters, int),
            ("banks", banks, str),
            ("metrics", metrics, str),
        ]:
            if not isinstance(field_value, list):
                raise ClarifierError(
                    f"{field_name} must be a list, got {type(field_value).__name__}"
                )
            for i, item in enumerate(field_value):
                if not isinstance(item, expected_type):
                    raise ClarifierError(
                        f"All {field_name} items must be {expected_type.__name__}, "
                        f"item {i} is {type(item).__name__}"
                    )

        # Validate quarters are in valid range
        for q in quarters:
            if q not in [1, 2, 3, 4]:
                raise ClarifierError(f"Quarter must be 1-4, got {q}")

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

        # For research statements, format the output as a comprehensive paragraph
        if action == "create_research_statement":
            # Create a comprehensive research statement that includes both intent and parameters
            detailed_context = format_research_parameters(
                banks, metrics, years, quarters
            )

            # Combine intent and detailed context into a single, comprehensive paragraph
            output = f"{intent}. {detailed_context}"
        # For time reference confirmations, leave the output as provided by the model
        elif action == "confirm_time_references":
            # The output will already be formatted as needed
            logger.info("Requesting confirmation of time references")

        # Construct the decision dictionary with the appropriate fields based on action
        decision = {
            "action": action,
            "output": output,
            "is_continuation": False,  # Default to False as we don't track continuations
        }

        # Only include research parameters for create_research_statement action
        if action == "create_research_statement":
            decision.update(
                {
                    "intent": intent,
                    "years": years,
                    "quarters": quarters,
                    "banks": banks,
                    "metrics": metrics,
                }
            )

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
    Format research parameters as a clear, concise paragraph that provides full context
    for the planner agent without excessive repetition. Clearly states all banks,
    quarters, years, and metrics being requested in a readable format.

    Args:
        banks (List[str]): List of bank identifiers
        metrics (List[str]): List of financial metrics
        years (List[int]): List of years
        quarters (List[int]): List of quarters

    Returns:
        str: Formatted paragraph containing complete research context
    """
    # Sort time periods chronologically
    year_quarter_pairs = []
    for year in years:
        for quarter in quarters:
            # Only include valid fiscal quarters (1-4)
            if 1 <= quarter <= 4:
                year_quarter_pairs.append((year, quarter))

    year_quarter_pairs.sort()

    # Format time periods for readability
    time_periods = [f"Q{quarter} {year}" for year, quarter in year_quarter_pairs]

    # Format metrics list
    if len(metrics) == 1:
        metrics_text = metrics[0]
    elif len(metrics) == 2:
        metrics_text = f"{metrics[0]} and {metrics[1]}"
    else:
        metrics_text = ", ".join(metrics[:-1]) + f", and {metrics[-1]}"

    # Format banks list
    if len(banks) == 1:
        banks_text = banks[0]
    elif len(banks) == 2:
        banks_text = f"{banks[0]} and {banks[1]}"
    else:
        banks_text = ", ".join(banks[:-1]) + f", and {banks[-1]}"

    # Format time periods list
    if len(time_periods) == 1:
        time_text = time_periods[0]
    elif len(time_periods) == 2:
        time_text = f"{time_periods[0]} and {time_periods[1]}"
    else:
        time_text = ", ".join(time_periods[:-1]) + f", and {time_periods[-1]}"

    # Create a concise but comprehensive paragraph
    paragraph = f"The research requires {metrics_text} data for {banks_text} across {time_text}."

    # Only add clarification if there are multiple banks AND multiple time periods to avoid confusion
    if len(banks) > 1 and len(time_periods) > 1:
        paragraph += (
            f" This applies to all specified banks across all specified time periods."
        )

    return paragraph
