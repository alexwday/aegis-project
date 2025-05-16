# -*- coding: utf-8 -*-
"""
Stage 3: Generate Transcript Chunks using LLM (Optimized)

This script processes transcript files from Stage 2.
For each transcript, it:
1. Uses regex patterns to parse transcript into structured sentences with speakers
2. Uses LLM to determine semantic chunk boundaries
3. Groups chunks into sections
4. Creates structured output for database insertion

Features:
- TEST_MODE configuration to process only one transcript
- Regex-based sentence parsing (no LLM for parsing)
- LLM with tool definitions for semantic operations
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
import re
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
    "client_secret": "YOUR_CLIENT_SECRET"
}

# --- GPT API Configuration ---
GPT_CONFIG = {
    "base_url": "YOUR_CUSTOM_GPT_API_BASE_URL",
    "model_name": "gpt-4o"
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

# --- Tool Definitions ---
CHUNKING_DECISION_TOOL = {
    "type": "function",
    "function": {
        "name": "chunking_decision",
        "description": "Decide whether to add a sentence to the current chunk or start a new chunk",
        "parameters": {
            "type": "object",
            "properties": {
                "add_to_chunk": {
                    "type": "boolean",
                    "description": "Whether to add the sentence to the current chunk"
                },
                "reasoning": {
                    "type": "string",
                    "description": "Brief explanation of the decision"
                },
                "related_chunks": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "IDs of previous chunks that are semantically related"
                },
                "additional_context": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "context": {"type": "string"},
                            "source": {"type": "string"}
                        }
                    },
                    "description": "Additional context from previous discussion"
                }
            },
            "required": ["add_to_chunk", "reasoning", "related_chunks", "additional_context"]
        }
    }
}

CHUNK_METADATA_TOOL = {
    "type": "function",
    "function": {
        "name": "extract_chunk_metadata",
        "description": "Extract metadata from a transcript chunk",
        "parameters": {
            "type": "object",
            "properties": {
                "chunk_speaker": {
                    "type": "string",
                    "description": "Primary speaker in the chunk"
                },
                "chunk_tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "3-5 keywords/phrases"
                },
                "chunk_topics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "2-3 thematic topics"
                }
            },
            "required": ["chunk_speaker", "chunk_tags", "chunk_topics"]
        }
    }
}

SECTION_BOUNDARY_TOOL = {
    "type": "function",
    "function": {
        "name": "section_boundary_decision",
        "description": "Determine if a chunk should start a new section",
        "parameters": {
            "type": "object",
            "properties": {
                "start_new_section": {
                    "type": "boolean",
                    "description": "Whether the chunk should start a new section"
                },
                "section_type": {
                    "type": "string",
                    "description": "Type of the section from the available types"
                },
                "section_name": {
                    "type": "string",
                    "description": "Specific descriptive name for this section"
                },
                "reasoning": {
                    "type": "string",
                    "description": "Brief explanation of the decision"
                }
            },
            "required": ["start_new_section", "section_type", "section_name", "reasoning"]
        }
    }
}

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
                "client_secret": OAUTH_CONFIG["client_secret"]
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
            "Authorization": f"Bearer {token}"
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
# --- Regex-based Parsing Functions ---
# ==============================================================================

def parse_transcript_to_sentences(content: str) -> List[Dict]:
    """Parse transcript into sentences with speaker identification using regex."""
    sentences = []
    sentence_id = 1
    
    # Common patterns for speaker identification
    speaker_patterns = [
        r'^([A-Z][a-zA-Z\s]+?):\s*(.+)',  # "John Smith: ..."
        r'^\[([^\]]+)\]\s*(.+)',           # "[CEO] ..."
        r'^<([^>]+)>\s*(.+)',              # "<Analyst> ..."
        r'^([A-Z][a-zA-Z\s]+)\s*-\s*(.+)'  # "John Smith - ..."
    ]
    
    # Split content into lines
    lines = content.split('\n')
    current_speaker = "Unknown"
    current_text = ""
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Check for speaker change
        speaker_found = False
        for pattern in speaker_patterns:
            match = re.match(pattern, line)
            if match:
                # Save previous sentence if exists
                if current_text:
                    sentences.append({
                        "sentence_id": sentence_id,
                        "text": current_text.strip(),
                        "position": sentence_id,
                        "speaker": current_speaker,
                        "speaker_title": ""
                    })
                    sentence_id += 1
                
                # Update speaker and start new text
                current_speaker = match.group(1).strip()
                current_text = match.group(2).strip()
                speaker_found = True
                break
        
        if not speaker_found:
            # Continue with current speaker
            if current_text:
                current_text += " " + line
            else:
                current_text = line
        
        # Split into sentences using punctuation
        if current_text and re.search(r'[.!?]$', current_text):
            # Use NLTK sentence tokenizer if available, otherwise simple split
            sentence_parts = re.split(r'(?<=[.!?])\s+', current_text)
            
            for i, part in enumerate(sentence_parts):
                if part.strip():
                    sentences.append({
                        "sentence_id": sentence_id,
                        "text": part.strip(),
                        "position": sentence_id,
                        "speaker": current_speaker,
                        "speaker_title": ""
                    })
                    sentence_id += 1
            
            current_text = ""
    
    # Don't forget the last sentence
    if current_text:
        sentences.append({
            "sentence_id": sentence_id,
            "text": current_text.strip(),
            "position": sentence_id,
            "speaker": current_speaker,
            "speaker_title": ""
        })
    
    return sentences

# ==============================================================================
# --- LLM-based Chunking Functions ---
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
"""
    
    try:
        response = client.chat.completions.create(
            model=GPT_CONFIG["model_name"],
            messages=[{"role": "user", "content": prompt}],
            tools=[CHUNKING_DECISION_TOOL],
            tool_choice={"type": "function", "function": {"name": "chunking_decision"}},
            temperature=0.3
        )
        
        tool_call = response.choices[0].message.tool_calls[0]
        return json.loads(tool_call.function.arguments)
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
"""
    
    try:
        response = client.chat.completions.create(
            model=GPT_CONFIG["model_name"],
            messages=[{"role": "user", "content": prompt}],
            tools=[CHUNK_METADATA_TOOL],
            tool_choice={"type": "function", "function": {"name": "extract_chunk_metadata"}},
            temperature=0.3
        )
        
        tool_call = response.choices[0].message.tool_calls[0]
        return json.loads(tool_call.function.arguments)
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
) -> Dict:
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
"""
    
    try:
        response = client.chat.completions.create(
            model=GPT_CONFIG["model_name"],
            messages=[{"role": "user", "content": prompt}],
            tools=[SECTION_BOUNDARY_TOOL],
            tool_choice={"type": "function", "function": {"name": "section_boundary_decision"}},
            temperature=0.3
        )
        
        tool_call = response.choices[0].message.tool_calls[0]
        return json.loads(tool_call.function.arguments)
    except Exception as e:
        logger.error(f"Error in section boundary detection: {e}")
        return {
            "start_new_section": False,
            "section_type": "Other",
            "section_name": "Unnamed Section",
            "reasoning": "Error in processing"
        }

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
            result = should_start_new_section(
                client,
                current_section_chunks,
                chunk,
                sections
            )
            
            if result["start_new_section"]:
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
                current_section_type = result["section_type"]
                current_section_name = result["section_name"]
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
    logger.info("Stage 3: Generate Transcript Chunks (Optimized)")
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
    
    # Determine input/output paths matching stage 1/2 structure
    # Base output directory (same as stage 1 and 2)
    base_output_path = f"//{NAS_PARAMS['ip']}/{NAS_PARAMS['share']}/{NAS_OUTPUT_FOLDER_PATH}/{DOCUMENT_SOURCE}"
    stage1_output_dir_smb = base_output_path
    
    logger.info(f"Using base output directory: {stage1_output_dir_smb}")
    
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
            
            # Parse transcript into sentences using regex
            logger.info("Parsing transcript into sentences using regex...")
            
            # Use markdown content if available, otherwise extract from JSON
            if markdown_content:
                sentences = parse_transcript_to_sentences(markdown_content)
            else:
                # Extract content from JSON if markdown not available
                json_text = json_content.get('content', '')
                sentences = parse_transcript_to_sentences(json_text)
            
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