# -*- coding: utf-8 -*-
"""
Stage 3: Generate Transcript Chunks using LLM

This script processes transcript files from Stage 2.
For each transcript, it:
1. Uses LLM to parse the transcript into structured sentences with speakers
2. Uses LLM to determine semantic chunk boundaries
3. Groups chunks into sections
4. Creates structured output for database insertion

Features:
- TEST_MODE configuration to process only one transcript
- LLM-only extraction (no regex patterns)
- Sliding window approach for chunking
- Batch embedding generation
"""

import os
import sys
import json
import time
import tempfile
import requests
import smbclient
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from openai import OpenAI

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

# --- NAS Configuration ---
# Network attached storage connection parameters
NAS_PARAMS = {
    "ip": "your_nas_ip",
    "share": "your_share_name",
    "user": "your_nas_user",
    "password": "your_nas_password"
}

# Base path on the NAS share where Stage 1/2 output files were stored
NAS_OUTPUT_FOLDER_PATH = "path/to/your/output_folder"

# --- Processing Configuration ---
# Document source identifier for earnings call transcripts
DOCUMENT_SOURCE = 'earnings_call'
DOCUMENT_TYPE = 'transcript'
DOCUMENT_LANGUAGE = 'en'

# --- OAuth Configuration ---
OAUTH_CONFIG = {
    "token_url": "YOUR_OAUTH_TOKEN_ENDPOINT_URL",
    "client_id": "YOUR_CLIENT_ID",
    "client_secret": "YOUR_CLIENT_SECRET",
    "scope": "api://YourResource/.default"
}

# --- GPT API Configuration ---
GPT_CONFIG = {
    "base_url": "YOUR_CUSTOM_GPT_API_BASE_URL",
    "model_name": "gpt-4o",
    "api_version": "2024-02-01"
}

# --- CA Bundle for SSL ---
CA_BUNDLE_FILENAME = 'rbc-ca-bundle.cer'
CA_BUNDLE_NAS_PATH = 'certs'

# --- Chunking Configuration ---
# Number of previous chunks to include in context
PREVIOUS_CHUNKS_CONTEXT = 20
# Number of future sentences to include in context
FUTURE_SENTENCES_CONTEXT = 19
# Maximum tokens per chunk (approximate)
MAX_CHUNK_TOKENS = 500

# --- Embedding Configuration ---
EMBEDDING_MODEL = "text-embedding-3-large"
EMBEDDING_DIMENSION = 2000
EMBEDDING_BATCH_SIZE = 50

# --- Section Types ---
SECTION_TYPES = [
    "Introduction",
    "Financial Results",
    "Business Segment Performance",
    "Risk Management",
    "Capital Management",
    "Guidance and Outlook",
    "Q&A Session",
    "Closing Remarks",
    "Other"
]

# ==============================================================================
# --- Helper Functions ---
# ==============================================================================

