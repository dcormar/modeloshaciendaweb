# Documentos RAG

Esta carpeta contiene todos los documentos que se indexan en el sistema RAG del asistente.

## Estructura

Los documentos se organizan en subcarpetas según su tipo:

- **`app_manual/`** - Documentación de la aplicación (manual de usuario, guías de uso)
- **`hacienda/`** - Información sobre modelos tributarios, plazos, obligaciones fiscales
- **`seg_social/`** - Información sobre Seguridad Social para autónomos

## Cómo añadir documentos

1. Crea un archivo `.md` (Markdown) en la subcarpeta correspondiente
2. El nombre del archivo será usado como título del documento
3. Ejecuta el script de indexación:
   ```bash
   cd backend
   python scripts/index_rag_content.py
   ```

## Formato de documentos

- Usa formato Markdown (`.md`)
- El contenido puede incluir:
  - Títulos y subtítulos (`#`, `##`, `###`)
  - Listas (`-`, `*`)
  - Texto formateado
  - Enlaces

## Ejemplo

```
docs/ragdocuments/
├── app_manual/
│   └── manual_usuario.md
├── hacienda/
│   ├── modelos_tributarios.md
│   └── plazos_fiscales.md
└── seg_social/
    └── guia_autonomos.md
```

## Notas

- Los documentos se dividen automáticamente en chunks de ~1500 caracteres
- Cada chunk se indexa con su embedding para búsqueda semántica
- Si modificas un documento, vuelve a ejecutar el script para reindexar
