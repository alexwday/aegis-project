# -*- coding: utf-8 -*-
"""
Stage 3: Generate Transcript Chunks with Sentence-Based LLM Chunking

This script processes markdown files from Stage 2 using a two-phase approach:
1. Phase 1: Split text into indexed sentences, then use LLM to identify chunk boundaries
2. Phase 2: Extract metadata for each chunk using LLM

The LLM only returns sentence indices, avoiding any content rewriting to handle DLP concerns.
"""

import os
import sys
import json
import time
import re
import tempfile
import requests
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
import logging
import smbclient
from openai import OpenAI
import tiktoken
import pysbd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ==============================================================================
# --- Configuration ---
# ==============================================================================

# --- Test Mode Configuration ---
# Set to True to process only one transcript for testing
TEST_MODE = True
# Specify which transcript to process in test mode (None = first available)
TEST_TRANSCRIPT_ID = None

# --- NAS Configuration (Should match Stage 1/2) ---
NAS_PARAMS = {
    "ip": "your_nas_ip",
    "share": "your_share_name",
    "user": "your_nas_user",
    "password": "your_nas_password"
}

# Base paths
NAS_OUTPUT_FOLDER_PATH = "path/to/your/output_folder"

# Document configuration
DOCUMENT_SOURCE = 'earnings_call'
DOCUMENT_TYPE = 'transcript'
DOCUMENT_LANGUAGE = 'en'

# --- OAuth Configuration ---
OAUTH_CONFIG = {
    "token_url": "YOUR_OAUTH_TOKEN_ENDPOINT_URL",
    "client_id": "YOUR_CLIENT_ID",
    "client_secret": "YOUR_CLIENT_SECRET"
}

# --- GPT API Configuration ---
GPT_CONFIG = {
    "base_url": "YOUR_CUSTOM_GPT_API_BASE_URL",
    "model_name": "gpt-4o"
}

# --- CA Bundle for SSL ---
CA_BUNDLE_FILENAME = 'rbc-ca-bundle.cer'
# Path to the CA Bundle on the NAS (relative to share root)
CA_BUNDLE_NAS_PATH = 'certs'

# --- Processing Configuration ---
# Chunking parameters
TARGET_CHUNK_SIZE = 500  # Target tokens per chunk
MIN_CHUNK_SIZE = 300     # Minimum tokens per chunk
MAX_CHUNK_SIZE = 700     # Maximum tokens per chunk
BATCH_TOKEN_LIMIT = 3000 # Maximum tokens to send to LLM per batch

# Metadata extraction parameters
METADATA_BATCH_SIZE = 5  # Number of chunks to process together for metadata

# Section grouping parameters
SECTION_BATCH_SIZE = 10  # Number of chunks to consider for section boundaries

# ==============================================================================
# --- Helper Functions ---
# ==============================================================================

def initialize_smb_client():
    """Sets up smbclient credentials."""
    try:
        smbclient.ClientConfig(username=NAS_PARAMS["user"], password=NAS_PARAMS["password"])
        logger.info("SMB client configured successfully.")
        return True
    except Exception as e:
        logger.error(f"Failed to configure SMB client: {e}")
        return False

