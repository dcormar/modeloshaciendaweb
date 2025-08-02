import { useState } from 'react'

function pad(n: number) {
  return n < 10 ? `0${n}` : n
}


export default function MesDetallePage({ token }: { token: string }) {
  const today = new Date()
  const [anio, setAnio] = useState(today.getFullYear())
  const [mes, setMes] = useState(today.getMonth() + 1)
  const [dia, setDia] = useState<number | ''>(today.getDate())
  const [ventas, setVentas] = useState<any[]>([])
  const [facturas, setFacturas] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchData = async () => {
    setLoading(true)
    setError(null)
    try {
      const mesStr = pad(mes)
      let desde = `${anio}-${mesStr}-01`
      let hasta = `${anio}-${mesStr}-${pad(new Date(anio, mes, 0).getDate())}`
      if (dia !== '') {
        const diaStr = pad(Number(dia))
        desde = `${anio}-${mesStr}-${diaStr}`
        hasta = desde
      }
      const ventasRes = await fetch(`http://localhost:8000/ventas?desde=${desde}&hasta=${hasta}`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      if (!ventasRes.ok) throw new Error('Error cargando ventas')
      const facturasRes = await fetch(`http://localhost:8000/facturas?desde=${desde}&hasta=${hasta}`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      if (!facturasRes.ok) throw new Error('Error cargando facturas')
      setVentas(await ventasRes.json())
      setFacturas(await facturasRes.json())
    } catch (e: any) {
      setError(e.message || 'Error desconocido')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mes-detalle-page">
      <h2>Ventas y facturas de un mes</h2>
      <form onSubmit={e => { e.preventDefault(); fetchData() }} style={{display:'flex',alignItems:'flex-end',gap:'1.5rem',flexWrap:'wrap'}}>
        <div style={{display:'flex',flexDirection:'column',alignItems:'flex-start'}}>
          <label style={{marginBottom:4}}>Año:</label>
          <input type="number" value={anio} onChange={e => setAnio(Number(e.target.value))} min={2000} max={2100} style={{width:80}} />
        </div>
        <div style={{display:'flex',flexDirection:'column',alignItems:'flex-start'}}>
          <label style={{marginBottom:4}}>Mes:</label>
          <input type="number" value={mes} onChange={e => setMes(Number(e.target.value))} min={1} max={12} style={{width:60}} />
        </div>
        <div style={{display:'flex',flexDirection:'column',alignItems:'flex-start'}}>
          <label style={{marginBottom:4}}>Día:</label>
          <input type="number" value={dia} onChange={e => setDia(e.target.value === '' ? '' : Number(e.target.value))} min={1} max={31} placeholder="Todo el mes" style={{width:60}} />
        </div>
        <div style={{display:'flex',flexDirection:'column',alignItems:'flex-start'}}>
          <span style={{visibility:'hidden',height:20,marginBottom:4}}>&nbsp;</span>
          <button type="submit" style={{height:36,minWidth:60,margin:0}}>Ver</button>
        </div>
      </form>
      <div style={{marginTop:'0.5rem',color:'#555',fontSize:'0.97em'}}>
        {dia === '' ?
          'No se ha indicado día: se mostrarán los datos de todo el mes seleccionado.' :
          'Se mostrarán los datos solo del día seleccionado.'
        }
      </div>
      {loading && <div style={{marginTop:'1.5rem'}}>Cargando...</div>}
      {error && <div style={{color:'red',marginTop:'1.5rem'}}>Error: {error}</div>}
      <div style={{marginTop:'2.5rem'}}>
        <h3>Ventas</h3>
        <div style={{overflowX:'auto'}}>
          <table>
            <thead>
              <tr style={{background:'#b3c6e0'}}>
                <th>ID</th>
                <th>SKU</th>
                <th>Descripción</th>
                <th>Fecha</th>
                <th>Cantidad</th>
                <th>Total (€)</th>
              </tr>
            </thead>
            <tbody>
              {ventas.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{textAlign:'center',color:'#888',background:'#f6f8fa'}}>No hay ventas registradas para el filtro seleccionado.</td>
                </tr>
              ) : ventas.map((v, i) => (
                <tr key={i}>
                  <td>{v.ID}</td>
                  <td>{v.SELLER_SKU}</td>
                  <td>{v.ITEM_DESCRIPTION}</td>
                  <td>{v.TRANSACTION_COMPLETE_DATE_DT || v.TRANSACTION_COMPLETE_DATE}</td>
                  <td>{v.QTY}</td>
                  <td>{v.TOTAL_PRICE_OF_ITEMS_AMT_VAT_INCL ?? v.TOTAL_PRICE_OF_ITEMS_AMT_VAT_EXCL}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <h3 style={{marginTop:'2.5rem'}}>Facturas</h3>
        <div style={{overflowX:'auto'}}>
          <table>
            <thead>
              <tr style={{background:'#b3c6e0'}}>
                <th>ID</th>
                <th>Proveedor</th>
                <th>Fecha</th>
                <th>Total (€)</th>
              </tr>
            </thead>
            <tbody>
              {facturas.length === 0 ? (
                <tr>
                  <td colSpan={4} style={{textAlign:'center',color:'#888',background:'#f6f8fa'}}>No hay facturas registradas para el filtro seleccionado.</td>
                </tr>
              ) : facturas.map((f, i) => (
                <tr key={i}>
                  <td>{f.id}</td>
                  <td>{f.proveedor}</td>
                  <td>{f.fecha}</td>
                  <td>{f.total}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
