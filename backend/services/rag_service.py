# rag_service.py
# Servicio RAG (Retrieval Augmented Generation) para el asistente

import os
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import json

import openai
from services.supabase_rest import SupabaseREST

# Cargar .env si está disponible (para scripts que se ejecutan directamente)
try:
    from dotenv import load_dotenv
    # Intentar cargar .env desde el directorio backend
    # Si este módulo está en backend/services/, el .env está en backend/
    current_file = Path(__file__)
    backend_dir = current_file.parent.parent  # backend/services/ -> backend/
    env_path = backend_dir / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)
    else:
        # Fallback: intentar cargar desde directorio actual
        load_dotenv(override=False)
except ImportError:
    # dotenv no disponible, continuar sin cargar
    pass

logger = logging.getLogger(__name__)

# Configuración (después de cargar .env)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()

# Modelo de embeddings
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536


def get_supabase_client() -> SupabaseREST:
    """Obtiene cliente de Supabase REST."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise ValueError("SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY deben estar configurados")
    
    try:
        return SupabaseREST()
    except Exception as e:
        import traceback
        print(f"\n❌ [ERROR] Error creando cliente Supabase:")
        traceback.print_exc()
        
        error_msg = str(e)
        if "Invalid API key" in error_msg or "Expected 3 parts in JWT" in error_msg:
            print(f"\n💡 [INFO] Problema con la key de Supabase:")
            print(f"   Verifica en Supabase Dashboard > Settings > API que la key sea correcta")
        raise


def get_openai_client() -> openai.OpenAI:
    """Obtiene cliente de OpenAI."""
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY debe estar configurada")
    
    # Limpiar la key
    clean_key = OPENAI_API_KEY.strip().replace('\n', '').replace('\r', '')
    
    if not clean_key.startswith('sk-'):
        raise ValueError(f"OPENAI_API_KEY no tiene formato válido. Debe empezar con 'sk-'")
    
    return openai.OpenAI(api_key=clean_key)


async def generate_embedding(text: str) -> List[float]:
    """
    Genera embedding para un texto usando OpenAI.
    
    Args:
        text: Texto a convertir en embedding
        
    Returns:
        Lista de floats representando el embedding
    """
    import traceback
    
    if not text or not text.strip():
        raise ValueError("El texto no puede estar vacío")
    
    # Verificar que la API key esté configurada y tenga formato correcto
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY no está configurada")
    
    # Limpiar la key (eliminar espacios, saltos de línea, etc.)
    clean_key = OPENAI_API_KEY.strip().replace('\n', '').replace('\r', '')
    
    # Verificar formato básico (debe empezar con sk-)
    if not clean_key.startswith('sk-'):
        raise ValueError(
            f"OPENAI_API_KEY no tiene formato válido. Debe empezar con 'sk-'."
        )
    
    try:
        # Usar la key limpia
        client = openai.OpenAI(api_key=clean_key)
        
        logger.debug(f"[RAG] Generando embedding con modelo {EMBEDDING_MODEL}")
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text.strip(),
            dimensions=EMBEDDING_DIMENSIONS
        )
        embedding = response.data[0].embedding
        logger.debug(f"[RAG] Embedding generado para texto de {len(text)} caracteres")
        return embedding
    except openai.AuthenticationError as e:
        logger.error(f"[RAG] Error de autenticación con OpenAI: {e}")
        print(f"\n❌ [ERROR] Traceback completo:")
        traceback.print_exc()
        error_msg = str(e)
        if "Invalid API key" in error_msg:
            raise ValueError(
                f"API key de OpenAI inválida o sin permisos. "
                f"Verifica que:\n"
                f"  1. La key esté correcta en tu .env\n"
                f"  2. La key tenga permisos para embeddings\n"
                f"  3. No haya espacios o saltos de línea en la key\n"
                f"  4. La key no haya expirado\n"
                f"Error: {error_msg}"
            )
        raise ValueError(f"Error de autenticación: {error_msg}")
    except openai.PermissionDeniedError as e:
        logger.error(f"[RAG] Permisos insuficientes: {e}")
        print(f"\n❌ [ERROR] Traceback completo:")
        traceback.print_exc()
        raise ValueError(
            f"La API key no tiene permisos para usar embeddings. "
            f"Verifica los permisos de tu key en https://platform.openai.com/api-keys"
        )
    except Exception as e:
        logger.error(f"[RAG] Error generando embedding: {e}")
        print(f"\n❌ [ERROR] Traceback completo:")
        traceback.print_exc()
        raise ValueError(f"Error generando embedding: {str(e)}")


async def index_document(
    content: str,
    doc_type: str,
    title: Optional[str] = None,
    source: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    chunk_index: int = 0
) -> int:
    """
    Indexa un documento en el sistema RAG.
    
    Args:
        content: Contenido del documento
        doc_type: Tipo de documento ('app_manual', 'hacienda', 'seg_social')
        title: Título del documento
        source: Fuente/URL del documento
        metadata: Metadatos adicionales
        chunk_index: Índice del chunk si el documento fue dividido
        
    Returns:
        ID del documento insertado
    """
    if not content or not content.strip():
        raise ValueError("El contenido no puede estar vacío")
    
    if doc_type not in ['app_manual', 'hacienda', 'seg_social']:
        raise ValueError(f"Tipo de documento inválido: {doc_type}")
    
    try:
        # Generar embedding
        embedding = await generate_embedding(content)
        
        # Insertar en Supabase
        sb = get_supabase_client()
        
        data = {
            "content": content.strip(),
            "embedding": embedding,
            "doc_type": doc_type,
            "title": title,
            "source": source,
            "metadata": metadata or {},
            "chunk_index": chunk_index
        }
        
        result = await sb.post("rag_documents", data)
        
        if result and len(result) > 0:
            doc_id = result[0].get("id")
            logger.info(f"[RAG] Documento indexado: id={doc_id}, type={doc_type}, title={title}")
            return doc_id
        else:
            raise ValueError("No se pudo insertar el documento")
            
    except Exception as e:
        logger.error(f"[RAG] Error indexando documento: {e}")
        raise ValueError(f"Error indexando documento: {str(e)}")


async def search_documents(
    query: str,
    doc_type: Optional[str] = None,
    match_threshold: float = 0.5,
    match_count: int = 5
) -> List[Dict[str, Any]]:
    """
    Busca documentos similares usando búsqueda semántica.
    
    Args:
        query: Consulta de búsqueda
        doc_type: Filtrar por tipo de documento (opcional)
        match_threshold: Umbral mínimo de similitud (0-1)
        match_count: Número máximo de resultados
        
    Returns:
        Lista de documentos con su similitud
    """
    if not query or not query.strip():
        raise ValueError("La consulta no puede estar vacía")
    
    try:
        # Generar embedding de la consulta
        query_embedding = await generate_embedding(query)
        
        # Buscar en Supabase usando la función RPC
        sb = get_supabase_client()
        
        result = await sb.rpc(
            "search_rag_documents",
            {
                "query_embedding": query_embedding,
                "match_threshold": match_threshold,
                "match_count": match_count,
                "filter_doc_type": doc_type
            }
        )
        
        documents = result if isinstance(result, list) else []
        logger.info(f"[RAG] Búsqueda completada: query='{query[:50]}...', encontrados={len(documents)}")
        
        return documents
        
    except Exception as e:
        logger.error(f"[RAG] Error buscando documentos: {e}")
        raise ValueError(f"Error buscando documentos: {str(e)}")


async def delete_document(doc_id: int) -> bool:
    """
    Elimina un documento del sistema RAG.
    
    Args:
        doc_id: ID del documento a eliminar
        
    Returns:
        True si se eliminó correctamente
    """
    try:
        sb = get_supabase_client()
        result = await sb.delete("rag_documents", {"id": f"eq.{doc_id}"})
        
        if result:
            logger.info(f"[RAG] Documento eliminado: id={doc_id}")
            return True
        return False
        
    except Exception as e:
        logger.error(f"[RAG] Error eliminando documento: {e}")
        raise ValueError(f"Error eliminando documento: {str(e)}")


async def list_documents(
    doc_type: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Lista documentos indexados.
    
    Args:
        doc_type: Filtrar por tipo (opcional)
        limit: Límite de resultados
        
    Returns:
        Lista de documentos (sin embeddings)
    """
    try:
        sb = get_supabase_client()
        
        params = {}
        if doc_type:
            params["doc_type"] = f"eq.{doc_type}"
        
        # Nota: El ordenamiento y límite deberían hacerse en la query, pero por ahora
        # obtenemos todos y ordenamos en memoria. Para mejor rendimiento, se podría
        # añadir soporte para order y limit en el wrapper.
        result = await sb.get(
            "rag_documents",
            "id,title,doc_type,source,chunk_index,created_at",
            params
        )
        
        # Ordenar por created_at descendente y limitar
        result.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return result[:limit]
        
    except Exception as e:
        logger.error(f"[RAG] Error listando documentos: {e}")
        raise ValueError(f"Error listando documentos: {str(e)}")


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """
    Divide un texto largo en chunks más pequeños.
    
    Args:
        text: Texto a dividir
        chunk_size: Tamaño máximo de cada chunk en caracteres
        overlap: Solapamiento entre chunks
        
    Returns:
        Lista de chunks
    """
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        
        # Intentar cortar en un salto de línea o espacio
        if end < len(text):
            # Buscar salto de línea cerca del final
            newline_pos = text.rfind('\n', start + chunk_size - 100, end)
            if newline_pos > start:
                end = newline_pos + 1
            else:
                # Buscar espacio
                space_pos = text.rfind(' ', start + chunk_size - 50, end)
                if space_pos > start:
                    end = space_pos + 1
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        start = end - overlap if end < len(text) else len(text)
    
    return chunks


async def index_document_with_chunking(
    content: str,
    doc_type: str,
    title: Optional[str] = None,
    source: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    chunk_size: int = 1000,
    overlap: int = 200
) -> List[int]:
    """
    Indexa un documento largo dividiéndolo en chunks.
    
    Args:
        content: Contenido del documento
        doc_type: Tipo de documento
        title: Título del documento
        source: Fuente del documento
        metadata: Metadatos adicionales
        chunk_size: Tamaño de cada chunk
        overlap: Solapamiento entre chunks
        
    Returns:
        Lista de IDs de los documentos insertados
    """
    chunks = chunk_text(content, chunk_size, overlap)
    doc_ids = []
    
    for i, chunk in enumerate(chunks):
        chunk_title = f"{title} (parte {i + 1}/{len(chunks)})" if title and len(chunks) > 1 else title
        
        doc_id = await index_document(
            content=chunk,
            doc_type=doc_type,
            title=chunk_title,
            source=source,
            metadata={**(metadata or {}), "total_chunks": len(chunks)},
            chunk_index=i
        )
        doc_ids.append(doc_id)
    
    logger.info(f"[RAG] Documento indexado en {len(chunks)} chunks: {title}")
    return doc_ids
