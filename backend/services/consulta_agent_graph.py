# consulta_agent_graph.py
# Grafo de LangGraph para el agente iterativo de consulta

import logging
import json
import warnings
import traceback

# Suprimir warnings de 'title' y 'default' de langchain_google_genai
# Estos warnings son informativos y no afectan la funcionalidad
# Se aplican ANTES de importar langchain_google_genai para que surtan efecto
warnings.filterwarnings("ignore", message=".*Key 'title' is not supported in schema.*")
warnings.filterwarnings("ignore", message=".*Key 'default' is not supported in schema.*")
warnings.filterwarnings("ignore", message=".*Key 'anyOf' is not supported in schema.*")
warnings.filterwarnings("ignore", message=".*Unrecognized FinishReason enum value.*")
# Suprimir todos los warnings del módulo langchain_google_genai._function_utils
warnings.filterwarnings("ignore", module="langchain_google_genai._function_utils")

from typing import Literal, Dict, Any, List, Optional
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from services.consulta_state import ConsultaAgentState
from services.consulta_tools import ALL_TOOLS
from services.consulta_mcp_tools import MCP_TOOLS

logging.getLogger("langchain_google_genai._function_utils").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)

# Importar LLM
import os
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

# Importar después de configurar warnings
try:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # Suprimir todos los warnings durante la importación
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_openai import ChatOpenAI
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    logger.warning("LangChain no está disponible. Instala langchain-google-genai o langchain-openai")


def get_llm(use_openai: bool = False, primary_llm: Optional[str] = None):
    """
    Obtiene el LLM configurado (Gemini o OpenAI).
    
    Args:
        use_openai: Si es True, fuerza el uso de OpenAI (útil para fallback)
        primary_llm: LLM preferido del estado ("gemini" o "openai"). Si está definido, se usa ese.
    """
    if not LANGCHAIN_AVAILABLE:
        raise ValueError("LangChain no está disponible")
    
    # Si hay un primary_llm definido en el estado, usarlo
    if primary_llm:
        if primary_llm == "openai":
            if OPENAI_API_KEY:
                logger.info("[GRAPH] Usando OpenAI como LLM (desde estado)")
                return ChatOpenAI(
                    model="gpt-4o-mini",
                    temperature=0.1,
                    api_key=OPENAI_API_KEY
                )
            else:
                raise ValueError("OPENAI_API_KEY no está configurada")
        elif primary_llm == "gemini":
            if GOOGLE_API_KEY:
                logger.info("[GRAPH] Usando Gemini como LLM (desde estado)")
                return ChatGoogleGenerativeAI(
                    model="gemini-2.5-flash-lite",
                    temperature=0.1,
                    google_api_key=GOOGLE_API_KEY
                )
            else:
                raise ValueError("GOOGLE_API_KEY no está configurada")
    
    # Si se fuerza OpenAI o no hay Google API key, usar OpenAI
    if use_openai or not GOOGLE_API_KEY:
        if OPENAI_API_KEY:
            logger.info("[GRAPH] Usando OpenAI como LLM")
            return ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0.1,
                api_key=OPENAI_API_KEY
            )
        else:
            raise ValueError("OPENAI_API_KEY no está configurada")
    
    # Intentar usar Gemini primero
    try:
        logger.info("[GRAPH] Usando Gemini como LLM")
        return ChatGoogleGenerativeAI(
            model="gemini-2.5-flash-lite",
            temperature=0.1,
            google_api_key=GOOGLE_API_KEY
        )
    except Exception as e:
        logger.warning(f"[GRAPH] Error creando ChatGoogleGenerativeAI: {e}")
        # Fallback a OpenAI si está disponible
        if OPENAI_API_KEY:
            logger.info("[GRAPH] Fallback a OpenAI debido a error en Gemini")
            return ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0.1,
                api_key=OPENAI_API_KEY
            )
        raise ValueError(f"Error con Gemini y OpenAI no está configurado: {str(e)}")


