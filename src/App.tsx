import { useState } from 'react'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import UploadPage from './pages/UploadPage'
import EstadoModelosPage from './pages/EstadoModelosPage'
import MesDetallePage from './pages/MesDetallePage'
import './App.css'

// Importamos el logo desde src/assets
import logo from './assets/logo.png'
// Iconos
import { LogOut, User } from 'lucide-react'

function App() {
  const [token, setToken] = useState<string | null>(null)
  const [page, setPage] = useState('dashboard')

  if (!token) return <LoginPage onLogin={setToken} />

  return (
    <div>
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
              onClick={() => setPage('dashboard')}
              className={`navlink ${page === 'dashboard' ? 'active' : ''}`}
              aria-current={page === 'dashboard' ? 'page' : undefined}
            >
              Dashboard
            </button>
            <button
              onClick={() => setPage('upload')}
              className={`navlink ${page === 'upload' ? 'active' : ''}`}
              aria-current={page === 'upload' ? 'page' : undefined}å
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
            onClick={() => { setToken(null); setPage('dashboard') }}
            className="navlink p-1"
            aria-label="Salir"
            title="Salir"
          >
            <LogOut className="w-5 h-5" />
          </button>
        </div>
      </nav>

      <main style={{ marginTop: '4rem' }}>
        {page === 'dashboard' && <DashboardPage token={token} />}
        {page === 'upload' && <UploadPage token={token} />}
        {page === 'estado' && <EstadoModelosPage token={token} />}
        {page === 'mesdetalle' && <MesDetallePage token={token} />}
      </main>
    </div>
  )
}

export default App