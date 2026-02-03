import React, { useRef, useState, useEffect } from "react";
import { UPLOAD_DELAY_MS } from "../config";
import { sleep } from "../utils/sleep"; // o define el helper en el mismo archivo
import { fetchWithAuth } from "../utils/fetchWithAuth";

type Props = { token: string | null; onLogout?: () => void };
type DocType = "factura" | "venta";

/** /api/uploads/historico */
type UploadStatus =
  | "UPLOADED"
  | "QUEUED"
  | "PROCESSING"
  | "PROCESSING_AI"
  | "AI_COMPLETED"
  | "UPLOADING_DRIVE"
  | "PROCESSED"
  | "COMPLETED"
  | "FAILED"
  | "FAILED_AI"
  | "FAILED_DRIVE";

/** Información del duplicado detectado */
type DuplicateInfo = {
  existing: {
    id: string;
    filename: string;
    uploaded_at: string;
    status: string;
  };
  factura: {
    id_factura: string;
    importe_total_euro: number | null;
    fecha: string;
  } | null;
  temp_file: string;
};

type Operacion = {
  id: string;
  fecha: string;
  tipo: "FACTURA" | "VENTA";
  original_filename: string;
  descripcion: string;
  tam_bytes?: number | null;
  storage_path?: string | null;
  status?: UploadStatus | null;
};

/** Estados del flujo de procesamiento paso a paso */
type ProcessingStep = 
  | "idle" 
  | "confirm_ai" 
  | "processing_ai" 
  | "confirm_drive" 
  | "uploading_drive" 
  | "completed" 
  | "error";

/** Datos extraídos por la IA */
type AIData = {
  id_factura?: string;
  fecha?: string;
  proveedor?: string;
  proveedor_vat?: string;
  importe_sin_iva?: number;
  iva_porcentaje?: number;
  importe_total?: number;
  moneda?: string;
  tipo_cambio?: number;
  pais_origen?: string;
  categoria?: string;
  descripcion?: string;
  [key: string]: any;
};

const ALLOWED_TYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
];

// ===== formulario manual =====
type ManualForm = {
  fecha: string;
  proveedor: string;
  total: string;
  categoria: string;
  importe_sin_iva_local: string;
  iva_local: string;
  total_moneda_local: string;
  moneda: string;
  tarifa_cambio: string;
  importe_sin_iva_euro: string;
  importe_total_euro: string;
  pais_origen: string;
  notas: string;
  descripcion: string;
  id_ext: string;
  fecha_dt: string;
  supplier_vat_number: string;
  ubicacion_factura: string;
};

const initialManualForm: ManualForm = {
  fecha: new Date().toISOString().split('T')[0], // Fecha de hoy en formato YYYY-MM-DD
  proveedor: "",
  total: "",
  categoria: "",
  importe_sin_iva_local: "",
  iva_local: "",
  total_moneda_local: "",
  moneda: "EUR",
  tarifa_cambio: "",
  importe_sin_iva_euro: "",
  importe_total_euro: "",
  pais_origen: "ES",
  notas: "",
  descripcion: "",
  id_ext: "",
  fecha_dt: new Date().toISOString().split('T')[0],
  supplier_vat_number: "",
  ubicacion_factura: "tbd",
};

// Lista abreviada de monedas y países (puedes ampliarla)
const CURRENCY_CODES = [
  "EUR",
  "USD",
  "GBP",
  "JPY",
  "CHF",
  "CAD",
  "AUD",
  "NZD",
  "MXN",
  "BRL",
  "CNY",
  "SEK",
  "NOK",
  "DKK",
  "PLN",
  "CZK",
  "HUF",
  "INR",
  "ZAR",
];

const COUNTRY_CODES = [
  "ES",
  "FR",
  "DE",
  "IT",
  "PT",
  "NL",
  "BE",
  "IE",
  "GB",
  "US",
  "CA",
  "MX",
  "BR",
  "AR",
  "CL",
  "CN",
  "JP",
  "AU",
  "NZ",
  "SE",
  "NO",
  "DK",
];

