import { useState, useRef, useEffect } from 'react'
import { fetchWithAuth } from '../utils/fetchWithAuth'

type ConsultaResult = {
  format: 'table' | 'text' | 'chart'
  data: any
  metadata?: {
    title?: string
    description?: string
    chartType?: 'bar' | 'line' | 'pie'
    chartLabels?: string[]
    chartSeries?: Array<{ name: string; data: number[]; color?: string }>
  }
}

export default function ConsultaPage({ token, onLogout }: { token: string; onLogout?: () => void }) {
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ConsultaResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const response = await fetchWithAuth('/api/consulta/query', {
        token,
        onLogout,
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query: query.trim() }),
      })

      if (!response.ok) {
        let errorMessage = `Error ${response.status}`
        try {
          const errorData = await response.json()
          errorMessage = errorData.detail || errorData.message || errorMessage
        } catch {
          // Si no se puede parsear JSON, usar el texto de respuesta
          const text = await response.text().catch(() => '')
          errorMessage = text || errorMessage
        }
        throw new Error(errorMessage)
      }

      const data = await response.json()
      
      // Validar estructura de respuesta
      if (!data || typeof data !== 'object') {
        throw new Error('Respuesta inválida del servidor')
      }
      
      setResult(data)
    } catch (err: any) {
      setError(err.message || 'Error al procesar la consulta')
    } finally {
      setLoading(false)
    }
  }

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`
    }
  }, [query])

  return (
    <div style={{ width: '100%', padding: '2rem', maxWidth: '1200px', margin: '0 auto' }}>
      <h2 style={{ marginBottom: '1.5rem', color: '#163a63' }}>✨ Consulta con IA ✨</h2>
      <p style={{ marginBottom: '2rem', color: '#5b667a' }}>
        Haz preguntas sobre tus datos en lenguaje natural. Por ejemplo: "Dame las facturas de Amazon de los últimos 3 meses"
      </p>

      {/* Formulario de consulta */}
      <form onSubmit={handleSubmit} style={{ marginBottom: '2rem' }}>
        <div
          style={{
            background: '#fff',
            borderRadius: 12,
            boxShadow: '0 8px 20px #0001',
            padding: '1.5rem',
            marginBottom: '1rem',
          }}
        >
          <label
            htmlFor="consulta-input"
            style={{
              display: 'block',
              marginBottom: '0.75rem',
              fontWeight: 600,
              color: '#163a63',
            }}
          >
            Tu consulta:
          </label>
          <textarea
            ref={textareaRef}
            id="consulta-input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ejemplo: ¿Cuánto gasté en software este año?"
            disabled={loading}
            style={{
              width: '100%',
              minHeight: '120px',
              padding: '12px',
              borderRadius: 8,
              border: '1px solid #d1d5db',
              fontSize: '16px',
              fontFamily: 'inherit',
              resize: 'vertical',
              boxSizing: 'border-box',
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                handleSubmit(e)
              }
            }}
          />
          <div style={{ marginTop: '0.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <small style={{ color: '#6b7280' }}>
              Presiona Ctrl+Enter (o Cmd+Enter en Mac) para enviar
            </small>
            <button
              type="submit"
              disabled={loading || !query.trim()}
              style={{
                padding: '10px 24px',
                borderRadius: 8,
                border: 'none',
                background: loading || !query.trim() ? '#9ca3af' : '#2563eb',
                color: 'white',
                fontSize: '16px',
                fontWeight: 600,
                cursor: loading || !query.trim() ? 'not-allowed' : 'pointer',
                transition: 'background-color 0.2s',
              }}
              onMouseOver={(e) => {
                if (!loading && query.trim()) {
                  e.currentTarget.style.backgroundColor = '#1d4ed8'
                }
              }}
              onMouseOut={(e) => {
                if (!loading && query.trim()) {
                  e.currentTarget.style.backgroundColor = '#2563eb'
                }
              }}
            >
              {loading ? 'Procesando...' : 'Buscar'}
            </button>
          </div>
        </div>
      </form>

      {/* Estado de carga */}
      {loading && (
        <div
          style={{
            background: '#fff',
            borderRadius: 12,
            boxShadow: '0 8px 20px #0001',
            padding: '3rem',
            textAlign: 'center',
          }}
        >
          <div
            style={{
              display: 'inline-block',
              width: '40px',
              height: '40px',
              border: '4px solid #e5e7eb',
              borderTopColor: '#2563eb',
              borderRadius: '50%',
              animation: 'spin 1s linear infinite',
              marginBottom: '1rem',
            }}
          />
          <p style={{ color: '#6b7280', margin: 0 }}>Procesando tu consulta con IA...</p>
          <style>{`
            @keyframes spin {
              to { transform: rotate(360deg); }
            }
          `}</style>
        </div>
      )}

      {/* Error */}
      {error && (
        <div
          style={{
            background: '#fef2f2',
            border: '1px solid #fecaca',
            borderRadius: 12,
            padding: '1.5rem',
            marginBottom: '2rem',
          }}
        >
          <h3 style={{ margin: '0 0 0.5rem', color: '#dc2626' }}>Error</h3>
          <p style={{ margin: 0, color: '#991b1b' }}>{error}</p>
        </div>
      )}

      {/* Resultados */}
      {result && !loading && (
        <div
          style={{
            background: '#fff',
            borderRadius: 12,
            boxShadow: '0 8px 20px #0001',
            padding: '1.5rem',
          }}
        >
          {result.metadata?.title && (
            <h3 style={{ margin: '0 0 0.5rem', color: '#163a63' }}>{result.metadata.title}</h3>
          )}
          {result.metadata?.description && (
            <p style={{ margin: '0 0 1.5rem', color: '#5b667a' }}>{result.metadata.description}</p>
          )}

          {result.format === 'table' && <TableRenderer data={result.data} />}
          {result.format === 'text' && <TextRenderer data={result.data} />}
          {result.format === 'chart' && (
            <ChartRenderer
              data={result.data}
              chartType={result.metadata?.chartType || 'bar'}
              labels={result.metadata?.chartLabels}
              series={result.metadata?.chartSeries}
            />
          )}
        </div>
      )}
    </div>
  )
}

/** Renderizador de tabla */
function TableRenderer({ data }: { data: any[] }) {
  if (!data || data.length === 0) {
    return <p style={{ color: '#6b7280', textAlign: 'center', padding: '2rem' }}>No hay datos para mostrar</p>
  }

  const columns = Object.keys(data[0])

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'separate', borderSpacing: 0 }}>
        <thead>
          <tr style={{ background: '#f6f8fa', color: '#163a63' }}>
            {columns.map((col) => (
              <th
                key={col}
                style={{
                  padding: '10px 12px',
                  fontWeight: 700,
                  textAlign: 'left',
                  borderBottom: '1px solid #e5e7eb',
                }}
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr key={i} style={{ borderBottom: '1px solid #eef2f7' }}>
              {columns.map((col) => (
                <td
                  key={col}
                  style={{
                    padding: '10px 12px',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {typeof row[col] === 'number'
                    ? row[col].toLocaleString('es-ES', {
                        minimumFractionDigits: row[col] % 1 === 0 ? 0 : 2,
                        maximumFractionDigits: 2,
                      })
                    : String(row[col] ?? '')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Renderizador de texto */
function TextRenderer({ data }: { data: string | { text: string } }) {
  const text = typeof data === 'string' ? data : data?.text || ''
  return (
    <div
      style={{
        padding: '1.5rem',
        background: '#f9fafb',
        borderRadius: 8,
        lineHeight: '1.6',
        color: '#1f2937',
        whiteSpace: 'pre-wrap',
      }}
    >
      {text}
    </div>
  )
}

/** Renderizador de gráficas */
function ChartRenderer({
  data,
  chartType,
  labels,
  series,
}: {
  data: any
  chartType: 'bar' | 'line' | 'pie'
  labels?: string[]
  series?: Array<{ name: string; data: number[]; color?: string }>
}) {
  // Si viene data estructurada, usarla directamente
  if (labels && series && series.length > 0) {
    if (chartType === 'bar' && series.length <= 2) {
      // Gráfica de barras (reutilizar componente de DashboardPage)
      const maxValue = Math.max(
        1,
        ...series.flatMap((s) => s.data),
      )
      return (
        <div style={{ height: '400px' }}>
          <BarsChart
            labels={labels}
            seriesA={series[0]?.data || []}
            seriesB={series[1]?.data || []}
            maxValue={maxValue}
            seriesAColor={series[0]?.color}
            seriesBColor={series[1]?.color}
            seriesAName={series[0]?.name}
            seriesBName={series[1]?.name}
          />
        </div>
      )
    }
  }

  // Fallback: intentar parsear data como objeto
  if (data && typeof data === 'object') {
    // Si tiene estructura de gráfica
    if (data.labels && data.series) {
      const maxValue = Math.max(1, ...data.series.flatMap((s: any) => s.data || []))
      return (
        <div style={{ height: '400px' }}>
          <BarsChart
            labels={data.labels}
            seriesA={data.series[0]?.data || []}
            seriesB={data.series[1]?.data || []}
            maxValue={maxValue}
          />
        </div>
      )
    }
  }

  return (
    <div style={{ padding: '2rem', textAlign: 'center', color: '#6b7280' }}>
      Formato de gráfica no soportado o datos incompletos
    </div>
  )
}

/** Gráfica de barras (adaptada de DashboardPage) */
function BarsChart({
  labels,
  seriesA,
  seriesB,
  maxValue,
  height,
  seriesAColor,
  seriesBColor,
  seriesAName,
  seriesBName,
}: {
  labels: string[]
  seriesA: number[]
  seriesB?: number[]
  maxValue: number
  height?: number
  seriesAColor?: string
  seriesBColor?: string
  seriesAName?: string
  seriesBName?: string
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(600)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    const measure = () => {
      const w = Math.max(480, Math.round(el.clientWidth))
      setWidth((prev) => (prev !== w ? w : prev))
    }
    measure()

    const ro = new ResizeObserver(() => measure())
    ro.observe(el)

    window.addEventListener('resize', measure)
    return () => {
      ro.disconnect()
      window.removeEventListener('resize', measure)
    }
  }, [])

  const containerH = Math.max(260, Math.round(containerRef.current?.clientHeight ?? 300))
  const chartW = width
  const chartH = height ?? containerH

  const paddingX = 36
  const paddingTop = 12
  const paddingBottom = 28
  const innerW = chartW - paddingX * 2
  const innerH = chartH - paddingTop - paddingBottom

  const n = Math.max(1, labels.length)
  const groupW = innerW / n
  const barW = seriesB ? Math.max(10, (groupW - 12) / 2) : Math.max(20, groupW - 8)
  const scaleY = (v: number) => innerH * (v / maxValue)
  const yBase = chartH - paddingBottom

  const colorA = seriesAColor || '#2563eb'
  const colorB = seriesBColor || '#16a34a'

  return (
    <div>
      {(seriesAName || seriesBName) && (
        <div style={{ display: 'flex', gap: '1.25rem', marginBottom: '0.75rem' }}>
          {seriesAName && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span
                style={{
                  display: 'inline-block',
                  width: 12,
                  height: 12,
                  borderRadius: 2,
                  background: colorA,
                }}
              />
              <span style={{ fontSize: 14, color: '#334' }}>{seriesAName}</span>
            </div>
          )}
          {seriesBName && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span
                style={{
                  display: 'inline-block',
                  width: 12,
                  height: 12,
                  borderRadius: 2,
                  background: colorB,
                }}
              />
              <span style={{ fontSize: 14, color: '#334' }}>{seriesBName}</span>
            </div>
          )}
        </div>
      )}
      <div ref={containerRef} style={{ width: '100%', height: '100%' }}>
        <svg width={chartW} height={chartH} role="img" aria-label="Gráfica de barras">
          {/* Ejes */}
          <line x1={paddingX} y1={yBase} x2={chartW - paddingX} y2={yBase} stroke="#e2e8f0" />
          <line x1={paddingX} y1={paddingTop} x2={paddingX} y2={yBase} stroke="#e2e8f0" />

          {/* Barras */}
          {labels.map((lb, i) => {
            const x0 = paddingX + i * groupW
            const hA = scaleY(seriesA[i] || 0)
            const hB = seriesB ? scaleY(seriesB[i] || 0) : 0
            return (
              <g key={lb}>
                <rect
                  x={x0 + 2}
                  y={yBase - hA}
                  width={barW}
                  height={hA}
                  rx={3}
                  fill={colorA}
                  opacity={0.9}
                />
                {seriesB && (
                  <rect
                    x={x0 + 2 + barW + 6}
                    y={yBase - hB}
                    width={barW}
                    height={hB}
                    rx={3}
                    fill={colorB}
                    opacity={0.9}
                  />
                )}
                <text x={x0 + groupW / 2} y={chartH - 8} textAnchor="middle" fontSize="11" fill="#64748b">
                  {lb}
                </text>
              </g>
            )
          })}

          {/* Ticks horizontales */}
          {[0.25, 0.5, 0.75, 1].map((p) => {
            const y = yBase - innerH * p
            const val = maxValue * p
            return (
              <g key={p}>
                <line x1={paddingX} y1={y} x2={chartW - paddingX} y2={y} stroke="#eef2f7" />
                <text x={paddingX - 8} y={y + 4} textAnchor="end" fontSize="10" fill="#94a3b8">
                  {val.toLocaleString('es-ES', { maximumFractionDigits: 0 })}
                </text>
              </g>
            )
          })}
        </svg>
      </div>
    </div>
  )
}
