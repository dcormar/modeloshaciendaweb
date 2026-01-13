#!/bin/bash
set -euo pipefail

# Ejecutar el script de backend
cd "$(dirname "$0")/backend"
./run.sh
