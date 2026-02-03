# consulta_executor.py
# Ejecutor de acciones para el agente de consulta
# Soporta dos modos: API (llamadas a endpoints) y SQL (consultas directas con validación)

import os
import re
import json
import logging
import httpx
import certifi
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()

# Whitelist de tablas permitidas
ALLOWED_TABLES = {
    "facturas",
    "ventas",
    "facturas_generadas",
    "uploads",  # Para consultas de estado de procesamiento
}

# Comandos SQL peligrosos (no permitidos)
DANGEROUS_SQL_PATTERNS = re.compile(
    r"\b(DROP|DELETE|UPDATE|INSERT|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|EXEC|EXECUTE)\b",
    re.IGNORECASE,
)

# Tablas que requieren filtrado por user_id
TABLES_WITH_USER_ID = {
    "facturas_generadas",  # Tiene created_by
    "uploads",  # Puede tener user_id
}


async def execute_api_action(action: Dict[str, Any], user_id: Optional[str] = None) -> Any:
    """
    Ejecuta una acción que llama a un endpoint de la API.
    
    Args:
        action: Diccionario con 'type': 'api', 'endpoint': str, 'method': str, 'params': dict
        user_id: ID del usuario (para autenticación si es necesario)
    
    Returns:
        Datos de respuesta de la API
    """
    logger.debug("[EJECUTOR] Iniciando ejecución de acción API")
    logger.debug(f"[EJECUTOR] Action recibida: {json.dumps(action, indent=2, ensure_ascii=False)}")
    logger.debug(f"[EJECUTOR] User ID: {user_id}")
    
    endpoint = action.get("endpoint", "")
    method = action.get("method", "GET").upper()
    params = action.get("params", {})
    headers = action.get("headers", {})

    if not endpoint:
        logger.error("[EJECUTOR] Endpoint no especificado")
        raise ValueError("Endpoint no especificado en la acción")

    # Construir URL completa
    # Para endpoints internos, usar localhost
    if endpoint.startswith("http"):
        url = endpoint
    else:
        # Asegurar que el endpoint empiece con /
        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"
        base_url = "http://localhost:8000"
        url = f"{base_url}{endpoint}"

    # Añadir parámetros de query si es GET
    if method == "GET" and params:
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        url = f"{url}?{query_string}"

    logger.info(f"[EJECUTOR] Llamando {method} {url}")
    logger.debug(f"[EJECUTOR] Parámetros: {params}")
    logger.debug(f"[EJECUTOR] Headers: {headers}")

    try:
        async with httpx.AsyncClient(
            timeout=30, 
            verify=certifi.where(),
            follow_redirects=True  # Seguir redirecciones automáticamente (307, 308, etc.)
        ) as client:
            if method == "GET":
                logger.debug(f"[EJECUTOR] Enviando GET request...")
                response = await client.get(url, headers=headers, follow_redirects=True)
            elif method == "POST":
                logger.debug(f"[EJECUTOR] Enviando POST request...")
                response = await client.post(url, json=params, headers=headers, follow_redirects=True)
            else:
                logger.error(f"[EJECUTOR] Método HTTP no soportado: {method}")
                raise ValueError(f"Método HTTP no soportado: {method}")

            logger.debug(f"[EJECUTOR] Respuesta recibida - Status: {response.status_code}")
            logger.debug(f"[EJECUTOR] Headers de respuesta: {dict(response.headers)}")
            content_type = response.headers.get('content-type', 'no especificado')
            logger.debug(f"[EJECUTOR] Content-Type: {content_type}")
            logger.debug(f"[EJECUTOR] Longitud de respuesta: {len(response.content)} bytes")
            
            # Log de los primeros caracteres de la respuesta para debug
            response_preview = response.text[:500] if response.text else "(vacío)"
            logger.debug(f"[EJECUTOR] Preview de respuesta (primeros 500 chars): {response_preview}")

            if response.status_code >= 400:
                error_text = response.text[:1000] if response.text else "(respuesta vacía)"
                logger.error(f"[EJECUTOR] Error HTTP {response.status_code}: {error_text}")
                logger.error(f"[EJECUTOR] Respuesta completa (primeros 2000 chars): {response.text[:2000] if response.text else '(vacía)'}")
                raise ValueError(
                    f"Error en API {endpoint}: {response.status_code} - {error_text[:500]}"
                )

            # Verificar que la respuesta no esté vacía
            if not response.content or len(response.content) == 0:
                logger.warning(f"[EJECUTOR] Respuesta vacía de {endpoint} - Status: {response.status_code}")
                # Una respuesta vacía puede ser válida (array vacío [])
                # Intentar parsear como JSON vacío
                try:
                    if response.text.strip() == '':
                        logger.info(f"[EJECUTOR] Respuesta vacía interpretada como array vacío")
                        return []
                    # Si hay texto, intentar parsearlo
                    result = response.json()
                    return result
                except:
                    logger.error(f"[EJECUTOR] No se pudo parsear respuesta vacía")
                    raise ValueError(f"Respuesta vacía de {endpoint} y no es JSON válido")

            # Intentar parsear JSON
            try:
                result = response.json()
                logger.info(f"[EJECUTOR] Respuesta parseada exitosamente")
                logger.debug(f"[EJECUTOR] Tipo de resultado: {type(result)}")
                if isinstance(result, list):
                    logger.debug(f"[EJECUTOR] Número de elementos: {len(result)}")
                    if len(result) > 0:
                        logger.debug(f"[EJECUTOR] Primer elemento (muestra): {json.dumps(result[0] if isinstance(result[0], dict) else str(result[0]), indent=2, ensure_ascii=False, default=str)[:500]}")
                elif isinstance(result, dict):
                    logger.debug(f"[EJECUTOR] Claves: {list(result.keys())}")
                return result
            except json.JSONDecodeError as e:
                # Respuesta no es JSON válido
                response_text = response.text[:2000] if response.text else "(respuesta vacía)"
                logger.error(f"[EJECUTOR] Error parseando JSON de {endpoint}: {e}")
                logger.error(f"[EJECUTOR] Posición del error: línea {e.lineno}, columna {e.colno}")
                logger.error(f"[EJECUTOR] Respuesta raw completa (primeros 2000 chars):\n{response_text}")
                logger.error(f"[EJECUTOR] Content-Type recibido: {content_type}")
                logger.error(f"[EJECUTOR] Status code: {response.status_code}")
                logger.error(f"[EJECUTOR] URL completa llamada: {url}")
                
                # Intentar detectar si es HTML (página de error)
                if response_text.strip().startswith('<') or 'html' in content_type.lower():
                    logger.error(f"[EJECUTOR] La respuesta parece ser HTML, no JSON")
                    # Extraer título o mensaje del HTML si es posible
                    html_title_match = re.search(r'<title>(.*?)</title>', response_text, re.IGNORECASE)
                    html_title = html_title_match.group(1) if html_title_match else "Error HTML"
                    raise ValueError(
                        f"La API {endpoint} devolvió HTML en lugar de JSON. "
                        f"Status: {response.status_code}. Título: {html_title}"
                    )
                
                # Si la respuesta es muy corta, mostrar todo
                if len(response_text) < 200:
                    logger.error(f"[EJECUTOR] Respuesta completa (corta): {response_text}")
                
                raise ValueError(
                    f"Respuesta inválida de {endpoint}: no es JSON válido. "
                    f"Status: {response.status_code}, Content-Type: {content_type}. "
                    f"Respuesta (primeros 500 chars): {response_text[:500]}"
                )
            except Exception as e:
                logger.exception(f"[EJECUTOR] Error inesperado parseando respuesta: {e}")
                logger.error(f"[EJECUTOR] Respuesta raw (primeros 1000 chars): {response.text[:1000] if response.text else '(vacía)'}")
                raise ValueError(f"Error parseando respuesta de {endpoint}: {str(e)}")
    except httpx.TimeoutException:
        logger.error(f"[EJECUTOR] Timeout al llamar a {endpoint}")
        raise ValueError(f"Timeout al llamar a {endpoint} (más de 30 segundos)")
    except httpx.RequestError as e:
        logger.error(f"[EJECUTOR] Error de red: {e}")
        raise ValueError(f"Error de red al llamar a {endpoint}: {str(e)}")
    except ValueError:
        raise  # Re-lanzar ValueError tal cual
    except Exception as e:
        logger.exception(f"[EJECUTOR] Error inesperado ejecutando acción API: {e}")
        raise ValueError(f"Error inesperado: {str(e)}")


