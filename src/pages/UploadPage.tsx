import { useState } from 'react'

export default function UploadPage({ token }: { token: string }) {
  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [msg, setMsg] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!file) return
    setLoading(true)
    setMsg('')
    const formData = new FormData()
    formData.append('file', file)
    try {
      // Aquí deberías tener un endpoint en FastAPI para subir archivos
      const res = await fetch('http://localhost:8000/n8n/webhook', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData as any // FastAPI debe aceptar multipart/form-data
      })
      if (!res.ok) throw new Error('Error subiendo archivo')
      setMsg('Archivo subido correctamente')
    } catch (err: any) {
      setMsg(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="upload-page">
      <h2>Subir factura o fichero de ventas</h2>
      <form onSubmit={handleSubmit}>
        <input type="file" accept=".pdf,.csv" onChange={e => setFile(e.target.files?.[0] || null)} required />
        <button type="submit" disabled={loading}>{loading ? 'Subiendo...' : 'Subir'}</button>
      </form>
      {msg && <div>{msg}</div>}
    </div>
  )
}
