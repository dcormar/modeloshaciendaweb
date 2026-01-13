#!/bin/bash
set -euo pipefail

# Ir al directorio del script (backend/)
cd "$(dirname "$0")"

# Cargar .env de forma segura
if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

# Arrancar uvicorn con el venv local
.venv/bin/uvicorn main:app --reload --port 8000
