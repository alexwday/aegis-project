#!/usr/bin/env python3
"""
Research Plan System Prompt Generator

This module generates iterative system prompts that build context as research plans
are created section by section. Each prompt includes:
- Prior completed research plans (for context and avoiding duplication)
- Current section instructions (the active section to create a plan for)
- Downstream section instructions (remaining sections for awareness)

The goal is to create a comprehensive, non-duplicative research planning process
that considers the full scope of analysis while focusing on the current section.
"""

from typing import List, Dict, Optional


class ResearchPlanPromptGenerator:
    """Generates system prompts for iterative research plan creation."""

    def __init__(self):
        self.base_instructions = self._get_base_instructions()

    def generate_prompt(
        self,
        current_section: Dict,
        completed_research_plans: List[Dict],
        downstream_sections: List[Dict],
        transcript_text: str,
    ) -> str:
        """
        Generate a comprehensive system prompt for research plan creation.

        Args:
            current_section: Section currently being planned (dict with name, description)
            completed_research_plans: List of sections with completed research plans
            downstream_sections: List of remaining sections (instructions only)
            transcript_text: Full transcript content

        Returns:
            str: Complete system prompt for LLM
        """

        # Build context sections
        prior_plans_section = self._format_prior_research_plans(
            completed_research_plans
        )
        current_section_part = self._format_current_section(current_section)
        downstream_sections_part = self._format_downstream_sections(downstream_sections)

        # Construct full prompt
        prompt = f"""{self.base_instructions}

{prior_plans_section}

{current_section_part}

{downstream_sections_part}

## TRANSCRIPT CONTENT

{transcript_text}

## INSTRUCTIONS FOR CURRENT SECTION RESEARCH PLAN

Create a comprehensive research plan specifically for the CURRENT SECTION above. Your research plan should:

1. **Avoid Duplication**: Review the prior research plans to ensure you don't duplicate content that has already been planned for extraction

2. **Consider Downstream Context**: Be aware of the downstream sections to come, and if content is more appropriate for a later section, note this in your plan

3. **Focus on Current Section**: Concentrate on content that is most relevant to the current section's specific requirements

4. **Create Actionable Extraction Instructions**: Provide specific, actionable guidance for extracting content from the transcript

5. **Structure for Business Quality**: Plan content organization that will result in professional, business-quality analysis

## RESPONSE FORMAT

Structure your response as a JSON object with the following format:

```json
{{
  "section_id": "{current_section.get('section_id', 'unknown')}",
  "section_name": "{current_section.get('section_name', 'Unknown Section')}",
  "research_plan": {{
    "content_availability": {{
      "high_priority_content": ["List of major content areas with substantial material"],
      "medium_priority_content": ["List of content areas with some material"],
      "low_priority_content": ["List of content areas with limited material"],
      "content_gaps": ["List of areas where content is missing or insufficient"]
    }},
    "extraction_strategy": {{
      "key_quotes": [
        {{
          "content_description": "Description of what quote covers",
          "speaker_attribution": "Expected speaker (CEO, CFO, etc.)",
          "approximate_location": "Where in transcript this appears",
          "priority": "high/medium/low"
        }}
      ],
      "numerical_data": [
        {{
          "metric_description": "Description of metric or data point",
          "expected_format": "Format expected (percentage, dollar amount, etc.)",
          "comparative_context": "What comparisons are available (YoY, QoQ, etc.)",
          "priority": "high/medium/low"
        }}
      ],
      "thematic_content": [
        {{
          "theme_description": "Description of thematic area to extract",
          "content_approach": "How to synthesize this content (paraphrase vs quotes)",
          "integration_notes": "How this integrates with other content",
          "priority": "high/medium/low"
        }}
      ]
    }},
    "organization_structure": {{
      "primary_subsections": [
        {{
          "subsection_name": "Name of subsection",
          "content_focus": "What content goes in this subsection",
          "priority_order": 1
        }}
      ],
      "content_sequencing": "How to sequence content within the section",
      "emphasis_approach": "What content should be emphasized and how"
    }},
    "integration_notes": {{
      "prior_section_references": ["Any references to content from prior sections"],
      "downstream_handoffs": ["Content that should be handled by downstream sections"],
      "cross_section_themes": ["Themes that span multiple sections"]
    }},
    "quality_considerations": {{
      "materiality_focus": "What makes content material for this section",
      "business_relevance": "How to present content for business audience",
      "synthesis_approach": "How to synthesize rather than just extract"
    }}
  }},
  "extraction_confidence": {{
    "high_confidence_areas": ["Areas where transcript has rich content"],
    "medium_confidence_areas": ["Areas where content is available but limited"],
    "low_confidence_areas": ["Areas where content may be insufficient"]
  }}
}}
```

Focus on creating a research plan that will enable the generation of professional, insightful business analysis that emphasizes synthesis and actionable insights over simple content extraction.
"""

        return prompt

    def _get_base_instructions(self) -> str:
        """Get the base instructions that appear in every prompt."""
        return """# EARNINGS CALL RESEARCH PLAN CREATION

You are a senior financial analyst creating a detailed research plan for extracting and analyzing specific content from an earnings call transcript. This is part of an iterative process where research plans are created section by section.

## YOUR ROLE AND OBJECTIVE

You are creating a research plan (not performing extraction yet) that will guide the systematic extraction of material content for a specific section. Your research plan will be used by the extraction phase to produce professional, business-quality analysis.

## PROCESS CONTEXT

This is an iterative research planning process:
- **PRIOR SECTIONS**: Research plans already completed (shown below for context)
- **CURRENT SECTION**: The section you are creating a research plan for (focus here)
- **DOWNSTREAM SECTIONS**: Sections that will come after (shown for awareness)

Your goal is to create the best possible research plan for the CURRENT SECTION while being aware of what has been planned before and what will come after."""

    def _format_prior_research_plans(self, completed_plans: List[Dict]) -> str:
        """Format completed research plans for context."""
        if not completed_plans:
            return "## PRIOR SECTION RESEARCH PLANS\n\n*No prior research plans completed yet.*"

        sections_text = "## PRIOR SECTION RESEARCH PLANS\n\n"
        sections_text += "The following sections have already had research plans created. Use this context to avoid duplication and understand what content has already been planned for extraction:\n\n"

        for i, plan in enumerate(completed_plans, 1):
            sections_text += f"### {i}. {plan.get('section_name', 'Unknown Section')}\n"
            sections_text += f"**Section ID**: {plan.get('section_id', 'unknown')}\n\n"

            # Include key highlights from the research plan
            research_plan = plan.get("research_plan", {})
            if isinstance(research_plan, dict):
                # If it's structured JSON
                content_avail = research_plan.get("content_availability", {})
                high_priority = content_avail.get("high_priority_content", [])
                if high_priority:
                    sections_text += f"**Key Content Areas Planned**: {', '.join(high_priority[:3])}\n"
            else:
                # If it's text format, include first part
                plan_text = (
                    str(research_plan)[:200] + "..."
                    if len(str(research_plan)) > 200
                    else str(research_plan)
                )
                sections_text += f"**Research Plan Summary**: {plan_text}\n"

            sections_text += "\n---\n\n"

        return sections_text

    def _format_current_section(self, current_section: Dict) -> str:
        """Format the current section that needs a research plan."""
        sections_text = "## CURRENT SECTION (CREATE RESEARCH PLAN FOR THIS SECTION)\n\n"
        sections_text += f"**Section Name**: {current_section.get('section_name', 'Unknown Section')}\n"
        sections_text += (
            f"**Section ID**: {current_section.get('section_id', 'unknown')}\n"
        )
        sections_text += (
            f"**Status**: ACTIVE - Create research plan for this section\n\n"
        )
        sections_text += "**Section Requirements**:\n"
        sections_text += (
            f"{current_section.get('description', 'No description available')}\n\n"
        )

        return sections_text

    def _format_downstream_sections(self, downstream_sections: List[Dict]) -> str:
        """Format remaining sections for awareness."""
        if not downstream_sections:
            return "## DOWNSTREAM SECTIONS\n\n*No remaining sections after current section.*"

        sections_text = "## DOWNSTREAM SECTIONS (FOR AWARENESS ONLY)\n\n"
        sections_text += "The following sections will have research plans created after the current section. Be aware of these to avoid planning content that would be more appropriate for a later section:\n\n"

        for i, section in enumerate(downstream_sections, 1):
            sections_text += (
                f"### {i}. {section.get('section_name', 'Unknown Section')}\n"
            )
            sections_text += f"**Section ID**: {section.get('section_id', 'unknown')}\n"

            # Include brief description
            description = section.get("description", "")
            if description:
                # Truncate description for overview
                brief_desc = (
                    description[:300] + "..." if len(description) > 300 else description
                )
                sections_text += f"**Brief Description**: {brief_desc}\n"

            sections_text += "\n"

        return sections_text


