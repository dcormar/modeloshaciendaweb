# Especificación de Flujos n8n - Procesamiento de Facturas

Este documento describe los flujos de n8n necesarios para el procesamiento paso a paso de facturas.

## Variables de Entorno Requeridas

Añadir en el backend (`.env`):

```bash
N8N_WEBHOOK_PROCESS_AI=https://tu-n8n.com/webhook/process-ai
N8N_WEBHOOK_UPLOAD_DRIVE=https://tu-n8n.com/webhook/upload-drive
N8N_WEBHOOK_SECRET=tu-secreto-opcional
```

---

## Flujo 1: `process-ai` (Procesar con Gemini)

### Propósito
Recibe un archivo de factura, lo procesa con Google Gemini para extraer la información estructurada, y devuelve los datos al backend.

### Webhook URL
```
POST https://tu-n8n.com/webhook/process-ai
```

### Request (JSON que recibe)

```json
{
  "upload_id": "uuid-del-upload",
  "storage_path": "/tmp/uploads/user/factura/archivo.pdf",
  "filename": "archivo.pdf",
  "user": "email@example.com"
}
```

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `upload_id` | string (UUID) | ID único del upload en la tabla `uploads` |
| `storage_path` | string | Ruta completa al archivo en el servidor |
| `filename` | string | Nombre original del archivo |
| `user` | string | Email/username del usuario |

### Response Esperada (JSON)

#### Caso de éxito:
```json
{
  "success": true,
  "data": {
    "id_factura": "ES-2024-001",
    "fecha": "15/01/2024",
    "proveedor": "Empresa S.L.",
    "proveedor_vat": "B12345678",
    "importe_sin_iva": 100.00,
    "iva_porcentaje": 21,
    "importe_total": 121.00,
    "moneda": "EUR",
    "tipo_cambio": 1.0,
    "pais_origen": "ES",
    "categoria": "Software",
    "descripcion": "Licencia anual de software"
  },
  "error": null
}
```

#### Caso de error:
```json
{
  "success": false,
  "data": null,
  "error": "Gemini API timeout"
}
```

### Campos de `data` esperados

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `id_factura` | string | Sí | ID/número de la factura |
| `fecha` | string | Sí | Fecha en formato DD/MM/YYYY |
| `proveedor` | string | Sí | Nombre del emisor/proveedor |
| `proveedor_vat` | string | No | NIF/VAT del proveedor |
| `importe_sin_iva` | number | Sí | Importe base sin IVA |
| `iva_porcentaje` | number | No | Porcentaje de IVA |
| `importe_total` | number | Sí | Importe total con IVA |
| `moneda` | string | No | Código de moneda (EUR, USD, etc.) |
| `tipo_cambio` | number | No | Tipo de cambio a EUR |
| `pais_origen` | string | No | Código país (ES, FR, etc.) |
| `categoria` | string | No | Categoría del gasto |
| `descripcion` | string | No | Descripción/concepto |

### Estructura sugerida del flujo en n8n

```
1. [Webhook] Recibir petición
      ↓
2. [HTTP Request / File Read] Leer archivo desde storage_path
      ↓
3. [Google Gemini] Enviar archivo + prompt para extraer datos
      ↓
4. [Function] Parsear respuesta de Gemini a JSON estructurado
      ↓
5. [Respond to Webhook] Devolver { success, data, error }
```

### Prompt sugerido para Gemini

```
Analiza esta factura y extrae la siguiente información en formato JSON:
- id_factura: número o identificador de la factura
- fecha: fecha de la factura en formato DD/MM/YYYY
- proveedor: nombre de la empresa emisora
- proveedor_vat: NIF o VAT del proveedor
- importe_sin_iva: importe base sin impuestos (número decimal)
- iva_porcentaje: porcentaje de IVA aplicado (número)
- importe_total: importe total con IVA (número decimal)
- moneda: código de moneda (EUR, USD, etc.)
- pais_origen: código del país de origen (ES, FR, DE, etc.)
- categoria: categoría del gasto (Software, Hardware, Servicios, etc.)
- descripcion: descripción breve del concepto

Devuelve SOLO el JSON, sin texto adicional.
```

