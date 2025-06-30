# -*- coding: utf-8 -*-
from dash import Dash, html, dcc, no_update, clientside_callback, ALL, MATCH
from dash.dependencies import Input, Output, State
import time
from threading import Thread
from datetime import datetime
import os
import json
import uuid

# Assuming your model import works correctly in your Dataiku environment
from aegis.src.chat_model.model import model

# Define the app instance
app = Dash(__name__)

MAX_MESSAGE_LENGTH = 2000
TYPING_INDICATOR = "AI is typing..."
start_time = None

greeting = """
Hello! I'm the AEGIS Assistant. I can help answer your questions using the latest financial data and research from our knowledge databases. What would you like to know?
"""

initial_conversation = [{
    "role": "assistant",
    "content": greeting,
    "timestamp": datetime.now().strftime("%I:%M %p")
}]

# Global variables for tracking state
assistant_response_chunks = []
is_generating = False
current_conversation = initial_conversation.copy()
database_results = {}  # Store database-specific results
active_databases = []  # Track which databases are being queried

# Keep the layout compact with minimal margins
app.layout = html.Div([
    # Header - more compact
    html.Div([
        html.Div([
            # Brand and title in one line
            html.Div([
                html.Span("AEGIS", style={
                    'color': '#00796b',  # Teal 700
                    'fontWeight': 'bold',
                    'fontSize': '24px',
                    'marginRight': '10px'
                }),
            ]),
            html.Div("Finance Assist for External Research and Insights", style={
                'color': '#333',
                'fontSize': '14px',
                'marginTop': '2px'
            })
        ], style={'flex': '1'}),

        html.Div([
            html.Button("New Chat", id="new-chat-button", style={
                'marginRight': '10px',
                'padding': '5px 12px',
                'backgroundColor': '#e0f2f1',  # Teal 50
                'border': '1px solid #b2dfdb',  # Teal 100
                'borderRadius': '4px',
                'cursor': 'pointer',
                'fontSize': '13px',
                'color': '#00796b'  # Teal 700
            }),
            html.Button("Export", id="export-button", style={
                'padding': '5px 12px',
                'backgroundColor': '#004d40',  # Teal 900
                'border': 'none',
                'borderRadius': '4px',
                'cursor': 'pointer',
                'color': 'white',
                'fontSize': '13px'
            })
        ])
    ], style={
        'display': 'flex',
        'justifyContent': 'space-between',
        'alignItems': 'center',
        'padding': '15px',
        'backgroundColor': '#e0f2f1',  # Teal 50
        'borderRadius': '8px',
        'boxShadow': '0 2px 5px rgba(0, 121, 107, 0.15)',  # Teal shadow
        'marginBottom': '15px',
        'borderLeft': '4px solid #00796b'  # Teal 700 accent border
    }),

    # Chat container - reduced height
    html.Div([
        # Typing indicator
        html.Div("AI is typing...", id="typing-indicator", style={
            'color': '#00796b',  # Teal 700
            'fontSize': '12px',
            'fontStyle': 'italic',
            'padding': '5px 10px',
            'display': 'none'
        }),

        # Chat messages - smaller height
        html.Div(id="chat-history", style={
            'overflowY': 'auto',
            'height': 'calc(100vh - 210px)',  # Reduced height
            'padding': '10px',
            'backgroundColor': '#f5f5f5'  # Light gray background
        }),

        # Hidden scroll helper (output for clientside callback)
        html.Div(id="scroll-helper-output") # Renamed dummy output slightly
    ], style={
        'backgroundColor': '#f5f5f5',  # Light gray background
        'borderRadius': '8px',
        'boxShadow': '0 2px 5px rgba(0, 121, 107, 0.15)',  # Teal shadow
        'marginBottom': '15px',
        'overflow': 'hidden',  # Prevent contents from overflowing
        'borderLeft': '4px solid #00796b'  # Teal 700 accent border
    }),

    # Input area - fixed spacing
    html.Div([
        # Fixed width for input to avoid overlap
        html.Div([
            dcc.Input(
                id="user-input",
                type="text",
                placeholder="Ask a question...",
                maxLength=MAX_MESSAGE_LENGTH,
                style={
                    'width': '100%',  # Take full width of container
                    'padding': '10px 15px',
                    'border': '1px solid #b2dfdb',  # Teal 100 border
                    'borderRadius': '6px',
                    'fontSize': '14px',
                    'boxSizing': 'border-box',  # Include padding in width calculation
                    'backgroundColor': 'white'
                }
            ),
            html.Div(id="char-counter", style={
                'fontSize': '11px',
                'color': '#00796b',  # Teal 700
                'position': 'absolute',
                'right': '10px',
                'bottom': '-18px',
                'display': 'none'
            })
        ], style={
            'position': 'relative',
            'width': 'calc(100% - 75px)',  # Leave space for button
            'marginRight': '10px'
        }),

        # Fixed width button
        html.Button("Send", id="submit-button", style={
            'width': '65px',  # Fixed width
            'padding': '10px 0',
            'backgroundColor': '#00796b',  # Teal 700
            'color': 'white',
            'border': 'none',
            'borderRadius': '6px',
            'cursor': 'pointer',
            'fontWeight': 'bold',
            'fontSize': '14px'
        })
    ], style={
        'display': 'flex',
        'alignItems': 'center',
        'marginBottom': '20px'
    }),

    # Store components (minimal)
    dcc.Store(id="conversation-store", data=initial_conversation),
    dcc.Store(id="database-results-store", data={}),
    dcc.Store(id="active-databases-store", data=[]),
    dcc.Interval(id="interval-component", interval=500, n_intervals=0, disabled=True),
    dcc.Download(id="download-conversation")
], style={
    'width': '95%',  # Use most of the screen width
    'maxWidth': '1200px',
    'margin': '0 auto',
    'padding': '10px',
    'backgroundColor': '#e8f5e9',  # Green 50 - subtle background
    'fontFamily': '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    'height': '100vh',  # Full viewport height
    'boxSizing': 'border-box'  # Include padding in height calculation
})

