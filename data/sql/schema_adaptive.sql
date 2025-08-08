-- AEGIS Adaptive Schema - Automatically adjusts based on pgvector capabilities
-- This schema adapts to use the best available vector type

-- First, run capability tests
\i test_vector_capabilities.sql

-- Drop existing tables if they exist
DROP TABLE IF EXISTS document_embeddings CASCADE;
DROP TABLE IF EXISTS documents CASCADE;
DROP TABLE IF EXISTS agent_responses CASCADE;
DROP TABLE IF EXISTS agents CASCADE;
DROP TABLE IF EXISTS conversations CASCADE;

-- Core tables (these don't depend on pgvector)
CREATE TABLE conversations (
    id SERIAL PRIMARY KEY,
    conversation_id VARCHAR(255) UNIQUE NOT NULL,
    user_id VARCHAR(255),
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE agents (
    id SERIAL PRIMARY KEY,
    agent_name VARCHAR(255) NOT NULL,
    agent_type VARCHAR(100) NOT NULL,
    description TEXT,
    configuration JSONB,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE agent_responses (
    id SERIAL PRIMARY KEY,
    conversation_id VARCHAR(255) REFERENCES conversations(conversation_id),
    agent_id INTEGER REFERENCES agents(id),
    request_text TEXT,
    response_text TEXT,
    tokens_used INTEGER,
    response_time_ms INTEGER,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR(255) UNIQUE NOT NULL,
    title VARCHAR(500),
    content TEXT,
    source VARCHAR(255),
    document_type VARCHAR(100),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Now create the embeddings table based on available capabilities
DO $$
DECLARE
    has_halfvec_3072 BOOLEAN;
    has_vector_3072 BOOLEAN;
    has_vector_1536 BOOLEAN;
    create_sql TEXT;
    index_sql TEXT;
    has_ivfflat BOOLEAN;
    has_hnsw BOOLEAN;
BEGIN
    -- Check capabilities
    SELECT COALESCE(supported, false) INTO has_halfvec_3072 
    FROM vector_capabilities 
    WHERE capability = 'halfvec_3072';
    
    SELECT COALESCE(supported, false) INTO has_vector_3072 
    FROM vector_capabilities 
    WHERE capability = 'vector_3072';
    
    SELECT COALESCE(supported, false) INTO has_vector_1536 
    FROM vector_capabilities 
    WHERE capability = 'vector_1536';
    
    SELECT COALESCE(supported, false) INTO has_ivfflat 
    FROM vector_capabilities 
    WHERE capability = 'ivfflat_index';
    
    SELECT COALESCE(supported, false) INTO has_hnsw 
    FROM vector_capabilities 
    WHERE capability = 'hnsw_index';
    
    -- Build CREATE TABLE statement based on capabilities
    create_sql := 'CREATE TABLE document_embeddings (
        id SERIAL PRIMARY KEY,
        document_id VARCHAR(255) REFERENCES documents(document_id),
        chunk_index INTEGER,
        chunk_text TEXT,';
    
    -- Choose the best available vector type
    IF has_halfvec_3072 THEN
        create_sql := create_sql || '
        embedding halfvec(3072),  -- Using halfvec for 50% storage savings';
        RAISE NOTICE 'Creating document_embeddings with halfvec(3072) - optimal storage';
    ELSIF has_vector_3072 THEN
        create_sql := create_sql || '
        embedding vector(3072),  -- Using standard vector for 3072 dimensions';
        RAISE NOTICE 'Creating document_embeddings with vector(3072) - full precision';
    ELSIF has_vector_1536 THEN
        create_sql := create_sql || '
        embedding vector(1536),  -- Limited to 1536 dimensions';
        RAISE NOTICE 'Creating document_embeddings with vector(1536) - smaller embeddings only';
    ELSE
        create_sql := create_sql || '
        embedding BYTEA,  -- Fallback: store as binary (no vector operations)';
        RAISE WARNING 'pgvector not properly configured - using BYTEA fallback';
    END IF;
    
    create_sql := create_sql || '
        embedding_model VARCHAR(100),
        metadata JSONB,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )';
    
    -- Execute the CREATE TABLE
    EXECUTE create_sql;
    
    -- Create appropriate index if vector type is available
    IF has_vector_1536 OR has_vector_3072 OR has_halfvec_3072 THEN
        IF has_hnsw THEN
            index_sql := 'CREATE INDEX idx_document_embeddings_vector 
                         ON document_embeddings 
                         USING hnsw (embedding vector_cosine_ops)';
            RAISE NOTICE 'Creating HNSW index for fast similarity search';
        ELSIF has_ivfflat THEN
            index_sql := 'CREATE INDEX idx_document_embeddings_vector 
                         ON document_embeddings 
                         USING ivfflat (embedding vector_cosine_ops) 
                         WITH (lists = 100)';
            RAISE NOTICE 'Creating IVFFlat index for similarity search';
        ELSE
            RAISE NOTICE 'No specialized vector indexes available - using default';
        END IF;
        
        IF index_sql IS NOT NULL THEN
            EXECUTE index_sql;
        END IF;
    END IF;
    
    -- Log what was created
    INSERT INTO vector_capabilities (capability, supported, details)
    VALUES ('schema_created', true, 
            'Embeddings table created with: ' || 
            CASE 
                WHEN has_halfvec_3072 THEN 'halfvec(3072)'
                WHEN has_vector_3072 THEN 'vector(3072)'
                WHEN has_vector_1536 THEN 'vector(1536)'
                ELSE 'BYTEA fallback'
            END);
END $$;

-- Create other indexes
CREATE INDEX idx_conversations_user_id ON conversations(user_id);
CREATE INDEX idx_conversations_status ON conversations(status);
CREATE INDEX idx_agent_responses_conversation ON agent_responses(conversation_id);
CREATE INDEX idx_agent_responses_agent ON agent_responses(agent_id);
CREATE INDEX idx_documents_type ON documents(document_type);
CREATE INDEX idx_document_embeddings_document ON document_embeddings(document_id);

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Add triggers for updated_at
CREATE TRIGGER update_conversations_updated_at BEFORE UPDATE ON conversations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_agents_updated_at BEFORE UPDATE ON agents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Show final configuration
SELECT 
    '✅ Schema created successfully!' as status,
    details as configuration
FROM vector_capabilities
WHERE capability = 'schema_created'
UNION ALL
SELECT 
    'ℹ️  Capability' as status,
    capability || ': ' || CASE WHEN supported THEN '✅' ELSE '❌' END || ' - ' || details
FROM vector_capabilities
WHERE capability != 'schema_created' AND capability != 'recommendation'
ORDER BY 1;