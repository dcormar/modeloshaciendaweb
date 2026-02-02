# email_service.py
# Servicio de envío de emails usando Resend

import os
import logging
from typing import Optional, List
from pathlib import Path
import httpx

# Cargar .env si está disponible (para asegurar que las variables estén disponibles)
try:
    from dotenv import load_dotenv
    # Intentar cargar .env desde el directorio backend
    current_file = Path(__file__)
    backend_dir = current_file.parent.parent  # backend/services/ -> backend/
    env_path = backend_dir / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)
    else:
        # Fallback: intentar cargar desde directorio actual
        load_dotenv(override=False)
except ImportError:
    # dotenv no disponible, continuar sin cargar (asumiendo que main.py ya lo cargó)
    pass

logger = logging.getLogger(__name__)

# Configuración (después de cargar .env)
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()
DEFAULT_FROM_EMAIL = os.getenv("EMAIL_FROM", "noreply@nementium.ai")
RESEND_API_URL = "https://api.resend.com/emails"


async def send_email(
    to: str | List[str],
    subject: str,
    html: str,
    from_email: Optional[str] = None,
    reply_to: Optional[str] = None,
    text: Optional[str] = None
) -> dict:
    """
    Envía un email usando la API de Resend.
    
    Args:
        to: Dirección(es) de email del destinatario
        subject: Asunto del email
        html: Contenido HTML del email
        from_email: Email del remitente (opcional, usa default)
        reply_to: Email para respuestas (opcional)
        text: Versión texto plano del email (opcional)
    
    Returns:
        Dict con id del email enviado o error
    """
    if not RESEND_API_KEY:
        logger.error("[EMAIL] RESEND_API_KEY no configurada")
        raise ValueError("RESEND_API_KEY no está configurada. Configura la variable de entorno.")
    
    # Preparar destinatarios
    if isinstance(to, str):
        to = [to]
    
    # Preparar payload
    payload = {
        "from": from_email or DEFAULT_FROM_EMAIL,
        "to": to,
        "subject": subject,
        "html": html
    }
    
    if reply_to:
        payload["reply_to"] = reply_to
    
    if text:
        payload["text"] = text
    
    logger.info(f"[EMAIL] Enviando email a {to}")
    logger.debug(f"[EMAIL] Subject: {subject}")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                RESEND_API_URL,
                headers={
                    "Authorization": f"Bearer {RESEND_API_KEY}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"[EMAIL] Email enviado: id={result.get('id')}")
                return {"success": True, "id": result.get("id")}
            else:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get("message", f"HTTP {response.status_code}")
                logger.error(f"[EMAIL] Error enviando email: {error_msg}")
                return {"success": False, "error": error_msg}
                
    except httpx.TimeoutException:
        logger.error("[EMAIL] Timeout enviando email")
        return {"success": False, "error": "Timeout al enviar email"}
    except Exception as e:
        logger.error(f"[EMAIL] Error: {e}")
        return {"success": False, "error": str(e)}


async def send_notification_email(
    to_email: str,
    from_user_name: str,
    subject_content: str,
    body: str
) -> dict:
    """
    Envía una notificación formateada desde un usuario de la app.
    
    Args:
        to_email: Email del destinatario
        from_user_name: Nombre del usuario que envía
        subject_content: Contenido del asunto
        body: Cuerpo del mensaje
    
    Returns:
        Dict con resultado del envío
    """
    # Construir asunto
    subject = f"Notificación de {from_user_name}: {subject_content}"
    
    # Escapar el body para HTML (evitar inyección XSS)
    import html
    
    # Asegurar que el body se pasa completo (sin truncar)
    body_full = str(body) if body else ""
    # Escapar caracteres HTML especiales
    body_escaped = html.escape(body_full)
    # Convertir saltos de línea en <br> para preservar el formato
    # Primero normalizar diferentes tipos de saltos de línea
    body_escaped = body_escaped.replace('\r\n', '\n').replace('\r', '\n')
    # Convertir \n en <br>
    body_escaped = body_escaped.replace('\n', '<br>')
    
    logger.debug(f"[EMAIL] Body recibido - length: {len(body_full)} caracteres")
    
    # Construir HTML con plantilla
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .header {{
                background: white;
                color: #2563eb;
                padding: 20px;
                border-radius: 8px 8px 0 0;
                text-align: center;
                border-bottom: 2px solid #2563eb;
            }}
            .header h1 {{
                margin: 0;
                font-size: 24px;
                color: #2563eb;
            }}
            .content {{
                background: #f9fafb;
                padding: 24px;
                border: 1px solid #e5e7eb;
                border-top: none;
                border-radius: 0 0 8px 8px;
            }}
            .message-box {{
                background: white;
                padding: 20px;
                border-radius: 8px;
                border-left: 4px solid #2563eb;
                margin: 16px 0;
            }}
            .message-box p {{
                margin: 0;
                white-space: pre-wrap;
            }}
            .footer {{
                text-align: center;
                color: #6b7280;
                font-size: 12px;
                margin-top: 20px;
            }}
            .sender {{
                color: #2563eb;
                font-weight: 600;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>📬 Nementium.ai</h1>
        </div>
        <div class="content">
            <p>Tienes una nueva notificación de <span class="sender">{html.escape(from_user_name)}</span>:</p>
            
            <div class="message-box">
                <p>{body_escaped}</p>
            </div>
            
            <p style="color: #6b7280; font-size: 14px;">
                Este mensaje fue enviado a través de la plataforma Nementium.ai
            </p>
        </div>
        <div class="footer">
            <p>© 2025 Nementium.ai - Gestión fiscal inteligente</p>
            <p>Este es un mensaje automático, por favor no respondas directamente a este email.</p>
        </div>
    </body>
    </html>
    """
    
    # Versión texto plano (usar body_full para asegurar que no se trunca)
    text = f"""
Notificación de {from_user_name}

{body_full}

---
Este mensaje fue enviado a través de Nementium.ai
"""
    
    return await send_email(
        to=to_email,
        subject=subject,
        html=html_content,
        text=text
    )


async def send_welcome_email(to_email: str, user_name: str) -> dict:
    """
    Envía un email de bienvenida a un nuevo usuario.
    """
    subject = "¡Bienvenido a Nementium.ai!"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .header {{
                background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 100%);
                color: white;
                padding: 30px;
                border-radius: 8px 8px 0 0;
                text-align: center;
            }}
            .content {{
                background: #f9fafb;
                padding: 24px;
                border: 1px solid #e5e7eb;
                border-top: none;
                border-radius: 0 0 8px 8px;
            }}
            .cta {{
                display: inline-block;
                background: #2563eb;
                color: white;
                padding: 12px 24px;
                border-radius: 6px;
                text-decoration: none;
                font-weight: 600;
                margin: 16px 0;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>¡Bienvenido a Nementium.ai! 🎉</h1>
        </div>
        <div class="content">
            <p>Hola <strong>{user_name}</strong>,</p>
            
            <p>¡Gracias por unirte a Nementium.ai! Estamos encantados de tenerte con nosotros.</p>
            
            <p>Con nuestra plataforma podrás:</p>
            <ul>
                <li>📄 Gestionar tus facturas automáticamente con IA</li>
                <li>📊 Ver el estado de tus obligaciones fiscales</li>
                <li>💬 Consultar información sobre Hacienda y Seguridad Social</li>
                <li>🤖 Usar nuestro asistente inteligente 24/7</li>
            </ul>
            
            <p style="text-align: center;">
                <a href="https://app.nementium.ai" class="cta">Acceder a la aplicación</a>
            </p>
            
            <p>Si tienes alguna pregunta, nuestro asistente IA está disponible en cualquier momento.</p>
            
            <p>¡Un saludo!<br>El equipo de Nementium.ai</p>
        </div>
    </body>
    </html>
    """
    
    return await send_email(
        to=to_email,
        subject=subject,
        html=html
    )
