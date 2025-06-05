#!/usr/bin/env python3
"""
Research Analysis System Prompt Generator

This module generates iterative system prompts for the research analysis phase,
building context as analysis is completed section by section. Each prompt includes:
- Prior completed research analyses (for context and cross-referencing)
- Current section's research plan (the active section to analyze)
- Full transcript content

The goal is to execute the research plans to extract and structure content
following the CO-STAR methodology with XML tags from research_analysis_prompt.py.
"""

from typing import List, Dict, Optional


class ResearchAnalysisPromptGenerator:
    """Generates system prompts for iterative research analysis execution."""

    def __init__(self):
        self.base_instructions = self._get_base_instructions()

    def generate_prompt(
        self,
        current_section: Dict,
        current_research_plan: Dict,
        completed_analyses: List[Dict],
        transcript_text: str,
    ) -> str:
        """
        Generate a comprehensive system prompt for research analysis execution.

        Args:
            current_section: Section currently being analyzed (dict with name, description)
            current_research_plan: Research plan for the current section
            completed_analyses: List of sections with completed analyses
            transcript_text: Full transcript content

        Returns:
            str: Complete system prompt for LLM
        """

        # Build context sections
        prior_analyses_section = self._format_prior_analyses(completed_analyses)
        current_section_part = self._format_current_section(
            current_section, current_research_plan
        )

        # Get CO-STAR methodology from research_analysis_prompt
        costar_prompt = self._get_costar_methodology()

        # Build the main sections
        instructions_section = """## INSTRUCTIONS FOR CURRENT SECTION ANALYSIS

Execute the research plan for the CURRENT SECTION above. Your analysis should:

1. **Follow the Research Plan Precisely**: Extract exactly what the research plan specifies

2. **Maintain Cross-Section Consistency**: Reference the prior analyses to ensure consistency and avoid duplication

3. **Use JSON Tool Calling**: Structure output using the transcript JSON format tool as specified in the research analysis methodology

4. **Focus on Material Content**: Prioritize the most significant and business-relevant information

5. **Preserve Accuracy**: Ensure all quotes, numbers, and attributions are precise"""

        format_section = """## RESPONSE FORMAT

Use the JSON extraction tool to structure your response according to the transcript JSON format schema. Your response MUST follow this exact structure from TRANSCRIPT_JSON_FORMAT.md:

```json
{
  "section_name": "Credit",
  "section_title": "Credit: Reviewed credit portfolios and bolstered reserves",
  "section_statement": "AI-generated 1-2 sentence summary of key section insights and business impact",
  "content": [
    {
      "subsection": "Subsection Name (e.g., 'Reserve Strategy and Credit Quality')",
      "quotes": [
        {
          "quote_text": "Exact quote with <span class=\\"highlight-keyword\\">keywords</span> and <span class=\\"highlight-figure\\">$500MM</span> highlighted",
          "context": "Additional clarifying information or null",
          "speaker": {
            "name": "Gabriel Dechaine",
            "title": "CFO",
            "company": "TD Bank"
          },
          "sentiment": "cautious",
          "sentiment_rationale": "Conservative approach to credit risk management",
          "key_metrics": ["$500MM reserve build", "45-55 basis points PCL ratio"]
        }
      ]
    }
  ]
}
```

### Required Field Specifications:

**Top Level:**
- `section_name`: Short identifier from research plan (e.g., "Credit", "Capital")  
- `section_title`: Descriptive title showing key theme (e.g., "Credit: Strengthened reserves amid economic uncertainty")
- `section_statement`: 1-2 sentence AI synthesis of main themes and business impact
- `content`: Array of subsection objects

**Subsections:**
- `subsection`: Specific topic within section (from research plan organization)
- `quotes`: Array of quote objects following the exact schema

**Quote Objects (All Fields Required):**
- `quote_text`: Exact transcript quote with HTML highlighting using:
  - `<span class="highlight-keyword">term</span>` for key business terms
  - `<span class="highlight-figure">$500MM</span>` for important numbers  
  - `<span class="highlight-time">Q3</span>` for time references
- `context`: Supporting clarification or `null` if not needed
- `speaker`: Object with `name`, `title`, `company` (all required)
- `sentiment`: Must be one of: `positive`, `negative`, `neutral`, `cautious`, `confident`, `optimistic`, `bullish`, `stable`
- `sentiment_rationale`: Brief explanation for sentiment classification
- `key_metrics`: Array of quantitative data mentioned in quote (empty array if none)

### Key Metrics Format:
Include dollar amounts, percentages, ratios, time periods, guidance ranges in original units with context (e.g., "30 million shares repurchased", "141% LCR")

Remember: You are executing a precise research plan. Focus on accuracy, materiality, and professional business analysis standards."""

        # Construct full prompt
        prompt = f"""{self.base_instructions}

{costar_prompt}

{prior_analyses_section}

{current_section_part}

## TRANSCRIPT CONTENT

{transcript_text}

{instructions_section}

{format_section}
"""

        return prompt

    def _get_base_instructions(self) -> str:
        """Get the base instructions that appear in every prompt."""
        return """# EARNINGS CALL RESEARCH ANALYSIS EXECUTION

You are a specialized financial analyst AI executing detailed research plans to extract and analyze specific content from an earnings call transcript. This is part of an iterative process where analyses are completed section by section.

## YOUR ROLE AND OBJECTIVE

You are executing a research plan (performing the actual extraction and analysis) to systematically extract material content for a specific section. Your analysis will produce professional, business-quality structured data that can be directly used in financial reports.

## PROCESS CONTEXT

This is an iterative analysis execution process:
- **PRIOR SECTIONS**: Analyses already completed (shown below for cross-referencing)
- **CURRENT SECTION**: The section you are analyzing now (focus here)
- **RESEARCH PLAN**: The detailed plan you must execute for the current section

Your goal is to execute the research plan precisely while maintaining consistency with prior analyses and producing high-quality structured output."""

    def _get_costar_methodology(self) -> str:
        """Extract and format the CO-STAR methodology from research_analysis_prompt."""
        return """
<context>
You are a specialized financial analyst AI designed to extract precise information from banking earnings call transcripts using a detailed research plan. Your role is to systematically extract content according to the research plan and structure it into the required JSON format.

This is the EXTRACTION phase of a two-phase process:
1. PLANNING (completed): Research plan created identifying what content to extract
2. EXTRACTION (this phase): Actually extract the content using the research plan

You will receive:
- A complete earnings call transcript
- A detailed research plan specifying what to extract
- The target JSON schema for output formatting
- Any context from previously extracted sections
</context>

<objective>
Execute the research plan to extract precise, accurate information from the transcript and structure it according to the specified JSON format. Your extraction must:

1. **Follow the Research Plan**: Extract exactly what the research plan specifies
2. **Maintain Accuracy**: Ensure all quotes, numbers, and attributions are precise
3. **Use JSON Tool Calling**: Structure output using the transcript JSON format tool
4. **Preserve Context**: Maintain speaker attribution and contextual information
5. **Handle Missing Data**: Appropriately handle cases where planned content is not available
6. **Cross-Reference**: Ensure consistency with previously extracted sections

Your output will be structured JSON data that can be directly inserted into analysis reports.
</objective>

<style>
- Extract information with precision and accuracy
- Maintain exact quotes without paraphrasing
- Use clear, professional financial terminology
- Preserve numerical precision (percentages, dollar amounts, basis points)
- Include proper speaker attribution for all quotes
- Structure data hierarchically according to the JSON schema
- Be comprehensive but avoid extracting irrelevant information
</style>

<tone>
Precise, analytical, and systematic. Extract information exactly as it appears in the transcript while maintaining professional financial analysis standards.
</tone>

<audience>
Financial analysts and reporting systems that will use the extracted JSON data for analysis and report generation.
</audience>

<extraction_guidelines>
<quote_extraction>
- Extract quotes exactly as spoken, including any verbal fillers or corrections
- Always include speaker name and role when available
- Provide context for when the quote was made (prepared remarks vs. Q&A)
- Use quotation marks to clearly delineate extracted speech
- Include relevant follow-up or clarifying statements
</quote_extraction>

<numerical_data>
- Preserve exact numerical values as stated
- Include units (millions, billions, percentages, basis points)
- Capture comparative references (vs. prior quarter, vs. prior year)
- Note any adjustments or non-GAAP reconciliations mentioned
- Include confidence levels or ranges when provided
</numerical_data>

<speaker_attribution>
- Use full names and titles when available (e.g., "John Smith, CEO")
- For analysts, include firm name when mentioned
- Distinguish between prepared remarks and Q&A responses
- Note when multiple speakers contribute to a topic
</speaker_attribution>

<contextual_information>
- Include timing references when available (e.g., "end of quarter", "beginning of next year")
- Capture conditional language (e.g., "expect", "anticipate", "guidance")
- Note any disclaimers or forward-looking statement caveats
- Include geographic or business segment context
</contextual_information>

<data_validation>
- Cross-check numerical data for consistency within the transcript
- Verify speaker attributions are accurate
- Ensure quotes are complete and in proper context
- Flag any apparent inconsistencies or unclear statements
</data_validation>
</extraction_guidelines>"""

    def _format_prior_analyses(self, completed_analyses: List[Dict]) -> str:
        """Format completed analyses for context."""
        if not completed_analyses:
            return "## PRIOR SECTION ANALYSES\n\n*No prior analyses completed yet. This is the first section being analyzed.*"

        sections_text = "## PRIOR SECTION ANALYSES\n\n"
        sections_text += "The following sections have already been analyzed. Use this context for cross-referencing and to avoid duplication:\n\n"

        for i, analysis in enumerate(completed_analyses, 1):
            sections_text += (
                f"### {i}. {analysis.get('section_name', 'Unknown Section')}\n"
            )
            sections_text += (
                f"**Section ID**: {analysis.get('section_id', 'unknown')}\n\n"
            )

            # Include key extracted content highlights
            extracted_content = analysis.get("extracted_content", {})
            if isinstance(extracted_content, dict):
                # Show number of key quotes and data points
                key_quotes = extracted_content.get("key_quotes", [])
                numerical_data = extracted_content.get("numerical_data", [])
                themes = extracted_content.get("thematic_synthesis", [])

                sections_text += f"**Extracted Elements**:\n"
                sections_text += f"- Key Quotes: {len(key_quotes)}\n"
                sections_text += f"- Numerical Data Points: {len(numerical_data)}\n"
                sections_text += f"- Synthesized Themes: {len(themes)}\n"

                # Include first theme as example if available
                if themes:
                    first_theme = themes[0]
                    sections_text += (
                        f"\n**Sample Theme**: {first_theme.get('theme', 'N/A')}\n"
                    )

            # Include completeness assessment if available
            completeness = analysis.get("completeness_assessment", {})
            if completeness:
                coverage = completeness.get("coverage_percentage", "N/A")
                sections_text += f"\n**Coverage**: {coverage}%\n"

            sections_text += "\n---\n\n"

        return sections_text

    def _format_current_section(
        self, current_section: Dict, research_plan: Dict
    ) -> str:
        """Format the current section and its research plan."""
        sections_text = "## CURRENT SECTION (EXECUTE ANALYSIS FOR THIS SECTION)\n\n"
        sections_text += f"**Section Name**: {current_section.get('section_name', 'Unknown Section')}\n"
        sections_text += (
            f"**Section ID**: {current_section.get('section_id', 'unknown')}\n"
        )
        sections_text += (
            f"**Status**: ACTIVE - Execute research plan for this section\n\n"
        )

        sections_text += "**Section Requirements**:\n"
        sections_text += (
            f"{current_section.get('description', 'No description available')}\n\n"
        )

        sections_text += "### RESEARCH PLAN TO EXECUTE\n\n"

        # Format the research plan based on its structure
        if isinstance(research_plan, dict):
            # Handle structured research plan
            plan_details = research_plan.get("research_plan", research_plan)

            if isinstance(plan_details, dict):
                # Extract key elements from structured plan
                content_avail = plan_details.get("content_availability", {})
                extraction_strategy = plan_details.get("extraction_strategy", {})
                organization = plan_details.get("organization_structure", {})

                sections_text += "**Content Availability Assessment**:\n"
                high_priority = content_avail.get("high_priority_content", [])
                if high_priority:
                    sections_text += f"- High Priority: {', '.join(high_priority)}\n"

                sections_text += "\n**Extraction Strategy**:\n"
                key_quotes = extraction_strategy.get("key_quotes", [])
                numerical_data = extraction_strategy.get("numerical_data", [])
                sections_text += f"- Key Quotes to Extract: {len(key_quotes)}\n"
                sections_text += f"- Numerical Data Points: {len(numerical_data)}\n"

                sections_text += "\n**Organization Structure**:\n"
                primary_subsections = organization.get("primary_subsections", [])
                if primary_subsections:
                    sections_text += "- Subsections: "
                    sections_text += ", ".join(
                        [s.get("subsection_name", "N/A") for s in primary_subsections]
                    )
                    sections_text += "\n"
            else:
                # Handle text-based research plan
                sections_text += str(plan_details)
        else:
            # Fallback for string research plans
            sections_text += str(research_plan)

        sections_text += "\n"
        return sections_text


