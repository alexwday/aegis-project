# AEGIS Transcript Summaries - Setup Guide

Quick setup guide for processing earnings call transcripts into research plans.

## Setup

### 1. Create Virtual Environment
```bash
# From the aegis-project root directory
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install beautifulsoup4 PyPDF2 requests openai cryptography
```

### 3. Configure Settings
Edit `config.json` with your API credentials:
```json
{
  "base_url": "your-api-base-url",
  "oauth_endpoint": "your-oauth-endpoint", 
  "client_id": "your-client-id",
  "client_secret": "your-client-secret"
}
```

Or set environment variable for standard OpenAI:
```bash
export OPENAI_API_KEY=your_api_key
```

## Usage

### 1. Generate Section Prompts
```bash
python template_to_section_prompts.py
```
This creates section prompt files from `summary_template.html`.

### 2. Add Transcript PDFs
Place your PDF transcripts in the `input_transcript/` folder.

### 3. Process Transcripts
```bash
python section_prompts_to_research_plans.py
```

## Output

Results are saved in `research_plans/TranscriptName_timestamp/`:
- `transcript.txt` - Extracted PDF text
- `{section}_research_plan.md` - Strategic research plan for each section
- `research_plans_summary.md` - Combined overview

## File Structure
```
aegis-transcript-summaries/
├── config.json                           # Configuration settings
├── summary_template.html                 # Section configuration interface
├── template_to_section_prompts.py        # Generate section prompts
├── section_prompts_to_research_plans.py  # Main processing script
├── section_prompts/                      # Generated section prompts
├── input_transcript/                     # PDF input folder
└── research_plans/                       # Output folder
```