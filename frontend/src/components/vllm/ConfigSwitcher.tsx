import { useState, useEffect, useCallback } from 'react'
import api from '../../services/api'
import EnvEditor from './EnvEditor'
import ModelConfigEditor from '../models/ModelConfigEditor'

interface VLLMConfig {
  filename: string
  name: string
  model: string
  model_type: string
  max_model_len: number
  tensor_parallel_size: number
  num_experts?: number
  quant_method?: string | null
  architecture?: string
}

interface VLLMStatus {
  status: string
  running: boolean
  id?: string
  health?: string
  error?: string
}

interface ActiveConfig {
  config: any
  filename: string | null
  model_type: string
  num_experts?: number
  quant_method?: string | null
  architecture?: string
}

const ConfigSwitcher = () => {
  const [configs, setConfigs] = useState<VLLMConfig[]>([])
  const [activeConfig, setActiveConfig] = useState<ActiveConfig | null>(null)
  const [vllmStatus, setVllmStatus] = useState<VLLMStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [switching, setSwitching] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showEnvEditor, setShowEnvEditor] = useState(false)
  const [editingModel, setEditingModel] = useState<string | null>(null)
  const [editingConfig, setEditingConfig] = useState<any>(null)
  const [editingConfigPath, setEditingConfigPath] = useState<string | null>(null)
  const [editingDetectedType, setEditingDetectedType] = useState<string | undefined>(undefined)

  const fetchData = useCallback(async () => {
    try {
      const [configsRes, activeRes, statusRes] = await Promise.all([
        api.get('/vllm/configs'),
        api.get('/vllm/active'),
        api.get('/vllm/status'),
      ])
      
      setConfigs(configsRes.data.data || [])
      setActiveConfig(activeRes.data.data)
      setVllmStatus(statusRes.data.data)
      setError(null)
    } catch (err) {
      setError('Failed to fetch vLLM configuration')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
    // Refresh status every 10 seconds
    const interval = setInterval(fetchData, 10000)
    return () => clearInterval(interval)
  }, [fetchData])

  const handleSwitch = async (configFilename: string) => {
    if (switching) return
    
    const config = configs.find(c => c.filename === configFilename)
    if (!config) return
    
    if (!confirm(`Switch to ${config.name}?\n\nThis will restart the vLLM server and may take a few minutes.`)) {
      return
    }
    
    setSwitching(true)
    setError(null)
    
    try {
      await api.post('/vllm/switch', { config_filename: configFilename })
      // Wait a moment for container to start recreating
      await new Promise(resolve => setTimeout(resolve, 2000))
      await fetchData()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to switch configuration')
    } finally {
      setSwitching(false)
    }
  }

  const handleRestart = async () => {
    if (switching) return
    
    if (!confirm('Restart vLLM server?')) return
    
    setSwitching(true)
    try {
      await api.post('/vllm/restart')
      await new Promise(resolve => setTimeout(resolve, 2000))
      await fetchData()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to restart')
    } finally {
      setSwitching(false)
    }
  }

  const handleReload = async () => {
    if (switching) return
    
    if (!confirm('Reload active configuration?\n\nThis re-reads the config YAML, regenerates env vars, and restarts the vLLM server.')) return
    
    setSwitching(true)
    setError(null)
    try {
      await api.post('/vllm/reload')
      await new Promise(resolve => setTimeout(resolve, 2000))
      await fetchData()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to reload configuration')
    } finally {
      setSwitching(false)
    }
  }

  const handleStop = async () => {
    if (switching) return
    
    if (!confirm('Stop vLLM server?')) return
    
    setSwitching(true)
    try {
      await api.post('/vllm/stop')
      await fetchData()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to stop')
    } finally {
      setSwitching(false)
    }
  }

  const handleStart = async () => {
    if (switching) return
    
    setSwitching(true)
    try {
      await api.post('/vllm/start')
      await fetchData()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to start')
    } finally {
      setSwitching(false)
    }
  }

  const handleOpenConfig = async (modelName: string) => {
    try {
      const response = await api.get(`/config/model/${modelName}`)
      const data = response.data.data || {}
      setEditingConfig(data.config || {})
      setEditingConfigPath(data.config_path || null)
      setEditingDetectedType(data.detected_model_type)
      setEditingModel(modelName)
    } catch (err) {
      console.error('Failed to fetch model config:', err)
      setEditingConfig({})
      setEditingConfigPath(null)
      setEditingDetectedType(undefined)
      setEditingModel(modelName)
    }
  }

  const handleSaveConfig = async (modelName: string, config: any) => {
    await api.post('/config/save', { model_name: modelName, config })
    await handleOpenConfig(modelName)
    await fetchData()
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running': return 'bg-green-100 text-green-800'
      case 'exited': return 'bg-red-100 text-red-800'
      case 'restarting': return 'bg-yellow-100 text-yellow-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  const getHealthColor = (health: string) => {
    switch (health) {
      case 'healthy': return 'text-green-600'
      case 'unhealthy': return 'text-red-600'
      case 'starting': return 'text-yellow-600'
      default: return 'text-body'
    }
  }

  const modelTypeBadge = (type: string) => {
    switch (type) {
      // MoE types
      case 'moe_full': return { cls: 'badge-purple', label: 'MoE' }
      case 'moe_fp8': return { cls: 'badge-purple', label: 'MoE FP8' }
      case 'moe_fp4': return { cls: 'badge-amber', label: 'MoE FP4' }
      // Dense types
      case 'dense_full': return { cls: 'badge-blue', label: 'Dense' }
      case 'dense_fp8': return { cls: 'badge-teal', label: 'Dense FP8' }
      case 'dense_int8': return { cls: 'badge-green', label: 'Dense INT8' }
      case 'dense_int4': return { cls: 'badge-green', label: 'Dense INT4' }
      // Legacy fallback
      case 'dense': return { cls: 'badge-blue', label: 'Dense' }
      default: return { cls: 'badge-gray', label: type || 'Unknown' }
    }
  }

  const metaDetail = (numExperts?: number, quantMethod?: string | null) => {
    const parts: string[] = []
    if (numExperts && numExperts > 0) parts.push(`${numExperts}E`)
    if (quantMethod) parts.push(quantMethod.toUpperCase())
    return parts.length > 0 ? parts.join(' · ') : null
  }

  if (loading) {
    return (
      <div className="dashboard-card">
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <span className="ml-3 text-body">Loading configurations...</span>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Status Card */}
      <div className="dashboard-card">
        <h2 className="text-lg font-semibold text-heading mb-4">vLLM Server Status</h2>
        
        <div className="border border-default rounded-lg p-4">
          <div className="flex justify-between items-start mb-3">
            <div>
              <h3 className="font-semibold text-heading">
                {activeConfig?.config?.served_model_name || 'No model loaded'}
              </h3>
              {activeConfig?.config && (
                <p className="text-sm text-dim">{activeConfig.config.model}</p>
              )}
            </div>
            <div className="flex items-center gap-2">
              {vllmStatus && (
                <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${getStatusColor(vllmStatus.status)}`}>
                  {vllmStatus.status}
                </span>
              )}
              {vllmStatus?.health && vllmStatus.health !== 'unknown' && (
                <span className={`text-xs ${getHealthColor(vllmStatus.health)}`}>
                  ({vllmStatus.health})
                </span>
              )}
            </div>
          </div>
          
          {activeConfig?.config && (
            <div className="flex flex-wrap items-center gap-4 text-xs text-dim mb-4">
              <span>Context: {activeConfig.config.max_model_len ? `${(activeConfig.config.max_model_len / 1024).toFixed(0)}K` : 'N/A'}</span>
              <span>TP: {activeConfig.config.tensor_parallel_size}</span>
              <span className={`badge ${modelTypeBadge(activeConfig.model_type).cls}`}>
                {modelTypeBadge(activeConfig.model_type).label}
              </span>
              {metaDetail(activeConfig.num_experts, activeConfig.quant_method) && (
                <span>{metaDetail(activeConfig.num_experts, activeConfig.quant_method)}</span>
              )}
            </div>
          )}

          <div className="flex gap-2 pt-3 border-t border-default">
            {vllmStatus?.running ? (
              <>
                <button 
                  onClick={handleReload}
                  disabled={switching || !activeConfig?.filename}
                  className="dashboard-button btn-sm disabled:opacity-50 disabled:cursor-not-allowed"
                  title="Re-read config YAML, regenerate env vars, and restart"
                >
                  {switching ? 'Working...' : 'Reload Config'}
                </button>
                <button 
                  onClick={handleRestart}
                  disabled={switching}
                  className="dashboard-button-secondary btn-sm disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Restart
                </button>
                <button 
                  onClick={handleStop}
                  disabled={switching}
                  className="dashboard-button-danger btn-sm disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Stop
                </button>
              </>
            ) : (
              <button 
                onClick={handleStart}
                disabled={switching}
                className="dashboard-button btn-sm disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {switching ? 'Starting...' : 'Start'}
              </button>
            )}
            <button 
              onClick={() => setShowEnvEditor(true)}
              className="dashboard-button-secondary btn-sm ml-auto"
            >
              Environment
            </button>
          </div>
        </div>
      </div>

      {/* Environment Editor Modal */}
      {showEnvEditor && (
        <EnvEditor onClose={() => setShowEnvEditor(false)} />
      )}

      {/* Model Config Editor Modal */}
      {editingModel && (
        <div className="modal-overlay">
          <div className="modal-container max-w-2xl max-h-[80vh] flex flex-col">
            <div className="modal-header">
              <h2 className="modal-title">
                Configuration: {editingModel}
              </h2>
              <button 
                onClick={() => { setEditingModel(null); setEditingConfig(null); setEditingDetectedType(undefined) }} 
                className="modal-close"
              >
                &times;
              </button>
            </div>
            <div className="modal-body flex-1 overflow-auto">
              <ModelConfigEditor 
                modelName={editingModel}
                config={editingConfig}
                configPath={editingConfigPath}
                detectedModelType={editingDetectedType}
                onSave={handleSaveConfig}
              />
            </div>
          </div>
        </div>
      )}

      {error && (
        <div className="alert alert-error">
          {error}
        </div>
      )}

      {/* Available Configurations */}
      <div className="dashboard-card">
        <h2 className="text-lg font-semibold text-heading mb-4">Available Configurations</h2>
        
        {configs.length === 0 ? (
          <div className="text-dim text-center py-8">
            No configurations found. Add YAML config files to your vLLM configs directory.
          </div>
        ) : (
          <div className="space-y-3">
            {configs.map((config) => {
              const isActive = activeConfig?.filename === config.filename
              
              return (
                <div 
                  key={config.filename}
                  className={`border rounded-lg p-4 transition-colors ${
                    isActive 
                      ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30' 
                      : 'border-default hover:border-gray-300 dark:hover:border-gray-600'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h3 className="font-semibold text-heading">{config.name}</h3>
                        {isActive && (
                          <span className="badge bg-blue-500 text-white">Active</span>
                        )}
                        <span className={`badge ${modelTypeBadge(config.model_type).cls}`}>
                          {modelTypeBadge(config.model_type).label}
                        </span>
                      </div>
                      <div className="text-sm text-body mt-1 truncate">{config.model}</div>
                      <div className="flex gap-4 mt-2 text-xs text-dim">
                        <span>Context: {config.max_model_len ? `${(config.max_model_len / 1024).toFixed(0)}K` : 'N/A'}</span>
                        <span>TP: {config.tensor_parallel_size}</span>
                        {metaDetail(config.num_experts, config.quant_method) && (
                          <span>{metaDetail(config.num_experts, config.quant_method)}</span>
                        )}
                        <span className="text-faint">{config.filename}</span>
                      </div>
                    </div>
                    
                    <div className="flex flex-col gap-1.5 ml-4 shrink-0">
                      {!isActive && (
                        <button
                          onClick={() => handleSwitch(config.filename)}
                          disabled={switching}
                          className="dashboard-button btn-sm disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
                        >
                          {switching ? 'Switching...' : 'Activate'}
                        </button>
                      )}
                      <button
                        onClick={() => handleOpenConfig(config.model.replace(/^\/models\//, ''))}
                        className="dashboard-button-secondary btn-sm whitespace-nowrap"
                      >
                        Config
                      </button>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {switching && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="surface-primary rounded-lg p-6 max-w-sm mx-4">
            <div className="flex items-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
              <span className="ml-3 text-body">
                Applying configuration...<br/>
                <span className="text-sm text-dim">This may take a few minutes</span>
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default ConfigSwitcher
