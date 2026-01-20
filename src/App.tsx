import { useState, useEffect } from 'react'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import UploadPage from './pages/UploadPage'
import EstadoModelosPage from './pages/EstadoModelosPage'
import MesDetallePage from './pages/MesDetallePage'
import CreateInvoicePage from './pages/CreateInvoicePage'
import './App.css'

// Importamos el logo desde src/assets
import logo from './assets/logo.png'
// Iconos
import { LogOut, User, Clock, RefreshCw, XCircle } from 'lucide-react'
import { fetchWithAuth } from './utils/fetchWithAuth'
import { useSessionRefresh } from './utils/useSessionRefresh'

// Componente Modal de aviso de sesión
function SessionWarningModal({ 
  timeRemaining, 
  onContinue, 
  onLogout 
}: { 
  timeRemaining: number
  onContinue: () => void
  onLogout: () => void
}) {
  const minutes = Math.floor(timeRemaining / 60)
  const seconds = timeRemaining % 60
  const timeDisplay = minutes > 0 
    ? `${minutes}:${seconds.toString().padStart(2, '0')}` 
    : `${seconds} segundos`

  return (
    <div 
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.7)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 99999, // Por encima de cualquier otro modal
        backdropFilter: 'blur(4px)',
      }}
    >
      <div 
        style={{
          backgroundColor: 'white',
          borderRadius: '12px',
          padding: '32px',
          maxWidth: '400px',
          width: '90%',
          textAlign: 'center',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
          animation: 'fadeIn 0.2s ease-out',
        }}
      >
        {/* Icono de reloj animado */}
        <div 
          style={{
            width: '64px',
            height: '64px',
            margin: '0 auto 20px',
            backgroundColor: '#fef3c7',
            borderRadius: '50%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Clock 
            style={{ 
              width: '32px', 
              height: '32px', 
              color: '#d97706',
              animation: 'pulse 1s ease-in-out infinite',
            }} 
          />
        </div>

        {/* Título */}
        <h2 
          style={{
            fontSize: '20px',
            fontWeight: 600,
            color: '#1f2937',
            marginBottom: '12px',
          }}
        >
          Tu sesión está a punto de expirar
        </h2>

        {/* Mensaje con cuenta regresiva */}
        <p 
          style={{
            fontSize: '16px',
            color: '#6b7280',
            marginBottom: '8px',
          }}
        >
          Por tu seguridad, la sesión se cerrará en:
        </p>

        {/* Tiempo restante destacado */}
        <div 
          style={{
            fontSize: '36px',
            fontWeight: 700,
            color: timeRemaining <= 30 ? '#dc2626' : '#d97706',
            marginBottom: '24px',
            fontFamily: 'monospace',
            transition: 'color 0.3s',
          }}
        >
          {timeDisplay}
        </div>

        {/* Botones */}
        <div style={{ display: 'flex', gap: '12px', justifyContent: 'center' }}>
          <button
            onClick={onContinue}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '12px 24px',
              backgroundColor: '#2563eb',
              color: 'white',
              border: 'none',
              borderRadius: '8px',
              fontSize: '14px',
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'background-color 0.2s',
            }}
            onMouseOver={(e) => e.currentTarget.style.backgroundColor = '#1d4ed8'}
            onMouseOut={(e) => e.currentTarget.style.backgroundColor = '#2563eb'}
          >
            <RefreshCw style={{ width: '16px', height: '16px' }} />
            Continuar sesión
          </button>
          
          <button
            onClick={onLogout}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '12px 24px',
              backgroundColor: '#f3f4f6',
              color: '#374151',
              border: '1px solid #d1d5db',
              borderRadius: '8px',
              fontSize: '14px',
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'background-color 0.2s',
            }}
            onMouseOver={(e) => e.currentTarget.style.backgroundColor = '#e5e7eb'}
            onMouseOut={(e) => e.currentTarget.style.backgroundColor = '#f3f4f6'}
          >
            <XCircle style={{ width: '16px', height: '16px' }} />
            Cerrar sesión
          </button>
        </div>
      </div>

      {/* Estilos de animación inline */}
      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: scale(0.95); }
          to { opacity: 1; transform: scale(1); }
        }
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>
    </div>
  )
}

