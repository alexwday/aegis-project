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
import requests
from openai import OpenAI


class ReportGenerator:
    """Generates HTML reports from section analyses."""

    def __init__(self, config_path: str = "config.json"):
        """Initialize the report generator."""
        # Set up paths
        self.sections_file = Path("9_report_sections.json")
        self.template_file = Path("10_report_template.html")
        self.output_file = Path("12_transcript_summary_report.html")
        self.config_path = Path(config_path)

        # Validate required files exist
        if not self.sections_file.exists():
            raise FileNotFoundError(f"Section analyses not found: {self.sections_file}")

        if not self.template_file.exists():
            raise FileNotFoundError(f"Template not found: {self.template_file}")

        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        # Load configuration
        with open(self.config_path, "r") as f:
            self.config = json.load(f)

        # Initialize components
        self.logger = self._setup_logging()
        self.oauth_token = None
        self.openai_client = None
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

    def setup_ssl(self) -> Optional[str]:
        """Setup SSL certificate if configured."""
        ssl_cert_path = self.config.get("ssl_cert_path")
        if not ssl_cert_path:
            self.logger.info("No SSL certificate configured")
            return None

        cert_path = Path(ssl_cert_path)
        if not cert_path.exists():
            self.logger.warning(f"SSL certificate not found at {cert_path}")
            return None

        self.logger.info(f"Using SSL certificate: {cert_path}")
        os.environ["SSL_CERT_FILE"] = str(cert_path)
        os.environ["REQUESTS_CA_BUNDLE"] = str(cert_path)

        return str(cert_path)

    def setup_oauth(self) -> Optional[str]:
        """Setup OAuth authentication if configured."""
        oauth_endpoint = self.config.get("oauth_endpoint")
        client_id = self.config.get("client_id")
        client_secret = self.config.get("client_secret")

        if not all([oauth_endpoint, client_id, client_secret]):
            self.logger.info("OAuth not configured - skipping authentication")
            return None

        if any(
            val.startswith("your-")
            for val in [oauth_endpoint, client_id, client_secret]
        ):
            self.logger.warning("OAuth appears to be using placeholder values")
            return None

        self.logger.info("Setting up OAuth authentication...")

        payload = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }

        try:
            response = requests.post(
                oauth_endpoint,
                data=payload,
                headers=headers,
                timeout=30,
                verify=(
                    self.config.get("ssl_cert_path")
                    if self.config.get("ssl_cert_path")
                    else True
                ),
            )

            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data.get("access_token")

                if access_token:
                    token_preview = (
                        access_token[:10] + "..."
                        if len(access_token) > 10
                        else access_token
                    )
                    self.logger.info(
                        f"OAuth successful. Token preview: {token_preview}"
                    )
                    return access_token
                else:
                    raise ValueError("No access token in OAuth response")
            else:
                self.logger.error(
                    f"OAuth failed with status {response.status_code}: {response.text}"
                )
                return None

        except Exception as e:
            self.logger.error(f"OAuth authentication failed: {e}")
            return None

    def initialize_openai_client(self) -> OpenAI:
        """Initialize OpenAI client with configuration."""
        self.logger.info("Initializing OpenAI client...")

        # Use OAuth token if available, otherwise expect API key in environment
        api_key = self.oauth_token if self.oauth_token else os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise ValueError(
                "No API key available (OAuth token or OPENAI_API_KEY environment variable)"
            )

        # Use base_url from config if provided
        base_url = self.config.get("base_url")
        if base_url and base_url.startswith("your-"):
            base_url = None  # Don't use placeholder values

        client_params = {"api_key": api_key}
        if base_url:
            client_params["base_url"] = base_url
            self.logger.info(f"Using custom base URL: {base_url}")

        client = OpenAI(**client_params)

        self.logger.info("OpenAI client initialized successfully")
        return client

    def call_llm(self, prompt: str) -> str:
        """Make LLM API call."""
        if not self.openai_client:
            raise ValueError("OpenAI client not initialized")

        self.logger.info("Making LLM API call for overall summary...")

        messages = [{"role": "user", "content": prompt}]

        try:
            response = self.openai_client.chat.completions.create(
                model=self.config.get("openai_model", "gpt-4"),
                messages=messages,
                max_tokens=self.config.get("max_tokens", 2000),
                temperature=self.config.get("temperature", 0.1),
            )

            if response.choices and response.choices[0].message:
                content = response.choices[0].message.content

                if hasattr(response, "usage") and response.usage:
                    self.logger.info(
                        f"Token usage - Prompt: {response.usage.prompt_tokens}, "
                        f"Completion: {response.usage.completion_tokens}, "
                        f"Total: {response.usage.total_tokens}"
                    )

                return content
            else:
                raise ValueError("No content in LLM response")

        except Exception as e:
            self.logger.error(f"LLM API call failed: {e}")
            raise

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
        """Generate HTML for a single section with grouped subsections."""
        section_name = section_data.get("section_name", "Unknown Section")
        section_title = section_data.get("section_title", section_name)
        section_statement = section_data.get(
            "section_statement", "No summary available"
        )

        # Start section HTML (sections start collapsed)
        section_html = f"""
    <div class="section">
        <div class="section-header">
            <h2>{section_title} <span class="toggle-icon">▶</span></h2>
            <div class="description">{section_statement}</div>
        </div>
        <div class="section-content">
"""

        # Process and group quotes by subsection
        content_items = section_data.get("content", [])
        total_quotes = 0

        for content_item in content_items:
            subsection_name = content_item.get("subsection", "General")
            quotes = content_item.get("quotes", [])

            if quotes:  # Only create subsection if it has quotes
                section_html += f"""
            <div class="subsection-group">
                <h3 class="subsection-title">{subsection_name}</h3>
                <div class="quotes-list">
"""
                # Generate each quote in the subsection
                for quote in quotes:
                    total_quotes += 1
                    quote_html = self.generate_quote_html(quote)
                    section_html += quote_html

                section_html += """
                </div>
            </div>
"""

        # Close section HTML
        section_html += """
        </div>
    </div>
"""

        self.logger.info(
            f"Generated HTML for section '{section_name}' with {total_quotes} quotes in {len(content_items)} subsections"
        )
        return section_html

    def generate_quote_html(self, quote: Dict) -> str:
        """Generate HTML for a single quote."""
        # Extract quote data with defaults
        quote_text = quote.get("quote_text", "No quote available")
        context = quote.get("context")
        speaker_info = quote.get("speaker", {})
        sentiment = quote.get("sentiment", "neutral")
        sentiment_rationale = quote.get("sentiment_rationale", "")
        key_metrics = quote.get("key_metrics", [])

        # Speaker information
        speaker_name = speaker_info.get("name", "Unknown Speaker")
        speaker_title = speaker_info.get("title", "Unknown Title")
        speaker_company = speaker_info.get("company", "Unknown Company")

        # Generate sentiment class
        sentiment_class = f"sentiment-{sentiment}"

        # Build quote HTML
        quote_html = f"""
                    <div class="quote-item">
                        <div class="quote-content">
                            <div class="quote-text">{quote_text}</div>"""

        # Add context if it exists and is not null
        if context and context.lower() != "null":
            quote_html += f"""
                            <div class="context">{context}</div>"""

        # Add key metrics if they exist
        if key_metrics:
            quote_html += """
                            <div class="key-metrics">"""
            for metric in key_metrics:
                quote_html += f"""
                                <span class="metric-tag">{metric}</span>"""
            quote_html += """
                            </div>"""

        quote_html += f"""
                        </div>
                        <div class="quote-meta">
                            <div class="speaker-info">
                                <div class="speaker">{speaker_name}</div>
                                <div class="title">{speaker_title}, {speaker_company}</div>
                            </div>
                            <div class="sentiment {sentiment_class}" title="{sentiment_rationale}">
                                {sentiment.title()}
                            </div>
                        </div>
                    </div>
"""
        return quote_html

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

    def generate_overall_summary(self, sections_data: List[Dict]) -> str:
        """Generate overall summary from all section data using GPT."""
        self.logger.info("Generating overall summary from all sections...")

        # Prepare content for summary generation
        summary_content = "# SECTION SUMMARIES AND KEY CONTENT\n\n"
        
        for i, section in enumerate(sections_data, 1):
            section_name = section.get("section_name", f"Section {i}")
            section_statement = section.get("section_statement", "No summary available")
            
            summary_content += f"## {i}. {section_name}\n"
            summary_content += f"**Section Summary**: {section_statement}\n\n"
            
            # Include key quotes from the section
            content_items = section.get("content", [])
            quote_count = 0
            for content_item in content_items:
                quotes = content_item.get("quotes", [])
                for quote in quotes[:2]:  # Limit to first 2 quotes per subsection
                    quote_count += 1
                    if quote_count > 5:  # Limit total quotes per section
                        break
                    quote_text = quote.get("quote_text", "")
                    speaker = quote.get("speaker", {}).get("name", "Unknown")
                    # Remove HTML highlighting for cleaner input
                    clean_quote = quote_text.replace('<span class="highlight-keyword">', '').replace('</span>', '').replace('<span class="highlight-figure">', '').replace('<span class="highlight-time">', '')
                    summary_content += f"**Key Quote ({speaker})**: {clean_quote}\n\n"
                if quote_count > 5:
                    break
            
            summary_content += "---\n\n"

        # Create prompt for overall summary using CO-STAR methodology
        prompt = f"""<context>
You are a specialized financial analyst AI designed to create executive-level summaries of earnings calls. Your role is to synthesize detailed section analyses into a comprehensive overview that provides senior leadership with a complete understanding of the call's content, themes, and business implications.

This is the SYNTHESIS phase where you consolidate multiple detailed section analyses into one cohesive executive summary that captures the essential narrative of the entire earnings call.

You will receive:
- Detailed section summaries covering all major topics discussed
- Key quotes from company executives and analysts
- Quantitative metrics and financial data points
- Strategic insights from across all sections
</context>

<objective>
Create a comprehensive one-paragraph executive summary that synthesizes the most important content across ALL sections. Your summary must:

1. **Integrate Cross-Section Themes**: Weave together insights from all sections into a coherent narrative
2. **Highlight Material Metrics**: Include the most significant financial data and performance indicators
3. **Capture Strategic Direction**: Reflect the company's outlook, guidance, and strategic initiatives
4. **Convey Overall Sentiment**: Represent the tone and confidence level expressed throughout the call
5. **Provide Executive Context**: Deliver insights appropriate for C-suite and board-level consumption
6. **Maintain Accuracy**: Ensure all financial figures and statements are precisely represented

Your output will be used as the primary executive summary in financial reports and presentations.
</objective>

<style>
- Use sophisticated financial terminology appropriate for executive audiences
- Present information in a logical flow that tells the complete earnings story
- Maintain precise numerical accuracy for all financial metrics
- Integrate themes seamlessly rather than listing section-by-section
- Balance optimism/caution appropriately based on management tone
- Focus on material business impact and forward-looking implications
</style>

<tone>
Professional, analytical, and executive-appropriate. Convey confidence while acknowledging uncertainties or challenges discussed during the call.
</tone>

<audience>
Senior executives, board members, institutional investors, and financial analysts who need a comprehensive yet concise understanding of the entire earnings call.
</audience>

<synthesis_guidelines>
<cross_section_integration>
- Identify overarching themes that span multiple business areas
- Connect financial performance to strategic initiatives
- Highlight cause-and-effect relationships between different topics
- Present a unified narrative rather than disconnected summaries
</synthesis_guidelines>

<quantitative_emphasis>
- Include the most material financial metrics (revenue, margins, growth rates)
- Highlight guidance updates and outlook statements
- Mention key ratios, returns, and performance indicators
- Capture any significant changes or milestones achieved
</quantitative_emphasis>

<strategic_context>
- Reflect management's strategic priorities and initiatives
- Include market positioning and competitive advantages discussed
- Capture regulatory, economic, or industry factors mentioned
- Highlight transformation efforts or major business changes
</strategic_context>
</synthesis_guidelines>

## CONTENT TO SYNTHESIZE

{summary_content}

## RESPONSE FORMAT

Provide ONLY a single comprehensive paragraph (6-10 sentences) that flows naturally and tells the complete story of the earnings call. Do not include headers, bullet points, or additional formatting. The paragraph should integrate all key themes into a cohesive executive summary suitable for immediate use in reports and presentations."""

        try:
            summary_response = self.call_llm(prompt)
            self.logger.info("Overall summary generated successfully")
            return summary_response.strip()
        except Exception as e:
            self.logger.error(f"Failed to generate overall summary: {e}")
            return "Summary generation failed. Please review individual section summaries for key insights."

    def generate_summary_section_html(self, overall_summary: str) -> str:
        """Generate HTML for the overall summary section."""
        summary_html = f"""
    <div class="section">
        <div class="section-header">
            <h2>Executive Summary <span class="toggle-icon">▶</span></h2>
            <div class="description">Comprehensive overview synthesizing all key themes, metrics, and strategic insights from the earnings call</div>
        </div>
        <div class="section-content">
            <div class="subsection-group">
                <div class="quotes-list">
                    <div class="quote-item">
                        <div class="quote-content">
                            <div class="quote-text" style="font-style: normal; font-size: 0.95rem; line-height: 1.6; color: #2c3e50;">{overall_summary}</div>
                        </div>
                        <div class="quote-meta">
                            <div class="speaker-info">
                                <div class="speaker">AI Analysis</div>
                                <div class="title">Executive Summary</div>
                            </div>
                            <div class="sentiment sentiment-neutral" title="Comprehensive synthesis of all call content">
                                Summary
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
"""
        return summary_html

    def generate_final_report(self) -> None:
        """Generate the complete HTML report."""
        try:
            self.logger.info("Starting report generation...")

            # Setup authentication if not already done
            if not self.openai_client:
                self.setup_ssl()
                self.oauth_token = self.setup_oauth()
                self.openai_client = self.initialize_openai_client()

            # Load data
            self.sections_data = self.load_section_analyses()
            self.template_html = self.load_template()

            # Generate overall summary
            overall_summary = self.generate_overall_summary(self.sections_data)
            summary_section_html = self.generate_summary_section_html(overall_summary)

            # Generate metadata
            metadata = self.generate_report_metadata(self.sections_data)

            # Generate HTML for all sections
            sections_html = summary_section_html  # Start with summary section
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
            self.logger.info(f"Total sections processed: {metadata['total_sections']} + summary")
            self.logger.info(f"Total quotes processed: {metadata['total_quotes']}")

            print(f"\n✅ Report generated successfully!")
            print(f"📄 Output file: {self.output_file}")
            print(f"📊 Sections: {metadata['total_sections']} + Executive Summary")
            print(f"💬 Quotes: {metadata['total_quotes']}")
            print(f"🤖 Overall summary generated via GPT")

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

            # Setup authentication
            self.setup_ssl()
            self.oauth_token = self.setup_oauth()
            self.openai_client = self.initialize_openai_client()

            # Generate the final report
            self.generate_final_report()

            self.logger.info("Report generation completed successfully")

        except Exception as e:
            self.logger.error(f"Report generation failed: {e}")
            raise


def main():
    """Main entry point."""
    import sys
    
    config_file = sys.argv[1] if len(sys.argv) > 1 else "config.json"
    generator = ReportGenerator(config_file)
    generator.run()


if __name__ == "__main__":
    main()