def create_research_analysis_prompt(
    current_section: Dict,
    current_research_plan: Dict,
    completed_analyses: List[Dict] = None,
    transcript_text: str = "",
) -> str:
    """
    Convenience function to create a research analysis prompt.

    Args:
        current_section: Current section to analyze
        current_research_plan: Research plan for current section
        completed_analyses: Previously completed analyses
        transcript_text: Full transcript content

    Returns:
        str: Generated system prompt
    """
    generator = ResearchAnalysisPromptGenerator()

    return generator.generate_prompt(
        current_section=current_section,
        current_research_plan=current_research_plan,
        completed_analyses=completed_analyses or [],
        transcript_text=transcript_text,
    )


if __name__ == "__main__":
    # Example usage for testing

    current_section = {
        "section_id": "credit",
        "section_name": "Credit Section",
        "description": "Analyze credit quality developments, reserve strategies, and portfolio risk management.",
    }

    current_research_plan = {
        "section_id": "credit",
        "section_name": "Credit Section",
        "research_plan": {
            "content_availability": {
                "high_priority_content": [
                    "PCL ratios",
                    "Reserve build",
                    "Credit quality metrics",
                ]
            },
            "extraction_strategy": {
                "key_quotes": [
                    {
                        "content_description": "CEO commentary on credit outlook",
                        "speaker_attribution": "CEO",
                        "approximate_location": "Prepared remarks",
                        "priority": "high",
                    }
                ],
                "numerical_data": [
                    {
                        "metric_description": "PCL ratio",
                        "expected_format": "basis points",
                        "comparative_context": "vs Q1 2024",
                        "priority": "high",
                    }
                ],
            },
        },
    }

    completed_analyses = [
        {
            "section_id": "macro-environment",
            "section_name": "Macro Environment Section",
            "extracted_content": {
                "key_quotes": [{"quote_text": "Economic outlook remains uncertain..."}],
                "numerical_data": [{"metric": "GDP growth", "value": "2.5%"}],
                "thematic_synthesis": [{"theme": "Regulatory challenges"}],
            },
            "completeness_assessment": {
                "coverage_percentage": 90,
                "confidence_level": "high",
            },
        }
    ]

    prompt = create_research_analysis_prompt(
        current_section=current_section,
        current_research_plan=current_research_plan,
        completed_analyses=completed_analyses,
        transcript_text="[Sample transcript text would go here...]",
    )

    print("Generated Research Analysis Prompt:")
    print("=" * 80)
    print(prompt[:1500] + "...")
    print("=" * 80)
    print(f"Total prompt length: {len(prompt)} characters")
