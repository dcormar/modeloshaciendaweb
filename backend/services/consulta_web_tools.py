# consulta_web_tools.py
# Herramientas de búsqueda online para el agente de consulta

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from langchain.tools import tool

logger = logging.getLogger(__name__)

try:
    from duckduckgo_search import DDGS
    DDG_AVAILABLE = True
except ImportError:
    DDG_AVAILABLE = False
    logger.warning("duckduckgo-search no está instalado. Búsqueda web no disponible.")


@tool
def web_search(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Busca información en internet usando un motor de búsqueda.
    Útil para verificar datos de proveedores, obtener tipos de cambio,
    buscar información contextual sobre facturas, etc.
    
    Args:
        query: Términos de búsqueda (ej: "Amazon España NIF", "tipo cambio USD EUR")
        max_results: Número máximo de resultados a retornar (default: 5, máx: 10)
    
    Returns:
        Lista de diccionarios con:
        - url: URL del resultado
        - snippet: Fragmento de texto relevante
        - name: Nombre/título del resultado
    """
    if not DDG_AVAILABLE:
        raise ValueError("Búsqueda web no disponible: duckduckgo-search no está instalado")
    
    if max_results > 10:
        max_results = 10
    if max_results < 1:
        max_results = 5
    
    logger.info(f"[WEB_SEARCH] Buscando: {query} (max_results={max_results})")
    
    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "name": r.get("title", ""),  # Usar 'name' en lugar de 'title' para evitar warning
                    "url": r.get("href", ""),
                    "snippet": r.get("body", "")
                })
        
        logger.info(f"[WEB_SEARCH] Encontrados {len(results)} resultados")
        return results
    except Exception as e:
        logger.error(f"[WEB_SEARCH] Error en búsqueda: {e}")
        raise ValueError(f"Error en búsqueda web: {str(e)}")


@tool
def search_exchange_rate(
    currency_from: str, 
    currency_to: str, 
    date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Busca el tipo de cambio entre dos monedas.
    Si no se especifica fecha, busca el tipo de cambio actual.
    
    Args:
        currency_from: Moneda origen (ej: "USD", "GBP", "EUR")
        currency_to: Moneda destino (ej: "EUR")
        date: Fecha en formato YYYY-MM-DD (opcional, default: hoy)
    
    Returns:
        Dict con:
        - rate: Tipo de cambio (float)
        - date: Fecha del tipo de cambio
        - currency_from: Moneda origen
        - currency_to: Moneda destino
        - source: Fuente de la información
    """
    if not DDG_AVAILABLE:
        raise ValueError("Búsqueda web no disponible: duckduckgo-search no está instalado")
    
    # Normalizar códigos de moneda
    currency_from = currency_from.upper().strip()
    currency_to = currency_to.upper().strip()
    
    # Construir query de búsqueda
    if date:
        query = f"tipo de cambio {currency_from} {currency_to} {date}"
    else:
        query = f"tipo de cambio {currency_from} {currency_to} hoy"
    
    logger.info(f"[EXCHANGE_RATE] Buscando tipo de cambio: {currency_from} -> {currency_to} ({date or 'hoy'})")
    
    try:
        # Buscar información del tipo de cambio
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))
        
        if not results:
            raise ValueError(f"No se encontró información del tipo de cambio {currency_from}/{currency_to}")
        
        # Intentar extraer el tipo de cambio del primer resultado
        # Esto es una aproximación - en producción podrías usar una API especializada
        first_result = results[0]
        snippet = first_result.get("body", "").lower()
        
        # Buscar números que parezcan tipos de cambio (ej: "1 USD = 0.92 EUR")
        import re
        # Patrón: número seguido de moneda = número seguido de moneda
        pattern = r'(\d+\.?\d*)\s*(?:usd|eur|gbp|usd|eur|gbp)'
        matches = re.findall(pattern, snippet)
        
        # Si no encontramos patrón claro, retornar información básica
        rate = None
        if matches and len(matches) >= 2:
            try:
                # Intentar calcular ratio
                val1 = float(matches[0])
                val2 = float(matches[1])
                if currency_from == "EUR" and currency_to != "EUR":
                    rate = val2 / val1 if val1 != 0 else None
                else:
                    rate = val1 / val2 if val2 != 0 else None
            except (ValueError, ZeroDivisionError):
                pass
        
        result = {
            "currency_from": currency_from,
            "currency_to": currency_to,
            "date": date or datetime.now().strftime("%Y-%m-%d"),
            "rate": rate,
            "source": first_result.get("href", ""),
            "snippet": first_result.get("body", "")[:200]  # Primeros 200 chars
        }
        
        logger.info(f"[EXCHANGE_RATE] Tipo de cambio encontrado: {rate}")
        return result
        
    except Exception as e:
        logger.error(f"[EXCHANGE_RATE] Error buscando tipo de cambio: {e}")
        raise ValueError(f"Error buscando tipo de cambio: {str(e)}")


