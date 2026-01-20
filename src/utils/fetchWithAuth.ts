/**
 * Wrapper de fetch que detecta errores 401 (token expirado)
 * y llama a onLogout para redirigir al usuario al login.
 * También emite eventos de actividad para mantener la sesión activa.
 */

// Flag para habilitar logs de debug (cambiar a true para diagnosticar)
const DEBUG_AUTH = true;

export async function fetchWithAuth(
  url: string,
  options: RequestInit & { token?: string; onLogout?: () => void } = {}
): Promise<Response> {
  const { token, onLogout, ...fetchOptions } = options;

  // Agregar el token al header si está presente
  const headers = new Headers(fetchOptions.headers);
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  let response: Response;
  try {
    response = await fetch(url, {
      ...fetchOptions,
      headers,
    });
  } catch (error) {
    console.error(`[fetchWithAuth] Error de red en ${url}:`, error);
    throw error;
  }

  // Si la llamada fue exitosa (2xx), emitir evento de actividad para resetear timer de sesión
  if (response.ok) {
    window.dispatchEvent(new CustomEvent('api-activity'));
  }

  // Si recibimos un 401, el token ha expirado
  if (response.status === 401) {
    console.warn(`[fetchWithAuth] 401 en ${url} - Token: ${token ? token.substring(0, 20) + '...' : 'ninguno'}`);
    
    if (DEBUG_AUTH) {
      try {
        const errorBody = await response.clone().text();
        console.warn(`[fetchWithAuth] Detalle 401:`, errorBody);
      } catch (e) {}
    }
    
    if (onLogout) {
      alert('Tu sesión ha expirado. Por favor, inicia sesión nuevamente.');
      onLogout();
    }
  }

  return response;
}
