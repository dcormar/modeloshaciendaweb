-- Script SQL para añadir el campo user_id a la tabla facturas_generadas
-- Ejecutar este script en el SQL Editor de Supabase

-- Añadir columna user_id (usaremos el username como identificador por ahora)
ALTER TABLE facturas_generadas 
ADD COLUMN IF NOT EXISTS user_id TEXT;

-- Crear índice para búsquedas por usuario
CREATE INDEX IF NOT EXISTS idx_facturas_generadas_user_id ON facturas_generadas(user_id);

-- Comentario
COMMENT ON COLUMN facturas_generadas.user_id IS 'Identificador del usuario que creó la factura (username)';

