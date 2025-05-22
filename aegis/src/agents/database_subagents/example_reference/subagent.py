# public_benchmarking/subagent.py
"""
Financial Benchmarking Subagent

This module handles queries to the Financial Benchmarking database,
including catalog retrieval, dataset selection, data retrieval,
and response synthesis.

Functions:
    query_database_sync: Synchronously query the Financial Benchmarking database
"""

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple, Union, cast

# Define response types consistent with database_router
MetadataResponse = List[Dict[str, Any]]
ResearchResponse = Dict[str, str]  # Dict with detailed_research and status_summary
DatabaseResponse = Union[MetadataResponse, ResearchResponse]
SubagentResult = Tuple[DatabaseResponse, Optional[List[str]]]  # result + doc_ids

from ....chat_model.model_settings import ENVIRONMENT, get_model_config
from ....initial_setup.db_config import connect_to_db
from ....llm_connectors.rbc_openai import call_llm
from .catalog_selection_prompt import get_catalog_selection_prompt
from .content_synthesis_prompt import get_content_synthesis_prompt

# Get module logger
logger = logging.getLogger(__name__)

# Define the tool schema for research synthesis
SYNTHESIS_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "synthesize_research_findings",
        "description": "Synthesizes research findings from provided benchmarking data and generates a status summary.",
        "parameters": {
            "type": "object",
            "properties": {
                "status_summary": {
                    "type": "string",
                    "description": "Concise status summary (1 sentence) indicating finding relevance (e.g., '✅ Found direct comparison data.', '📄 No relevant metrics found.').",
                },
                "detailed_research": {
                    "type": "string",
                    "description": "Detailed, structured markdown report synthesizing information from benchmark datasets, including data analysis and comparative insights.",
                },
            },
            "required": ["status_summary", "detailed_research"],
        },
    },
}


# For now, we'll use placeholder functions to simulate the database interactions
# In a real implementation, these would connect to actual databases


def format_catalog_for_llm(catalog_records: List[Dict[str, Any]]) -> str:
    """
    Format the catalog records into a string optimized for LLM comprehension.
    """
    formatted_catalog = ""
    for record in catalog_records:
        doc_id = record.get("id", "unknown")
        doc_name = record.get("document_name", "Untitled")
        doc_desc = record.get("document_description", "No description available")
        formatted_catalog += f"Document ID: {doc_id}\n"
        formatted_catalog += f"Document Name: {doc_name}\n"
        formatted_catalog += f"Document Description: {doc_desc}\n\n"
    return formatted_catalog.strip()


def format_benchmarking_data_for_llm(datasets: List[Dict[str, Any]]) -> str:
    """
    Format retrieved benchmarking datasets into a string optimized for LLM analysis.
    """
    formatted_data = ""
    for dataset in datasets:
        dataset_name = dataset.get("dataset_name", "Untitled Dataset")
        formatted_data += f"# {dataset_name}\n\n"

        # Format metadata if available
        metadata = dataset.get("metadata", {})
        if metadata:
            formatted_data += "## Dataset Metadata\n\n"
            for key, value in metadata.items():
                formatted_data += f"- **{key}**: {value}\n"
            formatted_data += "\n"

        # Format metrics data
        metrics = dataset.get("metrics", [])
        if metrics:
            formatted_data += "## Comparative Metrics\n\n"
            for metric in metrics:
                metric_name = metric.get("metric_name", "Unnamed Metric")
                metric_description = metric.get("description", "")
                formatted_data += f"### {metric_name}\n"
                if metric_description:
                    formatted_data += f"{metric_description}\n\n"

                # Format bank comparisons
                comparisons = metric.get("comparisons", [])
                if comparisons:
                    formatted_data += "| Bank | Value | YoY Change | QoQ Change |\n"
                    formatted_data += "|------|-------|-----------|-----------|\n"
                    for comparison in comparisons:
                        bank = comparison.get("bank", "Unknown")
                        value = comparison.get("value", "N/A")
                        yoy = comparison.get("yoy_change", "N/A")
                        qoq = comparison.get("qoq_change", "N/A")
                        formatted_data += f"| {bank} | {value} | {yoy} | {qoq} |\n"

                formatted_data += "\n"

        # Format trend data if available
        trends = dataset.get("trends", [])
        if trends:
            formatted_data += "## Trend Analysis\n\n"
            for trend in trends:
                trend_name = trend.get("trend_name", "Unnamed Trend")
                trend_description = trend.get("description", "")
                formatted_data += f"### {trend_name}\n"
                if trend_description:
                    formatted_data += f"{trend_description}\n\n"

        formatted_data += "---\n\n"

    return formatted_data.strip()


