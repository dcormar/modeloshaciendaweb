# Mejoras Futuras - Corporate Rocket

## 1. Google Drive - Migración a Shared Drives (Google Workspace)

**Estado**: Pendiente  
**Prioridad**: Media  
**Requisito**: Cuenta de Google Workspace (empresa/educación)

### Problema actual

Actualmente se usa OAuth2 con la cuenta personal del usuario para subir archivos a Google Drive. Esto funciona pero tiene limitaciones:

- El usuario debe autorizar la aplicación manualmente
- Los archivos se guardan en el Drive personal del usuario
- No es escalable para múltiples usuarios

### Solución propuesta

Migrar a **Shared Drives** (Drives compartidos) cuando se disponga de una cuenta de Google Workspace:

1. Crear un Shared Drive en Google Workspace
2. Dar acceso a la cuenta de servicio como "Content Manager"
3. Modificar `drive_service.py` para usar `supportsAllDrives=True`

### Cambios necesarios en el código

```python
# En drive_service.py

# Añadir al crear el archivo:
file = service.files().create(
    body=file_metadata,
    media_body=media,
    fields="id, webViewLink",
    supportsAllDrives=True  # <-- Añadir esto
).execute()

# Añadir al configurar permisos:
service.permissions().create(
    fileId=file_id,
    body={"role": "reader", "type": "anyone"},
    supportsAllDrives=True  # <-- Añadir esto
).execute()
```

### Beneficios

- No requiere autorización del usuario
- Archivos centralizados en un Drive compartido de la empresa
- Escalable para múltiples usuarios
- Mejor control de acceso y auditoría

### Referencias

- [Shared Drives API](https://developers.google.com/workspace/drive/api/guides/about-shareddrives)
- [Manage Shared Drives](https://developers.google.com/workspace/drive/api/guides/manage-shareddrives)

---

1. Agente de categorización inteligente
En lugar de que Gemini solo extraiga datos, un agente podría:
Categorizar automáticamente el gasto comparando con categorías existentes en tu BD
Detectar proveedores recurrentes y sugerir datos basados en histórico
Identificar facturas duplicadas antes de procesarlas
2. Validación y corrección automática
Un agente con herramientas (tools) que pueda:
Validar el NIF/VAT consultando APIs externas
Corregir errores de OCR comparando con datos conocidos
Verificar tipos de cambio consultando APIs de divisas
3. Chat conversacional sobre facturas
Un chatbot interno que use RAG (Retrieval Augmented Generation):
"¿Cuánto gasté en software el último trimestre?"
"Muéstrame las facturas pendientes de pago"
"Compara los gastos de este mes con el anterior"
4. Procesamiento de múltiples formatos
Extender a otros documentos usando diferentes chains:
Contratos (extraer fechas, partes, obligaciones)
Recibos de tarjeta
Extractos bancarios
Tickets de compra
5. Flujo de aprobación inteligente
Un agente que decida automáticamente:
Si una factura necesita aprobación manual (importe alto, proveedor nuevo)
A quién asignarla según el departamento/categoría
Alertar sobre anomalías (factura duplicada, importe inusual)
6. Multi-LLM / Fallback
LangChain facilita:
Usar Gemini para extracción y Claude para validación
Fallback automático si un proveedor falla
A/B testing entre modelos

---

*Última actualización: 2026-01-16*