def create_nas_directory(smb_path: str) -> bool:
    """Create a directory on NAS if it doesn't exist."""
    try:
        smbclient.makedirs(smb_path, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Error creating directory '{smb_path}': {e}")
        return False

def write_json_to_nas(smb_path: str, data: Any) -> bool:
    """Write JSON data to NAS."""
    try:
        json_string = json.dumps(data, indent=2, ensure_ascii=False)
        with smbclient.open_file(smb_path, mode='w', encoding='utf-8') as f:
            f.write(json_string)
        return True
    except Exception as e:
        logger.error(f"Error writing JSON to '{smb_path}': {e}")
        return False

def read_json_from_nas(smb_path: str) -> Optional[Any]:
    """Read JSON data from NAS."""
    try:
        with smbclient.open_file(smb_path, mode='r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
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

def extract_transcript_metadata(content: str, file_info: Dict) -> Dict:
    """Extract metadata from transcript content and file info."""
    metadata = {
        "document_source": DOCUMENT_SOURCE,
        "document_type": DOCUMENT_TYPE,
        "document_language": DOCUMENT_LANGUAGE,
        "bank_name": file_info.get("bank_name", ""),
        "fiscal_year": file_info.get("fiscal_year", ""),
        "fiscal_quarter": file_info.get("fiscal_quarter", ""),
        "file_name": file_info.get("file_name", ""),
        "file_path": file_info.get("file_path", ""),
        "date_last_modified": file_info.get("date_last_modified", "")
    }
    
    # Create document name
    metadata["document_name"] = f"{metadata['bank_name']} Q{metadata['fiscal_quarter']} {metadata['fiscal_year']} Earnings Call"
    
    # Create transcript ID
    metadata["transcript_id"] = f"{metadata['bank_name'].replace(' ', '_')}_{metadata['fiscal_year']}_Q{metadata['fiscal_quarter']}"
    
    return metadata

# ==============================================================================
# --- OAuth and OpenAI Client Functions ---
# ==============================================================================

def get_oauth_token() -> Optional[str]:
    """Obtain OAuth token using client credentials flow."""
    try:
        response = requests.post(
            OAUTH_CONFIG["token_url"],
            data={
                "grant_type": "client_credentials",
                "client_id": OAUTH_CONFIG["client_id"],
                "client_secret": OAUTH_CONFIG["client_secret"],
                "scope": OAUTH_CONFIG["scope"]
            }
        )
        response.raise_for_status()
        return response.json()["access_token"]
    except Exception as e:
        logger.error(f"Failed to obtain OAuth token: {e}")
        return None

def setup_openai_client() -> Optional[OpenAI]:
    """Set up OpenAI client with OAuth authentication."""
    token = get_oauth_token()
    if not token:
        return None
    
    # Download CA bundle if needed
    ca_bundle_local_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.cer') as tmp_file:
            ca_bundle_local_path = tmp_file.name
            smb_ca_path = f"//{NAS_PARAMS['ip']}/{NAS_PARAMS['share']}/{CA_BUNDLE_NAS_PATH}/{CA_BUNDLE_FILENAME}"
            
            with smbclient.open_file(smb_ca_path, mode='rb') as src:
                tmp_file.write(src.read())
    except Exception as e:
        logger.error(f"Failed to download CA bundle: {e}")
        return None
    
    # Create OpenAI client
    client = OpenAI(
        api_key=token,
        base_url=GPT_CONFIG["base_url"],
        default_headers={
            "Authorization": f"Bearer {token}",
            "api-version": GPT_CONFIG["api_version"]
        },
        http_client=None  # Will be configured with CA bundle
    )
    
    # Set up SSL verification
    if ca_bundle_local_path:
        import httpx
        client._client = httpx.Client(
            verify=ca_bundle_local_path,
            timeout=httpx.Timeout(timeout=600.0)
        )
    
    return client

# ==============================================================================
# --- LLM-based Parsing Functions ---
# ==============================================================================

def parse_transcript_to_sentences(client: OpenAI, content: str) -> List[Dict]:
    """Use LLM to parse transcript into sentences with speaker identification."""
    
    # Split content into manageable chunks for LLM processing
    max_content_length = 8000  # Approximate token limit
    content_chunks = []
    
    if len(content) > max_content_length:
        # Split at paragraph boundaries
        paragraphs = content.split('\n\n')
        current_chunk = ""
        
        for para in paragraphs:
            if len(current_chunk) + len(para) > max_content_length:
                if current_chunk:
                    content_chunks.append(current_chunk)
                current_chunk = para
            else:
                current_chunk += "\n\n" + para if current_chunk else para
        
        if current_chunk:
            content_chunks.append(current_chunk)
    else:
        content_chunks = [content]
    
    all_sentences = []
    sentence_id = 1
    
    for chunk_idx, chunk in enumerate(content_chunks):
        prompt = f"""
You are parsing an earnings call transcript. Extract individual sentences with their speakers.

Transcript content:
{chunk}

Parse this transcript and identify:
1. Individual sentences (complete thoughts, even if split across lines)
2. The speaker for each sentence (identify from context, speaker labels, or patterns)
3. Maintain the exact text of each sentence

Return JSON in this format:
{{
    "sentences": [
        {{
            "sentence_id": 1,
            "text": "Exact sentence text",
            "speaker": "Speaker Name",
            "speaker_title": "Optional Title"
        }}
    ]
}}

Important:
- Each sentence should be a complete thought
- Preserve the exact wording
- Identify speakers from context (e.g., "John Smith:", "[CEO]", etc.)
- If speaker changes mid-paragraph, split appropriately
- If no speaker is identifiable, use "Unknown"
"""
        
        try:
            response = client.chat.completions.create(
                model=GPT_CONFIG["model_name"],
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Add to overall sentence list with continuous numbering
            for sent in result.get("sentences", []):
                all_sentences.append({
                    "sentence_id": sentence_id,
                    "text": sent["text"],
                    "position": sentence_id,
                    "speaker": sent.get("speaker", "Unknown"),
                    "speaker_title": sent.get("speaker_title", "")
                })
                sentence_id += 1
                
        except Exception as e:
            logger.error(f"Error parsing chunk {chunk_idx}: {e}")
            # Fallback: treat the whole chunk as one sentence
            all_sentences.append({
                "sentence_id": sentence_id,
                "text": chunk.strip(),
                "position": sentence_id,
                "speaker": "Unknown",
                "speaker_title": ""
            })
            sentence_id += 1
    
    return all_sentences

# ==============================================================================
# --- Chunking Functions ---
# ==============================================================================

def should_add_to_chunk(
    client: OpenAI,
    previous_chunks: List[Dict],
    current_chunk: Dict,
    active_sentence: Dict,
    future_sentences: List[Dict]
) -> Dict:
    """Use LLM to decide if sentence should be added to current chunk."""
    
    # Prepare context
    context = {
        "previous_chunks": [
            {
                "chunk_id": c["chunk_id"],
                "summary": " ".join(c["content"].split()[:50]) + "..." if len(c["content"].split()) > 50 else c["content"]
            }
            for c in previous_chunks[-PREVIOUS_CHUNKS_CONTEXT:]
        ],
        "current_chunk": {
            "sentences": current_chunk["sentences"],
            "content": current_chunk["content"]
        },
        "active_sentence": {
            "sentence_id": active_sentence["sentence_id"],
            "text": active_sentence["text"],
            "speaker": active_sentence["speaker"]
        },
        "future_sentences": [
            {
                "sentence_id": s["sentence_id"],
                "text": s["text"],
                "speaker": s["speaker"]
            }
            for s in future_sentences[:FUTURE_SENTENCES_CONTEXT]
        ]
    }
    
    prompt = f"""
You are analyzing an earnings call transcript to determine semantic chunk boundaries.

Context:
{json.dumps(context, indent=2)}

Question: Should the active sentence be added to the current chunk, or should it start a new chunk?

Consider:
1. Topic continuity - Does the sentence continue the same topic?
2. Speaker changes - Is there a change in speaker that indicates a new section?
3. Semantic completeness - Would adding this sentence make the chunk too long or unfocused?
4. Natural boundaries - Does this sentence start a new question, answer, or topic?

Respond with JSON:
{{
    "add_to_chunk": true/false,
    "reasoning": "Brief explanation of your decision",
    "related_chunks": [list of previous chunk IDs that are semantically related],
    "additional_context": [
        {{"context": "Relevant context from previous discussion", "source": "sentence_id_value"}}
    ]
}}
"""
    
    try:
        response = client.chat.completions.create(
            model=GPT_CONFIG["model_name"],
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        logger.error(f"Error in LLM chunking decision: {e}")
        # Default to adding to current chunk if error
        return {
            "add_to_chunk": True,
            "reasoning": "Error in LLM processing, defaulting to continue chunk",
            "related_chunks": [],
            "additional_context": []
        }

def generate_chunk_metadata(client: OpenAI, chunk: Dict) -> Dict:
    """Generate metadata for a chunk using LLM."""
    
    prompt = f"""
Analyze this earnings call transcript chunk and extract metadata.

Chunk content:
{chunk["content"]}

Speaker information: {chunk.get("speakers", [])}

Extract the following metadata:
1. Primary speaker (if multiple, the main one)
2. Key tags (3-5 keywords/phrases)
3. Main topics (2-3 thematic topics)

Respond with JSON:
{{
    "chunk_speaker": "Primary speaker name",
    "chunk_tags": ["tag1", "tag2", "tag3"],
    "chunk_topics": ["topic1", "topic2"]
}}
"""
    
    try:
        response = client.chat.completions.create(
            model=GPT_CONFIG["model_name"],
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        logger.error(f"Error generating chunk metadata: {e}")
        return {
            "chunk_speaker": chunk.get("speakers", ["Unknown"])[0] if chunk.get("speakers") else "Unknown",
            "chunk_tags": [],
            "chunk_topics": []
        }

def generate_embeddings_batch(client: OpenAI, texts: List[str]) -> List[List[float]]:
    """Generate embeddings for multiple texts in batches."""
    all_embeddings = []
    
    # Process in batches
    for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[i:i + EMBEDDING_BATCH_SIZE]
        
        try:
            response = client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=batch,
                dimensions=EMBEDDING_DIMENSION
            )
            
            # Extract embeddings in order
            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)
            
        except Exception as e:
            logger.error(f"Error generating embeddings for batch {i//EMBEDDING_BATCH_SIZE}: {e}")
            # Return zero vectors for failed batch
            all_embeddings.extend([[0.0] * EMBEDDING_DIMENSION] * len(batch))
    
    return all_embeddings

def process_transcript_to_chunks(
    client: OpenAI,
    sentences: List[Dict],
    metadata: Dict
) -> List[Dict]:
    """Process sentences into semantic chunks."""
    
    chunks = []
    current_chunk = None
    chunk_counter = 1
    
    for i, sentence in enumerate(sentences):
        if current_chunk is None:
            # Start first chunk
            current_chunk = {
                "chunk_id": f"{metadata['transcript_id']}_C{chunk_counter:03d}",
                "sentences": [sentence["sentence_id"]],
                "content": sentence["text"],
                "speakers": [sentence["speaker"]] if sentence["speaker"] != "Unknown" else [],
                "related_chunks": [],
                "additional_context": []
            }
        else:
            # Get future sentences for context
            future_sentences = sentences[i+1:i+1+FUTURE_SENTENCES_CONTEXT]
            
            # Ask LLM if sentence should be added to current chunk
            decision = should_add_to_chunk(
                client,
                chunks,
                current_chunk,
                sentence,
                future_sentences
            )
            
            if decision["add_to_chunk"]:
                # Add to current chunk
                current_chunk["sentences"].append(sentence["sentence_id"])
                current_chunk["content"] += " " + sentence["text"]
                if sentence["speaker"] != "Unknown" and sentence["speaker"] not in current_chunk["speakers"]:
                    current_chunk["speakers"].append(sentence["speaker"])
                
                # Add any related chunks or context
                current_chunk["related_chunks"].extend(decision.get("related_chunks", []))
                current_chunk["additional_context"].extend(decision.get("additional_context", []))
            else:
                # Finalize current chunk
                chunk_metadata = generate_chunk_metadata(client, current_chunk)
                current_chunk.update(chunk_metadata)
                current_chunk.update(metadata)  # Add transcript metadata
                chunks.append(current_chunk)
                
                # Start new chunk
                chunk_counter += 1
                current_chunk = {
                    "chunk_id": f"{metadata['transcript_id']}_C{chunk_counter:03d}",
                    "sentences": [sentence["sentence_id"]],
                    "content": sentence["text"],
                    "speakers": [sentence["speaker"]] if sentence["speaker"] != "Unknown" else [],
                    "related_chunks": decision.get("related_chunks", []),
                    "additional_context": decision.get("additional_context", [])
                }
    
    # Don't forget the last chunk
    if current_chunk and current_chunk["sentences"]:
        chunk_metadata = generate_chunk_metadata(client, current_chunk)
        current_chunk.update(chunk_metadata)
        current_chunk.update(metadata)
        chunks.append(current_chunk)
    
    # Generate embeddings for all chunks in batch
    logger.info(f"Generating embeddings for {len(chunks)} chunks...")
    chunk_texts = [chunk["content"] for chunk in chunks]
    embeddings = generate_embeddings_batch(client, chunk_texts)
    
    # Add embeddings to chunks
    for i, chunk in enumerate(chunks):
        chunk["embedding"] = embeddings[i]
        # Add additional fields required for database
        chunk["section_importance_score"] = 1.0  # Default score, can be computed later
        chunk["section_token_count"] = len(chunk["content"].split())  # Approximate
    
    return chunks

# ==============================================================================
# --- Section Grouping Functions ---
# ==============================================================================

def should_start_new_section(
    client: OpenAI,
    current_section_chunks: List[Dict],
    next_chunk: Dict,
    previous_sections: List[Dict]
) -> Tuple[bool, str, str]:
    """Determine if chunk should start a new section."""
    
    context = {
        "current_section": {
            "chunks": [c["chunk_id"] for c in current_section_chunks],
            "content_summary": " ".join([c["content"] for c in current_section_chunks[-3:]])[:500] + "..."
        },
        "next_chunk": {
            "chunk_id": next_chunk["chunk_id"],
            "content": next_chunk["content"],
            "speaker": next_chunk.get("chunk_speaker", "Unknown"),
            "topics": next_chunk.get("chunk_topics", [])
        },
        "previous_sections": [
            {
                "section_name": s["section_name"],
                "section_type": s["section_type"]
            }
            for s in previous_sections[-5:]
        ]
    }
    
    prompt = f"""
You are analyzing an earnings call transcript to identify section boundaries.

Context:
{json.dumps(context, indent=2)}

Available section types: {SECTION_TYPES}

Question: Should the next chunk start a new section?

Consider:
1. Major topic shifts
2. Transition phrases (e.g., "Now let's turn to...", "Moving on to Q&A...")
3. Speaker changes that indicate new segments
4. Natural sections of an earnings call

Respond with JSON:
{{
    "start_new_section": true/false,
    "section_type": "One of the available section types",
    "section_name": "Specific descriptive name for this section",
    "reasoning": "Brief explanation"
}}
"""
    
    try:
        response = client.chat.completions.create(
            model=GPT_CONFIG["model_name"],
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        return (
            result["start_new_section"],
            result["section_type"],
            result["section_name"]
        )
    except Exception as e:
        logger.error(f"Error in section boundary detection: {e}")
        return False, "Other", "Unnamed Section"

def generate_section_summary(client: OpenAI, chunks: List[Dict], section_type: str, section_name: str) -> str:
    """Generate a summary for a section."""
    
    combined_content = " ".join([c["content"] for c in chunks])
    
    prompt = f"""
Generate a concise summary for this section of an earnings call transcript.

Section Type: {section_type}
Section Name: {section_name}

Content (first 2000 chars):
{combined_content[:2000]}...

Provide a 2-3 sentence summary that captures the key points and main takeaways from this section.
Focus on specific numbers, guidance, and important statements.
"""
    
    try:
        response = client.chat.completions.create(
            model=GPT_CONFIG["model_name"],
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Error generating section summary: {e}")
        return f"Summary generation failed for {section_name}"

def group_chunks_into_sections(client: OpenAI, chunks: List[Dict], metadata: Dict) -> List[Dict]:
    """Group chunks into coherent sections."""
    
    sections = []
    current_section_chunks = []
    section_counter = 1
    
    # Initialize with first chunk
    current_section_type = "Introduction"
    current_section_name = f"{metadata['bank_name']} Q{metadata['fiscal_quarter']} {metadata['fiscal_year']} Opening Remarks"
    
    for i, chunk in enumerate(chunks):
        if not current_section_chunks:
            current_section_chunks.append(chunk)
        else:
            should_start_new, new_type, new_name = should_start_new_section(
                client,
                current_section_chunks,
                chunk,
                sections
            )
            
            if should_start_new:
                # Finalize current section
                section = {
                    "section_id": f"{metadata['transcript_id']}_S{section_counter:03d}",
                    "section_type": current_section_type,
                    "section_name": current_section_name,
                    "section_summary": generate_section_summary(client, current_section_chunks, current_section_type, current_section_name),
                    "section_content": " ".join([c["content"] for c in current_section_chunks]),
                    "chunk_ids": [c["chunk_id"] for c in current_section_chunks]
                }
                section.update(metadata)
                sections.append(section)
                
                # Start new section
                section_counter += 1
                current_section_chunks = [chunk]
                current_section_type = new_type
                current_section_name = new_name
            else:
                current_section_chunks.append(chunk)
    
    # Don't forget the last section
    if current_section_chunks:
        section = {
            "section_id": f"{metadata['transcript_id']}_S{section_counter:03d}",
            "section_type": current_section_type,
            "section_name": current_section_name,
            "section_summary": generate_section_summary(client, current_section_chunks, current_section_type, current_section_name),
            "section_content": " ".join([c["content"] for c in current_section_chunks]),
            "chunk_ids": [c["chunk_id"] for c in current_section_chunks]
        }
        section.update(metadata)
        sections.append(section)
    
    # Update chunks with section information
    for section in sections:
        section_order = 1
        for chunk_id in section["chunk_ids"]:
            for chunk in chunks:
                if chunk["chunk_id"] == chunk_id:
                    chunk["section_name"] = section["section_name"]
                    chunk["section_type"] = section["section_type"]
                    chunk["section_summary"] = section["section_summary"]
                    chunk["section_order"] = section_order
                    section_order += 1
    
    return sections

# ==============================================================================
# --- Main Processing Function ---
# ==============================================================================

def main():
    """Main processing function."""
    logger.info("=" * 60)
    logger.info("Stage 3: Generate Transcript Chunks")
    logger.info("=" * 60)
    
    # Initialize SMB client
    logger.info("Initializing SMB client...")
    smbclient.ClientConfig(username=NAS_PARAMS["user"], password=NAS_PARAMS["password"])
    
    # Set up OpenAI client
    logger.info("Setting up OpenAI client...")
    client = setup_openai_client()
    if not client:
        logger.error("Failed to set up OpenAI client")
        sys.exit(1)
    
    # Determine input/output paths from stage 1/2
    # First, find the most recent processing folder
    base_output_path = f"//{NAS_PARAMS['ip']}/{NAS_PARAMS['share']}/{NAS_OUTPUT_FOLDER_PATH}/{DOCUMENT_SOURCE}"
    
    # For now, we'll assume the user provides the correct path or we find the most recent
    # In production, this would be passed as an argument
    import glob
    try:
        # List all processing folders
        smbclient.ClientConfig(username=NAS_PARAMS["user"], password=NAS_PARAMS["password"])
        processing_folders = smbclient.listdir(base_output_path)
        processing_folders = [f for f in processing_folders if f.startswith('processing_')]
        processing_folders.sort(reverse=True)  # Most recent first
        
        if not processing_folders:
            logger.error("No processing folders found")
            sys.exit(1)
            
        latest_folder = processing_folders[0]
        logger.info(f"Using processing folder: {latest_folder}")
        
        stage1_output_dir_smb = f"{base_output_path}/{latest_folder}"
    except Exception as e:
        logger.error(f"Error finding processing folder: {e}")
        sys.exit(1)
    
    stage2_output_dir_smb = os.path.join(stage1_output_dir_smb, '2A_processed_files').replace('\\', '/')
    stage3_output_dir_smb = os.path.join(stage1_output_dir_smb, '3A_transcript_chunks').replace('\\', '/')
    
    # Create output directory
    if not create_nas_directory(stage3_output_dir_smb):
        logger.error("Failed to create output directory")
        sys.exit(1)
    
    # Load list of processed files from stage 2
    files_to_process_path = os.path.join(stage1_output_dir_smb, '1C_nas_files_to_process.json').replace('\\', '/')
    files_to_process = read_json_from_nas(files_to_process_path)
    
    if not files_to_process:
        logger.warning("No files to process from stage 1")
        return
    
    # Filter for test mode
    if TEST_MODE:
        if TEST_TRANSCRIPT_ID:
            files_to_process = [f for f in files_to_process if f.get("file_name", "").startswith(TEST_TRANSCRIPT_ID)]
        else:
            files_to_process = files_to_process[:1]
        logger.info(f"TEST MODE: Processing {len(files_to_process)} transcript(s)")
    
    # Process each transcript
    total_files = len(files_to_process)
    
    for i, file_info in enumerate(files_to_process):
        logger.info(f"\nProcessing transcript {i+1}/{total_files}")
        logger.info(f"File: {file_info.get('file_name', 'Unknown')}")
        
        try:
            # Load content from stage 2
            file_base_name = os.path.splitext(file_info['file_name'])[0]
            
            # First try to load JSON for structured data
            json_path = os.path.join(
                stage2_output_dir_smb,
                file_base_name,
                f"{file_base_name}.json"
            ).replace('\\', '/')
            
            json_content = read_json_from_nas(json_path)
            
            # Load markdown as backup or for text extraction
            markdown_path = os.path.join(
                stage2_output_dir_smb,
                file_base_name,
                f"{file_base_name}.md"
            ).replace('\\', '/')
            
            markdown_content = read_text_from_nas(markdown_path)
            
            if not markdown_content and not json_content:
                logger.error(f"Failed to read stage 2 output files")
                continue
            
            # Extract metadata
            content_for_metadata = markdown_content if markdown_content else str(json_content)
            metadata = extract_transcript_metadata(content_for_metadata, file_info)
            transcript_id = metadata["transcript_id"]
            logger.info(f"Transcript ID: {transcript_id}")
            
            # Extract sentences using LLM
            logger.info("Using LLM to parse transcript into sentences...")
            
            # Use markdown content if available, otherwise extract from JSON
            if markdown_content:
                sentences = parse_transcript_to_sentences(client, markdown_content)
            else:
                # Extract content from JSON if markdown not available
                json_text = json_content.get('content', '')
                sentences = parse_transcript_to_sentences(client, json_text)
            
            logger.info(f"Found {len(sentences)} sentences")
            
            # Save sentence data
            sentences_output_path = os.path.join(
                stage3_output_dir_smb,
                f"2A_transcript_sentences_{transcript_id}.json"
            ).replace('\\', '/')
            
            sentence_data = {
                "transcript_id": transcript_id,
                "metadata": metadata,
                "sentences": sentences
            }
            
            if not write_json_to_nas(sentences_output_path, sentence_data):
                logger.error("Failed to save sentence data")
                continue
            
            # Generate chunks
            logger.info("Generating semantic chunks...")
            chunks = process_transcript_to_chunks(client, sentences, metadata)
            logger.info(f"Created {len(chunks)} chunks")
            
            # Save chunk data (before section assignment)
            chunks_output_path = os.path.join(
                stage3_output_dir_smb,
                f"3A_transcript_chunks_{transcript_id}.json"
            ).replace('\\', '/')
            
            if not write_json_to_nas(chunks_output_path, chunks):
                logger.error("Failed to save chunk data")
                continue
            
            # Group chunks into sections
            logger.info("Grouping chunks into sections...")
            sections = group_chunks_into_sections(client, chunks, metadata)
            logger.info(f"Created {len(sections)} sections")
            
            # Save section data
            sections_output_path = os.path.join(
                stage3_output_dir_smb,
                f"3B_transcript_sections_{transcript_id}.json"
            ).replace('\\', '/')
            
            if not write_json_to_nas(sections_output_path, sections):
                logger.error("Failed to save section data")
                continue
            
            # Save updated chunks (with section info)
            chunks_final_path = os.path.join(
                stage3_output_dir_smb,
                f"3C_transcript_chunks_final_{transcript_id}.json"
            ).replace('\\', '/')
            
            if not write_json_to_nas(chunks_final_path, chunks):
                logger.error("Failed to save final chunk data")
                continue
            
            logger.info(f"Successfully processed transcript: {transcript_id}")
            
        except Exception as e:
            logger.error(f"Error processing transcript: {e}")
            continue
    
    logger.info("\n" + "=" * 60)
    logger.info("Stage 3 completed successfully!")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()