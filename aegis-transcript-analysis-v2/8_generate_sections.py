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
import re

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

    def _get_model_params(self, model: str, use_tools: bool = False) -> dict:
        """Get supported parameters for the specified model."""
        # Models that don't support temperature or tools (like o1 series)
        no_temperature_models = ["o1-preview", "o1-mini", "o1"]
        no_tools_models = ["o1-preview", "o1-mini", "o1"]  # o1 models don't support function calling yet
        
        # Base parameters that all models support
        params = {
            "model": model,
            "messages": [],
        }
        
        # Add max_tokens if configured
        if "max_tokens" in self.config:
            params["max_tokens"] = self.config["max_tokens"]
        
        # Only add temperature for models that support it
        if not any(no_temp in model.lower() for no_temp in no_temperature_models):
            params["temperature"] = self.config.get("temperature", 0.1)
        else:
            self.logger.info(f"Model {model} doesn't support temperature parameter - skipping")
        
        # Only add tools for models that support them
        if use_tools and not any(no_tool in model.lower() for no_tool in no_tools_models):
            params["tools"] = [self._get_section_analysis_tool_schema()]
            params["tool_choice"] = {"type": "function", "function": {"name": "create_section_analysis"}}
        elif use_tools:
            self.logger.info(f"Model {model} doesn't support function calling - using structured prompt instead")
        
        return params

    def _get_section_analysis_tool_schema(self) -> dict:
        """Define the tool schema for structured section analysis output."""
        return {
            "type": "function",
            "function": {
                "name": "create_section_analysis",
                "description": "Create structured analysis for an earnings call transcript section",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "section_name": {
                            "type": "string",
                            "description": "Short identifier for the section"
                        },
                        "section_title": {
                            "type": "string", 
                            "description": "Descriptive title showing key theme"
                        },
                        "section_statement": {
                            "type": "string",
                            "description": "Comprehensive paragraph synthesizing all content and key themes"
                        },
                        "content": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "subsection": {
                                        "type": "string",
                                        "description": "Specific topic within section"
                                    },
                                    "quotes": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "quote_text": {
                                                    "type": "string",
                                                    "description": "Exact transcript quote with HTML highlighting"
                                                },
                                                "context": {
                                                    "type": ["string", "null"],
                                                    "description": "Supporting clarification or null if not needed"
                                                },
                                                "speaker": {
                                                    "type": "object",
                                                    "properties": {
                                                        "name": {"type": "string"},
                                                        "title": {"type": "string"},
                                                        "company": {"type": "string"}
                                                    },
                                                    "required": ["name", "title", "company"]
                                                },
                                                "sentiment": {
                                                    "type": "string",
                                                    "enum": ["positive", "negative", "neutral", "cautious", "confident", "optimistic", "bullish", "stable"]
                                                },
                                                "sentiment_rationale": {
                                                    "type": "string",
                                                    "description": "Brief explanation for sentiment classification"
                                                },
                                                "key_metrics": {
                                                    "type": "array",
                                                    "items": {"type": "string"},
                                                    "description": "Array of quantitative data mentioned in quote"
                                                }
                                            },
                                            "required": ["quote_text", "context", "speaker", "sentiment", "sentiment_rationale", "key_metrics"]
                                        }
                                    }
                                },
                                "required": ["subsection", "quotes"]
                            }
                        }
                    },
                    "required": ["section_name", "section_title", "section_statement", "content"]
                }
            }
        }

    def call_llm_with_structure(self, prompt: str, use_function_calling: bool = True) -> Dict:
        """Make LLM API call with structured output (function calling or fallback)."""
        if not self.openai_client:
            raise ValueError("OpenAI client not initialized")

        model = self.config.get("openai_model", "gpt-4")
        self.logger.info(f"Making structured LLM API call for section analysis with model: {model}")

        # Check if model supports function calling
        no_tools_models = ["o1-preview", "o1-mini", "o1"]
        supports_tools = not any(no_tool in model.lower() for no_tool in no_tools_models)
        
        messages = [{"role": "user", "content": prompt}]

        try:
            if use_function_calling and supports_tools:
                # Use function calling for supported models
                self.logger.info("Using function calling for structured section analysis")
                params = self._get_model_params(model, use_tools=True)
                params["messages"] = messages
                
                response = self.openai_client.chat.completions.create(**params)
                
                if response.choices and response.choices[0].message.tool_calls:
                    tool_call = response.choices[0].message.tool_calls[0]
                    function_args = json.loads(tool_call.function.arguments)
                    
                    if hasattr(response, "usage") and response.usage:
                        self.logger.info(
                            f"Token usage - Prompt: {response.usage.prompt_tokens}, "
                            f"Completion: {response.usage.completion_tokens}, "
                            f"Total: {response.usage.total_tokens}"
                        )
                    
                    return function_args
                else:
                    raise ValueError("No tool calls in function calling response")
                    
            else:
                # Fallback to structured prompt for o1 models
                self.logger.info("Using structured prompt fallback for section analysis (no function calling)")
                
                # Add JSON schema instruction to prompt for section analysis
                structured_prompt = f"""{prompt}

IMPORTANT: You MUST respond with valid JSON following the transcript JSON format exactly:

{{
  "section_name": "string",
  "section_title": "string showing key theme", 
  "section_statement": "Comprehensive paragraph synthesizing all content and themes",
  "content": [
    {{
      "subsection": "string",
      "quotes": [
        {{
          "quote_text": "exact quote with <span class=\\"highlight-keyword\\">keywords</span> highlighted",
          "context": "string or null",
          "speaker": {{
            "name": "string",
            "title": "string", 
            "company": "string"
          }},
          "sentiment": "positive|negative|neutral|cautious|confident|optimistic|bullish|stable",
          "sentiment_rationale": "brief explanation",
          "key_metrics": ["metric1", "metric2"]
        }}
      ]
    }}
  ]
}}

Respond with ONLY the JSON, no additional text or explanation."""

                params = self._get_model_params(model, use_tools=False)
                params["messages"] = [{"role": "user", "content": structured_prompt}]
                
                response = self.openai_client.chat.completions.create(**params)
                
                if response.choices and response.choices[0].message:
                    content = response.choices[0].message.content
                    
                    if hasattr(response, "usage") and response.usage:
                        self.logger.info(
                            f"Token usage - Prompt: {response.usage.prompt_tokens}, "
                            f"Completion: {response.usage.completion_tokens}, "
                            f"Total: {response.usage.total_tokens}"
                        )
                    
                    # Log the raw response for debugging
                    self.logger.info("=== RAW SECTION ANALYSIS RESPONSE START ===")
                    self.logger.info(content)
                    self.logger.info("=== RAW SECTION ANALYSIS RESPONSE END ===")
                    
                    # Parse JSON response
                    try:
                        parsed = json.loads(content.strip())
                        self.logger.info("✅ Successfully parsed section analysis JSON")
                        return parsed
                    except json.JSONDecodeError as e:
                        self.logger.warning(f"❌ Failed to parse section analysis JSON: {e}")
                        self.logger.warning(f"Error position: {e.pos if hasattr(e, 'pos') else 'unknown'}")
                        
                        # Show problematic part of response
                        if hasattr(e, 'pos') and e.pos < len(content):
                            start = max(0, e.pos - 50)
                            end = min(len(content), e.pos + 50)
                            problem_area = content[start:end]
                            self.logger.warning(f"Problematic area: ...{problem_area}...")
                        
                        # Try to extract JSON from the response
                        return self._extract_section_json_fallback(content)
                else:
                    raise ValueError("No content in LLM response")

        except Exception as e:
            self.logger.error(f"Structured section analysis LLM call failed: {e}")
            raise

    def _extract_section_json_fallback(self, response: str) -> Dict:
        """Fallback JSON extraction for section analysis with o1 reasoning text."""
        import re
        
        self.logger.info("🔍 Starting section analysis fallback JSON extraction...")
        
        # Try to find JSON in the response using various strategies
        json_patterns = [
            (r'```json\s*(.*?)\s*```', "```json blocks"),
            (r'```\s*(.*?)\s*```', "generic ``` blocks"),
        ]
        
        for pattern, description in json_patterns:
            matches = re.findall(pattern, response, re.DOTALL)
            for i, match in enumerate(matches):
                try:
                    parsed = json.loads(match.strip())
                    if isinstance(parsed, dict) and 'section_name' in parsed:
                        self.logger.info(f"✅ Success with {description} - match {i+1}")
                        return parsed
                except json.JSONDecodeError:
                    continue
        
        # Try brace-matched extraction
        json_candidates = []
        brace_count = 0
        start_idx = -1
        
        for i, char in enumerate(response):
            if char == '{':
                if brace_count == 0:
                    start_idx = i
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and start_idx != -1:
                    candidate = response[start_idx:i+1]
                    json_candidates.append(candidate)
                    start_idx = -1
        
        for candidate in json_candidates:
            try:
                parsed = json.loads(candidate.strip())
                if isinstance(parsed, dict) and 'section_name' in parsed:
                    self.logger.info("✅ Success with brace-matched extraction")
                    return parsed
            except json.JSONDecodeError:
                continue
        
        # If all else fails, return a basic structure
        self.logger.warning("❌ Section analysis extraction failed, returning basic structure")
        return {
            "section_name": "Unknown",
            "section_title": "Analysis Results",
            "section_statement": "Section analysis could not be properly parsed",
            "content": [
                {
                    "subsection": "Raw Analysis",
                    "quotes": [
                        {
                            "quote_text": "Analysis could not be parsed as JSON",
                            "context": response[:500] + "..." if len(response) > 500 else response,
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
        }

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

        # Make structured LLM call
        try:
            section_analysis = self.call_llm_with_structure(prompt)
        except Exception as e:
            self.logger.warning(f"Structured section analysis call failed, using fallback: {e}")
            section_analysis = {
                "section_name": section_name,
                "section_title": f"{section_name}: Analysis Results",
                "section_statement": f"Analysis generated for {section_name} section",
                "content": [
                    {
                        "subsection": "Raw Analysis",
                        "quotes": [
                            {
                                "quote_text": "Section analysis call failed",
                                "context": str(e),
                                "speaker": {
                                    "name": "System",
                                    "title": "Error Handler",
                                    "company": "AEGIS",
                                },
                                "sentiment": "neutral",
                                "sentiment_rationale": "System error fallback",
                                "key_metrics": [],
                            }
                        ],
                    }
                ],
                "processing_note": "LLM call failed, using fallback structure",
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