def validate_sql_query(query: str, user_id: Optional[str] = None) -> tuple[bool, Optional[str]]:
    """
    Valida una consulta SQL antes de ejecutarla.
    
    Args:
        query: Consulta SQL a validar
        user_id: ID del usuario (para añadir filtros automáticos)
    
    Returns:
        Tupla (es_valida, mensaje_error)
    """
    logger.debug(f"[EJECUTOR] Validando SQL query: {query[:200]}...")
    query_upper = query.upper().strip()

    # 1. Solo SELECT permitido
    if not query_upper.startswith("SELECT"):
        logger.warning("[EJECUTOR] SQL validation failed: No es SELECT")
        return False, "Solo se permiten consultas SELECT"

    # 2. Detectar comandos peligrosos
    if DANGEROUS_SQL_PATTERNS.search(query):
        logger.warning("[EJECUTOR] SQL validation failed: Comandos peligrosos detectados")
        return False, "La consulta contiene comandos peligrosos no permitidos"

    # 3. Verificar que las tablas estén en whitelist
    table_found = False
    for table in ALLOWED_TABLES:
        # Buscar referencias a la tabla (con o sin esquema)
        pattern = re.compile(rf"\b{re.escape(table)}\b", re.IGNORECASE)
        if pattern.search(query):
            logger.debug(f"[EJECUTOR] Tabla permitida encontrada: {table}")
            table_found = True
            break
    
    if not table_found:
        # Verificar si hay alguna referencia a tabla
        table_pattern = re.compile(r"\bFROM\s+(\w+)", re.IGNORECASE)
        match = table_pattern.search(query)
        if match:
            table_name = match.group(1).lower()
            logger.warning(f"[EJECUTOR] SQL validation failed: Tabla '{table_name}' no permitida")
            if table_name not in ALLOWED_TABLES:
                return False, f"Tabla '{table_name}' no está en la whitelist de tablas permitidas"

    # 4. Límite de filas (añadir LIMIT si no existe)
    if "LIMIT" not in query_upper:
        # Añadir LIMIT 1000 al final
        query = f"{query.rstrip(';')} LIMIT 1000"
        logger.debug("[EJECUTOR] LIMIT 1000 añadido automáticamente")

    logger.debug("[EJECUTOR] SQL query validada exitosamente")
    return True, None


