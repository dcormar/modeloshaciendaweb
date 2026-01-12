#!/bin/bash
set -euo pipefail

# Cargar .env de forma segura
if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

# Arrancar uvicorn (ajusta ruta del venv si cambia)
"/Users/davidcortijomartin/Documents/llm/modeloshaciendaweb/.venv/bin/uvicorn" main:app --reload --port 8000
