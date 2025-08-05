# services/src/agents/agent_direct_response/response_from_conversation.py
"""
Direct Response Agent Module

This module handles direct response generation based solely on conversation context
without requiring additional database research.

Functions:
    response_from_conversation: Generate a direct response based on conversation context

Dependencies:
    - json
    - logging
    - OpenAI connector for LLM calls
"""

import logging
import os
import yaml
from typing import Generator, Dict, Any

from ...initial_setup.env_config import config
from ...llm_connectors.rbc_openai import call_llm
from ...global_prompts.project_statement import get_project_statement
from ...global_prompts.fiscal_statement import get_fiscal_statement
from ...global_prompts.database_statement import get_database_statement, get_filtered_database_statement
from ...global_prompts.restrictions_statement import get_restrictions_statement

# Get module logger (no configuration here - using centralized config)
logger = logging.getLogger(__name__)


class DirectResponseError(Exception):
    """Base exception class for direct response errors."""

    pass


# Note: get_filtered_database_statement is now imported from global_prompts


def load_agent_config(available_databases=None):
    """
    Load agent configuration from YAML file and resolve dynamic context.
    NOTE: Direct response can optionally use available_databases for filtered database_statement

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
        yaml_path = os.path.join(current_dir, "response_prompt.yaml")

        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                yaml_config = yaml.safe_load(f)
        except (OSError, IOError) as e:
            raise DirectResponseError("Configuration file could not be read") from e
        except yaml.YAMLError as e:
            raise DirectResponseError("Configuration file format is invalid") from e

        # Extract model configuration from YAML
        model_config = yaml_config.get("model", {})
        capability = model_config.get("capability", "large")  # Default fallback
        max_tokens = model_config.get("max_tokens", 4096)
        temperature = model_config.get("temperature", 0.7)

        # Extract system prompt from YAML
        system_prompt = yaml_config.get("system_prompt", "")
        if not system_prompt:
            raise DirectResponseError("System prompt not found in configuration")

        # Replace the context placeholder
        system_prompt = system_prompt.replace(
            "{{CONTEXT_START}}", f"<CONTEXT>\n{context_block}\n</CONTEXT>"
        )

        return {
            "model_capability": capability,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system_prompt": system_prompt,
        }

    except DirectResponseError:
        raise  # Re-raise specific DirectResponseError exceptions
    except Exception as e:
        logger.error("Error loading agent configuration")
        raise DirectResponseError("Failed to load agent configuration") from e


# Load configuration once at module level
try:
    _config = load_agent_config()
    MODEL_CAPABILITY = _config["model_capability"]
    MAX_TOKENS = _config["max_tokens"]
    TEMPERATURE = _config["temperature"]
    SYSTEM_PROMPT = _config["system_prompt"]

    # Get model configuration based on capability
    model_config = config.get_model_config(MODEL_CAPABILITY)
    MODEL_NAME = model_config["name"]
    PROMPT_TOKEN_COST = model_config["prompt_token_cost"]
    COMPLETION_TOKEN_COST = model_config["completion_token_cost"]


except Exception as e:
    logger.error("Failed to initialize direct response agent configuration")
    raise


def response_from_conversation(
    conversation, token, available_databases=None
) -> Generator[Any, None, None]:
    """
    Generate a direct response based solely on conversation context.

    Yields content chunks (str) and finally a dictionary containing usage details:
    {'usage_details': {'model': str, ...}}

    Args:
        conversation (dict): Conversation with 'messages' key
        token (str): Authentication token for API access
            - In RBC environment: OAuth token
        available_databases (dict, optional): Dictionary of available database configurations (filtered by user selection)

    Yields:
        str: Content chunks of the response.
        dict: The final item yielded is a dictionary {'usage_details': ...}.

    Raises:
        DirectResponseError: If there is an error in generating the response.
    """
    final_usage_details = None
    try:
        # Generate dynamic configuration with filtered databases if provided
        if available_databases is not None:
            agent_config = load_agent_config(available_databases)
            system_prompt = agent_config["system_prompt"]
        else:
            system_prompt = SYSTEM_PROMPT

        # Prepare system message with response prompt
        system_message = {"role": "system", "content": system_prompt}

        # Prepare messages for the API call
        messages = [system_message]
        if conversation and "messages" in conversation:
            messages.extend(conversation["messages"])

        logger.debug("Generating direct response")

        # Make the API call with streaming
        response_stream, _ = call_llm(
            oauth_token=token,
            model=MODEL_NAME,
            messages=messages,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            stream=True,
            prompt_token_cost=PROMPT_TOKEN_COST,
            completion_token_cost=COMPLETION_TOKEN_COST,
        )

        # Process the streaming response (which includes usage details at the end)
        for item in response_stream:
            # Check if it's the final usage dictionary
            if isinstance(item, dict) and "usage_details" in item:
                final_usage_details = item  # Capture usage details
                break  # Stop iteration after getting usage details
            # Otherwise, process content chunks
            elif (
                hasattr(item, "choices")
                and item.choices
                and item.choices[0].delta
                and item.choices[0].delta.content
            ):
                content = item.choices[0].delta.content
                yield content
            # Handle potential empty chunks or other stream elements if necessary
            # else:
            #     logger.debug("Received non-content chunk in direct response stream.")

        logger.debug("Direct response stream finished.")

        # Yield the captured usage details as the final item
        if final_usage_details:
            yield final_usage_details
        else:
            # If usage details weren't found (e.g., error in stream wrapper), yield empty/error
            logger.warning("Usage details not found in response stream")
            yield {"usage_details": {"error": "Usage data missing from stream"}}

    except DirectResponseError:
        raise  # Re-raise specific DirectResponseError exceptions
    except Exception as e:
        logger.error("Error generating direct response")
        raise DirectResponseError("Failed to generate direct response") from e