def invoke_llm_with_fallback(llm, messages, tools=None, retry_with_openai=True, state=None):
    """
    Invoca el LLM con manejo automático de error 429 (rate limit) y fallback al LLM alternativo.
    Si falla el LLM principal, cambia al secundario en el estado para el resto de la ejecución.
    
    Args:
        llm: Instancia del LLM
        messages: Lista de mensajes
        tools: Herramientas opcionales para bind
        retry_with_openai: Si es True, intenta con el LLM alternativo en caso de error
        state: Estado del agente (opcional) para cambiar primary_llm si falla
    
    Returns:
        Respuesta del LLM
    """
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # Suprimir warnings durante la invocación
            if tools:
                llm_with_tools = llm.bind_tools(tools)
                response = llm_with_tools.invoke(messages)
            else:
                response = llm.invoke(messages)
            
            # Validar y limpiar tool_calls si existen
            if hasattr(response, 'tool_calls') and response.tool_calls:
                # Filtrar tool_calls inválidos (enteros, None, etc.)
                valid_tool_calls = []
                for tc in response.tool_calls:
                    if tc is None or isinstance(tc, (int, float, str)):
                        continue
                    valid_tool_calls.append(tc)
                # Reemplazar tool_calls con solo los válidos
                if len(valid_tool_calls) != len(response.tool_calls):
                    response.tool_calls = valid_tool_calls
            
            return response
    except AttributeError as e:
        # Error específico de langchain_google_genai cuando finish_reason es int en lugar de enum
        # Esto ocurre cuando Gemini no genera tool calls
        error_str = str(e)
        if "'int' object has no attribute 'name'" in error_str or "finish_reason" in error_str.lower():
            logger.warning(f"[GRAPH] Error de finish_reason en LLM actual (probablemente sin tool calls): {e}")
            
            # Detectar qué LLM está usando
            current_llm_type = "gemini" if "ChatGoogleGenerativeAI" in str(type(llm)) else "openai"
            alternate_llm_type = "openai" if current_llm_type == "gemini" else "gemini"
            
            logger.info(f"[GRAPH] Cambiando de {current_llm_type} a {alternate_llm_type} debido a error...")
            
            # Actualizar estado si está disponible
            if state is not None:
                state["primary_llm"] = alternate_llm_type
                logger.info(f"[GRAPH] Estado actualizado: primary_llm={alternate_llm_type} (para el resto de la ejecución)")
            
            # Obtener LLM alternativo
            alternate_llm = get_llm(use_openai=(alternate_llm_type == "openai"), primary_llm=alternate_llm_type)
            
            # Reintentar con LLM alternativo
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    if tools:
                        alternate_llm_with_tools = alternate_llm.bind_tools(tools)
                        response = alternate_llm_with_tools.invoke(messages)
                    else:
                        response = alternate_llm.invoke(messages)
                    
                    # Validar tool_calls también para el LLM alternativo
                    if hasattr(response, 'tool_calls') and response.tool_calls:
                        valid_tool_calls = []
                        for tc in response.tool_calls:
                            if tc is None or isinstance(tc, (int, float, str)):
                                continue
                            valid_tool_calls.append(tc)
                        if len(valid_tool_calls) != len(response.tool_calls):
                            response.tool_calls = valid_tool_calls
                    
                    return response
            except Exception as alternate_error:
                logger.error(f"[GRAPH] Error también con {alternate_llm_type}: {alternate_error}")
                # Crear respuesta vacía como último recurso
                from langchain_core.messages import AIMessage
                return AIMessage(content=f"Error con ambos LLMs ({current_llm_type}: finish_reason bug, {alternate_llm_type}: {str(alternate_error)})")
        else:
            # Otro AttributeError, re-lanzar
            raise
    except Exception as e:
        error_str = str(e).lower()
        # Detectar cualquier error (429, timeout, etc.) que requiera cambio de LLM
        if retry_with_openai:
            logger.warning(f"[GRAPH] Error en LLM actual: {e}")
            
            # Detectar qué LLM está usando
            current_llm_type = "gemini" if "ChatGoogleGenerativeAI" in str(type(llm)) else "openai"
            alternate_llm_type = "openai" if current_llm_type == "gemini" else "gemini"
            
            logger.info(f"[GRAPH] Cambiando de {current_llm_type} a {alternate_llm_type} debido a error...")
            
            # Actualizar estado si está disponible
            if state is not None:
                state["primary_llm"] = alternate_llm_type
                logger.info(f"[GRAPH] Estado actualizado: primary_llm={alternate_llm_type} (para el resto de la ejecución)")
            
            # Verificar que el LLM alternativo esté disponible
            if alternate_llm_type == "openai" and not OPENAI_API_KEY:
                logger.error("[GRAPH] OpenAI no está configurado para fallback")
                raise ValueError(f"Error en {current_llm_type} y OpenAI no está configurado: {str(e)}")
            if alternate_llm_type == "gemini" and not GOOGLE_API_KEY:
                logger.error("[GRAPH] Gemini no está configurado para fallback")
                raise ValueError(f"Error en {current_llm_type} y Gemini no está configurado: {str(e)}")
            
            # Obtener LLM alternativo
            alternate_llm = get_llm(use_openai=(alternate_llm_type == "openai"), primary_llm=alternate_llm_type)
            
            # Reintentar con LLM alternativo
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    if tools:
                        alternate_llm_with_tools = alternate_llm.bind_tools(tools)
                        response = alternate_llm_with_tools.invoke(messages)
                    else:
                        response = alternate_llm.invoke(messages)
                    
                    # Validar tool_calls también para el LLM alternativo
                    if hasattr(response, 'tool_calls') and response.tool_calls:
                        valid_tool_calls = []
                        for tc in response.tool_calls:
                            if tc is None or isinstance(tc, (int, float, str)):
                                continue
                            valid_tool_calls.append(tc)
                        if len(valid_tool_calls) != len(response.tool_calls):
                            response.tool_calls = valid_tool_calls
                    
                    return response
            except Exception as alternate_error:
                logger.error(f"[GRAPH] Error también con {alternate_llm_type}: {alternate_error}")
                raise ValueError(f"Error con ambos LLMs ({current_llm_type}: {str(e)}, {alternate_llm_type}: {str(alternate_error)})")
        else:
            # No retry, re-lanzar
            raise


