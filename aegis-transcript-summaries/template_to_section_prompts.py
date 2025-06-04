#!/usr/bin/env python3
"""
Script to convert earnings config template HTML to individual section prompts.
Reads the HTML config template, extracts selected sections and widgets,
and generates individual research planning prompts for each section.
"""

import re
import json
from typing import Dict, List, Optional
from pathlib import Path
from bs4 import BeautifulSoup


class ConfigToPromptConverter:
    """Converts HTML config template to individual section prompts for transcript research planning."""

    def __init__(self, config_file_path: str):
        self.config_file_path = Path(config_file_path)
        self.widget_templates = {
            "summary": {
                "description": "Key points overview with structured summary",
                "instructions": """Extract and organize the most important information into a clear, structured summary with:
- Executive summary paragraph (2-3 sentences)
- 3-5 key bullet points highlighting the most significant findings
- Brief context or background information when relevant
Focus on actionable insights and quantitative data when available.""",
            },
            "qa": {
                "description": "Analyst Q&A highlights and management responses",
                "instructions": """Identify and extract the most significant analyst questions and management responses:
- Key questions that reveal analyst concerns or focus areas
- Management's direct responses with specific commitments or clarifications
- Any pushback, defensive responses, or areas where management seemed uncertain
- Follow-up questions that indicate unresolved issues
Format as question-answer pairs with context about the analyst firm when available.""",
            },
            "exec": {
                "description": "Management commentary and strategic insights",
                "instructions": """Extract direct management commentary that provides strategic insights:
- Direct quotes from executives that reveal strategic thinking or priorities
- Management's tone and confidence level indicators
- Unprompted commentary that goes beyond standard Q&A responses
- Strategic rationale behind key decisions or initiatives
- Management's assessment of competitive positioning or market conditions
Preserve exact wording when quoting and note which executive made the statement.""",
            },
            "data": {
                "description": "Tables, figures, and quantitative metrics",
                "instructions": """Extract and organize quantitative data into structured format:
- Financial metrics with specific numbers, percentages, and time periods
- Growth rates, ratios, and key performance indicators
- Comparative data (YoY, QoQ, vs guidance, vs consensus)
- Forward-looking guidance ranges and targets
- Segment-specific or geographic breakdowns
Present data in table format when possible, with clear labels and time periods.""",
            },
            "highlights": {
                "description": "Key metric boxes with standout numbers",
                "instructions": """Identify the most important standalone metrics that deserve emphasis:
- Standout financial achievements or concerning declines
- Metrics that significantly beat or missed expectations
- Record highs/lows or milestone achievements
- Key ratios or percentages that tell a clear story
- Guidance updates or target achievements
Format as prominent callout boxes with context about why each metric is significant.""",
            },
            "trend": {
                "description": "Historical comparison and trend analysis",
                "instructions": """Analyze and present historical trends and comparisons:
- Multi-period progression showing clear directional trends
- Seasonal patterns or cyclical behaviors mentioned
- Comparison to prior year same period and sequential quarters
- Long-term trend analysis where management provides historical context
- Inflection points or trend reversals highlighted by management
Present trends with clear before/after context and management's explanation of drivers.""",
            },
            "peer": {
                "description": "Industry benchmarking and competitive analysis",
                "instructions": """Extract competitive positioning and industry comparison information:
- Direct competitive mentions or market share discussions
- Industry-wide trends or challenges affecting all players
- Competitive advantages or disadvantages highlighted by management
- Benchmarking against industry averages or peer performance
- Market positioning statements and differentiation strategies
Focus on how the company positions itself relative to competitors and industry norms.""",
            },
        }

    def parse_html_config(self) -> Dict:
        """Parse the HTML config file and extract configuration data."""
        with open(self.config_file_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        soup = BeautifulSoup(html_content, "html.parser")
        config_data = {"sections": []}

        # Find all section rows
        section_rows = soup.find_all("tr", class_="section-row")

        for row in section_rows:
            section_data = self._extract_section_data(row)
            if section_data:
                config_data["sections"].append(section_data)

        return config_data

    def _extract_section_data(self, row) -> Optional[Dict]:
        """Extract data from a single section row."""
        # Check if section is enabled (checkbox checked)
        section_checkbox = row.find("input", class_="section-checkbox")
        if not section_checkbox or not section_checkbox.has_attr("checked"):
            return None

        # Extract section name and description
        section_name_elem = row.find("div", class_="section-name")
        section_desc_elem = row.find("div", class_="section-desc")

        if not section_name_elem or not section_desc_elem:
            return None

        section_name = section_name_elem.get_text(strip=True)
        section_desc = section_desc_elem.get_text(strip=True)

        # Extract enabled widgets
        enabled_widgets = []
        widget_checkboxes = row.find_all("input", class_="widget-checkbox")

        for checkbox in widget_checkboxes:
            if checkbox.has_attr("checked") and not checkbox.has_attr("disabled"):
                widget_type = checkbox.get("data-widget")
                if widget_type and widget_type in self.widget_templates:
                    enabled_widgets.append(
                        {
                            "type": widget_type,
                            "description": self.widget_templates[widget_type][
                                "description"
                            ],
                            "instructions": self.widget_templates[widget_type][
                                "instructions"
                            ],
                        }
                    )

        return {
            "name": section_name,
            "description": section_desc,
            "enabled_widgets": enabled_widgets,
        }

    def generate_individual_section_prompts(self, config_data: Dict) -> List[Dict]:
        """Generate individual section prompts for iterative research planning."""
        section_prompts = []

        for section in config_data["sections"]:
            prompt = self._generate_single_section_prompt(section)
            section_prompts.append(
                {
                    "section_name": section["name"],
                    "section_id": section["name"]
                    .lower()
                    .replace(" ", "_")
                    .replace("-", "_"),
                    "prompt": prompt,
                    "enabled_widgets": [w["type"] for w in section["enabled_widgets"]],
                }
            )

        return section_prompts

    def _generate_single_section_prompt(self, section: Dict) -> str:
        """Generate a concise XML-structured section context for master prompt integration."""

        # Build widget analysis requirements
        widget_requirements = []
        if section["enabled_widgets"]:
            for widget in section["enabled_widgets"]:
                widget_requirements.append(
                    f'<widget name="{widget["type"]}">{widget["instructions"]}</widget>'
                )

        widget_content = (
            "\n".join(widget_requirements)
            if widget_requirements
            else '<widget name="summary">Provide structured summary with key points and context</widget>'
        )

        # Convert section description into focused bullet points
        focus_areas = self._extract_focus_areas(section["description"])

        prompt = f"""<section_context>
<section_name>{section['name']}</section_name>
<focus_areas>
{focus_areas}
</focus_areas>
<analysis_requirements>
{widget_content}
</analysis_requirements>
</section_context>"""

        return prompt

    def _extract_focus_areas(self, description: str) -> str:
        """Convert section description into structured focus areas."""
        # If description already has numbered points, convert to bullets
        if any(char.isdigit() and char in description[:10] for char in description):
            lines = description.split("\n")
            focus_points = []
            for line in lines:
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith("-")):
                    # Remove numbers and clean up
                    clean_line = line.lstrip("0123456789. -").strip()
                    if clean_line:
                        focus_points.append(f"- {clean_line}")
            return "\n".join(focus_points) if focus_points else f"- {description}"
        else:
            # Single description, convert to bullet
            return f"- {description}"

    def save_section_prompts(
        self, section_prompts: List[Dict], output_dir: str = None
    ) -> List[str]:
        """Save individual section prompts as separate markdown files."""
        if output_dir is None:
            output_dir = self.config_file_path.parent / "section_prompts"
        else:
            output_dir = Path(output_dir)

        output_dir.mkdir(exist_ok=True)

        saved_files = []
        for section_prompt in section_prompts:
            filename = f"{section_prompt['section_id']}.md"
            output_file = output_dir / filename

            # Create markdown content for each section
            md_content = f"""# {section_prompt['section_name']}

**Section ID:** `{section_prompt['section_id']}`  
**Enabled Widgets:** {', '.join(section_prompt['enabled_widgets'])}

## Section Context

{section_prompt['prompt']}
"""

            with open(output_file, "w", encoding="utf-8") as f:
                f.write(md_content)

            saved_files.append(str(output_file))

        return saved_files

    def convert(self, output_dir: str = None) -> List[str]:
        """Full conversion process: parse config and generate individual section markdown files."""
        config_data = self.parse_html_config()
        section_prompts = self.generate_individual_section_prompts(config_data)
        saved_files = self.save_section_prompts(section_prompts, output_dir)

        print(
            f"Generated {len(section_prompts)} individual section prompt markdown files"
        )
        print(f"Saved to directory: {Path(saved_files[0]).parent}")
        for section in section_prompts:
            print(
                f"  - {section['section_name']}: {len(section['enabled_widgets'])} widgets"
            )

        return saved_files


def main():
    """Main execution function."""
    import sys

    if len(sys.argv) < 2:
        config_file = Path(__file__).parent / "summary_template.html"
    else:
        config_file = sys.argv[1]

    output_dir = sys.argv[2] if len(sys.argv) > 2 else None

    converter = ConfigToPromptConverter(config_file)
    saved_files = converter.convert(output_dir)

    return saved_files


if __name__ == "__main__":
    main()
