# consulta_agent_service.py
# Servicio del agente IA para procesar consultas en lenguaje natural

import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
import openai

from services.consulta_executor import execute_action

logger = logging.getLogger(__name__)

# Configuración
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)


# Prompt para análisis de consulta
ANALYSIS_PROMPT = """Eres un asistente que analiza consultas de usuarios sobre sus datos financieros.

Analiza la siguiente consulta del usuario y extrae:
1. Tipo de datos solicitados (facturas, ventas, resumen, etc.)
2. Filtros mencionados (fechas, proveedores, categorías, etc.)
3. Operaciones requeridas (suma, conteo, listado, etc.)
4. Formato de salida sugerido (tabla, texto, gráfica)

Consulta del usuario: "{query}"

Responde SOLO con un JSON válido con esta estructura:
{{
  "data_type": "facturas|ventas|resumen|mixto",
  "filters": {{
    "fechas": {{"desde": "YYYY-MM-DD o null", "hasta": "YYYY-MM-DD o null", "periodo": "ultimos_3_meses|este_año|etc o null"}},
    "proveedor": "nombre o null",
    "categoria": "nombre o null",
    "otros": {{}}
  }},
  "operation": "listar|sumar|contar|promedio|grafica",
  "suggested_format": "table|text|chart"
}}
"""

# Prompt para planificación de acciones
PLANNING_PROMPT = """Eres un asistente que planifica acciones para responder consultas sobre datos financieros.

Basándote en el análisis de la consulta, genera un plan de acciones en formato JSON.

Análisis: {analysis}

APIs disponibles:
- GET /api/facturas?desde=YYYY-MM-DD&hasta=YYYY-MM-DD - Obtener facturas
- GET /ventas?desde=YYYY-MM-DD&hasta=YYYY-MM-DD - Obtener ventas
- GET /dashboard/ - Obtener resumen de últimos 6 meses
- GET /dashboard/historico?limit=N - Obtener histórico de operaciones

Responde SOLO con un JSON válido con esta estructura:
{{
  "actions": [
    {{
      "type": "api",
      "endpoint": "/api/facturas",
      "method": "GET",
      "params": {{"desde": "2024-01-01", "hasta": "2024-12-31"}},
      "description": "Obtener facturas del período"
    }}
  ],
  "post_process": {{
    "filter_by": "proveedor|catégoria|etc o null",
    "filter_value": "valor o null",
    "aggregate": "sum|count|avg o null",
    "aggregate_field": "importe_total_euro|etc o null"
  }}
}}
"""

# Prompt para formateo de resultados
FORMATTING_PROMPT = """Eres un asistente que formatea resultados de consultas.

Datos obtenidos: {data}
Consulta original: "{query}"
Formato sugerido: {suggested_format}

Formatea los datos según el formato sugerido y genera una respuesta estructurada.

Para formato "table": devuelve un array de objetos con las filas.
Para formato "text": devuelve un texto narrativo explicando los resultados.
Para formato "chart": devuelve datos estructurados para gráfica con labels y series.

Responde SOLO con un JSON válido:
{{
  "format": "table|text|chart",
  "data": <datos formateados>,
  "metadata": {{
    "title": "Título descriptivo",
    "description": "Descripción opcional",
    "chartType": "bar|line|pie (solo si format=chart)",
    "chartLabels": ["label1", "label2", ...] (solo si format=chart),
    "chartSeries": [
      {{"name": "Serie 1", "data": [1, 2, 3], "color": "#2563eb"}}
    ] (solo si format=chart)
  }}
}}
"""


