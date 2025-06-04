#!/usr/bin/env python3
"""
Master prompt template for iterative earnings call transcript analysis.
Uses CO-STAR prompting methodology with XML structure for systematic content organization.
"""


MASTER_PROMPT_TEMPLATE = """<context>
{prior_research_plans}
</context>

<objective>
Create a detailed research plan for the specified section based on what information is available in the earnings call transcript. This is a planning phase - you are NOT extracting the actual content yet, but rather identifying what content is available and planning how to structure the final analysis.
</objective>

<style>
Expert financial analyst creating a systematic research plan. Focus on identifying transcript locations, available information, and structural organization for future content extraction.
</style>

<tone>
Strategic and methodical. Use planning language ("will analyze", "found in", "plan to extract") rather than analytical conclusions.
</tone>

<audience>
Research team who will use this plan to systematically extract and analyze content in the next phase of work.
</audience>

<response_format>
## Research Plan for {section_name}

### Available Information Assessment
[What {section_name}-related information is present in this transcript and where it's located]

### Content Extraction Strategy  
[Detailed plan for what specific information to extract and from which parts of the transcript]

{widget_sections}

### Structural Organization Plan
[How the final analysis will be organized and presented]

### Integration Opportunities
[How this section's content will connect with previous research plans]

### Key Transcript References
[Note specific sections, speakers, or topics that contain relevant information - references only, not full content]
</response_format>

<section_instructions>
{section_context}
</section_instructions>

<transcript_content>
{transcript_text}
</transcript_content>

<task_reminder>
Your goal is to create a RESEARCH PLAN, not perform the actual analysis. Review the transcript to identify what {section_name}-related information is available, where it's located, and how you would structure the extraction and analysis. Reference specific parts of the transcript but do not extract or analyze the content itself - that will be done in a later phase.
</task_reminder>"""


def format_prior_research_context(prior_research_plans: str = "") -> str:
    """Format prior research plans for context section."""
    if prior_research_plans.strip():
        return f"""<prior_research_context>
The following research plans have been completed for previous sections of this earnings call analysis:

{prior_research_plans}

Use this context to ensure consistency and identify connections between this section and previous findings.
</prior_research_context>"""
    else:
        return "<prior_research_context>\nThis is the first section being analyzed. No prior research context available.\n</prior_research_context>"


def format_widget_sections(enabled_widgets: list) -> str:
    """Format widget sections for research planning based on enabled widgets."""
    widget_formats = {
        'summary': """### Summary Content Plan
[Plan for structured overview - what key points will be included and where they're found in transcript]""",
        'qa': """### Q&A Analysis Plan
[Which analyst questions and management responses to highlight - identify specific Q&A exchanges by speaker/topic]""",
        'exec': """### Management Commentary Plan
[Which executive quotes and strategic insights to extract - note speakers and topics without full quotes]""",
        'data': """### Data Extraction Plan
[What quantitative information is available and where - identify metrics, tables, figures by transcript location]""",
        'highlights': """### Performance Highlights Plan
[Which standout metrics to feature - note what achievements or concerns are mentioned and where]""",
        'trend': """### Trend Analysis Plan
[What historical comparisons are available - identify trend discussions and their transcript locations]""",
        'peer': """### Competitive Analysis Plan
[What competitive/industry information is present - note competitive mentions and market positioning discussions]"""
    }
    
    sections = []
    for widget in enabled_widgets:
        if widget in widget_formats:
            sections.append(widget_formats[widget])
    
    return "\n\n".join(sections)


def load_section_context_from_file(section_md_file: str) -> str:
    """Load just the XML section context from a generated markdown file."""
    with open(section_md_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the XML section_context block
    start_marker = '<section_context>'
    end_marker = '</section_context>'
    
    start_pos = content.find(start_marker)
    end_pos = content.find(end_marker)
    
    if start_pos == -1 or end_pos == -1:
        raise ValueError(f"Could not find section_context XML in {section_md_file}")
    
    return content[start_pos:end_pos + len(end_marker)]


def generate_master_prompt(section_name: str,
                          section_context: str, 
                          transcript_text: str,
                          enabled_widgets: list,
                          prior_research_plans: str = "") -> str:
    """Generate a complete master prompt for a specific section."""
    
    formatted_prior = format_prior_research_context(prior_research_plans)
    widget_sections = format_widget_sections(enabled_widgets)
    
    return MASTER_PROMPT_TEMPLATE.format(
        prior_research_plans=formatted_prior,
        section_name=section_name,
        section_context=section_context,
        transcript_text=transcript_text,
        widget_sections=widget_sections
    )