# LLM interaction helper
def get_completion(
    capability: str,
    prompt: str,
    max_tokens: int = 1000,
    temperature: float = 0.7,
    token: Optional[str] = None,
    database_name: Optional[str] = None,
    **kwargs: Any,  # Accept additional kwargs for tools, tool_choice etc.
) -> Tuple[
    Any, Optional[Dict[str, Any]]
]:  # Returns (response_content, usage_details) tuple
    """
    Helper function to get a completion from the LLM synchronously.
    Handles standard completions and tool calls. Returns content and usage details.
    """
    usage_details = None  # Initialize
    response = None  # Initialize
    try:
        model_config = get_model_config(capability)
        model_name = model_config["name"]
        prompt_cost = model_config["prompt_token_cost"]
        completion_cost = model_config["completion_token_cost"]
    except Exception as config_err:
        logger.error(
            f"Failed to get model configuration for capability '{capability}': {config_err}"
        )
        # Return error string and None for usage details
        return f"Error: Configuration error for model capability '{capability}'", None

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": prompt},
    ]

    call_params = {
        "oauth_token": token or "placeholder_token",
        "prompt_token_cost": prompt_cost,
        "completion_token_cost": completion_cost,
        "model": model_name,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "database_name": database_name,
        **kwargs,
    }

    is_tool_call = "tools" in kwargs and kwargs["tools"]
    if is_tool_call:
        call_params["stream"] = False
        logger.info("Forcing non-streaming mode for tool call.")
    else:
        call_params.setdefault("stream", False)

    try:
        # Direct synchronous call - now returns a tuple (response, usage_details)
        result = call_llm(**call_params)

        # Handle the new tuple format: (api_response, usage_details)
        if isinstance(result, tuple) and len(result) == 2:
            response, usage_details = result
            if usage_details:
                logger.debug(f"Usage details for {database_name}: {usage_details}")
        else:
            # For backward compatibility
            response = result
            usage_details = None
            logger.debug("call_llm did not return usage_details")

    except Exception as llm_err:
        logger.error(f"call_llm failed: {llm_err}", exc_info=True)
        # Return error string and None for usage details
        return f"Error: LLM call failed ({type(llm_err).__name__})", None

    if is_tool_call:
        logger.debug("Returning raw response object and usage details for tool call.")
        if (
            not response
            or not hasattr(response, "choices")
            or not response.choices
            or not hasattr(response.choices[0], "message")
            or not hasattr(response.choices[0].message, "tool_calls")
        ):
            logger.error("Invalid response structure received for tool call.")
            # Return error string and usage details (which might be None)
            return "Error: Invalid response structure for tool call.", usage_details
        # Return the response object and usage details
        return response, usage_details
    else:
        # Handle standard completion
        response_value = ""
        if response and hasattr(response, "choices") and response.choices:
            message = response.choices[0].message
            if message and hasattr(message, "content") and message.content is not None:
                response_value = message.content.strip()
            else:
                logger.warning("LLM response message content was missing or None.")
                response_value = ""
        else:
            logger.error("LLM response object or choices attribute missing/empty.")
            response_value = "Error: Could not retrieve response content."
        logger.debug(
            "Returning extracted content string and usage details for standard completion."
        )
        # Return the content string and usage details
        return response_value, usage_details


# Placeholder database functions


