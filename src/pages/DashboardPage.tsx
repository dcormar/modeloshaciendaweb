import { useEffect, useState } from 'react'

export default function DashboardPage({ token }: { token: string }) {
  const [data, setData] = useState<{ ventas_mes: number, gastos_mes: number, facturas_trimestre: number } | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('http://localhost:8000/dashboard/', {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then(r => r.json())
      .then(setData)
      .finally(() => setLoading(false))
  }, [token])

  if (loading) return <div>Cargando...</div>
  if (!data) return <div>Error cargando dashboard</div>

  return (
    <div className="dashboard-page">
      <h2>Dashboard</h2>
      <div>Ventas del mes: <b>{data.ventas_mes} €</b></div>
      <div>Gastos del mes: <b>{data.gastos_mes} €</b></div>
      <div>Facturas subidas en el trimestre: <b>{data.facturas_trimestre}</b></div>
    </div>
  )
}