def analyze_node(state: ConsultaAgentState) -> ConsultaAgentState:
    """
    Nodo que analiza la consulta con contexto de iteraciones previas.
    En la primera iteración, simplemente añade el mensaje del usuario.
    En iteraciones posteriores, añade contexto sobre lo que falta.
    """
    logger.info(f"[GRAPH] analyze_node - Iteración {state['iteration']}")
    
    query = state["query_original"]
    iteration = state["iteration"]
    previous_results = state.get("results", [])
    errors = state.get("errors", [])
    
    # Si es la primera iteración, solo añadir el mensaje del usuario
    if iteration == 0:
        if not state["messages"] or not isinstance(state["messages"][0], HumanMessage):
            state["messages"].append(HumanMessage(content=query))
        logger.info("[GRAPH] Primera iteración - mensaje del usuario añadido")
        return state
    
    # En iteraciones posteriores, añadir contexto
    context_parts = [f"Iteración {iteration + 1}"]
    if previous_results:
        context_parts.append(f"Resultados previos: {len(previous_results)} conjunto(s) de datos obtenidos")
    if errors:
        context_parts.append(f"Errores encontrados: {', '.join(errors)}")
    
    context = "\n".join(context_parts)
    context_message = f"Contexto: {context}\n\n¿Qué falta para completar la consulta '{query}'?"
    
    state["messages"].append(HumanMessage(content=context_message))
    logger.info(f"[GRAPH] Contexto añadido para iteración {iteration + 1}")
    
    return state


