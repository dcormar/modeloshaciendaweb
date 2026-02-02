-- Script SQL para crear la tabla USER_CONTACTS en Supabase
-- Tabla para almacenar contactos de cada usuario (para envío de notificaciones)

CREATE TABLE IF NOT EXISTS user_contacts (
    id BIGSERIAL PRIMARY KEY,
    username TEXT NOT NULL, -- Username del usuario propietario (email)
    nombre TEXT NOT NULL,
    email TEXT,
    telegram_chat_id TEXT,
    telegram_username TEXT,
    tipo TEXT DEFAULT 'general', -- 'gestor', 'cliente', 'proveedor', 'general'
    activo BOOLEAN DEFAULT true,
    metadata JSONB DEFAULT '{}', -- Datos adicionales (códigos de vinculación, etc.)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índices para búsquedas frecuentes
CREATE INDEX IF NOT EXISTS idx_user_contacts_username ON user_contacts(username);
CREATE INDEX IF NOT EXISTS idx_user_contacts_tipo ON user_contacts(tipo);
CREATE INDEX IF NOT EXISTS idx_user_contacts_activo ON user_contacts(activo);

-- Trigger para actualizar updated_at automáticamente
CREATE OR REPLACE FUNCTION update_user_contacts_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_user_contacts_updated_at ON user_contacts;
CREATE TRIGGER trigger_user_contacts_updated_at
    BEFORE UPDATE ON user_contacts
    FOR EACH ROW
    EXECUTE FUNCTION update_user_contacts_updated_at();

-- Comentarios
COMMENT ON TABLE user_contacts IS 'Contactos de usuarios para envío de notificaciones por email y Telegram';
COMMENT ON COLUMN user_contacts.username IS 'Username (email) del usuario propietario del contacto';
COMMENT ON COLUMN user_contacts.nombre IS 'Nombre del contacto';
COMMENT ON COLUMN user_contacts.email IS 'Email del contacto (para notificaciones por correo)';
COMMENT ON COLUMN user_contacts.telegram_chat_id IS 'Chat ID de Telegram (se obtiene cuando el contacto vincula su cuenta)';
COMMENT ON COLUMN user_contacts.telegram_username IS 'Username de Telegram del contacto';
COMMENT ON COLUMN user_contacts.tipo IS 'Tipo de contacto: gestor, cliente, proveedor, general';
COMMENT ON COLUMN user_contacts.activo IS 'Si el contacto está activo para recibir notificaciones';
