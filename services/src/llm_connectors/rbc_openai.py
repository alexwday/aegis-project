# services/src/llm_connectors/rbc_openai.py
"""
OpenAI Connector Module

This module provides secure connectors to the OpenAI API that handle
chat completions and embeddings. It works in both RBC and local environments
with comprehensive error handling, retry logic, and cost tracking.

Functions:
    calculate_cost: Calculates token usage costs using Decimal precision
    call_llm: Makes chat completion calls (streaming and non-streaming)
    call_llm_embedding: Makes embedding calls

Examples:
    # Chat completion
    response, usage = call_llm(
        oauth_token=token,
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello"}],
        prompt_token_cost=0.00003,
        completion_token_cost=0.00006
    )

    # Streaming chat
    stream, _ = call_llm(
        oauth_token=token,
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello"}],
        stream=True,
        prompt_token_cost=0.00003,
        completion_token_cost=0.00006
    )
    for chunk in stream:
        if 'usage_details' in chunk:
            usage = chunk['usage_details']
        else:
            content = chunk.choices[0].delta.content

    # Embeddings
    response, usage = call_llm_embedding(
        oauth_token=token,
        model="text-embedding-3-small",
        input="Hello world",
        prompt_token_cost=0.00002
    )

Dependencies:
    - openai
    - logging
    - time
    - decimal
"""

import logging
import time
from decimal import Decimal
from typing import Any, Dict, Iterator, Optional, Tuple, Union

from openai import (
    OpenAI,
    OpenAIError,
    RateLimitError,
    AuthenticationError,
    APIConnectionError,
)

from ..initial_setup.env_config import config

# Get settings from config - defer validation to runtime
MAX_RETRY_ATTEMPTS = config.MAX_RETRY_ATTEMPTS
REQUEST_TIMEOUT = config.REQUEST_TIMEOUT
RETRY_DELAY_SECONDS = config.RETRY_DELAY_SECONDS

def _get_base_url():
    """Get and validate BASE_URL at runtime."""
    base_url = config.BASE_URL
    if not base_url:
        raise ValueError("BASE_URL not configured in environment")
    return base_url

# Get module logger
logger = logging.getLogger(__name__)


class OpenAIConnectorError(Exception):
    """Base exception class for OpenAI connector errors."""


def calculate_cost(
    prompt_tokens: int,
    completion_tokens: int,
    prompt_token_cost: float,
    completion_token_cost: float,
) -> float:
    """
    Calculate total cost based on token usage and per-token costs.

    Token costs are specified per 1,000 tokens (industry standard).
    For example, if prompt_token_cost=0.03, that's $0.03 per 1K tokens.

    Args:
        prompt_tokens (int): Number of prompt tokens used
        completion_tokens (int): Number of completion tokens used
        prompt_token_cost (float): Cost per 1K prompt tokens in USD
        completion_token_cost (float): Cost per 1K completion tokens in USD

    Returns:
        float: Total cost in USD with financial precision
    """
    # Use Decimal for financial calculations to avoid floating point errors
    prompt_cost = (Decimal(str(prompt_tokens)) / 1000) * Decimal(str(prompt_token_cost))
    completion_cost = (Decimal(str(completion_tokens)) / 1000) * Decimal(
        str(completion_token_cost)
    )
    total_cost = prompt_cost + completion_cost
    return float(total_cost)