def fetch_benchmarking_catalog() -> List[Dict[str, Any]]:
    """
    Fetch the benchmarking catalog from the database.
    Currently returns placeholder data for demonstration.
    """
    # In a real implementation, this would query the database
    logger.info("Fetching benchmarking catalog (placeholder data)")

    # Example catalog data - in reality, this would come from a database query
    return [
        {
            "id": "bench-001",
            "document_name": "Q1 2023 Key Profitability Ratios - Major Banks",
            "document_description": "Comparative analysis of key profitability ratios (ROE, ROA, Efficiency Ratio) for major Canadian and US banks for Q1 2023, including YoY and QoQ changes.",
        },
        {
            "id": "bench-002",
            "document_name": "Q1 2023 Capital Adequacy Metrics - Major Banks",
            "document_description": "Comparative analysis of capital adequacy metrics (CET1, Tier 1, Total Capital, Leverage Ratio) for major Canadian and US banks for Q1 2023, including YoY and QoQ changes.",
        },
        {
            "id": "bench-003",
            "document_name": "Q1 2023 Asset Quality Indicators - Major Banks",
            "document_description": "Comparative analysis of asset quality indicators (NPL Ratio, Provision Coverage, Credit Costs) for major Canadian and US banks for Q1 2023, with trend analysis.",
        },
    ]


