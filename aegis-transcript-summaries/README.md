# AEGIS Transcript Summaries

## Overview

This module provides a streamlined system for iterative earnings call transcript analysis. It generates XML-structured section prompts that integrate into a CO-STAR master prompt template for systematic analysis workflow.

## Core Files

- **`earnings_config_template.html`** - Interactive configuration interface for selecting sections and analysis widgets
- **`config_to_prompt.py`** - Converts HTML config into XML-structured section contexts
- **`master_prompt_template.py`** - CO-STAR master prompt template with XML structure

## Workflow

### 1. Configure Analysis Sections
Use the HTML interface to select which sections to analyze and what widgets to include for each section.

### 2. Generate Section Contexts  
Run the script to create XML-structured section contexts that define focus areas and analysis requirements.

### 3. Build Master Prompts
Use the master template to combine section contexts with transcript data and prior research plans into complete CO-STAR prompts.

## Usage

### 1. Configure Analysis Sections
```bash
open earnings_config_template.html
```
- Enable/disable sections using checkboxes
- Select analysis widgets for each section
- Reorder sections by dragging
- Save configuration

### 2. Generate Section Contexts
```bash
source ../venv/bin/activate
python3 config_to_prompt.py
```
Creates XML-structured section contexts in `section_prompts/` directory.

### 3. Build Master Prompts
```python
from master_prompt_template import load_section_context_from_file, generate_master_prompt

# Load clean XML section context from generated .md file
section_context = load_section_context_from_file("section_prompts/macro_environment.md")
enabled_widgets = ["qa", "exec"]

# Generate complete master prompt
master_prompt = generate_master_prompt(
    section_name="Macro Environment",
    section_context=section_context,
    transcript_text="[earnings call transcript]",
    enabled_widgets=enabled_widgets,
    prior_research_plans="[previous sections' research plans]"
)
```

### 4. Iterative Analysis Flow
1. **Section 1**: Master prompt + transcript → Research plan 1
2. **Section 2**: Master prompt + transcript + research plan 1 → Research plan 2  
3. **Section 3**: Master prompt + transcript + research plans 1&2 → Research plan 3
4. **Continue** accumulating context through all sections

## Output Structure

Generated section contexts are XML-structured for master prompt integration:

```xml
<section_context>
<section_name>Macro Environment</section_name>
<focus_areas>
- Economic outlook statements and market condition assessments
- Regulatory environment commentary and policy impact discussions
- Geopolitical factors affecting business strategy
</focus_areas>
<analysis_requirements>
<widget name="qa">Extract significant analyst questions and management responses</widget>
<widget name="exec">Extract direct management commentary and strategic insights</widget>
</analysis_requirements>
</section_context>
```

## Complete Processing Workflow

### Automated Transcript Processing

For complete end-to-end processing, use the standalone processor:

```bash
# Setup input folder and place PDF transcripts
mkdir input_transcripts
# Copy your earnings call PDF files to input_transcripts/

# Run the complete processor
python3 transcript_processor.py
```

**The processor will:**
1. Initialize RBC SSL and OAuth authentication
2. Extract text from all PDF files in `input_transcripts/`
3. Generate research plans for each configured section iteratively
4. Build master prompts with accumulated planning context
5. Call LLM to create systematic research plans (not full analysis)
6. Save individual research plans and planning summary

**Output Structure:**
```
analysis_results/
└── TranscriptName_20241201_143022/
    ├── transcript.txt                    # Extracted PDF text
    ├── macro_environment_master_prompt.txt
    ├── macro_environment_research_plan.md  # Research plan (not full analysis)
    ├── outlook_master_prompt.txt
    ├── outlook_research_plan.md         # Research plan (not full analysis)
    ├── ...
    └── research_plans_summary.md        # Combined research plans overview
```

**Note:** This phase creates **research plans** that identify available information and plan the extraction strategy. The actual content analysis would be a separate subsequent phase.

## Dependencies

- **Python 3.7+**
- **beautifulsoup4**: `pip install beautifulsoup4`
- **PyPDF2**: `pip install PyPDF2`
- **openai**: `pip install openai`
- **cryptography**: `pip install cryptography`
- **requests**: `pip install requests`