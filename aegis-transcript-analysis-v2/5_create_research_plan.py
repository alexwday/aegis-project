#!/usr/bin/env python3
"""
Research Plan Creation Script

This script orchestrates the iterative creation of research plans for each section
defined in the section instructions. It builds context progressively as each
research plan is completed.

Flow:
1. Load section instructions from 2_section_instructions.json
2. Extract PDF text from 4_transcript_input_pdf/
3. Iteratively create research plans for each enabled section:
   - Use prior completed research plans as context
   - Focus on current section requirements
   - Show downstream sections for awareness
4. Save all research plans to 6_research_plan.json

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
    "research_prompt", "3_research_plan_system_prompt.py"
)
research_prompt_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(research_prompt_module)
create_research_plan_prompt = research_prompt_module.create_research_plan_prompt


class ResearchPlanCreator:
    """Creates iterative research plans from transcript and section instructions."""

    def __init__(self, config_path: str = "config.json"):
        """Initialize with configuration from JSON file."""

        # Load configuration
        self.config_path = Path(config_path)
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(self.config_path, "r") as f:
            self.config = json.load(f)

        # Set up paths
        self.section_instructions_file = Path("2_section_instructions.json")
        self.transcript_input_folder = Path("4_transcript_input_pdf")
        self.output_file = Path("6_research_plan.json")

        # Validate required files exist
        if not self.section_instructions_file.exists():
            raise FileNotFoundError(
                f"Section instructions not found: {self.section_instructions_file}"
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
        self.section_instructions = None
        self.transcript_text = None
        self.completed_research_plans = []

    def _setup_logging(self) -> logging.Logger:
        """Configure logging for the processor."""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler("research_plan_creator.log"),
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

    def load_section_instructions(self) -> List[Dict]:
        """Load section instructions from JSON file."""
        self.logger.info(
            f"Loading section instructions from: {self.section_instructions_file}"
        )

        with open(self.section_instructions_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        sections = data.get("sections", [])
        enabled_sections = [s for s in sections if s.get("enabled", True)]

        self.logger.info(
            f"Loaded {len(sections)} total sections, {len(enabled_sections)} enabled"
        )
        return enabled_sections

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
            params["tools"] = [self._get_research_plan_tool_schema()]
            params["tool_choice"] = {"type": "function", "function": {"name": "create_research_plan"}}
        elif use_tools:
            self.logger.info(f"Model {model} doesn't support function calling - using structured prompt instead")
        
        return params

    def _get_research_plan_tool_schema(self) -> dict:
        """Define the tool schema for structured research plan output."""
        return {
            "type": "function",
            "function": {
                "name": "create_research_plan",
                "description": "Create a structured research plan for extracting content from an earnings call transcript section",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "section_id": {
                            "type": "string",
                            "description": "Short identifier for the section (e.g., 'credit', 'capital')"
                        },
                        "section_name": {
                            "type": "string", 
                            "description": "Full name of the section being analyzed"
                        },
                        "research_plan": {
                            "type": "object",
                            "properties": {
                                "content_availability": {
                                    "type": "object",
                                    "properties": {
                                        "high_priority_content": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                            "description": "List of high-priority content types expected in this section"
                                        },
                                        "medium_priority_content": {
                                            "type": "array", 
                                            "items": {"type": "string"},
                                            "description": "List of medium-priority content types that may be present"
                                        }
                                    }
                                },
                                "extraction_strategy": {
                                    "type": "object",
                                    "properties": {
                                        "key_quotes": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "content_description": {"type": "string"},
                                                    "speaker_attribution": {"type": "string"},
                                                    "approximate_location": {"type": "string"},
                                                    "priority": {"type": "string", "enum": ["high", "medium", "low"]}
                                                }
                                            }
                                        },
                                        "numerical_data": {
                                            "type": "array",
                                            "items": {
                                                "type": "object", 
                                                "properties": {
                                                    "metric_description": {"type": "string"},
                                                    "expected_format": {"type": "string"},
                                                    "comparative_context": {"type": "string"},
                                                    "priority": {"type": "string", "enum": ["high", "medium", "low"]}
                                                }
                                            }
                                        }
                                    }
                                },
                                "organization_structure": {
                                    "type": "object",
                                    "properties": {
                                        "primary_subsections": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "subsection_name": {"type": "string"},
                                                    "content_focus": {"type": "string"}
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "required": ["section_id", "section_name", "research_plan"]
                }
            }
        }

    def call_llm_with_structure(self, prompt: str, use_function_calling: bool = True) -> Dict:
        """Make LLM API call with structured output (function calling or fallback)."""
        if not self.openai_client:
            raise ValueError("OpenAI client not initialized")

        model = self.config.get("openai_model", "gpt-4")
        self.logger.info(f"Making structured LLM API call with model: {model}")

        # Check if model supports function calling
        no_tools_models = ["o1-preview", "o1-mini", "o1"]
        supports_tools = not any(no_tool in model.lower() for no_tool in no_tools_models)
        
        messages = [{"role": "user", "content": prompt}]

        try:
            if use_function_calling and supports_tools:
                # Use function calling for supported models
                self.logger.info("Using function calling for structured output")
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
                # Fallback to structured prompt for o1 models or when function calling is disabled
                self.logger.info("Using structured prompt fallback (no function calling)")
                
                # Add JSON schema instruction to prompt
                structured_prompt = f"""{prompt}

