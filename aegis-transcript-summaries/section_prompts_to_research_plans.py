#!/usr/bin/env python3
"""
Transcript processing script for AEGIS earnings call analysis.
Processes PDF transcripts through configured sections to generate research plans.
"""

import os
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional
import requests
from openai import OpenAI
from cryptography import x509
from cryptography.hazmat.backends import default_backend
import datetime
import PyPDF2

from template_to_section_prompts import ConfigToPromptConverter


class TranscriptProcessor:
    """Transcript processor with configurable authentication and processing."""

    def __init__(self, config_path: str = "config.json"):
        """Initialize processor with configuration from JSON file."""

        # Load configuration
        self.config_path = Path(config_path)
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(self.config_path, "r") as f:
            self.config = json.load(f)

        # Set up paths
        self.input_folder = Path(self.config["input_folder"])
        self.output_folder = Path(self.config["output_folder"])
        self.section_prompts_folder = Path(self.config["section_prompts_folder"])

        # Create directories
        self.input_folder.mkdir(exist_ok=True)
        self.output_folder.mkdir(exist_ok=True)

        # Initialize components
        self.logger = self._setup_logging()
        self.oauth_token = None
        self.openai_client = None

        # Analysis state
        self.current_analysis_folder = None
        self.completed_research_plans = []

    def _setup_logging(self) -> logging.Logger:
        """Configure logging for the processor."""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler("transcript_processor.log"),
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

    def extract_pdf_text(self, pdf_path: Path) -> str:
        """Extract text from PDF transcript."""
        self.logger.info(f"Extracting text from PDF: {pdf_path}")

        try:
            with open(pdf_path, "rb") as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""

                for page_num, page in enumerate(pdf_reader.pages):
                    try:
                        page_text = page.extract_text()
                        text += f"\n--- Page {page_num + 1} ---\n{page_text}\n"
                    except Exception as e:
                        self.logger.warning(
                            f"Error extracting page {page_num + 1}: {e}"
                        )
                        continue

                if not text.strip():
                    raise ValueError("No text extracted from PDF")

                self.logger.info(
                    f"Successfully extracted {len(text)} characters from PDF"
                )
                return text.strip()

        except Exception as e:
            self.logger.error(f"Failed to extract PDF text: {e}")
            raise

    def setup_analysis_folder(self, transcript_name: str) -> Path:
        """Create analysis folder for current transcript."""
        clean_name = "".join(
            c for c in transcript_name if c.isalnum() or c in (" ", "-", "_")
        ).rstrip()
        clean_name = clean_name.replace(" ", "_")

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        folder_name = f"{clean_name}_{timestamp}"

        analysis_folder = self.output_folder / folder_name
        analysis_folder.mkdir(exist_ok=True)

        self.logger.info(f"Created analysis folder: {analysis_folder}")
        return analysis_folder

    def load_section_context_from_file(self, file_path: str) -> str:
        """Load section context from markdown file, extracting section name and description."""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Extract section name and description from the new simplified format
        lines = content.split("\n")
        section_name = ""
        section_description = ""
        in_description = False

        for line in lines:
            if "<section_name>" in line:
                section_name = (
                    line.replace("<section_name>", "")
                    .replace("</section_name>", "")
                    .strip()
                )
            elif "<section_description>" in line:
                in_description = True
            elif "</section_description>" in line:
                break
            elif in_description and line.strip():
                section_description += line.strip() + " "

        # Return clean section context
        return f"""Section: {section_name}
Content Description: {section_description.strip()}"""

    def generate_research_prompt(
        self,
        section_name: str,
        section_context: str,
        transcript_text: str,
        prior_research: str = "",
    ) -> str:
        """Generate research planning prompt for a section."""

        prior_context = (
            f"\n\n## Prior Research Plans\n{prior_research}" if prior_research else ""
        )

        prompt = f"""You are creating a research plan for extracting content from this specific earnings call transcript.

{section_context}

Analyze this transcript to create a detailed extraction plan that identifies the most material content for this section. Focus on creating a plan that will produce business-quality analysis similar to professional earnings summaries.

## Research Plan Requirements

1. **Material Content Identification**
   - Identify the most significant developments, announcements, or changes discussed
   - Locate specific metrics, figures, guidance, and quantitative data points
   - Find key management statements that reveal strategy, confidence levels, or concerns
   - Prioritize content by materiality and business impact

2. **Content Structure Strategy**
   - Organize content by materiality: major developments first, then supporting details
   - Group related information logically (e.g., all reserve-building discussion together)
   - Plan how to synthesize information rather than just extract quotes
   - Identify where paraphrasing vs. direct quotes would be most effective

3. **Specific Extraction Targets**
   - Key metrics with specific numbers, percentages, timeframes, and context
   - Management guidance, targets, ranges, and forward-looking statements
   - Important rationale or explanations behind major decisions
   - Comparative information (vs. prior periods, vs. expectations, vs. peers)

4. **Business-Style Presentation Planning**
   - Plan clear subheadings that reflect business priorities
   - Identify content that should be emphasized through formatting
   - Plan how to present complex information in digestible, actionable insights
   - Consider integration with related content from other sections{prior_context}

Create a research plan that will enable generation of professional, business-quality analysis that emphasizes synthesis and actionable insights over academic extraction.

## Transcript Content
{transcript_text}
"""
        return prompt

    def call_llm(self, prompt: str) -> str:
        """Make LLM API call."""
        if not self.openai_client:
            raise ValueError("OpenAI client not initialized")

        self.logger.info("Making LLM API call...")

        messages = [{"role": "user", "content": prompt}]

        try:
            response = self.openai_client.chat.completions.create(
                model=self.config.get("openai_model", "gpt-4"),
                messages=messages,
                max_tokens=self.config.get("max_tokens", 4000),
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

    def process_transcript(self, pdf_path: Path) -> Path:
        """Process a single transcript through all configured sections."""
        self.logger.info(f"Starting transcript processing: {pdf_path}")

        # Setup analysis folder
        transcript_name = pdf_path.stem
        self.current_analysis_folder = self.setup_analysis_folder(transcript_name)

        # Extract PDF text
        transcript_text = self.extract_pdf_text(pdf_path)

        # Save transcript text for reference
        transcript_file = self.current_analysis_folder / "transcript.txt"
        with open(transcript_file, "w", encoding="utf-8") as f:
            f.write(transcript_text)

        # Find available section prompts
        section_files = list(self.section_prompts_folder.glob("*.md"))

        if not section_files:
            raise ValueError(
                f"No section prompt files found in {self.section_prompts_folder}"
            )

        self.logger.info(f"Processing {len(section_files)} sections")

        # Reset analysis state
        self.completed_research_plans = []

        # Generate research plans for each section
        for i, section_file in enumerate(section_files, 1):
            section_id = section_file.stem
            section_name = section_id.replace("_", " ").title()

            self.logger.info(
                f"Creating research plan {i}/{len(section_files)}: {section_name}"
            )

            try:
                # Load section context
                section_context = self.load_section_context_from_file(str(section_file))

                # Format prior research context
                prior_context = self._format_prior_research_context()

                # Generate research prompt
                research_prompt = self.generate_research_prompt(
                    section_name, section_context, transcript_text, prior_context
                )

                # Save prompt for debugging
                prompt_file = (
                    self.current_analysis_folder / f"{section_id}_research_prompt.txt"
                )
                with open(prompt_file, "w", encoding="utf-8") as f:
                    f.write(research_prompt)

                # Make LLM call
                research_plan = self.call_llm(research_prompt)

                # Save research plan
                plan_file = (
                    self.current_analysis_folder / f"{section_id}_research_plan.md"
                )
                with open(plan_file, "w", encoding="utf-8") as f:
                    f.write(research_plan)

                # Add to completed plans for context
                self.completed_research_plans.append(
                    {
                        "section_name": section_name,
                        "section_id": section_id,
                        "research_plan": research_plan,
                    }
                )

                self.logger.info(f"Research plan completed: {section_name}")

            except Exception as e:
                self.logger.error(
                    f"Failed to create research plan for {section_name}: {e}"
                )
                raise

        # Generate final summary
        self._generate_research_plans_summary()

        self.logger.info(
            f"Research planning completed. Results in: {self.current_analysis_folder}"
        )
        return self.current_analysis_folder

    def _format_prior_research_context(self) -> str:
        """Format completed research plans as context."""
        if not self.completed_research_plans:
            return ""

        context_parts = []
        for plan in self.completed_research_plans:
            context_parts.append(
                f"## {plan['section_name']} Research Plan\n\n{plan['research_plan']}"
            )

        return "\n\n".join(context_parts)

    def _generate_research_plans_summary(self):
        """Generate summary of all research plans."""
        # Build summary content
        planning_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        num_plans = len(self.completed_research_plans)

        summary_content = f"# Earnings Call Research Plans Summary\n\n"
        summary_content += f"**Planning Date:** {planning_date}\n"
        summary_content += f"**Research Plans Created:** {num_plans}\n\n"
        summary_content += "## Research Planning Overview\n\n"
        summary_content += "This document contains the research plans for systematic content extraction and analysis. "
        summary_content += "These plans identify what information is available in the transcript and how it should be structured for comprehensive analysis.\n\n"
        summary_content += "## Section Research Plans\n\n"

        for i, plan in enumerate(self.completed_research_plans, 1):
            summary_content += (
                f"{i}. **{plan['section_name']}** (`{plan['section_id']}`)\n"
            )

        summary_content += "\n## Complete Research Plans\n\n"

        for plan in self.completed_research_plans:
            summary_content += (
                f"### {plan['section_name']}\n\n{plan['research_plan']}\n\n---\n\n"
            )

        summary_content += "## Next Steps\n\n"
        summary_content += "Use these research plans to systematically extract and analyze content from the transcript. Each plan provides:\n"
        summary_content += "- Available information assessment\n"
        summary_content += "- Content extraction strategy\n"
        summary_content += "- Structural organization approach\n"
        summary_content += "- Integration opportunities with other sections\n"
        summary_content += "- Key transcript reference points\n\n"
        summary_content += "The research plans serve as a roadmap for comprehensive analysis execution.\n"

        summary_file = self.current_analysis_folder / "research_plans_summary.md"
        with open(summary_file, "w", encoding="utf-8") as f:
            f.write(summary_content)

        self.logger.info(f"Generated research plans summary: {summary_file}")

    def run(self):
        """Main processing workflow."""
        try:
            self.logger.info("Initializing AEGIS Transcript Processor...")

            # Setup SSL if configured
            self.setup_ssl()

            # Setup OAuth if configured
            self.oauth_token = self.setup_oauth()

            # Initialize OpenAI client
            self.openai_client = self.initialize_openai_client()

            # Look for PDF files in input folder
            pdf_files = list(self.input_folder.glob("*.pdf"))

            if not pdf_files:
                self.logger.warning(f"No PDF files found in {self.input_folder}")
                return

            self.logger.info(f"Found {len(pdf_files)} PDF file(s) to process")

            # Process each PDF
            for pdf_file in pdf_files:
                try:
                    result_folder = self.process_transcript(pdf_file)
                    self.logger.info(f"Successfully processed: {pdf_file.name}")
                    print(f"Results saved to: {result_folder}")

                except Exception as e:
                    self.logger.error(f"Failed to process {pdf_file.name}: {e}")

            self.logger.info("All transcripts processed successfully")

        except Exception as e:
            self.logger.error(f"Processing failed: {e}")
            raise


def main():
    """Main entry point."""
    import sys

    config_file = sys.argv[1] if len(sys.argv) > 1 else "config.json"

    processor = TranscriptProcessor(config_file)
    processor.run()


if __name__ == "__main__":
    main()