# --- FORMAT MESSAGES WITH DROPDOWNS ---
def format_messages(messages, database_results_data=None):
    """Format conversation messages for display, including database research dropdowns."""
    chat_display = []
    
    for idx, msg in enumerate(messages):
        is_user = msg["role"] == "user"
        
        # Check if this is a database research message
        is_database_research = (not is_user and 
                              msg.get("content", "").startswith("---\n# 📋 Research Plan") or
                              "database_results" in msg)
        
        if is_database_research and database_results_data:
            # Create a container for the research response
            research_container = html.Div([
                html.Div([
                    html.Span("AI", style={
                        'fontSize': '11px',
                        'fontWeight': 'bold',
                        'marginBottom': '3px',
                        'color': '#00796b',
                    }),
                    html.Div(msg["timestamp"], style={
                        'fontSize': '11px',
                        'color': '#777',
                        'marginLeft': 'auto'
                    })
                ], style={
                    'display': 'flex',
                    'alignItems': 'center',
                    'marginBottom': '10px'
                }),
                
                # Research plan section
                dcc.Markdown(msg.get("content", ""), style={
                    'marginBottom': '15px',
                    'padding': '10px',
                    'backgroundColor': 'white',
                    'borderRadius': '8px',
                    'border': '1px solid #e0f2f1'
                }),
                
                # Database dropdowns
                html.Div([
                    create_database_dropdown(db_id, db_data)
                    for db_id, db_data in database_results_data.items()
                ], style={'marginBottom': '15px'}),
                
                # Final summary (if available)
                html.Div(id=f"summary-{idx}", style={'marginTop': '15px'})
            ], style={
                'padding': '15px',
                'backgroundColor': 'white',
                'borderRadius': '8px',
                'border': '1px solid #e0f2f1',
                'marginBottom': '10px',
                'maxWidth': '85%'
            })
            
            chat_display.append(research_container)
        else:
            # Regular message formatting
            bubble_style = {
                'padding': '10px 15px', 
                'borderRadius': '8px', 
                'maxWidth': '85%',
                'marginBottom': '10px', 
                'boxShadow': '0 1px 2px rgba(0, 121, 107, 0.15)',
                'backgroundColor': '#b2dfdb' if is_user else 'white',
                'marginLeft': 'auto' if is_user else '0',
                'marginRight': '0' if is_user else 'auto',
                'border': 'none' if is_user else '1px solid #e0f2f1',
                'overflowWrap': 'break-word', 
                'wordWrap': 'break-word'
            }
            
            label_text = "AI" if not is_user else None
            message_element = html.Div([
                html.Div(label_text, style={
                    'fontSize': '11px', 
                    'fontWeight': 'bold', 
                    'marginBottom': '3px',
                    'color': '#00796b',
                    'display': 'none' if is_user else 'block'
                }) if label_text else None,
                dcc.Markdown(msg["content"], style={'fontSize': '14px','lineHeight': '1.4'}),
                html.Div([
                    html.Span(msg["timestamp"], style={'fontSize': '11px','color': '#777'}),
                    html.Div([
                        html.Button("Copy", id={"type": "copy-button", "index": idx}, n_clicks=0, style={
                            'border': 'none', 
                            'background': 'none', 
                            'fontSize': '11px',
                            'color': '#00796b',
                            'cursor': 'pointer', 
                            'padding': '2px 5px'
                        }),
                        html.Button("👍", id={"type": "upvote-button", "index": idx}, n_clicks=0, style={
                            'border': 'none', 
                            'background': 'none', 
                            'fontSize': '11px',
                            'cursor': 'pointer', 
                            'padding': '2px 3px'
                        }),
                        html.Button("👎", id={"type": "downvote-button", "index": idx}, n_clicks=0, style={
                            'border': 'none', 
                            'background': 'none', 
                            'fontSize': '11px',
                            'cursor': 'pointer', 
                            'padding': '2px 3px'
                        })
                    ], style={'display': 'flex'})
                ], style={
                    'display': 'flex', 
                    'justifyContent': 'space-between', 
                    'alignItems': 'center',
                    'marginTop': '5px', 
                    'paddingTop': '5px', 
                    'borderTop': '1px solid #e0f2f1'
                })
            ], style=bubble_style)
            chat_display.append(message_element)
    
    return chat_display

