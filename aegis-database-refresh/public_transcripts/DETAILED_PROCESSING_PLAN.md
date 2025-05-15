# Detailed Transcript Processing Plan

## Overview
This document outlines the detailed workflow for processing financial earnings call transcripts into the `transcript_chunks` and `transcript_sections` tables using LLM-based semantic chunking.

## Database Schema (Simplified)

### 1. transcript_sections
```
id                  SERIAL PRIMARY KEY
document_source     TEXT
document_type       TEXT
document_name       TEXT
document_language   TEXT
fiscal_year         INTEGER
fiscal_quarter      INTEGER
bank_name           TEXT
section_name        TEXT
section_type        TEXT
section_summary     TEXT
section_content     TEXT
date_created        TIMESTAMP
date_last_modified  TIMESTAMP
file_name           TEXT
file_type           TEXT
file_size           BIGINT
file_path           TEXT
file_link           TEXT
```

### 2. transcript_chunks
```
id                    SERIAL PRIMARY KEY
document_source       TEXT
document_type         TEXT
document_name         TEXT
document_language     TEXT
fiscal_year           INTEGER
fiscal_quarter        INTEGER
bank_name             TEXT
section_name          TEXT
section_type          TEXT
section_summary       TEXT
section_importance_score FLOAT
section_token_count   INTEGER
section_order         INTEGER
chunk_speaker         TEXT
chunk_tags            TEXT[]
chunk_topics          TEXT[]
content               TEXT
embedding             VECTOR(1536)
```

## Processing Workflow with Field Mappings

### Stage 1: Extract & Compare (tp_stage1_extract_postgres.py)
- **Input**: Raw transcript files, PostgreSQL database
- **Output**: JSON lists of transcripts to process and records to delete
- **Database Table**: `transcript_sections`
- **SQL Query Fields**:
  ```sql
  SELECT id, file_name, file_path, date_last_modified, file_size,
         document_source, document_type, document_name, bank_name,
         fiscal_year, fiscal_quarter
  FROM transcript_sections
  WHERE document_source = 'earnings_call';
  ```
- **File Comparison**: Based on `file_name`, `date_last_modified`
- **Output JSON Files**:
  - `1A_catalog_in_postgres.json` - Current DB records
  - `1B_files_in_nas.json` - Available transcript files
  - `1C_nas_files_to_process.json` - Files to process
  - `1D_postgres_files_to_delete.json` - DB records to delete

### Stage 2: Process Transcripts (tp_stage2_process_transcripts.py)
- **Input**: JSON list of transcripts to process (`1C_nas_files_to_process.json`)
- **Output**: Sentence-level data for each transcript
- **Processing Steps**:
  1. Parse transcript to extract:
     - Metadata (bank_name, fiscal_year, fiscal_quarter, document_name)
     - Speaker information
     - Full text content
  2. Split transcript into sentences
  3. Assign unique sentence ID to each sentence
  4. Create structured sentence data:
     ```json
     {
       "transcript_id": "JPM_2023_Q1",
       "sentence_id": 45,
       "text": "We expect net interest income to be approximately $56 billion for the full year.",
       "position": 45,
       "speaker": "Jeremy Barnum, CFO",
       "metadata": {
         "document_source": "earnings_call",
         "document_type": "transcript",
         "document_name": "Q1 2023 Earnings Call",
         "bank_name": "JP Morgan Chase",
         "fiscal_year": 2023,
         "fiscal_quarter": 1
       }
     }
     ```
  5. Save processed sentences to:
     - `2A_transcript_sentences_{transcript_id}.json`
     - `2B_transcript_metadata_{transcript_id}.json`

### Stage 3: Generate Chunks (tp_stage3_generate_chunks.py)
- **Input**: Processed sentence data from Stage 2
- **Output**: Semantic chunks with metadata
- **Processing Steps**:
  1. Initialize first sentence as first chunk
  2. For each subsequent sentence:
     - Present to LLM with:
       - Previous 20 chunks as context
       - Current active chunk
       - Next 19 sentences
     - LLM decides:
       ```json
       {
         "add_to_chunk": true/false,
         "related_chunks": [chunk_ids],
         "additional_context": [
           {"context": "Context text", "source": sentence_id}
         ]
       }
       ```
  3. Generate chunk metadata using LLM:
     ```json
     {
       "chunk_speaker": "Jeremy Barnum, CFO",
       "chunk_tags": ["net interest income", "guidance", "financial forecast"],
       "chunk_topics": ["revenue projection", "interest rate impact"]
     }
     ```
  4. Create embedding for each chunk content
  5. Generate chunk file:
     ```json
     {
       "chunk_id": "JPM_2023_Q1_C042",
       "document_source": "earnings_call",
       "document_type": "transcript",
       "document_name": "Q1 2023 Earnings Call",
       "document_language": "en",
       "fiscal_year": 2023,
       "fiscal_quarter": 1,
       "bank_name": "JP Morgan Chase",
       "temporary_section_id": "TEMP_S007",
       "sentences": [45, 46, 47],
       "content": "We expect net interest income to be approximately $56 billion for the full year. This represents a significant increase from our previous guidance. The upward revision is primarily due to the sustained higher interest rate environment.",
       "related_chunks": [38, 41],
       "additional_context": [
         {"context": "Previous guidance was $54 billion", "source": 24}
       ],
       "chunk_speaker": "Jeremy Barnum, CFO",
       "chunk_tags": ["net interest income", "guidance", "financial forecast"],
       "chunk_topics": ["revenue projection", "interest rate impact"],
       "embedding": [0.123, 0.456, ...] 
     }
     ```
  6. Save to `3A_transcript_chunks_{transcript_id}.json`

