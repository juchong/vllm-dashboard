import { useState, useEffect, useRef } from 'react'
import api from '../services/api'
import ModelList from '../components/models/ModelList'
import ModelDownload from '../components/models/ModelDownload'
import ModelConfigEditor from '../components/models/ModelConfigEditor'
import LoadingSpinner from '../components/common/LoadingSpinner'
import Alert from '../components/common/Alert'
import { ModelInfo } from '../types/models'

interface ActiveDownload {
  id: string
  model_name: string
  status: 'pending' | 'downloading' | 'completed' | 'failed' | 'cancelled' | 'resumable'
  progress: string
  error: string | null
  started_at: string
  downloaded_size: number
  downloaded_size_human: string
  expected_size: number | null
  expected_size_human: string | null
  progress_pct: number | null
  speed_bps: number
  speed_human: string | null
  eta_seconds: number | null
  elapsed_seconds: number
}

const Models = () => {
  const [models, setModels] = useState<ModelInfo[]>([])
  const [selectedModel, setSelectedModel] = useState<string | null>(null)
  const [modelConfig, setModelConfig] = useState<any>(null)
  const [modelConfigPath, setModelConfigPath] = useState<string | null>(null)
  const [detectedModelType, setDetectedModelType] = useState<string | undefined>(undefined)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showDownload, setShowDownload] = useState(false)
  const [activeDownloads, setActiveDownloads] = useState<ActiveDownload[]>([])
  const pollIntervalRef = useRef<number | null>(null)
  const prevTaskIdsRef = useRef<Set<string>>(new Set())

  const fetchModels = async () => {
    setLoading(true)
    try {
      const response = await api.get('/models/list')
      setModels(response.data.data)
    } catch (err) {
      setError('Failed to fetch models')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const fetchActiveDownloads = async () => {
    try {
      const response = await api.get('/models/download/active')
      const downloads = response.data.data as ActiveDownload[]
      setActiveDownloads(downloads)
      
      const currentIds = new Set(downloads.map(d => d.id))
      const prevIds = prevTaskIdsRef.current
      
      // If any previously-tracked task ID disappeared, a download completed
      for (const id of prevIds) {
        if (!currentIds.has(id)) {
          fetchModels()
          break
        }
      }
      prevTaskIdsRef.current = currentIds
    } catch (err) {
      console.error('Failed to fetch active downloads:', err)
    }
  }

  const fetchModelConfig = async (modelName: string) => {
    try {
      const response = await api.get(`/config/model/${modelName}`)
      const data = response.data.data || {}
      setModelConfig(data.config || {})
      setModelConfigPath(data.config_path || null)
      setDetectedModelType(data.detected_model_type)
    } catch (err) {
      console.error('Failed to fetch model config:', err)
      setModelConfig({})
      setModelConfigPath(null)
      setDetectedModelType(undefined)
    }
  }

  const handleDownloadSuccess = async () => {
    await fetchModels()
    await fetchActiveDownloads()
  }

  const handleCancelDownload = async (taskId: string) => {
    if (!confirm('Are you sure you want to cancel this download? Partial files will be deleted.')) return
    
    try {
      await api.post(`/models/download/cancel/${taskId}`)
      await fetchActiveDownloads()
      await fetchModels()
    } catch (err: any) {
      const detail = err.response?.data?.detail || 'Failed to cancel download'
      setError(detail)
      console.error(err)
    }
  }

  const handleDelete = async (modelPath: string) => {
    if (!confirm('Are you sure you want to delete this model?')) return
    
    setLoading(true)
    try {
      // Don't encode - FastAPI path parameter handles slashes natively
      await api.delete(`/models/${modelPath}`)
      await fetchModels()
    } catch (err: any) {
      const detail = err.response?.data?.detail || 'Failed to delete model'
      setError(detail)
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const handleRename = async (oldPath: string, oldName: string, newName: string) => {
    setLoading(true)
    try {
      // Derive models base directory from old path and old name
      // e.g., oldPath=/models/openai/gpt-oss-20b, oldName=openai/gpt-oss-20b -> baseDir=/models
      const baseDir = oldPath.substring(0, oldPath.length - oldName.length - 1)
      const newPath = `${baseDir}/${newName}`
      
      await api.post('/models/rename', { old_path: oldPath, new_path: newPath })
      await fetchModels()
    } catch (err: any) {
      const detail = err.response?.data?.detail || 'Failed to rename model'
      setError(detail)
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const handleSaveConfig = async (modelName: string, config: any) => {
    await api.post('/config/save', { model_name: modelName, config })
    await fetchModelConfig(modelName)
  }

  const formatElapsedTime = (seconds: number) => {
    if (seconds < 60) return `${seconds}s`
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`
    return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`
  }

  // Get list of model names currently being downloaded
  const downloadingModelNames = activeDownloads.map(d => d.model_name)

  useEffect(() => {
    fetchModels()
    fetchActiveDownloads()
  }, [])

  // Only poll when there are active downloads
  useEffect(() => {
    if (activeDownloads.length > 0) {
      pollIntervalRef.current = window.setInterval(fetchActiveDownloads, 3000)
    } else {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current)
        pollIntervalRef.current = null
      }
    }
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current)
      }
    }
  }, [activeDownloads.length > 0])

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-heading">Models</h1>
        <button onClick={() => setShowDownload(true)} className="dashboard-button">Download Model</button>
      </div>

      {/* Active Downloads Section */}
      {activeDownloads.length > 0 && (
        <div className="alert alert-info">
          <h2 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <div className="animate-spin rounded-full h-4 w-4 border-2 border-blue-600 border-t-transparent"></div>
            Active Downloads ({activeDownloads.length})
          </h2>
          <div className="space-y-2">
            {activeDownloads.map((download) => (
              <div key={download.id} className="surface-primary rounded-md p-3 border border-blue-100">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="font-medium text-heading">{download.model_name}</span>
                    <span className="text-xs text-dim ml-2">({download.id})</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="text-right text-sm">
                      <div className="text-blue-600 font-medium">
                        {download.downloaded_size_human || '0 B'}
                        {download.expected_size_human && ` / ${download.expected_size_human}`}
                      </div>
                      <div className="text-dim text-xs space-x-2">
                        <span>{formatElapsedTime(download.elapsed_seconds)}</span>
                        {download.speed_human && <span>{download.speed_human}</span>}
                        {download.eta_seconds != null && <span>ETA: {formatElapsedTime(download.eta_seconds)}</span>}
                      </div>
                    </div>
                    <button
                      onClick={() => handleCancelDownload(download.id)}
                      className="dashboard-button-danger btn-xs"
                      title="Cancel download"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
                {download.progress_pct != null && (
                  <div className="mt-2 w-full bg-gray-200 rounded-full h-2">
                    <div
                      className="bg-blue-600 h-2 rounded-full transition-all"
                      style={{ width: `${download.progress_pct}%` }}
                    />
                  </div>
                )}
                <div className="text-sm text-body mt-1">
                  {download.status === 'pending' ? 'Queued...' :
                   download.status === 'downloading' ? (download.progress_pct != null ? `${download.progress_pct}% complete` : 'Downloading...') :
                   download.progress}
                </div>
                {download.error && (
                  <div className="text-sm text-red-600 mt-1">{download.error}</div>
                )}
              </div>
            ))}
          </div>
          <p className="text-xs text-blue-700 mt-3">
            Downloads continue in the background. You can close this page and return later.
          </p>
        </div>
      )}

      {loading && <LoadingSpinner message="Loading models..." />}
      {error && <Alert type="error">Error: {error}</Alert>}

      <ModelList 
        models={models}
        downloadingModels={downloadingModelNames}
        onDelete={handleDelete}
        onRename={handleRename}
        onViewConfig={(modelName) => {
          setSelectedModel(modelName)
          setModelConfig(null)
          fetchModelConfig(modelName)
        }}
      />

      {showDownload && (
        <ModelDownload 
          onSuccess={handleDownloadSuccess}
          onClose={() => setShowDownload(false)}
        />
      )}

      {selectedModel && (
        <div className="modal-overlay">
          <div className="modal-container max-w-2xl max-h-[80vh] flex flex-col">
            <div className="modal-header">
              <h2 className="modal-title">
                Configuration: {selectedModel}
              </h2>
              <button 
                onClick={() => { setSelectedModel(null); setModelConfig(null); setDetectedModelType(undefined) }} 
                className="modal-close"
              >
                &times;
              </button>
            </div>
            <div className="modal-body flex-1 overflow-auto">
              <ModelConfigEditor 
                modelName={selectedModel}
                config={modelConfig}
                configPath={modelConfigPath}
                detectedModelType={detectedModelType}
                onSave={handleSaveConfig}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default Models
