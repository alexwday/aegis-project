# -*- coding: utf-8 -*-
from dash import Dash, html, dcc, no_update, clientside_callback # Make sure clientside_callback is imported
from dash.dependencies import Input, Output, State
# import dash_bootstrap_components as dbc # Keep commented if not used
import time
from threading import Thread
from datetime import datetime
import os
import json

# Assuming your model import works correctly in your Dataiku environment
from aegis.src.chat_model.model import model

# Define the app instance (assuming Dataiku provides this or you define it)
# from dataiku.dash import App
# app = App()
# For standalone testing:
app = Dash(__name__) # Minimal Dash app initialization

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
    # dcc.Store(id="scroll-trigger", data=0), # No longer needed for server-side trigger
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

# --- FORMAT MESSAGES (UPDATED FOR TEAL THEME) ---
def format_messages(messages):
    """Format conversation messages for display, rendering content as Markdown."""
    chat_display = []
    for idx, msg in enumerate(messages):
        is_user = msg["role"] == "user"
        bubble_style = {
            'padding': '10px 15px', 
            'borderRadius': '8px', 
            'maxWidth': '85%',
            'marginBottom': '10px', 
            'boxShadow': '0 1px 2px rgba(0, 121, 107, 0.15)',  # Teal shadow
            'backgroundColor': '#b2dfdb' if is_user else 'white',  # Teal 100 for user
            'marginLeft': 'auto' if is_user else '0',
            'marginRight': '0' if is_user else 'auto',
            'border': 'none' if is_user else '1px solid #e0f2f1',  # Teal 50 border
            'overflowWrap': 'break-word', 
            'wordWrap': 'break-word'
        }
        label_text = "AI" if not is_user else None
        message_element = html.Div([
            html.Div(label_text, style={
                'fontSize': '11px', 
                'fontWeight': 'bold', 
                'marginBottom': '3px',
                'color': '#00796b',  # Teal 700
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
                        'color': '#00796b',  # Teal 700
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
                'borderTop': '1px solid #e0f2f1'  # Teal 50 border
            })
        ], style=bubble_style)
        chat_display.append(message_element)
    return chat_display

# --- GENERATE RESPONSE (No change here) ---
def generate_response(conversation):
    """Generate a response using the model and update global state"""
    global assistant_response_chunks, is_generating, current_conversation, start_time
    is_generating = True
    assistant_response_chunks = []
    start_time = time.time()
    try:
        stream = model(conversation)
        for response_chunk in stream:
             if isinstance(response_chunk, (str, bytes)):
                 assistant_response_chunks.append(str(response_chunk))
        generation_time = round(time.time() - start_time, 1)
        final_content = "".join(assistant_response_chunks)
        current_conversation = conversation + [{
            "role": "assistant", "content": final_content,
            "timestamp": f"{datetime.now().strftime('%I:%M %p')} ({generation_time}s)"
        }]
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

# --- CALLBACKS ---

# Initial chat display
@app.callback(
    Output('chat-history', 'children'),
    Input('conversation-store', 'data')
)
def display_conversation(conversation):
    """Display the current conversation."""
    if conversation is None: return []
    return format_messages(conversation)

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


# *** REVISED CLIENTSIDE CALLBACK FOR SCROLLING ***
clientside_callback(
    """
    function(conversationData, intervalDisabled) {
        // Use window scope to store state persistently across callbacks
        window.dashChatState = window.dashChatState || {};
        var state = window.dashChatState;

        var chatContainer = document.getElementById('chat-history');
        if (!chatContainer) {
            return window.dash_clientside.no_update;
        }

        // --- Initialize state and scroll listener (only once) ---
        if (state.scrollListenerAttached === undefined) {
            state.userScrolledUp = false; // Flag to track if user manually scrolled
            state.previousIntervalDisabled = intervalDisabled; // Track interval state changes
            state.scrollListenerAttached = true; // Ensure listener is added only once

            // Add event listener for user scrolling
            chatContainer.addEventListener('scroll', function() {
                const threshold = 30; // Increased threshold: How many pixels from bottom to consider "at bottom"
                // Check if scroll position is near the bottom
                let isAtBottom = chatContainer.scrollHeight - chatContainer.scrollTop - chatContainer.clientHeight < threshold;

                // Update the flag based *only* on whether user is away from bottom
                state.userScrolledUp = !isAtBottom;
                // if (!isAtBottom && !state.userScrolledUp) console.log("Scroll Lock ON");
                // if (isAtBottom && state.userScrolledUp) console.log("Scroll Lock OFF (scrolled to bottom)");

            }, { passive: true }); // Use passive listener if possible
            // console.log("Scroll listener attached.");
        }

        // --- Check if generation just finished ---
        // Generation finishes when interval becomes disabled (true)
        let generationJustFinished = intervalDisabled && !state.previousIntervalDisabled;
        if (generationJustFinished) {
            // console.log("Generation finished, resetting scroll lock.");
            // Reset the scroll lock when generation completes
            state.userScrolledUp = false;
        }
        // Update the stored interval state for the next check
        state.previousIntervalDisabled = intervalDisabled;

        // --- Decide whether to auto-scroll ---
        // Schedule the check and potential scroll within setTimeout
        // This allows the DOM to render new messages AND checks the latest scroll lock state
        setTimeout(function() {
            // Check the flag *inside* the timeout, just before scrolling
            if (!state.userScrolledUp) {
                // console.log("Timeout Check: Scrolling condition met.");
                chatContainer.scrollTo({
                    top: chatContainer.scrollHeight,
                    behavior: 'smooth' // or 'auto' for instant scroll
                });
            } else {
                // console.log("Timeout Check: Scrolling skipped (User scrolled up).");
            }
        }, 100); // 100ms delay. Adjust if needed.

        // Return a changing value for the dummy output to ensure callback fires
        return performance.now();
    }
    """,
    Output('scroll-helper-output', 'data-timestamp'), # Dummy output
    Input('conversation-store', 'data'),          # Trigger on new message data
    Input('interval-component', 'disabled')       # Trigger when generation starts/stops
)
# *** END OF REVISED CLIENTSIDE CALLBACK ***


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
    triggered_by_click = n_clicks is not None # Simpler check if button exists
    triggered_by_enter = n_submit is not None # Simpler check if enter exists

    # Check if triggered and message is valid
    if not (triggered_by_click or triggered_by_enter) or not user_message or not user_message.strip():
        return interval_disabled, conversation, user_message or "", not interval_disabled

    # Prevent sending if already generating
    if not interval_disabled:
        # print("Already generating...") # Optional user feedback
        return no_update, no_update, user_message, True # Keep things as they are

    user_msg = {"role": "user", "content": user_message.strip(), "timestamp": datetime.now().strftime("%I:%M %p")}
    updated_conversation = conversation + [user_msg]
    current_conversation = updated_conversation.copy()
    thread = Thread(target=generate_response, args=(updated_conversation,))
    thread.start()
    return False, updated_conversation, "", True


