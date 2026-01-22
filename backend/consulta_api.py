# consulta_api.py
# API endpoint para consultas con IA

import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Any, Dict, List, Union

from auth import get_current_user, UserInDB
from services.consulta_agent_graph import process_query_with_graph

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/consulta", tags=["consulta"])


class ConsultaRequest(BaseModel):
    query: str


class ConsultaResponse(BaseModel):
    format: str  # 'table' | 'text' | 'chart'
    data: Union[Dict[str, Any], List[Dict[str, Any]], str, Any]  # Puede ser tabla, texto o datos de gráfica
    metadata: Optional[Dict[str, Any]] = None


@router.post("/query", response_model=ConsultaResponse)
async def query_consulta(
    request: ConsultaRequest,
    current_user: UserInDB = Depends(get_current_user),
):
    """
    Procesa una consulta en lenguaje natural y retorna resultados formateados.
    
    El agente IA analiza la consulta, planifica acciones, ejecuta las consultas
    necesarias y formatea los resultados en tabla, texto o gráfica.
    """
    logger.info("=" * 80)
    logger.info(f"[CONSULTA API] Inicio de consulta - Usuario: {current_user.username}")
    logger.info(f"[CONSULTA API] Query recibida: {request.query}")
    logger.debug("=" * 80)
    
    if not request.query or not request.query.strip():
        logger.warning("[CONSULTA API] Consulta vacía rechazada")
        raise HTTPException(status_code=400, detail="La consulta no puede estar vacía")

    try:
        logger.debug(f"[CONSULTA API] Llamando a process_query_with_graph con user_id={current_user.username}")
        
        # Procesar consulta con el agente iterativo (LangGraph)
        result = await process_query_with_graph(request.query, current_user.username)
        
        logger.info(f"[CONSULTA API] Resultado obtenido - Formato: {result.get('format')}")
        logger.debug(f"[CONSULTA API] Metadata: {result.get('metadata')}")
        logger.debug(f"[CONSULTA API] Tipo de datos: {type(result.get('data'))}")
        if isinstance(result.get('data'), list):
            logger.debug(f"[CONSULTA API] Número de elementos en datos: {len(result.get('data'))}")
        logger.info("=" * 80)
        
        return ConsultaResponse(
            format=result.get("format", "text"),
            data=result.get("data"),
            metadata=result.get("metadata"),
        )
    except ValueError as e:
        logger.error(f"[CONSULTA API] Error de validación: {e}")
        logger.info("=" * 80)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"[CONSULTA API] Error procesando consulta: {e}")
        logger.info("=" * 80)
        raise HTTPException(
            status_code=500,
            detail=f"Error al procesar la consulta: {str(e)}"
        )
