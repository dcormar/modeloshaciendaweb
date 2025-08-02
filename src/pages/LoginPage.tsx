import { useState } from 'react'

export default function LoginPage({ onLogin }: { onLogin: (token: string) => void }) {
  const [email, setEmail] = useState('demo@demo.com')
  const [password, setPassword] = useState('demo')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const res = await fetch('http://localhost:8000/auth/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ username: email, password, grant_type: 'password' })
      })
      if (!res.ok) throw new Error('Login incorrecto')
      const data = await res.json()
      onLogin(data.access_token)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-page">
      <h2>Iniciar sesión</h2>
      <form onSubmit={handleSubmit}>
        <input
            type="email"
            name="username"
            autoComplete="username"
            placeholder="Email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            required
        />
        <input
            type="password"
            name="password"
            autoComplete="current-password"
            placeholder="Contraseña"
            value={password}
            onChange={e => setPassword(e.target.value)}
            required
        />
        <button type="submit" disabled={loading}>
            {loading ? 'Entrando...' : 'Entrar'}
        </button>
        {error && <div className="error">{error}</div>}
        </form>
    </div>
  )
}
