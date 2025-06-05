#!/usr/bin/env python3
"""Example script to show what a full system prompt looks like."""

import sys

sys.path.append(".")

# Import the module with a different approach
import importlib.util

spec = importlib.util.spec_from_file_location(
    "research_prompt", "3_research_plan_system_prompt.py"
)
research_prompt_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(research_prompt_module)

create_research_plan_prompt = research_prompt_module.create_research_plan_prompt
import json


def main():
    # Load actual section data
    with open("2_section_instructions.json", "r") as f:
        data = json.load(f)

    sections = data["sections"]

    # Simulate we're on the 3rd section (Credit Section)
    current_section = sections[2]  # Credit Section

    # Mock completed research plans for first 2 sections
    completed_plans = [
        {
            "section_id": "macro-environment",
            "section_name": "Macro Environment Section",
            "research_plan": {
                "content_availability": {
                    "high_priority_content": [
                        "Economic outlook statements",
                        "Regulatory environment impact",
                        "Competitive landscape assessment",
                    ],
                    "medium_priority_content": [
                        "Geopolitical risk factors",
                        "Strategic response planning",
                    ],
                    "low_priority_content": ["Industry consolidation trends"],
                    "content_gaps": ["Specific regulatory compliance costs"],
                },
                "extraction_strategy": {
                    "key_quotes": [
                        {
                            "content_description": "CEO comments on economic outlook and recession probability",
                            "speaker_attribution": "CEO",
                            "approximate_location": "Prepared remarks - economic environment section",
                            "priority": "high",
                        }
                    ]
                },
            },
        },
        {
            "section_id": "outlook",
            "section_name": "Outlook Section",
            "research_plan": {
                "content_availability": {
                    "high_priority_content": [
                        "Financial guidance ranges",
                        "Strategic initiative timelines",
                        "Management confidence indicators",
                    ],
                    "medium_priority_content": [
                        "Long-term strategic objectives",
                        "Risk factor assessment",
                    ],
                    "content_gaps": ["Specific investment commitment amounts"],
                }
            },
        },
    ]

    # Remaining sections (downstream)
    downstream_sections = sections[3:6]  # Next few sections

    # Sample transcript excerpt
    transcript_text = """Q2 2024 EARNINGS CALL TRANSCRIPT - XYZ Bank

PREPARED REMARKS:

CEO: Good morning everyone. I'll start with an overview of our Q2 performance. The economic environment remains challenging with continued uncertainty around interest rates and potential recession risks. We're maintaining a cautious outlook while positioning for growth opportunities.

Our credit portfolio has performed well this quarter. We built additional reserves of $150 million to prepare for potential economic headwinds. Our charge-off rate remained stable at 0.45%, well within our expected range. We continue to see strength in our commercial lending book, though we're being more selective in certain sectors like commercial real estate.

From a capital perspective, we returned $800 million to shareholders this quarter through dividends and share buybacks. Our CET1 ratio stands at 12.1%, well above regulatory minimums.

CFO: Thank you. Looking at our financial results, net interest income was $2.1 billion, up 3% quarter-over-quarter. Our net interest margin expanded to 2.85% as we benefited from higher rates on our asset repricing.

Q&A SESSION:

ANALYST 1: Can you talk about your credit outlook and reserve building strategy?

CFO: We're taking a prudent approach to reserving. The $150 million build this quarter reflects our economic scenario modeling which incorporates a higher probability of recession. We're particularly focused on our CRE exposure and have increased reserves there by 25%.

ANALYST 2: What's your guidance for credit costs going forward?

CEO: We expect provision expense to be in the range of $300-400 million for the full year, with most of that being reserve building rather than charge-offs. Our underwriting standards remain disciplined."""

    prompt = create_research_plan_prompt(
        current_section=current_section,
        completed_research_plans=completed_plans,
        downstream_sections=downstream_sections,
        transcript_text=transcript_text,
    )

    print("FULL SYSTEM PROMPT EXAMPLE (Credit Section - 3rd in sequence):")
    print("=" * 100)
    print(prompt)
    print("=" * 100)
    print(f"Total prompt length: {len(prompt):,} characters")


if __name__ == "__main__":
    main()
