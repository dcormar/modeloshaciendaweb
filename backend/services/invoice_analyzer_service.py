# invoice_analyzer_service.py
# Servicio para extraer datos de facturas usando Google Gemini directamente

import os
import logging
from datetime import datetime
from typing import Optional
from pathlib import Path

import google.generativeai as genai

logger = logging.getLogger(__name__)

# Configuración
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()

# Configurar la API de Gemini
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)


EXTRACTION_PROMPT = """Mi empresa es David Cortijo Martín, que es el receptor de la factura.

A partir del documento de factura proporcionado, extrae los siguientes campos y devuelve un objeto JSON con los campos en el orden exacto listado a continuación:

Campos a extraer:
- tipo: clasifica el documento como "factura" o "venta"
- id_factura: número o identificador único de la factura
- proveedor_vat: NIF o VAT del proveedor. Si no aparece, usa "N/A"
- fecha: fecha de emisión en formato DD/MM/YYYY (ej: 15/01/2024)
- categoria: clasifica el gasto en una de estas categorías:
    • Nota de Crédito
    • Tarifas de Logística de Amazon
    • Tarifas de Vender en Amazon
    • Tarifas de Anuncios de Amazon
    • Software
    • Hardware
    • Servicios profesionales
    • Marketing
    • Viajes
    • Material de oficina
    • Otros (especificar en notas)
- proveedor: nombre de la empresa o persona que emitió la factura (NO es David Cortijo Martín, sino la entidad emisora)
- descripcion: breve explicación del producto o servicio prestado, en español
- importe_sin_iva: precio neto total antes de IVA (número con punto decimal, sin símbolos de moneda. Ej: 1200.00)
- iva_porcentaje: porcentaje de IVA aplicado (número. Ej: 21). Si no hay IVA, usar 0
- importe_total: importe total con IVA incluido (número con punto decimal, sin símbolos de moneda. Ej: 1452.00)
- moneda: código de moneda ISO en mayúsculas (EUR, USD, GBP, etc.)
- tipo_cambio: ratio Euro/moneda local si aparece en el documento, o null si la moneda es EUR
- pais_origen: país desde el que se emite la factura, en formato ISO 3166-2 (ES, FR, DE, etc.)
- notas: cualquier anotación relevante para contabilidad o aclaraciones, en español. Si no aplica, usa "N/A"

Ejemplo de respuesta esperada:
{"tipo": "factura", "id_factura": "FAC-2024-001", "proveedor_vat": "B12345678", "fecha": "15/01/2024", "categoria": "Software", "proveedor": "Empresa S.L.", "descripcion": "Licencia anual de software", "importe_sin_iva": 100.00, "iva_porcentaje": 21, "importe_total": 121.00, "moneda": "EUR", "tipo_cambio": null, "pais_origen": "ES", "notas": "N/A"}

IMPORTANTE:
- Responde ÚNICAMENTE con el JSON, sin texto adicional ni markdown.
- Ningún campo debe quedar vacío: usa "N/A" donde no haya datos.
- Mantén el orden exacto de los campos."""


def _parse_json_response(text: str) -> dict:
    """Parsea la respuesta JSON de Gemini, limpiando posibles artefactos"""
    import json
    
    # Limpiar posibles markdown code blocks
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(f"Error parseando JSON de Gemini: {e}\nTexto: {text[:500]}")
        raise ValueError(f"Respuesta de Gemini no es JSON válido: {str(e)}")


