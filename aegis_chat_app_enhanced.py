# -*- coding: utf-8 -*-
"""
Enhanced AEGIS Chat App with Real-time Database Research Dropdowns

This version displays individual database queries in collapsible dropdowns
that update in real-time as each subagent processes the query.
"""

from dash import Dash, html, dcc, no_update, clientside_callback
from dash.dependencies import Input, Output, State
import time
from threading import Thread
from datetime import datetime
import json
import uuid

# Import the enhanced model with dropdown support
from aegis.src.chat_model.model_with_dropdowns import model_with_dropdowns

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
    "timestamp": datetime.now().strftime("%I:%M %p"),
    "message_id": str(uuid.uuid4())
}]

# Global variables for tracking state
assistant_response_chunks = []
is_generating = False
current_conversation = initial_conversation.copy()
current_message_id = None
current_dropdowns = {}  # Track active dropdown states

# Layout with enhanced styling
app.layout = html.Div([
    # Header
    html.Div([
        html.Div([
            html.Div([
                html.Span("AEGIS", style={
                    'color': '#00796b',
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
                'backgroundColor': '#e0f2f1',
                'border': '1px solid #b2dfdb',
                'borderRadius': '4px',
                'cursor': 'pointer',
                'fontSize': '13px',
                'color': '#00796b'
            }),
            html.Button("Export", id="export-button", style={
                'padding': '5px 12px',
                'backgroundColor': '#004d40',
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
        'backgroundColor': '#e0f2f1',
        'borderRadius': '8px',
        'boxShadow': '0 2px 5px rgba(0, 121, 107, 0.15)',
        'marginBottom': '15px',
        'borderLeft': '4px solid #00796b'
    }),

    # Chat container
    html.Div([
        # Typing indicator
        html.Div("AI is typing...", id="typing-indicator", style={
            'color': '#00796b',
            'fontSize': '12px',
            'fontStyle': 'italic',
            'padding': '5px 10px',
            'display': 'none'
        }),

        # Chat messages
        html.Div(id="chat-history", style={
            'overflowY': 'auto',
            'height': 'calc(100vh - 210px)',
            'padding': '10px',
            'backgroundColor': '#f5f5f5'
        }),

        # Hidden scroll helper
        html.Div(id="scroll-helper-output")
    ], style={
        'backgroundColor': '#f5f5f5',
        'borderRadius': '8px',
        'boxShadow': '0 2px 5px rgba(0, 121, 107, 0.15)',
        'marginBottom': '15px',
        'overflow': 'hidden',
        'borderLeft': '4px solid #00796b'
    }),

    # Input area
    html.Div([
        html.Div([
            dcc.Input(
                id="user-input",
                type="text",
                placeholder="Ask a question...",
                maxLength=MAX_MESSAGE_LENGTH,
                style={
                    'width': '100%',
                    'padding': '10px 15px',
                    'border': '1px solid #b2dfdb',
                    'borderRadius': '6px',
                    'fontSize': '14px',
                    'boxSizing': 'border-box',
                    'backgroundColor': 'white'
                }
            ),
            html.Div(id="char-counter", style={
                'fontSize': '11px',
                'color': '#00796b',
                'position': 'absolute',
                'right': '10px',
                'bottom': '-18px',
                'display': 'none'
            })
        ], style={
            'position': 'relative',
            'width': 'calc(100% - 75px)',
            'marginRight': '10px'
        }),

        html.Button("Send", id="submit-button", style={
            'width': '65px',
            'padding': '10px 0',
            'backgroundColor': '#00796b',
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

    # Store components
    dcc.Store(id="conversation-store", data=initial_conversation),
    dcc.Store(id="dropdowns-store", data={}),
    dcc.Interval(id="interval-component", interval=500, n_intervals=0, disabled=True),
    dcc.Download(id="download-conversation")
], style={
    'width': '95%',
    'maxWidth': '1200px',
    'margin': '0 auto',
    'padding': '10px',
    'backgroundColor': '#e8f5e9',
    'fontFamily': '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    'height': '100vh',
    'boxSizing': 'border-box'
})

def create_database_dropdown(db_id, dropdown_data):
    """Create a collapsible dropdown for a database result."""
    status = dropdown_data.get('status', 'pending')
    db_name = dropdown_data.get('display_name', 'Unknown Database')
    content = dropdown_data.get('content', '')
    
    # Status styling
    status_configs = {
        'pending': {'icon': '⏳', 'color': '#ffa726', 'text': 'Pending'},
        'streaming': {'icon': '🔄', 'color': '#42a5f5', 'text': 'Querying'},
        'completed': {'icon': '✅', 'color': '#66bb6a', 'text': 'Complete'},
        'error': {'icon': '❌', 'color': '#ef5350', 'text': 'Error'}
    }
    
    config = status_configs.get(status, {'icon': '❓', 'color': '#bdbdbd', 'text': 'Unknown'})
    
    return html.Details([
        html.Summary([
            html.Span(f"{config['icon']} ", style={'fontSize': '16px'}),
            html.Span(db_name, style={
                'fontWeight': 'bold',
                'marginRight': '10px'
            }),
            html.Span(f"[{config['text']}]", style={
                'fontSize': '12px',
                'color': config['color'],
                'fontStyle': 'italic'
            })
        ], style={
            'cursor': 'pointer',
            'padding': '10px',
            'backgroundColor': '#f5f5f5',
            'borderRadius': '6px',
            'border': f'2px solid {config["color"]}',
            'marginBottom': '5px',
            'listStyle': 'none',
            'outline': 'none',
            'userSelect': 'none'
        }),
        html.Div([
            dcc.Markdown(content) if content else html.Div(
                "Waiting for response...", 
                style={'color': '#999', 'fontStyle': 'italic', 'padding': '10px'}
            )
        ], style={
            'padding': '15px',
            'backgroundColor': '#ffffff',
            'borderRadius': '6px',
            'border': '1px solid #e0e0e0',
            'marginTop': '5px',
            'maxHeight': '400px',
            'overflowY': 'auto'
        })
    ], 
    open=(status == 'streaming'),  # Auto-open when actively querying
    style={'marginBottom': '10px'})

def format_messages(messages, dropdowns_data=None):
    """Format conversation messages for display with dropdown support."""
    chat_display = []
    
    for msg in messages:
        is_user = msg["role"] == "user"
        message_id = msg.get("message_id", str(uuid.uuid4()))
        
        # Check if this message has associated dropdowns
        message_dropdowns = dropdowns_data.get(message_id, {}) if dropdowns_data else {}
        
        if not is_user and message_dropdowns:
            # Research response with dropdowns
            content_parts = msg["content"].split("---\n")
            
            # Container for the entire research response
            research_container = html.Div([
                # AI header
                html.Div([
                    html.Span("AI", style={
                        'fontSize': '11px',
                        'fontWeight': 'bold',
                        'color': '#00796b',
                    }),
                    html.Span(msg["timestamp"], style={
                        'fontSize': '11px',
                        'color': '#777',
                        'marginLeft': 'auto'
                    })
                ], style={
                    'display': 'flex',
                    'alignItems': 'center',
                    'marginBottom': '10px'
                }),
                
                # Research plan section (if present)
                html.Div([
                    dcc.Markdown(part) for part in content_parts if "📋 Research Plan" in part or "Research Statement" in part
                ], style={
                    'marginBottom': '15px',
                    'padding': '10px',
                    'backgroundColor': 'white',
                    'borderRadius': '8px',
                    'border': '1px solid #e0f2f1'
                }),
                
                # Database dropdowns container
                html.Div([
                    create_database_dropdown(db_id, dropdown_data)
                    for db_id, dropdown_data in sorted(message_dropdowns.items(), 
                                                     key=lambda x: x[1].get('timestamp', ''))
                ], style={
                    'marginBottom': '15px',
                    'padding': '10px',
                    'backgroundColor': '#fafafa',
                    'borderRadius': '8px',
                    'border': '1px dashed #b2dfdb'
                }),
                
                # Summary section (if present in content)
                html.Div([
                    dcc.Markdown(part) for part in content_parts if "📊 Research Summary" in part
                ], style={
                    'marginTop': '15px',
                    'padding': '10px',
                    'backgroundColor': 'white',
                    'borderRadius': '8px',
                    'border': '1px solid #e0f2f1'
                })
            ], style={
                'padding': '15px',
                'backgroundColor': 'white',
                'borderRadius': '8px',
                'border': '1px solid #e0f2f1',
                'marginBottom': '10px',
                'maxWidth': '85%',
                'boxShadow': '0 2px 4px rgba(0,0,0,0.1)'
            })
            
            chat_display.append(research_container)
        else:
            # Regular message bubble
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
            
            message_element = html.Div([
                html.Div("AI", style={
                    'fontSize': '11px',
                    'fontWeight': 'bold',
                    'marginBottom': '3px',
                    'color': '#00796b',
                    'display': 'none' if is_user else 'block'
                }) if not is_user else None,
                dcc.Markdown(msg["content"], style={'fontSize': '14px', 'lineHeight': '1.4'}),
                html.Div(msg["timestamp"], style={
                    'fontSize': '11px',
                    'color': '#777',
                    'marginTop': '5px'
                })
            ], style=bubble_style)
            
            chat_display.append(message_element)
    
    return chat_display

def generate_response(conversation):
    """Generate a response using the enhanced model with dropdown support."""
    global assistant_response_chunks, is_generating, current_conversation, start_time
    global current_message_id, current_dropdowns
    
    is_generating = True
    assistant_response_chunks = []
    current_message_id = str(uuid.uuid4())
    current_dropdowns = {}
    start_time = time.time()
    
    try:
        stream = model_with_dropdowns(conversation)
        
        for response_chunk in stream:
            if isinstance(response_chunk, dict):
                # Handle structured dropdown data
                if response_chunk.get("type") == "database_dropdowns_init":
                    # Initialize all dropdowns
                    current_dropdowns = response_chunk["dropdowns"]
                elif response_chunk.get("type") == "database_dropdown_update":
                    # Update specific dropdown
                    db_id = response_chunk["db_id"]
                    if db_id in current_dropdowns:
                        current_dropdowns[db_id]["status"] = response_chunk["status"]
                        current_dropdowns[db_id]["content"] = response_chunk["content"]
                        current_dropdowns[db_id]["timestamp"] = datetime.now().isoformat()
            else:
                # Regular text content
                assistant_response_chunks.append(str(response_chunk))
        
        # Finalize the response
        generation_time = round(time.time() - start_time, 1)
        final_content = "".join(assistant_response_chunks)
        
        message_data = {
            "role": "assistant",
            "content": final_content,
            "timestamp": f"{datetime.now().strftime('%I:%M %p')} ({generation_time}s)",
            "message_id": current_message_id
        }
        
        current_conversation = conversation + [message_data]
        
    except Exception as e:
        print(f"Error in generate_response: {str(e)}")
        generation_time = round(time.time() - start_time, 1) if start_time else 0
        error_content = f"Sorry, an error occurred: {str(e)}"
        current_conversation = conversation + [{
            "role": "assistant",
            "content": error_content,
            "timestamp": f"{datetime.now().strftime('%I:%M %p')} (Error after {generation_time}s)",
            "message_id": str(uuid.uuid4())
        }]
    finally:
        is_generating = False

# --- CALLBACKS ---

@app.callback(
    Output('chat-history', 'children'),
    Input('conversation-store', 'data'),
    Input('dropdowns-store', 'data')
)
def display_conversation(conversation, dropdowns_data):
    """Display the conversation with dropdown support."""
    if conversation is None:
        return []
    return format_messages(conversation, dropdowns_data)

@app.callback(
    Output('char-counter', 'children'),
    Output('char-counter', 'style'),
    Input('user-input', 'value')
)
def update_char_counter(value):
    """Update the character counter."""
    if not value:
        return "", {'display': 'none'}
    count = len(value)
    threshold_warn = 0.7 * MAX_MESSAGE_LENGTH
    threshold_danger = 0.9 * MAX_MESSAGE_LENGTH
    color = '#00796b' if count < threshold_warn else ('orange' if count < threshold_danger else 'red')
    return f"{count}/{MAX_MESSAGE_LENGTH}", {
        'fontSize': '11px', 'color': color, 'position': 'absolute',
        'right': '10px', 'bottom': '-18px', 'display': 'block'
    }

@app.callback(
    Output('typing-indicator', 'style'),
    Input('interval-component', 'disabled'),
    State('typing-indicator', 'style')
)
def update_typing_indicator(is_disabled, current_style):
    """Update typing indicator visibility."""
    new_display = 'none' if is_disabled else 'block'
    if current_style and current_style.get('display') == new_display:
        return no_update
    return {
        'color': '#00796b', 'fontSize': '12px', 'fontStyle': 'italic',
        'padding': '5px 10px', 'display': new_display
    }

# Client-side scrolling
clientside_callback(
    """
    function(conversationData, intervalDisabled) {
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
    Input('interval-component', 'disabled')
)

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
    """Handle user input submission."""
    global current_conversation
    
    triggered_by_click = n_clicks is not None
    triggered_by_enter = n_submit is not None

    if not (triggered_by_click or triggered_by_enter) or not user_message or not user_message.strip():
        return interval_disabled, conversation, user_message or "", not interval_disabled

    if not interval_disabled:
        return no_update, no_update, user_message, True

    user_msg = {
        "role": "user",
        "content": user_message.strip(),
        "timestamp": datetime.now().strftime("%I:%M %p"),
        "message_id": str(uuid.uuid4())
    }
    updated_conversation = conversation + [user_msg]
    current_conversation = updated_conversation.copy()
    
    thread = Thread(target=generate_response, args=(updated_conversation,))
    thread.start()
    
    return False, updated_conversation, "", True

@app.callback(
    Output('conversation-store', 'data', allow_duplicate=True),
    Output('dropdowns-store', 'data'),
    Output('interval-component', 'disabled', allow_duplicate=True),
    Output('submit-button', 'disabled', allow_duplicate=True),
    Input('interval-component', 'n_intervals'),
    State('conversation-store', 'data'),
    State('dropdowns-store', 'data'),
    prevent_initial_call=True
)
def update_streaming_response(n_intervals, conversation_in_store, dropdowns_in_store):
    """Update streaming response and dropdowns."""
    global assistant_response_chunks, is_generating, current_conversation, start_time
    global current_message_id, current_dropdowns

    if not is_generating and not assistant_response_chunks:
        if conversation_in_store != current_conversation:
            return current_conversation, dropdowns_in_store, True, False
        return no_update, no_update, True, False

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

    # Update or add the assistant message
    if messages_to_display and messages_to_display[-1]['role'] == 'assistant':
        messages_to_display[-1]['content'] = current_response_content
        messages_to_display[-1]['timestamp'] = timestamp_text
    else:
        messages_to_display.append({
            "role": "assistant",
            "content": current_response_content,
            "timestamp": timestamp_text,
            "message_id": current_message_id
        })

    # Update dropdowns store
    updated_dropdowns = dropdowns_in_store.copy()
    if current_dropdowns:
        updated_dropdowns[current_message_id] = current_dropdowns

    if not is_generating:
        return current_conversation, updated_dropdowns, True, False
    else:
        return messages_to_display, updated_dropdowns, False, True

@app.callback(
    Output('download-conversation', 'data'),
    Input('export-button', 'n_clicks'),
    State('conversation-store', 'data'),
    prevent_initial_call=True
)
def export_conversation(n_clicks, conversation):
    """Export conversation as JSON."""
    if n_clicks:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return dict(
            content=json.dumps(conversation, indent=2),
            filename=f"aegis_chat_conversation_{timestamp}.json",
            type="application/json"
        )
    return no_update

@app.callback(
    Output('conversation-store', 'data', allow_duplicate=True),
    Output('dropdowns-store', 'data', allow_duplicate=True),
    Output('interval-component', 'disabled', allow_duplicate=True),
    Output('submit-button', 'disabled', allow_duplicate=True),
    Output('user-input', 'value', allow_duplicate=True),
    Input('new-chat-button', 'n_clicks'),
    prevent_initial_call=True
)
def reset_conversation(n_clicks):
    """Reset conversation to initial state."""
    global current_conversation, assistant_response_chunks, is_generating, start_time
    global current_message_id, current_dropdowns
    
    if n_clicks:
        assistant_response_chunks = []
        is_generating = False
        start_time = None
        current_message_id = None
        current_dropdowns = {}
        new_initial_state = [{
            "role": "assistant",
            "content": greeting,
            "timestamp": datetime.now().strftime("%I:%M %p"),
            "message_id": str(uuid.uuid4())
        }]
        current_conversation = new_initial_state.copy()
        return new_initial_state, {}, True, False, ""
    return no_update, no_update, no_update, no_update, no_update

if __name__ == '__main__':
    print("Running Enhanced AEGIS Chat App with Database Dropdowns...")
    app.run_server(debug=True, port=8052)