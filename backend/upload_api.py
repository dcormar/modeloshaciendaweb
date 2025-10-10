# upload_api.py
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from pathlib import Path
import shutil, re, os, logging, hashlib
import httpx
from auth import get_current_user, UserInDB

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/upload", tags=["upload"])

def sanitize_folder(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9@\.\-_]", "_", name or "user")

def get_upload_base() -> Path:
    return Path(os.getenv("UPLOAD_BASE", "/tmp/uploads"))

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").strip()
SUPABASE_KEY = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()

def supabase_headers():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise HTTPException(status_code=500, detail="Configura SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY")
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

@router.post("/", status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    tipo: str = Form(...),  # "factura" | "venta"
    current_user: UserInDB = Depends(get_current_user),
):
    base = get_upload_base()
    base.mkdir(parents=True, exist_ok=True)

    tipo = (tipo or "").lower().strip()
    if tipo not in ("factura", "venta"):
        raise HTTPException(status_code=400, detail="tipo debe ser 'factura' o 'venta'")

    # Validación simple por extensión (podrías mejorar con magic/mimetype)
    fname_lower = (file.filename or "").lower()
    if not (fname_lower.endswith(".pdf") or fname_lower.endswith(".xlsx")):
        raise HTTPException(status_code=400, detail="Solo se admiten PDF o XLSX")

    # Guardar a disco
    user_folder = base / sanitize_folder(current_user.username) / tipo
    user_folder.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^\w\-.]+", "_", file.filename or "file")
    dest_file = user_folder / safe_name

    logger.info("UPLOAD_BASE=%s  -> guardando en: %s", str(base), str(dest_file))

    try:
        with dest_file.open("wb") as out:
            shutil.copyfileobj(file.file, out)
    except Exception:
        logger.exception("Error guardando archivo en disco")
        raise HTTPException(status_code=500, detail="Error guardando archivo")

    if not dest_file.exists():
        logger.warning("⚠️ No se encontró el archivo tras escribirlo: %s", dest_file)
        raise HTTPException(status_code=500, detail="No se pudo verificar el archivo en disco")

    # Metadatos del fichero
    size_bytes = dest_file.stat().st_size
    mime_type = file.content_type or ("application/pdf" if fname_lower.endswith(".pdf") else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    sha256 = sha256_file(dest_file)
    storage_path = str(dest_file)

    # Insertar en Supabase según tipo
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            if tipo == "venta":
                # Insert en public.ventas_uploads
                payload = {
                    "status": "UPLOADED",
                    "original_filename": safe_name,   # requiere columna nueva (ver SQL)
                    "storage_path": storage_path,     # requiere columna nueva
                    "mime_type": mime_type,           # requiere columna nueva
                    "file_size_bytes": size_bytes,    # requiere columna nueva
                    "sha256": sha256,                 # requiere columna nueva (unique opcional)
                    "notes": f"Subido por {current_user.username}",
                }
                resp = await client.post(
                    f"{SUPABASE_URL}/rest/v1/ventas_uploads",
                    headers=supabase_headers(),
                    json=payload
                )
            else:
                # Insert en public.uploads (tipo FACTURA)
                payload = {
                    "tipo": "FACTURA",
                    "status": "UPLOADED",             # requiere columna nueva en uploads
                    "original_filename": safe_name,
                    "storage_path": storage_path,
                    "mime_type": mime_type,
                    "file_size_bytes": size_bytes,
                    "sha256": sha256,
                    "source": "manual",
                    # factura_id se rellenará cuando el flujo n8n cree la fila en facturas
                    # ventas_batch_id es solo para tipo VENTA (no aplica aquí)
                }
                resp = await client.post(
                    f"{SUPABASE_URL}/rest/v1/uploads",
                    headers=supabase_headers(),
                    json=payload
                )

        if resp.status_code not in (200, 201):
            logger.error("Insert Supabase falló %s: %s", resp.status_code, resp.text)
            raise HTTPException(status_code=502, detail=f"Error insertando metadatos en BD: {resp.text}")

        row = resp.json()[0] if isinstance(resp.json(), list) and resp.json() else resp.json()

    except httpx.RequestError as e:
        logger.exception("Error de red con Supabase")
        raise HTTPException(status_code=502, detail=f"Error de red con Supabase: {e}") from e

    return {
        "ok": True,
        "path": storage_path,
        "filename": safe_name,
        "tipo": tipo,
        "usuario": current_user.username,
        "db_row": row,  # devolvemos lo insertado por comodidad
    }