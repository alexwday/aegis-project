# AEGIS Transcript Analysis V2 - Research Plan Generation Workflow

This project creates iterative research plans for extracting content from earnings call transcripts. The system builds context progressively as each section's research plan is created.

## Workflow Overview

The process follows these sequential steps:

1. **Template Configuration** → Section extraction → **Research Plan Generation** → Analysis Execution
2. Business users configure sections in a visual HTML template
3. Section instructions are extracted to structured JSON
4. Iterative research plans are created section-by-section with full context
5. Research plans guide downstream analysis and extraction

## File Structure and Flow

```
0_document_template.html          # Visual section configuration (INPUT: Business configures)
        ↓ (extraction)
1_document_template_extraction.py # Extracts sections from HTML template
        ↓ (generates)
2_section_instructions.json       # Structured section instructions (INTERMEDIATE)
        ↓ (used by)
3_research_plan_system_prompt.py  # System prompt generator for iterative planning
        ↓ (supports)
4_transcript_input_pdf/           # Folder containing transcript PDF (INPUT: Business provides)
        ↓ (processed by)
5_create_research_plan.py         # Main orchestration script (EXECUTION)
        ↓ (generates)
6_research_plan.json             # Final research plans (OUTPUT)
```

## Detailed Component Description

### 0_document_template.html
- **Purpose**: Visual interface for business users to configure analysis sections
- **Features**: 
  - Drag-and-drop section reordering
  - Enable/disable sections
  - Edit section descriptions and requirements
  - Save configuration embedded in HTML
- **Usage**: Open in browser, configure sections, save file

### 1_document_template_extraction.py
- **Purpose**: Extracts section configuration from HTML template
- **Input**: 0_document_template.html
- **Output**: 2_section_instructions.json
- **Run**: `python 1_document_template_extraction.py`

### 2_section_instructions.json
- **Purpose**: Structured section instructions for analysis
- **Format**: JSON with metadata and section array
- **Content**: Section ID, name, enabled status, detailed description
- **Usage**: Referenced by research plan creation process

### 3_research_plan_system_prompt.py
- **Purpose**: Generates iterative system prompts for LLM calls
- **Key Feature**: Context building across sections
- **Sections Structure**:
  - **Prior Research Plans**: Completed sections (for context/avoiding duplication)
  - **Current Section**: Active section to create research plan for
  - **Downstream Sections**: Remaining sections (for awareness/appropriate assignment)

### 4_transcript_input_pdf/
- **Purpose**: Input folder for transcript PDF files
- **Usage**: Place earnings call transcript PDF in this folder
- **Format**: Readable text PDF (not scanned images)
- **Processing**: Text extracted via PyPDF2

### 5_create_research_plan.py
- **Purpose**: Main orchestration script that creates research plans iteratively
- **Authentication**: OAuth/SSL support (follows corporate security patterns)
- **Process**:
  1. Load section instructions
  2. Extract PDF transcript text
  3. For each enabled section:
     - Generate prompt with prior context
     - Call LLM to create research plan
     - Add result to context for next section
  4. Save all research plans to JSON

### 6_research_plan.json
- **Purpose**: Final output containing all research plans
- **Format**: JSON with metadata and research plans array
- **Content**: Structured research plans for each section
- **Usage**: Guides downstream analysis and content extraction

## Iterative Context Building

The core innovation is the iterative approach that builds context:

1. **Section 1**: Creates research plan with no prior context
2. **Section 2**: Creates research plan with Section 1's plan as context
3. **Section 3**: Creates research plan with Sections 1-2 as context
4. **Continue...** until all sections have research plans

This approach:
- **Avoids duplication** between sections
- **Enables smart content assignment** to most appropriate sections
- **Maintains consistency** across the full analysis
- **Builds comprehensive context** for better decision-making

## Configuration

### config.json
```json
{
  "base_url": "your-api-base-url",           # Custom OpenAI endpoint (optional)
  "oauth_endpoint": "your-oauth-endpoint",   # OAuth authentication endpoint
  "client_id": "your-client-id",             # OAuth client ID
  "client_secret": "your-client-secret",     # OAuth client secret
  "ssl_cert_path": "rbc-ca-bundle.cer",      # SSL certificate path
  "openai_model": "gpt-4",                   # LLM model to use
  "max_tokens": 8000,                        # Maximum response tokens
  "temperature": 0.1                         # LLM temperature (low for consistency)
}
```

### Authentication Options
1. **OAuth**: Configure oauth_endpoint, client_id, client_secret
2. **Direct API Key**: Set OPENAI_API_KEY environment variable
3. **SSL**: Place certificate file and update ssl_cert_path

## Usage Instructions

### 1. Configure Sections
```bash
# Open template in browser to configure sections
open 0_document_template.html
# Configure sections, save file
```

### 2. Extract Section Instructions
```bash
python 1_document_template_extraction.py
# Generates: 2_section_instructions.json
```

### 3. Prepare Transcript
```bash
# Copy transcript PDF to input folder
cp your_transcript.pdf 4_transcript_input_pdf/
```

### 4. Create Research Plans
```bash
# Ensure authentication is configured in config.json
python 5_create_research_plan.py
# Generates: 6_research_plan.json
```

### 5. Review Results
```bash
# Examine the generated research plans
cat 6_research_plan.json | jq .
```

## Dependencies

Install required packages:
```bash
pip install openai PyPDF2 beautifulsoup4 requests cryptography
```

## Error Handling

The system includes comprehensive error handling:
- **Missing files**: Clear error messages for missing inputs
- **PDF extraction**: Graceful handling of unreadable PDFs
- **Authentication**: Fallback between OAuth and API key
- **LLM calls**: Retry logic and detailed error logging
- **JSON parsing**: Fallback to text storage if JSON parsing fails

## Logging

All operations are logged to:
- `research_plan_creator.log`: Detailed processing logs
- Console output: Real-time progress updates

## Next Steps

After research plans are created:
1. **Content Extraction**: Use research plans to guide systematic content extraction
2. **Analysis Generation**: Transform extracted content into business-quality analysis
3. **Report Assembly**: Combine all sections into comprehensive earnings analysis

This research planning phase sets the foundation for high-quality, comprehensive analysis by ensuring systematic, context-aware content identification and extraction strategy.