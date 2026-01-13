# exchange_service.py
# Servicio para obtener tipos de cambio de la API de Frankfurter

import logging
import httpx
from typing import Optional

logger = logging.getLogger(__name__)

# API de Frankfurter - tipos de cambio oficiales del BCE
FRANKFURTER_API_URL = "https://api.frankfurter.app"


async def get_exchange_rate(date: str, currency: str) -> Optional[float]:
    """
    Obtiene el tipo de cambio de una moneda a EUR para una fecha específica.
    
    Usa la API de Frankfurter que proporciona tipos de cambio oficiales
    del Banco Central Europeo (BCE).
    
    Args:
        date: Fecha en formato YYYY-MM-DD (ISO)
        currency: Código de moneda origen (USD, GBP, etc.)
    
    Returns:
        Tipo de cambio (cuántos EUR por 1 unidad de moneda origen).
        Por ejemplo: Si 1 USD = 0.92 EUR según la API (rates.EUR = 0.92),
        devolvemos 1/0.92 = 1.087 (el multiplicador para convertir a EUR).
        
        None si no se puede obtener el tipo de cambio.
    
    Example:
        >>> rate = await get_exchange_rate("2024-01-15", "USD")
        >>> print(rate)  # Ej: 1.0870
    """
    # Si la moneda es EUR, el tipo de cambio es 1
    if not currency or currency.upper() == "EUR":
        return 1.0
    
    currency = currency.upper().strip()
    
    # Construir URL de la API
    # GET https://api.frankfurter.app/{fecha}?from={moneda}&to=EUR
    url = f"{FRANKFURTER_API_URL}/{date}?from={currency}&to=EUR"
    
    logger.info(f"Consultando tipo de cambio: {url}")
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url)
            
            if response.status_code != 200:
                logger.warning(
                    f"Frankfurter API respondió con status {response.status_code}: {response.text}"
                )
                return None
            
            data = response.json()
            
            # La API devuelve algo como:
            # {
            #   "amount": 1,
            #   "base": "USD",
            #   "date": "2024-01-15",
            #   "rates": {"EUR": 0.92}
            # }
            
            eur_rate = data.get("rates", {}).get("EUR")
            
            if eur_rate is None:
                logger.warning(f"No se encontró rate EUR en respuesta: {data}")
                return None
            
            if eur_rate == 0:
                logger.warning(f"Rate EUR es 0, no se puede calcular tipo de cambio")
                return None
            
            # El tipo de cambio es 1 / rates.EUR
            # Esto nos da cuánto vale 1 unidad de la moneda origen en EUR
            # Redondeamos a 4 decimales
            exchange_rate = round(1 / eur_rate, 4)
            
            logger.info(f"Tipo de cambio {currency}->EUR para {date}: {exchange_rate}")
            return exchange_rate
            
    except httpx.TimeoutException:
        logger.error(f"Timeout consultando Frankfurter API para {currency} en {date}")
        return None
    except httpx.RequestError as e:
        logger.error(f"Error de red consultando Frankfurter API: {e}")
        return None
    except Exception as e:
        logger.exception(f"Error inesperado obteniendo tipo de cambio: {e}")
        return None


async def get_latest_exchange_rate(currency: str) -> Optional[float]:
    """
    Obtiene el tipo de cambio más reciente de una moneda a EUR.
    
    Args:
        currency: Código de moneda origen (USD, GBP, etc.)
    
    Returns:
        Tipo de cambio más reciente, o None si no se puede obtener.
    """
    if not currency or currency.upper() == "EUR":
        return 1.0
    
    currency = currency.upper().strip()
    url = f"{FRANKFURTER_API_URL}/latest?from={currency}&to=EUR"
    
    logger.info(f"Consultando tipo de cambio actual: {url}")
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url)
            
            if response.status_code != 200:
                logger.warning(f"Frankfurter API respondió con status {response.status_code}")
                return None
            
            data = response.json()
            eur_rate = data.get("rates", {}).get("EUR")
            
            if eur_rate and eur_rate != 0:
                return round(1 / eur_rate, 4)
            return None
            
    except Exception as e:
        logger.exception(f"Error obteniendo tipo de cambio actual: {e}")
        return None

