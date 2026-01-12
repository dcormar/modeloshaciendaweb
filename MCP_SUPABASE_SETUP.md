# Configuración de MCP de Supabase para Cursor

## Opción 1: Usar servidor MCP oficial de Supabase (si existe)

1. **Instalar el servidor MCP de Supabase** (si está disponible):
   ```bash
   npm install -g @modelcontextprotocol/server-supabase
   ```

2. **Configurar en Cursor**:
   - Abre la configuración de Cursor (Settings)
   - Busca "MCP Servers" o "Model Context Protocol"
   - Añade la siguiente configuración en `~/.cursor/mcp.json` o en la configuración de Cursor:

   ```json
   {
     "mcpServers": {
       "supabase": {
         "command": "npx",
         "args": ["@modelcontextprotocol/server-supabase"],
         "env": {
           "SUPABASE_URL": "https://tu-proyecto.supabase.co",
           "SUPABASE_SERVICE_ROLE_KEY": "tu-service-role-key"
         }
       }
     }
   }
   ```

3. **Obtener las credenciales**:
   - Ve a tu proyecto en Supabase Dashboard
   - Settings → API
   - Copia la `URL` del proyecto (SUPABASE_URL)
   - Copia la `service_role` key (SUPABASE_SERVICE_ROLE_KEY) - **¡Cuidado! Esta clave tiene acceso completo**

## Opción 2: Usar MCP genérico con PostgreSQL

Si no existe un servidor MCP específico de Supabase, puedes usar un servidor MCP genérico de PostgreSQL que se conecte a tu base de datos de Supabase:

1. **Obtener la connection string de Supabase**:
   - Ve a Settings → Database
   - Copia la "Connection string" (formato URI o usar los parámetros individuales)

2. **Configurar MCP de PostgreSQL**:
   ```json
   {
     "mcpServers": {
       "supabase-postgres": {
         "command": "npx",
         "args": ["@modelcontextprotocol/server-postgres"],
         "env": {
           "POSTGRES_CONNECTION_STRING": "postgresql://postgres:[PASSWORD]@[HOST]:5432/postgres"
         }
       }
     }
   }
   ```

## Nota importante

**Recomendación**: La forma más sencilla y segura es ejecutar el script SQL manualmente en el SQL Editor de Supabase. Esto te da control total y no requiere configurar servidores MCP adicionales.

El archivo `sql/create_facturas_generadas.sql` contiene todo lo necesario para crear la tabla.

