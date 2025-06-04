#!/usr/bin/env python3
"""
Standalone transcript processing script for AEGIS earnings call analysis.
Processes PDF transcripts iteratively through configured sections using RBC infrastructure.
"""

import os
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import requests
from openai import OpenAI
from cryptography import x509
from cryptography.hazmat.backends import default_backend
import datetime
import PyPDF2

# Import our custom modules
from master_prompt_template import generate_master_prompt, load_section_context_from_file
from config_to_prompt import ConfigToPromptConverter


class TranscriptProcessor:
    """Standalone transcript processor with RBC-specific authentication and SSL."""
    
    def __init__(self, config_file: str = "earnings_config_template.html", 
                 input_folder: str = "input_transcripts",
                 output_folder: str = "analysis_results"):
        """Initialize processor with RBC environment settings."""
        
        # RBC Environment Configuration
        self.ENVIRONMENT = "rbc"
        self.IS_RBC_ENV = True
        
        # SSL Configuration (copied from AEGIS)
        self.SSL_CERT_FILENAME = "rbc-ca-bundle.cer"
        self.SSL_CERT_DIR = Path(__file__).parent
        self.SSL_CERT_PATH = self.SSL_CERT_DIR / self.SSL_CERT_FILENAME
        self.CHECK_CERT_EXPIRY = True
        self.CERT_EXPIRY_WARNING_DAYS = 30
        self.USE_SSL = True
        
        # OAuth Configuration (copied from AEGIS)
        self.OAUTH_ENDPOINT = "x"  # Replace with actual RBC OAuth endpoint
        self.CLIENT_ID = "x"       # Replace with actual client ID
        self.CLIENT_SECRET = "x"   # Replace with actual client secret
        self.OAUTH_TIMEOUT = 180
        self.OAUTH_RETRIES = 3
        self.OAUTH_RETRY_DELAY = 2
        self.USE_OAUTH = True
        
        # OpenAI Configuration (RBC-specific)
        self.RBC_BASE_URL = "https://perf-apigw-int.saifg.rbc.com/JLCO/llm-control-stack/v1"
        self.BASE_URL = self.RBC_BASE_URL
        
        # Model Configuration (RBC)
        self.MODEL_CONFIG = {
            "name": "gpt-4o-2024-08-06",
            "max_tokens": 32768,
            "temperature": 0.1,
            "top_p": 0.95
        }
        
        # Paths
        self.config_file = Path(config_file)
        self.input_folder = Path(input_folder)
        self.output_folder = Path(output_folder)
        self.section_prompts_dir = Path("section_prompts")
        
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
    
    def setup_ssl(self) -> str:
        """Setup SSL certificate configuration (copied from AEGIS)."""
        if not self.USE_SSL:
            return "SSL certificate not required"
        
        self.logger.info("Setting up SSL certificate...")
        
        # Verify certificate exists
        if not os.path.exists(self.SSL_CERT_PATH):
            raise FileNotFoundError(f"SSL certificate not found at {self.SSL_CERT_PATH}")
        
        # Check certificate expiry if enabled
        if self.CHECK_CERT_EXPIRY:
            try:
                with open(self.SSL_CERT_PATH, 'rb') as cert_file:
                    cert_data = cert_file.read()
                    cert = x509.load_pem_x509_certificate(cert_data, default_backend())
                    
                    # Check expiry
                    days_until_expiry = (cert.not_valid_after - datetime.datetime.now()).days
                    if days_until_expiry <= 0:
                        raise ValueError(f"SSL certificate expired on {cert.not_valid_after}")
                    elif days_until_expiry <= self.CERT_EXPIRY_WARNING_DAYS:
                        self.logger.warning(f"SSL certificate expires in {days_until_expiry} days")
                    
                    self.logger.info(f"SSL certificate valid until {cert.not_valid_after}")
            except Exception as e:
                self.logger.warning(f"Could not validate certificate expiry: {e}")
        
        # Configure SSL environment variables
        os.environ["SSL_CERT_FILE"] = str(self.SSL_CERT_PATH)
        os.environ["REQUESTS_CA_BUNDLE"] = str(self.SSL_CERT_PATH)
        
        self.logger.info(f"SSL certificate configured: {self.SSL_CERT_PATH}")
        return str(self.SSL_CERT_PATH)
    
    def setup_oauth(self) -> str:
        """Setup OAuth authentication (copied from AEGIS)."""
        if not self.USE_OAUTH:
            raise ValueError("OAuth is required for RBC environment")
        
        self.logger.info("Setting up OAuth authentication...")
        
        # Validate OAuth configuration
        if self.OAUTH_ENDPOINT == "x" or self.CLIENT_ID == "x" or self.CLIENT_SECRET == "x":
            raise ValueError("OAuth configuration not properly set. Please update CLIENT_ID, CLIENT_SECRET, and OAUTH_ENDPOINT")
        
        # Prepare OAuth request
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.CLIENT_ID,
            "client_secret": self.CLIENT_SECRET,
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json"
        }
        
        # Retry logic
        for attempt in range(self.OAUTH_RETRIES):
            try:
                self.logger.info(f"OAuth attempt {attempt + 1}/{self.OAUTH_RETRIES}")
                
                response = requests.post(
                    self.OAUTH_ENDPOINT,
                    data=payload,
                    headers=headers,
                    timeout=self.OAUTH_TIMEOUT,
                    verify=str(self.SSL_CERT_PATH) if self.USE_SSL else True
                )
                
                if response.status_code == 200:
                    token_data = response.json()
                    access_token = token_data.get("access_token")
                    
                    if not access_token:
                        raise ValueError("No access token in OAuth response")
                    
                    # Log token preview for debugging (first 10 chars)
                    token_preview = access_token[:10] + "..." if len(access_token) > 10 else access_token
                    self.logger.info(f"OAuth successful. Token preview: {token_preview}")
                    
                    return access_token
                else:
                    error_msg = f"OAuth failed with status {response.status_code}: {response.text}"
                    self.logger.error(error_msg)
                    
                    if attempt < self.OAUTH_RETRIES - 1:
                        self.logger.info(f"Retrying in {self.OAUTH_RETRY_DELAY} seconds...")
                        time.sleep(self.OAUTH_RETRY_DELAY)
                    else:
                        raise Exception(error_msg)
                        
            except requests.exceptions.RequestException as e:
                error_msg = f"OAuth request failed: {e}"
                self.logger.error(error_msg)
                
                if attempt < self.OAUTH_RETRIES - 1:
                    self.logger.info(f"Retrying in {self.OAUTH_RETRY_DELAY} seconds...")
                    time.sleep(self.OAUTH_RETRY_DELAY)
                else:
                    raise Exception(error_msg)
        
        raise Exception("OAuth authentication failed after all retries")
    
    def initialize_openai_client(self) -> OpenAI:
        """Initialize OpenAI client with RBC configuration."""
        if not self.oauth_token:
            raise ValueError("OAuth token required before initializing OpenAI client")
        
        self.logger.info("Initializing OpenAI client...")
        
        client = OpenAI(
            api_key=self.oauth_token,
            base_url=self.BASE_URL
        )
        
        self.logger.info(f"OpenAI client initialized with base URL: {self.BASE_URL}")
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
        # Clean transcript name for folder
        clean_name = "".join(c for c in transcript_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        clean_name = clean_name.replace(' ', '_')
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        folder_name = f"{clean_name}_{timestamp}"
        
        analysis_folder = self.output_folder / folder_name
        analysis_folder.mkdir(exist_ok=True)
        
        self.logger.info(f"Created analysis folder: {analysis_folder}")
        return analysis_folder
    
    def call_llm(self, messages: List[Dict], **kwargs) -> str:
        """Make LLM API call with RBC configuration."""
        if not self.openai_client:
            raise ValueError("OpenAI client not initialized")
        
        self.logger.info("Making LLM API call...")
        
        # Prepare parameters
        params = {
            "model": self.MODEL_CONFIG["name"],
            "messages": messages,
            "max_tokens": self.MODEL_CONFIG.get("max_tokens", 32768),
            "temperature": self.MODEL_CONFIG.get("temperature", 0.1),
            "top_p": self.MODEL_CONFIG.get("top_p", 0.95),
            **kwargs
        }
        
        try:
            response = self.openai_client.chat.completions.create(**params)
            
            if response.choices and response.choices[0].message:
                content = response.choices[0].message.content
                
                # Log usage if available
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
        
        # Load section configurations
        converter = ConfigToPromptConverter(str(self.config_file))
        config_data = converter.parse_html_config()
        section_prompts = converter.generate_individual_section_prompts(config_data)
        
        self.logger.info(f"Processing {len(section_prompts)} sections")
        
        # Reset analysis state
        self.completed_research_plans = []
        
        # Generate research plans for each section iteratively
        for i, section_info in enumerate(section_prompts, 1):
            self.logger.info(f"Creating research plan {i}/{len(section_prompts)}: {section_info['section_name']}")
            
            try:
                research_plan = self._generate_research_plan(
                    section_info, 
                    transcript_text, 
                    i, 
                    len(section_prompts)
                )
                
                # Save research plan
                plan_file = self.current_analysis_folder / f"{section_info['section_id']}_research_plan.md"
                with open(plan_file, 'w', encoding='utf-8') as f:
                    f.write(research_plan)
                
                # Add to completed plans for context
                self.completed_research_plans.append({
                    'section_name': section_info['section_name'],
                    'section_id': section_info['section_id'],
                    'research_plan': research_plan
                })
                
                self.logger.info(f"Research plan completed: {section_info['section_name']}")
                
            except Exception as e:
                self.logger.error(f"Failed to create research plan for {section_info['section_name']}: {e}")
                raise
        
        # Generate final summary of research plans
        self._generate_research_plans_summary()
        
        self.logger.info(f"Research planning completed. Results in: {self.current_analysis_folder}")
        return self.current_analysis_folder
    
    def _generate_research_plan(self, section_info: Dict, transcript_text: str, 
                               section_num: int, total_sections: int) -> str:
        """Generate a research plan for a single section."""
        
        # Load section context from file
        section_file = self.section_prompts_dir / f"{section_info['section_id']}.md"
        if not section_file.exists():
            raise FileNotFoundError(f"Section prompt file not found: {section_file}")
        
        section_context = load_section_context_from_file(str(section_file))
        
        # Format prior research context
        prior_context = self._format_prior_research_context()
        
        # Generate master prompt
        master_prompt = generate_master_prompt(
            section_name=section_info['section_name'],
            section_context=section_context,
            transcript_text=transcript_text,
            enabled_widgets=section_info['enabled_widgets'],
            prior_research_plans=prior_context
        )
        
        # Save master prompt for debugging
        prompt_file = self.current_analysis_folder / f"{section_info['section_id']}_master_prompt.txt"
        with open(prompt_file, 'w', encoding='utf-8') as f:
            f.write(master_prompt)
        
        # Make LLM call
        messages = [{"role": "user", "content": master_prompt}]
        research_plan = self.call_llm(messages)
        
        return research_plan
    
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
            # Initialize RBC environment
            self.logger.info("Initializing AEGIS Transcript Processor...")
            
            # Setup SSL
            cert_path = self.setup_ssl()
            
            # Setup OAuth
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
    
    # Command line arguments
    config_file = sys.argv[1] if len(sys.argv) > 1 else "earnings_config_template.html"
    input_folder = sys.argv[2] if len(sys.argv) > 2 else "input_transcripts"
    output_folder = sys.argv[3] if len(sys.argv) > 3 else "analysis_results"
    
    # Create and run processor
    processor = TranscriptProcessor(config_file, input_folder, output_folder)
    processor.run()


if __name__ == "__main__":
    main()