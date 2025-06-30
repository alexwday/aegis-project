# aegis/src/chat_model/model_with_dropdowns.py
"""
Enhanced Model with Dropdown Support for Database Research

This version yields structured data that the chat interface can use to create
and update dropdown components in real-time as database queries execute.
"""

import json
import logging
import time
import uuid
import concurrent.futures
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional, Union, Generator

# Import the existing model components
from .model import (
    QUERY_DELAY_SECONDS,
    DEFAULT_THREAD_POOL_SIZE,
    database_connection,
    _execute_query_worker,
    UsageDetails,
    DatabaseResult,
    RoutingDecision
)

# --- Enhanced Generator for Dropdown Support ---
def model_with_dropdowns(
    conversation: Optional[Dict[str, Any]] = None,
    html_callback: Optional[callable] = None,
) -> Generator[Union[str, Dict[str, Any]], None, None]:
    """
    Enhanced model that yields structured data for dropdown display.
    
    Yields either:
    - str: Regular text content to display
    - dict: Structured data for special handling (e.g., database dropdowns)
    """
    from ..initial_setup.process_monitor import enable_monitoring, get_process_monitor
    from ..agents.agent_clarifier.clarifier import clarify_research_needs
    from ..agents.agent_direct_response.response_from_conversation import (
        response_from_conversation,
    )
    from ..agents.agent_planner.planner import create_database_selection_plan
    from ..agents.agent_router.router import get_routing_decision
    from ..agents.agent_summarizer.summarizer import generate_streaming_summary
    from ..conversation_setup.conversation import process_conversation
    from ..initial_setup.logging_config import configure_logging
    from ..initial_setup.oauth.oauth import setup_oauth
    from ..initial_setup.ssl.ssl import setup_ssl
    from ..global_prompts.database_statement import get_available_databases
    from .model_settings import SHOW_USAGE_SUMMARY

    logger = configure_logging()
    
    # Setup process monitoring
    enable_monitoring(True)
    process_monitor = get_process_monitor()
    run_uuid_val = uuid.uuid4()
    process_monitor.set_run_uuid(run_uuid_val)
    process_monitor.start_monitoring()

    try:
        logger.info("Initializing enhanced model with dropdown support...")
        
        # SSL and OAuth setup
        process_monitor.start_stage("ssl_setup")
        cert_path = setup_ssl()
        process_monitor.end_stage("ssl_setup")
        
        process_monitor.start_stage("oauth_setup")
        token = setup_oauth()
        process_monitor.end_stage("oauth_setup")
        
        if not conversation:
            yield "Model initialized, but no conversation provided to process."
            return
            
        # Process conversation
        process_monitor.start_stage("conversation_processing")
        try:
            processed_conversation = process_conversation(conversation)
            logger.info(f"Conversation processed: {len(processed_conversation['messages'])} messages")
        except Exception as e:
            yield f"Error processing conversation: {str(e)}"
            return
        process_monitor.end_stage("conversation_processing")
        
        # Get routing decision
        process_monitor.start_stage("router")
        routing_decision, router_usage_details = get_routing_decision(processed_conversation, token)
        process_monitor.end_stage("router")
        
        if routing_decision["function_name"] == "response_from_conversation":
            # Direct response path - no dropdowns needed
            logger.info("Using direct response path")
            process_monitor.start_stage("direct_response")
            
            for chunk in response_from_conversation(processed_conversation, token):
                if isinstance(chunk, dict) and "usage_details" in chunk:
                    # Skip usage details for now
                    continue
                else:
                    yield chunk
                    
            process_monitor.end_stage("direct_response")
            
        elif routing_decision["function_name"] == "research_from_database":
            # Research path - needs dropdowns
            logger.info("Using research from database path")
            process_monitor.start_stage("clarifier")
            
            clarifier_decision, clarifier_usage_details = clarify_research_needs(
                processed_conversation, token
            )
            process_monitor.end_stage("clarifier")
            
            if clarifier_decision.get("needs_clarification"):
                yield clarifier_decision.get("clarification_message", "Please provide more details.")
            else:
                research_statement = clarifier_decision.get("output", "")
                is_continuation = clarifier_decision.get("is_continuation", False)
                
                # Get database selection plan
                process_monitor.start_stage("planner")
                db_selection_plan, planner_usage_details = create_database_selection_plan(
                    research_statement, token, is_continuation
                )
                selected_databases = db_selection_plan.get("databases", [])
                process_monitor.end_stage("planner")
                
                # Display research plan
                available_databases = get_available_databases()
                yield "---\n# 📋 Research Plan\n\n"
                yield f"## Research Statement\n{research_statement}\n\n"
                
                selected_db_display_names = [
                    available_databases.get(db_name, {}).get("name", db_name)
                    for db_name in selected_databases
                ]
                
                if selected_db_display_names:
                    if len(selected_db_display_names) == 1:
                        names_str = selected_db_display_names[0]
                    elif len(selected_db_display_names) == 2:
                        names_str = f"{selected_db_display_names[0]} and {selected_db_display_names[1]}"
                    else:
                        names_str = (
                            ", ".join(selected_db_display_names[:-1])
                            + f", and {selected_db_display_names[-1]}"
                        )
                    yield f"Searching the following databases: {names_str}.\n\n"
                    
                    # Yield dropdown initialization data
                    database_dropdowns = {}
                    for db_name in selected_databases:
                        db_id = str(uuid.uuid4())
                        db_display_name = available_databases.get(db_name, {}).get("name", db_name)
                        database_dropdowns[db_id] = {
                            "db_name": db_name,
                            "display_name": db_display_name,
                            "status": "pending",
                            "content": "",
                            "timestamp": datetime.now().isoformat()
                        }
                    
                    yield {
                        "type": "database_dropdowns_init",
                        "dropdowns": database_dropdowns
                    }
                    
                    yield "---\n"
                    
                    # Execute database queries with real-time updates
                    if selected_databases:
                        aggregated_detailed_research = {}
                        futures = []
                        db_id_mapping = {}  # Map db_name to dropdown ID
                        
                        # Create reverse mapping
                        for db_id, dropdown_data in database_dropdowns.items():
                            db_id_mapping[dropdown_data["db_name"]] = db_id
                        
                        with concurrent.futures.ThreadPoolExecutor(max_workers=DEFAULT_THREAD_POOL_SIZE) as executor:
                            # Submit all queries
                            for i, db_name in enumerate(selected_databases):
                                db_display_name = available_databases.get(db_name, {}).get("name", db_name)
                                
                                # Update dropdown to "streaming" status
                                db_id = db_id_mapping[db_name]
                                yield {
                                    "type": "database_dropdown_update",
                                    "db_id": db_id,
                                    "status": "streaming",
                                    "content": "🔄 Querying database..."
                                }
                                
                                if i > 0:
                                    time.sleep(QUERY_DELAY_SECONDS)
                                    
                                future = executor.submit(
                                    _execute_query_worker,
                                    db_name,
                                    research_statement,
                                    token,
                                    db_display_name,
                                    i,
                                    len(selected_databases),
                                )
                                futures.append((future, db_name, db_id))
                            
                            # Process results as they complete
                            for future, db_name, db_id in futures:
                                try:
                                    result_data = future.result()
                                    db_display_name = result_data["db_display_name"]
                                    task_exception = result_data["exception"]
                                    result = result_data["result"]
                                    
                                    # Determine status and content
                                    if task_exception:
                                        status = "error"
                                        content = f"❌ Error: {str(task_exception)}"
                                        aggregated_detailed_research[db_name] = f"Error: {str(task_exception)}"
                                    elif result is not None:
                                        if isinstance(result, dict) and "detailed_research" in result:
                                            status = "completed"
                                            content = result["status_summary"]
                                            aggregated_detailed_research[db_name] = result["detailed_research"]
                                        else:
                                            status = "error"
                                            content = "❌ Error: Unexpected result format."
                                            aggregated_detailed_research[db_name] = f"Error: {str(result)[:200]}..."
                                    else:
                                        status = "error"
                                        content = "❓ Unknown status"
                                    
                                    # Update dropdown with final result
                                    yield {
                                        "type": "database_dropdown_update",
                                        "db_id": db_id,
                                        "status": status,
                                        "content": content
                                    }
                                    
                                except Exception as exc:
                                    logger.error(f"Error retrieving result: {exc}", exc_info=True)
                                    yield {
                                        "type": "database_dropdown_update",
                                        "db_id": db_id,
                                        "status": "error",
                                        "content": f"❌ Error: {str(exc)}"
                                    }
                        
                        # Generate summary if we have results
                        if aggregated_detailed_research:
                            yield "\n\n---\n"
                            yield "\n\n## 📊 Research Summary\n"
                            
                            process_monitor.start_stage("summary")
                            try:
                                for chunk in generate_streaming_summary(
                                    aggregated_detailed_research,
                                    "research",
                                    token,
                                    None
                                ):
                                    if isinstance(chunk, dict) and "usage_details" in chunk:
                                        continue
                                    else:
                                        yield chunk
                            finally:
                                process_monitor.end_stage("summary")
                
                else:
                    yield "No databases selected for search.\n\n---\n"
                    
    except Exception as e:
        logger.error(f"Error in model_with_dropdowns: {str(e)}", exc_info=True)
        yield f"An error occurred: {str(e)}"
    finally:
        process_monitor.stop_monitoring()
        
        # Log final usage summary if enabled
        if SHOW_USAGE_SUMMARY:
            total_usage = process_monitor.get_total_usage()
            if total_usage["total_cost"] > 0:
                yield f"\n\n---\n📊 Usage Summary: ${total_usage['total_cost']:.4f}"