# Update streaming response
@app.callback(
    Output('conversation-store', 'data', allow_duplicate=True),
    Output('interval-component', 'disabled', allow_duplicate=True),
    Output('submit-button', 'disabled', allow_duplicate=True),
    Input('interval-component', 'n_intervals'),
    State('conversation-store', 'data'),
    prevent_initial_call=True
)
def update_streaming_response(n_intervals, conversation_in_store):
    """Update the displayed response while the AI is generating."""
    global assistant_response_chunks, is_generating, current_conversation, start_time

    if not is_generating and not assistant_response_chunks:
        if conversation_in_store != current_conversation:
             return current_conversation, True, False
        return no_update, True, False

    messages_to_display = conversation_in_store.copy()
    current_response_content = "".join(assistant_response_chunks)
    elapsed_time = round(time.time() - start_time, 1) if start_time else 0

    if is_generating:
        timestamp_text = f"{TYPING_INDICATOR} ({elapsed_time}s)"
    else:
        if current_conversation and len(current_conversation) > 0 and current_conversation[-1]['role'] == 'assistant':
             timestamp_text = current_conversation[-1]['timestamp']
        else:
             timestamp_text = f"{datetime.now().strftime('%I:%M %p')} ({elapsed_time}s)" # Fallback

    if messages_to_display and messages_to_display[-1]['role'] == 'assistant':
        messages_to_display[-1]['content'] = current_response_content
        messages_to_display[-1]['timestamp'] = timestamp_text
    else:
        messages_to_display.append({
            "role": "assistant", "content": current_response_content, "timestamp": timestamp_text
        })

    if not is_generating:
        return current_conversation, True, False
    else:
        return messages_to_display, False, True


# Export conversation
@app.callback(
    Output('download-conversation', 'data'),
    Input('export-button', 'n_clicks'),
    State('conversation-store', 'data'),
    prevent_initial_call=True
)
def export_conversation(n_clicks, conversation):
    """Export the conversation as a JSON file."""
    if n_clicks: # Simpler check
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
    Output('interval-component', 'disabled', allow_duplicate=True),
    Output('submit-button', 'disabled', allow_duplicate=True),
    Output('user-input', 'value', allow_duplicate=True),
    Input('new-chat-button', 'n_clicks'),
    prevent_initial_call=True
)
def reset_conversation(n_clicks):
    """Reset the conversation to the initial greeting."""
    global current_conversation, assistant_response_chunks, is_generating, start_time
    if n_clicks: # Simpler check
        assistant_response_chunks = []
        is_generating = False
        start_time = None
        new_initial_state = [{"role": "assistant", "content": greeting, "timestamp": datetime.now().strftime("%I:%M %p")}]
        current_conversation = new_initial_state.copy()
        # Also reset the client-side scroll lock state if the user starts a new chat
        # We can't directly call JS from Python, but the next scroll callback will re-init if needed
        # Or we could add another clientside callback triggered by the new chat button if necessary.
        return new_initial_state, True, False, ""
    return no_update, no_update, no_update, no_update

# --- Run the app (for standalone testing) ---
if __name__ == '__main__':
    print("Running Dash app locally for testing...")
    app.run_server(debug=True, port=8050)