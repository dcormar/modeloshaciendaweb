# assistant_api.py
# API endpoints para el asistente IA overlay

import logging
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

# Cargar .env si está disponible (para asegurar que las variables estén disponibles)
try:
    from dotenv import load_dotenv
    # Intentar cargar .env desde el directorio backend
    current_file = Path(__file__)
    backend_dir = current_file.parent  # assistant_api.py está en backend/
    env_path = backend_dir / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)
    else:
        # Fallback: intentar cargar desde directorio actual
        load_dotenv(override=False)
except ImportError:
    # dotenv no disponible, continuar sin cargar (asumiendo que main.py ya lo cargó)
    pass

from auth import get_current_user, UserInDB
from services.assistant_agent import process_assistant_message

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/assistant", tags=["assistant"])


# ============================================================================
# MODELOS DE REQUEST/RESPONSE
# ============================================================================

class ChatMessage(BaseModel):
    role: str  # 'user' o 'assistant'
    content: str


class AssistantChatRequest(BaseModel):
    message: str
    conversation_history: Optional[List[ChatMessage]] = None


class AssistantChatResponse(BaseModel):
    response: str
    actions_executed: List[Dict[str, Any]] = []


class ContactCreate(BaseModel):
    nombre: str
    email: Optional[str] = None
    telegram_username: Optional[str] = None
    tipo: str = "general"


class ContactResponse(BaseModel):
    id: int
    nombre: str
    email: Optional[str]
    telegram_username: Optional[str]
    telegram_chat_id: Optional[str]
    tipo: str
    activo: bool


# ============================================================================
# ENDPOINTS DEL ASISTENTE
# ============================================================================

