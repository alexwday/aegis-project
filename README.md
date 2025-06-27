# AEGIS - Financial Market Data Assistant

AEGIS (AI Enhanced Global Investment System) is an intelligent financial data analysis system that provides comprehensive research capabilities across earnings call transcripts, quarterly reports, supplementary packages, and investor relations summaries.

## Quick Start

### Prerequisites

- Python 3.8 or higher
- pip package manager

### Installation & Setup

1. **Clone or navigate to the project directory:**
   ```bash
   cd aegis-project
   ```

2. **Test the system structure (optional):**
   ```bash
   python3 test_system.py
   ```
   
   This verifies that all components are correctly configured before installation.

3. **Run the setup script:**
   ```bash
   ./setup.sh
   ```
   
   This will:
   - Create a Python virtual environment
   - Install all required dependencies
   - Set up the necessary Python packages

4. **Start the server:**
   ```bash
   python start_server.py
   ```
   
   The server will start on `http://localhost:8000`

5. **Open the chat interface:**
   
   Open your web browser and navigate to:
   ```
   http://localhost:8000
   ```
   
   Or directly open the HTML file:
   ```bash
   open chat_interface.html
   ```

### Environment Configuration

Before running AEGIS, you may need to configure environment variables. Create a `.env` file in the project root:

```env
# OpenAI API Configuration (if using OpenAI)
OPENAI_API_KEY=your_openai_api_key_here

# Database Configuration (when implementing real databases)
# Add your database connection strings here

# Optional: Logging Configuration
LOG_LEVEL=INFO
```

## Using AEGIS

### Chat Interface

The web interface provides an intuitive chat experience where you can:

- **Ask financial questions** with specific context (bank, quarter, year)
- **Filter databases** to focus on specific data sources
- **View streaming responses** as they're generated
- **Access database filtering** via the "Database Filters" section

### Database Sources

AEGIS has access to four main financial data sources:

1. **Earnings Call Transcripts** - Complete transcripts of quarterly earnings calls
2. **Quarterly Reports** - Official quarterly financial reports and statements  
3. **Supplementary Packages** - Additional financial data and peer benchmarking
4. **IR Call Summaries** - Structured summaries of investor relations calls

### Example Queries

AEGIS works best with specific, contextual queries:

✅ **Good queries:**
- "What was Royal Bank of Canada's net income in Q3 2024?"
- "How did TD Bank's operating margin compare to Q2 2023 in Q2 2024?"
- "What guidance did Bank of Montreal's management provide for fiscal 2025?"
- "Compare RBC's Q4 2024 performance to Canadian banking peers"

❌ **Queries that need clarification:**
- "What was revenue last quarter?" (missing bank and specific quarter)
- "How did we perform?" (missing bank, time period, and metrics)
- "Show me the earnings" (missing context)

The system's clarifier agent will help you refine vague queries by asking for:
- **Specific banks** (e.g., Royal Bank of Canada, TD Bank, Bank of Montreal)
- **Specific time periods** (e.g., Q3 2024, fiscal year 2023)
- **Specific metrics** (e.g., net income, operating margin, return on equity)

## System Architecture

### Core Components

- **Router Agent** - Determines whether to use conversation context or research databases
- **Clarifier Agent** - Ensures queries have proper financial context (bank/quarter/year)
- **Planner Agent** - Selects appropriate databases for research
- **Database Subagents** - Query specific financial data sources
- **Summarizer Agent** - Synthesizes research results into comprehensive responses

### API Endpoints

- `GET /` - API information
- `GET /health` - Health check
- `POST /chat` - Process chat messages (supports streaming)
- `GET /docs` - API documentation

## Development Notes

### Current Status

This is the base framework with placeholder subagents. The system is ready for:

1. **Database Integration** - Connect real financial databases to each subagent
2. **Data Processing** - Implement actual search and analysis logic
3. **Authentication** - Add user authentication if needed
4. **Deployment** - Configure for production environments

### Placeholder Responses

Currently, all database subagents return sample data. To implement real functionality:

1. Navigate to `services/src/agents/database_subagents/[database_name]/subagent.py`
2. Replace the placeholder logic with actual database queries
3. Update the response format to match your data structure

### Key Files

- `setup.py` - Dependencies and package configuration
- `start_server.py` - Development server launcher
- `chat_interface.html` - Web-based chat interface
- `services/src/api.py` - FastAPI REST endpoints
- `services/src/global_prompts/` - System prompts and database configurations
- `services/src/agents/` - All AI agents and their configurations

## Troubleshooting

### Common Issues

1. **Server won't start:**
   - Ensure virtual environment is activated
   - Check all dependencies are installed: `pip install -e .`
   - Verify Python version (3.8+)

2. **Import errors:**
   - Run `pip install -e .` from the project root
   - Check that all required packages are in `setup.py`

3. **Database connection errors:**
   - Placeholder subagents don't connect to real databases yet
   - This is expected behavior in the current framework

4. **Chat interface not loading:**
   - Ensure server is running on `http://localhost:8000`
   - Check browser console for JavaScript errors
   - Try opening `chat_interface.html` directly

### Getting Help

- Check the `/health` endpoint for system status
- Review logs for detailed error information
- Ensure all environment variables are properly configured

## Next Steps

1. **Implement Database Connections** - Replace placeholder subagents with real data queries
2. **Add Authentication** - Implement user authentication if required
3. **Configure Production Deployment** - Set up for your target environment
4. **Customize Financial Metrics** - Tailor the system for your specific financial analysis needs

---

**Note:** This system is designed for financial market data analysis. All data should be from public sources and proper disclaimers should be maintained for any investment-related information.