def fetch_benchmarking_data(dataset_ids: List[str]) -> List[Dict[str, Any]]:
    """
    Fetch the full content of specified benchmarking datasets.
    Currently returns placeholder data for demonstration.
    """
    # In a real implementation, this would query the database
    logger.info(f"Fetching benchmarking data for IDs: {dataset_ids} (placeholder data)")

    # Example document content - in reality, this would come from a database query
    datasets = []

    for dataset_id in dataset_ids:
        if dataset_id == "bench-001":
            datasets.append(
                {
                    "dataset_name": "Q1 2023 Key Profitability Ratios - Major Banks",
                    "metadata": {
                        "time_period": "Q1 2023",
                        "data_source": "Quarterly financial statements and earnings releases",
                        "last_updated": "April 15, 2023",
                    },
                    "metrics": [
                        {
                            "metric_name": "Return on Equity (ROE)",
                            "description": "Annualized net income as a percentage of average common shareholders' equity. Indicates how efficiently a bank generates profits from shareholders' equity.",
                            "comparisons": [
                                {
                                    "bank": "RBC",
                                    "value": "15.3%",
                                    "yoy_change": "-0.7%",
                                    "qoq_change": "+0.2%",
                                },
                                {
                                    "bank": "TD Bank",
                                    "value": "14.1%",
                                    "yoy_change": "-1.2%",
                                    "qoq_change": "-0.3%",
                                },
                                {
                                    "bank": "CIBC",
                                    "value": "13.8%",
                                    "yoy_change": "-0.9%",
                                    "qoq_change": "+0.1%",
                                },
                                {
                                    "bank": "JPMorgan",
                                    "value": "16.2%",
                                    "yoy_change": "+0.8%",
                                    "qoq_change": "+0.4%",
                                },
                                {
                                    "bank": "Bank of America",
                                    "value": "11.9%",
                                    "yoy_change": "-0.5%",
                                    "qoq_change": "+0.2%",
                                },
                            ],
                        },
                        {
                            "metric_name": "Return on Assets (ROA)",
                            "description": "Annualized net income as a percentage of average total assets. Measures how efficiently a bank uses its assets to generate profits.",
                            "comparisons": [
                                {
                                    "bank": "RBC",
                                    "value": "0.89%",
                                    "yoy_change": "-0.05%",
                                    "qoq_change": "+0.01%",
                                },
                                {
                                    "bank": "TD Bank",
                                    "value": "0.82%",
                                    "yoy_change": "-0.07%",
                                    "qoq_change": "-0.02%",
                                },
                                {
                                    "bank": "CIBC",
                                    "value": "0.78%",
                                    "yoy_change": "-0.04%",
                                    "qoq_change": "0.00%",
                                },
                                {
                                    "bank": "JPMorgan",
                                    "value": "1.05%",
                                    "yoy_change": "+0.06%",
                                    "qoq_change": "+0.03%",
                                },
                                {
                                    "bank": "Bank of America",
                                    "value": "0.75%",
                                    "yoy_change": "-0.03%",
                                    "qoq_change": "+0.01%",
                                },
                            ],
                        },
                        {
                            "metric_name": "Efficiency Ratio",
                            "description": "Non-interest expenses as a percentage of total revenue. Lower values indicate better operational efficiency.",
                            "comparisons": [
                                {
                                    "bank": "RBC",
                                    "value": "52.3%",
                                    "yoy_change": "+0.8%",
                                    "qoq_change": "-0.4%",
                                },
                                {
                                    "bank": "TD Bank",
                                    "value": "54.1%",
                                    "yoy_change": "+1.2%",
                                    "qoq_change": "+0.3%",
                                },
                                {
                                    "bank": "CIBC",
                                    "value": "55.9%",
                                    "yoy_change": "+0.7%",
                                    "qoq_change": "-0.2%",
                                },
                                {
                                    "bank": "JPMorgan",
                                    "value": "51.8%",
                                    "yoy_change": "-1.1%",
                                    "qoq_change": "-0.6%",
                                },
                                {
                                    "bank": "Bank of America",
                                    "value": "57.4%",
                                    "yoy_change": "+0.3%",
                                    "qoq_change": "-0.1%",
                                },
                            ],
                        },
                    ],
                    "trends": [
                        {
                            "trend_name": "Profitability Pressure",
                            "description": "Most Canadian banks are experiencing year-over-year declines in ROE and ROA, primarily due to economic uncertainty, higher loan loss provisions, and competitive pressures. US banks, particularly JPMorgan, have shown more resilience in maintaining profitability ratios.",
                        }
                    ],
                }
            )
        elif dataset_id == "bench-002":
            datasets.append(
                {
                    "dataset_name": "Q1 2023 Capital Adequacy Metrics - Major Banks",
                    "metadata": {
                        "time_period": "Q1 2023",
                        "data_source": "Quarterly financial statements and regulatory filings",
                        "last_updated": "April 15, 2023",
                    },
                    "metrics": [
                        {
                            "metric_name": "Common Equity Tier 1 (CET1) Ratio",
                            "description": "Common equity as a percentage of risk-weighted assets. Primary measure of a bank's financial strength from a regulatory perspective.",
                            "comparisons": [
                                {
                                    "bank": "RBC",
                                    "value": "13.1%",
                                    "yoy_change": "+0.4%",
                                    "qoq_change": "+0.1%",
                                },
                                {
                                    "bank": "TD Bank",
                                    "value": "13.5%",
                                    "yoy_change": "+0.6%",
                                    "qoq_change": "+0.2%",
                                },
                                {
                                    "bank": "CIBC",
                                    "value": "12.2%",
                                    "yoy_change": "+0.3%",
                                    "qoq_change": "+0.1%",
                                },
                                {
                                    "bank": "JPMorgan",
                                    "value": "13.0%",
                                    "yoy_change": "+0.5%",
                                    "qoq_change": "+0.2%",
                                },
                                {
                                    "bank": "Bank of America",
                                    "value": "11.8%",
                                    "yoy_change": "+0.2%",
                                    "qoq_change": "0.0%",
                                },
                            ],
                        },
                        {
                            "metric_name": "Leverage Ratio",
                            "description": "Tier 1 capital as a percentage of total exposure. Non-risk-based measure to complement risk-based capital requirements.",
                            "comparisons": [
                                {
                                    "bank": "RBC",
                                    "value": "4.8%",
                                    "yoy_change": "+0.1%",
                                    "qoq_change": "0.0%",
                                },
                                {
                                    "bank": "TD Bank",
                                    "value": "4.6%",
                                    "yoy_change": "+0.2%",
                                    "qoq_change": "+0.1%",
                                },
                                {
                                    "bank": "CIBC",
                                    "value": "4.4%",
                                    "yoy_change": "+0.1%",
                                    "qoq_change": "0.0%",
                                },
                                {
                                    "bank": "JPMorgan",
                                    "value": "5.2%",
                                    "yoy_change": "+0.3%",
                                    "qoq_change": "+0.1%",
                                },
                                {
                                    "bank": "Bank of America",
                                    "value": "4.9%",
                                    "yoy_change": "+0.2%",
                                    "qoq_change": "+0.1%",
                                },
                            ],
                        },
                    ],
                    "trends": [
                        {
                            "trend_name": "Capital Accumulation",
                            "description": "All major banks have increased their CET1 ratios year-over-year, reflecting conservative capital management in anticipation of uncertain economic conditions and potential regulatory changes. Canadian banks maintain strong capital positions relative to global peers.",
                        }
                    ],
                }
            )
        elif dataset_id == "bench-003":
            datasets.append(
                {
                    "dataset_name": "Q1 2023 Asset Quality Indicators - Major Banks",
                    "metadata": {
                        "time_period": "Q1 2023",
                        "data_source": "Quarterly financial statements and credit quality disclosures",
                        "last_updated": "April 15, 2023",
                    },
                    "metrics": [
                        {
                            "metric_name": "Non-Performing Loans (NPL) Ratio",
                            "description": "Non-performing loans as a percentage of total loans. Lower values indicate better asset quality.",
                            "comparisons": [
                                {
                                    "bank": "RBC",
                                    "value": "0.23%",
                                    "yoy_change": "+0.05%",
                                    "qoq_change": "+0.02%",
                                },
                                {
                                    "bank": "TD Bank",
                                    "value": "0.25%",
                                    "yoy_change": "+0.06%",
                                    "qoq_change": "+0.03%",
                                },
                                {
                                    "bank": "CIBC",
                                    "value": "0.28%",
                                    "yoy_change": "+0.08%",
                                    "qoq_change": "+0.04%",
                                },
                                {
                                    "bank": "JPMorgan",
                                    "value": "0.52%",
                                    "yoy_change": "+0.11%",
                                    "qoq_change": "+0.05%",
                                },
                                {
                                    "bank": "Bank of America",
                                    "value": "0.48%",
                                    "yoy_change": "+0.09%",
                                    "qoq_change": "+0.04%",
                                },
                            ],
                        },
                        {
                            "metric_name": "Provision Coverage Ratio",
                            "description": "Loan loss provisions as a percentage of non-performing loans. Higher values indicate more conservative provisioning.",
                            "comparisons": [
                                {
                                    "bank": "RBC",
                                    "value": "185%",
                                    "yoy_change": "-15%",
                                    "qoq_change": "-5%",
                                },
                                {
                                    "bank": "TD Bank",
                                    "value": "192%",
                                    "yoy_change": "-8%",
                                    "qoq_change": "-3%",
                                },
                                {
                                    "bank": "CIBC",
                                    "value": "176%",
                                    "yoy_change": "-12%",
                                    "qoq_change": "-4%",
                                },
                                {
                                    "bank": "JPMorgan",
                                    "value": "198%",
                                    "yoy_change": "-10%",
                                    "qoq_change": "-4%",
                                },
                                {
                                    "bank": "Bank of America",
                                    "value": "181%",
                                    "yoy_change": "-14%",
                                    "qoq_change": "-6%",
                                },
                            ],
                        },
                    ],
                    "trends": [
                        {
                            "trend_name": "Emerging Credit Quality Concerns",
                            "description": "All major banks are experiencing a slight deterioration in NPL ratios and have reduced their provision coverage ratios year-over-year. This suggests emerging concerns about asset quality, though levels remain historically low. Canadian banks maintain stronger asset quality metrics compared to their US counterparts.",
                        }
                    ],
                }
            )

    return datasets