@router.post("/chat", response_model=AssistantChatResponse)
async def assistant_chat(
    request: AssistantChatRequest,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Procesa un mensaje del usuario y retorna la respuesta del asistente.
    
    El asistente puede:
    - Responder preguntas sobre la aplicación
    - Dar información sobre Hacienda y Seguridad Social
    - Enviar notificaciones por email o Telegram
    """
    logger.info("=" * 60)
    logger.info(f"[ASSISTANT API] Chat - Usuario: {current_user.username}")
    logger.info(f"[ASSISTANT API] Mensaje: {request.message[:100]}...")
    
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío")
    
    try:
        # Convertir historial a formato dict
        history = None
        if request.conversation_history:
            history = [{"role": msg.role, "content": msg.content} for msg in request.conversation_history]
        
        # Procesar con el agente
        result = await process_assistant_message(
            message=request.message.strip(),
            username=current_user.username,
            conversation_history=history
        )
        
        logger.info(f"[ASSISTANT API] Respuesta generada - {len(result.get('response', ''))} chars")
        logger.info("=" * 60)
        
        return AssistantChatResponse(
            response=result.get("response", ""),
            actions_executed=result.get("actions_executed", [])
        )
        
    except Exception as e:
        logger.exception(f"[ASSISTANT API] Error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando mensaje: {str(e)}"
        )


# ============================================================================
# ENDPOINTS DE CONTACTOS
# ============================================================================

@router.get("/contacts", response_model=List[ContactResponse])
async def list_contacts(
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Lista los contactos del usuario actual.
    """
    from services.supabase_rest import SupabaseREST
    
    try:
        sb = SupabaseREST()
        result = await sb.get(
            "user_contacts",
            "*",
            {"username": current_user.username}
        )
        # Ordenar por nombre (el ordenamiento debería hacerse en la query, pero por ahora lo hacemos aquí)
        result.sort(key=lambda x: x.get("nombre", ""))
        return result
        
    except Exception as e:
        logger.exception(f"[ASSISTANT API] Error listando contactos: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/contacts", response_model=ContactResponse)
async def create_contact(
    contact: ContactCreate,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Crea un nuevo contacto para el usuario.
    """
    from services.supabase_rest import SupabaseREST
    
    if not contact.email and not contact.telegram_username:
        raise HTTPException(
            status_code=400, 
            detail="Debe proporcionar al menos un email o username de Telegram"
        )
    
    try:
        sb = SupabaseREST()
        
        data = {
            "username": current_user.username,
            "nombre": contact.nombre,
            "email": contact.email,
            "telegram_username": contact.telegram_username,
            "tipo": contact.tipo,
            "activo": True
        }
        
        result = await sb.post("user_contacts", data)
        
        if result and len(result) > 0:
            logger.info(f"[ASSISTANT API] Contacto creado: {contact.nombre}")
            return result[0]
        else:
            raise HTTPException(status_code=500, detail="Error creando contacto")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[ASSISTANT API] Error creando contacto: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/contacts/{contact_id}", response_model=ContactResponse)
async def update_contact(
    contact_id: int,
    contact: ContactCreate,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Actualiza un contacto existente.
    """
    import urllib.parse
    from services.supabase_rest import SupabaseREST
    
    try:
        sb = SupabaseREST()
        
        # Verificar que el contacto pertenece al usuario
        existing = await sb.get_single(
            "user_contacts",
            "id",
            {"id": contact_id, "username": current_user.username}
        )
        
        if not existing:
            raise HTTPException(status_code=404, detail="Contacto no encontrado")
        
        data = {
            "nombre": contact.nombre,
            "email": contact.email,
            "telegram_username": contact.telegram_username,
            "tipo": contact.tipo
        }
        
        result = await sb.patch(
            "user_contacts",
            data,
            {"id": contact_id},
            return_representation=True
        )
        
        if result and len(result) > 0:
            logger.info(f"[ASSISTANT API] Contacto actualizado: {contact_id}")
            return result[0]
        else:
            raise HTTPException(status_code=500, detail="Error actualizando contacto")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[ASSISTANT API] Error actualizando contacto: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/contacts/{contact_id}")
async def delete_contact(
    contact_id: int,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Elimina (desactiva) un contacto.
    """
    import urllib.parse
    from services.supabase_rest import SupabaseREST
    
    try:
        sb = SupabaseREST()
        
        # Verificar que el contacto pertenece al usuario
        existing = await sb.get_single(
            "user_contacts",
            "id",
            {"id": contact_id, "username": current_user.username}
        )
        
        if not existing:
            raise HTTPException(status_code=404, detail="Contacto no encontrado")
        
        # Soft delete - marcar como inactivo
        await sb.patch(
            "user_contacts",
            {"activo": False},
            {"id": contact_id}
        )
        
        logger.info(f"[ASSISTANT API] Contacto eliminado: {contact_id}")
        return {"message": "Contacto eliminado"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[ASSISTANT API] Error eliminando contacto: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ENDPOINT DE VINCULACIÓN TELEGRAM
# ============================================================================

@router.post("/telegram/link")
async def generate_telegram_link_code(
    contact_id: int,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Genera un código único para vincular Telegram a un contacto.
    El contacto debe enviar este código al bot para vincular su cuenta.
    """
    import os
    import secrets
    import urllib.parse
    from services.supabase_rest import SupabaseREST
    
    TELEGRAM_BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "NementiumBot")
    
    try:
        sb = SupabaseREST()
        
        # Verificar que el contacto pertenece al usuario
        existing = await sb.get_single(
            "user_contacts",
            "id,nombre",
            {"id": contact_id, "username": current_user.username}
        )
        
        if not existing:
            raise HTTPException(status_code=404, detail="Contacto no encontrado")
        
        # Generar código único
        code = secrets.token_hex(4).upper()  # 8 caracteres hex
        
        # Guardar código en metadata del contacto
        await sb.patch(
            "user_contacts",
            {"metadata": {"telegram_link_code": code, "link_expires": "24h"}},
            {"id": contact_id}
        )
        
        bot_link = f"https://t.me/{TELEGRAM_BOT_USERNAME}?start={code}"
        
        return {
            "code": code,
            "bot_link": bot_link,
            "message": f"Comparte este enlace con {existing['nombre']} para vincular su Telegram"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[ASSISTANT API] Error generando código Telegram: {e}")
        raise HTTPException(status_code=500, detail=str(e))
