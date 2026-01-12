-- Script SQL para crear la tabla FACTURAS_GENERADAS en Supabase
-- Ejecutar este script en el SQL Editor de Supabase

CREATE TABLE IF NOT EXISTS facturas_generadas (
    id BIGSERIAL PRIMARY KEY,
    numero_factura TEXT NOT NULL UNIQUE,
    fecha_emision DATE NOT NULL,
    fecha_emision_dt TIMESTAMPTZ,
    cliente_nombre TEXT NOT NULL,
    cliente_nif TEXT NOT NULL,
    cliente_direccion TEXT NOT NULL,
    concepto TEXT NOT NULL,
    base_imponible NUMERIC(12, 2) NOT NULL,
    tipo_iva NUMERIC(5, 2) NOT NULL,
    importe_iva NUMERIC(12, 2) NOT NULL,
    total NUMERIC(12, 2) NOT NULL,
    moneda TEXT NOT NULL DEFAULT 'EUR',
    notas TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT
);

-- Crear índice para búsquedas por número de factura (aunque ya es UNIQUE, esto ayuda en consultas)
CREATE INDEX IF NOT EXISTS idx_facturas_generadas_numero_factura ON facturas_generadas(numero_factura);

-- Crear índice para búsquedas por fecha
CREATE INDEX IF NOT EXISTS idx_facturas_generadas_fecha_emision ON facturas_generadas(fecha_emision);

-- Crear índice para búsquedas por cliente
CREATE INDEX IF NOT EXISTS idx_facturas_generadas_cliente_nif ON facturas_generadas(cliente_nif);

-- Comentarios en las columnas (opcional, ayuda en la documentación)
COMMENT ON TABLE facturas_generadas IS 'Tabla para almacenar facturas generadas (facturas de venta)';
COMMENT ON COLUMN facturas_generadas.numero_factura IS 'UUID único generado automáticamente por el backend';
COMMENT ON COLUMN facturas_generadas.fecha_emision IS 'Fecha de emisión de la factura';
COMMENT ON COLUMN facturas_generadas.fecha_emision_dt IS 'Fecha de emisión como timestamp para consultas';
COMMENT ON COLUMN facturas_generadas.created_by IS 'Usuario que creó la factura';

