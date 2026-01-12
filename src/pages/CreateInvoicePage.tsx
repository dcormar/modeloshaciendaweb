import { useState, useEffect } from 'react'
import { fetchWithAuth } from '../utils/fetchWithAuth'

type Props = { token: string; onLogout?: () => void }

type InvoiceForm = {
  fecha_emision: string
  cliente_nombre: string
  cliente_nif: string
  cliente_direccion: string
  concepto: string
  base_imponible: string
  tipo_iva: string
  importe_iva: string
  total: string
  moneda: string
  notas: string
}

const initialForm: InvoiceForm = {
  fecha_emision: new Date().toISOString().split('T')[0],
  cliente_nombre: '',
  cliente_nif: '',
  cliente_direccion: '',
  concepto: '',
  base_imponible: '',
  tipo_iva: '21',
  importe_iva: '',
  total: '',
  moneda: 'EUR',
  notas: '',
}

const CURRENCY_CODES = [
  'EUR',
  'USD',
  'GBP',
  'JPY',
  'CHF',
  'CAD',
  'AUD',
  'NZD',
  'MXN',
  'BRL',
  'CNY',
  'SEK',
  'NOK',
  'DKK',
  'PLN',
  'CZK',
  'HUF',
  'INR',
  'ZAR',
]

export default function CreateInvoicePage({ token, onLogout }: Props) {
  const [form, setForm] = useState<InvoiceForm>(initialForm)
  const [errors, setErrors] = useState<Partial<Record<keyof InvoiceForm, string>>>({})
  const [submitting, setSubmitting] = useState(false)
  const [showSuccessModal, setShowSuccessModal] = useState(false)
  const [successMessage, setSuccessMessage] = useState<string>('')
  const [error, setError] = useState<string | null>(null)
  const [showAIModal, setShowAIModal] = useState(false)
  const [aiInput, setAiInput] = useState('')
  const [aiProcessing, setAiProcessing] = useState(false)

  // Calcular IVA y total automáticamente
  useEffect(() => {
    const base = parseFloat(form.base_imponible) || 0
    const tipoIva = parseFloat(form.tipo_iva) || 0

    if (base > 0 && tipoIva >= 0) {
      const iva = base * (tipoIva / 100)
      const total = base + iva

      setForm(prev => ({
        ...prev,
        importe_iva: iva.toFixed(2),
        total: total.toFixed(2),
      }))
    } else {
      setForm(prev => ({
        ...prev,
        importe_iva: '',
        total: '',
      }))
    }
  }, [form.base_imponible, form.tipo_iva])

  // Cerrar modales con Esc
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (showSuccessModal) {
          setShowSuccessModal(false)
        }
        if (showAIModal) {
          setShowAIModal(false)
          setAiInput('')
        }
      }
    }
    window.addEventListener('keydown', handleEsc)
    return () => window.removeEventListener('keydown', handleEsc)
  }, [showSuccessModal, showAIModal])

  const validate = (): boolean => {
    const newErrors: Partial<Record<keyof InvoiceForm, string>> = {}

    if (!form.fecha_emision.trim()) {
      newErrors.fecha_emision = 'La fecha de emisión es requerida'
    }

    if (!form.cliente_nombre.trim()) {
      newErrors.cliente_nombre = 'El nombre del cliente es requerido'
    }

    if (!form.cliente_nif.trim()) {
      newErrors.cliente_nif = 'El NIF/CIF del cliente es requerido'
    }

    if (!form.cliente_direccion.trim()) {
      newErrors.cliente_direccion = 'La dirección del cliente es requerida'
    }

    if (!form.concepto.trim()) {
      newErrors.concepto = 'El concepto es requerido'
    }

    if (!form.base_imponible.trim()) {
      newErrors.base_imponible = 'La base imponible es requerida'
    } else {
      const base = parseFloat(form.base_imponible)
      if (isNaN(base) || base <= 0) {
        newErrors.base_imponible = 'La base imponible debe ser un número mayor que 0'
      }
    }

    if (!form.tipo_iva.trim()) {
      newErrors.tipo_iva = 'El tipo de IVA es requerido'
    } else {
      const tipo = parseFloat(form.tipo_iva)
      if (isNaN(tipo) || tipo < 0 || tipo > 100) {
        newErrors.tipo_iva = 'El tipo de IVA debe ser un número entre 0 y 100'
      }
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    if (!validate()) {
      return
    }

    setSubmitting(true)

    try {
      const payload = {
        fecha_emision: form.fecha_emision,
        cliente_nombre: form.cliente_nombre.trim(),
        cliente_nif: form.cliente_nif.trim(),
        cliente_direccion: form.cliente_direccion.trim(),
        concepto: form.concepto.trim(),
        base_imponible: parseFloat(form.base_imponible),
        tipo_iva: parseFloat(form.tipo_iva),
        importe_iva: parseFloat(form.importe_iva),
        total: parseFloat(form.total),
        moneda: form.moneda,
        notas: form.notas.trim() || null,
      }

      const response = await fetchWithAuth('http://localhost:8000/generate-invoice/', {
        method: 'POST',
        token,
        onLogout,
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Error desconocido' }))
        throw new Error(errorData.detail || `Error ${response.status}`)
      }

      const data = await response.json()
      setSuccessMessage(`Factura creada exitosamente. Número de factura: ${data.numero_factura}`)
      setShowSuccessModal(true)
      setForm(initialForm)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al crear la factura')
    } finally {
      setSubmitting(false)
    }
  }

  const handleAIGenerate = async () => {
    if (!aiInput.trim()) {
      setError('Por favor, introduce la información de la factura')
      return
    }

    setAiProcessing(true)
    setError(null)

    try {
      const response = await fetchWithAuth('http://localhost:8000/generate-invoice/ai', {
        method: 'POST',
        token,
        onLogout,
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ texto: aiInput.trim() }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Error desconocido' }))
        throw new Error(errorData.detail || `Error ${response.status}`)
      }

      const data = await response.json()
      
      // Rellenar el formulario con los datos extraídos
      setForm({
        fecha_emision: data.fecha_emision || initialForm.fecha_emision,
        cliente_nombre: data.cliente_nombre || '',
        cliente_nif: data.cliente_nif || '',
        cliente_direccion: data.cliente_direccion || '',
        concepto: data.concepto || '',
        base_imponible: data.base_imponible ? String(data.base_imponible) : '',
        tipo_iva: data.tipo_iva ? String(data.tipo_iva) : '21',
        importe_iva: data.importe_iva ? String(data.importe_iva) : '',
        total: data.total ? String(data.total) : '',
        moneda: data.moneda || 'EUR',
        notas: data.notas || '',
      })

      setShowAIModal(false)
      setAiInput('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al procesar con IA')
    } finally {
      setAiProcessing(false)
    }
  }

  const handleChange = (
    field: keyof InvoiceForm,
    value: string
  ) => {
    setForm(prev => ({ ...prev, [field]: value }))
    // Limpiar error del campo cuando el usuario empieza a escribir
    if (errors[field]) {
      setErrors(prev => {
        const newErrors = { ...prev }
        delete newErrors[field]
        return newErrors
      })
    }
  }

  return (
    <div style={{ width: '100%', padding: '2rem', maxWidth: '800px', margin: '0 auto' }}>
      <h1 style={{ marginBottom: '2rem', color: '#163a63' }}>Crear Factura</h1>

      {error && (
        <div
          style={{
            padding: '1rem',
            marginBottom: '1.5rem',
            background: '#fef2f2',
            border: '1px solid #ef4444',
            borderRadius: '8px',
            color: '#991b1b',
          }}
        >
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div
          style={{
            background: '#fff',
            borderRadius: '12px',
            boxShadow: '0 8px 20px #0001',
            padding: '2rem',
          }}
        >
          <div style={{ display: 'grid', gap: '1.5rem' }}>
            {/* Fecha de emisión */}
            <div>
              <label
                htmlFor="fecha_emision"
                style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 600, color: '#374151' }}
              >
                Fecha de emisión <span style={{ color: '#ef4444' }}>*</span>
              </label>
              <input
                type="date"
                id="fecha_emision"
                value={form.fecha_emision}
                onChange={e => handleChange('fecha_emision', e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  border: errors.fecha_emision ? '2px solid #ef4444' : '1px solid #d1d5db',
                  borderRadius: '6px',
                  fontSize: '1rem',
                }}
              />
              {errors.fecha_emision && (
                <div style={{ color: '#ef4444', fontSize: '0.875rem', marginTop: '0.25rem' }}>
                  {errors.fecha_emision}
                </div>
              )}
            </div>

            {/* Cliente nombre */}
            <div>
              <label
                htmlFor="cliente_nombre"
                style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 600, color: '#374151' }}
              >
                Nombre del cliente <span style={{ color: '#ef4444' }}>*</span>
              </label>
              <input
                type="text"
                id="cliente_nombre"
                value={form.cliente_nombre}
                onChange={e => handleChange('cliente_nombre', e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  border: errors.cliente_nombre ? '2px solid #ef4444' : '1px solid #d1d5db',
                  borderRadius: '6px',
                  fontSize: '1rem',
                }}
              />
              {errors.cliente_nombre && (
                <div style={{ color: '#ef4444', fontSize: '0.875rem', marginTop: '0.25rem' }}>
                  {errors.cliente_nombre}
                </div>
              )}
            </div>

            {/* Cliente NIF */}
            <div>
              <label
                htmlFor="cliente_nif"
                style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 600, color: '#374151' }}
              >
                NIF/CIF del cliente <span style={{ color: '#ef4444' }}>*</span>
              </label>
              <input
                type="text"
                id="cliente_nif"
                value={form.cliente_nif}
                onChange={e => handleChange('cliente_nif', e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  border: errors.cliente_nif ? '2px solid #ef4444' : '1px solid #d1d5db',
                  borderRadius: '6px',
                  fontSize: '1rem',
                }}
              />
              {errors.cliente_nif && (
                <div style={{ color: '#ef4444', fontSize: '0.875rem', marginTop: '0.25rem' }}>
                  {errors.cliente_nif}
                </div>
              )}
            </div>

            {/* Cliente dirección - CAMBIADO A INPUT */}
            <div>
              <label
                htmlFor="cliente_direccion"
                style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 600, color: '#374151' }}
              >
                Dirección del cliente <span style={{ color: '#ef4444' }}>*</span>
              </label>
              <input
                type="text"
                id="cliente_direccion"
                value={form.cliente_direccion}
                onChange={e => handleChange('cliente_direccion', e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  border: errors.cliente_direccion ? '2px solid #ef4444' : '1px solid #d1d5db',
                  borderRadius: '6px',
                  fontSize: '1rem',
                }}
              />
              {errors.cliente_direccion && (
                <div style={{ color: '#ef4444', fontSize: '0.875rem', marginTop: '0.25rem' }}>
                  {errors.cliente_direccion}
                </div>
              )}
            </div>

            {/* Concepto */}
            <div>
              <label
                htmlFor="concepto"
                style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 600, color: '#374151' }}
              >
                Concepto/Descripción <span style={{ color: '#ef4444' }}>*</span>
              </label>
              <textarea
                id="concepto"
                value={form.concepto}
                onChange={e => handleChange('concepto', e.target.value)}
                rows={3}
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  border: errors.concepto ? '2px solid #ef4444' : '1px solid #d1d5db',
                  borderRadius: '6px',
                  fontSize: '1rem',
                  fontFamily: 'inherit',
                  resize: 'vertical',
                }}
              />
              {errors.concepto && (
                <div style={{ color: '#ef4444', fontSize: '0.875rem', marginTop: '0.25rem' }}>
                  {errors.concepto}
                </div>
              )}
            </div>

            {/* Base imponible y Tipo IVA en la misma fila */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <div>
                <label
                  htmlFor="base_imponible"
                  style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 600, color: '#374151' }}
                >
                  Base imponible (€) <span style={{ color: '#ef4444' }}>*</span>
                </label>
                <input
                  type="number"
                  id="base_imponible"
                  step="0.01"
                  min="0"
                  value={form.base_imponible}
                  onChange={e => handleChange('base_imponible', e.target.value)}
                  style={{
                    width: '100%',
                    padding: '0.75rem',
                    border: errors.base_imponible ? '2px solid #ef4444' : '1px solid #d1d5db',
                    borderRadius: '6px',
                    fontSize: '1rem',
                  }}
                />
                {errors.base_imponible && (
                  <div style={{ color: '#ef4444', fontSize: '0.875rem', marginTop: '0.25rem' }}>
                    {errors.base_imponible}
                  </div>
                )}
              </div>

              <div>
                <label
                  htmlFor="tipo_iva"
                  style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 600, color: '#374151' }}
                >
                  Tipo de IVA (%) <span style={{ color: '#ef4444' }}>*</span>
                </label>
                <input
                  type="number"
                  id="tipo_iva"
                  step="0.01"
                  min="0"
                  max="100"
                  value={form.tipo_iva}
                  onChange={e => handleChange('tipo_iva', e.target.value)}
                  placeholder="21"
                  style={{
                    width: '100%',
                    padding: '0.75rem',
                    border: errors.tipo_iva ? '2px solid #ef4444' : '1px solid #d1d5db',
                    borderRadius: '6px',
                    fontSize: '1rem',
                  }}
                />
                {errors.tipo_iva && (
                  <div style={{ color: '#ef4444', fontSize: '0.875rem', marginTop: '0.25rem' }}>
                    {errors.tipo_iva}
                  </div>
                )}
              </div>
            </div>

            {/* Importe IVA y Total en la misma fila */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <div>
                <label
                  htmlFor="importe_iva"
                  style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 600, color: '#374151' }}
                >
                  Importe de IVA (€)
                </label>
                <input
                  type="number"
                  id="importe_iva"
                  step="0.01"
                  value={form.importe_iva}
                  onChange={e => handleChange('importe_iva', e.target.value)}
                  readOnly
                  style={{
                    width: '100%',
                    padding: '0.75rem',
                    border: '1px solid #d1d5db',
                    borderRadius: '6px',
                    fontSize: '1rem',
                    background: '#f3f4f6',
                    cursor: 'not-allowed',
                  }}
                />
              </div>

              <div>
                <label
                  htmlFor="total"
                  style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 600, color: '#374151' }}
                >
                  Total (€)
                </label>
                <input
                  type="number"
                  id="total"
                  step="0.01"
                  value={form.total}
                  onChange={e => handleChange('total', e.target.value)}
                  readOnly
                  style={{
                    width: '100%',
                    padding: '0.75rem',
                    border: '1px solid #d1d5db',
                    borderRadius: '6px',
                    fontSize: '1rem',
                    background: '#f3f4f6',
                    cursor: 'not-allowed',
                    fontWeight: 600,
                  }}
                />
              </div>
            </div>

            {/* Moneda */}
            <div>
              <label
                htmlFor="moneda"
                style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 600, color: '#374151' }}
              >
                Moneda
              </label>
              <select
                id="moneda"
                value={form.moneda}
                onChange={e => handleChange('moneda', e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  border: '1px solid #d1d5db',
                  borderRadius: '6px',
                  fontSize: '1rem',
                }}
              >
                {CURRENCY_CODES.map(code => (
                  <option key={code} value={code}>
                    {code}
                  </option>
                ))}
              </select>
            </div>

            {/* Notas */}
            <div>
              <label
                htmlFor="notas"
                style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 600, color: '#374151' }}
              >
                Notas/Observaciones
              </label>
              <textarea
                id="notas"
                value={form.notas}
                onChange={e => handleChange('notas', e.target.value)}
                rows={3}
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  border: '1px solid #d1d5db',
                  borderRadius: '6px',
                  fontSize: '1rem',
                  fontFamily: 'inherit',
                  resize: 'vertical',
                }}
              />
            </div>
          </div>

          {/* Botones */}
          <div style={{ marginTop: '2rem', display: 'flex', justifyContent: 'flex-end', gap: '1rem' }}>
            <button
              type="button"
              onClick={() => setShowAIModal(true)}
              style={{
                padding: '0.75rem 2rem',
                background: '#10b981',
                color: '#fff',
                border: 'none',
                borderRadius: '6px',
                fontSize: '1rem',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Generar por IA
            </button>
            <button
              type="submit"
              disabled={submitting}
              style={{
                padding: '0.75rem 2rem',
                background: submitting ? '#9ca3af' : '#163a63',
                color: '#fff',
                border: 'none',
                borderRadius: '6px',
                fontSize: '1rem',
                fontWeight: 600,
                cursor: submitting ? 'not-allowed' : 'pointer',
              }}
            >
              {submitting ? 'Generando...' : 'Generar manualmente'}
            </button>
          </div>
        </div>
      </form>

      {/* Modal de éxito */}
      {showSuccessModal && (
        <div
          className="fixed inset-0 bg-black/40 flex items-center justify-center z-50"
          onClick={() => setShowSuccessModal(false)}
        >
          <div
            className="bg-white rounded-2xl p-6 w-full max-w-md shadow-xl border border-gray-100 text-center"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-lg font-semibold text-gray-900 mb-3">
              ✅ Factura creada exitosamente
            </h2>
            <p className="text-gray-700 text-sm mb-6">
              {successMessage}
            </p>
            <button
              onClick={() => setShowSuccessModal(false)}
              className="px-4 py-2 bg-blue-700 text-white rounded-lg hover:bg-blue-800"
            >
              Cerrar
            </button>
          </div>
        </div>
      )}

      {/* Modal de IA */}
      {showAIModal && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
          style={{ paddingTop: '80px' }}
          onClick={(e) => {
            if (e.target === e.currentTarget) {
              setShowAIModal(false)
              setAiInput('')
            }
          }}
        >
          <div
            className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[calc(90vh-80px)] overflow-hidden flex flex-col"
            style={{
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
            }}
          >
            {/* Header */}
            <div className="flex items-center justify-between p-6 border-b border-gray-200">
              <h2
                className="text-2xl font-bold"
                style={{
                  background: 'linear-gradient(135deg, #3631a3 0%, #092342 100%)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                  backgroundClip: 'text',
                }}
              >
                Generar factura por IA
              </h2>
              <button
                onClick={() => {
                  setShowAIModal(false)
                  setAiInput('')
                }}
                className="text-gray-400 hover:text-gray-600 transition-colors"
                style={{
                  fontSize: '24px',
                  lineHeight: '1',
                  padding: '4px',
                  cursor: 'pointer',
                }}
                aria-label="Cerrar"
              >
                ×
              </button>
            </div>

            {/* Contenido */}
            <div className="overflow-y-auto p-6" style={{ maxHeight: 'calc(90vh - 200px)' }}>
              <p className="text-sm text-gray-600 mb-4">
                Introduce la información de la factura en texto libre. La IA extraerá automáticamente los campos necesarios.
              </p>
              <textarea
                value={aiInput}
                onChange={(e) => setAiInput(e.target.value)}
                placeholder="Ejemplo: Factura emitida el 15/03/2024 a la empresa ABC S.L. con NIF B12345678, ubicada en Calle Mayor 1, Madrid. Concepto: Servicios de consultoría. Base imponible: 1000€, IVA 21%, total 1210€..."
                rows={10}
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  border: '1px solid #d1d5db',
                  borderRadius: '8px',
                  fontSize: '0.95rem',
                  fontFamily: 'inherit',
                  resize: 'vertical',
                }}
              />
            </div>

            {/* Footer con botón */}
            <div className="flex items-center justify-end gap-3 p-6 border-t border-gray-200">
              <button
                onClick={() => {
                  setShowAIModal(false)
                  setAiInput('')
                }}
                className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
              >
                Cancelar
              </button>
              <button
                onClick={handleAIGenerate}
                disabled={aiProcessing || !aiInput.trim()}
                className="px-4 py-2 bg-blue-700 text-white rounded-lg hover:bg-blue-800 disabled:bg-gray-400 disabled:cursor-not-allowed"
              >
                {aiProcessing ? 'Procesando...' : '🪄 Generar'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
