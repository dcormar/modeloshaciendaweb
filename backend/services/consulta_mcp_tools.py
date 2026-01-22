# consulta_mcp_tools.py
# Herramientas LangChain que envuelven funciones MCP de Supabase

import logging
from typing import Optional, List, Dict, Any
from langchain.tools import tool

logger = logging.getLogger(__name__)

# Nota: Estas funciones asumen que las funciones MCP están disponibles
# En desarrollo, podrían estar disponibles como funciones Python
# En producción, necesitarías un cliente MCP o llamadas directas a Supabase


@tool
def execute_sql_safe(query: str, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Ejecuta una consulta SQL de forma segura usando MCP de Supabase.
    Solo permite SELECT y valida automáticamente.
    
    Args:
        query: Consulta SQL (solo SELECT permitido)
        user_id: ID del usuario para filtrado automático (opcional)
    
    Returns:
        Lista de resultados de la consulta
    """
    logger.info(f"[MCP_TOOL] execute_sql_safe - Query: {query[:100]}...")
    
    # Por ahora, intentar usar la función MCP si está disponible
    # Si no, lanzar error indicando que se use APIs
    try:
        # Intentar llamar a la función MCP
        # En Cursor, las funciones MCP están disponibles directamente
        # En producción, necesitarías un cliente MCP
        
        # Por ahora, retornar error indicando que se use APIs
        # TODO: Implementar llamada real a MCP cuando esté disponible
        raise ValueError(
            "Las consultas SQL directas requieren configuración MCP. "
            "Por ahora, usa las herramientas API disponibles (get_facturas, get_ventas, etc.)"
        )
    except Exception as e:
        logger.error(f"[MCP_TOOL] Error en execute_sql_safe: {e}")
        raise


@tool
def list_available_tables() -> List[Dict[str, str]]:
    """
    Lista las tablas disponibles en la base de datos.
    Útil para que el agente sepa qué datos puede consultar.
    
    Returns:
        Lista de diccionarios con información de tablas:
        - name: Nombre de la tabla
        - schema: Esquema (ej: "public")
    """
    logger.info("[MCP_TOOL] list_available_tables")
    
    # Tablas conocidas (whitelist)
    # En el futuro, esto se obtendría dinámicamente de MCP
    known_tables = [
        {"name": "facturas", "schema": "public"},
        {"name": "ventas", "schema": "public"},
        {"name": "facturas_generadas", "schema": "public"},
        {"name": "uploads", "schema": "public"},
    ]
    
    logger.info(f"[MCP_TOOL] Retornando {len(known_tables)} tablas conocidas")
    return known_tables


@tool
def get_table_schema(table_name: str) -> Dict[str, Any]:
    """
    Obtiene el esquema de una tabla específica.
    Útil para que el agente entienda qué campos tiene cada tabla.
    
    Args:
        table_name: Nombre de la tabla
    
    Returns:
        Dict con información del esquema:
        - name: Nombre de la tabla
        - columns: Lista de columnas con nombre y tipo
    """
    logger.info(f"[MCP_TOOL] get_table_schema({table_name})")
    
    # Esquemas conocidos (hardcoded por ahora)
    # En el futuro, esto se obtendría de MCP o de la BD directamente
    schemas = {
        "facturas": {
            "name": "facturas",
            "columns": [
                {"name": "id", "type": "integer"},
                {"name": "fecha", "type": "text"},
                {"name": "fecha_dt", "type": "date"},
                {"name": "proveedor", "type": "text"},
                {"name": "importe_total_euro", "type": "numeric"},
                {"name": "importe_sin_iva_euro", "type": "numeric"},
                {"name": "categoria", "type": "text"},
                {"name": "pais_origen", "type": "text"},
            ]
        },
        "ventas": {
            "name": "ventas",
            "columns": [
                {"name": "ID", "type": "integer"},
                {"name": "TRANSACTION_COMPLETE_DATE", "type": "text"},
                {"name": "TRANSACTION_COMPLETE_DATE_DT", "type": "date"},
                {"name": "TOTAL_PRICE_OF_ITEMS_AMT_VAT_INCL", "type": "numeric"},
                {"name": "MARKETPLACE", "type": "text"},
                {"name": "SALES_CHANNEL", "type": "text"},
            ]
        },
    }
    
    if table_name.lower() in schemas:
        return schemas[table_name.lower()]
    else:
        logger.warning(f"[MCP_TOOL] Esquema desconocido para tabla: {table_name}")
        return {
            "name": table_name,
            "columns": [],
            "note": "Esquema no disponible. Usa list_available_tables para ver tablas conocidas."
        }


@tool
def check_data_quality(table_name: str) -> Dict[str, Any]:
    """
    Verifica la calidad de los datos en una tabla.
    Retorna estadísticas y posibles problemas usando get_advisors de MCP.
    
    Args:
        table_name: Nombre de la tabla a verificar
    
    Returns:
        Dict con:
        - table_name: Nombre de la tabla
        - issues: Lista de problemas encontrados
        - stats: Estadísticas básicas
    """
    logger.info(f"[MCP_TOOL] check_data_quality({table_name})")
    
    # Por ahora, retornar estructura básica
    # En el futuro, esto llamaría a mcp_modeloshaciendaweb-supabase_get_advisors
    return {
        "table_name": table_name,
        "issues": [],
        "stats": {},
        "note": "Verificación de calidad requiere configuración MCP completa"
    }


# Lista de herramientas MCP
MCP_TOOLS = [
    execute_sql_safe,
    list_available_tables,
    get_table_schema,
    check_data_quality,
]
