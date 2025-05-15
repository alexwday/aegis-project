# Transcript Processing Plan

## Overview
This document outlines the approach for processing financial earnings call transcripts into semantically meaningful chunks that can be effectively queried by an LLM agent.

## Processing Workflow

### 1. Transcript Segmentation
- Split raw transcripts into individual sentences
- Number each sentence sequentially (1...N)
- Preserve metadata about the transcript source, date, speaker, etc.

### 2. Chunk Generation Process
For each sentence in the transcript, we use an LLM to decide if it belongs with the previous chunk or starts a new chunk:

```
PROCESSING WINDOW:
┌───────────────────────────────────────┐
│ Previous 20 Chunks (Context History)  │ 
├───────────────────────────────────────┤
│ Current Active Chunk                  │
│  Contains: [Sentence(s)]              │
│                                       │
│ Active Sentence = Next Sentence       │
│  Question: Add to current chunk?      │
├───────────────────────────────────────┤
│ Next 19 Sentences (Future context)    │
└───────────────────────────────────────┘
```

### 3. LLM Decision Making
For each sentence evaluation, the LLM provides:

1. Decision: Whether to add the active sentence to the current chunk or start a new chunk
2. Related Chunks: IDs of previous chunks that provide relevant context 
3. Additional Context: Specific information needed to understand the chunk, referencing sentence numbers

### 4. Output Format
Each processed chunk will have:
```json
{
  "chunk_id": "unique_id",
  "transcript_id": "source_transcript_id",
  "raw_text": "Combined sentences that form a complete semantic unit",
  "sentences": [1, 2, 3, 4],  // Sentence IDs contained in this chunk
  "related_chunks": [12, 15, 18],  // IDs of related chunks that provide context
  "additional_context": [
    {"context": "First piece of additional context", "source": 124},
    {"context": "Second piece of additional context", "source": 135}
  ],
  "metadata": {
    "speakers": ["John Doe", "Jane Smith"],
    "timestamp": "2023-05-15T10:30:00Z",
    "topic_tags": ["revenue", "growth", "forecast"]
  }
}
```

## Processing Stages

The processing pipeline consists of the following stages:

1. **Extract PostgreSQL** (`tp_stage1_extract_postgres.py`): 
   - Extract transcript catalog from database
   - Compare with filesystem to identify new/updated transcripts
   - Generate list of transcripts to process

2. **Process Transcripts** (`tp_stage2_process_transcripts.py`):
   - Transform raw transcripts into sentence-level data
   - Assign unique sentence IDs
   - Prepare for chunk generation

3. **Generate Chunks** (`tp_stage3_generate_chunks.py`):
   - Use LLM to determine sentence grouping
   - Identify related chunks and additional context
   - Generate structured chunk data

4. **Update PostgreSQL** (`tp_stage4_update_postgres.py`):
   - Upload processed chunks to database
   - Update catalog entries
   - Apply any necessary corrections

5. **Archive Results** (`tp_stage5_archive_results.py`):
   - Archive processed files
   - Generate processing summaries
   - Create logs for monitoring

## Database Schema

Chunks will be stored in a PostgreSQL database with the following structure:

1. **Transcript Catalog Table**:
   - transcript_id (PK)
   - source (bank/company name)
   - date
   - quarter
   - year
   - title
   - participants
   - filesize
   - metadata

2. **Transcript Chunks Table**:
   - chunk_id (PK)
   - transcript_id (FK)
   - raw_text
   - sentences (array)
   - related_chunks (array)
   - additional_context (JSONB)
   - metadata (JSONB)
   - embedding (vector)

3. **Sentences Table**:
   - sentence_id (PK)
   - transcript_id (FK)
   - text
   - position
   - speaker
   - timestamp