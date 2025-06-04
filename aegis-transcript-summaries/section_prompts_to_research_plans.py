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
        
        with open(self.config_path, 'r') as f:
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
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('transcript_processor.log'),
                logging.StreamHandler()
            ]
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
        
        if any(val.startswith("your-") for val in [oauth_endpoint, client_id, client_secret]):
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
            "Accept": "application/json"
        }
        
        try:
            response = requests.post(
                oauth_endpoint,
                data=payload,
                headers=headers,
                timeout=30,
                verify=self.config.get("ssl_cert_path") if self.config.get("ssl_cert_path") else True
            )
            
            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data.get("access_token")
                
                if access_token:
                    token_preview = access_token[:10] + "..." if len(access_token) > 10 else access_token
                    self.logger.info(f"OAuth successful. Token preview: {token_preview}")
                    return access_token
                else:
                    raise ValueError("No access token in OAuth response")
            else:
                self.logger.error(f"OAuth failed with status {response.status_code}: {response.text}")
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
            raise ValueError("No API key available (OAuth token or OPENAI_API_KEY environment variable)")
        
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
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                
                for page_num, page in enumerate(pdf_reader.pages):
                    try:
                        page_text = page.extract_text()
                        text += f"\n--- Page {page_num + 1} ---\n{page_text}\n"
                    except Exception as e:
                        self.logger.warning(f"Error extracting page {page_num + 1}: {e}")
                        continue
                
                if not text.strip():
                    raise ValueError("No text extracted from PDF")
                
                self.logger.info(f"Successfully extracted {len(text)} characters from PDF")
                return text.strip()
                
        except Exception as e:
            self.logger.error(f"Failed to extract PDF text: {e}")
            raise
    
    def setup_analysis_folder(self, transcript_name: str) -> Path:
        """Create analysis folder for current transcript."""
        clean_name = "".join(c for c in transcript_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        clean_name = clean_name.replace(' ', '_')
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        folder_name = f"{clean_name}_{timestamp}"
        
        analysis_folder = self.output_folder / folder_name
        analysis_folder.mkdir(exist_ok=True)
        
        self.logger.info(f"Created analysis folder: {analysis_folder}")
        return analysis_folder
    
    def load_section_context_from_file(self, file_path: str) -> str:
        """Load section context from markdown file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract the section context XML from the markdown
        lines = content.split('\n')
        in_context = False
        context_lines = []
        
        for line in lines:
            if '<section_context>' in line:
                in_context = True
                context_lines.append(line)
            elif '</section_context>' in line:
                context_lines.append(line)
                break
            elif in_context:
                context_lines.append(line)
        
        return '\n'.join(context_lines)
    
    def generate_research_prompt(self, section_name: str, section_context: str, 
                                transcript_text: str, prior_research: str = "") -> str:
        """Generate research planning prompt for a section."""
        
        prior_context = f"\n\n## Prior Research Plans\n{prior_research}" if prior_research else ""
        
        prompt = f"""# AEGIS Research Planning Task

## Objective
Create a concise research plan that guides systematic content extraction from an earnings call transcript. Focus on planning strategy and approach, NOT on extracting actual content.

## Section Focus
{section_context}

## Critical Instructions
- DO NOT include specific numbers, quotes, or detailed facts from the transcript
- DO NOT extract content - only plan how to extract it
- Keep the plan focused and concise (target 200-400 words)
- The analyst using this plan will have direct access to the full transcript

## Task: Create a strategic research plan covering:

1. **Content Availability Assessment** (2-3 sentences)
   - Rate the richness of relevant information in this transcript for this section
   - Note any gaps or limitations in available content

2. **Extraction Strategy** (bullet points)
   - Which transcript sections/speakers to prioritize
   - What types of information to look for (without including the actual content)
   - Recommended extraction sequence/approach

3. **Organization Framework** (brief structure)
   - How to structure the extracted content for clarity
   - Key themes or categories to organize around
   - Integration touchpoints with other sections

4. **Research Notes** (practical guidance)
   - Any transcript-specific challenges or opportunities
   - Contextual factors that will aid interpretation
   - Recommended focus areas based on what's uniquely available

## Output Requirements
- Maximum 400 words
- Focus on HOW to research, not WHAT was found
- Provide strategic guidance for the content extraction phase{prior_context}

## Transcript Content
{transcript_text}

---

Create a concise strategic research plan for "{section_name}" that guides efficient content extraction without including actual content."""

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
                temperature=self.config.get("temperature", 0.1)
            )
            
            if response.choices and response.choices[0].message:
                content = response.choices[0].message.content
                
                if hasattr(response, 'usage') and response.usage:
                    self.logger.info(f"Token usage - Prompt: {response.usage.prompt_tokens}, "
                                   f"Completion: {response.usage.completion_tokens}, "
                                   f"Total: {response.usage.total_tokens}")
                
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
        with open(transcript_file, 'w', encoding='utf-8') as f:
            f.write(transcript_text)
        
        # Find available section prompts
        section_files = list(self.section_prompts_folder.glob("*.md"))
        
        if not section_files:
            raise ValueError(f"No section prompt files found in {self.section_prompts_folder}")
        
        self.logger.info(f"Processing {len(section_files)} sections")
        
        # Reset analysis state
        self.completed_research_plans = []
        
        # Generate research plans for each section
        for i, section_file in enumerate(section_files, 1):
            section_id = section_file.stem
            section_name = section_id.replace('_', ' ').title()
            
            self.logger.info(f"Creating research plan {i}/{len(section_files)}: {section_name}")
            
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
                prompt_file = self.current_analysis_folder / f"{section_id}_research_prompt.txt"
                with open(prompt_file, 'w', encoding='utf-8') as f:
                    f.write(research_prompt)
                
                # Make LLM call
                research_plan = self.call_llm(research_prompt)
                
                # Save research plan
                plan_file = self.current_analysis_folder / f"{section_id}_research_plan.md"
                with open(plan_file, 'w', encoding='utf-8') as f:
                    f.write(research_plan)
                
                # Add to completed plans for context
                self.completed_research_plans.append({
                    'section_name': section_name,
                    'section_id': section_id,
                    'research_plan': research_plan
                })
                
                self.logger.info(f"Research plan completed: {section_name}")
                
            except Exception as e:
                self.logger.error(f"Failed to create research plan for {section_name}: {e}")
                raise
        
        # Generate final summary
        self._generate_research_plans_summary()
        
        self.logger.info(f"Research planning completed. Results in: {self.current_analysis_folder}")
        return self.current_analysis_folder
    
    def _format_prior_research_context(self) -> str:
        """Format completed research plans as context."""
        if not self.completed_research_plans:
            return ""
        
        context_parts = []
        for plan in self.completed_research_plans:
            context_parts.append(f"""## {plan['section_name']} Research Plan

{plan['research_plan']}""")
        
        return "\n\n".join(context_parts)
    
    def _generate_research_plans_summary(self):
        """Generate summary of all research plans."""
        summary_content = f"""# Earnings Call Research Plans Summary

**Planning Date:** {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Research Plans Created:** {len(self.completed_research_plans)}

## Research Planning Overview

This document contains the research plans for systematic content extraction and analysis. These plans identify what information is available in the transcript and how it should be structured for comprehensive analysis.

## Section Research Plans

"""
        
        for i, plan in enumerate(self.completed_research_plans, 1):
            summary_content += f"{i}. **{plan['section_name']}** (`{plan['section_id']}`)\n"
        
        summary_content += "\n## Complete Research Plans\n\n"
        
        for plan in self.completed_research_plans:
            summary_content += f"### {plan['section_name']}\n\n{plan['research_plan']}\n\n---\n\n"
        
        summary_content += """
## Next Steps

Use these research plans to systematically extract and analyze content from the transcript. Each plan provides:
- Available information assessment
- Content extraction strategy  
- Structural organization approach
- Integration opportunities with other sections
- Key transcript reference points

The research plans serve as a roadmap for comprehensive analysis execution.
"""
        
        summary_file = self.current_analysis_folder / "research_plans_summary.md"
        with open(summary_file, 'w', encoding='utf-8') as f:
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
                    continue
            
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