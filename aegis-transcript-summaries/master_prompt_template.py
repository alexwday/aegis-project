#!/usr/bin/env python3
"""
Master prompt template for iterative earnings call transcript analysis.
Uses CO-STAR prompting methodology with XML structure for systematic content organization.
"""


MASTER_PROMPT_TEMPLATE = """<context>
{prior_research_plans}
</context>

<objective>
Analyze the provided earnings call transcript to extract and synthesize information for the specified section. Build upon previous research plans to create comprehensive, interconnected insights that contribute to a holistic view of the company's performance and outlook.
</objective>

<style>
Expert financial analyst providing institutional-grade equity research analysis. Emphasize quantitative data, specific metrics, and actionable insights. Use precise financial terminology and maintain objectivity in assessments.
</style>

<tone>
Professional, analytical, data-driven. Present findings with confidence while acknowledging uncertainties. Use clear, direct language appropriate for sophisticated institutional investors.
</tone>

<audience>
Institutional investors, equity research professionals, and portfolio managers requiring detailed earnings analysis for investment decision-making. Assume advanced financial knowledge and preference for specific, actionable insights over general commentary.
</audience>

<response_format>
## {section_name} Analysis

### Executive Summary
[2-3 sentences summarizing the most critical findings and their implications]

### Key Points
[3-5 bullet points highlighting specific insights with supporting data/quotes]

{widget_sections}

### Integration with Prior Research
[Brief note on how this section's findings connect to or build upon previous sections' insights]

### Strategic Implications
[1-2 sentences on what these findings mean for the company's outlook or investment thesis]
</response_format>

<section_instructions>
{section_context}
</section_instructions>

<transcript_content>
{transcript_text}
</transcript_content>

<task_reminder>
Using the section instructions above, analyze the transcript content to extract relevant information. Incorporate context from prior research plans where applicable. Generate your analysis following the exact response format specified above, ensuring each widget section is properly structured and all findings are grounded in specific transcript content.
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
    """Format widget sections for the response format based on enabled widgets."""
    widget_formats = {
        'summary': """### Summary
[Structured overview with key points and context]""",
        'qa': """### Q&A Highlights
[Significant analyst questions and management responses]""",
        'exec': """### Management Commentary
[Direct executive quotes and strategic insights]""",
        'data': """### Key Metrics & Data
[Quantitative information in structured format]""",
        'highlights': """### Performance Highlights
[Standout metrics and achievements]""",
        'trend': """### Trend Analysis
[Historical comparisons and directional insights]""",
        'peer': """### Competitive Positioning
[Industry benchmarking and competitive analysis]"""
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