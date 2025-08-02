from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import httpx
from datetime import datetime

SUPABASE_URL = "https://rzuyndmogkawqdstlnht.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJ6dXluZG1vZ2thd3Fkc3Rsbmh0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTM4OTA1ODMsImV4cCI6MjA2OTQ2NjU4M30.OaJpVhtgv564iQ8A3c7pPXhK3A4-v5D1geS2r1Kxymo"

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

class DashboardData(BaseModel):
    ventas_mes: float
    gastos_mes: float
    facturas_trimestre: int

@router.get("/", response_model=DashboardData)
async def get_dashboard():
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    async with httpx.AsyncClient() as client:
        # Ventas del mes
        hoy = datetime.now()
        mes = hoy.month
        anio = hoy.year
        ventas_url = f"{SUPABASE_URL}/rest/v1/ventas?select=TOTAL_PRICE_OF_ITEMS_AMT_VAT_INCL,TRANSACTION_COMPLETE_DATE"
        ventas_resp = await client.get(ventas_url, headers=headers)
        ventas = ventas_resp.json() if ventas_resp.status_code == 200 else []
        ventas_mes = sum(v['TOTAL_PRICE_OF_ITEMS_AMT_VAT_INCL'] for v in ventas if datetime.fromisoformat(v['TRANSACTION_COMPLETE_DATE']).month == mes and datetime.fromisoformat(v['TRANSACTION_COMPLETE_DATE']).year == anio)
        # Gastos del mes
        gastos_url = f"{SUPABASE_URL}/rest/v1/facturas?select=TOTAL_PRICE_OF_ITEMS_AMT_VAT_INCL,TRANSACTION_COMPLETE_DATE"
        gastos_resp = await client.get(gastos_url, headers=headers)
        gastos = gastos_resp.json() if gastos_resp.status_code == 200 else []
        gastos_mes = sum(f['TOTAL_PRICE_OF_ITEMS_AMT_VAT_INCL'] for f in gastos if datetime.fromisoformat(f['TRANSACTION_COMPLETE_DATE']).month == mes and datetime.fromisoformat(f['TRANSACTION_COMPLETE_DATE']).year == anio)
        # Facturas subidas en el trimestre
        trimestre = (mes - 1) // 3 + 1
        facturas_trimestre = sum(1 for f in gastos if ((datetime.fromisoformat(f['TRANSACTION_COMPLETE_DATE']).month - 1) // 3 + 1) == trimestre and datetime.fromisoformat(f['TRANSACTION_COMPLETE_DATE']).year == anio)
        return DashboardData(ventas_mes=ventas_mes, gastos_mes=gastos_mes, facturas_trimestre=facturas_trimestre)
