import httpx
import logging
import os
import uuid
import json
import hashlib
import re
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from auth import get_current_user, UserInDB
from datetime import datetime
import certifi
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
UPLOAD_BASE = os.getenv("UPLOAD_BASE", "/tmp/uploads")

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/generate-invoice", tags=["generate-invoice"])


def sanitize_folder(name: str) -> str:
    """Sanitiza el nombre de carpeta para evitar caracteres problemáticos"""
    return re.sub(r"[^a-zA-Z0-9@\.\-_]", "_", name or "user")


def get_upload_base() -> Path:
    """Obtiene la ruta base para almacenar archivos"""
    return Path(UPLOAD_BASE)


def sha256_file(path: Path) -> str:
    """Calcula el hash SHA256 de un archivo"""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


async def get_user_data(username: str) -> Optional[dict]:
    """
    Obtiene los datos del usuario desde la tabla USERS en Supabase.
    
    Args:
        username: Nombre de usuario
        
    Returns:
        Diccionario con nombre_empresa, nif, direccion o None si no existe
    """
    try:
        url = f"{SUPABASE_URL}/rest/v1/users?username=eq.{username}&select=nombre_empresa,nif,direccion"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}"
        }
        
        async with httpx.AsyncClient(timeout=10, verify=certifi.where()) as client:
            response = await client.get(url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    return data[0]
            return None
    except Exception as e:
        logger.warning(f"Error obteniendo datos del usuario {username}: {e}")
        return None


def generate_invoice_pdf(factura_data: dict, numero_factura: str, output_path: Path, user_data: Optional[dict] = None) -> None:
    """
    Genera un PDF de factura con formato típico español.
    
    Args:
        factura_data: Diccionario con los datos de la factura
        numero_factura: UUID de la factura
        output_path: Ruta donde guardar el PDF
        user_data: Diccionario con datos del usuario/empresa (nombre_empresa, nif, direccion)
    """
    doc = SimpleDocTemplate(str(output_path), pagesize=A4)
    story = []
    styles = getSampleStyleSheet()
    
    # Estilos personalizados
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor('#163a63'),
        spaceAfter=30,
        alignment=1,  # Centrado
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#163a63'),
        spaceAfter=12,
    )
    
    normal_style = styles['Normal']
    normal_style.fontSize = 10
    
    # Cabecera de la empresa/autónomo
    if user_data:
        story.append(Paragraph("DATOS DEL EMISOR", heading_style))
        empresa_info = []
        if user_data.get("nombre_empresa"):
            empresa_info.append(["Nombre:", user_data.get("nombre_empresa", "")])
        if user_data.get("nif"):
            empresa_info.append(["NIF:", user_data.get("nif", "")])
        if user_data.get("direccion"):
            empresa_info.append(["Dirección:", user_data.get("direccion", "")])
        
        if empresa_info:
            empresa_table = Table(empresa_info, colWidths=[40*mm, 120*mm])
            empresa_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ]))
            story.append(empresa_table)
            story.append(Spacer(1, 20))
    
    # Título
    story.append(Paragraph("FACTURA", title_style))
    story.append(Spacer(1, 20))
    
    # Información de la factura
    factura_info = [
        ["Número de factura:", numero_factura],
        ["Fecha de emisión:", factura_data.get("fecha_emision", "")],
    ]
    
    factura_table = Table(factura_info, colWidths=[60*mm, 100*mm])
    factura_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(factura_table)
    story.append(Spacer(1, 20))
    
    # Datos del cliente
    story.append(Paragraph("DATOS DEL CLIENTE", heading_style))
    cliente_info = [
        ["Nombre:", factura_data.get("cliente_nombre", "")],
        ["NIF/CIF:", factura_data.get("cliente_nif", "")],
        ["Dirección:", factura_data.get("cliente_direccion", "")],
    ]
    
    cliente_table = Table(cliente_info, colWidths=[40*mm, 120*mm])
    cliente_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(cliente_table)
    story.append(Spacer(1, 20))
    
    # Concepto
    story.append(Paragraph("CONCEPTO", heading_style))
    concepto_text = factura_data.get("concepto", "")
    story.append(Paragraph(concepto_text, normal_style))
    story.append(Spacer(1, 20))
    
    # Desglose de importes
    story.append(Paragraph("DESGLOSE DE IMPORTES", heading_style))
    
    base_imponible = factura_data.get("base_imponible", 0)
    tipo_iva = factura_data.get("tipo_iva", 0)
    importe_iva = factura_data.get("importe_iva", 0)
    total = factura_data.get("total", 0)
    moneda = factura_data.get("moneda", "EUR")
    
    # Crear tabla de importes sin HTML en el total
    importes_data = [
        ["Concepto", "Importe"],
        ["Base imponible", f"{base_imponible:.2f} {moneda}"],
        [f"IVA ({tipo_iva}%)", f"{importe_iva:.2f} {moneda}"],
        ["TOTAL", f"{total:.2f} {moneda}"],  # Sin etiquetas HTML
    ]
    
    importes_table = Table(importes_data, colWidths=[100*mm, 60*mm])
    importes_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#163a63')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (0, -2), 'Helvetica'),
        ('FONTNAME', (1, 1), (1, -2), 'Helvetica'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),  # Negrita para TOTAL usando estilo de tabla
        ('FONTNAME', (1, -1), (1, -1), 'Helvetica-Bold'),  # Negrita para el importe total
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ]))
    story.append(importes_table)
    
    # Notas si existen
    if factura_data.get("notas"):
        story.append(Spacer(1, 20))
        story.append(Paragraph("NOTAS", heading_style))
        story.append(Paragraph(factura_data.get("notas", ""), normal_style))
    
    # Construir el PDF
    doc.build(story)


