-- AEGIS Project Postgres Schema File

-- 1. transcript_sections Table - Stores full transcript sections with summaries and metadata
CREATE TABLE transcript_sections (
    -- System fields
    id SERIAL PRIMARY KEY, -- Unique identifier for each section record
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- Auto-generated timestamp when record is created
    
    -- Document identification fields
    document_source TEXT NOT NULL, -- Source of the document (e.g., 'Earnings Call', 'Annual Report')
    document_type TEXT NOT NULL, -- Type of document (e.g., 'Transcript', 'Press Release')
    document_name TEXT NOT NULL, -- Name of the document (e.g., 'Q3 2023 Earnings Call')
    document_language TEXT NOT NULL, -- Language of the document (e.g., 'en', 'es', 'fr')
    
    -- Retrieval fields
    fiscal_year INTEGER NOT NULL, -- The fiscal year of the document (e.g., 2023)
    fiscal_quarter INTEGER NOT NULL CHECK (fiscal_quarter BETWEEN 1 AND 4), -- Fiscal quarter (1-4)
    bank_name TEXT NOT NULL, -- Name of the bank (e.g., 'JP Morgan Chase', 'Bank of America')
    
    -- Section fields
    section_name TEXT NOT NULL, -- Unique identifier for the section (e.g., 'Introduction', 'Q&A-1')
    section_type TEXT NOT NULL, -- Category of the section (e.g., 'Introduction', 'Financial Results', 'Q&A')
    
    -- Content fields
    section_summary TEXT, -- Concise summary of the section content
    section_content TEXT NOT NULL, -- Full content of the section
    
    -- Refresh fields
    date_created TIMESTAMP NOT NULL, -- When the original document was created
    date_last_modified TIMESTAMP NOT NULL, -- When the document was last modified
    file_name TEXT, -- Original filename (e.g., 'JPM_2023_Q3_Earnings.pdf')
    file_type TEXT, -- File format (e.g., 'PDF', 'DOCX', 'TXT')
    file_size BIGINT, -- Size of the file in bytes
    file_path TEXT, -- Path to the file in storage
    file_link TEXT, -- URL or link to access the original document
    
    -- Unique constraint
    UNIQUE(bank_name, fiscal_year, fiscal_quarter, document_name, section_name)
);

COMMENT ON TABLE transcript_sections IS 'Stores full transcript sections with summaries and metadata for financial documents';

-- 2. transcript_chunks Table - Stores individual chunks of transcript sections with embeddings and metadata
CREATE TABLE transcript_chunks (
    -- System fields
    id SERIAL PRIMARY KEY, -- Unique identifier for each chunk record
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- Auto-generated timestamp when record is created
    
    -- Document identification fields
    document_source TEXT NOT NULL, -- Source of the document (e.g., 'Earnings Call', 'Annual Report')
    document_type TEXT NOT NULL, -- Type of document (e.g., 'Transcript', 'Press Release')
    document_name TEXT NOT NULL, -- Name of the document (e.g., 'Q3 2023 Earnings Call')
    document_language TEXT NOT NULL, -- Language of the document (e.g., 'en', 'es', 'fr')
    
    -- Retrieval fields
    fiscal_year INTEGER NOT NULL, -- The fiscal year of the document (e.g., 2023)
    fiscal_quarter INTEGER NOT NULL CHECK (fiscal_quarter BETWEEN 1 AND 4), -- Fiscal quarter (1-4)
    bank_name TEXT NOT NULL, -- Name of the bank (e.g., 'JP Morgan Chase', 'Bank of America')
    
    -- Section fields
    section_name TEXT NOT NULL, -- Identifier matching with transcript_sections (e.g., 'Introduction', 'Q&A-1')
    section_type TEXT NOT NULL, -- Category of the section (e.g., 'Introduction', 'Financial Results', 'Q&A')
    section_summary TEXT, -- Concise summary of the parent section
    
    -- Reranking fields
    section_importance_score FLOAT, -- Numeric score indicating section importance (e.g., 0.85)
    section_token_count INTEGER, -- Count of tokens in the section for context length management
    section_order INTEGER, -- Order of the chunk within the section (e.g., 1, 2, 3)
    chunk_speaker TEXT, -- Name of person speaking in this chunk (e.g., 'Jamie Dimon, CEO')
    chunk_tags TEXT[], -- Array of tags for categorization (e.g., {'revenue', 'guidance', 'outlook'})
    chunk_topics TEXT[], -- Array of topics covered (e.g., {'interest rates', 'loan growth'})
    
    -- Chunk fields
    content TEXT NOT NULL, -- The actual text content of this chunk
    embedding VECTOR(1536) -- Vector representation of the chunk for semantic search
);

COMMENT ON TABLE transcript_chunks IS 'Stores individual chunks of transcript sections with embeddings and metadata for semantic search';

-- 3. process_monitor_logs Table - Monitors performance and metrics for each stage of processing
CREATE TABLE IF NOT EXISTS process_monitor_logs (
    -- Core Fields --
    log_id BIGSERIAL PRIMARY KEY,                         -- Auto-incrementing unique ID for each log entry
    run_uuid UUID NOT NULL,                               -- Unique ID generated for each complete model invocation/run
    model_name VARCHAR(100) NOT NULL,                     -- Identifier for the model (e.g., 'iris', 'model_b')
    stage_name VARCHAR(100) NOT NULL,                     -- Name of the specific process stage (e.g., 'SSL_Setup', 'Router_Processing')
    stage_start_time TIMESTAMPTZ NOT NULL,                 -- Timestamp when the stage began
    stage_end_time TIMESTAMPTZ,                            -- Timestamp when the stage ended
    duration_ms INT,                                       -- Duration of the stage in milliseconds (calculated: end_time - start_time)
    llm_calls JSONB,                                       -- JSON array storing details for LLM calls within this stage
    total_tokens INT,                                      -- Sum of total tokens from all llm_calls in this stage (calculated)
    total_cost DECIMAL(12, 6),                             -- Sum of costs from all llm_calls in this stage (calculated)
    status VARCHAR(255),                                   -- Outcome/Status of the stage (e.g., 'Success', 'Failure', 'Clarification')
    decision_details TEXT,                                -- Text field for specific outputs or decisions (e.g., Router's chosen agent)
    error_message TEXT,                                   -- Detailed error message if the stage failed
    log_timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,   -- Timestamp when this specific log row was created

    -- Optional Extra Fields for Future Use --
    user_id VARCHAR(255),                                 -- Optional: Identifier for the user initiating the request (if applicable)
    environment VARCHAR(50),                              -- Optional: Environment identifier (e.g., 'production', 'staging', 'development')
    custom_metadata JSONB,                                -- Optional: Flexible JSONB field for any other structured metadata
    notes TEXT                                             -- Optional: Free-form text field for additional notes or context
);

-- Comments for clarity --
COMMENT ON COLUMN process_monitor_logs.llm_calls IS 'JSON array storing details for LLM calls: [{"model": str, "input_tokens": int, "output_tokens": int, "cost": float, "response_time_ms": int}]';
COMMENT ON COLUMN process_monitor_logs.custom_metadata IS 'Flexible JSONB field for any other structured metadata specific to the invocation or environment.';