def _call_llm(prompt: str, model: str = "gemini-2.5-flash-lite") -> str:
    """Llama a la API de Gemini o OpenAI."""
    logger.debug(f"[LLM] Llamando a modelo: {model}")
    logger.debug(f"[LLM] Longitud del prompt: {len(prompt)} caracteres")
    
    try:
        if GOOGLE_API_KEY and model.startswith("gemini"):
            logger.debug("[LLM] Usando Gemini")
            try:
                genai_model = genai.GenerativeModel(model)
                logger.debug("[LLM] Modelo Gemini creado, generando contenido...")
                response = genai_model.generate_content(prompt)
                logger.debug(f"[LLM] Respuesta de Gemini recibida (longitud: {len(response.text) if response.text else 0} chars)")
                if not response.text:
                    logger.error("[LLM] Respuesta vacía de Gemini")
                    raise ValueError("Respuesta vacía de Gemini")
                return response.text
            except google_exceptions.ResourceExhausted:
                logger.warning("[LLM] Gemini rate limit detectado, intentando con OpenAI...")
                if OPENAI_API_KEY:
                    return _call_llm_openai(prompt)
                raise ValueError("Gemini tiene rate limit y OpenAI no está configurado")
            except Exception as e:
                logger.error(f"[LLM] Error con Gemini: {e}")
                if OPENAI_API_KEY:
                    logger.info("[LLM] Intentando fallback a OpenAI...")
                    return _call_llm_openai(prompt)
                raise
        elif OPENAI_API_KEY:
            logger.debug("[LLM] Usando OpenAI directamente")
            return _call_llm_openai(prompt)
        else:
            logger.error("[LLM] No hay API key configurada")
            raise ValueError("No hay API key configurada (GOOGLE_API_KEY o OPENAI_API_KEY)")
    except ValueError:
        raise  # Re-lanzar ValueError
    except Exception as e:
        logger.error(f"[LLM] Error llamando a LLM: {e}")
        raise ValueError(f"Error en servicio de IA: {str(e)}")


def _call_llm_openai(prompt: str) -> str:
    """Llama a OpenAI como fallback."""
    logger.debug("[LLM] Llamando a OpenAI (gpt-4o-mini)")
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        logger.debug("[LLM] Cliente OpenAI creado, enviando request...")
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            timeout=30,
        )
        logger.debug(f"[LLM] Respuesta de OpenAI recibida")
        content = response.choices[0].message.content
        logger.debug(f"[LLM] Contenido extraído (longitud: {len(content) if content else 0} chars)")
        if not content:
            logger.error("[LLM] Respuesta vacía de OpenAI")
            raise ValueError("Respuesta vacía de OpenAI")
        return content
    except openai.RateLimitError:
        logger.error("[LLM] OpenAI rate limit")
        raise ValueError("OpenAI también tiene rate limit. Intenta más tarde.")
    except Exception as e:
        logger.error(f"[LLM] Error con OpenAI: {e}")
        raise ValueError(f"Error en OpenAI: {str(e)}")


def _parse_json_response(text: str) -> Dict[str, Any]:
    """Parsea la respuesta JSON de la IA."""
    text = text.strip()
    # Limpiar markdown code blocks
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
        logger.error(f"Error parseando JSON: {e}\nTexto: {text[:500]}")
        raise ValueError(f"Respuesta de IA no es JSON válido: {str(e)}")