function App() {
  const [token, setToken] = useState<string | null>(null)
  const [page, setPage] = useState('dashboard')
  const [checkingToken, setCheckingToken] = useState(false)
  const [dashboardKey, setDashboardKey] = useState(0)

  const handleLogout = (source: string = 'unknown') => {
    console.warn(`[App] ⚠️ LOGOUT llamado desde: ${source}`)
    console.trace('[App] Stack trace:')
    setToken(null)
    setPage('dashboard')
  }

  // Hook de gestión de sesión con aviso de expiración
  const { showExpiryWarning, timeRemaining, extendSession } = useSessionRefresh(
    token, 
    setToken, 
    () => handleLogout('useSessionRefresh')
  )

  // Verificar si el token es válido cuando cambia el token o la página
  useEffect(() => {
    if (!token) return

    const verifyToken = async () => {
      setCheckingToken(true)
      try {
        const response = await fetchWithAuth('http://localhost:8000/auth/me', {
          token,
          onLogout: () => handleLogout('fetchWithAuth-401'),
        })
        if (!response.ok) {
          // Si el token no es válido, handleLogout ya fue llamado por fetchWithAuth
          return
        }
      } catch (error) {
        // Si hay un error de red, también cerramos sesión por seguridad
        console.error('[App] Error de red verificando token:', error)
        handleLogout('verifyToken-network-error')
      } finally {
        setCheckingToken(false)
      }
    }

    verifyToken()
  }, [token, page]) // Verificar cuando cambia el token o la página

  if (!token) return <LoginPage onLogin={setToken} />
  
  if (checkingToken) {
    return <div style={{ padding: '2rem', textAlign: 'center' }}>Verificando sesión...</div>
  }

  return (
    <div>
      {/* Modal de aviso de sesión - z-index muy alto para aparecer sobre todo */}
      {showExpiryWarning && (
        <SessionWarningModal 
          timeRemaining={timeRemaining}
          onContinue={extendSession}
          onLogout={() => handleLogout('SessionWarningModal')}
        />
      )}

      <nav style={{ display: 'flex', alignItems: 'center', width: '100%' }} className="bg-blue-900 text-white px-6 py-3 mb-8">
        {/* Logo y Menú juntos a la izquierda */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '2rem' }}>
          {/* Logo */}
          <div className="flex items-center space-x-2">
            <img src={logo} alt="Nementium.ai" className="h-6 object-contain" />
          </div>

          {/* Menú junto al logo */}
          <div className="flex space-x-6">
            <button
              onClick={() => {
                setPage('dashboard')
                // Forzar remount del dashboard para recargar datos
                setDashboardKey(prev => prev + 1)
              }}
              className={`navlink ${page === 'dashboard' ? 'active' : ''}`}
              aria-current={page === 'dashboard' ? 'page' : undefined}
            >
              Dashboard
            </button>
            <button
              onClick={() => setPage('upload')}
              className={`navlink ${page === 'upload' ? 'active' : ''}`}
              aria-current={page === 'upload' ? 'page' : undefined}
            >
              Subir factura/ventas
            </button>
            <button
              onClick={() => setPage('estado')}
              className={`navlink ${page === 'estado' ? 'active' : ''}`}
              aria-current={page === 'estado' ? 'page' : undefined}
            >
              Estado trimestral
            </button>
            <button
              onClick={() => setPage('mesdetalle')}
              className={`navlink ${page === 'mesdetalle' ? 'active' : ''}`}
              aria-current={page === 'mesdetalle' ? 'page' : undefined}
            >
              Histórico
            </button>
            <button
              onClick={() => setPage('crear-factura')}
              className={`navlink ${page === 'crear-factura' ? 'active' : ''}`}
              aria-current={page === 'crear-factura' ? 'page' : undefined}
            >
              Crear Facturas
            </button>
            <button
              onClick={() => setPage('mesdetalle')}
              className={`navlink ${page === 'mesdetalle' ? 'active' : ''}`}
              aria-current={page === 'mesdetalle' ? 'page' : undefined}
            >
              Notificaciones (2)
            </button>
            <button
              onClick={() => setPage('mesdetalle')}
              className={`navlink ${page === 'mesdetalle' ? 'active' : ''}`}
              aria-current={page === 'mesdetalle' ? 'page' : undefined}
            >
              Documentos presentados
            </button>
          </div>
        </div>

        {/* Espacio flexible para empujar los botones a la derecha */}
        <div style={{ flex: 1 }}></div>

        {/* Botones a la derecha - siempre dentro de la imagen */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginRight: '3rem' }}>
          <button
            type="button"
            className="navlink p-1"
            aria-label="Usuario"
            title="Usuario"
          >
            <User className="w-5 h-5" />
          </button>
          <button
            onClick={() => handleLogout('nav-button')}
            className="navlink p-1"
            aria-label="Salir"
            title="Salir"
          >
            <LogOut className="w-5 h-5" />
          </button>
        </div>
      </nav>

      <main style={{ marginTop: '4rem' }}>
        {page === 'dashboard' && <DashboardPage key={dashboardKey} token={token} onLogout={() => handleLogout('DashboardPage')} />}
        {page === 'upload' && <UploadPage token={token} onLogout={() => handleLogout('UploadPage')} />}
        {page === 'estado' && <EstadoModelosPage token={token} onLogout={() => handleLogout('EstadoModelosPage')} />}
        {page === 'mesdetalle' && <MesDetallePage token={token} onLogout={() => handleLogout('MesDetallePage')} />}
        {page === 'crear-factura' && <CreateInvoicePage token={token} onLogout={() => handleLogout('CreateInvoicePage')} />}
      </main>
    </div>
  )
}

export default App