# Core functionality


def select_relevant_datasets(
    query: str,
    catalog: List[Dict[str, Any]],
    token: Optional[str] = None,
    database_name: str = "public_benchmarking",
    process_monitor=None,
    stage_name: Optional[str] = None,
) -> List[str]:
    """
    Use an LLM to select the most relevant benchmarking datasets.
    """
    logger.info("Selecting relevant benchmarking datasets from catalog")
    formatted_catalog = format_catalog_for_llm(catalog)
    selection_prompt = get_catalog_selection_prompt(query, formatted_catalog)

    try:
        logger.info(
            f"Initiating Benchmarking Dataset Selection API call (DB: {database_name})"
        )
        # Direct synchronous call - returns a tuple
        selection_response_str, selection_usage = get_completion(
            capability="small",
            prompt=selection_prompt,
            max_tokens=200,
            token=token,
            database_name=database_name,
        )

        # Track token usage from LLM calls
        if selection_usage:
            logger.debug(f"Dataset selection usage: {selection_usage}")
            # Update process monitor if available
            if process_monitor and stage_name:
                process_monitor.add_llm_call_details_to_stage(
                    stage_name, selection_usage
                )
                process_monitor.add_stage_details(stage_name, task="dataset_selection")

        # Check if get_completion returned an error string
        if isinstance(
            selection_response_str, str
        ) and selection_response_str.startswith("Error:"):
            logger.error(
                f"get_completion failed during dataset selection: {selection_response_str}"
            )
            return []

        try:
            selected_ids = json.loads(selection_response_str)
            if isinstance(selected_ids, list) and all(
                isinstance(i, str) for i in selected_ids
            ):
                logger.info(f"LLM selected benchmarking dataset IDs: {selected_ids}")
                return selected_ids
            else:
                logger.error(
                    f"LLM response for benchmarking selection was valid JSON but not list of strings: {selection_response_str}"
                )
                return []
        except json.JSONDecodeError:
            logger.error(
                "Failed to parse benchmarking selection LLM response as JSON, attempting fallback"
            )
            matches = re.findall(r'["\'](.*?)["\']', selection_response_str)
            valid_ids = [m.strip() for m in matches if m.strip()]
            if valid_ids:
                logger.warning(
                    f"Extracted benchmarking dataset IDs using fallback regex: {valid_ids}"
                )
                return valid_ids
            logger.error(
                "Could not extract benchmarking dataset IDs from response using fallback."
            )
            return []
    except Exception as e:
        logger.error(f"Error during LLM benchmarking dataset selection: {str(e)}")
        return []