IMPORTANT: You MUST respond with valid JSON following this exact structure:

{{
  "section_id": "string",
  "section_name": "string", 
  "research_plan": {{
    "content_availability": {{
      "high_priority_content": ["string1", "string2"],
      "medium_priority_content": ["string1", "string2"]
    }},
    "extraction_strategy": {{
      "key_quotes": [{{
        "content_description": "string",
        "speaker_attribution": "string",
        "approximate_location": "string", 
        "priority": "high|medium|low"
      }}],
      "numerical_data": [{{
        "metric_description": "string",
        "expected_format": "string",
        "comparative_context": "string",
        "priority": "high|medium|low"
      }}]
    }},
    "organization_structure": {{
      "primary_subsections": [{{
        "subsection_name": "string",
        "content_focus": "string"
      }}]
    }}
  }}
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
                    
                    # Parse JSON response
                    try:
                        return json.loads(content.strip())
                    except json.JSONDecodeError as e:
                        self.logger.warning(f"Failed to parse JSON from structured prompt: {e}")
                        # Try to extract JSON from the response
                        return self._extract_json_fallback(content)
                else:
                    raise ValueError("No content in LLM response")

        except Exception as e:
            self.logger.error(f"Structured LLM API call failed: {e}")
            raise

    def _extract_json_fallback(self, response: str) -> Dict:
        """Fallback JSON extraction for o1 models with reasoning text."""
        import re
        
        # Try to find JSON in the response
        json_patterns = [
            r'```json\s*(.*?)\s*```',
            r'```\s*(.*?)\s*```',
            r'\{.*\}',
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, response, re.DOTALL)
            for match in matches:
                try:
                    parsed = json.loads(match.strip())
                    if isinstance(parsed, dict) and 'section_id' in parsed:
                        return parsed
                except json.JSONDecodeError:
                    continue
        
        # If all else fails, return a basic structure
        self.logger.warning("Could not extract valid JSON, returning basic structure")
        return {
            "section_id": "unknown",
            "section_name": "Unknown Section",
            "research_plan": {
                "content_availability": {"high_priority_content": [], "medium_priority_content": []},
                "extraction_strategy": {"key_quotes": [], "numerical_data": []}, 
                "organization_structure": {"primary_subsections": []}
            }
        }

    def create_research_plan_for_section(
        self,
        current_section: Dict,
        completed_plans: List[Dict],
        downstream_sections: List[Dict],
    ) -> Dict:
        """Create a research plan for a single section."""

        section_name = current_section.get("section_name", "Unknown Section")
        self.logger.info(f"Creating research plan for: {section_name}")

        # Generate system prompt
        prompt = create_research_plan_prompt(
            current_section=current_section,
            completed_research_plans=completed_plans,
            downstream_sections=downstream_sections,
            transcript_text=self.transcript_text,
        )

        # Make structured LLM call
        try:
            research_plan = self.call_llm_with_structure(prompt)
        except Exception as e:
            self.logger.warning(f"Structured LLM call failed, using fallback: {e}")
            research_plan = {
                "section_id": current_section.get("section_id", "unknown"),
                "section_name": section_name,
                "research_plan": {
                    "content_availability": {"high_priority_content": [], "medium_priority_content": []},
                    "extraction_strategy": {"key_quotes": [], "numerical_data": []}, 
                    "organization_structure": {"primary_subsections": []}
                },
                "format": "fallback",
            }

        self.logger.info(f"Research plan created for: {section_name}")
        return research_plan

    def process_sections_iteratively(self) -> List[Dict]:
        """Process all sections iteratively, building context as we go."""
        sections = self.section_instructions
        completed_plans = []

        self.logger.info(f"Starting iterative processing of {len(sections)} sections")

        for i, current_section in enumerate(sections):
            section_name = current_section.get("section_name", f"Section {i+1}")

            # Determine downstream sections (remaining sections after current)
            downstream_sections = sections[i + 1 :] if i < len(sections) - 1 else []

            self.logger.info(
                f"Processing section {i+1}/{len(sections)}: {section_name} "
                f"(Prior: {len(completed_plans)}, Downstream: {len(downstream_sections)})"
            )

            try:
                # Create research plan for current section
                research_plan = self.create_research_plan_for_section(
                    current_section=current_section,
                    completed_plans=completed_plans,
                    downstream_sections=downstream_sections,
                )

                # Add to completed plans for next iteration
                completed_plans.append(research_plan)

                # Small delay to be respectful to API
                time.sleep(1)

            except Exception as e:
                self.logger.error(
                    f"Failed to create research plan for {section_name}: {e}"
                )
                # Continue with other sections rather than failing completely
                continue

        self.logger.info(f"Completed processing {len(completed_plans)} sections")
        return completed_plans

    def save_research_plans(self, research_plans: List[Dict]) -> None:
        """Save research plans to JSON file."""
        output_data = {
            "metadata": {
                "creation_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "source_sections_file": str(self.section_instructions_file),
                "transcript_source_folder": str(self.transcript_input_folder),
                "total_sections_processed": len(research_plans),
                "processing_approach": "iterative_context_building",
            },
            "research_plans": research_plans,
        }

        self.logger.info(f"Saving research plans to: {self.output_file}")
        with open(self.output_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        self.logger.info(f"Research plans saved successfully")

    def run(self):
        """Main processing workflow."""
        try:
            self.logger.info("Starting AEGIS Research Plan Creator...")

            # Setup authentication
            self.setup_ssl()
            self.oauth_token = self.setup_oauth()
            self.openai_client = self.initialize_openai_client()

            # Load section instructions
            self.section_instructions = self.load_section_instructions()

            # Extract transcript text
            self.transcript_text = self.extract_pdf_text()

            # Process sections iteratively
            research_plans = self.process_sections_iteratively()

            # Save results
            self.save_research_plans(research_plans)

            self.logger.info("Research plan creation completed successfully")
            print(f"Research plans saved to: {self.output_file}")

        except Exception as e:
            self.logger.error(f"Research plan creation failed: {e}")
            raise


def main():
    """Main entry point."""
    import sys

    config_file = sys.argv[1] if len(sys.argv) > 1 else "config.json"

    creator = ResearchPlanCreator(config_file)
    creator.run()


if __name__ == "__main__":
    main()
