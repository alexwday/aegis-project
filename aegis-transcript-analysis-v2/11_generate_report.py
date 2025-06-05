#!/usr/bin/env python3
"""
Generate HTML Report from Section Analyses

This script generates a final HTML report from the section analyses created by
8_generate_sections.py. It uses the report template and creates a polished,
interactive HTML report suitable for business presentation.

Flow:
1. Load section analyses from 9_report_sections.json
2. Load HTML template from 10_report_template.html
3. Generate HTML for each section following transcript JSON format
4. Apply template styling and interactivity
5. Save final report to 12_transcript_summary_report.html

The script creates a professional 3-column report with:
- Section statements and insights
- Quote content with HTML highlighting
- Speaker attribution and sentiment analysis
"""

import json
import os
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


class ReportGenerator:
    """Generates HTML reports from section analyses."""

    def __init__(self):
        """Initialize the report generator."""
        # Set up paths
        self.sections_file = Path("9_report_sections.json")
        self.template_file = Path("10_report_template.html")
        self.output_file = Path("12_transcript_summary_report.html")

        # Validate required files exist
        if not self.sections_file.exists():
            raise FileNotFoundError(f"Section analyses not found: {self.sections_file}")

        if not self.template_file.exists():
            raise FileNotFoundError(f"Template not found: {self.template_file}")

        # Initialize components
        self.logger = self._setup_logging()
        self.sections_data = None
        self.template_html = None

    def _setup_logging(self) -> logging.Logger:
        """Configure logging for the generator."""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler("report_generator.log"),
                logging.StreamHandler(),
            ],
        )
        return logging.getLogger(__name__)

    def load_section_analyses(self) -> List[Dict]:
        """Load section analyses from JSON file."""
        self.logger.info(f"Loading section analyses from: {self.sections_file}")

        with open(self.sections_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        sections = data.get("sections", [])
        metadata = data.get("metadata", {})

        self.logger.info(f"Loaded {len(sections)} section analyses")
        self.logger.info(
            f"Source created: {metadata.get('creation_timestamp', 'Unknown')}"
        )

        return sections

    def load_template(self) -> str:
        """Load HTML template."""
        self.logger.info(f"Loading HTML template from: {self.template_file}")

        with open(self.template_file, "r", encoding="utf-8") as f:
            template_html = f.read()

        # Remove the hardcoded sections from template (lines 299-353)
        # These are just examples and will be replaced with our generated content
        template_html = self._clean_template(template_html)

        self.logger.info("HTML template loaded successfully")
        return template_html

    def _clean_template(self, template_html: str) -> str:
        """Remove hardcoded example sections from template."""
        # Find and remove the example sections (from <!-- Section 8: NIM to end of sections)
        start_marker = "<!-- Section 8: NIM"
        end_marker = "{{DIGITAL_INITIATIVES_QUOTES}}\n        </div>\n    </div>"

        start_index = template_html.find(start_marker)
        end_index = template_html.find(end_marker)

        if start_index != -1 and end_index != -1:
            # Remove the hardcoded sections
            end_index += len(end_marker)
            template_html = template_html[:start_index] + template_html[end_index:]
            self.logger.info("Removed hardcoded example sections from template")

        return template_html

    def generate_section_html(self, section_data: Dict) -> str:
        """Generate HTML for a single section with card/tile structure."""
        section_name = section_data.get("section_name", "Unknown Section")
        section_title = section_data.get("section_title", section_name)
        section_statement = section_data.get(
            "section_statement", "No summary available"
        )

        section_html = f"""
    <div class="section">
        <div class="section-header">
            <h2>{section_title}</h2>
            <div class="description">{section_statement}</div>
        </div>
        <div class="quotes-container">
"""

        # Process each subsection and its quotes
        content_items = section_data.get("content", [])
        quote_count = 0

        for content_item in content_items:
            subsection = content_item.get("subsection", "General")
            quotes = content_item.get("quotes", [])

            # Add each quote as a tile
            for quote in quotes:
                quote_count += 1

                # Get quote data with defaults
                quote_text = quote.get("quote_text", "No quote available")
                context = quote.get("context")
                speaker_info = quote.get("speaker", {})
                sentiment = quote.get("sentiment", "neutral")
                sentiment_rationale = quote.get("sentiment_rationale", "")

                # Speaker information
                speaker_name = speaker_info.get("name", "Unknown Speaker")
                speaker_title = speaker_info.get("title", "Unknown Title")
                speaker_company = speaker_info.get("company", "Unknown Company")

                # Generate sentiment class
                sentiment_class = f"sentiment-{sentiment}"

                section_html += f"""
            <div class="quote-tile">
                <div class="tile-header">
                    <h3 class="tile-title">{subsection}</h3>
                </div>
                <div class="content-row">
                    <div class="quote-column">
                        <div class="quote">{quote_text}</div>"""

                # Add context if it exists and is not null
                if context and context.lower() != "null":
                    section_html += f"""
                        <div class="context">{context}</div>"""

                # Add key metrics if they exist
                key_metrics = quote.get("key_metrics", [])
                if key_metrics:
                    metrics_html = ", ".join(
                        f'<span class="key-metric">{metric}</span>'
                        for metric in key_metrics
                    )
                    section_html += f"""
                        <div class="context"><strong>Key Metrics:</strong> {metrics_html}</div>"""

                section_html += f"""
                    </div>
                    <div class="attribution-column">
                        <div class="speaker">{speaker_name}</div>
                        <div class="title">{speaker_title}, {speaker_company}</div>
                        <div class="sentiment {sentiment_class}" title="{sentiment_rationale}">
                            {sentiment.title()}
                        </div>
                    </div>
                </div>
            </div>
"""

        section_html += """        </div>
    </div>
"""

        self.logger.info(
            f"Generated HTML for section '{section_name}' with {quote_count} quotes"
        )
        return section_html

    def generate_report_metadata(self, sections: List[Dict]) -> Dict[str, str]:
        """Generate metadata for the report."""
        total_quotes = sum(
            len(content_item.get("quotes", []))
            for section in sections
            for content_item in section.get("content", [])
        )

        # Extract company name from first speaker (if available)
        company_name = "Company"
        if sections:
            first_section = sections[0]
            content_items = first_section.get("content", [])
            if content_items:
                quotes = content_items[0].get("quotes", [])
                if quotes:
                    speaker_info = quotes[0].get("speaker", {})
                    company_name = speaker_info.get("company", "Company")

        # Generate timestamp
        generation_time = datetime.now().strftime("%B %d, %Y at %I:%M %p")

        return {
            "report_title": f"{company_name} Earnings Call Analysis",
            "report_subtitle": f"AI-Enhanced Transcript Intelligence Report • Generated {generation_time}",
            "total_sections": len(sections),
            "total_quotes": total_quotes,
        }

    def generate_final_report(self) -> None:
        """Generate the complete HTML report."""
        try:
            self.logger.info("Starting report generation...")

            # Load data
            self.sections_data = self.load_section_analyses()
            self.template_html = self.load_template()

            # Generate metadata
            metadata = self.generate_report_metadata(self.sections_data)

            # Generate HTML for all sections
            sections_html = ""
            for section_data in self.sections_data:
                section_html = self.generate_section_html(section_data)
                sections_html += section_html

            # Replace template placeholders
            final_html = self.template_html.replace(
                "{{REPORT_TITLE}}", metadata["report_title"]
            )
            final_html = final_html.replace(
                "{{REPORT_SUBTITLE}}", metadata["report_subtitle"]
            )
            final_html = final_html.replace("{{SECTIONS}}", sections_html)

            # Write output file
            with open(self.output_file, "w", encoding="utf-8") as f:
                f.write(final_html)

            self.logger.info(f"Report generated successfully: {self.output_file}")
            self.logger.info(f"Total sections processed: {metadata['total_sections']}")
            self.logger.info(f"Total quotes processed: {metadata['total_quotes']}")

            print(f"\n✅ Report generated successfully!")
            print(f"📄 Output file: {self.output_file}")
            print(f"📊 Sections: {metadata['total_sections']}")
            print(f"💬 Quotes: {metadata['total_quotes']}")

        except Exception as e:
            self.logger.error(f"Report generation failed: {e}")
            raise

    def validate_section_data(self, section_data: Dict) -> bool:
        """Validate that section data follows expected transcript JSON format."""
        required_fields = ["section_name", "content"]

        for field in required_fields:
            if field not in section_data:
                self.logger.warning(
                    f"Section missing required field '{field}': {section_data.get('section_name', 'Unknown')}"
                )
                return False

        # Validate content structure
        content_items = section_data.get("content", [])
        for content_item in content_items:
            if "quotes" not in content_item:
                self.logger.warning(
                    f"Content item missing 'quotes' field in section: {section_data.get('section_name', 'Unknown')}"
                )
                return False

            quotes = content_item.get("quotes", [])
            for quote in quotes:
                required_quote_fields = [
                    "quote_text",
                    "speaker",
                    "sentiment",
                    "sentiment_rationale",
                ]
                for field in required_quote_fields:
                    if field not in quote:
                        self.logger.warning(
                            f"Quote missing required field '{field}' in section: {section_data.get('section_name', 'Unknown')}"
                        )
                        return False

        return True

    def run(self):
        """Main execution method."""
        try:
            self.logger.info("Starting AEGIS Report Generator...")

            # Generate the final report
            self.generate_final_report()

            self.logger.info("Report generation completed successfully")

        except Exception as e:
            self.logger.error(f"Report generation failed: {e}")
            raise


def main():
    """Main entry point."""
    generator = ReportGenerator()
    generator.run()


if __name__ == "__main__":
    main()