def create_research_plan_prompt(
    current_section: Dict,
    completed_research_plans: List[Dict] = None,
    downstream_sections: List[Dict] = None,
    transcript_text: str = "",
) -> str:
    """
    Convenience function to create a research plan prompt.

    Args:
        current_section: Current section to create research plan for
        completed_research_plans: Previously completed research plans
        downstream_sections: Remaining sections to be planned
        transcript_text: Full transcript content

    Returns:
        str: Generated system prompt
    """
    generator = ResearchPlanPromptGenerator()

    return generator.generate_prompt(
        current_section=current_section,
        completed_research_plans=completed_research_plans or [],
        downstream_sections=downstream_sections or [],
        transcript_text=transcript_text,
    )


if __name__ == "__main__":
    # Example usage for testing

    current_section = {
        "section_id": "credit",
        "section_name": "Credit Section",
        "description": "Analyze credit quality developments, reserve strategies, and portfolio risk management.",
    }

    completed_plans = [
        {
            "section_id": "macro-environment",
            "section_name": "Macro Environment Section",
            "research_plan": {
                "content_availability": {
                    "high_priority_content": ["Economic outlook", "Regulatory impact"]
                }
            },
        }
    ]

    downstream_sections = [
        {
            "section_id": "capital",
            "section_name": "Capital Section",
            "description": "Analyze capital strength, deployment strategies, and liquidity management.",
        }
    ]

    prompt = create_research_plan_prompt(
        current_section=current_section,
        completed_research_plans=completed_plans,
        downstream_sections=downstream_sections,
        transcript_text="[Sample transcript text would go here...]",
    )

    print("Generated Research Plan Prompt:")
    print("=" * 80)
    print(prompt[:1000] + "...")
    print("=" * 80)
    print(f"Total prompt length: {len(prompt)} characters")
