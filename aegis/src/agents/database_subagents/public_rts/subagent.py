# public_rts/subagent.py
"""
Shareholder Reports Subagent

This module handles queries to the Shareholder Reports database,
including catalog retrieval, document selection, content retrieval,
and response synthesis.

Functions:
    query_database_sync: Synchronously query the Shareholder Reports database
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
        "description": "Synthesizes research findings from provided documents and generates a status summary.",
        "parameters": {
            "type": "object",
            "properties": {
                "status_summary": {
                    "type": "string",
                    "description": "Concise status summary (1 sentence) indicating finding relevance (e.g., '✅ Found direct answer.', '📄 No relevant info found.').",
                },
                "detailed_research": {
                    "type": "string",
                    "description": "Detailed, structured markdown report synthesizing information from documents, including citations (document and section names).",
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


def format_documents_for_llm(documents: List[Dict[str, Any]]) -> str:
    """
    Format retrieved documents with content into a string optimized for LLM analysis.
    """
    formatted_docs = ""
    for doc in documents:
        doc_name = doc.get("document_name", "Untitled")
        formatted_docs += f"# {doc_name}\n\n"
        sections = doc.get("sections", [])
        for section in sections:
            section_name = section.get("section_name", "Untitled Section")
            section_content = section.get("section_content", "No content available")
            formatted_docs += f"## {section_name}\n\n"
            formatted_docs += f"{section_content}\n\n"
        formatted_docs += "---\n\n"
    return formatted_docs.strip()


# LLM interaction helper
def get_completion(
    capability: str,
    prompt: str,
    max_tokens: int = 1000,
    temperature: float = 0.7,
    token: Optional[str] = None,
    database_name: Optional[str] = None,
    **kwargs: Any,  # Accept additional kwargs for tools, tool_choice etc.
) -> Tuple[Any, Optional[Dict[str, Any]]]:  # Returns (response_content, usage_details) tuple
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
        logger.debug("Returning extracted content string and usage details for standard completion.")
        # Return the content string and usage details
        return response_value, usage_details


# Placeholder database functions

def fetch_report_catalog() -> List[Dict[str, Any]]:
    """
    Fetch the shareholder report catalog from the database.
    Currently returns placeholder data for demonstration.
    """
    # In a real implementation, this would query the database
    logger.info("Fetching shareholder report catalog (placeholder data)")
    
    # Example catalog data - in reality, this would come from a database query
    return [
        {
            "id": "rpt-001",
            "document_name": "RBC Q1 2023 Report to Shareholders",
            "document_description": "Royal Bank of Canada Q1 2023 Report to Shareholders. Contains MD&A, financial statements, notes, and key performance metrics."
        },
        {
            "id": "rpt-002",
            "document_name": "TD Bank Q1 2023 Report to Shareholders",
            "document_description": "TD Bank Q1 2023 Report to Shareholders. Contains financial results, MD&A, risk management discussion, and consolidated financial statements."
        },
        {
            "id": "rpt-003",
            "document_name": "CIBC Q1 2023 Report to Shareholders",
            "document_description": "CIBC Q1 2023 Report to Shareholders. Contains management's discussion and analysis, financial performance, and consolidated financial statements."
        }
    ]


def fetch_report_content(doc_ids: List[str]) -> List[Dict[str, Any]]:
    """
    Fetch the full content of specified shareholder report documents.
    Currently returns placeholder data for demonstration.
    """
    # In a real implementation, this would query the database
    logger.info(f"Fetching shareholder report content for IDs: {doc_ids} (placeholder data)")
    
    # Example document content - in reality, this would come from a database query
    documents = []
    
    for doc_id in doc_ids:
        if doc_id == "rpt-001":
            documents.append({
                "document_name": "RBC Q1 2023 Report to Shareholders",
                "sections": [
                    {
                        "section_name": "Financial Highlights",
                        "section_content": "For the quarter ended January 31, 2023, RBC reported net income of $3.2 billion, down 2% from the prior year. Diluted earnings per share (EPS) was $2.29, down 1% from the prior year. Return on common equity (ROE) was 15.3%. Common Equity Tier 1 (CET1) ratio was 13.1% as of January 31, 2023."
                    },
                    {
                        "section_name": "MD&A - Personal & Commercial Banking",
                        "section_content": "Personal & Commercial Banking reported net income of $1.7 billion, up 7% from the prior year, primarily driven by higher net interest income reflecting strong volume growth, partially offset by higher PCL and non-interest expenses. Net interest margin expanded by 12 basis points compared to the previous quarter due to higher interest rates."
                    },
                    {
                        "section_name": "Financial Statements - Net Interest Income",
                        "section_content": "Net interest income was $5.8 billion for Q1 2023, an increase of $872 million or 17% from the previous year. This was primarily driven by volume growth of 7% in Canadian Banking and higher net interest margins resulting from higher interest rates across all businesses."
                    }
                ]
            })
        elif doc_id == "rpt-002":
            documents.append({
                "document_name": "TD Bank Q1 2023 Report to Shareholders",
                "sections": [
                    {
                        "section_name": "Financial Results Summary",
                        "section_content": "TD Bank Group reported net income of $1,582 million, down 3.4% from the first quarter last year. Adjusted net income was $4,155 million, up 2.0% compared with the first quarter last year. Reported diluted earnings per share were $0.82, down 4.7% compared with the first quarter last year."
                    },
                    {
                        "section_name": "Canadian Retail",
                        "section_content": "Canadian Retail net income was $1,729 million, an increase of 6% compared with the first quarter last year, reflecting higher revenue, partially offset by higher expenses, PCL, and insurance claims. Revenue increased 8%, reflecting volume growth, margin expansion, and growth in fee income."
                    }
                ]
            })
        elif doc_id == "rpt-003":
            documents.append({
                "document_name": "CIBC Q1 2023 Report to Shareholders",
                "sections": [
                    {
                        "section_name": "Financial Performance Summary",
                        "section_content": "CIBC reported net income of $1,841 million for the first quarter of 2023, compared with $1,782 million for the same period in 2022. Adjusted net income was $1,834 million, compared with $1,857 million for the same period last year."
                    },
                    {
                        "section_name": "Capital Markets and Direct Financial Services",
                        "section_content": "Capital Markets and Direct Financial Services net income was $612 million, an increase of $69 million from the first quarter of 2022, driven by higher trading revenue and fees, partially offset by higher expenses and PCL."
                    }
                ]
            })
    
    return documents


# Core functionality

def select_relevant_documents(
    query: str,
    catalog: List[Dict[str, Any]],
    token: Optional[str] = None,
    database_name: str = "public_rts",
    process_monitor=None,
    stage_name: Optional[str] = None
) -> List[str]:
    """
    Use an LLM to select the most relevant shareholder report documents.
    """
    logger.info("Selecting relevant shareholder report documents from catalog")
    formatted_catalog = format_catalog_for_llm(catalog)
    selection_prompt = get_catalog_selection_prompt(query, formatted_catalog)

    try:
        logger.info(
            f"Initiating Shareholder Report Document Selection API call (DB: {database_name})"
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
            logger.debug(f"Document selection usage: {selection_usage}")
            # Update process monitor if available
            if process_monitor and stage_name:
                process_monitor.add_llm_call_details_to_stage(stage_name, selection_usage)
                process_monitor.add_stage_details(stage_name, task="document_selection")

        # Check if get_completion returned an error string
        if isinstance(selection_response_str, str) and selection_response_str.startswith("Error:"):
            logger.error(
                f"get_completion failed during document selection: {selection_response_str}"
            )
            return []

        try:
            selected_ids = json.loads(selection_response_str)
            if isinstance(selected_ids, list) and all(
                isinstance(i, str) for i in selected_ids
            ):
                logger.info(f"LLM selected shareholder report document IDs: {selected_ids}")
                return selected_ids
            else:
                logger.error(
                    f"LLM response for shareholder report selection was valid JSON but not list of strings: {selection_response_str}"
                )
                return []
        except json.JSONDecodeError:
            logger.error(
                "Failed to parse shareholder report selection LLM response as JSON, attempting fallback"
            )
            matches = re.findall(r'["\'](.*?)["\']', selection_response_str)
            valid_ids = [m.strip() for m in matches if m.strip()]
            if valid_ids:
                logger.warning(
                    f"Extracted shareholder report document IDs using fallback regex: {valid_ids}"
                )
                return valid_ids
            logger.error(
                "Could not extract shareholder report document IDs from response using fallback."
            )
            return []
    except Exception as e:
        logger.error(f"Error during LLM shareholder report document selection: {str(e)}")
        return []


def synthesize_response_and_status(
    query: str,
    documents: List[Dict[str, Any]],
    token: Optional[str] = None,
    database_name: str = "public_rts",
    process_monitor=None,
    stage_name: Optional[str] = None
) -> ResearchResponse:
    """
    Use an LLM tool call to synthesize a detailed research response and status summary.
    """
    logger.info(
        f"Synthesizing response and status for {database_name} using tool call."
    )
    default_error_status = f"❌ Error processing {database_name} query."
    default_no_info_status = f"📄 No relevant information found in {database_name}."
    default_research = f"No detailed research generated for {database_name} due to missing documents or error."
    error_result = {
        "detailed_research": default_research,
        "status_summary": default_error_status,
    }

    if not documents:
        logger.warning(f"No documents provided for {database_name} synthesis.")
        return {
            "detailed_research": default_research,
            "status_summary": default_no_info_status,
        }

    formatted_documents = format_documents_for_llm(documents) 
    synthesis_prompt = get_content_synthesis_prompt(query, formatted_documents)

    try:
        logger.info(
            f"Initiating Shareholder Report Synthesis API call (DB: {database_name})"
        )
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
                process_monitor.add_llm_call_details_to_stage(stage_name, synthesis_usage)
                process_monitor.add_stage_details(stage_name, task="research_synthesis")

        # Check if get_completion returned an error string in the response part
        if isinstance(synthesis_response_obj, str) and synthesis_response_obj.startswith("Error:"):
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
                        if not isinstance(status, str): status = default_error_status
                        if not isinstance(research, str): research = default_research
                        return {"status_summary": status, "detailed_research": research}
                    else:
                        logger.error(
                            f"Missing required keys in parsed tool arguments for {database_name}: {arguments}"
                        )
                        error_result["detailed_research"] = "Error: Tool call arguments missing required keys."
                        return error_result
                except json.JSONDecodeError as json_err:
                    logger.error(
                        f"Failed to parse tool arguments JSON for {database_name}: {json_err}. Arguments: {arguments_str}"
                    )
                    error_result["detailed_research"] = f"Error: Failed to parse tool arguments JSON - {json_err}"
                    return error_result
            else:
                logger.error(
                    f"Unexpected tool called for {database_name}: {tool_call.function.name}"
                )
                error_result["detailed_research"] = f"Error: Unexpected tool called: {tool_call.function.name}"
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
                error_result["detailed_research"] = f"Error: LLM returned text instead of tool call. Content: {content[:200]}..."
            else:
                error_result["detailed_research"] = "Error: No tool call or content received from LLM."
            return error_result

    except Exception as e:
        logger.error(
            f"Exception during synthesis tool call for {database_name}: {str(e)}",
            exc_info=True,
        )
        error_result["detailed_research"] = f"Error during synthesis: {str(e)}"
        return error_result


def query_database_sync(
    query: str, scope: str, token: Optional[str] = None, process_monitor=None, query_stage_name: Optional[str] = None
) -> SubagentResult:
    """
    Synchronously query the Shareholder Reports database based on the specified scope.
    """
    logger.info(f"Querying Shareholder Reports database (sync): '{query}' with scope: {scope}")
    database_name = "public_rts"
    default_error_status = "❌ Error during query processing."
    selected_doc_ids: Optional[List[str]] = None
    stage_name = query_stage_name or f"db_query_{database_name}_unknown"
    
    try:
        # 1. Fetch Catalog
        catalog = fetch_report_catalog()
        logger.info(f"Retrieved {len(catalog)} total shareholder report catalog entries")
        if not catalog:
            response: DatabaseResponse = [] if scope == "metadata" else {
                "detailed_research": "No documents found in the Shareholder Reports database catalog.",
                "status_summary": "📄 No documents found in catalog.",
            }
            return response, None

        # 2. Select Relevant Documents
        selected_doc_ids = select_relevant_documents(
            query, catalog, token, database_name, process_monitor, stage_name
        )
        logger.info(f"LLM selected {len(selected_doc_ids)} relevant shareholder report document IDs: {selected_doc_ids}")

        if not selected_doc_ids:
            response: DatabaseResponse = [] if scope == "metadata" else {
                "detailed_research": "LLM did not select any relevant shareholder report documents from the catalog based on the query.",
                "status_summary": "📄 No relevant documents selected by LLM.",
            }
            if process_monitor:
                process_monitor.add_stage_details(stage_name, result_count=0, document_ids=[])
            return response, [] # Return empty list for doc IDs

        # 3. Process based on scope
        if scope == "metadata":
            selected_items = [item for item in catalog if item.get("id") in selected_doc_ids]
            logger.info(f"Returning {len(selected_items)} selected shareholder report metadata items.")
            if process_monitor:
                process_monitor.add_stage_details(stage_name, result_count=len(selected_items), document_ids=selected_doc_ids)
            return selected_items, selected_doc_ids

        elif scope == "research":
            # 4. Fetch Document Content for Selected Documents
            documents_with_content = fetch_report_content(selected_doc_ids)
            if not documents_with_content:
                response = {
                    "detailed_research": "Could not retrieve content for the selected shareholder report documents.",
                    "status_summary": "❌ Error retrieving document content.",
                }
                if process_monitor:
                    process_monitor.add_stage_details(stage_name, error="Could not retrieve document content", document_ids=selected_doc_ids)
                return response, selected_doc_ids

            # 5. Synthesize Final Response
            research_result = synthesize_response_and_status(
                query, documents_with_content, token, database_name, process_monitor, stage_name
            )

            # Log final details for the stage
            if process_monitor:
                process_monitor.add_stage_details(
                    stage_name,
                    result_count=len(documents_with_content),
                    document_ids=selected_doc_ids,
                    status_summary=research_result.get("status_summary", "")
                )
            return research_result, selected_doc_ids

        else:
            logger.error(f"Invalid scope provided to public_rts subagent: {scope}")
            raise ValueError(f"Invalid scope: {scope}")

    except Exception as e:
        error_msg = f"Error querying Shareholder Reports database (scope: {scope}): {str(e)}"
        logger.error(error_msg, exc_info=True)
        response: DatabaseResponse = [] if scope == "metadata" else {
            "detailed_research": f"**Error processing request for Shareholder Reports:** {str(e)}",
            "status_summary": default_error_status,
        }
        if process_monitor:
            process_monitor.add_stage_details(stage_name, error=str(e), document_ids=selected_doc_ids)
        return response, selected_doc_ids
