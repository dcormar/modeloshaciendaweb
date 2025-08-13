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
  // Filtro de ventas
  const ventaCampos = ventas.length > 0
    ? Object.keys(ventas[0]).map(k => ({ key: k, label: k }))
    : []
  // Eliminados: const [ventaCampo, setVentaCampo] = useState<string>('')
  // Eliminados: const [ventaValor, setVentaValor] = useState<string>('')
  const [ventaFiltros, setVentaFiltros] = useState([{ campo: '', valor: '' }])
  const [columnasVisibles, setColumnasVisibles] = useState<string[]>([])
  const [showColumnPanel, setShowColumnPanel] = useState(false)

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
      <h2>Ventas y facturas por fecha</h2>
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
          <label style={{marginBottom: 4, visibility: 'hidden'}}>Acción</label>
          <button type="submit" style={{height:36,minWidth:60,marginBottom:8}}>Ver</button>
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
        {/* Filtro solo tras pulsar 'Ver' y si hay datos */}
        {ventas.length > 0 && (
          <div style={{display:'flex',alignItems:'flex-end',gap:'1.5rem',marginBottom:'1rem',flexWrap:'wrap',justifyContent:'space-between'}}>
            <div>
              {ventaFiltros.map((filtro, idx) => (
                <div key={idx} style={{display:'flex',alignItems:'flex-end',gap:'1rem',marginBottom: idx < ventaFiltros.length-1 ? '0.5rem' : 0}}>
                  <div style={{display:'flex',flexDirection:'column',alignItems:'flex-start'}}>
                    <label style={{marginBottom:4}}>Filtrar ventas por:</label>
                    <select value={filtro.campo} onChange={e => {
                      const nuevo = [...ventaFiltros]
                      nuevo[idx].campo = e.target.value
                      nuevo[idx].valor = ''
                      setVentaFiltros(nuevo)
                    }} style={{width:140}}>
                      <option value="">(Selecciona campo)</option>
                      {ventaCampos.map(c => <option key={c.key} value={c.key}>{c.label}</option>)}
                    </select>
                  </div>
                  <div style={{display:'flex',flexDirection:'column',alignItems:'flex-start'}}>
                    <label style={{marginBottom:4}}>Valor:</label>
                    <select value={filtro.valor} onChange={e => {
                      const nuevo = [...ventaFiltros]
                      nuevo[idx].valor = e.target.value
                      setVentaFiltros(nuevo)
                    }} style={{width:140}} disabled={!filtro.campo}>
                      <option value="">Todos</option>
                      {filtro.campo && [...new Set(ventas.map(v => v[filtro.campo]).filter(v => v !== undefined && v !== null))].map((v, i) => (
                        <option key={i} value={v}>{v}</option>
                      ))}
                    </select>
                  </div>
                  {idx === ventaFiltros.length-1 && filtro.campo && (
                    <button type="button" style={{marginLeft:8}} onClick={() => setVentaFiltros([...ventaFiltros, { campo: '', valor: '' }])}>+</button>
                  )}
                  {ventaFiltros.length > 1 && (
                    <button type="button" style={{marginLeft:8}} onClick={() => setVentaFiltros(ventaFiltros.filter((_, i) => i !== idx))}>-</button>
                  )}
                </div>
              ))}
            </div>
            {/* Selector de columnas */}
            <div style={{display:'flex',flexDirection:'column',alignItems:'flex-end',marginLeft:'auto'}}>
              <button type="button" style={{marginBottom:4,padding:'4px 12px',borderRadius:4,border:'1px solid #b3c6e0',background:'#f6f8fa',cursor:'pointer'}} onClick={() => setShowColumnPanel(v => !v)}>
                {showColumnPanel ? 'Ocultar columnas ▲' : 'Mostrar columnas ▼'}
              </button>
              {showColumnPanel && (
                <div style={{border:'1px solid #b3c6e0',borderRadius:6,background:'#fff',boxShadow:'0 2px 8px #0001',padding:'10px',maxHeight:180,overflowY:'auto',minWidth:180,marginBottom:4}}>
                  <label style={{fontWeight:600,marginBottom:8,display:'block'}}>Columnas a mostrar:</label>
                  <div style={{display:'flex',flexDirection:'column',gap:'0.5rem'}}>
                    {ventaCampos.map(c => (
                      <label key={c.key} style={{display:'flex',alignItems:'center',marginRight:8}}>
                        <input
                          type="checkbox"
                          checked={columnasVisibles.length === 0 || columnasVisibles.includes(c.key)}
                          onChange={e => {
                            let nuevas = columnasVisibles.length === 0 ? ventaCampos.map(col=>col.key) : [...columnasVisibles]
                            if (e.target.checked) {
                              if (!nuevas.includes(c.key)) nuevas.push(c.key)
                            } else {
                              nuevas = nuevas.filter(k => k !== c.key)
                            }
                            setColumnasVisibles(nuevas)
                          }}
                        />
                        {c.label}
                      </label>
                    ))}
                  </div>
                  <small style={{color:'#555'}}>Marca/desmarca para mostrar u ocultar columnas</small>
                </div>
              )}
            </div>
          </div>
        )}
        <div style={{overflowX:'auto'}}>
          <table style={{whiteSpace:'nowrap'}}>
            <thead>
              <tr style={{background:'#b3c6e0'}}>
                {ventas.length > 0 ? (columnasVisibles.length ? columnasVisibles : Object.keys(ventas[0])).map((col) => (
                  <th key={col}>{col}</th>
                )) : <th>ID</th>}
              </tr>
            </thead>
            <tbody>
              {ventas.length === 0 ? (
                <tr>
                  <td colSpan={1} style={{textAlign:'center',color:'#888',background:'#f6f8fa'}}>No hay ventas registradas para el filtro seleccionado.</td>
                </tr>
              ) : ventas
                .filter(v => ventaFiltros.every(f => !f.campo || f.valor === '' || v[f.campo] === f.valor))
                .map((v, i) => (
                  <tr key={i}>
                    {(columnasVisibles.length ? columnasVisibles : Object.keys(ventas[0])).map((col) => (
                      <td key={col}>{v[col]}</td>
                    ))}
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
