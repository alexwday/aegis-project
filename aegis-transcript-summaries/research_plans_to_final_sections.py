#!/usr/bin/env python3
"""
Final section generation script for AEGIS earnings call analysis.
Takes research plans and executes them to create final formatted sections.
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


class FinalSectionGenerator:
    """Generates final formatted sections from research plans and transcripts."""

    def __init__(self, config_path: str = "config.json"):
        """Initialize generator with configuration from JSON file."""

        # Load configuration
        self.config_path = Path(config_path)
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(self.config_path, "r") as f:
            self.config = json.load(f)

        # Set up paths
        self.input_folder = Path(
            self.config["output_folder"]
        )  # Read from research_plans folder
        self.output_folder = Path(
            self.config.get("final_sections_folder", "final_sections")
        )

        # Create directories
        self.output_folder.mkdir(exist_ok=True)

        # Initialize components
        self.logger = self._setup_logging()
        self.oauth_token = None
        self.openai_client = None

        # Analysis state
        self.current_analysis_folder = None
        self.completed_sections = []

    def _setup_logging(self) -> logging.Logger:
        """Configure logging for the generator."""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler("final_section_generator.log"),
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

    def find_analysis_folders(self) -> List[Path]:
        """Find all analysis folders in the research plans directory."""
        analysis_folders = []

        for item in self.input_folder.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                # Check if it has research plan files
                plan_files = list(item.glob("*_research_plan.md"))
                if plan_files:
                    analysis_folders.append(item)

        return sorted(analysis_folders)

    def load_transcript(self, analysis_folder: Path) -> str:
        """Load transcript text from analysis folder."""
        transcript_file = analysis_folder / "transcript.txt"
        if not transcript_file.exists():
            raise FileNotFoundError(f"Transcript file not found: {transcript_file}")

        with open(transcript_file, "r", encoding="utf-8") as f:
            return f.read()

    def load_research_plans(self, analysis_folder: Path) -> List[Dict]:
        """Load all research plans from analysis folder."""
        plan_files = list(analysis_folder.glob("*_research_plan.md"))
        research_plans = []

        for plan_file in sorted(plan_files):
            section_id = plan_file.stem.replace("_research_plan", "")
            section_name = section_id.replace("_", " ").title()

            with open(plan_file, "r", encoding="utf-8") as f:
                plan_content = f.read()

            research_plans.append(
                {
                    "section_id": section_id,
                    "section_name": section_name,
                    "research_plan": plan_content,
                    "plan_file": plan_file,
                }
            )

        return research_plans

    def generate_section_content_prompt(
        self,
        section_name: str,
        research_plan: str,
        transcript_text: str,
        prior_sections: str = "",
    ) -> str:
        """Generate prompt for creating final section content."""

        prior_context = (
            f"\n\n## Prior Completed Sections\n{prior_sections}"
            if prior_sections
            else ""
        )

        prompt = f"""You are creating a professional earnings call analysis section similar to what business analysts produce.

## Section: {section_name}

## Research Plan
{research_plan}

## Content Guidelines
Execute the research plan above to create a business-quality section that follows professional earnings summary format:

**Content Style (Match Business Format):**
- Lead with major developments and material announcements
- Synthesize information into coherent narratives, not bullet lists of facts
- Use strategic direct quotes only when they add significant insight or emphasis
- Present specific metrics, figures, and timeframes prominently 
- Group related information under clear, business-relevant subheadings
- Prioritize actionable insights over comprehensive coverage

**Professional Structure:**
- Start with the most material content first
- Use descriptive subheadings that reflect business priorities
- Combine quantitative data with qualitative context
- Include management rationale and strategic thinking
- Present information in logical flow that tells a coherent story

**Business-Quality Output Requirements:**
- Write concise, direct paragraphs focused on key insights
- Include specific numbers, percentages, timeframes, and context
- Capture management confidence levels and guidance
- Highlight risks, opportunities, and forward-looking statements
- Maintain analytical tone while being accessible to business readers

Create a section that reads like professional business analysis - substantive, well-organized, and immediately actionable for decision-makers.{prior_context}

