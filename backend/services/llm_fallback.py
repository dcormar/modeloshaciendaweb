# llm_fallback.py
# Wrapper para manejo de fallback entre LLMs (Gemini <-> OpenAI)

import logging
import warnings
from typing import Any, List, Optional
from google.api_core import exceptions as google_exceptions

logger = logging.getLogger(__name__)

# Importar LLMs
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_openai import ChatOpenAI
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    logger.warning("LangChain no disponible para fallback")


def _is_rate_limit_error(error: Exception) -> bool:
    """
    Detecta si el error es un rate limit (429) o similar.
    
    Args:
        error: Excepción a verificar
    
    Returns:
        True si es un error de rate limit
    """
    error_str = str(error).lower()
    
    # Detectar errores de rate limit de diferentes formas
    if "429" in error_str:
        return True
    if "resource exhausted" in error_str:
        return True
    if "quota" in error_str:
        return True
    if "rate limit" in error_str:
        return True
    if isinstance(error, google_exceptions.ResourceExhausted):
        return True
    
    return False


def _is_retryable_error(error: Exception) -> bool:
    """
    Detecta si el error es recuperable (rate limit, timeout, etc.).
    
    Args:
        error: Excepción a verificar
    
    Returns:
        True si el error es recuperable con fallback
    """
    # Rate limits
    if _is_rate_limit_error(error):
        return True
    
    # Timeouts
    error_str = str(error).lower()
    if "timeout" in error_str:
        return True
    
    # Errores de servicio temporalmente no disponible
    if "503" in error_str or "502" in error_str or "500" in error_str:
        return True
    
    return False


def get_llm_with_fallback(
    google_api_key: Optional[str] = None,
    openai_api_key: Optional[str] = None,
    prefer_google: bool = True,
    model_google: str = "gemini-2.5-flash-lite",
    model_openai: str = "gpt-4o-mini",
    temperature: float = 0.3,
    timeout: float = 10.0
):
    """
    Obtiene un LLM con capacidad de fallback.
    
    Args:
        google_api_key: API key de Google (Gemini)
        openai_api_key: API key de OpenAI
        prefer_google: Si True, intenta usar Gemini primero
        model_google: Modelo de Google a usar
        model_openai: Modelo de OpenAI a usar
        temperature: Temperatura para ambos modelos
        timeout: Timeout en segundos para las llamadas (default: 10.0)
    
    Returns:
        Tupla (llm, llm_type) donde llm_type es "gemini" o "openai"
    """
    if not LANGCHAIN_AVAILABLE:
        raise ValueError("LangChain no disponible")
    
    # Determinar qué LLM usar primero
    if prefer_google and google_api_key:
        try:
            llm = ChatGoogleGenerativeAI(
                model=model_google,
                temperature=temperature,
                google_api_key=google_api_key,
                timeout=timeout,
                max_retries=0  # No hacer retry, pasar directamente al fallback
            )
            logger.info(f"[LLM FALLBACK] Usando modelo: {model_google} (Google) - timeout: {timeout}s")
            return llm, "gemini"
        except Exception as e:
            logger.warning(f"[LLM FALLBACK] Error creando Gemini, usando OpenAI: {e}")
            if not openai_api_key:
                raise ValueError(f"Error con Gemini y OpenAI no está configurado: {str(e)}")
    
    if openai_api_key:
        llm = ChatOpenAI(
            model=model_openai,
            temperature=temperature,
            api_key=openai_api_key,
            timeout=timeout,
            max_retries=0  # No hacer retry, pasar directamente al fallback
        )
        logger.info(f"[LLM FALLBACK] Usando modelo: {model_openai} (OpenAI) - timeout: {timeout}s")
        return llm, "openai"
    
    raise ValueError("No hay API key configurada (GOOGLE_API_KEY o OPENAI_API_KEY)")