def add_user_filter(query: str, user_id: Optional[str], table_name: str) -> str:
    """
    Añade un filtro por user_id a la consulta si la tabla lo requiere.
    
    Args:
        query: Consulta SQL
        user_id: ID del usuario
        table_name: Nombre de la tabla
    
    Returns:
        Consulta SQL modificada
    """
    if not user_id or table_name not in TABLES_WITH_USER_ID:
        return query

    # Determinar el nombre del campo de usuario según la tabla
    user_field = "created_by" if table_name == "facturas_generadas" else "user_id"

    # Buscar si ya hay un WHERE
    query_upper = query.upper()
    if "WHERE" in query_upper:
        # Añadir AND user_id = '...' al WHERE existente
        # Buscar el WHERE y añadir después
        where_pos = query_upper.find("WHERE")
        # Encontrar el final del WHERE (antes de GROUP BY, ORDER BY, LIMIT)
        end_keywords = ["GROUP BY", "ORDER BY", "LIMIT", "HAVING"]
        end_pos = len(query)
        for keyword in end_keywords:
            pos = query_upper.find(keyword, where_pos)
            if pos != -1 and pos < end_pos:
                end_pos = pos

        before_where = query[:where_pos + 5]  # "WHERE"
        after_where = query[where_pos + 5:end_pos].strip()
        rest = query[end_pos:]

        # Añadir el filtro
        filter_clause = f"{user_field} = '{user_id}'"
        if after_where:
            new_where = f" {before_where} {after_where} AND {filter_clause} "
        else:
            new_where = f" {before_where} {filter_clause} "
        return f"{new_where}{rest}"
    else:
        # Añadir WHERE user_id = '...'
        # Buscar antes de GROUP BY, ORDER BY, LIMIT
        end_keywords = ["GROUP BY", "ORDER BY", "LIMIT", "HAVING"]
        end_pos = len(query)
        for keyword in end_keywords:
            pos = query_upper.find(keyword)
            if pos != -1 and pos < end_pos:
                end_pos = pos

        before = query[:end_pos].rstrip()
        rest = query[end_pos:]
        filter_clause = f"{user_field} = '{user_id}'"
        return f"{before} WHERE {filter_clause} {rest}"