def call_llm(
    oauth_token: str,
    prompt_token_cost: float = 0,
    completion_token_cost: float = 0,
    **params,
) -> Tuple[Union[Any, Iterator[Any]], Optional[Dict[str, Any]]]:
    """
    Makes a chat completion call to the OpenAI API.

    Returns a tuple for consistent interface:
    - Non-streaming: (ChatCompletion, usage_details_dict)
    - Streaming: (Iterator, None) - usage details yielded as final chunk

    Args:
        oauth_token (str):
            - In RBC environment: OAuth token for API authentication
            - In local environment: OpenAI API key
        prompt_token_cost (float): Cost per 1K prompt tokens in USD
        completion_token_cost (float): Cost per 1K completion tokens in USD
        **params: Parameters to pass to the OpenAI API
            Required parameters:
                - model (str): The model to use
                - messages (list): The messages to send to the model
            Optional parameters:
                - stream (bool): Whether to stream the response
                - tools (list): Tool definitions for tool calls
                - tool_choice (dict/str): Tool choice specification
                - temperature (float): Randomness parameter
                - max_tokens (int): Maximum tokens for model response

    Returns:
        Tuple[Union[ChatCompletion, Iterator], Optional[Dict]]:
            - Non-streaming: (response_object, usage_details)
            - Streaming: (iterator, None) - usage in final chunk as:
              {'usage_details': {'model': str, 'prompt_tokens': int, ...}}

    Raises:
        OpenAIConnectorError: If the API call fails after all retry attempts
        ValueError: If required parameters are missing
    """
    if not params.get("model") or not params.get("messages"):
        raise ValueError("Both 'model' and 'messages' parameters are required")

    # Security: Validate messages structure
    messages = params.get("messages", [])
    if not isinstance(messages, list) or not all(
        isinstance(msg, dict) and "role" in msg and "content" in msg for msg in messages
    ):
        raise ValueError("Messages must be a list of dicts with 'role' and 'content'")

    attempts = 0
    last_exception: Optional[Exception] = None
    call_start_time = time.time()

    # Create the OpenAI client
    client = OpenAI(api_key=oauth_token, base_url=_get_base_url())

    logger.info("Making chat completion API call to %s", params.get("model", "unknown"))

    # Set timeout if not provided
    if "timeout" not in params:
        params["timeout"] = REQUEST_TIMEOUT

    # Handle streaming option
    is_streaming = params.get("stream", False)
    if is_streaming:
        # Ensure stream_options includes usage for the final chunk
        params["stream_options"] = {"include_usage": True}

    # Capture model name for usage tracking
    model_name = params.get("model", "unknown")

    while attempts < MAX_RETRY_ATTEMPTS:
        attempt_start_time = time.time()
        attempts += 1

        try:
            # Make the chat completion API call
            api_response = client.chat.completions.create(**params)
            attempt_response_time_ms = int((time.time() - attempt_start_time) * 1000)

            if is_streaming:
                # Return the stream wrapper
                return (
                    _stream_wrapper(
                        stream_iterator=api_response,
                        model_name=model_name,
                        prompt_token_cost=prompt_token_cost,
                        completion_token_cost=completion_token_cost,
                        call_start_time=call_start_time,
                    ),
                    None,
                )

            # Calculate usage details for non-streaming
            usage_details = None
            if hasattr(api_response, "usage") and api_response.usage:
                prompt_tokens = api_response.usage.prompt_tokens or 0
                completion_tokens = api_response.usage.completion_tokens or 0
                cost = calculate_cost(
                    prompt_tokens,
                    completion_tokens,
                    prompt_token_cost,
                    completion_token_cost,
                )
                usage_details = {
                    "model": model_name,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "cost": cost,
                    "response_time_ms": attempt_response_time_ms,
                }

            return api_response, usage_details

        except AuthenticationError as e:
            # Don't retry authentication errors
            logger.error("Authentication failed: %s", str(e))
            raise OpenAIConnectorError(f"Authentication failed: {str(e)}") from e

        except RateLimitError as e:
            last_exception = e
            # Use exponential backoff for rate limits
            retry_delay = RETRY_DELAY_SECONDS * (2 ** (attempts - 1))
            attempt_time_secs = time.time() - attempt_start_time
            logger.warning(
                "Rate limit hit on attempt %d after %.2f seconds. "
                "Retrying in %.2f seconds: %s",
                attempts,
                attempt_time_secs,
                retry_delay,
                str(e),
            )

            if attempts < MAX_RETRY_ATTEMPTS:
                time.sleep(retry_delay)

        except (APIConnectionError, OpenAIError) as e:
            last_exception = e
            attempt_time_secs = time.time() - attempt_start_time
            logger.warning(
                "API call attempt %d failed after %.2f seconds: %s - %s",
                attempts,
                attempt_time_secs,
                type(e).__name__,
                str(e),
            )

            if attempts < MAX_RETRY_ATTEMPTS:
                time.sleep(RETRY_DELAY_SECONDS)

    # If we've exhausted all retries, raise the last exception
    logger.error("Failed to complete chat completion call after %d attempts", attempts)
    raise OpenAIConnectorError(
        f"Failed to complete OpenAI API call: {str(last_exception)}"
    )


