from fastapi import APIRouter, HTTPException, Depends
import httpx, os, logging
from pydantic import BaseModel
from typing import List, Optional
from auth import get_current_user, UserInDB
import certifi

router = APIRouter(prefix="/api/uploads", tags=["uploads"])
logger = logging.getLogger(__name__)

class UploadItem(BaseModel):
    id: str
    fecha: str
    tipo: str
    descripcion: str
    tam_bytes: Optional[int]
    storage_path: Optional[str]
    status: Optional[str] = None
    original_filename: str

class UploadsResponse(BaseModel):
    items: List[UploadItem]

@router.get("/historico", response_model=UploadsResponse)
async def uploads_historico(limit: int = 20, tz: str = "Europe/Madrid"):
    supabase_url = (os.getenv("SUPABASE_URL") or "").strip()
    supabase_key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not supabase_url or not supabase_key:
        raise HTTPException(status_code=500, detail="Config supabase incompleta")

    rpc_url = f"{supabase_url}/rest/v1/rpc/uploads_historico"
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Prefer": "return=representation",
    }
    payload = {"p_limit": limit, "p_tz": tz}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(rpc_url, headers=headers, json=payload)

    if resp.status_code != 200:
        logger.error("📛 RPC uploads_historico falló %s: %s", resp.status_code, resp.text)
        raise HTTPException(status_code=502, detail=resp.text)

    rows = resp.json() or []
    logger.info("📦 RPC uploads_historico devolvió %d filas", len(rows))
    if rows:
        logger.debug("🔍 Primera fila: %s", rows[0])
    return {
        "items": [
            {
                "id": r["id"],
                "fecha": r["fecha"],
                "tipo": r["tipo"],
                "descripcion": r["descripcion"] or "Pending Processing",
                "tam_bytes": r.get("tam_bytes"),
                "storage_path": r.get("storage_path"),
                "status": r.get("status"),
                "original_filename":r.get("original_filename"),
            }
            for r in rows
        ]
    }

@router.get("/{upload_id}/factura")
async def get_factura_from_upload(
    upload_id: str,
    current_user: UserInDB = Depends(get_current_user),
):
    """
    Obtiene los detalles de la factura asociada a un upload.
    """
    supabase_url = (os.getenv("SUPABASE_URL") or "").strip()
    supabase_key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not supabase_url or not supabase_key:
        raise HTTPException(status_code=500, detail="Config supabase incompleta")

    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30, verify=certifi.where()) as client:
            # Primero obtener el factura_id del upload
            upload_resp = await client.get(
                f"{supabase_url}/rest/v1/uploads?id=eq.{upload_id}&select=factura_id,tipo",
                headers=headers
            )
            
            if upload_resp.status_code != 200:
                raise HTTPException(status_code=502, detail=f"Error obteniendo upload: {upload_resp.text}")
            
            upload_rows = upload_resp.json()
            if not upload_rows:
                raise HTTPException(status_code=404, detail="Upload no encontrado")
            
            upload = upload_rows[0]
            factura_id = upload.get("factura_id")
            tipo = upload.get("tipo")
            
            # Si no es una factura, retornar null
            if tipo != "FACTURA":
                return {"factura": None, "factura_id": None}
            
            # Si no tiene factura_id, retornar null pero con factura_id None
            if not factura_id:
                return {"factura": None, "factura_id": None}
            
            # Obtener los detalles de la factura
            factura_resp = await client.get(
                f"{supabase_url}/rest/v1/facturas?id=eq.{factura_id}",
                headers=headers
            )
            
            if factura_resp.status_code != 200:
                raise HTTPException(status_code=502, detail=f"Error obteniendo factura: {factura_resp.text}")
            
            factura_rows = factura_resp.json()
            if not factura_rows:
                return {"factura": None, "factura_id": factura_id}
            
            return {"factura": factura_rows[0], "factura_id": factura_id}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error obteniendo factura desde upload %s", upload_id)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")