### Stage 3b: Group Chunks into Sections (Part of tp_stage3_generate_chunks.py)
- **Input**: Generated chunks from first part of Stage 3
- **Output**: Section definitions with grouped chunks
- **Processing Steps**:
  1. Group related chunks using LLM:
     - Feed chunks in sequence to LLM with context
     - LLM determines section boundaries
     - LLM assigns:
       - `section_type` (from predefined categories: Introduction, Financial Results, Q&A, etc.)
       - `section_name` (specific to content: "Q1 2023 Net Interest Income Outlook")
  2. Generate section summary for each section
  3. Create section JSON:
     ```json
     {
       "section_id": "JPM_2023_Q1_S007",
       "document_source": "earnings_call",
       "document_type": "transcript",
       "document_name": "Q1 2023 Earnings Call",
       "document_language": "en",
       "fiscal_year": 2023,
       "fiscal_quarter": 1,
       "bank_name": "JP Morgan Chase",
       "section_name": "Q1 2023 Net Interest Income Outlook",
       "section_type": "Financial Results",
       "section_summary": "CFO Jeremy Barnum provides updated net interest income guidance of $56 billion for 2023, up from previous $54 billion forecast, citing sustained higher interest rates.",
       "section_content": "[Full text of combined chunks]",
       "chunk_ids": ["JPM_2023_Q1_C042", "JPM_2023_Q1_C043", "JPM_2023_Q1_C044"],
       "date_created": "2023-01-20T14:30:00Z",
       "date_last_modified": "2023-01-20T14:30:00Z", 
       "file_name": "JPM_2023_Q1_Earnings_Call.pdf",
       "file_type": "PDF",
       "file_size": 1234567,
       "file_path": "data/earnings_calls/JPM/2023/Q1/JPM_2023_Q1_Earnings_Call.pdf"
     }
     ```
  4. Save to `3B_transcript_sections_{transcript_id}.json`
  5. Update chunk records with final section_name, section_type, section_summary, and section order

### Stage 4: Update PostgreSQL (tp_stage4_update_postgres.py)
- **Input**: Chunk and section files from Stage 3
- **Output**: Database records in PostgreSQL
- **Processing Steps**:
  1. Delete outdated records (using `1D_postgres_files_to_delete.json`)
  2. Insert chunks into `transcript_chunks` table:
     ```sql
     INSERT INTO transcript_chunks (
       document_source, document_type, document_name, document_language,
       fiscal_year, fiscal_quarter, bank_name, 
       section_name, section_type, section_summary,
       section_importance_score, section_token_count, section_order,
       chunk_speaker, chunk_tags, chunk_topics, content, embedding
     ) VALUES (...);
     ```
  3. Insert sections into `transcript_sections` table:
     ```sql
     INSERT INTO transcript_sections (
       document_source, document_type, document_name, document_language,
       fiscal_year, fiscal_quarter, bank_name,
       section_name, section_type, section_summary, section_content,
       date_created, date_last_modified, file_name, file_type, file_size, file_path
     ) VALUES (...);
     ```
  4. Log processing stats to `process_monitor_logs` table

### Stage 5: Archive Results (tp_stage5_archive_results.py)
- **Input**: Output files from all previous stages
- **Output**: Archived files in a timestamped directory
- **Processing Steps**:
  1. Create timestamped archive folder
  2. Move all output files to archive
  3. Generate processing summary report
  4. Clean up temporary files

## Processing Metrics

The following metrics will be tracked in the `process_monitor_logs` table:
- Total transcripts processed
- Total sentences processed
- Total chunks generated
- Total sections created
- LLM calls and token usage
- Processing time for each stage
- Total cost of processing
- Success/failure status

## Output File Structure
```
/nas_path/earnings_calls/
  /output/
    /1A_catalog_in_postgres.json
    /1B_files_in_nas.json
    /1C_nas_files_to_process.json  
    /1D_postgres_files_to_delete.json
    /JPM_2023_Q1/
      /2A_transcript_sentences.json
      /2B_transcript_metadata.json
      /3A_transcript_chunks.json  
      /3B_transcript_sections.json
    /BAC_2023_Q1/
      /...
    /process_summary.json
```