def plan_node(state: ConsultaAgentState) -> ConsultaAgentState:
    """
    Nodo que planifica qué herramientas usar usando function calling del LLM.
    """
    logger.info(f"[GRAPH] plan_node - Iteración {state['iteration']}")
    
    # Obtener contexto de la consulta y análisis previo
    query = state["query_original"]
    iteration = state["iteration"]
    previous_results = state.get("results", [])
    errors = state.get("errors", [])
    
    # Construir contexto básico
    context_parts = []
    
    if iteration > 0:
        context_parts.append(f"Iteración {iteration + 1}. Ya se ejecutaron acciones previas.")
        if previous_results:
            context_parts.append(f"Resultados previos: {len(previous_results)} conjunto(s) de datos obtenidos")
        if errors:
            context_parts.append(f"Errores encontrados: {', '.join(errors)}")
        context_parts.append("\nAnaliza qué falta o qué errores hay que resolver.")
    else:
        context_parts.append("Primera iteración. Analiza la consulta completa y planifica las acciones necesarias.")
    
    context = "\n".join(context_parts)
    
    from datetime import date
    today = date.today().isoformat()
    
    prompt = f"""Eres un agente que planifica acciones para responder consultas sobre datos financieros.

Consulta original: "{query}"
{context}

DEBES usar las herramientas disponibles para obtener los datos. NO respondas directamente, SIEMPRE usa las herramientas.

Herramientas disponibles:
- get_facturas(desde, hasta, proveedor=None, pais_origen=None, importe_min=None, importe_max=None, categoria=None, moneda=None, limit=None): 
  Obtiene facturas con múltiples filtros. Parámetros principales: desde/hasta (requeridos). 
  Filtros opcionales: proveedor (búsqueda parcial), pais_origen, importe_min/max, categoria, moneda, limit.
  Ejemplo: get_facturas(desde="2025-10-01", hasta="2026-01-01", proveedor="Meta", importe_min=100.0)
- get_ventas(desde, hasta): Obtiene ventas entre dos fechas (formato YYYY-MM-DD)
- get_dashboard(): Obtiene resumen de los últimos 6 meses
- get_historico(limit): Obtiene histórico reciente
- filter_data(data, campo, valor): Filtra datos por campo y valor
- aggregate_data(data, operation, field): Agrega datos (operation: "sum", "count", "avg")
- web_search(query): Busca información en internet
- verify_company_info(company_name): Verifica información de empresa
- search_exchange_rate(currency_from, currency_to, date): Busca tipo de cambio

IMPORTANTE:
- La fecha actual ES: {today}
- NO inventes fechas.
- Cuando la consulta diga "últimos X meses", calcula el rango usando ESTA fecha como referencia.
- Si ya tienes datos de facturas/ventas, usa filter_data o aggregate_data en lugar de volver a consultar.

INSTRUCCIONES:
1. Si la consulta menciona "últimos 3 meses", calcula SIEMPRE LAS FECHAS (no inventes, usa las fechas reales): desde = fecha actual - 90 días, hasta = fecha actual
2. Si menciona un proveedor (ej: "Meta"), país, importe, categoría o moneda, usa los filtros directamente en get_facturas en lugar de obtener todas las facturas y luego filtrar.
   Ejemplo: Si la consulta es "facturas de Meta", usa: get_facturas(desde=..., hasta=..., proveedor="Meta")
3. SIEMPRE usa las herramientas. NO respondas con texto directo.
4. Prefiere usar filtros en get_facturas sobre usar filter_data cuando sea posible (más eficiente).

Ejemplo para "{query}":
- Si la consulta menciona proveedor/categoría/país/importe: usa get_facturas con esos filtros directamente
  Ejemplo: get_facturas(desde="2025-10-23", hasta="2026-01-21", proveedor="Meta")
- Si NO se ha ejecutado get_facturas, calcula fechas y ejecuta con los filtros necesarios"""
    
    try:
        # Obtener LLM usando primary_llm del estado si está disponible
        primary_llm = state.get("primary_llm")
        llm = get_llm(primary_llm=primary_llm)
        all_tools = ALL_TOOLS + MCP_TOOLS
        
        # Invocar LLM con el historial de mensajes (con fallback automático si hay error)
        logger.info("Cargando historial de mensajes")
        messages = state["messages"].copy()
        if not messages or not isinstance(messages[-1], HumanMessage):
            messages.append(HumanMessage(content=prompt))
        else:
            # Añadir prompt al último mensaje o crear uno nuevo
            messages.append(HumanMessage(content=prompt))
        
        response = invoke_llm_with_fallback(llm, messages, tools=all_tools, state=state)
        
        # Añadir respuesta al estado
        state["messages"].append(response)
        
        # Verificar si hay tool calls (manejar diferentes formatos)
        try:
            logger.info("Solicitando tool calls")
            tool_calls = getattr(response, 'tool_calls', None)
            if tool_calls is None:
                logger.info("No hay tool calls")
                tool_calls = []
            elif not isinstance(tool_calls, list): 
                logger.info("Tool calls no es una lista")
                tool_calls = [tool_calls] if tool_calls else []
            
            # Filtrar elementos válidos (no enteros ni None)
            valid_tool_calls = []
            for tc in tool_calls:
                if tc is None:
                    continue
                if isinstance(tc, (int, float, str)):
                    logger.warning(f"[GRAPH] Tool call inválido (tipo {type(tc)}): {tc}")
                    continue
                valid_tool_calls.append(tc)
            
            if valid_tool_calls:
                logger.info(f"[GRAPH] LLM generó {len(valid_tool_calls)} tool call(s)")
            else:
                logger.warning("[GRAPH] LLM no generó tool calls válidos")
                # Si no hay tool calls pero hay contenido, puede ser una respuesta directa
                if hasattr(response, 'content') and response.content:
                    logger.info(f"[GRAPH] LLM respondió directamente sin herramientas: {response.content[:100]}")
                    # No terminar aquí, dejar que reevaluate decida
        except Exception as tool_calls_error:
            logger.exception(f"[GRAPH] Error verificando tool_calls: {tool_calls_error}")
            logger.warning("[GRAPH] Continuando sin tool calls debido a error")
        
        return state
        
    except Exception as e:
        logger.exception(f"[GRAPH] Error en plan_node: {e}")
        error_traceback = traceback.format_exc()
        state["errors"].append(f"Error en planificación: {str(e)}\nTraceback: {error_traceback}")
        state["should_finish"] = True
        return state