class FacturaGeneradaRequest(BaseModel):
    fecha_emision: str
    cliente_nombre: str
    cliente_nif: str
    cliente_direccion: str
    concepto: str
    base_imponible: float
    tipo_iva: float
    importe_iva: float
    total: float
    moneda: str = "EUR"
    notas: Optional[str] = None


class FacturaGeneradaResponse(BaseModel):
    ok: bool
    numero_factura: str
    id: Optional[int] = None
    message: Optional[str] = None


class AIRequest(BaseModel):
    texto: str


class AIResponse(BaseModel):
    fecha_emision: Optional[str] = None
    cliente_nombre: Optional[str] = None
    cliente_nif: Optional[str] = None
    cliente_direccion: Optional[str] = None
    concepto: Optional[str] = None
    base_imponible: Optional[float] = None
    tipo_iva: Optional[float] = None
    importe_iva: Optional[float] = None
    total: Optional[float] = None
    moneda: Optional[str] = "EUR"
    notas: Optional[str] = None


async def generate_unique_uuid() -> str:
    """
    Genera un UUID único verificando que no exista en la base de datos.
    Repite hasta encontrar uno único (máximo 10 intentos).
    """
    max_attempts = 10
    
    for attempt in range(max_attempts):
        new_uuid = str(uuid.uuid4())
        
        # Verificar si existe en Supabase
        url = f"{SUPABASE_URL}/rest/v1/facturas_generadas?numero_factura=eq.{new_uuid}&select=numero_factura"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}"
        }
        
        try:
            async with httpx.AsyncClient(timeout=10, verify=certifi.where()) as client:
                response = await client.get(url, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    # Si la lista está vacía, el UUID no existe
                    if not data or len(data) == 0:
                        logger.info(f"UUID único generado en intento {attempt + 1}: {new_uuid}")
                        return new_uuid
                    else:
                        logger.warning(f"UUID {new_uuid} ya existe, generando otro...")
                else:
                    # Si hay error en la consulta, asumimos que el UUID es único
                    # (mejor generar uno nuevo que fallar)
                    logger.warning(f"Error consultando Supabase para UUID: {response.status_code}")
                    continue
        except Exception as e:
            logger.error(f"Error verificando UUID en Supabase: {e}")
            # En caso de error, intentar con otro UUID
            continue
    
    # Si llegamos aquí, no pudimos generar un UUID único después de 10 intentos
    raise HTTPException(
        status_code=500,
        detail="No se pudo generar un UUID único después de múltiples intentos"
    )


@router.post("/", status_code=201, response_model=FacturaGeneradaResponse)
async def generate_invoice(
    factura: FacturaGeneradaRequest,
    current_user: UserInDB = Depends(get_current_user),
):
    """
    Endpoint para crear una factura generada.
    Genera un UUID único para numero_factura y lo inserta en Supabase.
    """
    try:
        # Generar UUID único
        numero_factura = await generate_unique_uuid()
        
        # Procesar fecha: convertir de YYYY-MM-DD a formato date y timestamp
        fecha_emision_date = None
        fecha_emision_dt = None
        
        try:
            # Intentar parsear como YYYY-MM-DD
            dt = datetime.strptime(factura.fecha_emision, "%Y-%m-%d")
            fecha_emision_date = dt.date().isoformat()
            fecha_emision_dt = dt.isoformat()
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Formato de fecha inválido. Se espera YYYY-MM-DD, se recibió: {factura.fecha_emision}"
            )
        
        # Preparar datos para insertar
        factura_row = {
            "numero_factura": numero_factura,
            "fecha_emision": fecha_emision_date,
            "fecha_emision_dt": fecha_emision_dt,
            "cliente_nombre": factura.cliente_nombre.strip(),
            "cliente_nif": factura.cliente_nif.strip(),
            "cliente_direccion": factura.cliente_direccion.strip(),
            "concepto": factura.concepto.strip(),
            "base_imponible": factura.base_imponible,
            "tipo_iva": factura.tipo_iva,
            "importe_iva": factura.importe_iva,
            "total": factura.total,
            "moneda": factura.moneda or "EUR",
            "notas": factura.notas.strip() if factura.notas else None,
            "created_by": current_user.username,
            "user_id": current_user.username,  # Usar username como user_id por ahora
        }
        
        # Insertar en Supabase
        url = f"{SUPABASE_URL}/rest/v1/facturas_generadas"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
        
        async with httpx.AsyncClient(timeout=20, verify=certifi.where()) as client:
            response = await client.post(url, headers=headers, json=factura_row)
            
            if response.status_code not in (200, 201):
                logger.error(f"Error insertando factura en Supabase: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=502,
                    detail=f"Error insertando factura en Supabase: {response.text}"
                )
            
            # Obtener el registro insertado
            result = response.json()
            db_row = result[0] if isinstance(result, list) and result else result
            factura_id = db_row.get("id")
            
            logger.info(f"Factura generada exitosamente: {numero_factura} (ID: {factura_id})")
            
            # Generar PDF de la factura
            try:
                # Obtener datos del usuario desde Supabase
                user_data = await get_user_data(current_user.username)
                
                base = get_upload_base()
                base.mkdir(parents=True, exist_ok=True)
                user_folder = base / sanitize_folder(current_user.username) / "facturas_generadas"
                user_folder.mkdir(parents=True, exist_ok=True)
                
                pdf_filename = f"factura_{numero_factura}.pdf"
                pdf_path = user_folder / pdf_filename
                
                # Datos para el PDF
                pdf_data = {
                    "fecha_emision": fecha_emision_date,
                    "cliente_nombre": factura.cliente_nombre.strip(),
                    "cliente_nif": factura.cliente_nif.strip(),
                    "cliente_direccion": factura.cliente_direccion.strip(),
                    "concepto": factura.concepto.strip(),
                    "base_imponible": factura.base_imponible,
                    "tipo_iva": factura.tipo_iva,
                    "importe_iva": factura.importe_iva,
                    "total": factura.total,
                    "moneda": factura.moneda or "EUR",
                    "notas": factura.notas.strip() if factura.notas else None,
                }
                
                # Generar PDF con datos del usuario
                generate_invoice_pdf(pdf_data, numero_factura, pdf_path, user_data)
                
                # Calcular hash y tamaño
                file_size = pdf_path.stat().st_size
                sha256_hash = sha256_file(pdf_path)
                
                # Insertar registro del documento en FACTURAS_GENERADAS_DOCS
                doc_url = f"{SUPABASE_URL}/rest/v1/facturas_generadas_docs"
                doc_headers = {
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": "application/json",
                    "Prefer": "return=representation"
                }
                
                doc_payload = {
                    "factura_id": factura_id,
                    "file_name": pdf_filename,
                    "storage_path": str(pdf_path),
                    "file_size_bytes": file_size,
                    "mime_type": "application/pdf",
                    "sha256": sha256_hash,
                    "created_by": current_user.username,
                }
                
                async with httpx.AsyncClient(timeout=20, verify=certifi.where()) as doc_client:
                    doc_response = await doc_client.post(doc_url, headers=doc_headers, json=doc_payload)
                    
                    if doc_response.status_code not in (200, 201):
                        logger.warning(f"Error insertando documento PDF en Supabase: {doc_response.status_code} - {doc_response.text}")
                        # No fallamos la operación si falla el guardado del PDF
                    else:
                        logger.info(f"PDF de factura guardado: {pdf_filename} (ID factura: {factura_id})")
                        
            except Exception as e:
                logger.exception(f"Error generando PDF de factura: {e}")
                # No fallamos la operación si falla la generación del PDF
            
            return FacturaGeneradaResponse(
                ok=True,
                numero_factura=numero_factura,
                id=factura_id,
                message="Factura creada exitosamente"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error inesperado al generar factura: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error inesperado al generar factura: {str(e)}"
        )


