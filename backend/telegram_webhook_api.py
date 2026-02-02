# telegram_webhook_api.py
# Endpoint para recibir webhooks de Telegram

import logging
from fastapi import APIRouter, Request
from typing import Dict, Any

from services.telegram_service import handle_telegram_webhook

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.post("/webhook")
async def telegram_webhook(request: Request) -> Dict[str, Any]:
    """
    Endpoint para recibir actualizaciones de Telegram via webhook.
    
    Configurar en Telegram con:
    https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://tu-dominio.com/telegram/webhook
    """
    try:
        update = await request.json()
        logger.info(f"[TELEGRAM WEBHOOK] Recibida actualización: {update.get('update_id')}")
        
        result = await handle_telegram_webhook(update)
        return result
        
    except Exception as e:
        logger.error(f"[TELEGRAM WEBHOOK] Error: {e}")
        return {"ok": False, "error": str(e)}


@router.get("/webhook/status")
async def telegram_webhook_status():
    """
    Verifica el estado del bot de Telegram.
    """
    from services.telegram_service import get_bot_info
    
    try:
        info = await get_bot_info()
        return info
    except Exception as e:
        return {"ok": False, "error": str(e)}
