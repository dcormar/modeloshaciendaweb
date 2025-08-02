import { useState } from 'react'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import UploadPage from './pages/UploadPage'
import EstadoModelosPage from './pages/EstadoModelosPage'
import MesDetallePage from './pages/MesDetallePage'
import './App.css'

function App() {
  const [token, setToken] = useState<string | null>(null)
  const [page, setPage] = useState('dashboard')

  if (!token) return <LoginPage onLogin={setToken} />

  return (
    <div>
      <nav>
        <button onClick={() => setPage('dashboard')}>Dashboard</button>
        <button onClick={() => setPage('upload')}>Subir factura/ventas</button>
        <button onClick={() => setPage('estado')}>Estado modelos</button>
        <button onClick={() => setPage('mesdetalle')}>Ventas/Facturas por mes</button>
        <button onClick={() => { setToken(null); setPage('dashboard') }}>Salir</button>
      </nav>
      {page === 'dashboard' && <DashboardPage token={token} />}
      {page === 'upload' && <UploadPage token={token} />}
      {page === 'estado' && <EstadoModelosPage token={token} />}
      {page === 'mesdetalle' && <MesDetallePage token={token} />}
    </div>
  )
}

export default App