@tool
def verify_company_info(company_name: str, country: Optional[str] = None) -> Dict[str, Any]:
    """
    Verifica información de una empresa/proveedor en internet.
    Busca NIF/VAT, dirección, información de contacto, etc.
    
    Args:
        company_name: Nombre de la empresa (ej: "Amazon España", "Meta Platforms")
        country: País (opcional, para refinar búsqueda, ej: "España", "ES")
    
    Returns:
        Dict con información encontrada:
        - company_name: Nombre de la empresa
        - nif_vat: NIF/VAT encontrado (si aplica)
        - address: Dirección (si encontrada)
        - website: Sitio web
        - snippets: Fragmentos de texto relevantes
        - sources: URLs de las fuentes
    """
    if not DDG_AVAILABLE:
        raise ValueError("Búsqueda web no disponible: duckduckgo-search no está instalado")
    
    # Construir query de búsqueda
    if country:
        query = f"{company_name} {country} NIF VAT información empresa"
    else:
        query = f"{company_name} NIF VAT información empresa"
    
    logger.info(f"[VERIFY_COMPANY] Verificando información de: {company_name} ({country or 'sin país'})")
    
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
        
        if not results:
            return {
                "company_name": company_name,
                "nif_vat": None,
                "address": None,
                "website": None,
                "snippets": [],
                "sources": [],
                "found": False
            }
        
        # Extraer información de los resultados
        snippets = [r.get("body", "") for r in results]
        sources = [r.get("href", "") for r in results]
        
        # Buscar NIF/VAT en los snippets
        import re
        nif_vat = None
        # Patrones comunes: B12345678, ESB12345678, VAT: ES123456789
        nif_patterns = [
            r'\b([A-Z]\d{8})\b',  # B12345678
            r'\b(ES[A-Z]\d{8})\b',  # ESB12345678
            r'VAT[:\s]+([A-Z]{2}?\d{8,9})',  # VAT: ES123456789
            r'NIF[:\s]+([A-Z]?\d{8,9})',  # NIF: B12345678
        ]
        
        for snippet in snippets:
            for pattern in nif_patterns:
                match = re.search(pattern, snippet, re.IGNORECASE)
                if match:
                    nif_vat = match.group(1).upper()
                    break
            if nif_vat:
                break
        
        # Buscar dirección (patrón básico)
        address = None
        address_pattern = r'(Calle|Avenida|Av\.|Plaza|Paseo)[\s\w,]+(?:Madrid|Barcelona|Valencia|Sevilla|España)'
        for snippet in snippets:
            match = re.search(address_pattern, snippet, re.IGNORECASE)
            if match:
                address = match.group(0)
                break
        
        # Buscar website
        website = None
        url_pattern = r'https?://(?:www\.)?([a-zA-Z0-9-]+\.[a-zA-Z]{2,})'
        for source in sources:
            match = re.search(url_pattern, source)
            if match:
                website = match.group(0)
                break
        
        result = {
            "company_name": company_name,
            "nif_vat": nif_vat,
            "address": address,
            "website": website,
            "snippets": snippets[:3],  # Primeros 3 snippets
            "sources": sources[:3],  # Primeras 3 fuentes
            "found": True
        }
        
        logger.info(f"[VERIFY_COMPANY] Información encontrada - NIF: {nif_vat}, Website: {website}")
        return result
        
    except Exception as e:
        logger.error(f"[VERIFY_COMPANY] Error verificando empresa: {e}")
        raise ValueError(f"Error verificando información de empresa: {str(e)}")


# Lista de herramientas de búsqueda web
WEB_SEARCH_TOOLS = [web_search, search_exchange_rate, verify_company_info]
