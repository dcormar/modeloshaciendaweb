from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import httpx
from datetime import datetime

SUPABASE_URL = "https://rzuyndmogkawqdstlnht.supabase.co"
SUPABASE_KEY = "sb_secret_dUm0eji6_z3fiu6Z7vn2aQ_fbHKu5zA"

router = APIRouter(prefix="/modelos", tags=["modelos"])

class EstadoModelos(BaseModel):
    ingresos_netos: float
    gastos_deducibles: float
    rendimiento_neto: float
    resultado_irpf: float
    ventas_nacionales_iva: float
    iva_repercutido: float
    entregas_intracomunitarias: float
    casilla_60: float
    adquisiciones_intracomunitarias: float
    servicios_intracomunitarios: float
    servicios_extracomunitarios: float
    importaciones_duas: float
    gastos_nacionales_iva: float

@router.get("/estado", response_model=EstadoModelos)
async def get_estado_modelos():
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    async with httpx.AsyncClient() as client:
        # Aquí deberías consultar y calcular cada campo según tus tablas y lógica
        # Por ahora, se devuelven valores dummy
        return EstadoModelos(
            ingresos_netos=10000,
            gastos_deducibles=2000,
            rendimiento_neto=8000,
            resultado_irpf=1200,
            ventas_nacionales_iva=9000,
            iva_repercutido=1890,
            entregas_intracomunitarias=0,
            casilla_60=0,
            adquisiciones_intracomunitarias=0,
            servicios_intracomunitarios=0,
            servicios_extracomunitarios=0,
            importaciones_duas=0,
            gastos_nacionales_iva=1500
        )
