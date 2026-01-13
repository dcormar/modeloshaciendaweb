# Mejoras Futuras - Corporate Rocket

## Google Drive - Migración a Shared Drives (Google Workspace)

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

*Última actualización: 2026-01-13*
