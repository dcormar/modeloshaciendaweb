-- Script SQL para crear la tabla USERS en Supabase
-- Ejecutar este script en el SQL Editor de Supabase

CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    nombre_empresa TEXT,
    nif TEXT,
    direccion TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Crear índice para búsquedas por username
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- Comentarios
COMMENT ON TABLE users IS 'Tabla de usuarios con información de empresa/autónomo';
COMMENT ON COLUMN users.username IS 'Nombre de usuario (compatible con usuarios en memoria)';
COMMENT ON COLUMN users.nombre_empresa IS 'Nombre de la empresa o autónomo';
COMMENT ON COLUMN users.nif IS 'NIF de la empresa o autónomo';
COMMENT ON COLUMN users.direccion IS 'Dirección de la empresa o autónomo';

-- Insertar usuario demo por defecto (opcional, para pruebas)
-- INSERT INTO users (username, nombre_empresa, nif, direccion) 
-- VALUES ('demo@demo.com', 'Mi Empresa S.L.', 'B12345678', 'Calle Ejemplo 123, Madrid')
-- ON CONFLICT (username) DO NOTHING;

