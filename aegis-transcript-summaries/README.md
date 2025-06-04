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

### 3. Generate Research Plans
```bash
python section_prompts_to_research_plans.py
```

### 4. Generate Final Sections
```bash
python research_plans_to_final_sections.py
```

## Output

**Research Plans** are saved in `research_plans/TranscriptName_timestamp/`:
- `transcript.txt` - Extracted PDF text
- `{section}_research_plan.md` - Strategic research plan for each section
- `research_plans_summary.md` - Combined overview

**Final Sections** are saved in `final_sections/TranscriptName_timestamp/`:
- `{section}_final_section.md` - Final formatted section content
- `complete_earnings_analysis.md` - Full analysis report

## File Structure
```
aegis-transcript-summaries/
├── config.json                           # Configuration settings
├── summary_template.html                 # Section configuration interface
├── template_to_section_prompts.py        # Generate section prompts
├── section_prompts_to_research_plans.py  # Generate research plans
├── research_plans_to_final_sections.py   # Generate final sections
├── section_prompts/                      # Generated section prompts
├── input_transcript/                     # PDF input folder
├── research_plans/                       # Research plans output
└── final_sections/                       # Final analysis output
```