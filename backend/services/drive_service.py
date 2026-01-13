# drive_service.py
# Servicio para subir archivos a Google Drive

import os
import logging
import re
from pathlib import Path
from typing import Optional
from datetime import datetime

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# Configuración
GOOGLE_DRIVE_CREDENTIALS_FILE = os.getenv("GOOGLE_DRIVE_CREDENTIALS_FILE", "").strip()
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "").strip()

# Scopes necesarios para subir archivos
SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def _get_drive_service():
    """
    Crea y devuelve un servicio de Google Drive autenticado.
    """
    if not GOOGLE_DRIVE_CREDENTIALS_FILE:
        raise ValueError("GOOGLE_DRIVE_CREDENTIALS_FILE no está configurada")
    
    if not Path(GOOGLE_DRIVE_CREDENTIALS_FILE).exists():
        raise FileNotFoundError(
            f"Archivo de credenciales no encontrado: {GOOGLE_DRIVE_CREDENTIALS_FILE}"
        )
    
    try:
        credentials = service_account.Credentials.from_service_account_file(
            GOOGLE_DRIVE_CREDENTIALS_FILE,
            scopes=SCOPES
        )
        service = build("drive", "v3", credentials=credentials)
        return service
    except Exception as e:
        logger.error(f"Error inicializando servicio de Drive: {e}")
        raise ValueError(f"Error de autenticación con Google Drive: {str(e)}")


def _generate_file_name(original_name: str, ai_data: dict) -> str:
    """
    Genera un nombre descriptivo para el archivo basándose en los datos extraídos.
    
    Formato: YYYY-MM-DD_Proveedor_ID-Factura.pdf
    Ejemplo: 2024-01-15_Empresa_SL_FAC-2024-001.pdf
    """
    # Extraer datos
    fecha_str = ai_data.get("fecha", "")
    proveedor = ai_data.get("proveedor", "")
    id_factura = ai_data.get("id_factura", "")
    
    # Convertir fecha de DD/MM/YYYY a YYYY-MM-DD
    try:
        if fecha_str:
            dt = datetime.strptime(fecha_str, "%d/%m/%Y")
            fecha_iso = dt.strftime("%Y-%m-%d")
        else:
            fecha_iso = datetime.now().strftime("%Y-%m-%d")
    except ValueError:
        fecha_iso = datetime.now().strftime("%Y-%m-%d")
    
    # Limpiar proveedor (quitar caracteres especiales)
    if proveedor:
        proveedor_clean = re.sub(r"[^a-zA-Z0-9\s]", "", proveedor)
        proveedor_clean = proveedor_clean.replace(" ", "_")[:30]
    else:
        proveedor_clean = "Desconocido"
    
    # Limpiar ID factura
    if id_factura:
        id_clean = re.sub(r"[^a-zA-Z0-9\-]", "", id_factura)[:20]
    else:
        id_clean = "sin-id"
    
    # Obtener extensión del archivo original
    extension = Path(original_name).suffix or ".pdf"
    
    # Construir nombre final
    new_name = f"{fecha_iso}_{proveedor_clean}_{id_clean}{extension}"
    
    return new_name


async def upload_to_drive(
    file_path: str, 
    file_name: str, 
    ai_data: dict,
    folder_id: Optional[str] = None
) -> dict:
    """
    Sube un archivo a Google Drive.
    
    Args:
        file_path: Ruta completa al archivo a subir
        file_name: Nombre original del archivo
        ai_data: Datos extraídos de la factura (para generar nombre descriptivo)
        folder_id: ID de la carpeta destino (opcional, usa GOOGLE_DRIVE_FOLDER_ID por defecto)
    
    Returns:
        dict con:
            - success: bool
            - drive_url: URL pública del archivo
            - drive_file_id: ID del archivo en Drive
            - error: mensaje de error (si hay)
    
    Example:
        >>> result = await upload_to_drive(
        ...     "/tmp/factura.pdf",
        ...     "factura.pdf",
        ...     {"fecha": "15/01/2024", "proveedor": "Empresa S.L."}
        ... )
        >>> print(result["drive_url"])
    """
    # Validar archivo
    path = Path(file_path)
    if not path.exists():
        return {
            "success": False,
            "drive_url": None,
            "drive_file_id": None,
            "error": f"Archivo no encontrado: {file_path}"
        }
    
    # Determinar carpeta destino
    target_folder = folder_id or GOOGLE_DRIVE_FOLDER_ID
    if not target_folder:
        return {
            "success": False,
            "drive_url": None,
            "drive_file_id": None,
            "error": "GOOGLE_DRIVE_FOLDER_ID no está configurada"
        }
    
    # Generar nombre descriptivo
    new_file_name = _generate_file_name(file_name, ai_data)
    logger.info(f"Subiendo archivo a Drive: {file_path} -> {new_file_name}")
    
    try:
        # Inicializar servicio
        service = _get_drive_service()
        
        # Determinar MIME type
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            mime_type = "application/pdf"
        elif suffix == ".xlsx":
            mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        elif suffix in (".png", ".jpg", ".jpeg"):
            mime_type = f"image/{suffix.replace('.', '')}"
        else:
            mime_type = "application/octet-stream"
        
        # Metadatos del archivo
        file_metadata = {
            "name": new_file_name,
            "parents": [target_folder]
        }
        
        # Subir archivo
        media = MediaFileUpload(
            file_path,
            mimetype=mime_type,
            resumable=True
        )
        
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, webViewLink"
        ).execute()
        
        file_id = file.get("id")
        web_link = file.get("webViewLink")
        
        logger.info(f"Archivo subido exitosamente: {file_id}")
        
        # Hacer el archivo accesible con enlace (opcional)
        # Esto permite que cualquiera con el enlace pueda ver el archivo
        try:
            service.permissions().create(
                fileId=file_id,
                body={
                    "role": "reader",
                    "type": "anyone"
                }
            ).execute()
            logger.info(f"Permisos de lectura pública configurados para {file_id}")
        except HttpError as e:
            # Si falla la configuración de permisos, no es crítico
            logger.warning(f"No se pudieron configurar permisos públicos: {e}")
        
        return {
            "success": True,
            "drive_url": web_link,
            "drive_file_id": file_id,
            "error": None
        }
        
    except FileNotFoundError as e:
        return {
            "success": False,
            "drive_url": None,
            "drive_file_id": None,
            "error": str(e)
        }
    except ValueError as e:
        return {
            "success": False,
            "drive_url": None,
            "drive_file_id": None,
            "error": str(e)
        }
    except HttpError as e:
        logger.error(f"Error de Google Drive API: {e}")
        return {
            "success": False,
            "drive_url": None,
            "drive_file_id": None,
            "error": f"Error de Google Drive: {str(e)}"
        }
    except Exception as e:
        logger.exception(f"Error inesperado subiendo a Drive: {e}")
        return {
            "success": False,
            "drive_url": None,
            "drive_file_id": None,
            "error": f"Error inesperado: {str(e)}"
        }


async def delete_from_drive(file_id: str) -> bool:
    """
    Elimina un archivo de Google Drive.
    
    Args:
        file_id: ID del archivo a eliminar
    
    Returns:
        True si se eliminó correctamente, False en caso contrario
    """
    try:
        service = _get_drive_service()
        service.files().delete(fileId=file_id).execute()
        logger.info(f"Archivo eliminado de Drive: {file_id}")
        return True
    except HttpError as e:
        logger.error(f"Error eliminando archivo de Drive: {e}")
        return False
    except Exception as e:
        logger.exception(f"Error inesperado eliminando de Drive: {e}")
        return False