def create_nas_directory(smb_dir_path):
    """Creates a directory on the NAS if it doesn't exist."""
    try:
        if not smbclient.path.exists(smb_dir_path):
            logger.info(f"Creating NAS directory: {smb_dir_path}")
            smbclient.makedirs(smb_dir_path, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Error creating/accessing NAS directory '{smb_dir_path}': {e}")
        return False

def write_json_to_nas(smb_path: str, data: Any) -> bool:
    """Writes JSON data to a specified file path on the NAS."""
    try:
        dir_path = os.path.dirname(smb_path)
        if not smbclient.path.exists(dir_path):
            smbclient.makedirs(dir_path, exist_ok=True)

        json_string = json.dumps(data, indent=2, default=str)
        with smbclient.open_file(smb_path, mode='w', encoding='utf-8') as f:
            f.write(json_string)
        logger.info(f"Successfully wrote JSON to: {smb_path}")
        return True
    except Exception as e:
        logger.error(f"Error writing JSON to NAS '{smb_path}': {e}")
        return False

def read_json_from_nas(smb_path: str) -> Optional[Any]:
    """Read JSON data from NAS."""
    try:
        with smbclient.open_file(smb_path, mode='r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"File not found: {smb_path}")
        return None
    except Exception as e:
        logger.error(f"Error reading JSON from '{smb_path}': {e}")
        return None

def read_text_from_nas(smb_path: str) -> Optional[str]:
    """Read text file from NAS."""
    try:
        with smbclient.open_file(smb_path, mode='r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error reading text from '{smb_path}': {e}")
        return None

def get_oauth_token():
    """Retrieves an OAuth access token using client credentials flow."""
    logger.info("Requesting OAuth access token...")
    payload = {
        'client_id': OAUTH_CONFIG['client_id'],
        'client_secret': OAUTH_CONFIG['client_secret'],
        'grant_type': 'client_credentials'
    }

    try:
        response = requests.post(OAUTH_CONFIG['token_url'], data=payload)
        response.raise_for_status()
        token_data = response.json()
        access_token = token_data.get('access_token')
        
        if not access_token:
            logger.error("'access_token' not found in OAuth response.")
            return None
            
        logger.info("OAuth token obtained successfully.")
        return access_token
        
    except Exception as e:
        logger.error(f"Failed to get OAuth token: {e}")
        return None

def setup_openai_client() -> Optional[OpenAI]:
    """Sets up the OpenAI client with auth token and SSL configuration."""
    original_requests_ca_bundle = os.environ.get('REQUESTS_CA_BUNDLE')
    original_ssl_cert_file = os.environ.get('SSL_CERT_FILE')
    temp_cert_file_path = None
    
    try:
        # Download CA bundle if needed
        if CA_BUNDLE_FILENAME:
            try:
                # Try the dedicated CA bundle path first
                smb_ca_path = f"//{NAS_PARAMS['ip']}/{NAS_PARAMS['share']}/{CA_BUNDLE_NAS_PATH}/{CA_BUNDLE_FILENAME}"
                if not smbclient.path.exists(smb_ca_path):
                    # Try output path
                    smb_ca_path = f"//{NAS_PARAMS['ip']}/{NAS_PARAMS['share']}/{NAS_OUTPUT_FOLDER_PATH}/{CA_BUNDLE_FILENAME}"
                    if not smbclient.path.exists(smb_ca_path):
                        # Finally try root path
                        smb_ca_path = f"//{NAS_PARAMS['ip']}/{NAS_PARAMS['share']}/{CA_BUNDLE_FILENAME}"
                
                # If any path exists, download the cert
                if smbclient.path.exists(smb_ca_path):
                    with tempfile.NamedTemporaryFile(suffix='.cer', delete=False) as temp_ca_file:
                        temp_cert_file_path = temp_ca_file.name
                        with smbclient.open_file(smb_ca_path, mode='rb') as f_ca:
                            temp_ca_file.write(f_ca.read())
                    logger.info(f"CA bundle downloaded from {smb_ca_path} to temporary file: {temp_cert_file_path}")
                    
                    # Set environment variables for SSL verification
                    os.environ['REQUESTS_CA_BUNDLE'] = temp_cert_file_path
                    os.environ['SSL_CERT_FILE'] = temp_cert_file_path
                    logger.info(f"Set REQUESTS_CA_BUNDLE environment variable to: {temp_cert_file_path}")
                    logger.info(f"Set SSL_CERT_FILE environment variable to: {temp_cert_file_path}")
                else:
                    logger.warning(f"CA bundle not found at any expected paths")
            except Exception as e:
                logger.warning(f"Failed to download CA bundle: {e}")
        
        # Get OAuth token
        access_token = get_oauth_token()
        if not access_token:
            logger.error("Failed to obtain OAuth token.")
            return None
            
        # Set up OpenAI client
        client = OpenAI(
            api_key=access_token,
            base_url=GPT_CONFIG.get('base_url', 'https://api.openai.com/v1')
        )
        
        return client
    except Exception as e:
        logger.error(f"Error setting up OpenAI client: {e}")
        return None
    finally:
        # Clean up the temporary certificate file
        if temp_cert_file_path and os.path.exists(temp_cert_file_path):
            try:
                os.remove(temp_cert_file_path)
                logger.info(f"Removed temporary CA bundle file: {temp_cert_file_path}")
            except Exception as e:
                logger.warning(f"Failed to remove temporary CA bundle file: {e}")
        
        # Restore original environment variables
        if original_requests_ca_bundle is None:
            if 'REQUESTS_CA_BUNDLE' in os.environ:
                del os.environ['REQUESTS_CA_BUNDLE']
                logger.info("Unset REQUESTS_CA_BUNDLE environment variable")
        else:
            os.environ['REQUESTS_CA_BUNDLE'] = original_requests_ca_bundle
            logger.info(f"Restored original REQUESTS_CA_BUNDLE environment variable")
            
        if original_ssl_cert_file is None:
            if 'SSL_CERT_FILE' in os.environ:
                del os.environ['SSL_CERT_FILE']
                logger.info("Unset SSL_CERT_FILE environment variable")
        else:
            os.environ['SSL_CERT_FILE'] = original_ssl_cert_file
            logger.info(f"Restored original SSL_CERT_FILE environment variable")

def count_tokens(text: str, model: str = "gpt-4") -> int:
    """Count tokens in text using tiktoken."""
    try:
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except Exception as e:
        logger.warning(f"Error counting tokens, using approximation: {e}")
        # Rough approximation: 1 token ≈ 4 characters
        return len(text) // 4

# ==============================================================================
# --- Sentence Processing Functions ---
# ==============================================================================

def split_into_sentences(text: str) -> List[str]:
    """
    Split text into sentences using PySBD (Python Sentence Boundary Disambiguation).
    This handles edge cases like abbreviations, decimals, and complex punctuation.
    Returns a list of sentences.
    """
    # Initialize the segmenter with clean=False to preserve original formatting
    segmenter = pysbd.Segmenter(language="en", clean=False)
    
    # Segment the text into sentences
    sentences = segmenter.segment(text)
    
    # Filter out empty sentences and strip whitespace
    cleaned_sentences = [s.strip() for s in sentences if s.strip()]
    
    return cleaned_sentences

def create_indexed_sentences(sentences: List[str]) -> Dict[int, str]:
    """
    Create a dictionary of indexed sentences.
    Returns {1: "First sentence.", 2: "Second sentence.", ...}
    """
    return {i + 1: sentence for i, sentence in enumerate(sentences)}

def format_sentences_for_llm(indexed_sentences: Dict[int, str], start_idx: int, end_idx: int) -> str:
    """Format indexed sentences for LLM input."""
    formatted_lines = []
    for idx in range(start_idx, end_idx + 1):
        if idx in indexed_sentences:
            formatted_lines.append(f"[{idx}] {indexed_sentences[idx]}")
    return "\n".join(formatted_lines)

def collect_sentences_for_batch(
    indexed_sentences: Dict[int, str], 
    start_idx: int, 
    token_limit: int
) -> Tuple[int, str, int]:
    """
    Collect sentences starting from start_idx up to token_limit.
    Returns: (end_idx, formatted_text, token_count)
    """
    current_tokens = 0
    current_idx = start_idx
    batch_sentences = []
    
    while current_idx <= len(indexed_sentences) and current_tokens < token_limit:
        if current_idx in indexed_sentences:
            sentence = indexed_sentences[current_idx]
            sentence_tokens = count_tokens(f"[{current_idx}] {sentence}")
            
            if current_tokens + sentence_tokens > token_limit and batch_sentences:
                # Don't add this sentence if it would exceed limit
                break
                
            batch_sentences.append(f"[{current_idx}] {sentence}")
            current_tokens += sentence_tokens
        
        current_idx += 1
    
    formatted_text = "\n".join(batch_sentences)
    return current_idx - 1, formatted_text, current_tokens

# ==============================================================================
# --- LLM Processing Functions ---
# ==============================================================================

def create_chunking_prompt(
    batch_sentences: str,
    last_chunk_boundary: int,
    target_chunk_size: int,
    sentence_count: int
) -> str:
    """Creates the prompt for the LLM to identify chunk boundaries."""
    
    prompt = f"""You are processing a financial earnings call transcript. Your task is to identify natural breakpoints to create semantic chunks.

CURRENT SENTENCES TO PROCESS:
{batch_sentences}

INSTRUCTIONS:
1. Identify sentence indices where new chunks should start
2. Target chunk size is approximately {target_chunk_size} tokens (roughly 10-15 sentences)
3. Minimum chunk size: {MIN_CHUNK_SIZE} tokens
4. Maximum chunk size: {MAX_CHUNK_SIZE} tokens
5. Create chunks at natural boundaries:
   - Topic changes
   - Speaker transitions
   - Section changes (e.g., from prepared remarks to Q&A)
   - Logical breaks in discussion

IMPORTANT:
- The first chunk starts at sentence [{last_chunk_boundary + 1}]
- Return ONLY the sentence indices where NEW chunks should begin
- Do not include {last_chunk_boundary + 1} in your response
- Each index marks the START of a new chunk

RESPOND WITH JSON:
{{
    "chunk_breaks": [list of sentence indices where new chunks start],
    "reasoning": "Brief explanation of your chunking decisions"
}}

Example: If sentences 47-62 form one chunk and 63-78 form another, return {{"chunk_breaks": [63]}}"""

    return prompt

def create_metadata_prompt(chunks_batch: List[Dict[str, Any]]) -> str:
    """Creates prompt for extracting metadata from chunks."""
    
    chunks_text = ""
    for i, chunk in enumerate(chunks_batch):
        chunks_text += f"\nCHUNK {chunk['chunk_id']} (Sentences {chunk['start_sentence']}-{chunk['end_sentence']}):\n"
        chunks_text += chunk['content']
        chunks_text += "\n" + "-" * 50
    
    prompt = f"""Analyze these transcript chunks and extract structured metadata for each.

{chunks_text}

For EACH chunk, extract:
1. Speaker(s) and their roles (if identifiable)
2. Main topics discussed
3. Key financial metrics with specific values
4. Sentiment/tone of the discussion
5. Important statements or guidance
6. Which other chunks it references or relates to
7. An importance score (1-10) based on financial significance

RESPOND WITH JSON:
{{
    "chunks": [
        {{
            "chunk_id": "chunk_id_here",
            "speakers": [
                {{"name": "Speaker Name or 'Unknown'", "role": "CEO/CFO/Analyst/Unknown"}}
            ],
            "topics": ["topic1", "topic2"],
            "financial_metrics": [
                {{"metric": "Revenue", "value": "$X", "period": "Q1 2023", "context": "up X% YoY"}}
            ],
            "sentiment": "positive/neutral/negative/mixed",
            "key_statements": ["Important quote or guidance"],
            "references_chunks": ["related_chunk_ids"],
            "importance_score": 7,
            "summary": "One sentence summary of this chunk"
        }}
    ]
}}"""

    return prompt

def create_section_grouping_prompt(chunks_batch: List[Dict[str, Any]]) -> str:
    """Creates prompt for grouping chunks into sections."""
    
    chunks_summary = ""
    for chunk in chunks_batch:
        chunks_summary += f"\nChunk {chunk['chunk_id']}:\n"
        chunks_summary += f"Topics: {chunk.get('topics', [])}\n"
        chunks_summary += f"Summary: {chunk.get('summary', 'No summary')}\n"
        chunks_summary += "-" * 30
    
    prompt = f"""Analyze these transcript chunks and identify section boundaries for the earnings call.

{chunks_summary}

Earnings calls typically have these sections:
- Introduction/Opening Remarks
- Financial Results Overview
- Business Segment Performance
- Guidance and Outlook
- Q&A Session
- Closing Remarks

Identify where sections begin based on:
1. Major topic shifts
2. Transition phrases ("Now turning to...", "Let's move to Q&A", etc.)
3. Speaker patterns (CEO to CFO handoff, Operator introducing Q&A)
4. Content type changes (results to outlook, prepared remarks to Q&A)

RESPOND WITH JSON:
{{
    "sections": [
        {{
            "start_chunk_id": "chunk_001",
            "end_chunk_id": "chunk_005",
            "section_type": "Introduction",
            "section_name": "Q1 2023 Opening Remarks",
            "reasoning": "Why this is a distinct section"
        }}
    ]
}}"""

    return prompt

def process_with_llm(client: OpenAI, prompt: str, temperature: float = 0.1) -> Optional[Dict[str, Any]]:
    """Sends prompt to LLM and returns parsed JSON response."""
    try:
        response = client.chat.completions.create(
            model=GPT_CONFIG['model_name'],
            messages=[
                {"role": "system", "content": "You are an expert at analyzing financial transcripts. Always respond with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            response_format={"type": "json_object"}
        )
        
        response_text = response.choices[0].message.content
        return json.loads(response_text)
        
    except Exception as e:
        logger.error(f"Error processing with LLM: {e}")
        return None

# ==============================================================================
# --- Phase 1: Smart Chunking ---
# ==============================================================================

def phase1_smart_chunking(
    indexed_sentences: Dict[int, str],
    client: OpenAI
) -> List[Dict[str, Any]]:
    """
    Phase 1: Use LLM to identify chunk boundaries.
    Returns list of chunks with sentence ranges.
    """
    chunks = []
    last_chunk_boundary = 0
    total_sentences = len(indexed_sentences)
    
    logger.info(f"Starting Phase 1: Smart chunking of {total_sentences} sentences")
    
    while last_chunk_boundary < total_sentences:
        # Collect sentences for this batch
        batch_end_idx, batch_text, token_count = collect_sentences_for_batch(
            indexed_sentences,
            last_chunk_boundary + 1,
            BATCH_TOKEN_LIMIT
        )
        
        if batch_end_idx <= last_chunk_boundary:
            # No more sentences to process
            break
            
        logger.info(f"Processing batch: sentences {last_chunk_boundary + 1} to {batch_end_idx} ({token_count} tokens)")
        
        # Get chunk boundaries from LLM
        prompt = create_chunking_prompt(
            batch_text,
            last_chunk_boundary,
            TARGET_CHUNK_SIZE,
            batch_end_idx - last_chunk_boundary
        )
        
        response = process_with_llm(client, prompt)
        
        if response and 'chunk_breaks' in response:
            chunk_breaks = response['chunk_breaks']
            logger.info(f"LLM identified chunk breaks at: {chunk_breaks}")
            
            # Process the chunk breaks
            current_start = last_chunk_boundary + 1
            
            for break_idx in chunk_breaks:
                if break_idx > current_start and break_idx <= batch_end_idx:
                    # Create chunk from current_start to break_idx - 1
                    chunks.append({
                        'start_sentence': current_start,
                        'end_sentence': break_idx - 1
                    })
                    current_start = break_idx
            
            # Update last_chunk_boundary to the last break point
            if chunk_breaks and chunk_breaks[-1] <= batch_end_idx:
                last_chunk_boundary = chunk_breaks[-1] - 1
            else:
                # If no valid breaks, use the end of this batch
                last_chunk_boundary = batch_end_idx
        else:
            logger.warning("LLM did not return valid chunk breaks, using batch boundary")
            # Create a chunk for this entire batch
            chunks.append({
                'start_sentence': last_chunk_boundary + 1,
                'end_sentence': batch_end_idx
            })
            last_chunk_boundary = batch_end_idx
    
    # Don't forget the final chunk
    if last_chunk_boundary < total_sentences:
        chunks.append({
            'start_sentence': last_chunk_boundary + 1,
            'end_sentence': total_sentences
        })
    
    # Add chunk IDs and content
    for i, chunk in enumerate(chunks):
        chunk['chunk_id'] = f"chunk_{i+1:03d}"
        # Combine sentences for this chunk
        sentences = []
        for idx in range(chunk['start_sentence'], chunk['end_sentence'] + 1):
            if idx in indexed_sentences:
                sentences.append(indexed_sentences[idx])
        chunk['content'] = " ".join(sentences)
        chunk['token_count'] = count_tokens(chunk['content'])
    
    logger.info(f"Phase 1 complete: Created {len(chunks)} chunks")
    return chunks

# ==============================================================================
# --- Phase 2: Metadata Extraction ---
# ==============================================================================

def phase2_metadata_extraction(
    chunks: List[Dict[str, Any]],
    client: OpenAI
) -> List[Dict[str, Any]]:
    """
    Phase 2: Extract metadata for chunks using LLM.
    Returns chunks with added metadata.
    """
    logger.info(f"Starting Phase 2: Metadata extraction for {len(chunks)} chunks")
    
    # Process chunks in batches
    for i in range(0, len(chunks), METADATA_BATCH_SIZE):
        batch = chunks[i:i + METADATA_BATCH_SIZE]
        logger.info(f"Processing metadata batch: chunks {i+1} to {min(i+METADATA_BATCH_SIZE, len(chunks))}")
        
        prompt = create_metadata_prompt(batch)
        response = process_with_llm(client, prompt, temperature=0.2)
        
        if response and 'chunks' in response:
            # Match metadata to chunks
            for chunk_metadata in response['chunks']:
                chunk_id = chunk_metadata.get('chunk_id')
                # Find the matching chunk
                for chunk in batch:
                    if chunk['chunk_id'] == chunk_id:
                        # Add metadata to chunk
                        chunk['speakers'] = chunk_metadata.get('speakers', [])
                        chunk['topics'] = chunk_metadata.get('topics', [])
                        chunk['financial_metrics'] = chunk_metadata.get('financial_metrics', [])
                        chunk['sentiment'] = chunk_metadata.get('sentiment', 'neutral')
                        chunk['key_statements'] = chunk_metadata.get('key_statements', [])
                        chunk['references_chunks'] = chunk_metadata.get('references_chunks', [])
                        chunk['importance_score'] = chunk_metadata.get('importance_score', 5)
                        chunk['summary'] = chunk_metadata.get('summary', '')
                        break
        else:
            logger.warning(f"Failed to extract metadata for batch starting at chunk {i+1}")
    
    logger.info("Phase 2 complete: Metadata extraction finished")
    return chunks

# ==============================================================================
# --- Phase 3: Section Grouping ---
# ==============================================================================

def phase3_section_grouping(
    chunks: List[Dict[str, Any]],
    client: OpenAI,
    metadata: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Phase 3: Group chunks into sections.
    Returns (updated_chunks, sections)
    """
    logger.info(f"Starting Phase 3: Section grouping for {len(chunks)} chunks")
    
    sections = []
    
    # Process chunks to identify section boundaries
    for i in range(0, len(chunks), SECTION_BATCH_SIZE):
        batch = chunks[i:i + SECTION_BATCH_SIZE * 2]  # Get overlapping context
        logger.info(f"Processing section batch starting at chunk {i+1}")
        
        prompt = create_section_grouping_prompt(batch)
        response = process_with_llm(client, prompt, temperature=0.2)
        
        if response and 'sections' in response:
            for section_info in response['sections']:
                # Create section entry
                section_id = f"{metadata['transcript_id']}_S{len(sections)+1:03d}"
                
                # Find chunks in this section
                section_chunks = []
                for chunk in chunks:
                    if (chunk['chunk_id'] >= section_info['start_chunk_id'] and 
                        chunk['chunk_id'] <= section_info['end_chunk_id']):
                        section_chunks.append(chunk)
                
                if section_chunks:
                    section = {
                        'section_id': section_id,
                        'section_type': section_info['section_type'],
                        'section_name': section_info['section_name'],
                        'section_content': " ".join([c['content'] for c in section_chunks]),
                        'chunk_ids': [c['chunk_id'] for c in section_chunks],
                        'start_sentence': section_chunks[0]['start_sentence'],
                        'end_sentence': section_chunks[-1]['end_sentence'],
                        **metadata
                    }
                    
                    # Generate section summary
                    section['section_summary'] = section_chunks[0].get('summary', '') if section_chunks else ''
                    
                    sections.append(section)
    
    # Update chunks with section information
    for section in sections:
        for i, chunk_id in enumerate(section['chunk_ids']):
            for chunk in chunks:
                if chunk['chunk_id'] == chunk_id:
                    chunk['section_id'] = section['section_id']
                    chunk['section_name'] = section['section_name']
                    chunk['section_type'] = section['section_type']
                    chunk['section_summary'] = section['section_summary']
                    chunk['section_order'] = i + 1
                    break
    
    logger.info(f"Phase 3 complete: Created {len(sections)} sections")
    return chunks, sections

# ==============================================================================
# --- Main Processing Function ---
# ==============================================================================

def process_transcript(
    markdown_content: str,
    client: OpenAI,
    file_metadata: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    """
    Process a transcript through all phases.
    Returns (chunks, sections, processing_metadata)
    """
    start_time = time.time()
    
    # Split into sentences
    logger.info("Splitting text into sentences...")
    sentences = split_into_sentences(markdown_content)
    indexed_sentences = create_indexed_sentences(sentences)
    logger.info(f"Created {len(indexed_sentences)} indexed sentences")
    
    # Phase 1: Smart chunking
    chunks = phase1_smart_chunking(indexed_sentences, client)
    
    # Add file metadata to each chunk
    for chunk in chunks:
        chunk.update(file_metadata)
    
    # Phase 2: Metadata extraction
    chunks = phase2_metadata_extraction(chunks, client)
    
    # Phase 3: Section grouping
    chunks, sections = phase3_section_grouping(chunks, client, file_metadata)
    
    # Generate embeddings (placeholder - would need embedding model)
    for chunk in chunks:
        chunk['embedding'] = [0.0] * 1536  # Placeholder embedding
        chunk['section_token_count'] = chunk.get('token_count', 0)
        chunk['section_importance_score'] = chunk.get('importance_score', 5) / 10.0
    
    # Create processing metadata
    processing_metadata = {
        'total_sentences': len(sentences),
        'total_chunks': len(chunks),
        'total_sections': len(sections),
        'total_tokens': sum(chunk.get('token_count', 0) for chunk in chunks),
        'processing_time': time.time() - start_time,
        'processing_timestamp': datetime.now(timezone.utc).isoformat(),
        'model_used': GPT_CONFIG['model_name'],
        'chunking_parameters': {
            'target_chunk_size': TARGET_CHUNK_SIZE,
            'min_chunk_size': MIN_CHUNK_SIZE,
            'max_chunk_size': MAX_CHUNK_SIZE,
            'batch_token_limit': BATCH_TOKEN_LIMIT
        }
    }
    
    return chunks, sections, processing_metadata

# ==============================================================================
# --- Main Execution Logic ---
# ==============================================================================

def main():
    logger.info("=" * 60)
    logger.info("Running Stage 3: Generate Chunks with Sentence-Based Chunking")
    logger.info(f"Document Source: {DOCUMENT_SOURCE}")
    logger.info("=" * 60)
    
    # Initialize clients
    if not initialize_smb_client():
        logger.error("Failed to initialize SMB client. Exiting.")
        sys.exit(1)
    
    openai_client = setup_openai_client()
    if not openai_client:
        logger.error("Failed to set up OpenAI client. Exiting.")
        sys.exit(1)
    
    # Define paths
    stage1_output_dir = os.path.join(NAS_OUTPUT_FOLDER_PATH, DOCUMENT_SOURCE).replace('\\', '/')
    stage1_output_dir_smb = f"//{NAS_PARAMS['ip']}/{NAS_PARAMS['share']}/{stage1_output_dir}"
    stage2_output_dir_smb = os.path.join(stage1_output_dir_smb, '2A_processed_files').replace('\\', '/')
    stage3_output_dir_smb = os.path.join(stage1_output_dir_smb, '3_transcript_chunks').replace('\\', '/')
    
    # Create output directory
    create_nas_directory(stage3_output_dir_smb)
    
    # Check for skip flag
    skip_flag_path = os.path.join(stage1_output_dir_smb, '_SKIP_SUBSEQUENT_STAGES.flag').replace('\\', '/')
    try:
        if smbclient.path.exists(skip_flag_path):
            logger.info("Skip flag found. No files to process.")
            return
    except Exception as e:
        logger.warning(f"Error checking skip flag: {e}")
    
    # Load files to process
    files_json_path = os.path.join(stage1_output_dir_smb, '1C_nas_files_to_process.json').replace('\\', '/')
    files_to_process = read_json_from_nas(files_json_path)
    
    if not files_to_process:
        logger.error("No files to process or error loading file list.")
        return
    
    logger.info(f"Found {len(files_to_process)} files to process")
    
    # Filter for test mode if enabled
    if TEST_MODE:
        if TEST_TRANSCRIPT_ID:
            files_to_process = [f for f in files_to_process if TEST_TRANSCRIPT_ID in f.get('file_name', '')]
        else:
            files_to_process = files_to_process[:1]
        logger.info(f"TEST MODE: Processing only {len(files_to_process)} file(s)")
    
    # Process each file
    all_transcripts_metadata = []
    
    for idx, file_info in enumerate(files_to_process):
        try:
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing file {idx + 1}/{len(files_to_process)}: {file_info['file_name']}")
            logger.info(f"{'='*60}")
            
            # Build path to markdown file from Stage 2
            file_base_name = os.path.splitext(file_info['file_name'])[0]
            markdown_path = os.path.join(
                stage2_output_dir_smb,
                file_base_name,
                f"{file_base_name}.md"
            ).replace('\\', '/')
            
            # Read markdown content
            markdown_content = read_text_from_nas(markdown_path)
            if not markdown_content:
                logger.error(f"Failed to read markdown file: {markdown_path}")
                continue
            
            # Prepare metadata
            file_metadata = {
                'document_source': DOCUMENT_SOURCE,
                'document_type': DOCUMENT_TYPE,
                'document_language': DOCUMENT_LANGUAGE,
                'bank_name': file_info['bank_name'],
                'fiscal_year': file_info['fiscal_year'],
                'fiscal_quarter': file_info['fiscal_quarter'],
                'document_name': file_info.get('document_name', f"Q{file_info['fiscal_quarter']} {file_info['fiscal_year']} Earnings Call"),
                'file_name': file_info['file_name'],
                'file_path': file_info['file_path'],
                'file_size': file_info['file_size'],
                'date_last_modified': file_info['date_last_modified'],
                'date_created': datetime.now(timezone.utc).isoformat(),
                'date_processed': datetime.now(timezone.utc).isoformat()
            }
            
            # Create transcript ID
            transcript_id = f"{file_metadata['bank_name'].replace(' ', '_')}_{file_metadata['fiscal_year']}_Q{file_metadata['fiscal_quarter']}"
            file_metadata['transcript_id'] = transcript_id
            
            # Process transcript
            chunks, sections, processing_metadata = process_transcript(
                markdown_content,
                openai_client,
                file_metadata
            )
            
            # Create transcript output directory
            transcript_dir = os.path.join(stage3_output_dir_smb, transcript_id).replace('\\', '/')
            create_nas_directory(transcript_dir)
            
            # Save indexed sentences
            sentences_path = os.path.join(transcript_dir, f"2A_transcript_sentences_{transcript_id}.json").replace('\\', '/')
            sentences = split_into_sentences(markdown_content)
            indexed_sentences = create_indexed_sentences(sentences)
            sentence_data = {
                "transcript_id": transcript_id,
                "metadata": file_metadata,
                "sentences": [
                    {"sentence_id": i, "text": text, "position": i}
                    for i, text in indexed_sentences.items()
                ]
            }
            write_json_to_nas(sentences_path, sentence_data)
            
            # Save metadata
            metadata_path = os.path.join(transcript_dir, f"2B_transcript_metadata_{transcript_id}.json").replace('\\', '/')
            write_json_to_nas(metadata_path, {**file_metadata, **processing_metadata})
            
            # Save chunks
            chunks_path = os.path.join(transcript_dir, f"3A_transcript_chunks_{transcript_id}.json").replace('\\', '/')
            write_json_to_nas(chunks_path, chunks)
            
            # Save sections
            sections_path = os.path.join(transcript_dir, f"3B_transcript_sections_{transcript_id}.json").replace('\\', '/')
            write_json_to_nas(sections_path, sections)
            
            # Add to overall metadata
            all_transcripts_metadata.append({
                **file_metadata,
                **processing_metadata,
                'chunks_file': chunks_path,
                'sections_file': sections_path,
                'status': 'completed'
            })
            
            logger.info(f"Successfully processed {file_info['file_name']} into {len(chunks)} chunks and {len(sections)} sections")
            
        except Exception as e:
            logger.error(f"Error processing {file_info.get('file_name', 'unknown')}: {e}")
            all_transcripts_metadata.append({
                **file_info,
                'status': 'failed',
                'error': str(e),
                'date_processed': datetime.now(timezone.utc).isoformat()
            })
    
    # Save overall processing summary
    summary_path = os.path.join(stage3_output_dir_smb, '3_processing_summary.json').replace('\\', '/')
    write_json_to_nas(summary_path, {
        'stage': 'stage3_generate_chunks',
        'processed_count': len([m for m in all_transcripts_metadata if m.get('status') == 'completed']),
        'failed_count': len([m for m in all_transcripts_metadata if m.get('status') == 'failed']),
        'total_files': len(files_to_process),
        'processing_timestamp': datetime.now(timezone.utc).isoformat(),
        'transcripts': all_transcripts_metadata
    })
    
    logger.info("=" * 60)
    logger.info("Stage 3 completed successfully!")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()