def create_database_dropdown(db_id, db_data):
    """Create a dropdown component for a single database result."""
    status = db_data.get('status', 'pending')
    db_name = db_data.get('display_name', db_id)
    content = db_data.get('content', '')
    
    # Determine status icon and color
    if status == 'pending':
        status_icon = '⏳'
        header_color = '#ffa726'  # Orange
    elif status == 'streaming':
        status_icon = '🔄'
        header_color = '#42a5f5'  # Blue
    elif status == 'completed':
        status_icon = '✅'
        header_color = '#66bb6a'  # Green
    elif status == 'error':
        status_icon = '❌'
        header_color = '#ef5350'  # Red
    else:
        status_icon = '❓'
        header_color = '#bdbdbd'  # Gray
    
    return html.Details([
        html.Summary([
            html.Span(f"{status_icon} {db_name}", style={
                'cursor': 'pointer',
                'padding': '8px 12px',
                'fontSize': '14px',
                'fontWeight': 'bold',
                'color': 'white'
            })
        ], style={
            'backgroundColor': header_color,
            'borderRadius': '6px',
            'marginBottom': '5px',
            'listStyle': 'none',
            'outline': 'none'
        }),
        html.Div([
            dcc.Markdown(content) if content else html.Div("Waiting for response...", style={
                'color': '#999',
                'fontStyle': 'italic'
            })
        ], style={
            'padding': '10px',
            'backgroundColor': '#f9f9f9',
            'borderRadius': '6px',
            'border': '1px solid #e0e0e0',
            'marginTop': '5px',
            'maxHeight': '300px',
            'overflowY': 'auto'
        }, id={'type': 'database-content', 'index': db_id})
    ], id={'type': 'database-dropdown', 'index': db_id}, 
    open=status == 'streaming',  # Auto-open if streaming
    style={
        'marginBottom': '10px'
    })