export default function UploadPage({ token, onLogout }: Props) {
  const [docType, setDocType] = useState<DocType | null>(null);

  // 🔄 multi-archivo
  const [files, setFiles] = useState<File[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadingIndex, setUploadingIndex] = useState<number | null>(null);

  const inputRef = useRef<HTMLInputElement>(null);
  const [showSuccess, setShowSuccess] = useState(false);
  
  // Modal de detalles
  const [selectedOp, setSelectedOp] = useState<Operacion | null>(null);
  const [showDetailsModal, setShowDetailsModal] = useState(false);
  const [facturaData, setFacturaData] = useState<any | null>(null);
  const [facturaId, setFacturaId] = useState<number | null>(null);
  const [loadingFactura, setLoadingFactura] = useState(false);
  const [facturaError, setFacturaError] = useState<string | null>(null);

  // overlay formulario manual
  const [showManualModal, setShowManualModal] = useState(false);
  const [showTypeSelectionModal, setShowTypeSelectionModal] = useState(false);
  const [manualForm, setManualForm] = useState<ManualForm>(initialManualForm);
  const [manualFile, setManualFile] = useState<File | null>(null);
  const manualFileInputRef = useRef<HTMLInputElement>(null);

  // ====== FLUJO PASO A PASO ======
  const [processingStep, setProcessingStep] = useState<ProcessingStep>("idle");
  const [currentUploadId, setCurrentUploadId] = useState<string | null>(null);
  const [currentFileName, setCurrentFileName] = useState<string | null>(null);
  const [aiResult, setAiResult] = useState<AIData | null>(null);
  const [driveUrl, setDriveUrl] = useState<string | null>(null);
  const [processingError, setProcessingError] = useState<string | null>(null);
  const [pendingFiles, setPendingFiles] = useState<Array<{file: File, uploadId: string}>>([]);
  const [currentFileIndex, setCurrentFileIndex] = useState(0);

  // ====== DUPLICADO ======
  const [showDuplicateModal, setShowDuplicateModal] = useState(false);
  const [duplicateInfo, setDuplicateInfo] = useState<DuplicateInfo | null>(null);
  const [pendingDuplicateFile, setPendingDuplicateFile] = useState<File | null>(null);
  const [duplicateProcessing, setDuplicateProcessing] = useState(false);

  // ====== MODAL SELECCIÓN DE TIPO ======
  const [showTypeSelectModal, setShowTypeSelectModal] = useState(false);
  const [pendingDropFiles, setPendingDropFiles] = useState<File[]>([]);

  console.log("⏱️ Delay entre subidas configurado:", UPLOAD_DELAY_MS, "ms");

  // ====== HISTÓRICO (uploads) ======
  const [ops, setOps] = useState<Operacion[]>([]);
  const [opsError, setOpsError] = useState<string | null>(null);
  const [sortColumn, setSortColumn] = useState<string>("fecha");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("desc");
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [totalRecords, setTotalRecords] = useState<number>(0);
  const [totalPages, setTotalPages] = useState<number>(1);
  const pageSize = 20;

  const loadHistorico = () => {
    const offset = (currentPage - 1) * pageSize;
    const url = `/api/uploads/historico?limit=${pageSize}&offset=${offset}&order_by=${sortColumn}&order_dir=${sortDirection}`;
    
    fetchWithAuth(url, {
      token: token || undefined,
      onLogout,
    })
      .then((r) => (r.ok ? r.json() : Promise.reject("Error cargando histórico")))
      .then((data) => {
        console.debug("Respuesta /api/uploads/historico:", data);
        setOps(data.items || []);
        setTotalRecords(data.total || 0);
        setTotalPages(data.total_pages || 1);
      })
      .catch((e) =>
        setOpsError(typeof e === "string" ? e : "Error desconocido"),
      );
  };

  const handleSort = (column: string) => {
    if (sortColumn === column) {
      // Si ya está ordenando por esta columna, cambiar dirección
      setSortDirection(sortDirection === "asc" ? "desc" : "asc");
    } else {
      // Nueva columna, empezar con desc
      setSortColumn(column);
      setSortDirection("desc");
    }
    setCurrentPage(1); // Resetear a primera página al cambiar ordenamiento
  };

  const handlePageChange = (newPage: number) => {
    if (newPage >= 1 && newPage <= totalPages) {
      setCurrentPage(newPage);
    }
  };

  useEffect(() => {
    loadHistorico();
  }, [token, currentPage, sortColumn, sortDirection]);
  // ==================================

  // Helpers multi-archivo
  const isAllowed = (f: File) => {
    const name = f.name.toLowerCase();
    return (
      ALLOWED_TYPES.includes(f.type) ||
      name.endsWith(".pdf") ||
      name.endsWith(".xlsx")
    );
  };

  const addFiles = (list: FileList | File[]) => {
    const incoming = Array.from(list);
    const valid = incoming.filter(isAllowed);
    if (valid.length !== incoming.length) {
      alert("Algunos archivos fueron ignorados (solo PDF o XLSX).");
    }
    // dedupe por nombre+tamaño
    const dedup = [...files];
    for (const f of valid) {
      const exists = dedup.some((d) => d.name === f.name && d.size === f.size);
      if (!exists) dedup.push(f);
    }
    setFiles(dedup);
  };

  const removeFile = (name: string, size: number) => {
    setFiles((prev) => prev.filter((f) => !(f.name === name && f.size === size)));
  };

  const clearFiles = () => setFiles([]);

  // Eventos
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files?.length) return;
    
    // Si no hay tipo seleccionado, mostrar modal para elegir
    if (!docType) {
      const incoming = Array.from(e.target.files);
      const valid = incoming.filter(isAllowed);
      if (valid.length > 0) {
        setPendingDropFiles(valid);
        setShowTypeSelectModal(true);
      } else {
        alert("Algunos archivos fueron ignorados (solo PDF o XLSX).");
      }
    } else {
      addFiles(e.target.files);
    }
    // permite volver a seleccionar el mismo archivo si se borra
    e.target.value = "";
  };

  const handleDrop: React.DragEventHandler<HTMLDivElement> = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);
    
    if (!e.dataTransfer.files?.length) return;
    
    // Si no hay tipo seleccionado, mostrar modal para elegir
    if (!docType) {
      const incoming = Array.from(e.dataTransfer.files);
      const valid = incoming.filter(isAllowed);
      if (valid.length > 0) {
        setPendingDropFiles(valid);
        setShowTypeSelectModal(true);
      } else {
        alert("Algunos archivos fueron ignorados (solo PDF o XLSX).");
      }
      return;
    }
    
    addFiles(e.dataTransfer.files);
  };

  /** Maneja la selección de tipo desde el modal */
  const handleTypeSelect = (type: DocType) => {
    setDocType(type);
    setShowTypeSelectModal(false);
    // Añadir los archivos pendientes
    if (pendingDropFiles.length > 0) {
      // dedupe por nombre+tamaño
      const dedup = [...files];
      for (const f of pendingDropFiles) {
        const exists = dedup.some((d) => d.name === f.name && d.size === f.size);
        if (!exists) dedup.push(f);
      }
      setFiles(dedup);
      setPendingDropFiles([]);
    }
  };

  const startUpload = () => {
    if (!token) return alert("Sesión caducada. Inicia sesión de nuevo.");
    if (!docType) return alert("Selecciona si es Factura o Venta");
    if (files.length === 0) return alert("Selecciona al menos un archivo");
    setShowConfirm(true);
  };

  const confirmUpload = async (forceUpload = false) => {
    if (!token || !docType || files.length === 0) return;
    setUploading(true);
    setUploadingIndex(0);
    
    // Para facturas, recopilamos los upload_ids para el flujo paso a paso
    const uploadedFiles: Array<{file: File, uploadId: string}> = [];
    
    try {
      // Secuencial: subir todos los archivos primero
      for (let i = 0; i < files.length; i++) {
        setUploadingIndex(i);
        const fd = new FormData();
        fd.append("file", files[i]);
        fd.append("tipo", docType);
        fd.append("force", forceUpload ? "true" : "false");
        const res = await fetchWithAuth("/api/upload/", {
          method: "POST",
          token: token || undefined,
          onLogout,
          body: fd,
        });
        
        // Manejar duplicado (409)
        if (res.status === 409) {
          const data = await res.json();
          if (data.error === "duplicate_hash") {
            // Mostrar modal de duplicado
            setDuplicateInfo(data);
            setPendingDuplicateFile(files[i]);
            setShowDuplicateModal(true);
            setShowConfirm(false);
            setUploading(false);
            setUploadingIndex(null);
            // Guardar los archivos restantes para continuar después
            const remainingFiles = files.slice(i + 1);
            setFiles(remainingFiles);
            return;
          }
        }
        
        if (!res.ok) {
          const t = await res.text();
          console.error(`Fallo subiendo ${files[i].name}:`, t);
          alert(`Fallo subiendo ${files[i].name}: ${t}`);
          continue;
        }
        
        const result = await res.json();
        
        // Para facturas, guardar el upload_id para el procesamiento paso a paso
        if (docType === "factura" && result.upload_id) {
          uploadedFiles.push({ file: files[i], uploadId: result.upload_id });
        }
        
        loadHistorico();
        if (UPLOAD_DELAY_MS > 0) {
          await sleep(UPLOAD_DELAY_MS);
        }
      }
      
      // Para facturas: iniciar el flujo paso a paso
      if (docType === "factura" && uploadedFiles.length > 0) {
        setPendingFiles(uploadedFiles);
        setCurrentFileIndex(0);
        setCurrentUploadId(uploadedFiles[0].uploadId);
        setCurrentFileName(uploadedFiles[0].file.name);
        setProcessingStep("confirm_ai");
        setShowConfirm(false);
        setUploading(false);
        setUploadingIndex(null);
        return; // No cerrar el modal, el flujo paso a paso continuará
      }
      
      // Para ventas: comportamiento original
      setShowConfirm(false);
      clearFiles();
      setShowSuccess(true);
    } catch (err: any) {
      alert("Error subiendo archivos: " + (err?.message ?? String(err)));
    } finally {
      setUploading(false);
      setUploadingIndex(null);
    }
  };

  // Manejar ignorar duplicado y subir de todos modos
  const handleDuplicateIgnore = async () => {
    if (!pendingDuplicateFile || !token || !docType) return;
    
    setDuplicateProcessing(true);
    
    try {
      const fd = new FormData();
      fd.append("file", pendingDuplicateFile);
      fd.append("tipo", docType);
      fd.append("force", "true");
      
      const res = await fetchWithAuth("/api/upload/", {
        method: "POST",
        token: token || undefined,
        onLogout,
        body: fd,
      });
      
      if (!res.ok) {
        const t = await res.text();
        console.error(`Fallo subiendo ${pendingDuplicateFile.name}:`, t);
        alert(`Fallo subiendo ${pendingDuplicateFile.name}: ${t}`);
        return;
      }
      
      const result = await res.json();
      
      // Para facturas, iniciar el flujo paso a paso
      if (docType === "factura" && result.upload_id) {
        setShowDuplicateModal(false);
        setDuplicateInfo(null);
        setPendingDuplicateFile(null);
        setPendingFiles([{ file: pendingDuplicateFile, uploadId: result.upload_id }]);
        setCurrentFileIndex(0);
        setCurrentUploadId(result.upload_id);
        setCurrentFileName(pendingDuplicateFile.name);
        setProcessingStep("confirm_ai");
      } else {
        // Para ventas
        setShowDuplicateModal(false);
        setDuplicateInfo(null);
        setPendingDuplicateFile(null);
        setShowSuccess(true);
      }
      
      loadHistorico();
      
      // Continuar con los archivos restantes si hay
      if (files.length > 0) {
        setShowConfirm(true);
      }
    } catch (err: any) {
      alert("Error subiendo archivo: " + (err?.message ?? String(err)));
    } finally {
      setDuplicateProcessing(false);
    }
  };

  // Manejar cancelar duplicado y eliminar archivo temporal
  const handleDuplicateCancel = async () => {
    if (!duplicateInfo?.temp_file || !token) {
      setShowDuplicateModal(false);
      setDuplicateInfo(null);
      setPendingDuplicateFile(null);
      return;
    }
    
    setDuplicateProcessing(true);
    
    try {
      // Eliminar el archivo temporal del backend
      await fetchWithAuth("/api/upload/temp", {
        method: "DELETE",
        token: token || undefined,
        onLogout,
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ file_path: duplicateInfo.temp_file }),
      });
    } catch (err) {
      console.error("Error eliminando archivo temporal:", err);
    } finally {
      setDuplicateProcessing(false);
      setShowDuplicateModal(false);
      setDuplicateInfo(null);
      setPendingDuplicateFile(null);
      
      // Continuar con los archivos restantes si hay
      if (files.length > 0) {
        setShowConfirm(true);
      }
    }
  };

  const disabled = !docType;

  // ====== FUNCIONES DEL FLUJO PASO A PASO ======
  
  /** Inicia el procesamiento con IA para un upload */
  const startAIProcessing = async (uploadId: string) => {
    if (!token) return;
    setProcessingStep("processing_ai");
    setProcessingError(null);
    
    try {
      const response = await fetchWithAuth(`/api/processing/${uploadId}/start-ai`, {
        method: "POST",
        token: token || undefined,
        onLogout,
      });
      
      const data = await response.json();
      
      if (data.success) {
        setAiResult(data.ai_data);
        setProcessingStep("confirm_drive");
        loadHistorico();
      } else {
        setProcessingError(data.error || "Error en el procesamiento con IA");
        setProcessingStep("error");
        loadHistorico();
      }
    } catch (err: any) {
      console.error("Error en startAIProcessing:", err);
      setProcessingError(err?.message || "Error desconocido");
      setProcessingStep("error");
    }
  };
  
  /** Inicia la subida a Google Drive */
  const startDriveUpload = async (uploadId: string) => {
    if (!token) return;
    setProcessingStep("uploading_drive");
    setProcessingError(null);
    
    try {
      const response = await fetchWithAuth(`/api/processing/${uploadId}/start-drive`, {
        method: "POST",
        token: token || undefined,
        onLogout,
      });
      
      const data = await response.json();
      
      if (data.success) {
        setDriveUrl(data.drive_url);
        setProcessingStep("completed");
        loadHistorico();
      } else {
        setProcessingError(data.error || "Error subiendo a Drive");
        setProcessingStep("error");
        loadHistorico();
      }
    } catch (err: any) {
      console.error("Error en startDriveUpload:", err);
      setProcessingError(err?.message || "Error desconocido");
      setProcessingStep("error");
    }
  };
  
  /** Reintentar el paso fallido */
  const retryProcessing = async () => {
    if (!currentUploadId || !token) return;
    
    // Obtener el estado actual del upload para determinar qué paso falló
    try {
      const statusResponse = await fetchWithAuth(`/api/processing/${currentUploadId}/status`, {
        method: "GET",
        token: token || undefined,
        onLogout,
      });
      
      if (!statusResponse.ok) {
        throw new Error("No se pudo obtener el estado del upload");
      }
      
      const statusData = await statusResponse.json();
      const currentStatus = statusData.status;
      
      // Determinar qué paso reintentar basándose en el estado
      if (currentStatus === "FAILED_AI" || currentStatus === "UPLOADED" || currentStatus === "QUEUED") {
        // Falló el procesamiento con IA, reintentar IA
        await startAIProcessing(currentUploadId);
      } else if (currentStatus === "FAILED_DRIVE" || currentStatus === "AI_COMPLETED") {
        // Falló la subida a Drive, reintentar Drive
        await startDriveUpload(currentUploadId);
      } else {
        // Estado desconocido, usar endpoint genérico de retry
        const response = await fetchWithAuth(`/api/processing/${currentUploadId}/retry`, {
          method: "POST",
          token: token || undefined,
          onLogout,
        });
        
        const data = await response.json();
        
        if (data.success) {
          if (data.status === "AI_COMPLETED") {
            setAiResult(data.ai_data);
            setProcessingStep("confirm_drive");
          } else if (data.status === "COMPLETED") {
            setDriveUrl(data.drive_url);
            setProcessingStep("completed");
          }
          loadHistorico();
        } else {
          setProcessingError(data.error || "Error en el reintento");
          setProcessingStep("error");
        }
      }
    } catch (err: any) {
      console.error("Error en retryProcessing:", err);
      setProcessingError(err?.message || "Error desconocido");
      setProcessingStep("error");
    }
  };
  
  /** Pasar a la siguiente factura o finalizar */
  const processNextFile = () => {
    const nextIndex = currentFileIndex + 1;
    if (nextIndex < pendingFiles.length) {
      setCurrentFileIndex(nextIndex);
      setCurrentUploadId(pendingFiles[nextIndex].uploadId);
      setCurrentFileName(pendingFiles[nextIndex].file.name);
      setAiResult(null);
      setDriveUrl(null);
      setProcessingError(null);
      setProcessingStep("confirm_ai");
    } else {
      // Finalizar
      resetProcessingState();
      clearFiles();
      setShowSuccess(true);
    }
  };
  
  /** Resetear el estado del flujo */
  const resetProcessingState = () => {
    setProcessingStep("idle");
    setCurrentUploadId(null);
    setCurrentFileName(null);
    setAiResult(null);
    setDriveUrl(null);
    setProcessingError(null);
    setPendingFiles([]);
    setCurrentFileIndex(0);
  };
  
  /** Cancelar el procesamiento */
  const cancelProcessing = () => {
    resetProcessingState();
    setShowConfirm(false);
  };

  // helpers formulario manual
  const setManualField = <K extends keyof ManualForm>(
    field: K,
    value: string,
  ) => {
    setManualForm((prev) => ({ ...prev, [field]: value }));
  };

  const openManualModal = () => {
    if (!docType) {
      setShowTypeSelectionModal(true);
      return;
    }
    setManualForm(initialManualForm); // reseteamos
    setManualFile(null);
    setShowManualModal(true);
  };

  const handleTypeSelection = (type: DocType) => {
    setDocType(type);
    setShowTypeSelectionModal(false);
    setManualForm(initialManualForm);
    setManualFile(null);
    setShowManualModal(true);
  };

  // Cerrar modal con Esc
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (showManualModal) {
          setShowManualModal(false);
          setManualForm(initialManualForm);
          setManualFile(null);
        }
        if (showTypeSelectionModal) {
          setShowTypeSelectionModal(false);
        }
        if (showDetailsModal) {
          setShowDetailsModal(false);
          setSelectedOp(null);
          setFacturaData(null);
          setFacturaId(null);
          setFacturaError(null);
        }
        // Cerrar modal del flujo paso a paso (solo si no está procesando)
        if (processingStep !== "idle" && processingStep !== "processing_ai" && processingStep !== "uploading_drive") {
          cancelProcessing();
        }
      }
    };
    window.addEventListener("keydown", handleEsc);
    return () => window.removeEventListener("keydown", handleEsc);
  }, [showManualModal, showTypeSelectionModal, showDetailsModal, processingStep]);

  // Abrir modal de detalles
  const handleRowClick = async (op: Operacion) => {
    console.log("🔵 [DEBUG] handleRowClick - Operación clickeada:", op);
    console.log("🔵 [DEBUG] handleRowClick - ID del upload:", op.id);
    console.log("🔵 [DEBUG] handleRowClick - Tipo:", op.tipo);
    
    setSelectedOp(op);
    setShowDetailsModal(true);
    setFacturaData(null);
    setFacturaId(null);
    setFacturaError(null);
    
    // Si es una factura, cargar los datos de la factura
    if (op.tipo === "FACTURA" && token) {
      const url = `/api/uploads/${op.id}/factura`;
      console.log("🔵 [DEBUG] handleRowClick - URL del endpoint:", url);
      console.log("🔵 [DEBUG] handleRowClick - Token disponible:", !!token);
      
      setLoadingFactura(true);
      try {
        console.log("🔵 [DEBUG] handleRowClick - Iniciando petición al backend...");
        const response = await fetchWithAuth(
          url,
          {
            token: token || undefined,
            onLogout,
          }
        );
        
        console.log("🔵 [DEBUG] handleRowClick - Respuesta recibida, status:", response.status);
        console.log("🔵 [DEBUG] handleRowClick - Response OK:", response.ok);
        
        if (response.ok) {
          const data = await response.json();
          console.log("🔵 [DEBUG] handleRowClick - Datos recibidos del backend:", data);
          console.log("🔵 [DEBUG] handleRowClick - factura_id recibido:", data.factura_id);
          console.log("🔵 [DEBUG] handleRowClick - factura recibida:", data.factura);
          
          setFacturaData(data.factura);
          setFacturaId(data.factura_id);
          setFacturaError(null);
        } else {
          const errorText = await response.text();
          console.error("🔴 [DEBUG] handleRowClick - Error en respuesta, status:", response.status);
          console.error("🔴 [DEBUG] handleRowClick - Error text:", errorText);
          
          let errorMessage = errorText;
          try {
            const errorJson = JSON.parse(errorText);
            errorMessage = errorJson.detail || errorJson.message || errorText;
            console.error("🔴 [DEBUG] handleRowClick - Error parseado:", errorMessage);
          } catch {
            // Si no es JSON, usar el texto directamente
            console.error("🔴 [DEBUG] handleRowClick - Error no es JSON, usando texto directo");
          }
          setFacturaError(errorMessage);
          console.error("Error cargando factura:", errorMessage);
        }
      } catch (err: any) {
        console.error("🔴 [DEBUG] handleRowClick - Excepción capturada:", err);
        console.error("🔴 [DEBUG] handleRowClick - Tipo de error:", typeof err);
        console.error("🔴 [DEBUG] handleRowClick - Mensaje de error:", err?.message);
        
        const errorMessage = err?.message || String(err) || "Error desconocido al cargar la factura";
        setFacturaError(errorMessage);
        console.error("Error cargando factura:", err);
      } finally {
        console.log("🔵 [DEBUG] handleRowClick - Finalizando carga, setting loadingFactura = false");
        setLoadingFactura(false);
      }
    } else {
      console.log("🔵 [DEBUG] handleRowClick - No es FACTURA o no hay token");
      console.log("🔵 [DEBUG] handleRowClick - Tipo:", op.tipo, "Token:", !!token);
    }
  };

  // Abrir archivo en Google Drive
  const handleOpenFile = (url: string) => {
    if (!url) {
      alert("Archivo no disponible");
      return;
    }

    // ubicacion_factura contiene la URL de Google Drive
    const fileUrl = url.trim();
    console.log("Abriendo archivo con URL:", fileUrl);
    
    // Abrir directamente la URL de Google Drive
    window.open(fileUrl, "_blank", "noopener,noreferrer");
  };

  const handleManualSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!docType) {
      alert("Falta el tipo (Factura/Venta).");
      return;
    }
    
    if (!token) {
      alert("Sesión caducada. Inicia sesión de nuevo.");
      return;
    }
    
    // Validar campos obligatorios
    if (!manualForm.fecha_dt || !manualForm.proveedor || !manualForm.importe_sin_iva_local || !manualForm.iva_local) {
      alert("Por favor, completa todos los campos obligatorios (marcados con *)");
      return;
    }

    setUploading(true);
    try {
      // Preparar FormData con todos los campos
      const fd = new FormData();
      
      // Campos obligatorios
      fd.append("fecha", manualForm.fecha || "");
      fd.append("fecha_dt", manualForm.fecha_dt || "");
      fd.append("proveedor", manualForm.proveedor);
      fd.append("importe_sin_iva_local", manualForm.importe_sin_iva_local || "");
      fd.append("iva_local", manualForm.iva_local || "");
      
      // Campos opcionales
      if (manualForm.supplier_vat_number) fd.append("supplier_vat_number", manualForm.supplier_vat_number);
      if (manualForm.total_moneda_local) fd.append("total_moneda_local", manualForm.total_moneda_local);
      if (manualForm.moneda) fd.append("moneda", manualForm.moneda);
      if (manualForm.tarifa_cambio) fd.append("tarifa_cambio", manualForm.tarifa_cambio);
      if (manualForm.importe_sin_iva_euro) fd.append("importe_sin_iva_euro", manualForm.importe_sin_iva_euro);
      if (manualForm.importe_total_euro) fd.append("importe_total_euro", manualForm.importe_total_euro);
      if (manualForm.pais_origen) fd.append("pais_origen", manualForm.pais_origen);
      if (manualForm.id_ext) fd.append("id_ext", manualForm.id_ext);
      if (manualForm.notas) fd.append("notas", manualForm.notas);
      if (manualForm.descripcion) fd.append("descripcion", manualForm.descripcion);
      if (manualForm.categoria) fd.append("categoria", manualForm.categoria);
      
      // Archivo opcional
      if (manualFile) {
        fd.append("file", manualFile);
      }
      
      // Llamar al endpoint del backend
      const res = await fetchWithAuth("/api/facturas/manual", {
        method: "POST",
        token: token || undefined,
        onLogout,
        body: fd,
      });
      
      if (!res.ok) {
        const errorText = await res.text();
        console.error("Error guardando factura manual:", errorText);
        alert(`Error guardando factura: ${errorText}`);
        return;
      }
      
      const result = await res.json();
      console.log("✅ Factura manual guardada:", result);
      
      // Recargar histórico si hay archivo
      if (manualFile) {
        loadHistorico();
      }
      
      setShowManualModal(false);
      setManualForm(initialManualForm);
      setManualFile(null);
      setShowSuccess(true);
    } catch (err: any) {
      console.error("Error en handleManualSubmit:", err);
      alert("Error guardando factura: " + (err?.message ?? String(err)));
    } finally {
      setUploading(false);
    }
  };

  const manualLabelStyle: React.CSSProperties = {
    fontSize: "0.875rem",
    fontWeight: 600,
    marginBottom: 6,
    color: "#374151",
  };

  const manualInputStyle: React.CSSProperties = {
    width: "100%",
    padding: "10px 12px",
    borderRadius: 8,
    border: "1px solid #d1d5db",
    fontSize: "0.95rem",
    boxSizing: "border-box",
    transition: "border-color 0.2s, box-shadow 0.2s",
  };

  return (
    <div className="w-full sm:max-w-[75%] mx-auto px-4 sm:px-6 lg:px-8">
      <div className="rounded-2xl shadow-soft bg-white/80 backdrop-blur p-6 border border-gray-100">
        <h1
          className="text-3xl sm:text-4xl font-bold text-center mb-2"
          style={{
            background: "linear-gradient(135deg, #092342 0%, #1a335a 100%)",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
            backgroundClip: "text",
            marginBottom: 32,
            letterSpacing: "-0.02em",
          }}
        >
          Subir factura o fichero de ventas
        </h1>

        {/* Selector tipo */}
        <div className="text-center mb-3 text-sm text-gray-600">
          Selecciona el tipo de fichero a subir
        </div>
        <div
          className="flex items-center justify-center gap-4 mb-6"
          style={{ marginBottom: 8 }}
        >
          <button
            type="button"
            className="px-4 py-2 rounded-lg text-white"
            style={{
              marginRight: "6px",
              backgroundColor: docType === "factura" ? "#071a2e" : "#0875bb",
            }}
            onMouseEnter={(e) => {
              if (docType !== "factura") {
                e.currentTarget.style.backgroundColor = "#071a2e";
              }
            }}
            onMouseLeave={(e) => {
              if (docType !== "factura") {
                e.currentTarget.style.backgroundColor = "#0875bb";
              }
            }}
            onClick={() => setDocType("factura")}
          >
            Factura
          </button>
          <button
            type="button"
            className="px-4 py-2 rounded-lg text-white"
            style={{
              marginLeft: "6px",
              backgroundColor: docType === "venta" ? "#071a2e" : "#0875bb",
            }}
            onMouseEnter={(e) => {
              if (docType !== "venta") {
                e.currentTarget.style.backgroundColor = "#071a2e";
              }
            }}
            onMouseLeave={(e) => {
              if (docType !== "venta") {
                e.currentTarget.style.backgroundColor = "#0875bb";
              }
            }}
            onClick={() => setDocType("venta")}
          >
            Venta
          </button>
          <button
            type="button"
            onClick={openManualModal}
            className="px-4 py-2 rounded-lg bg-[#0875bb] text-white hover:bg-[#071a2e]"
          >
            ➕ Añadir manualmente
          </button>
        </div>

        {/* input oculto (multiple) */}
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".pdf,.xlsx,application/pdf,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          style={{ display: "none" }}
          onChange={handleInputChange}
        />

        {/* Dropzone */}
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => {
            setDragOver(false);
          }}
          onDrop={(e) => {
            handleDrop(e);
          }}
          onClick={() => {
            inputRef.current?.click();
          }}
          style={{
            maxWidth: 720,
            margin: "12px auto 16px",
            background: "#fff",
            border: `2px dashed ${dragOver ? "#1d4ed8" : "#cbd5e1"}`,
            borderRadius: 12,
            minHeight: 260,
            padding: 24,
            textAlign: "center" as const,
            cursor: "pointer",
            boxShadow: dragOver ? "0 6px 20px rgba(29,78,216,.15)" : "none",
            transition:
              "border-color 120ms ease, box-shadow 120ms ease",
            position: "relative",
          }}
        >

          <p
            style={{
              fontWeight: 600,
              color: "#111827",
              margin: "4px 0 6px",
            }}
          >
            Arrastra y suelta archivos aquí
          </p>
          <p
            style={{
              color: "#6b7280",
              fontSize: "0.95rem",
              margin: 0,
            }}
          >
            o haz clic para seleccionar PDF o XLSX (múltiples)
          </p>

          {/* Lista de archivos seleccionados */}
          {files.length > 0 && (
            <div
              style={{
                marginTop: 14,
                display: "flex",
                gap: 8,
                flexWrap: "wrap",
                justifyContent: "center",
              }}
            >
              {files.map((f) => (
                <div
                  key={f.name + f.size}
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
                  }}
                  title={f.name}
                >
                  <span
                    className="font-medium"
                    style={{
                      maxWidth: 220,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {f.name}
                  </span>
                  <span style={{ opacity: 0.7 }}>
                    {(f.size / 1024).toFixed(0)} KB
                  </span>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      removeFile(f.name, f.size);
                    }}
                    aria-label="Quitar archivo"
                    title="Quitar archivo"
                    style={{
                      background: "transparent",
                      border: 0,
                      fontSize: 16,
                      cursor: "pointer",
                      color: "inherit",
                    }}
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Botón limpiar selección */}
          {files.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  clearFiles();
                }}
                className="px-3 py-1 rounded-lg border"
                title="Vaciar selección"
              >
                Limpiar selección
              </button>
            </div>
          )}
        </div>

        {/* CTA Subir */}
        <div className="flex justify-center mt-4" style={{ minHeight: 60 }}>
          {files.length > 0 && !disabled && (
            <button
              onClick={startUpload}
              disabled={uploading}
              className={`seg-option ${
                uploading ? "opacity-50 cursor-not-allowed" : "seg-selected"
              }`}
              style={{ opacity: uploading ? 0.6 : 1 }}
            >
              {uploading
                ? `Subiendo… ${
                    uploadingIndex !== null
                      ? `${uploadingIndex + 1}/${files.length}`
                      : ""
                  }`
                : `Subir ${files.length} archivo${
                    files.length > 1 ? "s" : ""
                  }`}
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
              Vas a subir <strong>{files.length}</strong> archivo
              {files.length > 1 ? "s" : ""} como{" "}
              <strong>{docType}</strong>. ¿Confirmas?
            </p>
            {/* Muestra hasta 5 nombres */}
            <div className="flex justify-center mt-2">
              <ul className="text-xs text-gray-600 max-h-28 overflow-auto text-left">
                {files.slice(0, 5).map((f) => (
                  <li key={f.name + f.size}>• {f.name}</li>
                ))}
                {files.length > 5 && (
                  <li>… y {files.length - 5} más</li>
                )}
              </ul>
            </div>
            
            {/* Mensaje de progreso animado */}
            {uploading && (
              <div 
                className="mt-6 flex flex-col items-center justify-center gap-2"
                style={{
                  opacity: 0,
                  animation: "fadeIn 0.3s ease-in forwards",
                }}
              >
                <div className="flex items-center gap-2">
                  <div 
                    style={{
                      width: "20px",
                      height: "20px",
                      border: "2px solid #0875bb",
                      borderTopColor: "transparent",
                      borderRadius: "50%",
                      animation: "spin 1s linear infinite",
                    }}
                  />
                  <span className="text-sm font-medium text-[#0875bb]">
                    Subiendo archivos, por favor espere...
                  </span>
                </div>
                {uploadingIndex !== null && (
                  <span className="text-xs text-gray-500">
                    {uploadingIndex + 1} de {files.length} archivos
                  </span>
                )}
              </div>
            )}
            
            {/* Botones - ocultos cuando está subiendo */}
            {!uploading && (
              <div className="mt-6 flex justify-center gap-4">
                <button
                  className="modal-btn modal-btn-cancel"
                  onClick={() => setShowConfirm(false)}
                  disabled={uploading}
                >
                  Cancelar
                </button>
                <button
                  className="modal-btn modal-btn-confirm"
                  onClick={() => confirmUpload()}
                  disabled={uploading}
                >
                  Confirmar
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Modal de éxito */}
      {showSuccess && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-6 w-full max-w-md shadow-xl border border-gray-100 text-center">
            <h2 className="text-lg font-semibold text-gray-900 mb-3">
              ✅ Archivo
              {files.length > 1 ? "s" : ""} subido
              {files.length > 1 ? "s" : ""} correctamente
            </h2>
            <p className="text-gray-700 text-sm mb-6">
              Tus archivos se han guardado y procesado correctamente.
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

      {/* ========= MODAL FLUJO PASO A PASO ========= */}
      {processingStep !== "idle" && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div
            className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col"
            style={{ boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.25)" }}
          >
            {/* Header */}
            <div className="flex items-center justify-between p-6 border-b border-gray-200">
              <div>
                <h2 
                  className="text-xl font-bold"
                  style={{
                    background: "linear-gradient(135deg, #3631a3 0%, #092342 100%)",
                    WebkitBackgroundClip: "text",
                    WebkitTextFillColor: "transparent",
                    backgroundClip: "text",
                  }}
                >
                  Procesamiento de Factura
                </h2>
                {pendingFiles.length > 1 && (
                  <p className="text-sm text-gray-500 mt-1">
                    Factura {currentFileIndex + 1} de {pendingFiles.length}
                  </p>
                )}
              </div>
              <button
                onClick={cancelProcessing}
                className="text-gray-400 hover:text-gray-600 transition-colors"
                style={{ fontSize: "24px", lineHeight: "1", padding: "4px", cursor: "pointer" }}
                aria-label="Cerrar"
              >
                ×
              </button>
            </div>

            {/* Contenido */}
            <div className="overflow-y-auto p-6" style={{ maxHeight: "calc(90vh - 200px)" }}>
              {/* Nombre del archivo */}
              {currentFileName && (
                <div className="mb-4 p-3 bg-gray-50 rounded-lg">
                  <p className="text-sm text-gray-600">
                    <span className="font-semibold">Archivo:</span> {currentFileName}
                  </p>
                </div>
              )}

              {/* PASO 1: Confirmar procesamiento con IA */}
              {processingStep === "confirm_ai" && (
                <div className="text-center py-6">
                  <div className="mb-6">
                    <div className="w-16 h-16 mx-auto mb-4 bg-blue-100 rounded-full flex items-center justify-center">
                      <span className="text-3xl">🤖</span>
                    </div>
                    <h3 className="text-lg font-semibold text-gray-900 mb-2">
                      ¿Procesar con Inteligencia Artificial?
                    </h3>
                    <p className="text-gray-600 text-sm">
                      La IA extraerá automáticamente los datos de la factura: fecha, proveedor, importes, etc.
                    </p>
                  </div>
                  <div className="flex justify-center gap-4">
                    <button
                      onClick={cancelProcessing}
                      className="px-5 py-2 rounded-lg border border-gray-300 bg-white hover:bg-gray-50 transition-colors font-medium"
                    >
                      Cancelar
                    </button>
                    <button
                      onClick={() => currentUploadId && startAIProcessing(currentUploadId)}
                      className="px-5 py-2 rounded-lg bg-[#0875bb] text-white hover:bg-[#065a8f] transition-colors font-medium"
                    >
                      Sí, procesar con IA
                    </button>
                  </div>
                </div>
              )}

              {/* PASO 2: Procesando con IA */}
              {processingStep === "processing_ai" && (
                <div className="text-center py-8">
                  <div className="mb-6">
                    <div 
                      className="w-16 h-16 mx-auto mb-4 border-4 border-blue-500 border-t-transparent rounded-full"
                      style={{ animation: "spin 1s linear infinite" }}
                    />
                    <h3 className="text-lg font-semibold text-gray-900 mb-2">
                      Procesando con IA...
                    </h3>
                    <p className="text-gray-600 text-sm">
                      Extrayendo información de la factura. Esto puede tardar unos segundos.
                    </p>
                  </div>
                </div>
              )}

              {/* PASO 3: Confirmar subida a Drive */}
              {processingStep === "confirm_drive" && (
                <div className="py-4">
                  <div className="mb-6 text-center">
                    <div className="w-16 h-16 mx-auto mb-4 bg-green-100 rounded-full flex items-center justify-center">
                      <span className="text-3xl">✅</span>
                    </div>
                    <h3 className="text-lg font-semibold text-gray-900 mb-2">
                      Datos extraídos correctamente
                    </h3>
                  </div>
                  
                  {/* Mostrar datos extraídos */}
                  {aiResult && (
                    <div className="mb-6 p-4 bg-gray-50 rounded-lg">
                      <h4 className="text-sm font-semibold text-gray-700 mb-3">Información extraída:</h4>
                      <div className="grid grid-cols-2 gap-3 text-sm">
                        {aiResult.fecha && (
                          <div>
                            <span className="text-gray-500">Fecha:</span>
                            <span className="ml-2 text-gray-900">{aiResult.fecha}</span>
                          </div>
                        )}
                        {aiResult.proveedor && (
                          <div>
                            <span className="text-gray-500">Proveedor:</span>
                            <span className="ml-2 text-gray-900">{aiResult.proveedor}</span>
                          </div>
                        )}
                        {aiResult.importe_sin_iva != null && (
                          <div>
                            <span className="text-gray-500">Importe sin IVA:</span>
                            <span className="ml-2 text-gray-900">{aiResult.importe_sin_iva} {aiResult.moneda || "EUR"}</span>
                          </div>
                        )}
                        {aiResult.iva_porcentaje != null && (
                          <div>
                            <span className="text-gray-500">IVA:</span>
                            <span className="ml-2 text-gray-900">{aiResult.iva_porcentaje}%</span>
                          </div>
                        )}
                        {aiResult.importe_total != null && (
                          <div>
                            <span className="text-gray-500">Total:</span>
                            <span className="ml-2 text-gray-900 font-semibold">{aiResult.importe_total} {aiResult.moneda || "EUR"}</span>
                          </div>
                        )}
                        {aiResult.pais_origen && (
                          <div>
                            <span className="text-gray-500">País:</span>
                            <span className="ml-2 text-gray-900">{aiResult.pais_origen}</span>
                          </div>
                        )}
                        {aiResult.categoria && (
                          <div className="col-span-2">
                            <span className="text-gray-500">Categoría:</span>
                            <span className="ml-2 text-gray-900">{aiResult.categoria}</span>
                          </div>
                        )}
                        {aiResult.descripcion && (
                          <div className="col-span-2">
                            <span className="text-gray-500">Descripción:</span>
                            <span className="ml-2 text-gray-900">{aiResult.descripcion}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                  
                  <div className="text-center">
                    <p className="text-gray-600 text-sm mb-4">
                      ¿Deseas subir el archivo a Google Drive?
                    </p>
                    <div className="flex justify-center gap-4">
                      <button
                        onClick={processNextFile}
                        className="px-5 py-2 rounded-lg border border-gray-300 bg-white hover:bg-gray-50 transition-colors font-medium"
                      >
                        Omitir Drive
                      </button>
                      <button
                        onClick={() => currentUploadId && startDriveUpload(currentUploadId)}
                        className="px-5 py-2 rounded-lg bg-[#0875bb] text-white hover:bg-[#065a8f] transition-colors font-medium inline-flex items-center gap-2"
                      >
                        <span>📁</span>
                        <span>Subir a Drive</span>
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* PASO 4: Subiendo a Drive */}
              {processingStep === "uploading_drive" && (
                <div className="text-center py-8">
                  <div className="mb-6">
                    <div 
                      className="w-16 h-16 mx-auto mb-4 border-4 border-green-500 border-t-transparent rounded-full"
                      style={{ animation: "spin 1s linear infinite" }}
                    />
                    <h3 className="text-lg font-semibold text-gray-900 mb-2">
                      Subiendo a Google Drive...
                    </h3>
                    <p className="text-gray-600 text-sm">
                      Guardando el archivo en tu Google Drive.
                    </p>
                  </div>
                </div>
              )}

              {/* PASO 5: Completado */}
              {processingStep === "completed" && (
                <div className="text-center py-6">
                  <div className="mb-6">
                    <div className="w-16 h-16 mx-auto mb-4 bg-green-100 rounded-full flex items-center justify-center">
                      <span className="text-3xl">🎉</span>
                    </div>
                    <h3 className="text-lg font-semibold text-gray-900 mb-2">
                      ¡Factura procesada correctamente!
                    </h3>
                    {driveUrl && (
                      <div className="mb-4">
                        <button
                          onClick={() => driveUrl && window.open(driveUrl, "_blank", "noopener,noreferrer")}
                          className="text-blue-600 hover:text-blue-800 text-sm underline"
                        >
                          Ver en Google Drive
                        </button>
                      </div>
                    )}
                  </div>
                  <div className="flex justify-center">
                    <button
                      onClick={processNextFile}
                      className="px-6 py-2 rounded-lg bg-[#0875bb] text-white hover:bg-[#065a8f] transition-colors font-medium"
                    >
                      {currentFileIndex + 1 < pendingFiles.length ? "Siguiente factura" : "Finalizar"}
                    </button>
                  </div>
                </div>
              )}

              {/* ERROR */}
              {processingStep === "error" && (
                <div className="text-center py-6">
                  <div className="mb-6">
                    <div className="w-16 h-16 mx-auto mb-4 bg-red-100 rounded-full flex items-center justify-center">
                      <span className="text-3xl">❌</span>
                    </div>
                    <h3 className="text-lg font-semibold text-gray-900 mb-2">
                      Error en el procesamiento
                    </h3>
                    {processingError && (
                      <p className="text-red-600 text-sm mb-4 p-3 bg-red-50 rounded-lg">
                        {processingError}
                      </p>
                    )}
                  </div>
                  <div className="flex justify-center gap-4">
                    <button
                      onClick={processNextFile}
                      className="px-5 py-2 rounded-lg border border-gray-300 bg-white hover:bg-gray-50 transition-colors font-medium"
                    >
                      Omitir esta factura
                    </button>
                    <button
                      onClick={retryProcessing}
                      className="px-5 py-2 rounded-lg bg-[#0875bb] text-white hover:bg-[#065a8f] transition-colors font-medium"
                    >
                      Reintentar
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Modal de selección de tipo */}
      {showTypeSelectionModal && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
          onClick={(e) => {
            if (e.target === e.currentTarget) {
              setShowTypeSelectionModal(false);
            }
          }}
        >
          <div
            className="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden"
            style={{
              boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.25)",
            }}
          >
            {/* Header con botón X */}
            <div className="flex items-center justify-between p-6 border-b border-gray-200">
              <h2 
                className="text-xl font-bold"
                style={{
                  background: "linear-gradient(135deg, #3631a3 0%, #092342 100%)",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                  backgroundClip: "text",
                }}
              >
                Selecciona el tipo
              </h2>
              <button
                onClick={() => setShowTypeSelectionModal(false)}
                className="text-gray-400 hover:text-gray-600 transition-colors"
                style={{
                  fontSize: "24px",
                  lineHeight: "1",
                  padding: "4px",
                  cursor: "pointer",
                }}
                aria-label="Cerrar"
              >
                ×
              </button>
            </div>

            {/* Contenido */}
            <div className="p-6">
              <p className="text-sm text-gray-600 mb-6 text-center">
                Por favor, selecciona si quieres añadir una factura o una venta manualmente.
              </p>
              
              <div className="flex flex-col gap-4">
                <button
                  type="button"
                  onClick={() => handleTypeSelection("factura")}
                  className="seg-option seg-selected text-center py-4 px-6"
                  style={{
                    fontSize: "16px",
                    fontWeight: 700,
                  }}
                >
                  Factura
                </button>
                <button
                  type="button"
                  onClick={() => handleTypeSelection("venta")}
                  className="seg-option seg-selected text-center py-4 px-6"
                  style={{
                    fontSize: "16px",
                    fontWeight: 700,
                  }}
                >
                  Venta
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modal formulario manual */}
      {showManualModal && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
          style={{ paddingTop: "80px" }}
          onClick={(e) => {
            if (e.target === e.currentTarget) {
              setShowManualModal(false);
              setManualForm(initialManualForm);
              setManualFile(null);
            }
          }}
        >
          <div
            className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[calc(90vh-80px)] overflow-hidden flex flex-col"
            style={{
              boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.25)",
            }}
          >
            {/* Header con botón X */}
            <div className="flex items-center justify-between p-6 border-b border-gray-200">
              <h2 
                className="text-2xl font-bold"
                style={{
                  background: "linear-gradient(135deg, #3631a3 0%, #092342 100%)",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                  backgroundClip: "text",
                }}
              >
                Añadir {docType === "venta" ? "venta" : "factura"} manualmente
              </h2>
              <button
                onClick={() => {
                  setShowManualModal(false);
                  setManualForm(initialManualForm);
                  setManualFile(null);
                }}
                className="text-gray-400 hover:text-gray-600 transition-colors"
                style={{
                  fontSize: "24px",
                  lineHeight: "1",
                  padding: "4px",
                  cursor: "pointer",
                }}
                aria-label="Cerrar"
              >
                ×
              </button>
            </div>

            {/* Contenido scrolleable */}
            <div className="overflow-y-auto p-6" style={{ maxHeight: "calc(90vh - 200px)" }}>
              <p className="text-sm text-gray-600 mb-6">
                Completa los campos obligatorios (marcados con <span className="text-red-500">*</span>) y opcionalmente sube el archivo de la factura.
              </p>

            <form
              id="manual-form"
              onSubmit={handleManualSubmit}
            >
              {/* Sección 1: Datos generales */}
              <div className="mb-6">
                <h3 className="text-lg font-semibold text-gray-800 mb-4 pb-2 border-b border-gray-200">
                  1. Datos generales
                </h3>
                <div style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
                  gap: "1.25rem 1.5rem",
                }}>
                  {/* Fecha */}
                  <div>
                    <label style={manualLabelStyle}>
                      Fecha <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="date"
                      required
                      value={manualForm.fecha_dt}
                      onChange={(e) => {
                        setManualField("fecha_dt", e.target.value);
                        setManualField("fecha", e.target.value);
                      }}
                      style={manualInputStyle}
                      onFocus={(e) => {
                        e.currentTarget.style.borderColor = "#0875bb";
                        e.currentTarget.style.boxShadow = "0 0 0 3px rgba(8, 117, 187, 0.1)";
                      }}
                      onBlur={(e) => {
                        e.currentTarget.style.borderColor = "#d1d5db";
                        e.currentTarget.style.boxShadow = "none";
                      }}
                    />
                  </div>

                  {/* Proveedor */}
                  <div>
                    <label style={manualLabelStyle}>
                      Nombre de proveedor <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      required
                      value={manualForm.proveedor}
                      onChange={(e) => setManualField("proveedor", e.target.value)}
                      style={manualInputStyle}
                      onFocus={(e) => {
                        e.currentTarget.style.borderColor = "#0875bb";
                        e.currentTarget.style.boxShadow = "0 0 0 3px rgba(8, 117, 187, 0.1)";
                      }}
                      onBlur={(e) => {
                        e.currentTarget.style.borderColor = "#d1d5db";
                        e.currentTarget.style.boxShadow = "none";
                      }}
                    />
                  </div>

                  {/* VAT proveedor */}
                  <div style={{ gridColumn: "1 / -1" }}>
                    <label style={manualLabelStyle}>VAT del proveedor</label>
                    <input
                      type="text"
                      value={manualForm.supplier_vat_number}
                      onChange={(e) =>
                        setManualField("supplier_vat_number", e.target.value)
                      }
                      style={manualInputStyle}
                      onFocus={(e) => {
                        e.currentTarget.style.borderColor = "#0875bb";
                        e.currentTarget.style.boxShadow = "0 0 0 3px rgba(8, 117, 187, 0.1)";
                      }}
                      onBlur={(e) => {
                        e.currentTarget.style.borderColor = "#d1d5db";
                        e.currentTarget.style.boxShadow = "none";
                      }}
                    />
                  </div>
                </div>
              </div>

              {/* Sección 2: Coste */}
              <div className="mb-6">
                <h3 className="text-lg font-semibold text-gray-800 mb-4 pb-2 border-b border-gray-200">
                  2. Coste
                </h3>
                <div style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
                  gap: "1.25rem 1.5rem",
                }}>

                  {/* Importe sin IVA local */}
                  <div>
                    <label style={manualLabelStyle}>
                      Importe local sin IVA <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="number"
                      step="0.01"
                      required
                      value={manualForm.importe_sin_iva_local}
                      onChange={(e) =>
                        setManualField("importe_sin_iva_local", e.target.value)
                      }
                      style={manualInputStyle}
                      onFocus={(e) => {
                        e.currentTarget.style.borderColor = "#0875bb";
                        e.currentTarget.style.boxShadow = "0 0 0 3px rgba(8, 117, 187, 0.1)";
                      }}
                      onBlur={(e) => {
                        e.currentTarget.style.borderColor = "#d1d5db";
                        e.currentTarget.style.boxShadow = "none";
                      }}
                    />
                  </div>

                  {/* IVA local */}
                  <div>
                    <label style={manualLabelStyle}>
                      % IVA local <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="number"
                      step="0.01"
                      required
                      value={manualForm.iva_local}
                      onChange={(e) => setManualField("iva_local", e.target.value)}
                      style={manualInputStyle}
                      onFocus={(e) => {
                        e.currentTarget.style.borderColor = "#0875bb";
                        e.currentTarget.style.boxShadow = "0 0 0 3px rgba(8, 117, 187, 0.1)";
                      }}
                      onBlur={(e) => {
                        e.currentTarget.style.borderColor = "#d1d5db";
                        e.currentTarget.style.boxShadow = "none";
                      }}
                    />
                  </div>

                  {/* Moneda */}
                  <div>
                    <label style={manualLabelStyle}>Moneda</label>
                    <select
                      value={manualForm.moneda}
                      onChange={(e) => setManualField("moneda", e.target.value)}
                      style={manualInputStyle}
                    >
                      {CURRENCY_CODES.map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Total moneda local */}
                  <div>
                    <label style={manualLabelStyle}>Total en moneda local</label>
                    <input
                      type="number"
                      step="0.01"
                      value={manualForm.total_moneda_local}
                      onChange={(e) =>
                        setManualField("total_moneda_local", e.target.value)
                      }
                      style={manualInputStyle}
                      onFocus={(e) => {
                        e.currentTarget.style.borderColor = "#0875bb";
                        e.currentTarget.style.boxShadow = "0 0 0 3px rgba(8, 117, 187, 0.1)";
                      }}
                      onBlur={(e) => {
                        e.currentTarget.style.borderColor = "#d1d5db";
                        e.currentTarget.style.boxShadow = "none";
                      }}
                    />
                  </div>

                  {/* Tarifa de cambio */}
                  <div>
                    <label style={manualLabelStyle}>Tarifa de cambio €/moneda local</label>
                    <input
                      type="number"
                      step="0.0001"
                      value={manualForm.tarifa_cambio}
                      onChange={(e) =>
                        setManualField("tarifa_cambio", e.target.value)
                      }
                      style={manualInputStyle}
                      onFocus={(e) => {
                        e.currentTarget.style.borderColor = "#0875bb";
                        e.currentTarget.style.boxShadow = "0 0 0 3px rgba(8, 117, 187, 0.1)";
                      }}
                      onBlur={(e) => {
                        e.currentTarget.style.borderColor = "#d1d5db";
                        e.currentTarget.style.boxShadow = "none";
                      }}
                    />
                  </div>

                  {/* Importe sin IVA (EUR) */}
                  <div>
                    <label style={manualLabelStyle}>Importe sin IVA (EUR)</label>
                    <input
                      type="number"
                      step="0.01"
                      value={manualForm.importe_sin_iva_euro}
                      onChange={(e) =>
                        setManualField("importe_sin_iva_euro", e.target.value)
                      }
                      style={manualInputStyle}
                      onFocus={(e) => {
                        e.currentTarget.style.borderColor = "#0875bb";
                        e.currentTarget.style.boxShadow = "0 0 0 3px rgba(8, 117, 187, 0.1)";
                      }}
                      onBlur={(e) => {
                        e.currentTarget.style.borderColor = "#d1d5db";
                        e.currentTarget.style.boxShadow = "none";
                      }}
                    />
                  </div>

                  {/* Importe total (EUR) */}
                  <div>
                    <label style={manualLabelStyle}>Importe total (EUR)</label>
                    <input
                      type="number"
                      step="0.01"
                      value={manualForm.importe_total_euro}
                      onChange={(e) =>
                        setManualField("importe_total_euro", e.target.value)
                      }
                      style={manualInputStyle}
                      onFocus={(e) => {
                        e.currentTarget.style.borderColor = "#0875bb";
                        e.currentTarget.style.boxShadow = "0 0 0 3px rgba(8, 117, 187, 0.1)";
                      }}
                      onBlur={(e) => {
                        e.currentTarget.style.borderColor = "#d1d5db";
                        e.currentTarget.style.boxShadow = "none";
                      }}
                    />
                  </div>
                </div>
              </div>

              {/* Sección 3: Datos adicionales */}
              <div className="mb-6">
                <h3 className="text-lg font-semibold text-gray-800 mb-4 pb-2 border-b border-gray-200">
                  3. Datos adicionales
                </h3>
                <div style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
                  gap: "1.25rem 1.5rem",
                }}>
                  {/* País origen */}
                  <div>
                    <label style={manualLabelStyle}>País de origen</label>
                    <select
                      value={manualForm.pais_origen}
                      onChange={(e) =>
                        setManualField("pais_origen", e.target.value)
                      }
                      style={manualInputStyle}
                    >
                      {COUNTRY_CODES.map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* ID externo */}
                  <div>
                    <label style={manualLabelStyle}>ID externo de factura</label>
                    <input
                      type="text"
                      value={manualForm.id_ext}
                      onChange={(e) => setManualField("id_ext", e.target.value)}
                      style={manualInputStyle}
                      onFocus={(e) => {
                        e.currentTarget.style.borderColor = "#0875bb";
                        e.currentTarget.style.boxShadow = "0 0 0 3px rgba(8, 117, 187, 0.1)";
                      }}
                      onBlur={(e) => {
                        e.currentTarget.style.borderColor = "#d1d5db";
                        e.currentTarget.style.boxShadow = "none";
                      }}
                    />
                  </div>

                  {/* Notas */}
                  <div style={{ gridColumn: "1 / -1" }}>
                    <label style={manualLabelStyle}>Notas</label>
                    <textarea
                      value={manualForm.notas}
                      onChange={(e) => setManualField("notas", e.target.value)}
                      style={{ ...manualInputStyle, minHeight: 60, resize: "vertical" }}
                      onFocus={(e) => {
                        e.currentTarget.style.borderColor = "#0875bb";
                        e.currentTarget.style.boxShadow = "0 0 0 3px rgba(8, 117, 187, 0.1)";
                      }}
                      onBlur={(e) => {
                        e.currentTarget.style.borderColor = "#d1d5db";
                        e.currentTarget.style.boxShadow = "none";
                      }}
                    />
                  </div>

                  {/* Descripción */}
                  <div style={{ gridColumn: "1 / -1" }}>
                    <label style={manualLabelStyle}>Descripción</label>
                    <textarea
                      value={manualForm.descripcion}
                      onChange={(e) =>
                        setManualField("descripcion", e.target.value)
                      }
                      style={{ ...manualInputStyle, minHeight: 60, resize: "vertical" }}
                      onFocus={(e) => {
                        e.currentTarget.style.borderColor = "#0875bb";
                        e.currentTarget.style.boxShadow = "0 0 0 3px rgba(8, 117, 187, 0.1)";
                      }}
                      onBlur={(e) => {
                        e.currentTarget.style.borderColor = "#d1d5db";
                        e.currentTarget.style.boxShadow = "none";
                      }}
                    />
                  </div>
                </div>
              </div>

              {/* Sección 4: Archivo de factura */}
              <div className="mb-6">
                <h3 className="text-lg font-semibold text-gray-800 mb-4 pb-2 border-b border-gray-200">
                  4. Archivo de factura (opcional)
                </h3>
                <div className="flex items-center gap-3">
                  <input
                    ref={manualFileInputRef}
                    type="file"
                    accept=".pdf,.xlsx,application/pdf,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    onChange={(e) => {
                      if (e.target.files && e.target.files[0]) {
                        setManualFile(e.target.files[0]);
                      }
                    }}
                    style={{ display: "none" }}
                  />
                  <button
                    type="button"
                    onClick={() => manualFileInputRef.current?.click()}
                    className="px-4 py-2 rounded-lg border border-gray-300 hover:bg-gray-50 transition-colors"
                    style={{ fontSize: "0.875rem" }}
                  >
                    {manualFile ? "Cambiar archivo" : "Seleccionar archivo"}
                  </button>
                  {manualFile && (
                    <span className="text-sm text-gray-600">
                      {manualFile.name} ({(manualFile.size / 1024).toFixed(0)} KB)
                    </span>
                  )}
                </div>
              </div>

            </form>
            </div>

            {/* Footer con botones */}
            <div className="flex justify-end gap-3 p-6 border-t border-gray-200 bg-gray-50">
              <button
                type="button"
                onClick={() => {
                  setShowManualModal(false);
                  setManualForm(initialManualForm);
                  setManualFile(null);
                }}
                className="px-5 py-2 rounded-lg border border-gray-300 bg-white hover:bg-gray-50 transition-colors font-medium"
                disabled={uploading}
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={handleManualSubmit}
                className="px-5 py-2 rounded-lg bg-[#0875bb] text-white hover:bg-[#065a8f] transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={uploading}
              >
                {uploading ? (
                  <span className="flex items-center gap-2">
                    <div 
                      style={{
                        width: "16px",
                        height: "16px",
                        border: "2px solid #ffffff",
                        borderTopColor: "transparent",
                        borderRadius: "50%",
                        animation: "spin 1s linear infinite",
                      }}
                    />
                    Guardando...
                  </span>
                ) : (
                  "Guardar"
                )}
              </button>
            </div>
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
        <p
          style={{
            margin: "0.25rem 0 1rem",
            color: "#5b667a",
            textAlign: "center",
          }}
        >
          Facturas (1:1) y ventas (por lote)
        </p>

        {opsError && (
          <div style={{ color: "red", marginBottom: "0.75rem" }}>
            {opsError}
          </div>
        )}

        {/* Controles de paginación superior */}
        <div style={{ 
          display: "flex", 
          justifyContent: "space-between", 
          alignItems: "center",
          marginBottom: "1rem",
          padding: "0.5rem 0"
        }}>
          <div style={{ fontSize: "14px", color: "#5b667a" }}>
            Total: {totalRecords} registro{totalRecords !== 1 ? "s" : ""}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <button
              onClick={() => handlePageChange(currentPage - 1)}
              disabled={currentPage === 1}
              style={{
                padding: "6px 12px",
                border: "1px solid #d1d5db",
                borderRadius: "6px",
                background: currentPage === 1 ? "#f3f4f6" : "white",
                color: currentPage === 1 ? "#9ca3af" : "#374151",
                cursor: currentPage === 1 ? "not-allowed" : "pointer",
                fontSize: "14px",
                display: "flex",
                alignItems: "center",
                gap: "4px"
              }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="15,18 9,12 15,6"/>
              </svg>
              Anterior
            </button>
            <span style={{ fontSize: "14px", color: "#5b667a", minWidth: "100px", textAlign: "center" }}>
              Página {currentPage} de {totalPages}
            </span>
            <button
              onClick={() => handlePageChange(currentPage + 1)}
              disabled={currentPage === totalPages}
              style={{
                padding: "6px 12px",
                border: "1px solid #d1d5db",
                borderRadius: "6px",
                background: currentPage === totalPages ? "#f3f4f6" : "white",
                color: currentPage === totalPages ? "#9ca3af" : "#374151",
                cursor: currentPage === totalPages ? "not-allowed" : "pointer",
                fontSize: "14px",
                display: "flex",
                alignItems: "center",
                gap: "4px"
              }}
            >
              Siguiente
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="9,18 15,12 9,6"/>
              </svg>
            </button>
          </div>
        </div>

        <div style={{ overflowX: "auto" }}>
          <table
            style={{
              width: "100%",
              borderCollapse: "separate",
              borderSpacing: 0,
            }}
          >
            <thead>
              <tr style={{ background: "#f6f8fa", color: "#163a63" }}>
                <th 
                  style={{ ...th, textAlign: "center", cursor: "pointer", userSelect: "none" }}
                  onClick={() => handleSort("fecha")}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "4px" }}>
                    Fecha
                    {sortColumn === "fecha" && (
                      <span>{sortDirection === "asc" ? "↑" : "↓"}</span>
                    )}
                  </div>
                </th>
                <th 
                  style={{ ...th, textAlign: "center", cursor: "pointer", userSelect: "none" }}
                  onClick={() => handleSort("tipo")}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "4px" }}>
                    Tipo
                    {sortColumn === "tipo" && (
                      <span>{sortDirection === "asc" ? "↑" : "↓"}</span>
                    )}
                  </div>
                </th>
                <th 
                  style={{ ...th, textAlign: "center", cursor: "pointer", userSelect: "none" }}
                  onClick={() => handleSort("original_filename")}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "4px" }}>
                    Nombre Fichero
                    {sortColumn === "original_filename" && (
                      <span>{sortDirection === "asc" ? "↑" : "↓"}</span>
                    )}
                  </div>
                </th>
                <th style={{ ...th, textAlign: "center" }}>
                  Descripción
                </th>
                <th 
                  style={{ ...th, textAlign: "right", cursor: "pointer", userSelect: "none" }}
                  onClick={() => handleSort("tam_bytes")}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: "4px" }}>
                    Tamaño (KB)
                    {sortColumn === "tam_bytes" && (
                      <span>{sortDirection === "asc" ? "↑" : "↓"}</span>
                    )}
                  </div>
                </th>
                <th 
                  style={{ ...th, textAlign: "center", cursor: "pointer", userSelect: "none" }}
                  onClick={() => handleSort("status")}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "4px" }}>
                    Acciones
                    {sortColumn === "status" && (
                      <span>{sortDirection === "asc" ? "↑" : "↓"}</span>
                    )}
                  </div>
                </th>
              </tr>
            </thead>
            <tbody>
              {ops.map((op) => (
                <tr 
                  key={op.id} 
                  style={{ 
                    borderBottom: "1px solid #eef2f7",
                    cursor: "pointer",
                    transition: "background-color 0.2s ease",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = "#f3f4f6";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = "transparent";
                  }}
                  onClick={() => handleRowClick(op)}
                >
                  <td style={{ ...td, textAlign: "center" }}>
                    {new Date(op.fecha).toLocaleString("es-ES")}
                  </td>
                  <td style={{ ...td, textAlign: "center" }}>
                    <span
                      style={{
                        fontSize: 12,
                        padding: "2px 8px",
                        borderRadius: 999,
                        background:
                          op.tipo === "FACTURA" ? "#eef2ff" : "#ecfdf5",
                        color:
                          op.tipo === "FACTURA" ? "#3730a3" : "#065f46",
                        fontWeight: 600,
                      }}
                    >
                      {op.tipo}
                    </span>
                  </td>
                  <td
                    style={{
                      ...td,
                      textAlign: "left",
                      maxWidth: "200px",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                    title={op.original_filename}
                  >
                    {op.original_filename.length > 30
                      ? op.original_filename.substring(0, 30) + "..."
                      : op.original_filename}
                  </td>
                  <td
                    style={{
                      ...td,
                      textAlign: "left",
                      maxWidth: "200px",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                    title={op.descripcion}
                  >
                    {op.descripcion.length > 30
                      ? op.descripcion.substring(0, 30) + "..."
                      : op.descripcion}
                  </td>
                  <td
                    style={{
                      ...td,
                      textAlign: "right",
                      fontVariantNumeric: "tabular-nums",
                    }}
                  >
                    {op.tam_bytes != null
                      ? (op.tam_bytes / 1024).toFixed(0)
                      : "-"}
                  </td>
                  <td style={{ ...td, textAlign: "center" }}>
                    {(() => {
                      const status = op.status;
                      switch (status) {
                        case "UPLOADED":
                        case "QUEUED":
                          return (
                            <span 
                              style={{ 
                                display: "inline-flex", 
                                alignItems: "center", 
                                gap: 4, 
                                color: "#f59e0b",
                                fontSize: 12,
                                fontWeight: 500
                              }}
                              title="Pendiente de procesar con IA"
                            >
                              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <circle cx="12" cy="12" r="10"/>
                                <polyline points="12,6 12,12 16,14"/>
                              </svg>
                              Pendiente IA
                            </span>
                          );
                        case "PROCESSING_AI":
                        case "PROCESSING":
                          return (
                            <span 
                              style={{ 
                                display: "inline-flex", 
                                alignItems: "center", 
                                gap: 4, 
                                color: "#3b82f6",
                                fontSize: 12,
                                fontWeight: 500
                              }}
                              title="Procesando con IA..."
                            >
                              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ animation: "spin 1s linear infinite" }}>
                                <path d="M21 12a9 9 0 11-6.219-8.56"/>
                              </svg>
                              Procesando IA...
                            </span>
                          );
                        case "AI_COMPLETED":
                          return (
                            <span 
                              style={{ 
                                display: "inline-flex", 
                                alignItems: "center", 
                                gap: 4, 
                                color: "#f59e0b",
                                fontSize: 12,
                                fontWeight: 500
                              }}
                              title="Pendiente de subir a Drive"
                            >
                              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
                                <polyline points="17,8 12,3 7,8"/>
                                <line x1="12" y1="3" x2="12" y2="15"/>
                              </svg>
                              Pendiente Drive
                            </span>
                          );
                        case "UPLOADING_DRIVE":
                          return (
                            <span 
                              style={{ 
                                display: "inline-flex", 
                                alignItems: "center", 
                                gap: 4, 
                                color: "#3b82f6",
                                fontSize: 12,
                                fontWeight: 500
                              }}
                              title="Subiendo a Drive..."
                            >
                              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ animation: "spin 1s linear infinite" }}>
                                <path d="M21 12a9 9 0 11-6.219-8.56"/>
                              </svg>
                              Subiendo...
                            </span>
                          );
                        case "COMPLETED":
                        case "PROCESSED":
                          return (
                            <span 
                              style={{ 
                                display: "inline-flex", 
                                alignItems: "center", 
                                gap: 4, 
                                color: "#22c55e",
                                fontSize: 12,
                                fontWeight: 500
                              }}
                              title="Procesamiento completado"
                            >
                              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                                <polyline points="20,6 9,17 4,12"/>
                              </svg>
                              Completado
                            </span>
                          );
                        case "FAILED_AI":
                          return (
                            <span 
                              style={{ 
                                display: "inline-flex", 
                                alignItems: "center", 
                                gap: 4, 
                                color: "#ef4444",
                                fontSize: 12,
                                fontWeight: 500
                              }}
                              title="Error en procesamiento IA"
                            >
                              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <circle cx="12" cy="12" r="10"/>
                                <line x1="15" y1="9" x2="9" y2="15"/>
                                <line x1="9" y1="9" x2="15" y2="15"/>
                              </svg>
                              Error IA
                            </span>
                          );
                        case "FAILED_DRIVE":
                          return (
                            <span 
                              style={{ 
                                display: "inline-flex", 
                                alignItems: "center", 
                                gap: 4, 
                                color: "#ef4444",
                                fontSize: 12,
                                fontWeight: 500
                              }}
                              title="Error al subir a Drive"
                            >
                              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <circle cx="12" cy="12" r="10"/>
                                <line x1="15" y1="9" x2="9" y2="15"/>
                                <line x1="9" y1="9" x2="15" y2="15"/>
                              </svg>
                              Error Drive
                            </span>
                          );
                        case "FAILED":
                          return (
                            <span 
                              style={{ 
                                display: "inline-flex", 
                                alignItems: "center", 
                                gap: 4, 
                                color: "#ef4444",
                                fontSize: 12,
                                fontWeight: 500
                              }}
                              title="Error en el procesamiento"
                            >
                              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <circle cx="12" cy="12" r="10"/>
                                <line x1="15" y1="9" x2="9" y2="15"/>
                                <line x1="9" y1="9" x2="15" y2="15"/>
                              </svg>
                              Error
                            </span>
                          );
                        default:
                          return <span style={{ color: "#94a3b8" }}>—</span>;
                      }
                    })()}
                  </td>
                </tr>
              ))}
              {ops.length === 0 && !opsError && (
                <tr>
                  <td
                    colSpan={6}
                    style={{
                      ...td,
                      textAlign: "center",
                      color: "#667085",
                    }}
                  >
                    Sin subidas recientes.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Controles de paginación inferior */}
        <div style={{ 
          display: "flex", 
          justifyContent: "space-between", 
          alignItems: "center",
          marginTop: "1rem",
          padding: "0.5rem 0"
        }}>
          <div style={{ fontSize: "14px", color: "#5b667a" }}>
            Total: {totalRecords} registro{totalRecords !== 1 ? "s" : ""}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <button
              onClick={() => handlePageChange(currentPage - 1)}
              disabled={currentPage === 1}
              style={{
                padding: "6px 12px",
                border: "1px solid #d1d5db",
                borderRadius: "6px",
                background: currentPage === 1 ? "#f3f4f6" : "white",
                color: currentPage === 1 ? "#9ca3af" : "#374151",
                cursor: currentPage === 1 ? "not-allowed" : "pointer",
                fontSize: "14px",
                display: "flex",
                alignItems: "center",
                gap: "4px"
              }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="15,18 9,12 15,6"/>
              </svg>
              Anterior
            </button>
            <span style={{ fontSize: "14px", color: "#5b667a", minWidth: "100px", textAlign: "center" }}>
              Página {currentPage} de {totalPages}
            </span>
            <button
              onClick={() => handlePageChange(currentPage + 1)}
              disabled={currentPage === totalPages}
              style={{
                padding: "6px 12px",
                border: "1px solid #d1d5db",
                borderRadius: "6px",
                background: currentPage === totalPages ? "#f3f4f6" : "white",
                color: currentPage === totalPages ? "#9ca3af" : "#374151",
                cursor: currentPage === totalPages ? "not-allowed" : "pointer",
                fontSize: "14px",
                display: "flex",
                alignItems: "center",
                gap: "4px"
              }}
            >
              Siguiente
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="9,18 15,12 9,6"/>
              </svg>
            </button>
          </div>
        </div>
      </section>

      {/* Modal de detalles de la operación */}
      {showDetailsModal && selectedOp && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
          onClick={(e) => {
            if (e.target === e.currentTarget) {
              setShowDetailsModal(false);
              setSelectedOp(null);
              setFacturaData(null);
              setFacturaId(null);
              setFacturaError(null);
            }
          }}
        >
          <div
            className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col"
            style={{
              boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.25)",
            }}
          >
            {/* Header */}
            <div className="flex items-center justify-between p-6 border-b border-gray-200">
              <h2 
                className="text-2xl font-bold"
                style={{
                  background: "linear-gradient(135deg, #3631a3 0%, #092342 100%)",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                  backgroundClip: "text",
                }}
              >
                Detalles de {selectedOp.tipo === "FACTURA" ? "Factura" : "Venta"}
              </h2>
              <button
                onClick={() => {
                  setShowDetailsModal(false);
                  setSelectedOp(null);
                  setFacturaData(null);
                  setFacturaId(null);
                  setFacturaError(null);
                }}
                className="text-gray-400 hover:text-gray-600 transition-colors"
                style={{
                  fontSize: "24px",
                  lineHeight: "1",
                  padding: "4px",
                  cursor: "pointer",
                }}
                aria-label="Cerrar"
              >
                ×
              </button>
            </div>

            {/* Contenido scrolleable */}
            <div className="overflow-y-auto p-6" style={{ maxHeight: "calc(90vh - 180px)" }}>
              {/* ID de factura en la parte superior izquierda */}
              {selectedOp.tipo === "FACTURA" && facturaId && (
                <div className="mb-4">
                  <span className="text-xs text-gray-400 font-mono">
                    ID Factura: {facturaId}
                  </span>
                </div>
              )}
              
              {loadingFactura ? (
                <div className="flex items-center justify-center py-8">
                  <div 
                    style={{
                      width: "32px",
                      height: "32px",
                      border: "3px solid #0875bb",
                      borderTopColor: "transparent",
                      borderRadius: "50%",
                      animation: "spin 1s linear infinite",
                    }}
                  />
                  <span className="ml-3 text-gray-600">Cargando datos de la factura...</span>
                </div>
              ) : selectedOp.tipo === "FACTURA" && facturaData ? (
                <div className="space-y-4">
                  {/* Fecha */}
                  <div>
                    <label className="text-sm font-semibold text-gray-600 block mb-1">
                      Fecha
                    </label>
                    <p className="text-gray-900">
                      {facturaData.fecha_dt 
                        ? new Date(facturaData.fecha_dt).toLocaleDateString("es-ES", {
                            year: "numeric",
                            month: "long",
                            day: "numeric",
                          })
                        : facturaData.fecha || "—"}
                    </p>
                  </div>

                  {/* Proveedor */}
                  <div>
                    <label className="text-sm font-semibold text-gray-600 block mb-1">
                      Proveedor
                    </label>
                    <p className="text-gray-900">{facturaData.proveedor || "—"}</p>
                  </div>

                  {/* VAT Number */}
                  {facturaData.supplier_vat_number && (
                    <div>
                      <label className="text-sm font-semibold text-gray-600 block mb-1">
                        VAT del proveedor
                      </label>
                      <p className="text-gray-900">{facturaData.supplier_vat_number}</p>
                    </div>
                  )}

                  {/* Importe sin IVA local */}
                  {facturaData.importe_sin_iva_local != null && (
                    <div>
                      <label className="text-sm font-semibold text-gray-600 block mb-1">
                        Importe sin IVA (local)
                      </label>
                      <p className="text-gray-900">
                        {facturaData.importe_sin_iva_local.toFixed(2)} {facturaData.moneda || "EUR"}
                      </p>
                    </div>
                  )}

                  {/* IVA local */}
                  {facturaData.iva_local != null && (
                    <div>
                      <label className="text-sm font-semibold text-gray-600 block mb-1">
                        % IVA local
                      </label>
                      <p className="text-gray-900">{facturaData.iva_local}%</p>
                    </div>
                  )}

                  {/* Total moneda local */}
                  {facturaData.total_moneda_local != null && (
                    <div>
                      <label className="text-sm font-semibold text-gray-600 block mb-1">
                        Total en moneda local
                      </label>
                      <p className="text-gray-900">
                        {facturaData.total_moneda_local.toFixed(2)} {facturaData.moneda || "EUR"}
                      </p>
                    </div>
                  )}

                  {/* Moneda */}
                  {facturaData.moneda && (
                    <div>
                      <label className="text-sm font-semibold text-gray-600 block mb-1">
                        Moneda
                      </label>
                      <p className="text-gray-900">{facturaData.moneda}</p>
                    </div>
                  )}

                  {/* Tarifa de cambio */}
                  {facturaData.tarifa_cambio != null && (
                    <div>
                      <label className="text-sm font-semibold text-gray-600 block mb-1">
                        Tarifa de cambio (€/moneda local)
                      </label>
                      <p className="text-gray-900">{facturaData.tarifa_cambio.toFixed(4)}</p>
                    </div>
                  )}

                  {/* Importe sin IVA (EUR) */}
                  {facturaData.importe_sin_iva_euro != null && (
                    <div>
                      <label className="text-sm font-semibold text-gray-600 block mb-1">
                        Importe sin IVA (EUR)
                      </label>
                      <p className="text-gray-900 font-semibold">
                        {facturaData.importe_sin_iva_euro.toFixed(2)} EUR
                      </p>
                    </div>
                  )}

                  {/* Importe total (EUR) */}
                  {facturaData.importe_total_euro != null && (
                    <div>
                      <label className="text-sm font-semibold text-gray-600 block mb-1">
                        Importe total (EUR)
                      </label>
                      <p className="text-gray-900 font-semibold text-lg">
                        {facturaData.importe_total_euro.toFixed(2)} EUR
                      </p>
                    </div>
                  )}

                  {/* País origen */}
                  {facturaData.pais_origen && (
                    <div>
                      <label className="text-sm font-semibold text-gray-600 block mb-1">
                        País de origen
                      </label>
                      <p className="text-gray-900">{facturaData.pais_origen}</p>
                    </div>
                  )}

                  {/* ID externo */}
                  {facturaData.id_ext && (
                    <div>
                      <label className="text-sm font-semibold text-gray-600 block mb-1">
                        ID externo
                      </label>
                      <p className="text-gray-900">{facturaData.id_ext}</p>
                    </div>
                  )}

                  {/* Categoría */}
                  {facturaData.categoria && (
                    <div>
                      <label className="text-sm font-semibold text-gray-600 block mb-1">
                        Categoría
                      </label>
                      <p className="text-gray-900">{facturaData.categoria}</p>
                    </div>
                  )}

                  {/* Descripción */}
                  {facturaData.descripcion && (
                    <div>
                      <label className="text-sm font-semibold text-gray-600 block mb-1">
                        Descripción
                      </label>
                      <p className="text-gray-900 break-words">{facturaData.descripcion}</p>
                    </div>
                  )}

                  {/* Notas */}
                  {facturaData.notas && (
                    <div>
                      <label className="text-sm font-semibold text-gray-600 block mb-1">
                        Notas
                      </label>
                      <p className="text-gray-900 break-words">{facturaData.notas}</p>
                    </div>
                  )}

                  {/* Enlace al archivo */}
                  {facturaData.ubicacion_factura && (
                    <div>
                      <label className="text-sm font-semibold text-gray-600 block mb-1">
                        Archivo
                      </label>
                      <button
                        type="button"
                        onClick={() => handleOpenFile(facturaData.ubicacion_factura)}
                        className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[#0875bb] text-white hover:bg-[#065a8f] transition-colors"
                      >
                        <span>📄</span>
                        <span>Ver archivo en Google Drive</span>
                      </button>
                    </div>
                  )}
                </div>
              ) : selectedOp.tipo === "FACTURA" && !loadingFactura ? (
                <div className="text-center py-8 text-gray-500">
                  <p>No se encontraron datos de la factura.</p>
                  <p className="text-sm mt-2">La factura puede estar aún procesándose.</p>
                  {!facturaId && (
                    <p className="text-xs mt-2 text-gray-400">La factura aún no tiene un ID asignado.</p>
                  )}
                  {facturaError && (
                    <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-left">
                      <p className="text-xs font-semibold text-red-700 mb-1">Error técnico:</p>
                      <p className="text-xs text-red-600 font-mono break-words">{facturaError}</p>
                    </div>
                  )}
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="text-center py-8 text-gray-500">
                    <p>Los detalles de ventas no están disponibles en este momento.</p>
                  </div>
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="flex justify-end gap-3 p-6 border-t border-gray-200 bg-gray-50">
              {/* Botón Continuar proceso - solo si está pendiente */}
              {selectedOp && ["UPLOADED", "QUEUED", "AI_COMPLETED", "FAILED_AI", "FAILED_DRIVE"].includes(selectedOp.status || "") && (
                <button
                  type="button"
                  onClick={() => {
                    const status = selectedOp.status;
                    const uploadId = selectedOp.id;
                    const fileName = selectedOp.original_filename;
                    
                    // Cerrar modal de detalles
                    setShowDetailsModal(false);
                    setSelectedOp(null);
                    
                    // Configurar el flujo de procesamiento
                    setCurrentUploadId(uploadId);
                    setCurrentFileName(fileName);
                    
                    // Determinar en qué paso continuar
                    if (status === "UPLOADED" || status === "QUEUED" || status === "FAILED_AI") {
                      setProcessingStep("confirm_ai");
                    } else if (status === "AI_COMPLETED" || status === "FAILED_DRIVE") {
                      // Para estos estados, necesitamos cargar ai_result si existe
                      setProcessingStep("confirm_drive");
                    }
                  }}
                  className="px-5 py-2 rounded-lg bg-amber-500 text-white hover:bg-amber-600 transition-colors font-medium inline-flex items-center gap-2"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polygon points="5,3 19,12 5,21 5,3"/>
                  </svg>
                  {selectedOp.status === "UPLOADED" || selectedOp.status === "QUEUED" || selectedOp.status === "FAILED_AI" 
                    ? "Procesar con IA" 
                    : "Subir a Drive"}
                </button>
              )}
              <button
                type="button"
                onClick={() => {
                  setShowDetailsModal(false);
                  setSelectedOp(null);
                }}
                className="px-5 py-2 rounded-lg bg-[#0875bb] text-white hover:bg-[#065a8f] transition-colors font-medium"
              >
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal de duplicado detectado */}
      {showDuplicateModal && duplicateInfo && (
        <div
          className="fixed inset-0 bg-black/60 flex items-center justify-center z-[60]"
          onClick={(e) => {
            if (e.target === e.currentTarget && !duplicateProcessing) {
              handleDuplicateCancel();
            }
          }}
        >
          <div
            className="bg-white rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden"
            style={{
              boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.4)",
              animation: "fadeIn 0.2s ease-out",
            }}
          >
            {/* Header con icono de advertencia */}
            <div className="bg-amber-50 p-6 border-b border-amber-100">
              <div className="flex items-center gap-4">
                <div 
                  className="w-14 h-14 rounded-full bg-amber-100 flex items-center justify-center"
                >
                  <svg 
                    width="28" 
                    height="28" 
                    viewBox="0 0 24 24" 
                    fill="none" 
                    stroke="#d97706" 
                    strokeWidth="2"
                    strokeLinecap="round" 
                    strokeLinejoin="round"
                  >
                    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                    <line x1="12" y1="9" x2="12" y2="13"/>
                    <line x1="12" y1="17" x2="12.01" y2="17"/>
                  </svg>
                </div>
                <div>
                  <h2 className="text-xl font-bold text-gray-900">
                    Documento duplicado detectado
                  </h2>
                  <p className="text-sm text-gray-600 mt-1">
                    El archivo que intentas subir ya existe en el sistema
                  </p>
                </div>
              </div>
            </div>

            {/* Contenido */}
            <div className="p-6 space-y-4">
              {/* Info del documento existente */}
              <div className="bg-gray-50 rounded-lg p-4 space-y-2">
                <div className="flex items-center gap-2">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#6b7280" strokeWidth="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14,2 14,8 20,8"/>
                  </svg>
                  <span className="font-medium text-gray-900">
                    {duplicateInfo.existing.filename}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-sm text-gray-600">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
                    <line x1="16" y1="2" x2="16" y2="6"/>
                    <line x1="8" y1="2" x2="8" y2="6"/>
                    <line x1="3" y1="10" x2="21" y2="10"/>
                  </svg>
                  <span>
                    Subido el: {duplicateInfo.existing.uploaded_at 
                      ? new Date(duplicateInfo.existing.uploaded_at).toLocaleDateString("es-ES", {
                          year: "numeric",
                          month: "long",
                          day: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })
                      : "—"}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  {duplicateInfo.existing.status === "COMPLETED" || duplicateInfo.existing.status === "PROCESSED" ? (
                    <>
                      <span className="text-green-600">✅</span>
                      <span className="text-gray-600">Estado: Procesado</span>
                    </>
                  ) : duplicateInfo.existing.status === "FAILED" || duplicateInfo.existing.status === "FAILED_AI" || duplicateInfo.existing.status === "FAILED_DRIVE" ? (
                    <>
                      <span className="text-red-600">❌</span>
                      <span className="text-gray-600">Estado: Error en procesamiento</span>
                    </>
                  ) : (
                    <>
                      <span className="text-amber-600">⏳</span>
                      <span className="text-gray-600">Estado: Pendiente de procesar</span>
                    </>
                  )}
                </div>
              </div>

              {/* Info de la factura si existe */}
              {duplicateInfo.factura && (
                <div className="bg-blue-50 rounded-lg p-4 border border-blue-100">
                  <h4 className="font-semibold text-blue-900 mb-3 flex items-center gap-2">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#1e40af" strokeWidth="2">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                      <path d="M14 2v6h6"/>
                      <line x1="16" y1="13" x2="8" y2="13"/>
                      <line x1="16" y1="17" x2="8" y2="17"/>
                      <line x1="10" y1="9" x2="8" y2="9"/>
                    </svg>
                    Datos de la factura:
                  </h4>
                  <div className="space-y-2 text-sm">
                    <div className="flex items-center gap-2">
                      <span className="text-gray-600">ID:</span>
                      <span className="font-mono font-medium text-gray-900">
                        {duplicateInfo.factura.id_factura || "—"}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-gray-600">Total:</span>
                      <span className="font-bold text-gray-900">
                        {duplicateInfo.factura.importe_total_euro != null 
                          ? `${duplicateInfo.factura.importe_total_euro.toFixed(2)} €`
                          : "—"}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-gray-600">Fecha factura:</span>
                      <span className="text-gray-900">
                        {duplicateInfo.factura.fecha || "—"}
                      </span>
                    </div>
                  </div>
                </div>
              )}

              <p className="text-gray-600 text-center">
                ¿Deseas subirlo de todos modos?
              </p>
            </div>

            {/* Footer con botones */}
            <div className="flex justify-end gap-3 p-6 bg-gray-50 border-t border-gray-100">
              <button
                type="button"
                onClick={handleDuplicateCancel}
                disabled={duplicateProcessing}
                className="px-4 py-2 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-100 transition-colors font-medium disabled:opacity-50"
              >
                Cancelar - omitir subida
              </button>
              <button
                type="button"
                onClick={handleDuplicateIgnore}
                disabled={duplicateProcessing}
                className="px-4 py-2 rounded-lg bg-amber-500 text-white hover:bg-amber-600 transition-colors font-medium disabled:opacity-50 flex items-center gap-2"
              >
                {duplicateProcessing ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Procesando...
                  </>
                ) : (
                  "Ignorar y subir"
                )}
              </button>
            </div>
          </div>

          <style>{`
            @keyframes fadeIn {
              from { opacity: 0; transform: scale(0.95); }
              to { opacity: 1; transform: scale(1); }
            }
          `}</style>
        </div>
      )}

      {/* Modal de selección de tipo de documento */}
      {showTypeSelectModal && pendingDropFiles.length > 0 && (
        <div
          className="fixed inset-0 bg-black/60 flex items-center justify-center z-[60]"
          onClick={(e) => {
            if (e.target === e.currentTarget) {
              setShowTypeSelectModal(false);
              setPendingDropFiles([]);
            }
          }}
        >
          <div
            className="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden"
            style={{
              boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.4)",
              animation: "fadeIn 0.2s ease-out",
            }}
          >
            {/* Header */}
            <div className="bg-blue-50 p-6 border-b border-blue-100">
              <div className="flex items-center gap-4">
                <div className="w-14 h-14 rounded-full bg-blue-100 flex items-center justify-center">
                  <svg 
                    width="28" 
                    height="28" 
                    viewBox="0 0 24 24" 
                    fill="none" 
                    stroke="#2563eb" 
                    strokeWidth="2"
                    strokeLinecap="round" 
                    strokeLinejoin="round"
                  >
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14,2 14,8 20,8"/>
                    <line x1="12" y1="11" x2="12" y2="17"/>
                    <line x1="9" y1="14" x2="15" y2="14"/>
                  </svg>
                </div>
                <div>
                  <h2 className="text-xl font-bold text-gray-900">
                    Selecciona el tipo de documento
                  </h2>
                  <p className="text-sm text-gray-600 mt-1">
                    {pendingDropFiles.length === 1 
                      ? `Has arrastrado: ${pendingDropFiles[0].name}`
                      : `Has arrastrado ${pendingDropFiles.length} archivos`
                    }
                  </p>
                </div>
              </div>
            </div>

            {/* Contenido */}
            <div className="p-6">
              <p className="text-gray-600 text-center mb-6">
                ¿Qué tipo de documentos son?
              </p>
              
              <div className="flex gap-4 justify-center">
                <button
                  type="button"
                  onClick={() => handleTypeSelect("factura")}
                  className="flex-1 py-4 px-6 rounded-xl border-2 border-blue-200 bg-blue-50 hover:bg-blue-100 hover:border-blue-400 transition-all font-semibold text-blue-700 flex flex-col items-center gap-2"
                >
                  <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14,2 14,8 20,8"/>
                    <line x1="16" y1="13" x2="8" y2="13"/>
                    <line x1="16" y1="17" x2="8" y2="17"/>
                    <polyline points="10,9 9,9 8,9"/>
                  </svg>
                  Factura
                </button>
                
                <button
                  type="button"
                  onClick={() => handleTypeSelect("venta")}
                  className="flex-1 py-4 px-6 rounded-xl border-2 border-green-200 bg-green-50 hover:bg-green-100 hover:border-green-400 transition-all font-semibold text-green-700 flex flex-col items-center gap-2"
                >
                  <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="9" cy="21" r="1"/>
                    <circle cx="20" cy="21" r="1"/>
                    <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/>
                  </svg>
                  Venta
                </button>
              </div>
            </div>

            {/* Footer */}
            <div className="flex justify-center p-4 bg-gray-50 border-t border-gray-100">
              <button
                type="button"
                onClick={() => {
                  setShowTypeSelectModal(false);
                  setPendingDropFiles([]);
                }}
                className="px-4 py-2 rounded-lg text-gray-600 hover:text-gray-800 hover:bg-gray-100 transition-colors font-medium"
              >
                Cancelar
              </button>
            </div>
          </div>

          <style>{`
            @keyframes fadeIn {
              from { opacity: 0; transform: scale(0.95); }
              to { opacity: 1; transform: scale(1); }
            }
          `}</style>
        </div>
      )}
    </div>
  );
}

/* estilos tabla histórico */
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