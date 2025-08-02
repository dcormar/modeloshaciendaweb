
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from auth import router as auth_router
from n8n import router as n8n_router
from facturas_api import router as facturas_router
from ventas_api import router as ventas_router
from dashboard_api import router as dashboard_router
from modelos_api import router as modelos_router




# Configuración global de logging
import os
log_path = os.path.join(os.path.dirname(__file__), "log/modeloshaciendaweb.log")
log_format = '%(asctime)s %(levelname)s %(name)s %(message)s'
logging.basicConfig(
    level=logging.INFO,
    format=log_format,
    handlers=[
        logging.FileHandler(log_path, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
for logger_name in ("httpx", "uvicorn", "uvicorn.error", "uvicorn.access"):
    logging.getLogger(logger_name).setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(n8n_router)
app.include_router(facturas_router)
app.include_router(ventas_router)
app.include_router(dashboard_router)
app.include_router(modelos_router)
logger.info("Routers montados y aplicación FastAPI iniciada")

@app.get("/")
def read_root():
    return {"msg": "Backend FastAPI funcionando"}