def synthesize_response_and_status(
    query: str,
    datasets: List[Dict[str, Any]],
    token: Optional[str] = None,
    database_name: str = "public_benchmarking",
    process_monitor=None,
    stage_name: Optional[str] = None,
) -> ResearchResponse:
    """
    Use an LLM tool call to synthesize a detailed research response and status summary.
    """
    logger.info(
        f"Synthesizing response and status for {database_name} using tool call."
    )
    default_error_status = f"❌ Error processing {database_name} query."
    default_no_info_status = f"📄 No relevant benchmarking data found."
    default_research = f"No detailed research generated for {database_name} due to missing data or error."
    error_result = {
        "detailed_research": default_research,
        "status_summary": default_error_status,
    }

    if not datasets:
        logger.warning(f"No datasets provided for {database_name} synthesis.")
        return {
            "detailed_research": default_research,
            "status_summary": default_no_info_status,
        }

    formatted_datasets = format_benchmarking_data_for_llm(datasets)
    synthesis_prompt = get_content_synthesis_prompt(query, formatted_datasets)

    try:
        logger.info(f"Initiating Benchmarking Synthesis API call (DB: {database_name})")
        # Direct synchronous call - returns a tuple
        synthesis_response_obj, synthesis_usage = get_completion(
            capability="large",
            prompt=synthesis_prompt,
            max_tokens=2500,
            temperature=0.2,
            token=token,
            database_name=database_name,
            tools=[SYNTHESIS_TOOL_SCHEMA],
            tool_choice={
                "type": "function",
                "function": {"name": SYNTHESIS_TOOL_SCHEMA["function"]["name"]},
            },
        )

        # Track token usage from synthesis
        if synthesis_usage:
            logger.debug(f"Research synthesis usage: {synthesis_usage}")
            # Update process monitor if available
            if process_monitor and stage_name:
                process_monitor.add_llm_call_details_to_stage(
                    stage_name, synthesis_usage
                )
                process_monitor.add_stage_details(stage_name, task="research_synthesis")

        # Check if get_completion returned an error string in the response part
        if isinstance(
            synthesis_response_obj, str
        ) and synthesis_response_obj.startswith("Error:"):
            logger.error(
                f"get_completion failed for {database_name} synthesis: {synthesis_response_obj}"
            )
            error_result["detailed_research"] = synthesis_response_obj
            return error_result

        # Process Tool Call Response
        if (
            hasattr(synthesis_response_obj, "choices")
            and synthesis_response_obj.choices
            and hasattr(synthesis_response_obj.choices[0], "message")
            and synthesis_response_obj.choices[0].message
            and hasattr(synthesis_response_obj.choices[0].message, "tool_calls")
            and synthesis_response_obj.choices[0].message.tool_calls
        ):

            tool_call = synthesis_response_obj.choices[0].message.tool_calls[0]
            if tool_call.function.name == SYNTHESIS_TOOL_SCHEMA["function"]["name"]:
                arguments_str = tool_call.function.arguments
                logger.debug(f"Received tool arguments string: {arguments_str}")
                try:
                    arguments = json.loads(arguments_str)
                    if (
                        "status_summary" in arguments
                        and "detailed_research" in arguments
                    ):
                        logger.info(
                            f"Successfully parsed synthesis tool call for {database_name}."
                        )
                        status = arguments.get("status_summary", default_error_status)
                        research = arguments.get("detailed_research", default_research)
                        if not isinstance(status, str):
                            status = default_error_status
                        if not isinstance(research, str):
                            research = default_research
                        return {"status_summary": status, "detailed_research": research}
                    else:
                        logger.error(
                            f"Missing required keys in parsed tool arguments for {database_name}: {arguments}"
                        )
                        error_result["detailed_research"] = (
                            "Error: Tool call arguments missing required keys."
                        )
                        return error_result
                except json.JSONDecodeError as json_err:
                    logger.error(
                        f"Failed to parse tool arguments JSON for {database_name}: {json_err}. Arguments: {arguments_str}"
                    )
                    error_result["detailed_research"] = (
                        f"Error: Failed to parse tool arguments JSON - {json_err}"
                    )
                    return error_result
            else:
                logger.error(
                    f"Unexpected tool called for {database_name}: {tool_call.function.name}"
                )
                error_result["detailed_research"] = (
                    f"Error: Unexpected tool called: {tool_call.function.name}"
                )
                return error_result
        else:
            logger.error(
                f"No tool call received from LLM for {database_name} synthesis, despite being requested."
            )
            content = ""
            if (
                hasattr(synthesis_response_obj, "choices")
                and synthesis_response_obj.choices
                and hasattr(synthesis_response_obj.choices[0], "message")
                and synthesis_response_obj.choices[0].message
                and hasattr(synthesis_response_obj.choices[0].message, "content")
                and synthesis_response_obj.choices[0].message.content
            ):
                content = synthesis_response_obj.choices[0].message.content
                logger.warning(
                    f"LLM returned content instead of tool call: {content[:200]}..."
                )
                error_result["detailed_research"] = (
                    f"Error: LLM returned text instead of tool call. Content: {content[:200]}..."
                )
            else:
                error_result["detailed_research"] = (
                    "Error: No tool call or content received from LLM."
                )
            return error_result

    except Exception as e:
        logger.error(
            f"Exception during synthesis tool call for {database_name}: {str(e)}",
            exc_info=True,
        )
        error_result["detailed_research"] = f"Error during synthesis: {str(e)}"
        return error_result