async def execute_sql_action(action: Dict[str, Any], user_id: Optional[str] = None) -> Any:
    """
    Ejecuta una acción SQL con validaciones de seguridad.
    
    Args:
        action: Diccionario con 'type': 'sql', 'query': str
        user_id: ID del usuario (para filtrado automático)
    
    Returns:
        Resultados de la consulta
    """
    query = action.get("query", "").strip()

    if not query:
        raise ValueError("Query SQL no especificada")

    # Validar consulta
    is_valid, error_msg = validate_sql_query(query, user_id)
    if not is_valid:
        raise ValueError(f"Consulta SQL no válida: {error_msg}")

    # Detectar tabla principal
    table_match = re.search(r"\bFROM\s+(\w+)", query, re.IGNORECASE)
    table_name = table_match.group(1).lower() if table_match else None

    # Añadir filtro de usuario si es necesario
    if table_name and user_id:
        query = add_user_filter(query, user_id, table_name)

    # Ejecutar consulta en Supabase
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY no configuradas")

    url = f"{SUPABASE_URL}/rest/v1/rpc/execute_sql"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    # Nota: Supabase no tiene un RPC execute_sql por defecto
    # Usaremos la API REST directa si la tabla está en la whitelist
    # Para consultas complejas, necesitaremos crear una función RPC en Supabase
    # Por ahora, intentaremos usar la API REST con SELECT

    # Para consultas SQL, necesitamos usar la API REST de Supabase
    # que solo soporta SELECT simples. Para consultas complejas,
    # el agente debería usar las APIs existentes.
    # Por ahora, lanzamos un error indicando que se use APIs
    raise ValueError(
        "Las consultas SQL directas no están disponibles por seguridad. "
        "Por favor, usa acciones de tipo 'api' para consultas a tablas. "
        "Las APIs disponibles incluyen: /api/facturas/, /api/ventas/, /api/dashboard/"
    )

    # Si llegamos aquí, intentar usar RPC (requiere función en Supabase)
    payload = {"query": query}

    try:
        async with httpx.AsyncClient(timeout=10, verify=certifi.where()) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code != 200:
                raise ValueError(f"Error ejecutando SQL: {response.status_code} - {response.text}")
            return response.json()
    except httpx.RequestError as e:
        raise ValueError(f"Error de red ejecutando SQL: {str(e)}")


async def execute_action(action: Dict[str, Any], user_id: Optional[str] = None) -> Any:
    """
    Ejecuta una acción (API o SQL) según su tipo.
    
    Args:
        action: Diccionario con la acción a ejecutar
        user_id: ID del usuario
    
    Returns:
        Resultado de la acción
    """
    action_type = action.get("type", "").lower()
    logger.info(f"[EJECUTOR] Ejecutando acción de tipo: {action_type}")

    if action_type == "api":
        logger.debug("[EJECUTOR] Delegando a execute_api_action")
        result = await execute_api_action(action, user_id)
        logger.info("[EJECUTOR] Acción API completada")
        return result
    elif action_type == "sql":
        logger.debug("[EJECUTOR] Delegando a execute_sql_action")
        result = await execute_sql_action(action, user_id)
        logger.info("[EJECUTOR] Acción SQL completada")
        return result
    else:
        logger.error(f"[EJECUTOR] Tipo de acción no soportado: {action_type}")
        raise ValueError(f"Tipo de acción no soportado: {action_type}")