def call_llm_embedding(
    oauth_token: str,
    prompt_token_cost: float = 0,
    **params,
) -> Tuple[Any, Optional[Dict[str, Any]]]:
    """
    Makes an embedding call to the OpenAI API.

    Args:
        oauth_token (str): OAuth token (RBC) or API key (local)
        prompt_token_cost (float): Cost per 1K input tokens in USD
        **params: Parameters to pass to the OpenAI embeddings API
            Required parameters:
                - model (str): The embedding model to use
                - input (str|list): The input text(s) to embed
            Optional parameters:
                - dimensions (int): Number of dimensions for the embedding
                - encoding_format (str): Format for the embedding

    Returns:
        Tuple[CreateEmbeddingResponse, Optional[Dict]]:
            (embedding_response, usage_details)

    Raises:
        OpenAIConnectorError: If the API call fails after all retry attempts
        ValueError: If required parameters are missing
    """
    if not params.get("model") or not params.get("input"):
        raise ValueError("Both 'model' and 'input' parameters are required")

    attempts = 0
    last_exception: Optional[Exception] = None

    # Create the OpenAI client
    client = OpenAI(api_key=oauth_token, base_url=_get_base_url())

    logger.info("Making embedding API call to %s", params.get("model", "unknown"))

    # Set timeout if not provided
    if "timeout" not in params:
        params["timeout"] = REQUEST_TIMEOUT

    # Extract embedding-specific parameters
    embedding_params = {
        "input": params.get("input"),
        "model": params.get("model"),
        "dimensions": params.get("dimensions"),
        "encoding_format": params.get("encoding_format"),
        "timeout": params.get("timeout", REQUEST_TIMEOUT),
    }
    # Filter out None values
    embedding_params = {k: v for k, v in embedding_params.items() if v is not None}

    model_name = params.get("model", "unknown")

    while attempts < MAX_RETRY_ATTEMPTS:
        attempt_start_time = time.time()
        attempts += 1

        try:
            # Make the embedding API call
            api_response = client.embeddings.create(**embedding_params)
            attempt_response_time_ms = int((time.time() - attempt_start_time) * 1000)

            # Calculate usage details
            usage_details = None
            if hasattr(api_response, "usage") and api_response.usage:
                prompt_tokens = api_response.usage.prompt_tokens or 0
                cost = calculate_cost(prompt_tokens, 0, prompt_token_cost, 0)
                usage_details = {
                    "model": model_name,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": 0,
                    "cost": cost,
                    "response_time_ms": attempt_response_time_ms,
                }

            return api_response, usage_details

        except AuthenticationError as e:
            # Don't retry authentication errors
            logger.error("Authentication failed: %s", str(e))
            raise OpenAIConnectorError(f"Authentication failed: {str(e)}") from e

        except RateLimitError as e:
            last_exception = e
            # Use exponential backoff for rate limits
            retry_delay = RETRY_DELAY_SECONDS * (2 ** (attempts - 1))
            attempt_time_secs = time.time() - attempt_start_time
            logger.warning(
                "Rate limit hit on attempt %d after %.2f seconds. "
                "Retrying in %.2f seconds: %s",
                attempts,
                attempt_time_secs,
                retry_delay,
                str(e),
            )

            if attempts < MAX_RETRY_ATTEMPTS:
                time.sleep(retry_delay)

        except (APIConnectionError, OpenAIError) as e:
            last_exception = e
            attempt_time_secs = time.time() - attempt_start_time
            logger.warning(
                "API call attempt %d failed after %.2f seconds: %s - %s",
                attempts,
                attempt_time_secs,
                type(e).__name__,
                str(e),
            )

            if attempts < MAX_RETRY_ATTEMPTS:
                time.sleep(RETRY_DELAY_SECONDS)

    # If we've exhausted all retries, raise the last exception
    logger.error("Failed to complete embedding call after %d attempts", attempts)
    raise OpenAIConnectorError(
        f"Failed to complete OpenAI embedding call: {str(last_exception)}"
    )


def _stream_wrapper(
    stream_iterator: Iterator,
    model_name: str,
    prompt_token_cost: float,
    completion_token_cost: float,
    call_start_time: float,
) -> Iterator:
    """
    Wraps the OpenAI stream iterator to handle usage statistics and error handling.

    The final yielded item will always be:
    {'usage_details': {'model': str, 'prompt_tokens': int, ...}}

    Args:
        stream_iterator (Iterator): The streaming response from OpenAI API
        model_name (str): Name of the model being used
        prompt_token_cost (float): Cost per prompt token
        completion_token_cost (float): Cost per completion token
        call_start_time (float): Start time of the API call

    Yields:
        Iterator: Stream chunks followed by usage statistics
    """
    final_usage_data = None

    try:
        for chunk in stream_iterator:
            yield chunk
            # The final chunk in streams with include_usage=True contains usage stats
            if hasattr(chunk, "usage") and chunk.usage:
                final_usage_data = chunk.usage
    finally:
        # Calculate total duration from the initial call start
        total_response_time_ms = int((time.time() - call_start_time) * 1000)

        # Process and yield the final usage details
        if final_usage_data:
            prompt_tokens = final_usage_data.prompt_tokens or 0
            completion_tokens = final_usage_data.completion_tokens or 0
            cost = calculate_cost(
                prompt_tokens,
                completion_tokens,
                prompt_token_cost,
                completion_token_cost,
            )
            usage_details = {
                "model": model_name,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "cost": cost,
                "response_time_ms": total_response_time_ms,
            }
            # Yield the usage details as the very last item
            yield {"usage_details": usage_details}
        else:
            logger.warning(
                "Stream finished, but no usage data found. Cannot report usage."
            )
            # Yield usage dict with error indicator
            yield {
                "usage_details": {
                    "model": model_name,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "cost": 0.0,
                    "response_time_ms": total_response_time_ms,
                    "error": "Usage data missing from stream",
                }
            }
