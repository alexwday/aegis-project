# services/src/agents/agent_router/router.py
"""
Router Agent Module

This module handles routing decisions for user queries by analyzing
conversation context and determining the appropriate processing path
(direct response or research).

Functions:
    load_agent_config: Loads configuration from YAML file and resolves dynamic context
    get_routing_decision: Gets routing decision from the model via tool call

Dependencies:
    - json
    - logging
    - OpenAI connector for LLM calls
"""

import json
import logging
import os
import yaml
from typing import Tuple, Dict, Optional, Any

from ...initial_setup.env_config import config
from ...llm_connectors.rbc_openai import call_llm
from ...global_prompts.project_statement import get_project_statement
from ...global_prompts.fiscal_statement import get_fiscal_statement
from ...global_prompts.database_statement import get_database_statement, get_filtered_database_statement
from ...global_prompts.restrictions_statement import get_restrictions_statement

# Get module logger (no configuration here - using centralized config)
logger = logging.getLogger(__name__)


class RouterError(Exception):
    """Base exception class for router-related errors."""

    pass


# Note: get_filtered_database_statement is now imported from global_prompts


def load_agent_config(available_databases=None):
    """
    Load agent configuration from YAML file and resolve dynamic context.
    NOTE: Router can optionally use available_databases for filtered database_statement

    Args:
        available_databases (dict, optional): Dictionary of available database configurations

    Returns:
        dict: Configuration dictionary with resolved system prompt and settings
    """
    try:
        # Build context statements dynamically
        context_parts = [get_project_statement(), get_fiscal_statement()]

        # Handle database statement - use filtered version if available_databases provided
        if available_databases is not None:
            context_parts.append(get_filtered_database_statement(available_databases))
        else:
            context_parts.append(get_database_statement())

        context_parts.append(get_restrictions_statement())

        # Build the complete context block
        context_block = "\n\n".join(context_parts)

        # Read and parse the YAML file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        yaml_path = os.path.join(current_dir, "router_prompt.yaml")

        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                yaml_config = yaml.safe_load(f)
        except (OSError, IOError) as e:
            raise RouterError("Configuration file could not be read") from e
        except yaml.YAMLError as e:
            raise RouterError("Configuration file format is invalid") from e

        # Extract model configuration from YAML
        model_config = yaml_config.get("model", {})
        capability = model_config.get("capability", "small")  # Default fallback
        max_tokens = model_config.get("max_tokens", 4096)
        temperature = model_config.get("temperature", 0.0)

        # Extract system prompt from YAML
        system_prompt = yaml_config.get("system_prompt", "")
        if not system_prompt:
            raise RouterError("System prompt not found in configuration")

        # Replace the context placeholder
        system_prompt = system_prompt.replace(
            "{{CONTEXT_START}}", f"<CONTEXT>\n{context_block}\n</CONTEXT>"
        )

        # Define tools (hardcoded for simplicity)
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "route_query",
                    "description": "Route the user query to the appropriate function based on conversation analysis",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "function_name": {
                                "type": "string",
                                "description": "The function to route to based on conversation context analysis",
                                "enum": [
                                    "response_from_conversation",
                                    "research_from_database",
                                ],
                            },
                        },
                        "required": ["function_name"],
                    },
                },
            }
        ]

        return {
            "model_capability": capability,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system_prompt": system_prompt,
            "tool_definitions": tools,
        }

    except RouterError:
        raise  # Re-raise specific RouterError exceptions
    except Exception as e:
        logger.error("Error loading agent configuration")
        raise RouterError("Failed to load agent configuration") from e


# Load configuration once at module level
try:
    _config = load_agent_config()
    MODEL_CAPABILITY = _config["model_capability"]
    MAX_TOKENS = _config["max_tokens"]
    TEMPERATURE = _config["temperature"]
    SYSTEM_PROMPT = _config["system_prompt"]
    TOOL_DEFINITIONS = _config["tool_definitions"]

    # Get model configuration based on capability
    model_config = config.get_model_config(MODEL_CAPABILITY)
    MODEL_NAME = model_config["name"]
    PROMPT_TOKEN_COST = model_config["prompt_token_cost"]
    COMPLETION_TOKEN_COST = model_config["completion_token_cost"]


except Exception as e:
    logger.error("Failed to initialize router agent configuration")
    raise


def get_routing_decision(
    conversation, token, available_databases=None
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    """
    Get routing decision from the model using a tool call.

    Args:
        conversation (dict): Conversation with 'messages' key
        token (str): Authentication token for API access
            - In RBC environment: OAuth token
            - In local environment: API key
        available_databases (dict, optional): Dictionary of available database configurations (filtered by user selection)

    Returns:
        Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
            - Routing decision dictionary with 'function_name' key.
            - Usage details dictionary for the LLM call, or None if error/not applicable.

    Raises:
        RouterError: If there is an error in getting the routing decision.
    """
    usage_details = None  # Initialize usage details
    try:
        # Generate dynamic configuration with filtered databases if provided
        if available_databases is not None:
            agent_config = load_agent_config(available_databases)
            system_prompt = agent_config["system_prompt"]
        else:
            system_prompt = SYSTEM_PROMPT

        # Prepare system message with router prompt
        system_message = {"role": "system", "content": system_prompt}

        # Prepare the messages for the API call
        messages = [system_message]
        if conversation and "messages" in conversation:
            messages.extend(conversation["messages"])

        logger.debug(f"Getting routing decision using model: {MODEL_NAME}")

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
                "function": {"name": "route_query"},
            },  # Force tool call
            stream=False,
            prompt_token_cost=PROMPT_TOKEN_COST,
            completion_token_cost=COMPLETION_TOKEN_COST,
        )

        # Check if response object itself is valid before accessing attributes
        if not response or not hasattr(response, "choices") or not response.choices:
            raise RouterError("Invalid or empty response received from LLM")

        # Extract the tool call from the response
        message = response.choices[0].message
        if not message or not message.tool_calls:
            # Handle cases where the model might return content instead of a tool call
            logger.warning("Expected tool call but received content instead")
            # Decide on fallback behavior - perhaps default routing or raise error
            # For now, raise error as tool call is expected
            raise RouterError(
                "No tool call received in response, content returned instead."
            )

        tool_call = message.tool_calls[0]

        # Verify that the correct function was called
        if tool_call.function.name != "route_query":
            msg = f"Unexpected function call: {tool_call.function.name}"
            raise RouterError(msg)

        # Parse the arguments
        try:
            arguments = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError as e:
            raise RouterError("Invalid JSON in tool call arguments") from e

        # Extract function name only
        function_name = arguments.get("function_name")

        if not function_name:
            raise RouterError("Missing 'function_name' in tool arguments")

        logger.debug(f"Routing decision: {function_name}")

        # Return both decision and usage details
        return {"function_name": function_name}, usage_details

    except RouterError:
        raise  # Re-raise specific RouterError exceptions
    except Exception as e:
        logger.error("Error getting routing decision")
        raise RouterError("Failed to get routing decision") from e