def query_database_sync(
    query: str,
    scope: str,
    token: Optional[str] = None,
    process_monitor=None,
    query_stage_name: Optional[str] = None,
) -> SubagentResult:
    """
    Synchronously query the Financial Benchmarking database based on the specified scope.
    """
    logger.info(
        f"Querying Financial Benchmarking database (sync): '{query}' with scope: {scope}"
    )
    database_name = "public_benchmarking"
    default_error_status = "❌ Error during query processing."
    selected_dataset_ids: Optional[List[str]] = None
    stage_name = query_stage_name or f"db_query_{database_name}_unknown"

    try:
        # 1. Fetch Catalog
        catalog = fetch_benchmarking_catalog()
        logger.info(f"Retrieved {len(catalog)} total benchmarking catalog entries")
        if not catalog:
            response: DatabaseResponse = (
                []
                if scope == "metadata"
                else {
                    "detailed_research": "No datasets found in the Financial Benchmarking database catalog.",
                    "status_summary": "📄 No benchmarking datasets found in catalog.",
                }
            )
            return response, None

        # 2. Select Relevant Datasets
        selected_dataset_ids = select_relevant_datasets(
            query, catalog, token, database_name, process_monitor, stage_name
        )
        logger.info(
            f"LLM selected {len(selected_dataset_ids)} relevant benchmarking dataset IDs: {selected_dataset_ids}"
        )

        if not selected_dataset_ids:
            response: DatabaseResponse = (
                []
                if scope == "metadata"
                else {
                    "detailed_research": "LLM did not select any relevant benchmarking datasets from the catalog based on the query.",
                    "status_summary": "📄 No relevant datasets selected by LLM.",
                }
            )
            if process_monitor:
                process_monitor.add_stage_details(
                    stage_name, result_count=0, document_ids=[]
                )
            return response, []  # Return empty list for dataset IDs

        # 3. Process based on scope
        if scope == "metadata":
            selected_items = [
                item for item in catalog if item.get("id") in selected_dataset_ids
            ]
            logger.info(
                f"Returning {len(selected_items)} selected benchmarking metadata items."
            )
            if process_monitor:
                process_monitor.add_stage_details(
                    stage_name,
                    result_count=len(selected_items),
                    document_ids=selected_dataset_ids,
                )
            return selected_items, selected_dataset_ids

        elif scope == "research":
            # 4. Fetch Dataset Content for Selected Datasets
            datasets_with_content = fetch_benchmarking_data(selected_dataset_ids)
            if not datasets_with_content:
                response = {
                    "detailed_research": "Could not retrieve content for the selected benchmarking datasets.",
                    "status_summary": "❌ Error retrieving benchmark data content.",
                }
                if process_monitor:
                    process_monitor.add_stage_details(
                        stage_name,
                        error="Could not retrieve dataset content",
                        document_ids=selected_dataset_ids,
                    )
                return response, selected_dataset_ids

            # 5. Synthesize Final Response
            research_result = synthesize_response_and_status(
                query,
                datasets_with_content,
                token,
                database_name,
                process_monitor,
                stage_name,
            )

            # Log final details for the stage
            if process_monitor:
                process_monitor.add_stage_details(
                    stage_name,
                    result_count=len(datasets_with_content),
                    document_ids=selected_dataset_ids,
                    status_summary=research_result.get("status_summary", ""),
                )
            return research_result, selected_dataset_ids

        else:
            logger.error(
                f"Invalid scope provided to public_benchmarking subagent: {scope}"
            )
            raise ValueError(f"Invalid scope: {scope}")

    except Exception as e:
        error_msg = (
            f"Error querying Financial Benchmarking database (scope: {scope}): {str(e)}"
        )
        logger.error(error_msg, exc_info=True)
        response: DatabaseResponse = (
            []
            if scope == "metadata"
            else {
                "detailed_research": f"**Error processing request for Financial Benchmarking:** {str(e)}",
                "status_summary": default_error_status,
            }
        )
        if process_monitor:
            process_monitor.add_stage_details(
                stage_name, error=str(e), document_ids=selected_dataset_ids
            )
        return response, selected_dataset_ids
