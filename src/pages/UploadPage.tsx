import React, { useRef, useState, useEffect } from "react";

type Props = { token: string | null };
type DocType = "factura" | "venta";

/** Ahora refleja el shape de /uploads/historico */
type Operacion = {
  id: string;
  fecha: string;                  // ISO (timestamptz)
  tipo: "FACTURA" | "VENTA";
  descripcion: string;
  tam_bytes?: number | null;      // puede venir null
  storage_path?: string | null;
};

const ALLOWED_TYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
];

export default function UploadPage({ token }: Props) {
  const [docType, setDocType] = useState<DocType | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [uploading, setUploading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const [showSuccess, setShowSuccess] = useState(false)

  // ====== HISTÓRICO (ahora de uploads) ======
  const [ops, setOps] = useState<Operacion[]>([]);
  const [opsError, setOpsError] = useState<string | null>(null);

  useEffect(() => {
    fetch("http://localhost:8000/api/uploads/historico?limit=20", {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    })
      .then(r => (r.ok ? r.json() : Promise.reject("Error cargando histórico")))
      .then(data => setOps(data.items || []))
      .catch(e => setOpsError(typeof e === "string" ? e : "Error desconocido"));
  }, [token]);
  // ==========================================

  const onFile = (f: File | null) => {
    if (!f) return;
    const name = f.name.toLowerCase();
    if (
      !ALLOWED_TYPES.includes(f.type) &&
      !name.endsWith(".xlsx") &&
      !name.endsWith(".pdf")
    ) {
      alert("Solo se admiten PDF o XLSX");
      return;
    }
    setFile(f);
  };

  const handleDrop: React.DragEventHandler<HTMLDivElement> = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);
    onFile(e.dataTransfer.files?.[0] ?? null);
  };

  const startUpload = () => {
    if (!token) return alert("Sesión caducada. Inicia sesión de nuevo.");
    if (!file) return alert("Selecciona un PDF o XLSX");
    if (!docType) return alert("Selecciona si es Factura o Venta");
    setShowConfirm(true);
  };

  const confirmUpload = async () => {
    if (!file || !token || !docType) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("tipo", docType); // FastAPI espera 'tipo'

      const res = await fetch("/api/upload/", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      });
      if (!res.ok) throw new Error(await res.text());

      setShowConfirm(false);
      setFile(null);
      setShowSuccess(true);

      // refrescar histórico de uploads tras una subida exitosa
      fetch("http://localhost:8000/api/uploads/historico?limit=20", {
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      })
        .then(r => (r.ok ? r.json() : Promise.reject("Error cargando histórico")))
        .then(data => setOps(data.items || []))
        .catch(() => {});
    } catch (err: any) {
      alert("Error subiendo el archivo: " + (err?.message ?? String(err)));
    } finally {
      setUploading(false);
    }
  };

  // ← control de deshabilitado de la dropzone (muestra siempre, pero sin interacción)
  const disabled = !docType;

  return (
    <div className="max-w-3xl mx-auto">
      <div className="rounded-2xl shadow-soft bg-white/80 backdrop-blur p-6 border border-gray-100">
        <h1
          className="text-2xl font-semibold text-center text-gray-900"
          style={{ marginBottom: 32 }}
          >
          Subir factura o fichero de ventas
        </h1>

        {/* Selector tipo */}
        <div className="text-center mb-3 text-sm text-gray-600">
          Selecciona el tipo de fichero a subir
        </div>
        <div
          className="flex items-center justify-center gap-4 mb-6"
          style={{ marginBottom: 8 }}   // reduce el espacio antes del dropzone
        >
          <button
            type="button"
            className={`seg-option ${docType === "factura" ? "seg-selected" : ""}`}
            style={{ marginRight: "6px" }}
            onClick={() => setDocType("factura")}
          >
            Factura
          </button>
          <button
            type="button"
            className={`seg-option ${docType === "venta" ? "seg-selected" : ""}`}
            style={{ marginLeft: "6px" }}
            onClick={() => setDocType("venta")}
          >
            Venta
          </button>
        </div>

        {/* input oculto (siempre) */}
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.xlsx,application/pdf,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          style={{ display: "none" }}
          onChange={(e) => onFile(e.target.files?.[0] ?? null)}
        />

        {/* Dropzone SIEMPRE visible; deshabilitada si no se ha elegido tipo */}
        <div
          onDragOver={(e) => {
            if (disabled) return;
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => {
            if (disabled) return;
            setDragOver(false);
          }}
          onDrop={(e) => {
            if (disabled) return;
            handleDrop(e);
          }}
          onClick={() => {
            if (disabled) return;
            inputRef.current?.click();
          }}
          style={{
            maxWidth: 720,
            margin: "12px auto 32px",
            background: "#fff",
            border: `2px dashed ${dragOver && !disabled ? "#1d4ed8" : "#cbd5e1"}`,
            borderRadius: 12,
            minHeight: 420,
            padding: 40,
            textAlign: "center" as const,
            cursor: disabled ? "not-allowed" : "pointer",
            opacity: disabled ? 0.5 : 1,
            filter: disabled ? "grayscale(0.1)" : "none",
            boxShadow: dragOver && !disabled ? "0 6px 20px rgba(29,78,216,.15)" : "none",
            transition:
              "border-color 120ms ease, box-shadow 120ms ease, opacity 120ms ease",
            position: "relative",
          }}
        >
          {/* Overlay informativo cuando está deshabilitado */}
          {disabled && (
            <div
              style={{
                color: "#1f2937",                 // gris más oscuro
                fontWeight: 700,                  // más grueso
                fontSize: "1rem",
                background: "rgba(255,255,255,0.85)", // resalta sobre el fondo
                padding: "12px 16px",
                borderRadius: 8,
                textAlign: "center",
              }}
            >
              Elige <strong style={{ color: "#1d4ed8" }}>Factura</strong> <br />
              o <strong style={{ color: "#1d4ed8" }}>Venta</strong> para habilitar
            </div>
          )}

          <p style={{ fontWeight: 600, color: "#111827", margin: "4px 0 6px" }}>
            Arrastra y suelta un archivo aquí
          </p>
          <p style={{ color: "#6b7280", fontSize: "0.95rem", margin: 0 }}>
            o haz clic para seleccionar un PDF o XLSX
          </p>

          {file && (
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                padding: "6px 10px",
                borderRadius: 999,
                background: "#eff6ff",
                color: "#1e40af",
                border: "1px solid #bfdbfe",
                fontSize: ".9rem",
                marginTop: 14,
              }}
            >
              <span
                className="font-medium"
                title={file.name}
                style={{
                  maxWidth: 240,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {file.name}
              </span>
              <span style={{ opacity: 0.7 }}>
                {Math.round(file.size / 1024)} KB
              </span>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  if (disabled) return;
                  setFile(null);
                }}
                aria-label="Quitar archivo"
                title="Quitar archivo"
                style={{
                  background: "transparent",
                  border: 0,
                  fontSize: 16,
                  cursor: disabled ? "not-allowed" : "pointer",
                  color: "inherit",
                }}
              >
                ×
              </button>
            </div>
          )}
        </div>

        {/* CTA Subir: solo si hay archivo y tipo seleccionado */}
        <div className="flex justify-center mt-6" style={{ minHeight: 60 }}>
          {file && !disabled && (
            <button
              onClick={startUpload}
              disabled={uploading}
              className={`seg-option ${
                uploading ? "opacity-50 cursor-not-allowed" : "seg-selected"
              }`}
              style={{ opacity: uploading ? 0.6 : 1 }}
            >
              {uploading ? "Subiendo…" : "Subir"}
            </button>
          )}
        </div>
      </div>
      
      {/* Modal confirmación */}
      {showConfirm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-6 w-full max-w-md shadow-xl border border-gray-100">
            <h2 className="text-lg font-semibold mb-2 text-gray-900">
              Confirmar subida
            </h2>
            <p className="text-sm text-gray-700">
              Vas a subir <strong>{file?.name}</strong> como{" "}
              <strong>{docType}</strong>. ¿Confirmas?
            </p>
            <div className="mt-6 flex justify-end gap-4">
              <button
                className="modal-btn modal-btn-cancel"
                onClick={() => setShowConfirm(false)}
                disabled={uploading}
                style={{ marginRight: "6px" }}
              >
                Cancelar
              </button>
              <button
                className="modal-btn modal-btn-confirm"
                onClick={confirmUpload}
                disabled={uploading}
                style={{ marginLeft: "6px" }}
              >
                Confirmar
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Modal de éxito */}
      {showSuccess && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-6 w-full max-w-md shadow-xl border border-gray-100 text-center">
            <h2 className="text-lg font-semibold text-gray-900 mb-3">
              ✅ Archivo subido correctamente
            </h2>
            <p className="text-gray-700 text-sm mb-6">
              Tu archivo se ha guardado y será procesado en breve.
            </p>
            <button
              onClick={() => setShowSuccess(false)}
              className="px-4 py-2 bg-blue-700 text-white rounded-lg hover:bg-blue-800"
            >
              Cerrar
            </button>
          </div>
        </div>
      )}
      {/* ========= Histórico de ficheros subidos ========= */}
      <section
        style={{
          background: "#fff",
          borderRadius: 12,
          boxShadow: "0 8px 20px #0001",
          padding: "1.5rem",
          marginTop: "2rem",
        }}
      >
        <h3 style={{ margin: 0, color: "#163a63", textAlign: "center" }}>
          Histórico de ficheros subidos
        </h3>
        <p style={{ margin: "0.25rem 0 1rem", color: "#5b667a", textAlign: "center" }}>
          Facturas (1:1) y ventas (por lote)
        </p>

        {opsError && (
          <div style={{ color: "red", marginBottom: "0.75rem" }}>{opsError}</div>
        )}

        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "separate", borderSpacing: 0 }}>
            <thead>
              <tr style={{ background: "#f6f8fa", color: "#163a63" }}>
                <th style={{ ...th, textAlign: "center" }}>Fecha</th>
                <th style={{ ...th, textAlign: "center" }}>Tipo</th>
                <th style={{ ...th, textAlign: "center" }}>Descripción</th>
                <th style={{ ...th, textAlign: "right" }}>Tamaño (KB)</th>
              </tr>
            </thead>
            <tbody>
              {ops.map((op) => (
                <tr key={op.id} style={{ borderBottom: "1px solid #eef2f7" }}>
                  <td style={{ ...td, textAlign: "center" }}>
                    {new Date(op.fecha).toLocaleString("es-ES")}
                  </td>
                  <td style={{ ...td, textAlign: "center" }}>
                    <span
                      style={{
                        fontSize: 12,
                        padding: "2px 8px",
                        borderRadius: 999,
                        background: op.tipo === "FACTURA" ? "#eef2ff" : "#ecfdf5",
                        color: op.tipo === "FACTURA" ? "#3730a3" : "#065f46",
                        fontWeight: 600,
                      }}
                    >
                      {op.tipo}
                    </span>
                  </td>
                  <td style={td}>{op.descripcion}</td>
                  <td
                    style={{
                      ...td,
                      textAlign: "right",
                      fontVariantNumeric: "tabular-nums",
                    }}
                  >
                    {op.tam_bytes != null ? (op.tam_bytes / 1024).toFixed(0) : "-"}
                  </td>
                </tr>
              ))}
              {ops.length === 0 && !opsError && (
                <tr>
                  <td
                    colSpan={4}
                    style={{ ...td, textAlign: "center", color: "#667085" }}
                  >
                    Sin subidas recientes.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
      {/* =============================================== */}
    </div>
  );
}

/* estilos tabla histórico (mismos que dashboard) */
const th: React.CSSProperties = {
  padding: "10px 12px",
  fontWeight: 700,
  textAlign: "left",
  borderBottom: "1px solid #e5e7eb",
};
const td: React.CSSProperties = {
  padding: "10px 12px",
  whiteSpace: "nowrap",
};