def reevaluate_node(state: ConsultaAgentState) -> ConsultaAgentState:
    """
    Nodo que reevalúa los resultados y decide si continuar o terminar.
    """
    logger.info(f"[GRAPH] reevaluate_node - Iteración {state['iteration']}")
    
    query = state["query_original"]
    results = state.get("results", [])
    errors = state.get("errors", [])
    iteration = state["iteration"]
    
    # Obtener resultados de herramientas (últimos ToolMessage) y tool calls ejecutados
    tool_results = []
    executed_tool_calls = []
    
    for msg in reversed(state["messages"]):
        if isinstance(msg, ToolMessage):
            try:
                # Intentar parsear como JSON
                if isinstance(msg.content, str):
                    try:
                        parsed = json.loads(msg.content)
                        tool_results.append(parsed)
                    except:
                        tool_results.append(msg.content)
                else:
                    tool_results.append(msg.content)
            except:
                tool_results.append(str(msg.content))
        elif isinstance(msg, AIMessage):
            # Obtener tool calls ejecutados
            tool_calls = getattr(msg, 'tool_calls', None) or []
            if tool_calls:
                for tc in tool_calls:
                    try:
                        if isinstance(tc, dict):
                            executed_tool_calls.append({
                                "name": tc.get('name', 'unknown'),
                                "args": tc.get('args', {})
                            })
                        else:
                            executed_tool_calls.append({
                                "name": getattr(tc, 'name', 'unknown'),
                                "args": getattr(tc, 'args', {})
                            })
                    except:
                        pass
            # Verificar si tiene tool_calls (manejar diferentes formatos)
            if not tool_calls:
                break
    
    # Construir resumen detallado de resultados
    results_summary_parts = []
    
    # 0. Fecha actual
    from datetime import date
    today = date.today().isoformat()
    results_summary_parts.append(f"Fecha actual: {today}")
    
    # 1. Información básica
    total_results = len(tool_results)
    results_summary_parts.append(f"Total de conjuntos de resultados: {total_results}")
    
    # 2. Analizar cada resultado para extraer información detallada
    all_facturas = []
    all_ventas = []
    date_ranges = []
    total_amounts = []
    proveedores = set()
    categorias = set()
    
    for result in tool_results:
        if isinstance(result, list):
            # Si es una lista, analizar cada elemento
            for item in result:
                if isinstance(item, dict):
                    # Detectar tipo de dato
                    if "proveedor" in item or "importe_total_euro" in item:
                        # Es una factura
                        all_facturas.append(item)
                        if "proveedor" in item:
                            proveedores.add(str(item.get("proveedor", "")))
                        if "categoria" in item:
                            categorias.add(str(item.get("categoria", "")))
                        if "importe_total_euro" in item:
                            try:
                                total_amounts.append(float(item.get("importe_total_euro", 0)))
                            except:
                                pass
                        # Extraer fechas
                        if "fecha_dt" in item and item.get("fecha_dt"):
                            date_ranges.append(item.get("fecha_dt"))
                        elif "fecha" in item and item.get("fecha"):
                            date_ranges.append(item.get("fecha"))
                    elif "MARKETPLACE" in item or "TOTAL_PRICE_OF_ITEMS_AMT_VAT_INCL" in item:
                        # Es una venta
                        all_ventas.append(item)
                        if "TOTAL_PRICE_OF_ITEMS_AMT_VAT_INCL" in item:
                            try:
                                total_amounts.append(float(item.get("TOTAL_PRICE_OF_ITEMS_AMT_VAT_INCL", 0)))
                            except:
                                pass
                        # Extraer fechas
                        if "TRANSACTION_COMPLETE_DATE_DT" in item and item.get("TRANSACTION_COMPLETE_DATE_DT"):
                            date_ranges.append(item.get("TRANSACTION_COMPLETE_DATE_DT"))
                        elif "TRANSACTION_COMPLETE_DATE" in item and item.get("TRANSACTION_COMPLETE_DATE"):
                            date_ranges.append(item.get("TRANSACTION_COMPLETE_DATE"))
        elif isinstance(result, dict):
            # Si es un diccionario, puede ser un resultado único o un objeto con estructura
            if "ultimos_seis_meses" in result:
                # Es un resultado de dashboard
                results_summary_parts.append(f"Dashboard: {len(result.get('ultimos_seis_meses', []))} meses de datos")
            elif "items" in result:
                # Es un resultado con items
                items = result.get("items", [])
                results_summary_parts.append(f"Items obtenidos: {len(items)}")
            else:
                # Otro tipo de diccionario
                results_summary_parts.append(f"Resultado único con claves: {', '.join(list(result.keys())[:5])}")
    
    # 3. Información sobre facturas
    if all_facturas:
        results_summary_parts.append(f"Facturas obtenidas: {len(all_facturas)}")
        if total_amounts:
            total_sum = sum(total_amounts)
            results_summary_parts.append(f"Total facturado: {total_sum:.2f} EUR")
        if proveedores:
            results_summary_parts.append(f"Proveedores encontrados: {', '.join(list(proveedores)[:5])}")
        if categorias:
            results_summary_parts.append(f"Categorías: {', '.join(list(categorias)[:5])}")
    
    # 4. Información sobre ventas
    if all_ventas:
        results_summary_parts.append(f"Ventas obtenidas: {len(all_ventas)}")
        if total_amounts:
            total_sum = sum(total_amounts)
            results_summary_parts.append(f"Total vendido: {total_sum:.2f} EUR")
    
    # 5. Información sobre herramientas ejecutadas y rangos consultados (ANTES del rango de datos)
    if executed_tool_calls:
        tool_names = [tc.get("name", "unknown") for tc in executed_tool_calls]
        results_summary_parts.append(f"Herramientas ejecutadas: {', '.join(set(tool_names))}")
        
        # Extraer parámetros de fechas de los tool calls y otros filtros
        rangos_consultados = []
        for tc in executed_tool_calls:
            args = tc.get("args", {})
            tool_name = tc.get("name", "unknown")
            if "desde" in args and "hasta" in args:
                rango_info = f"RANGO CONSULTADO EN BD ({tool_name}): desde {args.get('desde')} hasta {args.get('hasta')}"
                if "proveedor" in args and args.get("proveedor"):
                    rango_info += f", proveedor: {args.get('proveedor')}"
                if "categoria" in args and args.get("categoria"):
                    rango_info += f", categoría: {args.get('categoria')}"
                if "pais_origen" in args and args.get("pais_origen"):
                    rango_info += f", país: {args.get('pais_origen')}"
                rangos_consultados.append(rango_info)
        
        if rangos_consultados:
            results_summary_parts.extend(rangos_consultados)
    
    # Construir el resumen final
    if results_summary_parts:
        results_summary = "\n".join(f"- {part}" for part in results_summary_parts)
    else:
        results_summary = "No se obtuvieron resultados detallados"
    
    # Log del summary para debugging
    logger.info(f"[GRAPH] reevaluate_node - Summary que se pasa al LLM:\n{results_summary}")
    
    # Extraer información de la consulta original para comparar rangos
    query_lower = query.lower()
    query_date_info = ""
    if "últimos" in query_lower or "últimas" in query_lower:
        # Intentar extraer número de meses/días
        import re
        meses_match = re.search(r'(\d+)\s*mes', query_lower)
        dias_match = re.search(r'(\d+)\s*día', query_lower)
        if meses_match:
            num_meses = int(meses_match.group(1))
            query_date_info = f"La consulta solicita los últimos {num_meses} meses."
        elif dias_match:
            num_dias = int(dias_match.group(1))
            query_date_info = f"La consulta solicita los últimos {num_dias} días."
    
    prompt = f"""Eres un agente que reevalúa resultados de acciones ejecutadas.

Consulta original: "{query}"
{query_date_info}
Iteración actual: {iteration + 1} (máximo 3)

RESUMEN DETALLADO DE RESULTADOS:
{results_summary}

Errores encontrados: {errors if errors else "ninguno"}
Acciones ejecutadas en total: {len(state.get('actions_executed', []))}

Analiza si:
1. Se cumplió el objetivo de la consulta original
2. Hay errores que necesitan resolverse
3. Faltan datos que requieren más acciones
4. Los resultados son suficientes o necesitan refinamiento (filtros, agregaciones, etc.)

Responde SOLO con un JSON válido:
{{
  "should_finish": true|false,
  "reason": "razón detallada de la decisión basada en el resumen de resultados",
  "next_actions_needed": ["acción1", "acción2"] o null,
  "errors_to_fix": ["error1"] o null,
  "result_quality": "completo|parcial|insuficiente",
  "data_coverage": "descripción de qué datos se obtuvieron y qué falta"
}}"""
    
    try:
        # Obtener LLM usando primary_llm del estado si está disponible
        primary_llm = state.get("primary_llm")
        llm = get_llm(primary_llm=primary_llm)
        messages = [HumanMessage(content=prompt)]
        response = invoke_llm_with_fallback(llm, messages, tools=None, state=state)
        eval_text = response.content
        
        # Parsear JSON
        evaluation = json.loads(eval_text.strip().replace("```json", "").replace("```", "").strip())
        
        state["should_finish"] = evaluation.get("should_finish", False)
        state["iteration"] += 1
        
        # Añadir evaluación al estado
        state["messages"].append(AIMessage(content=json.dumps(evaluation, ensure_ascii=False)))
        
        logger.info(f"[GRAPH] Reevaluación: should_finish={state['should_finish']}, reason={evaluation.get('reason')}")
        
        return state
        
    except Exception as e:
        logger.exception(f"[GRAPH] Error en reevaluate_node: {e}")
        # En caso de error, terminar para evitar loops infinitos
        state["should_finish"] = True
        state["errors"].append(f"Error en reevaluación: {str(e)}")
        return state