# --- GENERATE RESPONSE WITH DATABASE TRACKING ---
def generate_response(conversation):
    """Generate a response using the model and update global state"""
    global assistant_response_chunks, is_generating, current_conversation, start_time
    global database_results, active_databases
    
    is_generating = True
    assistant_response_chunks = []
    database_results = {}
    active_databases = []
    start_time = time.time()
    current_section = "main"  # Track which section we're in
    
    try:
        stream = model(conversation)
        for response_chunk in stream:
            if isinstance(response_chunk, (str, bytes)):
                chunk_str = str(response_chunk)
                
                # Detect research plan
                if "---\n# 📋 Research Plan" in chunk_str:
                    current_section = "research_plan"
                
                # Detect database status blocks
                if "**Database:**" in chunk_str and "**Status:**" in chunk_str:
                    # Parse database info
                    lines = chunk_str.strip().split('\n')
                    db_display_name = None
                    status_summary = None
                    
                    for line in lines:
                        if line.startswith("**Database:**"):
                            db_display_name = line.replace("**Database:**", "").strip()
                        elif line.startswith("**Status:**"):
                            status_summary = line.replace("**Status:**", "").strip()
                    
                    if db_display_name:
                        db_id = str(uuid.uuid4())
                        database_results[db_id] = {
                            'display_name': db_display_name,
                            'status': 'completed' if '✅' in status_summary else 'error',
                            'content': status_summary,
                            'timestamp': datetime.now().isoformat()
                        }
                        active_databases.append(db_id)
                        current_section = f"database_{db_id}"
                
                # Detect summary section
                elif "## 📊 Research Summary" in chunk_str:
                    current_section = "summary"
                
                # Append to appropriate section
                assistant_response_chunks.append(chunk_str)
                
        generation_time = round(time.time() - start_time, 1)
        final_content = "".join(assistant_response_chunks)
        
        # Store database results in the message if any were found
        message_data = {
            "role": "assistant", 
            "content": final_content,
            "timestamp": f"{datetime.now().strftime('%I:%M %p')} ({generation_time}s)"
        }
        
        if database_results:
            message_data["database_results"] = database_results
            
        current_conversation = conversation + [message_data]
        
    except Exception as e:
        print(f"Error in generate_response: {str(e)}")
        generation_time = round(time.time() - start_time, 1) if start_time else 0
        error_content = f"Sorry, an error occurred generating the response."
        current_conversation = conversation + [{
            "role": "assistant", "content": error_content,
            "timestamp": f"{datetime.now().strftime('%I:%M %p')} (Error after {generation_time}s)"
        }]
    finally:
        is_generating = False
        database_results = {}
        active_databases = []

# --- CALLBACKS ---

# Initial chat display
@app.callback(
    Output('chat-history', 'children'),
    Input('conversation-store', 'data'),
    Input('database-results-store', 'data')
)
def display_conversation(conversation, database_results_data):
    """Display the current conversation with database dropdowns."""
    if conversation is None: return []
    return format_messages(conversation, database_results_data)