def _calculate_date_range(periodo: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Calcula rango de fechas a partir de un período."""
    if not periodo:
        return None, None

    today = datetime.now()
    periodo_lower = periodo.lower()

    if "ultimos_3_meses" in periodo_lower or "últimos 3 meses" in periodo_lower:
        desde = (today - timedelta(days=90)).strftime("%Y-%m-%d")
        hasta = today.strftime("%Y-%m-%d")
        return desde, hasta
    elif "este_año" in periodo_lower or "este año" in periodo_lower:
        desde = f"{today.year}-01-01"
        hasta = today.strftime("%Y-%m-%d")
        return desde, hasta
    elif "ultimo_mes" in periodo_lower or "último mes" in periodo_lower:
        desde = (today - timedelta(days=30)).strftime("%Y-%m-%d")
        hasta = today.strftime("%Y-%m-%d")
        return desde, hasta
    elif "ultimos_6_meses" in periodo_lower or "últimos 6 meses" in periodo_lower:
        desde = (today - timedelta(days=180)).strftime("%Y-%m-%d")
        hasta = today.strftime("%Y-%m-%d")
        return desde, hasta

    return None, None


async def analyze_query(query: str) -> Dict[str, Any]:
    """Analiza la consulta del usuario."""
    logger.info("[AGENTE] Paso 1: Analizando consulta...")
    logger.debug(f"[AGENTE] Query a analizar: {query}")
    
    prompt = ANALYSIS_PROMPT.format(query=query)
    logger.debug(f"[AGENTE] Prompt de análisis generado (longitud: {len(prompt)} chars)")
    
    response_text = _call_llm(prompt)
    logger.debug(f"[AGENTE] Respuesta de IA recibida (longitud: {len(response_text)} chars)")
    logger.debug(f"[AGENTE] Respuesta raw (primeros 500 chars): {response_text[:500]}")
    
    analysis = _parse_json_response(response_text)
    logger.info(f"[AGENTE] Análisis completado - Tipo de datos: {analysis.get('data_type')}")
    logger.debug(f"[AGENTE] Análisis completo: {json.dumps(analysis, indent=2, ensure_ascii=False)}")
    
    return analysis


async def plan_actions(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Genera un plan de acciones basado en el análisis."""
    logger.info("[AGENTE] Paso 2: Planificando acciones...")
    logger.debug(f"[AGENTE] Análisis recibido: {json.dumps(analysis, indent=2, ensure_ascii=False)}")
    
    analysis_str = json.dumps(analysis, indent=2, ensure_ascii=False)
    prompt = PLANNING_PROMPT.format(analysis=analysis_str)
    logger.debug(f"[AGENTE] Prompt de planificación generado (longitud: {len(prompt)} chars)")
    
    response_text = _call_llm(prompt)
    logger.debug(f"[AGENTE] Respuesta de planificación recibida (longitud: {len(response_text)} chars)")
    logger.debug(f"[AGENTE] Plan raw (primeros 500 chars): {response_text[:500]}")
    
    plan = _parse_json_response(response_text)
    num_actions = len(plan.get("actions", []))
    logger.info(f"[AGENTE] Planificación completada - {num_actions} acción(es) generada(s)")
    logger.debug(f"[AGENTE] Plan completo: {json.dumps(plan, indent=2, ensure_ascii=False)}")
    
    return plan


async def format_result(
    data: Any, query: str, suggested_format: str, post_process: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Formatea los resultados según el formato sugerido."""
    logger.info(f"[AGENTE] Paso 4: Formateando resultado como '{suggested_format}'...")
    logger.debug(f"[AGENTE] Tipo de datos a formatear: {type(data)}")
    if isinstance(data, list):
        logger.debug(f"[AGENTE] Número de elementos: {len(data)}")
        if len(data) > 0:
            logger.debug(f"[AGENTE] Primer elemento (muestra): {json.dumps(data[0] if isinstance(data[0], dict) else str(data[0]), indent=2, ensure_ascii=False, default=str)[:500]}")
    elif isinstance(data, dict):
        logger.debug(f"[AGENTE] Claves del diccionario: {list(data.keys())}")
    
    data_str = json.dumps(data, indent=2, ensure_ascii=False, default=str)
    logger.debug(f"[AGENTE] Datos serializados (longitud: {len(data_str)} chars)")
    
    prompt = FORMATTING_PROMPT.format(
        data=data_str, query=query, suggested_format=suggested_format
    )
    logger.debug(f"[AGENTE] Prompt de formateo generado (longitud: {len(prompt)} chars)")
    
    response_text = _call_llm(prompt)
    logger.debug(f"[AGENTE] Respuesta de formateo recibida (longitud: {len(response_text)} chars)")
    logger.debug(f"[AGENTE] Formato raw (primeros 500 chars): {response_text[:500]}")
    
    formatted = _parse_json_response(response_text)
    logger.info(f"[AGENTE] Formateo completado - Formato final: {formatted.get('format')}")
    logger.debug(f"[AGENTE] Resultado formateado completo: {json.dumps(formatted, indent=2, ensure_ascii=False, default=str)[:1000]}")
    
    return formatted


def _apply_post_process(data: Any, post_process: Dict[str, Any]) -> Any:
    """Aplica post-procesamiento a los datos."""
    if not post_process or not isinstance(data, list):
        return data

    # Filtrar
    filter_by = post_process.get("filter_by")
    filter_value = post_process.get("filter_value")
    if filter_by and filter_value and isinstance(data, list):
        data = [item for item in data if item.get(filter_by) == filter_value]

    # Agregar
    aggregate = post_process.get("aggregate")
    aggregate_field = post_process.get("aggregate_field")
    if aggregate and aggregate_field and isinstance(data, list):
        values = [item.get(aggregate_field, 0) for item in data if isinstance(item.get(aggregate_field), (int, float))]
        if aggregate == "sum":
            return sum(values)
        elif aggregate == "count":
            return len(data)
        elif aggregate == "avg" and values:
            return sum(values) / len(values)

    return data


async def process_query(query: str, user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Procesa una consulta del usuario y retorna resultados formateados.
    
    Args:
        query: Consulta en lenguaje natural
        user_id: ID del usuario (para filtrado)
    
    Returns:
        Diccionario con formato, datos y metadata
    """
    try:
        logger.info("=" * 80)
        logger.info(f"[AGENTE] Iniciando procesamiento de consulta")
        logger.info(f"[AGENTE] Query: {query}")
        logger.info(f"[AGENTE] User ID: {user_id}")
        logger.debug("=" * 80)
        
        # 1. Analizar consulta
        analysis = await analyze_query(query)

        # 2. Calcular fechas si hay período
        logger.debug("[AGENTE] Calculando rangos de fechas si es necesario...")
        filters = analysis.get("filters", {})
        fechas = filters.get("fechas", {})
        periodo = fechas.get("periodo")
        if periodo:
            desde, hasta = _calculate_date_range(periodo)
            if desde and hasta:
                fechas["desde"] = desde
                fechas["hasta"] = hasta
                logger.debug(f"[AGENTE] Rango de fechas calculado: {desde} a {hasta}")
            else:
                logger.debug(f"[AGENTE] No se pudo calcular rango para período: {periodo}")
        else:
            logger.debug("[AGENTE] No hay período especificado en los filtros")

        # 3. Planificar acciones
        plan = await plan_actions(analysis)

        # 4. Ejecutar acciones
        logger.info("[AGENTE] Paso 3: Ejecutando acciones...")
        actions = plan.get("actions", [])
        if not actions:
            logger.error("[AGENTE] No se generaron acciones para ejecutar")
            raise ValueError("No se generaron acciones para ejecutar")

        logger.info(f"[AGENTE] Total de acciones a ejecutar: {len(actions)}")
        results = []
        for idx, action in enumerate(actions, 1):
            action_desc = action.get('description', action.get('type', 'desconocida'))
            logger.info(f"[AGENTE] Ejecutando acción {idx}/{len(actions)}: {action_desc}")
            logger.debug(f"[AGENTE] Detalles de acción {idx}: {json.dumps(action, indent=2, ensure_ascii=False)}")
            
            try:
                result = await execute_action(action, user_id)
                logger.info(f"[AGENTE] Acción {idx} completada exitosamente")
                logger.debug(f"[AGENTE] Resultado de acción {idx} - Tipo: {type(result)}")
                if isinstance(result, list):
                    logger.debug(f"[AGENTE] Resultado de acción {idx} - Elementos: {len(result)}")
                    if len(result) > 0:
                        logger.debug(f"[AGENTE] Primer elemento (muestra): {json.dumps(result[0] if isinstance(result[0], dict) else str(result[0]), indent=2, ensure_ascii=False, default=str)[:500]}")
                elif isinstance(result, dict):
                    logger.debug(f"[AGENTE] Resultado de acción {idx} - Claves: {list(result.keys())}")
                results.append(result)
            except Exception as e:
                logger.error(f"[AGENTE] Error ejecutando acción {idx} ({action_desc}): {e}")
                logger.exception(f"[AGENTE] Traceback completo:")
                raise ValueError(f"Error ejecutando acción: {str(e)}")

        # 5. Combinar resultados (si hay múltiples acciones)
        if not results:
            logger.error("[AGENTE] No se obtuvieron resultados de las acciones")
            raise ValueError("No se obtuvieron resultados de las acciones")
        
        logger.debug(f"[AGENTE] Total de resultados obtenidos: {len(results)}")
        combined_data = results[0] if len(results) == 1 else results
        logger.debug(f"[AGENTE] Datos combinados - Tipo: {type(combined_data)}")
        if isinstance(combined_data, list):
            logger.debug(f"[AGENTE] Datos combinados - Elementos: {len(combined_data)}")

        # 6. Aplicar post-procesamiento
        logger.debug("[AGENTE] Aplicando post-procesamiento...")
        post_process = plan.get("post_process", {})
        if post_process:
            logger.debug(f"[AGENTE] Post-procesamiento a aplicar: {json.dumps(post_process, indent=2, ensure_ascii=False)}")
        else:
            logger.debug("[AGENTE] No hay post-procesamiento configurado")
        
        processed_data = _apply_post_process(combined_data, post_process)
        logger.debug(f"[AGENTE] Datos después de post-procesamiento - Tipo: {type(processed_data)}")
        if isinstance(processed_data, (int, float)):
            logger.debug(f"[AGENTE] Resultado agregado: {processed_data}")
        elif isinstance(processed_data, list):
            logger.debug(f"[AGENTE] Elementos después de post-procesamiento: {len(processed_data)}")
        
        # Si después del post-procesamiento no hay datos, informar
        if processed_data is None or (isinstance(processed_data, list) and len(processed_data) == 0):
            logger.warning("[AGENTE] No hay datos después del post-procesamiento")
            return {
                "format": "text",
                "data": {"text": "No se encontraron datos que coincidan con tu consulta."},
                "metadata": {"title": "Sin resultados", "description": "La consulta no devolvió datos"},
            }

        # 7. Formatear resultado
        suggested_format = analysis.get("suggested_format", "table")
        formatted = await format_result(processed_data, query, suggested_format, post_process)

        logger.info("[AGENTE] Procesamiento completado exitosamente")
        logger.debug("=" * 80)
        return formatted

    except ValueError as e:
        # Errores de validación - retornar mensaje claro
        logger.warning(f"Error de validación en consulta: {e}")
        return {
            "format": "text",
            "data": {"text": f"Error: {str(e)}"},
            "metadata": {"title": "Error de validación", "description": "La consulta no pudo ser procesada"},
        }
    except Exception as e:
        logger.exception(f"Error procesando consulta: {e}")
        # Retornar error formateado con mensaje amigable
        error_msg = str(e)
        if "API key" in error_msg or "GOOGLE_API_KEY" in error_msg or "OPENAI_API_KEY" in error_msg:
            error_msg = "Error de configuración: No hay API key de IA configurada"
        elif "timeout" in error_msg.lower():
            error_msg = "La consulta tardó demasiado tiempo. Intenta con una consulta más específica."
        elif "network" in error_msg.lower() or "conexión" in error_msg.lower():
            error_msg = "Error de conexión. Verifica tu conexión a internet."
        
        return {
            "format": "text",
            "data": {"text": f"Error al procesar la consulta: {error_msg}"},
            "metadata": {"title": "Error", "description": "No se pudo procesar la consulta"},
        }