def format_node(state: ConsultaAgentState) -> ConsultaAgentState:
    """
    Nodo que formatea el resultado final usando el LLM.
    """
    logger.info("[GRAPH] format_node - Formateando resultado final")
    
    query = state["query_original"]
    results = state.get("results", [])
    
    # Obtener todos los resultados de herramientas
    all_results = []
    for msg in state["messages"]:
        if isinstance(msg, ToolMessage):
            try:
                # Intentar parsear como JSON
                if isinstance(msg.content, str):
                    try:
                        parsed = json.loads(msg.content)
                        all_results.append(parsed)
                    except:
                        all_results.append(msg.content)
                else:
                    all_results.append(msg.content)
            except:
                all_results.append(str(msg.content))
    
    # Si no hay resultados de herramientas, usar results del estado
    if not all_results and results:
        all_results = results
    
    # Si no hay resultados, retornar mensaje de error
    if not all_results:
        state["final_result"] = {
            "format": "text",
            "data": {"text": "No se obtuvieron resultados de la consulta."},
            "metadata": {"title": "Sin resultados", "description": "La consulta no devolvió datos"}
        }
        return state
    
    # Determinar formato sugerido
    suggested_format = "table"
    if len(all_results) == 1:
        first = all_results[0]
        if isinstance(first, (int, float, str)):
            suggested_format = "text"
        elif isinstance(first, dict) and len(first) == 1 and "text" in first:
            suggested_format = "text"
        elif isinstance(first, list) and len(first) > 0 and isinstance(first[0], dict):
            # Verificar si parece datos de gráfica
            if any(k in str(first[0]).lower() for k in ["chart", "series", "labels"]):
                suggested_format = "chart"
    
    # Preparar datos para el prompt (limitar tamaño)
    results_str = json.dumps(all_results, indent=2, ensure_ascii=False, default=str)
    if len(results_str) > 3000:
        results_str = results_str[:3000] + "... (truncado)"
    
    prompt = f"""Formatea los resultados de la consulta.

Consulta original: "{query}"
Resultados obtenidos: {results_str}
Formato sugerido: {suggested_format}

Formatea los datos según el formato sugerido.

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
    "chartLabels": ["label1", "label2"] (solo si format=chart),
    "chartSeries": [{{"name": "Serie 1", "data": [1, 2, 3], "color": "#2563eb"}}] (solo si format=chart)
  }}
}}"""
    
    try:
        # Obtener LLM usando primary_llm del estado si está disponible
        primary_llm = state.get("primary_llm")
        llm = get_llm(primary_llm=primary_llm)
        messages = state["messages"].copy()
        messages.append(HumanMessage(content=prompt))
        response = invoke_llm_with_fallback(llm, messages, tools=None, state=state)
        format_text = response.content
        
        # Parsear JSON
        formatted = json.loads(format_text.strip().replace("```json", "").replace("```", "").strip())
        
        state["final_result"] = formatted
        logger.info(f"[GRAPH] Resultado formateado: {formatted.get('format')}")
        
        return state
        
    except Exception as e:
        logger.exception(f"[GRAPH] Error en format_node: {e}")
        # Fallback: retornar resultado básico
        state["final_result"] = {
            "format": "text",
            "data": {"text": f"Error formateando resultado: {str(e)}. Datos obtenidos: {str(all_results)[:500]}"},
            "metadata": {"title": "Error", "description": "No se pudo formatear el resultado"}
        }
        return state