# Character counter
@app.callback(
    Output('char-counter', 'children'),
    Output('char-counter', 'style'),
    Input('user-input', 'value')
)
def update_char_counter(value):
    """Update the character counter."""
    if not value: return "", {'display': 'none'}
    count = len(value)
    threshold_warn = 0.7 * MAX_MESSAGE_LENGTH
    threshold_danger = 0.9 * MAX_MESSAGE_LENGTH
    color = '#00796b' if count < threshold_warn else ('orange' if count < threshold_danger else 'red')
    return f"{count}/{MAX_MESSAGE_LENGTH}", {
        'fontSize': '11px', 'color': color, 'position': 'absolute',
        'right': '10px', 'bottom': '-18px', 'display': 'block'
    }

# Typing indicator
@app.callback(
    Output('typing-indicator', 'style'),
    Input('interval-component', 'disabled'),
    State('typing-indicator', 'style')
)
def update_typing_indicator(is_disabled, current_style):
    """Update the typing indicator visibility."""
    new_display = 'none' if is_disabled else 'block'
    if current_style and current_style.get('display') == new_display:
        return no_update
    return {
        'color': '#00796b', 'fontSize': '12px', 'fontStyle': 'italic',
        'padding': '5px 10px', 'display': new_display
    }

# Client-side callback for scrolling
clientside_callback(
    """
    function(conversationData, intervalDisabled, dbResults) {
        window.dashChatState = window.dashChatState || {};
        var state = window.dashChatState;

        var chatContainer = document.getElementById('chat-history');
        if (!chatContainer) {
            return window.dash_clientside.no_update;
        }

        if (state.scrollListenerAttached === undefined) {
            state.userScrolledUp = false;
            state.previousIntervalDisabled = intervalDisabled;
            state.scrollListenerAttached = true;

            chatContainer.addEventListener('scroll', function() {
                const threshold = 30;
                let isAtBottom = chatContainer.scrollHeight - chatContainer.scrollTop - chatContainer.clientHeight < threshold;
                state.userScrolledUp = !isAtBottom;
            }, { passive: true });
        }

        let generationJustFinished = intervalDisabled && !state.previousIntervalDisabled;
        if (generationJustFinished) {
            state.userScrolledUp = false;
        }
        state.previousIntervalDisabled = intervalDisabled;

        setTimeout(function() {
            if (!state.userScrolledUp) {
                chatContainer.scrollTo({
                    top: chatContainer.scrollHeight,
                    behavior: 'smooth'
                });
            }
        }, 100);

        return performance.now();
    }
    """,
    Output('scroll-helper-output', 'data-timestamp'),
    Input('conversation-store', 'data'),
    Input('interval-component', 'disabled'),
    Input('database-results-store', 'data')
)

# Handle user input submission
@app.callback(
    Output('interval-component', 'disabled'),
    Output('conversation-store', 'data'),
    Output('user-input', 'value'),
    Output('submit-button', 'disabled'),
    Input('submit-button', 'n_clicks'),
    Input('user-input', 'n_submit'),
    State('user-input', 'value'),
    State('conversation-store', 'data'),
    State('interval-component', 'disabled'),
    prevent_initial_call=True
)
def handle_user_input(n_clicks, n_submit, user_message, conversation, interval_disabled):
    """Handle user input submission and trigger response generation."""
    global current_conversation
    triggered_by_click = n_clicks is not None
    triggered_by_enter = n_submit is not None

    if not (triggered_by_click or triggered_by_enter) or not user_message or not user_message.strip():
        return interval_disabled, conversation, user_message or "", not interval_disabled

    if not interval_disabled:
        return no_update, no_update, user_message, True

    user_msg = {"role": "user", "content": user_message.strip(), "timestamp": datetime.now().strftime("%I:%M %p")}
    updated_conversation = conversation + [user_msg]
    current_conversation = updated_conversation.copy()
    thread = Thread(target=generate_response, args=(updated_conversation,))
    thread.start()
    return False, updated_conversation, "", True

