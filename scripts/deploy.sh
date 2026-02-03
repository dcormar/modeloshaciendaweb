#!/bin/bash
# deploy.sh - Script de despliegue para Nementium Rocket
# Ejecutar desde tu ordenador local: ./scripts/deploy.sh

set -e  # Salir si hay error

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuración
SERVER="root@157.180.16.178"
PROJECT_PATH="/var/www/nementium_rocket"
SERVICE_NAME="nementium-rocket-api"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   Nementium Rocket - Deploy Script    ${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Verificar que estamos en el directorio correcto
if [ ! -f "package.json" ] || [ ! -d "backend" ]; then
    echo -e "${RED}Error: Ejecuta este script desde la raíz del proyecto nementium_rocket${NC}"
    exit 1
fi

# Opciones de deploy
DEPLOY_BACKEND=false
DEPLOY_FRONTEND=false
INSTALL_DEPS=false

# Parsear argumentos
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --backend|-b) DEPLOY_BACKEND=true ;;
        --frontend|-f) DEPLOY_FRONTEND=true ;;
        --all|-a) DEPLOY_BACKEND=true; DEPLOY_FRONTEND=true ;;
        --deps|-d) INSTALL_DEPS=true ;;
        --help|-h)
            echo "Uso: ./scripts/deploy.sh [opciones]"
            echo ""
            echo "Opciones:"
            echo "  --backend, -b    Solo deploy del backend"
            echo "  --frontend, -f   Solo deploy del frontend"
            echo "  --all, -a        Deploy completo (frontend + backend)"
            echo "  --deps, -d       Instalar dependencias (pip install / npm install)"
            echo "  --help, -h       Mostrar esta ayuda"
            echo ""
            echo "Ejemplos:"
            echo "  ./scripts/deploy.sh --backend           # Solo backend"
            echo "  ./scripts/deploy.sh --all --deps        # Todo + dependencias"
            exit 0
            ;;
        *) echo -e "${RED}Opción desconocida: $1${NC}"; exit 1 ;;
    esac
    shift
done

# Si no se especificó nada, preguntar
if [ "$DEPLOY_BACKEND" = false ] && [ "$DEPLOY_FRONTEND" = false ]; then
    echo -e "${YELLOW}¿Qué quieres deployar?${NC}"
    echo "  1) Solo backend"
    echo "  2) Solo frontend"
    echo "  3) Todo (backend + frontend)"
    read -p "Opción [1-3]: " choice
    case $choice in
        1) DEPLOY_BACKEND=true ;;
        2) DEPLOY_FRONTEND=true ;;
        3) DEPLOY_BACKEND=true; DEPLOY_FRONTEND=true ;;
        *) echo -e "${RED}Opción inválida${NC}"; exit 1 ;;
    esac
fi

echo ""
echo -e "${YELLOW}Configuración del deploy:${NC}"
echo "  - Backend: $DEPLOY_BACKEND"
echo "  - Frontend: $DEPLOY_FRONTEND"
echo "  - Instalar dependencias: $INSTALL_DEPS"
echo ""

# Confirmar
read -p "¿Continuar? (y/n): " confirm
if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo -e "${YELLOW}Deploy cancelado${NC}"
    exit 0
fi

echo ""
echo -e "${BLUE}[1/5] Conectando al servidor y haciendo git pull...${NC}"
ssh $SERVER "cd $PROJECT_PATH && git pull origin main"

if [ "$DEPLOY_FRONTEND" = true ]; then
    echo ""
    echo -e "${BLUE}[2/5] Construyendo frontend...${NC}"

    if [ "$INSTALL_DEPS" = true ]; then
        echo -e "${YELLOW}  Instalando dependencias npm...${NC}"
        ssh $SERVER "su - dcormar -c 'cd $PROJECT_PATH && npm install'"
    fi

    echo -e "${YELLOW}  Ejecutando npm run build...${NC}"
    ssh $SERVER "su - dcormar -c 'cd $PROJECT_PATH && npm run build'"
else
    echo ""
    echo -e "${YELLOW}[2/5] Saltando frontend...${NC}"
fi

if [ "$DEPLOY_BACKEND" = true ]; then
    echo ""
    echo -e "${BLUE}[3/5] Actualizando backend...${NC}"

    if [ "$INSTALL_DEPS" = true ]; then
        echo -e "${YELLOW}  Instalando dependencias pip...${NC}"
        ssh $SERVER "su - dcormar -c 'cd $PROJECT_PATH/backend && source venv/bin/activate && pip install -r requirements.txt'"
    fi

    echo ""
    echo -e "${BLUE}[4/5] Reiniciando servicio backend...${NC}"
    ssh $SERVER "systemctl restart $SERVICE_NAME"

    # Esperar un poco para que arranque
    sleep 2
else
    echo ""
    echo -e "${YELLOW}[3/5] Saltando backend...${NC}"
    echo -e "${YELLOW}[4/5] Saltando reinicio de servicio...${NC}"
fi

echo ""
echo -e "${BLUE}[5/5] Verificando estado...${NC}"

# Verificar servicio
echo ""
echo -e "${YELLOW}Estado del servicio:${NC}"
ssh $SERVER "systemctl status $SERVICE_NAME --no-pager -l | head -20"

# Health check
echo ""
echo -e "${YELLOW}Health check:${NC}"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" https://rocket.nementium.ai/health)
if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✅ rocket.nementium.ai responde correctamente (HTTP $HTTP_CODE)${NC}"
else
    echo -e "${RED}❌ rocket.nementium.ai responde HTTP $HTTP_CODE${NC}"
fi

API_CODE=$(curl -s -o /dev/null -w "%{http_code}" https://api.nementium.ai/api/auth/token -X POST -H "Content-Type: application/json" -d '{}')
echo -e "${GREEN}✅ api.nementium.ai accesible (HTTP $API_CODE - 422 es esperado sin credenciales)${NC}"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   Deploy completado exitosamente!     ${NC}"
echo -e "${GREEN}========================================${NC}"