def should_continue(state: ConsultaAgentState) -> Literal["continue", "finish"]:
    """
    Función de decisión para conditional edge.
    Decide si continuar iterando o terminar.
    """
    if state["should_finish"]:
        logger.info("[GRAPH] Decisión: finish (should_finish=True)")
        return "finish"
    
    if state["iteration"] >= 3:
        logger.info("[GRAPH] Decisión: finish (máximo de iteraciones alcanzado)")
        return "finish"
    
    logger.info("[GRAPH] Decisión: continue")
    return "continue"


def create_consulta_agent_graph():
    """
    Crea y compila el grafo de LangGraph para el agente de consulta.
    """
    if not LANGCHAIN_AVAILABLE:
        raise ValueError("LangChain no está disponible. Instala las dependencias necesarias.")
    
    # Combinar todas las herramientas
    all_tools = ALL_TOOLS + MCP_TOOLS
    
    # Crear ToolNode
    tool_node = ToolNode(all_tools)
    
    # Crear grafo
    graph = StateGraph(ConsultaAgentState)
    
    # Añadir nodos
    graph.add_node("analyze", analyze_node)
    graph.add_node("plan", plan_node)
    graph.add_node("tools", tool_node)
    graph.add_node("reevaluate", reevaluate_node)
    graph.add_node("format", format_node)
    
    # Añadir edges
    graph.add_edge(START, "analyze")
    graph.add_edge("analyze", "plan")
    
    # Conditional edge después de plan: si hay tool_calls, ir a tools; si no, a reevaluate
    def route_after_plan(state: ConsultaAgentState) -> Literal["tools", "reevaluate"]:
        last_message = state["messages"][-1] if state["messages"] else None
        if isinstance(last_message, AIMessage):
            # Verificar si tiene tool_calls (manejar diferentes formatos)
            tool_calls = getattr(last_message, 'tool_calls', None) or []
            if tool_calls and len(tool_calls) > 0:
                logger.debug(f"[GRAPH] Routing to tools: {len(tool_calls)} tool call(s)")
                return "tools"
            # Si no tiene tool_calls pero tiene contenido, puede ser respuesta directa
            if last_message.content and not tool_calls:
                logger.debug("[GRAPH] Routing to reevaluate: respuesta directa sin herramientas")
                return "reevaluate"
        logger.debug("[GRAPH] Routing to reevaluate: no hay tool calls")
        return "reevaluate"
    
    graph.add_conditional_edges(
        "plan",
        route_after_plan,
        {
            "tools": "tools",
            "reevaluate": "reevaluate"
        }
    )
    
    # Después de tools, ir directamente a reevaluate
    graph.add_edge("tools", "reevaluate")
    
    # Conditional edge: ¿continuar o terminar?
    graph.add_conditional_edges(
        "reevaluate",
        should_continue,
        {
            "continue": "analyze",  # Loop back
            "finish": "format"
        }
    )
    
    graph.add_edge("format", END)
    
    # Compilar grafo
    compiled = graph.compile()
    
    logger.info("[GRAPH] Grafo de agente creado y compilado")
    logger.info(f"[GRAPH] Herramientas disponibles: {len(all_tools)}")
    return compiled


