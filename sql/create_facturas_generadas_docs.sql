-- Script SQL para crear la tabla FACTURAS_GENERADAS_DOCS en Supabase
-- Ejecutar este script en el SQL Editor de Supabase

CREATE TABLE IF NOT EXISTS facturas_generadas_docs (
    id BIGSERIAL PRIMARY KEY,
    factura_id BIGINT NOT NULL REFERENCES facturas_generadas(id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    mime_type TEXT NOT NULL DEFAULT 'application/pdf',
    sha256 TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT
);

-- Crear índice para búsquedas por factura_id
CREATE INDEX IF NOT EXISTS idx_facturas_generadas_docs_factura_id ON facturas_generadas_docs(factura_id);

-- Comentarios
COMMENT ON TABLE facturas_generadas_docs IS 'Documentos PDF generados para facturas generadas';
COMMENT ON COLUMN facturas_generadas_docs.factura_id IS 'ID de la factura generada a la que pertenece este documento';
COMMENT ON COLUMN facturas_generadas_docs.storage_path IS 'Ruta donde se almacena el archivo PDF';

