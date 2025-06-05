#!/usr/bin/env python3
"""
Section Generation Script

This script iteratively processes sections from 6_research_plan.json to generate
structured analysis following the transcript JSON format. It builds context
progressively as each section is analyzed.

Flow:
1. Load research plans from 6_research_plan.json
2. Extract PDF text from 4_transcript_input_pdf/
3. Iteratively generate analysis for each section:
   - Use prior completed analyses as context
   - Execute current section's research plan using 7_research_analysis_system_prompt.py
   - Structure output according to TRANSCRIPT_JSON_FORMAT.md
4. Save all section analyses to 9_report_sections.json

The script follows the same authentication and configuration patterns as the
reference implementation.
"""

import os
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional
import requests
from openai import OpenAI
import PyPDF2

# Import with importlib to handle numeric filename
import importlib.util

spec = importlib.util.spec_from_file_location(
    "analysis_prompt", "7_research_analysis_system_prompt.py"
)
analysis_prompt_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis_prompt_module)
create_research_analysis_prompt = analysis_prompt_module.create_research_analysis_prompt


class SectionGenerator:
    """Generates iterative section analyses from research plans and transcript."""

    def __init__(self, config_path: str = "config.json"):
        """Initialize with configuration from JSON file."""

        # Load configuration
        self.config_path = Path(config_path)
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(self.config_path, "r") as f:
            self.config = json.load(f)

        # Set up paths
        self.research_plans_file = Path("6_research_plan.json")
        self.transcript_input_folder = Path("4_transcript_input_pdf")
        self.output_file = Path("9_report_sections.json")

        # Validate required files exist
        if not self.research_plans_file.exists():
            raise FileNotFoundError(
                f"Research plans not found: {self.research_plans_file}"
            )

        if not self.transcript_input_folder.exists():
            raise FileNotFoundError(
                f"Transcript input folder not found: {self.transcript_input_folder}"
            )

        # Initialize components
        self.logger = self._setup_logging()
        self.oauth_token = None
        self.openai_client = None

        # Processing state
        self.research_plans = None
        self.transcript_text = None
        self.completed_analyses = []

    def _setup_logging(self) -> logging.Logger:
        """Configure logging for the processor."""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler("section_generator.log"),
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

    def load_research_plans(self) -> List[Dict]:
        """Load research plans from JSON file."""
        self.logger.info(f"Loading research plans from: {self.research_plans_file}")

        with open(self.research_plans_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        research_plans = data.get("research_plans", [])

        self.logger.info(f"Loaded {len(research_plans)} research plans")
        return research_plans

    def extract_pdf_text(self) -> str:
        """Extract text from the first PDF found in the input folder."""
        pdf_files = list(self.transcript_input_folder.glob("*.pdf"))

        if not pdf_files:
            raise FileNotFoundError(
                f"No PDF files found in {self.transcript_input_folder}"
            )

        if len(pdf_files) > 1:
            self.logger.warning(
                f"Multiple PDFs found, using first one: {pdf_files[0].name}"
            )

        pdf_path = pdf_files[0]
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
                max_tokens=self.config.get("max_tokens", 8000),
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

    def generate_section_analysis(
        self, current_research_plan: Dict, completed_analyses: List[Dict]
    ) -> Dict:
        """Generate analysis for a single section using its research plan."""

        section_name = current_research_plan.get("section_name", "Unknown Section")
        section_id = current_research_plan.get("section_id", "unknown")

        self.logger.info(f"Generating analysis for: {section_name}")

        # Prepare current section info (extract from research plan)
        current_section = {
            "section_id": section_id,
            "section_name": section_name,
            "description": self._extract_section_description(current_research_plan),
        }

        # Generate system prompt using 7_research_analysis_system_prompt.py
        prompt = create_research_analysis_prompt(
            current_section=current_section,
            current_research_plan=current_research_plan,
            completed_analyses=completed_analyses,
            transcript_text=self.transcript_text,
        )

        # Make LLM call
        response = self.call_llm(prompt)

        # Try to parse as JSON, fallback to structured format if needed
        try:
            # Extract JSON from response if it's wrapped in markdown
            if "```json" in response:
                json_start = response.find("```json") + 7
                json_end = response.find("```", json_start)
                json_text = response[json_start:json_end].strip()
            else:
                json_text = response.strip()

            section_analysis = json.loads(json_text)

        except json.JSONDecodeError as e:
            self.logger.warning(
                f"Failed to parse JSON response, creating structured fallback: {e}"
            )
            # Create structured fallback following transcript JSON format
            section_analysis = {
                "section_name": section_name,
                "section_title": f"{section_name}: Analysis Results",
                "section_statement": f"Analysis generated for {section_name} section",
                "content": [
                    {
                        "subsection": "Raw Analysis",
                        "quotes": [
                            {
                                "quote_text": "Analysis could not be parsed as JSON",
                                "context": (
                                    response[:500] + "..."
                                    if len(response) > 500
                                    else response
                                ),
                                "speaker": {
                                    "name": "System",
                                    "title": "Parser",
                                    "company": "AEGIS",
                                },
                                "sentiment": "neutral",
                                "sentiment_rationale": "Raw text output",
                                "key_metrics": [],
                            }
                        ],
                    }
                ],
                "processing_note": "JSON parsing failed, review response format",
            }

        self.logger.info(f"Section analysis generated for: {section_name}")
        return section_analysis

    def _extract_section_description(self, research_plan: Dict) -> str:
        """Extract section description from research plan."""
        # Try to find description in various locations
        if "description" in research_plan:
            return research_plan["description"]

        plan_details = research_plan.get("research_plan", {})
        if isinstance(plan_details, dict):
            quality_considerations = plan_details.get("quality_considerations", {})
            business_relevance = quality_considerations.get("business_relevance", "")
            if business_relevance:
                return business_relevance

        # Fallback
        return f"Analysis of {research_plan.get('section_name', 'unknown')} section content"

    def process_sections_iteratively(self) -> List[Dict]:
        """Process all research plans iteratively, building context as we go."""
        research_plans = self.research_plans
        completed_analyses = []

        self.logger.info(
            f"Starting iterative processing of {len(research_plans)} sections"
        )

        for i, current_research_plan in enumerate(research_plans):
            section_name = current_research_plan.get("section_name", f"Section {i+1}")

            self.logger.info(
                f"Processing section {i+1}/{len(research_plans)}: {section_name} "
                f"(Prior analyses: {len(completed_analyses)})"
            )

            try:
                # Generate analysis for current section
                section_analysis = self.generate_section_analysis(
                    current_research_plan=current_research_plan,
                    completed_analyses=completed_analyses,
                )

                # Add to completed analyses for next iteration
                completed_analyses.append(section_analysis)

                # Small delay to be respectful to API
                time.sleep(1)

            except Exception as e:
                self.logger.error(
                    f"Failed to generate analysis for {section_name}: {e}"
                )
                # Continue with other sections rather than failing completely
                continue

        self.logger.info(f"Completed processing {len(completed_analyses)} sections")
        return completed_analyses

    def save_section_analyses(self, section_analyses: List[Dict]) -> None:
        """Save section analyses to JSON file."""
        output_data = {
            "metadata": {
                "creation_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "source_research_plans_file": str(self.research_plans_file),
                "transcript_source_folder": str(self.transcript_input_folder),
                "total_sections_processed": len(section_analyses),
                "processing_approach": "iterative_context_building",
                "format_specification": "TRANSCRIPT_JSON_FORMAT.md",
            },
            "sections": section_analyses,
        }

        self.logger.info(f"Saving section analyses to: {self.output_file}")
        with open(self.output_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        self.logger.info(f"Section analyses saved successfully")

    def run(self):
        """Main processing workflow."""
        try:
            self.logger.info("Starting AEGIS Section Generator...")

            # Setup authentication
            self.setup_ssl()
            self.oauth_token = self.setup_oauth()
            self.openai_client = self.initialize_openai_client()

            # Load research plans
            self.research_plans = self.load_research_plans()

            # Extract transcript text
            self.transcript_text = self.extract_pdf_text()

            # Process sections iteratively
            section_analyses = self.process_sections_iteratively()

            # Save results
            self.save_section_analyses(section_analyses)

            self.logger.info("Section generation completed successfully")
            print(f"Section analyses saved to: {self.output_file}")

        except Exception as e:
            self.logger.error(f"Section generation failed: {e}")
            raise


def main():
    """Main entry point."""
    import sys

    config_file = sys.argv[1] if len(sys.argv) > 1 else "config.json"

    generator = SectionGenerator(config_file)
    generator.run()


if __name__ == "__main__":
    main()