## Transcript Content
{transcript_text}"""

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

    def setup_output_folder(self, analysis_folder_name: str) -> Path:
        """Create output folder for final sections."""
        output_folder = self.output_folder / analysis_folder_name
        output_folder.mkdir(exist_ok=True)

        self.logger.info(f"Created output folder: {output_folder}")
        return output_folder

    def process_analysis_folder(self, analysis_folder: Path) -> Path:
        """Process a single analysis folder to generate final sections."""
        self.logger.info(f"Processing analysis folder: {analysis_folder}")

        # Setup output folder
        self.current_analysis_folder = self.setup_output_folder(analysis_folder.name)

        # Load transcript and research plans
        transcript_text = self.load_transcript(analysis_folder)
        research_plans = self.load_research_plans(analysis_folder)

        if not research_plans:
            raise ValueError(f"No research plans found in {analysis_folder}")

        self.logger.info(f"Found {len(research_plans)} research plans to execute")

        # Reset state
        self.completed_sections = []

        # Process each research plan to create final sections
        for i, plan_info in enumerate(research_plans, 1):
            self.logger.info(
                f"Creating final section {i}/{len(research_plans)}: {plan_info['section_name']}"
            )

            try:
                # Format prior sections context
                prior_context = self._format_prior_sections_context()

                # Generate content prompt
                content_prompt = self.generate_section_content_prompt(
                    plan_info["section_name"],
                    plan_info["research_plan"],
                    transcript_text,
                    prior_context,
                )

                # Save prompt for debugging
                prompt_file = (
                    self.current_analysis_folder
                    / f"{plan_info['section_id']}_content_prompt.txt"
                )
                with open(prompt_file, "w", encoding="utf-8") as f:
                    f.write(content_prompt)

                # Make LLM call
                section_content = self.call_llm(content_prompt)

                # Save final section
                section_file = (
                    self.current_analysis_folder
                    / f"{plan_info['section_id']}_final_section.md"
                )
                with open(section_file, "w", encoding="utf-8") as f:
                    f.write(section_content)

                # Add to completed sections for context
                self.completed_sections.append(
                    {
                        "section_name": plan_info["section_name"],
                        "section_id": plan_info["section_id"],
                        "content": section_content,
                    }
                )

                self.logger.info(
                    f"Final section completed: {plan_info['section_name']}"
                )

            except Exception as e:
                self.logger.error(
                    f"Failed to create final section for {plan_info['section_name']}: {e}"
                )
                raise

        # Generate final complete report
        self._generate_complete_report(transcript_text)

        self.logger.info(
            f"Final sections completed. Results in: {self.current_analysis_folder}"
        )
        return self.current_analysis_folder

    def _format_prior_sections_context(self) -> str:
        """Format completed sections as context for subsequent sections."""
        if not self.completed_sections:
            return ""

        context_parts = []
        for section in self.completed_sections:
            context_parts.append(
                f"""### {section['section_name']}

{section['content']}"""
            )

        return "\n\n".join(context_parts)

    def _generate_complete_report(self, transcript_text: str):
        """Generate final complete earnings call analysis report."""
        report_content = f"""# Earnings Call Analysis Report

**Analysis Date:** {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Sections Completed:** {len(self.completed_sections)}

## Executive Summary

This comprehensive analysis covers {len(self.completed_sections)} key areas of the earnings call, providing detailed insights and extracted content for each section.

## Analysis Sections

"""

        for i, section in enumerate(self.completed_sections, 1):
            report_content += (
                f"## {i}. {section['section_name']}\n\n{section['content']}\n\n---\n\n"
            )

        report_content += """
## Analysis Methodology

This report was generated using AEGIS (Automated Earnings Generation and Intelligence System) which:
1. Created section-specific research plans tailored to this transcript
2. Executed systematic content extraction following the research plans
3. Maintained context consistency across sections
4. Applied structured formatting for clarity and usability

Each section was processed iteratively with full context of prior sections to ensure coherent and comprehensive analysis.
"""

        report_file = self.current_analysis_folder / "complete_earnings_analysis.md"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report_content)

        self.logger.info(f"Generated complete analysis report: {report_file}")

    def run(self):
        """Main processing workflow."""
        try:
            self.logger.info("Initializing AEGIS Final Section Generator...")

            # Setup SSL if configured
            self.setup_ssl()

            # Setup OAuth if configured
            self.oauth_token = self.setup_oauth()

            # Initialize OpenAI client
            self.openai_client = self.initialize_openai_client()

            # Find analysis folders to process
            analysis_folders = self.find_analysis_folders()

            if not analysis_folders:
                self.logger.warning(f"No analysis folders found in {self.input_folder}")
                return

            self.logger.info(
                f"Found {len(analysis_folders)} analysis folder(s) to process"
            )

            # Process each analysis folder
            for analysis_folder in analysis_folders:
                try:
                    result_folder = self.process_analysis_folder(analysis_folder)
                    self.logger.info(f"Successfully processed: {analysis_folder.name}")
                    print(f"Final sections saved to: {result_folder}")

                except Exception as e:
                    self.logger.error(f"Failed to process {analysis_folder.name}: {e}")
                    continue

            self.logger.info("All analysis folders processed successfully")

        except Exception as e:
            self.logger.error(f"Processing failed: {e}")
            raise


def main():
    """Main entry point."""
    import sys

    config_file = sys.argv[1] if len(sys.argv) > 1 else "config.json"

    generator = FinalSectionGenerator(config_file)
    generator.run()


if __name__ == "__main__":
    main()
