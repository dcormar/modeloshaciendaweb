# consulta_tools.py
# Definición de herramientas LangChain para el agente de consulta

import logging
from typing import Optional, List, Dict, Any
from langchain.tools import tool
import httpx
import certifi
from datetime import datetime, timedelta

from services.consulta_web_tools import WEB_SEARCH_TOOLS

logger = logging.getLogger(__name__)


def _calculate_date_range(periodo: str) -> tuple[str, str]:
    """Calcula rango de fechas a partir de un período."""
    today = datetime.now()
    periodo_lower = periodo.lower()
    
    if "ultimos_3_meses" in periodo_lower or "últimos 3 meses" in periodo_lower or "last 3 months" in periodo_lower:
        desde = (today - timedelta(days=90)).strftime("%Y-%m-%d")
        hasta = today.strftime("%Y-%m-%d")
        return desde, hasta
    elif "este_año" in periodo_lower or "este año" in periodo_lower or "this year" in periodo_lower:
        desde = f"{today.year}-01-01"
        hasta = today.strftime("%Y-%m-%d")
        return desde, hasta
    elif "ultimo_mes" in periodo_lower or "último mes" in periodo_lower or "last month" in periodo_lower:
        desde = (today - timedelta(days=30)).strftime("%Y-%m-%d")
        hasta = today.strftime("%Y-%m-%d")
        return desde, hasta
    elif "ultimos_6_meses" in periodo_lower or "últimos 6 meses" in periodo_lower or "last 6 months" in periodo_lower:
        desde = (today - timedelta(days=180)).strftime("%Y-%m-%d")
        hasta = today.strftime("%Y-%m-%d")
        return desde, hasta
    
    # Default: últimos 3 meses
    desde = (today - timedelta(days=90)).strftime("%Y-%m-%d")
    hasta = today.strftime("%Y-%m-%d")
    return desde, hasta