async def extract_invoice_data(file_path: str) -> dict:
    """
    Extrae datos estructurados de una factura usando Gemini.
    
    Args:
        file_path: Ruta completa al archivo PDF de la factura
        
    Returns:
        Diccionario con los datos extraídos de la factura
        
    Raises:
        ValueError: Si no se puede procesar la factura
        FileNotFoundError: Si el archivo no existe
    """
    if not GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY no está configurada")
    
    logger.info(f"Extrayendo datos de factura: {file_path}")
    
    # 1. Verificar que el archivo existe
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {file_path}")
    
    # 2. Subir el archivo a Gemini
    try:
        logger.info(f"Subiendo archivo a Gemini: {path.name}")
        uploaded_file = genai.upload_file(path)
        logger.info(f"Archivo subido: {uploaded_file.name}")
    except Exception as e:
        logger.error(f"Error subiendo archivo a Gemini: {e}")
        raise ValueError(f"Error subiendo archivo: {str(e)}")
    
    # 3. Crear el modelo
    try:
        model = genai.GenerativeModel("gemini-2.0-flash-lite")
    except Exception as e:
        logger.error(f"Error inicializando Gemini: {e}")
        raise ValueError(f"Error inicializando modelo de IA: {str(e)}")
    
    # 4. Llamar a Gemini con el archivo
    try:
        response = model.generate_content([uploaded_file, EXTRACTION_PROMPT])
        response_text = response.text
        logger.debug(f"Respuesta de Gemini: {response_text[:500]}...")
    except Exception as e:
        logger.error(f"Error llamando a Gemini: {e}")
        raise ValueError(f"Error en procesamiento con IA: {str(e)}")
    finally:
        # Limpiar el archivo subido
        try:
            genai.delete_file(uploaded_file.name)
            logger.debug(f"Archivo temporal eliminado: {uploaded_file.name}")
        except Exception as e:
            logger.warning(f"No se pudo eliminar archivo temporal: {e}")
    
    # 5. Parsear la respuesta JSON
    try:
        data = _parse_json_response(response_text)
    except ValueError:
        raise
    
    # 6. Validar y normalizar datos
    data = _normalize_invoice_data(data)
    
    # 7. Si la moneda no es EUR y no hay tipo de cambio, obtenerlo de Frankfurter
    data = await _enrich_with_exchange_rate(data)
    
    logger.info(f"Datos extraídos exitosamente: {data.get('id_factura', 'sin ID')}")
    return data


def _normalize_invoice_data(data: dict) -> dict:
    """Normaliza y valida los datos extraídos"""
    # Normalizar tipo
    if data.get("tipo"):
        data["tipo"] = data["tipo"].lower().strip()
        if data["tipo"] not in ("factura", "venta"):
            data["tipo"] = "factura"  # Default
    else:
        data["tipo"] = "factura"
    
    # Asegurar que moneda tiene un valor por defecto
    if not data.get("moneda"):
        data["moneda"] = "EUR"
    else:
        data["moneda"] = data["moneda"].upper().strip()
    
    # Normalizar campos numéricos
    for field in ["importe_sin_iva", "iva_porcentaje", "importe_total", "tipo_cambio"]:
        if field in data and data[field] is not None:
            try:
                # Reemplazar coma por punto si viene en formato español
                if isinstance(data[field], str):
                    data[field] = data[field].replace(",", ".")
                data[field] = float(data[field])
            except (ValueError, TypeError):
                data[field] = None
    
    # Normalizar país
    if data.get("pais_origen"):
        data["pais_origen"] = data["pais_origen"].upper().strip()[:2]
    
    # Asegurar N/A en campos de texto vacíos
    for field in ["proveedor_vat", "notas"]:
        if not data.get(field) or data[field] == "":
            data[field] = "N/A"
    
    return data


async def _enrich_with_exchange_rate(data: dict) -> dict:
    """
    Si la factura no es en EUR y no tiene tipo de cambio,
    obtiene el tipo de cambio de la API de Frankfurter.
    """
    from services.exchange_service import get_exchange_rate
    
    moneda = data.get("moneda", "EUR")
    tipo_cambio = data.get("tipo_cambio")
    
    # Solo obtener tipo de cambio si no es EUR y no hay uno ya
    if moneda != "EUR" and not tipo_cambio:
        fecha_str = data.get("fecha", "")
        if fecha_str:
            try:
                # Convertir fecha DD/MM/YYYY a YYYY-MM-DD
                dt = datetime.strptime(fecha_str, "%d/%m/%Y")
                fecha_iso = dt.strftime("%Y-%m-%d")
                
                logger.info(f"Obteniendo tipo de cambio para {moneda} en fecha {fecha_iso}")
                tipo_cambio = await get_exchange_rate(fecha_iso, moneda)
                
                if tipo_cambio:
                    data["tipo_cambio"] = tipo_cambio
                    logger.info(f"Tipo de cambio obtenido: {tipo_cambio}")
                else:
                    logger.warning(f"No se pudo obtener tipo de cambio para {moneda}")
            except ValueError as e:
                logger.warning(f"Fecha inválida para obtener tipo de cambio: {fecha_str} - {e}")
    
    return data