---

## Flujo 2: `upload-drive` (Subir a Google Drive)

### Propósito
Recibe un archivo y los datos extraídos por la IA, sube el archivo a Google Drive (opcionalmente renombrándolo), y devuelve la URL.

### Webhook URL
```
POST https://tu-n8n.com/webhook/upload-drive
```

### Request (JSON que recibe)

```json
{
  "upload_id": "uuid-del-upload",
  "storage_path": "/tmp/uploads/user/factura/archivo.pdf",
  "filename": "archivo.pdf",
  "user": "email@example.com",
  "ai_data": {
    "id_factura": "ES-2024-001",
    "fecha": "15/01/2024",
    "proveedor": "Empresa S.L."
  }
}
```

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `upload_id` | string (UUID) | ID único del upload |
| `storage_path` | string | Ruta completa al archivo |
| `filename` | string | Nombre original del archivo |
| `user` | string | Email/username del usuario |
| `ai_data` | object | Datos extraídos por la IA (para renombrar el archivo) |

### Response Esperada (JSON)

#### Caso de éxito:
```json
{
  "success": true,
  "drive_url": "https://drive.google.com/file/d/xxx/view",
  "drive_file_id": "xxx",
  "error": null
}
```

#### Caso de error:
```json
{
  "success": false,
  "drive_url": null,
  "drive_file_id": null,
  "error": "Error de autenticación con Google Drive"
}
```

### Estructura sugerida del flujo en n8n

```
1. [Webhook] Recibir petición
      ↓
2. [Function] Generar nombre de archivo
   (ej: "{fecha}_{proveedor}_{id_factura}.pdf")
      ↓
3. [HTTP Request / File Read] Leer archivo desde storage_path
      ↓
4. [Google Drive] Subir archivo a carpeta específica
      ↓
5. [Google Drive] Obtener URL pública del archivo
      ↓
6. [Respond to Webhook] Devolver { success, drive_url, drive_file_id, error }
```

### Configuración de Google Drive

1. **Carpeta destino**: Crear una carpeta en Drive para las facturas
2. **Permisos**: El archivo puede quedar privado o con enlace compartido
3. **Nombrado**: Usar los datos de `ai_data` para nombrar el archivo de forma descriptiva

Ejemplo de nombre de archivo generado:
```
2024-01-15_Empresa_SL_ES-2024-001.pdf
```

---

## Consideraciones de Seguridad

### Validación del webhook secret

Si se configura `N8N_WEBHOOK_SECRET`, el backend enviará el header:
```
X-Webhook-Secret: tu-secreto
```

En n8n, validar este header en el nodo Webhook antes de procesar.

### Timeout

- Los endpoints del backend tienen un timeout de 120 segundos para las llamadas a n8n
- Asegurarse de que los flujos de n8n completen dentro de este tiempo
- Si Gemini tarda mucho, considerar aumentar el timeout o usar procesamiento asíncrono

### Manejo de errores en n8n

1. Usar nodos "Error Trigger" para capturar errores
2. Siempre devolver `{ success: false, error: "mensaje" }` en caso de fallo
3. Loguear errores para debugging

---

## Testing

### Probar flujo process-ai

```bash
curl -X POST https://tu-n8n.com/webhook/process-ai \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: tu-secreto" \
  -d '{
    "upload_id": "test-123",
    "storage_path": "/tmp/uploads/test/factura.pdf",
    "filename": "factura.pdf",
    "user": "test@example.com"
  }'
```

### Probar flujo upload-drive

```bash
curl -X POST https://tu-n8n.com/webhook/upload-drive \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: tu-secreto" \
  -d '{
    "upload_id": "test-123",
    "storage_path": "/tmp/uploads/test/factura.pdf",
    "filename": "factura.pdf",
    "user": "test@example.com",
    "ai_data": {
      "id_factura": "TEST-001",
      "fecha": "15/01/2024",
      "proveedor": "Test Company"
    }
  }'
```

