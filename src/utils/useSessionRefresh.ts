import { useEffect, useRef, useState, useCallback } from 'react';
import { fetchWithAuth } from './fetchWithAuth';

// Configuración de tiempos
const SESSION_DURATION_MINUTES = 15;      // Duración total del token (debe coincidir con backend)
const REFRESH_BEFORE_EXPIRY_MINUTES = 2;  // Refrescar 2 minutos ANTES de que expire
const INACTIVITY_WARNING_MINUTES = 14;    // Mostrar aviso de inactividad

interface SessionRefreshResult {
  showExpiryWarning: boolean;
  timeRemaining: number;
  extendSession: () => void;
}

/**
 * Decodifica un JWT y obtiene el timestamp de expiración
 */
function getTokenExpiration(token: string): number | null {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    if (payload.exp) {
      return payload.exp * 1000; // Convertir segundos a milliseconds
    }
    return null;
  } catch {
    return null;
  }
}

/**
 * Hook que gestiona el refresh automático del token basándose en su expiración REAL.
 * 
 * - Refresca el token automáticamente 2 minutos ANTES de que expire (basado en el JWT)
 * - Muestra aviso de inactividad si el usuario no interactúa por 14 minutos
 * - La actividad del usuario NO resetea el timer de refresh (solo el de inactividad)
 */
