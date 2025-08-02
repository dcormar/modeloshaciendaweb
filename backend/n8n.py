import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List

router = APIRouter(prefix="/n8n", tags=["n8n"])

class WebhookPayload(BaseModel):
    # Define aquí los campos que esperas recibir
    data: dict

@router.post("/webhook")
async def trigger_n8n_webhook(payload: WebhookPayload):
    # Llama al webhook de n8n (ajusta la URL a la de tu flujo real)
    n8n_url = "http://localhost:5678/webhook/tu-flujo"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(n8n_url, json=payload.data)
            response.raise_for_status()
        return {"status": "ok", "n8n_response": response.json()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
