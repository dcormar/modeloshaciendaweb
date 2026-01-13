-- Script SQL para añadir columna ai_result a la tabla uploads
-- Ejecutar este script en el SQL Editor de Supabase

-- Añadir columna ai_result para almacenar el resultado del procesamiento con Gemini
ALTER TABLE uploads ADD COLUMN IF NOT EXISTS ai_result JSONB;

-- Comentario para documentación
COMMENT ON COLUMN uploads.ai_result IS 'Resultado del procesamiento con IA (Gemini). Contiene los datos extraídos de la factura.';

-- Nota: Los nuevos valores de status que se usarán son:
-- UPLOADED       - Archivo guardado, pendiente procesar
-- PROCESSING_AI  - Procesando con Gemini (en curso)
-- AI_COMPLETED   - IA completada, pendiente subir a Drive
-- UPLOADING_DRIVE - Subiendo a Drive (en curso)
-- COMPLETED      - Todo completado
-- FAILED_AI      - Fallo en procesamiento IA
-- FAILED_DRIVE   - Fallo subiendo a Drive
-- DUPLICATED     - Factura duplicada (ya existía)

