# AEGIS Transcript Analysis V2

Revamped transcript analysis system based on comprehensive extraction guide and JSON format specifications.

## Project Overview

This new version implements:

1. **Comprehensive Template System**: Based on the comprehensive extraction guide content for each section
2. **Structured JSON Output**: Uses transcript JSON format with tool calling for precise data extraction
3. **Research Planning System**: Methodical planning phase that identifies content and structure before extraction
4. **Tool-Based Extraction**: Uses function calling to generate properly formatted JSON output per section
5. **Overall System Prompt**: Comprehensive system-wide instructions based on extraction guides

## Workflow

1. **Template → Section Prompts**: Convert comprehensive template into section-specific prompts
2. **Research Planning**: Analyze transcript and plan extraction approach for each section
3. **JSON Extraction**: Use tool calling to extract structured JSON data per section
4. **Report Assembly**: Combine JSON sections into final HTML report

## Key Files

- `comprehensive_summary_template.html` - New template based on extraction guide
- `template_to_section_prompts.py` - Converts template to section prompts
- `system_prompt.md` - Overall system prompt with comprehensive instructions
- `section_prompts_to_research_plans.py` - Plans content extraction approach
- `research_plans_to_json_sections.py` - Executes extraction with tool calling
- `config.json` - Configuration file
- `TRANSCRIPT_JSON_FORMAT.md` - JSON format specification (copied from original)
- `COMPREHENSIVE_EXTRACTION_GUIDE.md` - Extraction guide (copied from original)

## Setup

1. Copy config.json from original project and update paths
2. Place transcript PDFs in `input_transcripts/`
3. Run scripts in sequence or use the main workflow script

## Output

Each section generates a JSON file following the transcript format specification, containing:
- section_name, section_title, section_statement
- content with subsections and quotes
- Full metadata including sentiment, speakers, key_metrics

These JSON files can be inserted into HTML templates for final report generation.