async def process_query_with_graph(query: str, user_id: str) -> Dict[str, Any]:
    """
    Procesa una consulta usando el grafo de LangGraph.
    
    Args:
        query: Consulta en lenguaje natural
        user_id: ID del usuario
    
    Returns:
        Resultado formateado
    """
    logger.info("=" * 80)
    logger.info(f"[GRAPH] Iniciando procesamiento con grafo")
    logger.info(f"[GRAPH] Query: {query}")
    logger.info(f"[GRAPH] User ID: {user_id}")
    logger.debug("=" * 80)
    
    try:
        # Crear grafo
        graph = create_consulta_agent_graph()
        
        # Estado inicial
        initial_state: ConsultaAgentState = {
            "query_original": query,
            "user_id": user_id,
            "messages": [],  # Se añadirá en analyze_node
            "results": [],
            "errors": [],
            "iteration": 0,
            "should_finish": False,
            "final_result": None,
            "schema_discovered": False,
            "available_tables": [],
            "actions_executed": [],
            "primary_llm": None  # Se establecerá automáticamente al primer uso
        }
        
        # Ejecutar grafo
        logger.info("[GRAPH] Ejecutando grafo...")
        final_state = await graph.ainvoke(initial_state)
        
        # Extraer resultado final
        result = final_state.get("final_result")
        if not result:
            # Fallback si no hay resultado formateado
            result = {
                "format": "text",
                "data": {"text": "No se pudo generar resultado. Errores: " + ", ".join(final_state.get("errors", []))},
                "metadata": {"title": "Error", "description": "No se generó resultado"}
            }
        
        logger.info("[GRAPH] Procesamiento completado")
        logger.debug("=" * 80)
        
        return result
        
    except Exception as e:
        logger.exception(f"[GRAPH] Error procesando consulta: {e}")
        return {
            "format": "text",
            "data": {"text": f"Error procesando consulta: {str(e)}"},
            "metadata": {"title": "Error", "description": "Error en el procesamiento"}
        }
