-- Script SQL para crear la tabla RAG_DOCUMENTS en Supabase
-- Tabla para almacenar documentos y embeddings para el sistema RAG

-- Habilitar extensión pgvector (necesaria para embeddings)
CREATE EXTENSION IF NOT EXISTS vector;

-- Tabla de documentos RAG
CREATE TABLE IF NOT EXISTS rag_documents (
    id BIGSERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    embedding vector(1536), -- OpenAI text-embedding-3-small dimension
    metadata JSONB DEFAULT '{}',
    doc_type TEXT NOT NULL, -- 'app_manual', 'hacienda', 'seg_social'
    title TEXT,
    source TEXT, -- URL o referencia del documento original
    chunk_index INTEGER DEFAULT 0, -- Índice del chunk si el documento fue dividido
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índices para búsquedas
CREATE INDEX IF NOT EXISTS idx_rag_documents_doc_type ON rag_documents(doc_type);
CREATE INDEX IF NOT EXISTS idx_rag_documents_title ON rag_documents(title);

-- Índice HNSW para búsqueda de vectores (más eficiente para similitud coseno)
-- Nota: Este índice mejora significativamente el rendimiento de búsquedas vectoriales
CREATE INDEX IF NOT EXISTS idx_rag_documents_embedding ON rag_documents 
USING hnsw (embedding vector_cosine_ops);

-- Trigger para actualizar updated_at automáticamente
CREATE OR REPLACE FUNCTION update_rag_documents_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_rag_documents_updated_at ON rag_documents;
CREATE TRIGGER trigger_rag_documents_updated_at
    BEFORE UPDATE ON rag_documents
    FOR EACH ROW
    EXECUTE FUNCTION update_rag_documents_updated_at();

-- Función para buscar documentos similares por embedding
CREATE OR REPLACE FUNCTION search_rag_documents(
    query_embedding vector(1536),
    match_threshold FLOAT DEFAULT 0.7,
    match_count INT DEFAULT 5,
    filter_doc_type TEXT DEFAULT NULL
)
RETURNS TABLE (
    id BIGINT,
    content TEXT,
    title TEXT,
    doc_type TEXT,
    metadata JSONB,
    similarity FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        rd.id,
        rd.content,
        rd.title,
        rd.doc_type,
        rd.metadata,
        1 - (rd.embedding <=> query_embedding) AS similarity
    FROM rag_documents rd
    WHERE 
        (filter_doc_type IS NULL OR rd.doc_type = filter_doc_type)
        AND 1 - (rd.embedding <=> query_embedding) > match_threshold
    ORDER BY rd.embedding <=> query_embedding
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

-- Comentarios
COMMENT ON TABLE rag_documents IS 'Documentos indexados para el sistema RAG del asistente';
COMMENT ON COLUMN rag_documents.content IS 'Contenido del documento o chunk';
COMMENT ON COLUMN rag_documents.embedding IS 'Vector embedding del contenido (1536 dimensiones para OpenAI)';
COMMENT ON COLUMN rag_documents.metadata IS 'Metadatos adicionales en formato JSON';
COMMENT ON COLUMN rag_documents.doc_type IS 'Tipo: app_manual, hacienda, seg_social';
COMMENT ON COLUMN rag_documents.title IS 'Título del documento o sección';
COMMENT ON COLUMN rag_documents.source IS 'Fuente original del documento';
COMMENT ON COLUMN rag_documents.chunk_index IS 'Índice del chunk si el documento fue dividido';
COMMENT ON FUNCTION search_rag_documents IS 'Busca documentos similares usando similitud coseno';