# Update streaming response with database results
@app.callback(
    Output('conversation-store', 'data', allow_duplicate=True),
    Output('database-results-store', 'data'),
    Output('active-databases-store', 'data'),
    Output('interval-component', 'disabled', allow_duplicate=True),
    Output('submit-button', 'disabled', allow_duplicate=True),
    Input('interval-component', 'n_intervals'),
    State('conversation-store', 'data'),
    prevent_initial_call=True
)
def update_streaming_response(n_intervals, conversation_in_store):
    """Update the displayed response while the AI is generating, including database results."""
    global assistant_response_chunks, is_generating, current_conversation, start_time
    global database_results, active_databases

    if not is_generating and not assistant_response_chunks:
        if conversation_in_store != current_conversation:
            # Get database results from the last message if available
            last_msg = current_conversation[-1] if current_conversation else {}
            db_results = last_msg.get('database_results', {})
            return current_conversation, db_results, [], True, False
        return no_update, no_update, no_update, True, False

    messages_to_display = conversation_in_store.copy()
    current_response_content = "".join(assistant_response_chunks)
    elapsed_time = round(time.time() - start_time, 1) if start_time else 0

    if is_generating:
        timestamp_text = f"{TYPING_INDICATOR} ({elapsed_time}s)"
    else:
        if current_conversation and len(current_conversation) > 0 and current_conversation[-1]['role'] == 'assistant':
            timestamp_text = current_conversation[-1]['timestamp']
        else:
            timestamp_text = f"{datetime.now().strftime('%I:%M %p')} ({elapsed_time}s)"

    # Update the message
    if messages_to_display and messages_to_display[-1]['role'] == 'assistant':
        messages_to_display[-1]['content'] = current_response_content
        messages_to_display[-1]['timestamp'] = timestamp_text
        if database_results:
            messages_to_display[-1]['database_results'] = database_results
    else:
        message_data = {
            "role": "assistant", 
            "content": current_response_content, 
            "timestamp": timestamp_text
        }
        if database_results:
            message_data['database_results'] = database_results
        messages_to_display.append(message_data)

    if not is_generating:
        # Get database results from the last message if available
        last_msg = current_conversation[-1] if current_conversation else {}
        db_results = last_msg.get('database_results', {})
        return current_conversation, db_results, [], True, False
    else:
        return messages_to_display, database_results, active_databases, False, True

# Export conversation
@app.callback(
    Output('download-conversation', 'data'),
    Input('export-button', 'n_clicks'),
    State('conversation-store', 'data'),
    prevent_initial_call=True
)
def export_conversation(n_clicks, conversation):
    """Export the conversation as a JSON file."""
    if n_clicks:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return dict(
            content=json.dumps(conversation, indent=2),
            filename=f"aegis_chat_conversation_{timestamp}.json",
            type="application/json"
        )
    return no_update

# Reset conversation
@app.callback(
    Output('conversation-store', 'data', allow_duplicate=True),
    Output('database-results-store', 'data', allow_duplicate=True),
    Output('active-databases-store', 'data', allow_duplicate=True),
    Output('interval-component', 'disabled', allow_duplicate=True),
    Output('submit-button', 'disabled', allow_duplicate=True),
    Output('user-input', 'value', allow_duplicate=True),
    Input('new-chat-button', 'n_clicks'),
    prevent_initial_call=True
)
def reset_conversation(n_clicks):
    """Reset the conversation to the initial greeting."""
    global current_conversation, assistant_response_chunks, is_generating, start_time
    global database_results, active_databases
    
    if n_clicks:
        assistant_response_chunks = []
        is_generating = False
        start_time = None
        database_results = {}
        active_databases = []
        new_initial_state = [{"role": "assistant", "content": greeting, "timestamp": datetime.now().strftime("%I:%M %p")}]
        current_conversation = new_initial_state.copy()
        return new_initial_state, {}, [], True, False, ""
    return no_update, no_update, no_update, no_update, no_update, no_update

# --- Run the app (for standalone testing) ---
if __name__ == '__main__':
    print("Running Dash app with dropdowns locally for testing...")
    app.run_server(debug=True, port=8051)