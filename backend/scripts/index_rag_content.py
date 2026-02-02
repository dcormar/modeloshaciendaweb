#!/usr/bin/env python3
"""
Script para indexar contenido RAG desde archivos markdown.
Lee recursivamente todos los archivos .md de docs/ragdocuments/ y sus subcarpetas.

Ejecutar desde el directorio backend:
    python scripts/index_rag_content.py
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Dict, List

# Añadir directorio padre al path
# __file__ = backend/scripts/index_rag_content.py
# parent = backend/scripts/
# parent.parent = backend/
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# IMPORTANTE: Cargar .env ANTES de importar servicios
# porque los servicios leen las variables al importarse
from dotenv import load_dotenv
env_path = backend_dir / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)
else:
    # Intentar cargar desde el directorio actual también
    load_dotenv(override=True)

# Ahora importar servicios (ya tienen acceso a las variables del .env)
from services.rag_service import index_document_with_chunking, list_documents


# Mapeo de nombres de carpetas a tipos de documento
FOLDER_TO_DOC_TYPE: Dict[str, str] = {
    "app_manual": "app_manual",
    "hacienda": "hacienda",
    "seg_social": "seg_social",
    "seguridad_social": "seg_social",  # Alias
}


def get_doc_type_from_path(file_path: Path, base_path: Path) -> str:
    """
    Determina el tipo de documento basándose en la ruta.
    
    Args:
        file_path: Ruta completa del archivo
        base_path: Ruta base (docs/ragdocuments)
    
    Returns:
        Tipo de documento (app_manual, hacienda, seg_social)
    """
    # Obtener ruta relativa
    rel_path = file_path.relative_to(base_path)
    
    # Obtener primera carpeta
    if len(rel_path.parts) > 1:
        folder_name = rel_path.parts[0]
        return FOLDER_TO_DOC_TYPE.get(folder_name, "app_manual")
    
    return "app_manual"  # Default


def find_markdown_files(base_path: Path) -> List[Path]:
    """
    Encuentra todos los archivos .md recursivamente en subcarpetas de base_path.
    Excluye archivos que estén directamente en la raíz de base_path.
    
    Args:
        base_path: Directorio base para buscar
    
    Returns:
        Lista de rutas de archivos .md (solo en subcarpetas)
    """
    markdown_files = []
    
    if not base_path.exists():
        print(f"⚠️  El directorio {base_path} no existe. Creándolo...")
        base_path.mkdir(parents=True, exist_ok=True)
        return []
    
    # Buscar recursivamente, pero excluir archivos en la raíz
    for file_path in base_path.rglob("*.md"):
        if file_path.is_file():
            # Obtener ruta relativa desde base_path
            rel_path = file_path.relative_to(base_path)
            # Solo incluir si está en una subcarpeta (tiene al menos una carpeta padre)
            if len(rel_path.parts) > 1:
                markdown_files.append(file_path)
    
    return sorted(markdown_files)


async def index_file(file_path: Path, base_path: Path, chunk_size: int = 1500, overlap: int = 200) -> List[int]:
    """
    Indexa un archivo markdown.
    
    Args:
        file_path: Ruta del archivo
        base_path: Ruta base para calcular rutas relativas
        chunk_size: Tamaño de chunk
        overlap: Solapamiento entre chunks
    
    Returns:
        Lista de IDs de documentos indexados
    """
    try:
        # Leer contenido
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if not content.strip():
            print(f"   ⚠️  Archivo vacío: {file_path.name}")
            return []
        
        # Determinar tipo y título
        doc_type = get_doc_type_from_path(file_path, base_path)
        title = file_path.stem.replace('_', ' ').title()
        
        # Ruta relativa para source
        rel_path = file_path.relative_to(base_path.parent)
        source = str(rel_path).replace('\\', '/')
        
        print(f"   📄 {file_path.name} ({doc_type})")
        
        # Indexar
        doc_ids = await index_document_with_chunking(
            content=content,
            doc_type=doc_type,
            title=title,
            source=source,
            metadata={"file": file_path.name, "folder": file_path.parent.name},
            chunk_size=chunk_size,
            overlap=overlap
        )
        
        return doc_ids
        
    except Exception as e:
        import traceback
        print(f"   ❌ Error indexando {file_path.name}: {e}")
        print(f"\n   📋 Traceback completo:")
        traceback.print_exc()
        return []


async def main():
    """Indexa todo el contenido RAG desde archivos markdown."""
    print("=" * 60)
    print("Indexando contenido RAG desde archivos markdown...")
    print("=" * 60)
    
    # Verificar variables de entorno necesarias
    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    
    # Verificar variables de entorno (sin mostrar valores)
    if not supabase_url or not supabase_key:
        print("\n❌ ERROR: Variables de entorno de Supabase no configuradas")
        print(f"\nVerifica que el archivo .env esté en: {backend_dir / '.env'}")
        print("Y que contenga:")
        print("  SUPABASE_URL=tu_url_de_supabase")
        print("  SUPABASE_SERVICE_ROLE_KEY=tu_service_role_key")
        return
    
    if not openai_key:
        print("\n❌ ERROR: OPENAI_API_KEY no configurada")
        print(f"\nVerifica que el archivo .env esté en: {backend_dir / '.env'}")
        print("Y que contenga:")
        print("  OPENAI_API_KEY=sk-tu-api-key")
        return
    
    print("✅ Variables de entorno configuradas correctamente")
    
    # Determinar ruta base
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    rag_documents_path = project_root / "docs" / "ragdocuments"
    
    print(f"\n📁 Directorio base: {rag_documents_path}")
    
    # Verificar documentos existentes (opcional, no falla si no hay conexión)
    existing = []
    try:
        existing = await list_documents()
        print(f"\n📊 Documentos existentes en RAG: {len(existing)}")
    except Exception as e:
        print(f"\n⚠️  No se pudo verificar documentos existentes: {e}")
        print("   Continuando con la indexación...")
    
    if existing:
        print("\n⚠️  Ya hay contenido indexado.")
        print("Opciones:")
        print("  1. Continuar e indexar nuevos documentos (puede duplicar)")
        print("  2. Cancelar")
        response = input("\n¿Continuar? (s/n): ").strip().lower()
        if response != 's':
            print("❌ Cancelado.")
            return
    
    # Buscar archivos markdown
    markdown_files = find_markdown_files(rag_documents_path)
    
    if not markdown_files:
        print(f"\n⚠️  No se encontraron archivos .md en {rag_documents_path}")
        print("   Crea archivos .md en las subcarpetas:")
        print("   - docs/ragdocuments/app_manual/")
        print("   - docs/ragdocuments/hacienda/")
        print("   - docs/ragdocuments/seg_social/")
        return
    
    print(f"\n📚 Encontrados {len(markdown_files)} archivo(s) markdown:")
    for f in markdown_files:
        rel_path = f.relative_to(rag_documents_path)
        print(f"   - {rel_path}")
    
    # Indexar cada archivo
    print("\n" + "=" * 60)
    print("Indexando archivos...")
    print("=" * 60)
    
    total_docs = 0
    total_chunks = 0
    
    for i, file_path in enumerate(markdown_files, 1):
        rel_path = file_path.relative_to(rag_documents_path)
        print(f"\n[{i}/{len(markdown_files)}] {rel_path}")
        
        doc_ids = await index_file(file_path, rag_documents_path)
        
        if doc_ids:
            total_chunks += len(doc_ids)
            total_docs += 1
            print(f"   ✅ {len(doc_ids)} chunk(s) indexado(s)")
        else:
            print(f"   ⚠️  No se indexaron chunks")
    
    # Resumen
    print("\n" + "=" * 60)
    print("✅ Indexación completada")
    print("=" * 60)
    print(f"📄 Archivos procesados: {total_docs}/{len(markdown_files)}")
    print(f"🧩 Chunks totales indexados: {total_chunks}")
    print(f"📊 Total documentos en RAG: {len(existing) + total_chunks}")


if __name__ == "__main__":
    asyncio.run(main())