@router.post("/ai", response_model=AIResponse)
async def generate_invoice_ai(
    request: AIRequest,
    current_user: UserInDB = Depends(get_current_user),
):
    """
    Endpoint para procesar texto de factura con Gemini AI y extraer los campos.
    """
    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="GEMINI_API_KEY no configurada en variables de entorno"
        )

    try:
        # Prompt para Gemini
        prompt = f"""Extrae la información de factura del siguiente texto y devuélvela en formato JSON válido.
        
Campos a extraer:
- fecha_emision: fecha de emisión en formato YYYY-MM-DD (si no se encuentra, usar null)
- cliente_nombre: nombre del cliente (si no se encuentra, usar "")
- cliente_nif: NIF/CIF del cliente (si no se encuentra, usar "")
- cliente_direccion: dirección del cliente (si no se encuentra, usar "")
- concepto: concepto/descripción de la factura (si no se encuentra, usar "")
- base_imponible: base imponible sin IVA como número (si no se encuentra, usar null)
- tipo_iva: tipo de IVA en porcentaje como número (si no se encuentra, usar null)
- importe_iva: importe de IVA como número (si no se encuentra, usar null)
- total: total con IVA como número (si no se encuentra, usar null)
- moneda: código de moneda (EUR por defecto si no se encuentra)
- notas: notas adicionales (si no se encuentra, usar "")

Texto de la factura:
{request.texto}

Responde SOLO con un JSON válido, sin texto adicional, sin markdown, sin explicaciones. Ejemplo:
{{"fecha_emision": "2024-03-15", "cliente_nombre": "ABC S.L.", "cliente_nif": "B12345678", "cliente_direccion": "Calle Mayor 1, Madrid", "concepto": "Servicios de consultoría", "base_imponible": 1000.0, "tipo_iva": 21.0, "importe_iva": 210.0, "total": 1210.0, "moneda": "EUR", "notas": ""}}
"""

        # Llamar a la API de Gemini
        gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
        
        payload = {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }]
        }

        async with httpx.AsyncClient(timeout=30, verify=certifi.where()) as client:
            response = await client.post(
                gemini_url,
                headers={"Content-Type": "application/json"},
                json=payload
            )

            if response.status_code != 200:
                logger.error(f"Error llamando a Gemini API: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=502,
                    detail=f"Error en la API de Gemini: {response.text}"
                )

            result = response.json()
            
            # Extraer el texto de la respuesta
            try:
                text_response = result["candidates"][0]["content"]["parts"][0]["text"]
                # Limpiar el texto (puede venir con markdown o espacios)
                text_response = text_response.strip()
                # Eliminar markdown code blocks si existen
                if text_response.startswith("```"):
                    lines = text_response.split("\n")
                    text_response = "\n".join(lines[1:-1]) if len(lines) > 2 else text_response
                text_response = text_response.strip()
                
                # Parsear JSON
                extracted_data = json.loads(text_response)
                
                # Validar y limpiar los datos
                ai_response = AIResponse(
                    fecha_emision=extracted_data.get("fecha_emision"),
                    cliente_nombre=extracted_data.get("cliente_nombre") or "",
                    cliente_nif=extracted_data.get("cliente_nif") or "",
                    cliente_direccion=extracted_data.get("cliente_direccion") or "",
                    concepto=extracted_data.get("concepto") or "",
                    base_imponible=extracted_data.get("base_imponible"),
                    tipo_iva=extracted_data.get("tipo_iva"),
                    importe_iva=extracted_data.get("importe_iva"),
                    total=extracted_data.get("total"),
                    moneda=extracted_data.get("moneda") or "EUR",
                    notas=extracted_data.get("notas") or "",
                )
                
                logger.info(f"Factura procesada con IA para usuario {current_user.username}")
                return ai_response
                
            except (KeyError, IndexError, json.JSONDecodeError) as e:
                logger.error(f"Error parseando respuesta de Gemini: {e}. Respuesta: {result}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Error procesando respuesta de Gemini: {str(e)}"
                )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error inesperado al procesar con IA: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error inesperado al procesar con IA: {str(e)}"
        )