export function useSessionRefresh(
  token: string | null,
  onTokenUpdate: (newToken: string) => void,
  onLogout?: () => void
): SessionRefreshResult {
  const [showExpiryWarning, setShowExpiryWarning] = useState(false);
  const [timeRemaining, setTimeRemaining] = useState(SESSION_DURATION_MINUTES * 60);
  
  // Refs para timers
  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const warningTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inactivityTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const countdownIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  
  // Refs para estado
  const isRefreshingRef = useRef<boolean>(false);
  const isLoggingOutRef = useRef<boolean>(false);
  const lastActivityRef = useRef<number>(Date.now());
  const tokenExpirationRef = useRef<number | null>(null);

  // Limpiar todos los timers
  const clearAllTimers = useCallback(() => {
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current);
      refreshTimerRef.current = null;
    }
    if (warningTimerRef.current) {
      clearTimeout(warningTimerRef.current);
      warningTimerRef.current = null;
    }
    if (inactivityTimerRef.current) {
      clearTimeout(inactivityTimerRef.current);
      inactivityTimerRef.current = null;
    }
    if (countdownIntervalRef.current) {
      clearInterval(countdownIntervalRef.current);
      countdownIntervalRef.current = null;
    }
  }, []);

  // Función para refrescar el token
  const refreshToken = useCallback(async (): Promise<boolean> => {
    if (!token || isRefreshingRef.current || isLoggingOutRef.current) {
      return false;
    }

    isRefreshingRef.current = true;
    console.log('[Session] Refrescando token...');
    
    try {
      const response = await fetchWithAuth('http://localhost:8000/auth/refresh', {
        method: 'POST',
        token,
      });

      if (response.ok) {
        const data = await response.json();
        console.log('[Session] Token refrescado exitosamente');
        onTokenUpdate(data.access_token);
        return true;
      } else {
        console.warn('[Session] Fallo refresh:', response.status);
        return false;
      }
    } catch (error) {
      console.error('[Session] Error refresh:', error);
      return false;
    } finally {
      isRefreshingRef.current = false;
    }
  }, [token, onTokenUpdate]);

  // Programar el refresh basado en la expiración REAL del token
  const scheduleTokenRefresh = useCallback((tokenExp: number) => {
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current);
    }

    const now = Date.now();
    const refreshBeforeMs = REFRESH_BEFORE_EXPIRY_MINUTES * 60 * 1000;
    const timeUntilRefresh = Math.max(0, tokenExp - now - refreshBeforeMs);
    const timeUntilExpiry = Math.max(0, tokenExp - now);

    console.log(`[Session] Token expira en ${Math.round(timeUntilExpiry/1000)}s, refresh en ${Math.round(timeUntilRefresh/1000)}s`);

    // Si ya pasó el tiempo de refresh, hacerlo inmediatamente
    if (timeUntilRefresh <= 0 && timeUntilExpiry > 0) {
      console.log('[Session] Ejecutando refresh inmediato (cerca de expiración)');
      refreshToken().then(success => {
        if (!success && onLogout && !isLoggingOutRef.current) {
          console.warn('[Session] Refresh inmediato falló - cerrando sesión');
          isLoggingOutRef.current = true;
          onLogout();
        }
      });
      return;
    }

    // Si ya expiró, hacer logout
    if (timeUntilExpiry <= 0) {
      console.warn('[Session] Token ya expirado');
      if (onLogout && !isLoggingOutRef.current) {
        isLoggingOutRef.current = true;
        onLogout();
      }
      return;
    }

    // Programar el refresh
    refreshTimerRef.current = setTimeout(async () => {
      console.log('[Session] Timer de refresh disparado');
      const success = await refreshToken();
      if (!success && onLogout && !isLoggingOutRef.current) {
        console.warn('[Session] Refresh automático falló - cerrando sesión');
        isLoggingOutRef.current = true;
        onLogout();
      }
      // Si tuvo éxito, el token se actualizará y se reprogramará el refresh
    }, timeUntilRefresh);

    // Actualizar tiempo restante cada segundo para la UI
    if (countdownIntervalRef.current) {
      clearInterval(countdownIntervalRef.current);
    }
    countdownIntervalRef.current = setInterval(() => {
      const remaining = Math.max(0, Math.ceil((tokenExp - Date.now()) / 1000));
      setTimeRemaining(remaining);
    }, 1000);

  }, [refreshToken, onLogout]);

  // Programar timer de inactividad (basado en actividad del usuario)
  const scheduleInactivityTimer = useCallback(() => {
    if (inactivityTimerRef.current) {
      clearTimeout(inactivityTimerRef.current);
    }
    if (warningTimerRef.current) {
      clearTimeout(warningTimerRef.current);
    }

    const inactivityMs = INACTIVITY_WARNING_MINUTES * 60 * 1000;
    const now = Date.now();
    const timeSinceActivity = now - lastActivityRef.current;
    const timeUntilWarning = Math.max(0, inactivityMs - timeSinceActivity);

    // Timer para mostrar warning de inactividad
    if (timeUntilWarning > 0) {
      warningTimerRef.current = setTimeout(() => {
        console.log('[Session] Mostrando aviso de inactividad');
        setShowExpiryWarning(true);
      }, timeUntilWarning);
    }

    // Timer para logout por inactividad (1 minuto después del warning)
    const logoutMs = (INACTIVITY_WARNING_MINUTES + 1) * 60 * 1000;
    const timeUntilLogout = Math.max(0, logoutMs - timeSinceActivity);
    
    if (timeUntilLogout > 0) {
      inactivityTimerRef.current = setTimeout(() => {
        console.warn('[Session] Logout por inactividad');
        if (onLogout && !isLoggingOutRef.current) {
          isLoggingOutRef.current = true;
          onLogout();
        }
      }, timeUntilLogout);
    }
  }, [onLogout]);

  // Manejar actividad del usuario (solo resetea timer de inactividad, NO el de refresh)
  const handleActivity = useCallback(() => {
    if (isLoggingOutRef.current) return;
    
    lastActivityRef.current = Date.now();
    
    // Si estamos mostrando el aviso de inactividad, ocultarlo
    if (showExpiryWarning) {
      setShowExpiryWarning(false);
    }
    
    // Reprogramar solo el timer de inactividad (NO el de refresh del token)
    scheduleInactivityTimer();
  }, [showExpiryWarning, scheduleInactivityTimer]);

  // Función para extender la sesión manualmente
  const extendSession = useCallback(async () => {
    const success = await refreshToken();
    if (success) {
      lastActivityRef.current = Date.now();
      setShowExpiryWarning(false);
    } else if (onLogout && !isLoggingOutRef.current) {
      console.warn('[Session] Fallo al extender sesión');
      isLoggingOutRef.current = true;
      onLogout();
    }
  }, [refreshToken, onLogout]);

  // Efecto principal: cuando cambia el token
  useEffect(() => {
    if (!token) {
      clearAllTimers();
      setShowExpiryWarning(false);
      isLoggingOutRef.current = false;
      tokenExpirationRef.current = null;
      return;
    }

    // Obtener la expiración real del token
    const tokenExp = getTokenExpiration(token);
    if (!tokenExp) {
      console.error('[Session] No se pudo obtener la expiración del token');
      return;
    }

    tokenExpirationRef.current = tokenExp;
    isLoggingOutRef.current = false;
    lastActivityRef.current = Date.now();
    setShowExpiryWarning(false);

    const now = Date.now();
    const remaining = Math.max(0, Math.ceil((tokenExp - now) / 1000));
    setTimeRemaining(remaining);
    
    console.log(`[Session] Nuevo token detectado, expira en ${remaining}s`);

    // Programar refresh basado en expiración REAL del token
    scheduleTokenRefresh(tokenExp);

    // Programar timer de inactividad
    scheduleInactivityTimer();

    // Registrar listeners de actividad
    const events = ['mousedown', 'keypress', 'scroll', 'touchstart', 'click'];
    events.forEach(event => {
      window.addEventListener(event, handleActivity, { passive: true });
    });
    window.addEventListener('api-activity', handleActivity);

    return () => {
      events.forEach(event => {
        window.removeEventListener(event, handleActivity);
      });
      window.removeEventListener('api-activity', handleActivity);
      clearAllTimers();
    };
  }, [token, scheduleTokenRefresh, scheduleInactivityTimer, handleActivity, clearAllTimers]);

  return {
    showExpiryWarning,
    timeRemaining,
    extendSession,
  };
}
