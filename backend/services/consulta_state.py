# consulta_state.py
# Definición del estado tipado para el agente de LangGraph

from typing_extensions import TypedDict, Annotated
from typing import Optional, List, Dict, Any
from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages


class ConsultaAgentState(TypedDict):
    """
    Estado del agente de consulta que persiste entre iteraciones.
    
    Campos:
    - query_original: Consulta original del usuario
    - user_id: ID del usuario autenticado
    - messages: Historial de mensajes (para el LLM)
    - results: Resultados acumulados de las acciones ejecutadas
    - errors: Lista de errores encontrados
    - iteration: Número de iteración actual (0-indexed)
    - should_finish: Flag que indica si el agente debe terminar
    - final_result: Resultado final formateado (cuando should_finish=True)
    - schema_discovered: Flag que indica si ya se descubrió el esquema de BD
    - available_tables: Lista de tablas disponibles (si se descubrió esquema)
    - actions_executed: Historial de acciones ejecutadas (para evitar loops)
    - primary_llm: LLM principal actual ("gemini" o "openai"), cambia si falla
    """
    query_original: str
    user_id: str
    messages: Annotated[List[BaseMessage], add_messages]
    results: List[Any]
    errors: List[str]
    iteration: int
    should_finish: bool
    final_result: Optional[Dict[str, Any]]
    schema_discovered: bool
    available_tables: List[str]
    actions_executed: List[Dict[str, Any]]
    primary_llm: Optional[str]