async def _get_facturas_impl(
    desde: str, 
    hasta: str,
    proveedor: Optional[str] = None,
    pais_origen: Optional[str] = None,
    importe_min: Optional[float] = None,
    importe_max: Optional[float] = None,
    categoria: Optional[str] = None,
    moneda: Optional[str] = None,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Implementación async de get_facturas con filtros avanzados."""
    base_url = "http://localhost:8000"
    
    # Construir URL con parámetros
    params = [f"desde={desde}", f"hasta={hasta}"]
    
    if proveedor:
        params.append(f"proveedor={proveedor}")
    if pais_origen:
        params.append(f"pais_origen={pais_origen}")
    if importe_min is not None:
        params.append(f"importe_min={importe_min}")
    if importe_max is not None:
        params.append(f"importe_max={importe_max}")
    if categoria:
        params.append(f"categoria={categoria}")
    if moneda:
        params.append(f"moneda={moneda}")
    if limit is not None:
        params.append(f"limit={limit}")
    
    url = f"{base_url}/api/facturas/?" + "&".join(params)
    
    async with httpx.AsyncClient(
        timeout=30, 
        verify=certifi.where(),
        follow_redirects=True
    ) as client:
        response = await client.get(url)
        if response.status_code >= 400:
            raise ValueError(f"Error obteniendo facturas: {response.status_code}")
        return response.json()


@tool
def get_facturas(
    desde: str, 
    hasta: str,
    proveedor: Optional[str] = None,
    pais_origen: Optional[str] = None,
    importe_min: Optional[float] = None,
    importe_max: Optional[float] = None,
    categoria: Optional[str] = None,
    moneda: Optional[str] = None,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Obtiene facturas con múltiples filtros opcionales.
    
    Args:
        desde: Fecha inicio en formato YYYY-MM-DD (requerido)
        hasta: Fecha fin en formato YYYY-MM-DD (requerido)
        proveedor: Filtrar por proveedor (búsqueda parcial, opcional). Ej: "Meta", "Amazon"
        pais_origen: Filtrar por país de origen (opcional). Ej: "ES", "US"
        importe_min: Importe mínimo en EUR (opcional). Ej: 100.0
        importe_max: Importe máximo en EUR (opcional). Ej: 1000.0
        categoria: Filtrar por categoría (opcional). Ej: "Marketing", "Software"
        moneda: Filtrar por moneda (opcional). Ej: "EUR", "USD"
        limit: Límite de resultados (opcional, máx 1000). Ej: 50
    
    Returns:
        Lista de facturas con campos: id, fecha, proveedor, 
        importe_total_euro, categoria, pais_origen, moneda, etc.
    
    Ejemplos de uso:
    - get_facturas(desde="2025-10-01", hasta="2026-01-01", proveedor="Meta")
    - get_facturas(desde="2025-10-01", hasta="2026-01-01", importe_min=100.0, categoria="Marketing")
    - get_facturas(desde="2025-10-01", hasta="2026-01-01", pais_origen="ES", moneda="EUR")
    """
    logger.debug(f"[TOOL] get_facturas(desde={desde}, hasta={hasta}, proveedor={proveedor}, "
                 f"pais_origen={pais_origen}, importe_min={importe_min}, importe_max={importe_max}, "
                 f"categoria={categoria}, moneda={moneda}, limit={limit})")
    
    try:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Si hay un loop corriendo, crear tarea
                import nest_asyncio
                nest_asyncio.apply()
                return asyncio.run(_get_facturas_impl(
                    desde, hasta, proveedor, pais_origen, importe_min, 
                    importe_max, categoria, moneda, limit
                ))
            else:
                return loop.run_until_complete(_get_facturas_impl(
                    desde, hasta, proveedor, pais_origen, importe_min, 
                    importe_max, categoria, moneda, limit
                ))
        except RuntimeError:
            return asyncio.run(_get_facturas_impl(
                desde, hasta, proveedor, pais_origen, importe_min, 
                importe_max, categoria, moneda, limit
            ))
    except Exception as e:
        logger.error(f"[TOOL] Error en get_facturas: {e}")
        raise ValueError(f"Error obteniendo facturas: {str(e)}")


async def _get_ventas_impl(desde: str, hasta: str) -> List[Dict[str, Any]]:
    """Implementación async de get_ventas."""
    base_url = "http://localhost:8000"
    url = f"{base_url}/api/ventas/?desde={desde}&hasta={hasta}"
    
    async with httpx.AsyncClient(
        timeout=30, 
        verify=certifi.where(),
        follow_redirects=True
    ) as client:
        response = await client.get(url)
        if response.status_code >= 400:
            raise ValueError(f"Error obteniendo ventas: {response.status_code}")
        return response.json()


@tool
def get_ventas(desde: str, hasta: str) -> List[Dict[str, Any]]:
    """
    Obtiene ventas filtradas por rango de fechas.
    
    Args:
        desde: Fecha inicio en formato YYYY-MM-DD
        hasta: Fecha fin en formato YYYY-MM-DD
    
    Returns:
        Lista de ventas con campos: ID, TRANSACTION_COMPLETE_DATE, 
        TOTAL_PRICE_OF_ITEMS_AMT_VAT_INCL, MARKETPLACE, etc.
    """
    logger.debug(f"[TOOL] get_ventas(desde={desde}, hasta={hasta})")
    
    try:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import nest_asyncio
                nest_asyncio.apply()
                return asyncio.run(_get_ventas_impl(desde, hasta))
            else:
                return loop.run_until_complete(_get_ventas_impl(desde, hasta))
        except RuntimeError:
            return asyncio.run(_get_ventas_impl(desde, hasta))
    except Exception as e:
        logger.error(f"[TOOL] Error en get_ventas: {e}")
        raise ValueError(f"Error obteniendo ventas: {str(e)}")


async def _get_dashboard_impl() -> Dict[str, Any]:
    """Implementación async de get_dashboard."""
    base_url = "http://localhost:8000"
    url = f"{base_url}/api/dashboard/"
    
    async with httpx.AsyncClient(
        timeout=30, 
        verify=certifi.where(),
        follow_redirects=True
    ) as client:
        response = await client.get(url)
        if response.status_code >= 400:
            raise ValueError(f"Error obteniendo dashboard: {response.status_code}")
        return response.json()


@tool
def get_dashboard() -> Dict[str, Any]:
    """
    Obtiene el resumen de los últimos 6 meses (ventas, gastos, facturas).
    
    Returns:
        Dict con:
        - ultimos_seis_meses: Lista de resúmenes mensuales
    """
    logger.debug("[TOOL] get_dashboard()")
    
    try:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import nest_asyncio
                nest_asyncio.apply()
                return asyncio.run(_get_dashboard_impl())
            else:
                return loop.run_until_complete(_get_dashboard_impl())
        except RuntimeError:
            return asyncio.run(_get_dashboard_impl())
    except Exception as e:
        logger.error(f"[TOOL] Error en get_dashboard: {e}")
        raise ValueError(f"Error obteniendo dashboard: {str(e)}")


async def _get_historico_impl(limit: int = 10) -> Dict[str, Any]:
    """Implementación async de get_historico."""
    base_url = "http://localhost:8000"
    url = f"{base_url}/api/dashboard/historico?limit={limit}"
    
    async with httpx.AsyncClient(
        timeout=30, 
        verify=certifi.where(),
        follow_redirects=True
    ) as client:
        response = await client.get(url)
        if response.status_code >= 400:
            raise ValueError(f"Error obteniendo histórico: {response.status_code}")
        return response.json()


@tool
def get_historico(limit: int = 10) -> Dict[str, Any]:
    """
    Obtiene el histórico de operaciones recientes (facturas e ingresos).
    
    Args:
        limit: Número máximo de operaciones a retornar (default: 10)
    
    Returns:
        Dict con:
        - items: Lista de operaciones con tipo, fecha, descripcion, importe_eur
    """
    logger.debug(f"[TOOL] get_historico(limit={limit})")
    
    try:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import nest_asyncio
                nest_asyncio.apply()
                return asyncio.run(_get_historico_impl(limit))
            else:
                return loop.run_until_complete(_get_historico_impl(limit))
        except RuntimeError:
            return asyncio.run(_get_historico_impl(limit))
    except Exception as e:
        logger.error(f"[TOOL] Error en get_historico: {e}")
        raise ValueError(f"Error obteniendo histórico: {str(e)}")


@tool
def filter_data(data: List[Dict[str, Any]], campo: str, valor: Any) -> List[Dict[str, Any]]:
    """
    Filtra una lista de datos por un campo y valor específicos.
    
    Args:
        data: Lista de diccionarios a filtrar
        campo: Nombre del campo por el que filtrar
        valor: Valor a buscar (puede ser string, número, etc.)
    
    Returns:
        Lista filtrada de diccionarios que coinciden con el criterio
    """
    logger.debug(f"[TOOL] filter_data(campo={campo}, valor={valor}, elementos={len(data) if isinstance(data, list) else 0})")
    
    if not isinstance(data, list):
        raise ValueError("Los datos deben ser una lista")
    
    # Filtrar (comparación flexible: case-insensitive para strings)
    filtered = []
    for item in data:
        if not isinstance(item, dict):
            continue
        
        item_value = item.get(campo)
        
        # Comparación flexible
        if isinstance(valor, str) and isinstance(item_value, str):
            # Case-insensitive para strings
            if valor.lower() in item_value.lower() or item_value.lower() in valor.lower():
                filtered.append(item)
        elif item_value == valor:
            filtered.append(item)
    
    logger.debug(f"[TOOL] filter_data: {len(data)} -> {len(filtered)} elementos")
    return filtered


@tool
def aggregate_data(
    data: List[Dict[str, Any]], 
    operation: str, 
    field: str
) -> float:
    """
    Agrega datos numéricos de una lista.
    
    Args:
        data: Lista de diccionarios
        operation: Operación a realizar ("sum", "count", "avg")
        field: Campo numérico sobre el que operar
    
    Returns:
        Resultado de la operación (float)
    """
    logger.debug(f"[TOOL] aggregate_data(operation={operation}, field={field}, elementos={len(data) if isinstance(data, list) else 0})")
    
    if not isinstance(data, list):
        raise ValueError("Los datos deben ser una lista")
    
    if operation == "count":
        return float(len(data))
    
    # Extraer valores numéricos
    values = []
    for item in data:
        if not isinstance(item, dict):
            continue
        value = item.get(field)
        if isinstance(value, (int, float)):
            values.append(float(value))
        elif isinstance(value, str):
            try:
                # Intentar parsear string numérico
                values.append(float(value.replace(",", ".")))
            except ValueError:
                pass
    
    if not values:
        return 0.0
    
    if operation == "sum":
        result = sum(values)
    elif operation == "avg":
        result = sum(values) / len(values)
    else:
        raise ValueError(f"Operación no soportada: {operation}. Usa 'sum', 'count' o 'avg'")
    
    logger.debug(f"[TOOL] aggregate_data: {operation}({field}) = {result}")
    return result


# Herramientas API locales
API_TOOLS = [
    get_facturas,
    get_ventas,
    get_dashboard,
    get_historico,
    filter_data,
    aggregate_data,
]

# Todas las herramientas disponibles (API + Web Search)
# Las herramientas MCP se añadirán después
ALL_TOOLS = API_TOOLS + WEB_SEARCH_TOOLS
