# drive_service.py
# Servicio para subir archivos a Google Drive usando OAuth2

import os
import logging
import re
import json
from pathlib import Path
from typing import Optional
from datetime import datetime

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# Configuración
GOOGLE_DRIVE_CREDENTIALS_FILE = os.getenv("GOOGLE_DRIVE_CREDENTIALS_FILE", "").strip()
GOOGLE_DRIVE_TOKEN_FILE = os.getenv("GOOGLE_DRIVE_TOKEN_FILE", "credentials/drive-token.json").strip()
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "").strip()

# Scopes necesarios para subir archivos
SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def _get_credentials_path() -> Path:
    """Obtiene la ruta al archivo de credenciales OAuth2"""
    if GOOGLE_DRIVE_CREDENTIALS_FILE:
        return Path(GOOGLE_DRIVE_CREDENTIALS_FILE)
    # Ruta por defecto
    return Path(__file__).parent.parent / "credentials" / "drive-oauth-credentials.json"


def _get_token_path() -> Path:
    """Obtiene la ruta al archivo de token"""
    if GOOGLE_DRIVE_TOKEN_FILE:
        path = Path(GOOGLE_DRIVE_TOKEN_FILE)
        if not path.is_absolute():
            path = Path(__file__).parent.parent / path
        return path
    return Path(__file__).parent.parent / "credentials" / "drive-token.json"


def _get_drive_service():
    """
    Crea y devuelve un servicio de Google Drive autenticado con OAuth2.
    
    El flujo de autenticación:
    1. Si existe un token guardado y es válido, lo usa
    2. Si el token expiró pero tiene refresh_token, lo renueva
    3. Si no hay token, inicia el flujo de autorización (abre navegador)
    """
    creds = None
    token_path = _get_token_path()
    credentials_path = _get_credentials_path()
    
    # DEBUG: Mostrar rutas y contenido
    logger.info(f"[DEBUG] GOOGLE_DRIVE_CREDENTIALS_FILE env: '{GOOGLE_DRIVE_CREDENTIALS_FILE}'")
    logger.info(f"[DEBUG] Ruta de credenciales calculada: {credentials_path}")
    logger.info(f"[DEBUG] Ruta de token calculada: {token_path}")
    logger.info(f"[DEBUG] Archivo de credenciales existe: {credentials_path.exists()}")
    
    # Verificar que existe el archivo de credenciales OAuth
    if not credentials_path.exists():
        raise FileNotFoundError(
            f"Archivo de credenciales OAuth2 no encontrado: {credentials_path}\n"
            "Descarga las credenciales de Google Cloud Console (OAuth 2.0 Client IDs)"
        )
    
    # DEBUG: Leer y mostrar las claves del JSON
    try:
        import json
        with open(credentials_path, 'r') as f:
            creds_json = json.load(f)
        logger.info(f"[DEBUG] Claves en el JSON de credenciales: {list(creds_json.keys())}")
        if 'installed' in creds_json:
            logger.info("[DEBUG] ✓ Formato correcto: 'installed' (OAuth2 Desktop)")
        elif 'web' in creds_json:
            logger.info("[DEBUG] ✓ Formato: 'web' (OAuth2 Web)")
        elif 'type' in creds_json and creds_json['type'] == 'service_account':
            logger.error("[DEBUG] ✗ ERROR: Este es un archivo de SERVICE ACCOUNT, no OAuth2!")
        else:
            logger.warning(f"[DEBUG] ⚠ Formato desconocido. Claves: {list(creds_json.keys())}")
    except Exception as e:
        logger.error(f"[DEBUG] Error leyendo JSON de credenciales: {e}")
    
    # Intentar cargar token existente
    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
            logger.debug("Token cargado desde archivo")
        except Exception as e:
            logger.warning(f"Error cargando token: {e}")
            creds = None
    
    # Si no hay credenciales válidas, obtener nuevas
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                logger.info("Renovando token expirado...")
                creds.refresh(Request())
                logger.info("Token renovado exitosamente")
            except Exception as e:
                logger.warning(f"Error renovando token: {e}")
                creds = None
        
        if not creds:
            # Iniciar flujo de autorización
            logger.info("Iniciando flujo de autorización OAuth2...")
            logger.info("Se abrirá una ventana del navegador para autorizar la aplicación")
            
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_path), 
                SCOPES
            )
            creds = flow.run_local_server(port=0)  # Puerto automático
            logger.info("Autorización completada")
        
        # Guardar token para futuras ejecuciones
        token_path.parent.mkdir(parents=True, exist_ok=True)
        with open(token_path, "w") as token_file:
            token_file.write(creds.to_json())
        logger.info(f"Token guardado en {token_path}")
    
    # Construir servicio
    try:
        service = build("drive", "v3", credentials=creds)
        return service
    except Exception as e:
        logger.error(f"Error construyendo servicio de Drive: {e}")
        raise ValueError(f"Error inicializando Google Drive: {str(e)}")


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
    Sube un archivo a Google Drive usando OAuth2.
    
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