def invoke_llm_with_fallback(
    llm: Any,
    messages: List[Any],
    tools: Optional[List[Any]] = None,
    google_api_key: Optional[str] = None,
    openai_api_key: Optional[str] = None,
    model_google: str = "gemini-2.5-flash-lite",
    model_openai: str = "gpt-4o-mini",
    temperature: float = 0.3,
    timeout: float = 10.0
) -> Any:
    """
    Invoca un LLM con manejo automático de fallback.
    
    Si el LLM principal falla con un error recuperable (rate limit, timeout, etc.),
    automáticamente intenta con el LLM alternativo SIN hacer retry del mismo LLM.
    
    Args:
        llm: Instancia del LLM actual
        messages: Lista de mensajes para el LLM
        tools: Herramientas opcionales para bind
        google_api_key: API key de Google (para fallback)
        openai_api_key: API key de OpenAI (para fallback)
        model_google: Modelo de Google a usar en fallback
        model_openai: Modelo de OpenAI a usar en fallback
        temperature: Temperatura para el LLM de fallback
        timeout: Timeout en segundos para las llamadas (default: 10.0)
    
    Returns:
        Respuesta del LLM
    
    Raises:
        ValueError: Si ambos LLMs fallan o no hay fallback configurado
    """
    # Detectar qué tipo de LLM es
    llm_type = "gemini" if "ChatGoogleGenerativeAI" in str(type(llm)) else "openai"
    
    # Intentar una sola vez con el LLM principal (sin retry)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            
            if tools:
                llm_with_tools = llm.bind_tools(tools)
                response = llm_with_tools.invoke(messages)
            else:
                response = llm.invoke(messages)
            
            # Validar y limpiar tool_calls si existen
            if hasattr(response, 'tool_calls') and response.tool_calls:
                valid_tool_calls = []
                for tc in response.tool_calls:
                    if tc is None or isinstance(tc, (int, float, str)):
                        continue
                    valid_tool_calls.append(tc)
                if len(valid_tool_calls) != len(response.tool_calls):
                    response.tool_calls = valid_tool_calls
            
            return response
            
    except Exception as e:
        # Cualquier error (recuperable o no) pasa directamente al fallback
        # NO hacemos retry del mismo LLM
        logger.warning(f"[LLM FALLBACK] Error en {llm_type}: {e}")
        
        # Determinar LLM alternativo
        alternate_llm_type = "openai" if llm_type == "gemini" else "gemini"
        logger.info(f"[LLM FALLBACK] Cambiando directamente de {llm_type} a {alternate_llm_type} (sin retry)...")
        
        # Verificar que el LLM alternativo esté disponible
        if alternate_llm_type == "openai" and not openai_api_key:
            logger.error("[LLM FALLBACK] OpenAI no está configurado para fallback")
            raise ValueError(f"Error en {llm_type} y OpenAI no está configurado: {str(e)}")
        if alternate_llm_type == "gemini" and not google_api_key:
            logger.error("[LLM FALLBACK] Gemini no está configurado para fallback")
            raise ValueError(f"Error en {llm_type} y Gemini no está configurado: {str(e)}")
        
        # Obtener LLM alternativo
        alternate_llm, _ = get_llm_with_fallback(
            google_api_key=google_api_key,
            openai_api_key=openai_api_key,
            prefer_google=(alternate_llm_type == "gemini"),
            model_google=model_google,
            model_openai=model_openai,
            temperature=temperature,
            timeout=timeout
        )
        
        # Intentar una sola vez con el LLM alternativo (sin retry)
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
                
                logger.info(f"[LLM FALLBACK] Fallback exitoso a {alternate_llm_type}")
                return response
                
        except Exception as alternate_error:
            logger.error(f"[LLM FALLBACK] Error también con {alternate_llm_type}: {alternate_error}")
            raise ValueError(
                f"Error con ambos LLMs ({llm_type}: {str(e)}, {alternate_llm_type}: {str(alternate_error)})"
            )
